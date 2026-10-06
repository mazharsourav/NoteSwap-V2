"""
Feature rules (Phase 3): inbox forms, ratings, provider applications,
NoteSolve request lifecycle, note types and the message bar.
"""
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from core.models import (
    InboxMessage, Note, NoteSolveSolution, ProviderRequest, Rating, Review,
)
from core.templatetags.custom_filters import filled_stars
from core.tests.test_security import SecurityTestCase, make_user, pdf_upload, png_bytes

APPLICATION = {
    'first_name': 'A', 'last_name': 'B', 'email': 'a@example.com', 'university': 'Test U', 'department': 'CSE',
    'cgpa': '3.50', 'gender': 'other', 'nationality': 'BD', 'profession': 'student', 'address': 'x',
    'phone_number': '1',
}


class InboxTests(SecurityTestCase):
    def test_contact_form_saves_for_anonymous_visitors(self):
        response = self.client_for(None).post(reverse('contact'), {
            'name': 'Visitor', 'email': 'v@example.com', 'message': 'Hello there',
        })
        self.assertRedirects(response, reverse('contact'))
        message = InboxMessage.objects.get()
        self.assertEqual((message.kind, message.name, message.user), ('contact', 'Visitor', None))

    def test_feedback_and_questions_are_saved_with_the_user(self):
        client = self.client_for(self.basic)
        client.post(reverse('send_feedback'), {'name': 'B', 'email': 'b@example.com', 'message': 'Great site'})
        client.post(reverse('ask_question'), {'name': 'B', 'email': 'b@example.com', 'message': 'How do I upload?'})
        kinds = set(InboxMessage.objects.filter(user=self.basic).values_list('kind', flat=True))
        self.assertEqual(kinds, {'feedback', 'question'})

    def test_forms_are_prefilled_for_signed_in_users(self):
        self.basic.email = 'basic@example.com'
        self.basic.save()
        response = self.client_for(self.basic).get(reverse('contact'))
        self.assertEqual(response.context['form'].initial['email'], 'basic@example.com')

    def test_invalid_submission_shows_errors_instead_of_crashing(self):
        response = self.client_for(None).post(reverse('contact'), {'name': '', 'email': 'nope', 'message': ''})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(InboxMessage.objects.exists())


class RemovedAndGuardedRoutesTests(SecurityTestCase):
    def test_buy_premium_route_is_gone(self):
        with self.assertRaises(NoReverseMatch):
            reverse('buy_premium')
        self.assertEqual(self.client_for(self.basic).get('/buy-premium/').status_code, 404)

    def test_anonymous_review_post_goes_to_login(self):
        response = self.client_for(None).post(reverse('home'), {'comment': 'hi'})
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('account_login'), response['Location'])
        self.assertFalse(Review.objects.exists())


class RatingTests(SecurityTestCase):
    def rate(self, user, score, note=None):
        note = note or self.verified_note
        return self.client_for(user).post(reverse('rate_note', args=[note.id]), {'score': score})

    def test_rating_is_saved_and_can_be_changed(self):
        self.rate(self.basic, 3)
        self.rate(self.basic, 5)
        self.assertEqual(list(Rating.objects.filter(user=self.basic).values_list('score', flat=True)), [5])

    def test_out_of_range_and_garbage_scores_are_rejected(self):
        for score in ('0', '6', '999', 'abc', ''):
            response = self.rate(self.basic, score)
            self.assertEqual(response.status_code, 302, score)
        self.assertFalse(Rating.objects.exists())

    def test_providers_cannot_rate_their_own_notes(self):
        self.rate(self.provider, 5)
        self.assertFalse(Rating.objects.exists())

    def test_database_allows_one_rating_per_user_and_note(self):
        Rating.objects.create(note=self.verified_note, user=self.basic, score=4)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Rating.objects.create(note=self.verified_note, user=self.basic, score=2)

    def test_note_page_shows_the_users_rating_and_filled_stars(self):
        self.rate(self.basic, 4)
        response = self.client_for(self.basic).get(reverse('note_detail', args=[self.verified_note.id]))
        self.assertEqual(response.context['user_rating'], 4)
        self.assertContains(response, 'name="score" id="score-4" value="4" checked')
        self.assertContains(response, 'Update rating')
        self.assertEqual(response.content.decode().count('<svg class="star is-on"'), 4)  # the average, 4.0

    def test_owner_sees_no_rating_form(self):
        response = self.client_for(self.provider).get(reverse('note_detail', args=[self.verified_note.id]))
        self.assertNotContains(response, 'name="score"')
        self.assertContains(response, "You can't rate your own note.")

    def test_filled_stars_rounds_half_up(self):
        self.assertEqual([filled_stars(v) for v in (None, 0, 2.4, 2.5, 4.9, 7)], [0, 0, 2, 3, 5, 5])

    def test_notesolve_solution_rating_must_be_1_to_5(self):
        self.make_premium(self.basic)
        client = self.client_for(self.basic)
        client.post(reverse('notesolve_dashboard'), {'rate_solution_id': self.solution.id, 'rating': '9'})
        self.solution.refresh_from_db()
        self.assertIsNone(self.solution.rating)
        client.post(reverse('notesolve_dashboard'), {'rate_solution_id': self.solution.id, 'rating': '5'})
        self.solution.refresh_from_db()
        self.assertEqual(self.solution.rating, 5)


