"""
Pre-launch hardening (after Phase 6): bugs found in the full-project scan.

Empty NoteSolve solutions, number ranges, profile photo size, blank provider names in
messages, the Help Center text, the admin's reject action, and form gaps (blank solution
rating, rejected comments, comment length).
"""
from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image

from core.forms import NoteSolveRequestForm, NoteUploadForm, PremiumPackageForm, SubjectForm
from core.models import (
    Note, NoteComment, NoteSolveRequest, NoteSolveSolution, Notification,
)

from .test_security import SecurityTestCase, png_bytes


def image_upload(name, size, mode='RGB', fmt='PNG', exif=None):
    buf = BytesIO()
    image = Image.new(mode, size, (14, 181, 130, 128) if mode == 'RGBA' else (14, 181, 130))
    image.save(buf, fmt, **({'exif': exif} if exif else {}))
    return SimpleUploadedFile(name, buf.getvalue())


def messages_of(response):
    return [str(message) for message in response.context['messages']]


class EmptySolutionTests(SecurityTestCase):
    def setUp(self):
        self.pending = NoteSolveRequest.objects.create(
            user=self.basic, requested_to=self.provider, university='Test U', department='CSE',
            semester='1', year=1, subject='Physics', topic='Optics', problem_description='help',
        )
        self.url = reverse('solve_request', args=[self.pending.id])

    def test_a_solution_needs_text_or_a_file(self):
        response = self.client_for(self.provider).post(self.url, {'solution_text': '   '})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Write an explanation or attach your worked solution')
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, NoteSolveRequest.Status.PENDING)
        self.assertFalse(NoteSolveSolution.objects.filter(solve_request=self.pending).exists())

    def test_text_alone_is_enough(self):
        response = self.client_for(self.provider).post(self.url, {'solution_text': 'Use Snell’s law.'})
        self.assertRedirects(response, reverse('provider_solved_requests'), fetch_redirect_response=False)
        self.pending.refresh_from_db()
        self.assertEqual(self.pending.status, NoteSolveRequest.Status.SOLVED)


class NumberRangeTests(SecurityTestCase):
    def note_form(self, **values):
        data = {'name': 'n', 'caption': 'c', 'year': 2, 'semester': 3, 'university': 'Test U',
                'subject': self.subject.id, **values}
        return NoteUploadForm(data, {'file': SimpleUploadedFile('a.png', png_bytes())})

    def test_year_of_study_and_semester_are_checked(self):
        self.assertTrue(self.note_form().is_valid())  # plain year= and semester= still work
        self.assertTrue(self.note_form(term='5-3').is_valid())
        for values in [{'year': 0}, {'year': 2025}, {'year': -3}, {'semester': 0}, {'semester': 4}, {'term': '6-1'},
                       {'term': '2-0'}, {'term': 'abc'}]:
            form = self.note_form(**values)
            self.assertFalse(form.is_valid(), values)
            self.assertEqual(form.errors['term'], ['Choose a semester from the list, like 2-1.'], values)
        data = {'name': 'n', 'caption': 'c', 'university': 'Test U', 'subject': self.subject.id}
        self.assertEqual(NoteUploadForm(data, {'file': SimpleUploadedFile('a.png', png_bytes())}).errors['term'],
                         ['Choose the semester.'])

    def test_notesolve_form_checks_too_and_a_course_is_just_a_name(self):
        self.assertEqual(list(SubjectForm().fields), ['name'])
        self.assertIn('year', NoteSolveRequestForm({
            'university': 'Test U', 'department': 'CSE', 'semester': '1', 'year': 2024,
            'subject': 's', 'topic': 't', 'problem_description': 'p',
        }).errors)

    def test_the_semester_list_holds_only_real_semesters(self):
        html = str(self.note_form()['term'])
        self.assertIn('<option value="1-1">', html)
        self.assertIn('<option value="5-3">', html)
        self.assertNotIn('6-1', html)

    def test_premium_form_shows_its_limits(self):
        html = str(PremiumPackageForm()['price']) + str(PremiumPackageForm()['duration_in_months'])
        for attribute in ('min="1"', 'max="36"'):
            self.assertIn(attribute, html)

    def test_premium_price_and_length_are_checked(self):
        def errors(**values):
            return PremiumPackageForm({'name': 'p', 'description': 'd', 'price': 100,
                                       'duration_in_months': 6, **values}).errors
        self.assertEqual(errors(), {})
        self.assertIn('price', errors(price=0))
        self.assertIn('price', errors(price=-50))
        self.assertIn('duration_in_months', errors(duration_in_months=0))
        self.assertIn('duration_in_months', errors(duration_in_months=37))