class ProviderApplicationTests(SecurityTestCase):
    def reject(self, reason='Please add your transcript.'):
        return self.client_for(self.moderator).post(
            reverse('provider_request_action', args=[self.application.id, 'reject']), {'reason': reason})

    def test_pending_application_shows_status_instead_of_form(self):
        response = self.client_for(self.applicant).get(reverse('become_provider'))
        self.assertEqual(response.context['state'], 'pending')
        self.assertIsNone(response.context['form'])

    def test_rejection_needs_a_reason(self):
        self.reject(reason='   ')
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'pending')

    def test_rejection_reason_and_cooldown_are_shown(self):
        self.reject()
        response = self.client_for(self.applicant).get(reverse('become_provider'))
        self.assertEqual(response.context['state'], 'cooldown')
        self.assertContains(response, 'Please add your transcript.')
        # posting the form during the cooldown changes nothing
        self.client_for(self.applicant).post(reverse('become_provider'), APPLICATION)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'rejected')

    def test_can_reapply_after_30_days_without_crashing(self):
        self.reject()
        ProviderRequest.objects.filter(id=self.application.id).update(
            reviewed_at=timezone.now() - timedelta(days=31))
        response = self.client_for(self.applicant).post(reverse('become_provider'), APPLICATION)
        self.assertEqual(response.status_code, 302)
        self.application.refresh_from_db()
        self.assertEqual(self.application.status, 'pending')
        self.assertEqual(self.application.rejection_reason, '')
        self.assertEqual(ProviderRequest.objects.filter(user=self.applicant).count(), 1)

    def test_accept_promotes_the_user(self):
        self.client_for(self.moderator).post(reverse('provider_request_action', args=[self.application.id, 'accept']))
        self.applicant.refresh_from_db()
        self.assertEqual(self.applicant.user_type, 'provider')
        response = self.client_for(self.applicant).get(reverse('become_provider'))
        self.assertEqual(response.context['state'], 'accepted')

    def test_queue_lists_only_pending_applications(self):
        self.reject()
        response = self.client_for(self.moderator).get(reverse('provider_requests'))
        self.assertEqual(list(response.context['requests']), [])

    def test_first_application_works(self):
        newcomer = make_user('newcomer')
        self.client_for(newcomer).post(reverse('become_provider'), APPLICATION)
        self.assertEqual(ProviderRequest.objects.get(user=newcomer).status, 'pending')


class NoteSolveLifecycleTests(SecurityTestCase):
    def setUp(self):
        NoteSolveSolution.objects.filter(id=self.solution.id).delete()  # start from an unanswered request
        self.make_premium(self.basic)
        self.url = reverse('solve_request', args=[self.solve_request.id])

    def test_reject_keeps_the_request_with_a_reason(self):
        self.client_for(self.provider).post(self.url, {'action': 'reject', 'reason': 'Outside my subject.'})
        self.solve_request.refresh_from_db()
        self.assertEqual(self.solve_request.status, 'rejected')
        self.assertEqual(self.solve_request.rejection_reason, 'Outside my subject.')

    def test_reject_needs_a_reason(self):
        self.client_for(self.provider).post(self.url, {'action': 'reject', 'reason': ''})
        self.solve_request.refresh_from_db()
        self.assertEqual(self.solve_request.status, 'pending')

    def test_student_sees_the_reason_and_can_resend(self):
        self.client_for(self.provider).post(self.url, {'action': 'reject', 'reason': 'Outside my subject.'})
        student = self.client_for(self.basic)
        response = student.get(reverse('notesolve_dashboard'))
        self.assertContains(response, 'Outside my subject.')
        self.assertContains(response, reverse('resend_solve_request', args=[self.solve_request.id]))

        student.post(reverse('resend_solve_request', args=[self.solve_request.id]),
                     {'provider_id': self.other_provider.id})
        self.solve_request.refresh_from_db()
        self.assertEqual((self.solve_request.status, self.solve_request.requested_to), ('pending', self.other_provider))
        # the new provider can open it; the one who rejected it no longer can
        self.assertEqual(self.client_for(self.other_provider).get(self.url).status_code, 200)
        self.assertEqual(self.client_for(self.provider).get(self.url).status_code, 404)

    def test_cannot_resend_to_the_same_provider_or_a_pending_request(self):
        resend = reverse('resend_solve_request', args=[self.solve_request.id])
        self.assertEqual(self.client_for(self.basic).post(resend, {'provider_id': self.other_provider.id}).status_code, 404)
        self.client_for(self.provider).post(self.url, {'action': 'reject', 'reason': 'No.'})
        self.client_for(self.basic).post(resend, {'provider_id': self.provider.id})
        self.solve_request.refresh_from_db()
        self.assertEqual(self.solve_request.status, 'rejected')

    def test_solving_marks_the_request_solved(self):
        self.client_for(self.provider).post(self.url, {'solution_text': 'Here you go.'})
        self.solve_request.refresh_from_db()
        self.assertEqual(self.solve_request.status, 'solved')
        # answered requests leave the provider's inbox and can't be answered again
        inbox = self.client_for(self.provider).get(reverse('provider_solved_requests'))
        self.assertNotIn(self.solve_request, inbox.context['received_requests'])
        self.assertEqual(self.client_for(self.provider).get(self.url).status_code, 302)

    def test_rejected_requests_leave_the_provider_inbox(self):
        self.client_for(self.provider).post(self.url, {'action': 'reject', 'reason': 'No.'})
        inbox = self.client_for(self.provider).get(reverse('provider_solved_requests'))
        self.assertNotIn(self.solve_request, inbox.context['received_requests'])


class NoteTypeTests(SecurityTestCase):
    def upload(self, upload):
        return self.client_for(self.provider).post(reverse('upload_note'), {
            'name': 'Auto type', 'caption': 'c', 'year': 1, 'semester': 1, 'university': 'Test U',
            'subject': self.subject.id, 'file': upload,
        })

    def test_upload_form_has_no_type_dropdown(self):
        response = self.client_for(self.provider).get(reverse('upload_note'))
        self.assertNotContains(response, 'name="note_type"')

    def test_type_is_detected_from_the_file(self):
        self.upload(SimpleUploadedFile('diagram.png', png_bytes()))
        self.upload(pdf_upload('chapter.pdf'))
        types = dict(Note.objects.filter(name='Auto type').values_list('file', 'note_type'))
        self.assertEqual(sorted(types.values()), ['image', 'pdf'])

    def test_replacing_the_file_updates_the_type(self):
        self.client_for(self.provider).post(reverse('edit_note', args=[self.verified_note.id]), {
            'name': 'Published note', 'caption': 'c', 'year': 1, 'semester': 1, 'university': 'Test U',
            'subject': self.subject.id, 'file': SimpleUploadedFile('scan.png', png_bytes()),
        })
        self.verified_note.refresh_from_db()
        self.assertEqual(self.verified_note.note_type, 'image')


class MessageBarTests(SecurityTestCase):
    def test_messages_are_shown_on_the_next_page(self):
        client = self.client_for(self.basic)
        response = client.post(reverse('rate_note', args=[self.verified_note.id]), {'score': 5}, follow=True)
        self.assertContains(response, 'class="flash flash--success"')
        self.assertContains(response, 'Thanks for rating this note!')