class ProfilePhotoTests(SecurityTestCase):
    def upload(self, photo):
        return self.client_for(self.basic).post(reverse('edit_profile'), {
            'first_name': 'B', 'last_name': 'U', 'university': 'Test U', 'gender': 'Other',
            'profile_picture': photo,
        })

    def stored_photo(self):
        self.basic.refresh_from_db()
        with self.basic.profile_picture.open('rb') as handle, Image.open(handle) as image:
            return image.format, image.size

    def test_big_photos_are_shrunk_to_a_small_jpeg(self):
        self.assertRedirects(self.upload(image_upload('me.png', (2000, 1000), 'RGBA')), reverse('profile'),
                             fetch_redirect_response=False)
        self.assertEqual(self.stored_photo(), ('JPEG', (400, 200)))
        self.assertTrue(self.basic.profile_picture.name.endswith('me.jpg'))

    def test_phone_photos_are_turned_upright(self):
        exif = Image.Exif()
        exif[0x0112] = 6  # stored sideways, "rotate 90°" flag
        self.upload(image_upload('phone.jpg', (300, 100), fmt='JPEG', exif=exif.tobytes()))
        self.assertEqual(self.stored_photo(), ('JPEG', (100, 300)))

    def test_too_large_or_wrong_type_is_refused(self):
        photo = image_upload('huge.jpg', (40, 40), fmt='JPEG').read()
        huge = SimpleUploadedFile('huge.jpg', photo + b'\0' * (10 * 1024 * 1024))  # a real photo, padded
        self.assertContains(self.upload(huge), 'This photo is too large')
        gif = BytesIO()
        Image.new('RGB', (4, 4)).save(gif, 'GIF')
        self.assertContains(self.upload(SimpleUploadedFile('a.gif', gif.getvalue())), 'Use a JPG, PNG or WEBP photo')
        self.basic.refresh_from_db()
        self.assertFalse(self.basic.profile_picture)


class ProviderNameTests(SecurityTestCase):
    def test_request_message_names_a_provider_without_a_full_name(self):
        self.make_premium(self.basic)
        self.assertEqual(self.provider.get_full_name(), '')
        response = self.client_for(self.basic).post(reverse('notesolve_dashboard'), {
            'provider_id': self.provider.id, 'university': 'Test U', 'department': 'CSE', 'semester': '1',
            'year': 1, 'subject': 'Physics', 'topic': 'Optics', 'problem_description': 'help',
        }, follow=True)
        self.assertIn('Your NoteSolve request was sent to provider.', messages_of(response))


class HelpCenterTests(SecurityTestCase):
    def test_provider_article_matches_the_site(self):
        response = self.client_for(None).get(reverse('help_article', args=['becoming-a-provider']))
        self.assertContains(response, 'Send for review again')
        self.assertContains(response, 'Add or remove files')
        self.assertNotContains(response, '“Add files”')


class AdminRejectTests(SecurityTestCase):
    def post(self, **extra):
        return self.client_for(self.superuser).post(reverse('admin:core_note_changelist'), {
            'action': 'reject_with_reason', '_selected_action': [self.unverified_note.id, self.verified_note.id],
            **extra,
        })

    def test_asks_for_a_reason_first(self):
        response = self.post()
        self.assertContains(response, 'Pending note')
        self.assertContains(response, '1 other selected note is already published or rejected')
        response = self.post(post='yes', reason=' ')
        self.assertContains(response, 'Write a reason.')
        self.unverified_note.refresh_from_db()
        self.assertFalse(self.unverified_note.is_rejected)

    def test_rejects_with_the_reason_instead_of_deleting(self):
        self.post(post='yes', reason='Blurry photos')
        note = Note.objects.get(id=self.unverified_note.id)
        self.assertTrue(note.is_rejected)
        self.assertEqual(note.rejection_reason, 'Blurry photos')
        self.assertTrue(Notification.objects.filter(recipient=self.provider, note=note,
                                                    kind=Notification.Kind.NOTE_REJECTED).exists())
        self.verified_note.refresh_from_db()
        self.assertTrue(self.verified_note.is_verified)
        self.assertFalse(self.verified_note.is_rejected)


class FormGapTests(SecurityTestCase):
    def test_a_blank_solution_rating_is_refused(self):
        self.make_premium(self.basic)
        response = self.client_for(self.basic).post(
            reverse('notesolve_dashboard'), {'rate_solution_id': self.solution.id, 'rating': ''})
        self.assertIn('Choose a rating from 1 to 5 stars.', messages_of(response))
        self.solution.refresh_from_db()
        self.assertIsNone(self.solution.rating)

    def comment(self, text):
        return self.client_for(self.basic).post(
            reverse('comment_on_note', args=[self.verified_note.id]), {'comment': text}, follow=True)

    def test_empty_and_too_long_comments_say_why(self):
        self.assertIn('Write something before posting your comment.', messages_of(self.comment('   ')))
        self.assertIn('Your comment is too long. Keep it under 2000 characters.',
                      messages_of(self.comment('x' * 2001)))
        self.assertFalse(NoteComment.objects.exists())
        self.comment('Thanks!')
        self.assertEqual(NoteComment.objects.get().comment, 'Thanks!')

