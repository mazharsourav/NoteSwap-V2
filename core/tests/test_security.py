"""
Security and access-control tests (Phase 2).

Each class covers one class of hole found in the audit: role checks, state
changes over GET/CSRF, note visibility, protected files, NoteSolve isolation,
upload validation, re-review on file change and open redirects. Sign-in rules
(lockout, next=, email verification) are in test_accounts.py.
"""
import shutil
import tempfile
from datetime import timedelta
from io import BytesIO
from unittest import mock

from django.core.files.base import ContentFile
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core.forms import NoteUploadForm
from core.models import (
    CustomUser, Note, NoteFile, NoteSolveFile, NoteSolveRequest,
    NoteSolveSolution, PremiumPackage, PremiumPurchase, ProviderRequest, Subject, Topic,
)

PASSWORD = 'Str0ng-test-pass!'
PDF_BYTES = b'%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n'
MEDIA_ROOT = tempfile.mkdtemp(prefix='noteswap-test-media-')


def tearDownModule():
    shutil.rmtree(MEDIA_ROOT, ignore_errors=True)


def png_bytes():
    buf = BytesIO()
    Image.new('RGB', (4, 4), (14, 181, 130)).save(buf, 'PNG')
    return buf.getvalue()


def pdf_upload(name='note.pdf'):
    return SimpleUploadedFile(name, PDF_BYTES, content_type='application/pdf')


def make_user(username, **extra):
    return CustomUser.objects.create_user(
        username=username, password=PASSWORD, university='Test U', gender='other', **extra
    )


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SecurityTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.basic = make_user('basic')
        cls.provider = make_user('provider', user_type='provider')
        cls.other_provider = make_user('other_provider', user_type='provider')
        cls.moderator = make_user('moderator', user_type='moderator')
        cls.superuser = make_user('root', is_superuser=True, is_staff=True)

        cls.subject = Subject.objects.create(name='Physics', year=1, semester=1, university='Test U')
        cls.topic = Topic.objects.create(subject=cls.subject, name='Optics', year=1, semester=1, university='Test U')
        note_fields = dict(topic=cls.topic, provider=cls.provider, note_type='pdf', caption='c',
                           year=1, semester=1, university='Test U')
        cls.verified_note = Note.objects.create(name='Published note', is_verified=True,
                                                file=pdf_upload('published.pdf'), **note_fields)
        cls.unverified_note = Note.objects.create(name='Pending note', is_verified=False,
                                                  file=pdf_upload('pending.pdf'), **note_fields)
        cls.unverified_extra = NoteFile.objects.create(note=cls.verified_note, file=pdf_upload('extra.pdf'))

        cls.solve_request = NoteSolveRequest.objects.create(
            user=cls.basic, requested_to=cls.provider, university='Test U', department='CSE',
            semester='1', year=1, subject='Physics', topic='Optics', problem_description='help',
        )
        cls.solve_file = NoteSolveFile.objects.create(solve_request=cls.solve_request, file=pdf_upload('q.pdf'))
        cls.solution = NoteSolveSolution.objects.create(
            solve_request=cls.solve_request, provider=cls.provider, solution_text='answer', file=pdf_upload('a.pdf'),
        )

        cls.package = PremiumPackage.objects.create(name='Monthly', description='d', price=100, duration_in_months=1)
        cls.purchase = PremiumPurchase.objects.create(user=cls.basic, package_name='Monthly', amount=100,
                                                     duration_in_months=1)
        cls.applicant = make_user('applicant')
        cls.application = ProviderRequest.objects.create(
            user=cls.applicant, first_name='A', last_name='B', email='a@example.com', university='Test U',
            department='CSE', cgpa='3.50', gender='other', nationality='BD', profession='student',
            address='x', phone_number='1', status='pending',
        )

    def client_for(self, user, **kwargs):
        client = Client(**kwargs)
        if user is not None:
            client.force_login(user)
        return client

    def make_premium(self, user, days=30):
        user.premium_until = timezone.now() + timedelta(days=days)
        user.save(update_fields=['premium_until'])


class RoleAccessTests(SecurityTestCase):
    def admin_urls(self):
        return [
            reverse('verify_notes'), reverse('Manage'), reverse('provider_requests'),
            reverse('add_premium_package'), reverse('edit_premium_package', args=[self.package.id]),
        ]

    def test_anonymous_users_are_sent_to_login_not_a_crash(self):
        client = self.client_for(None)
        for url in self.admin_urls():
            response = client.get(url)
            self.assertEqual(response.status_code, 302, url)
            self.assertIn(reverse('account_login'), response['Location'], url)

    def test_basic_users_get_403(self):
        client = self.client_for(self.basic)
        for url in self.admin_urls():
            self.assertEqual(client.get(url).status_code, 403, url)

    def test_moderators_can_moderate_but_not_manage_payments(self):
        client = self.client_for(self.moderator)
        for url in (reverse('verify_notes'), reverse('provider_requests'), reverse('Manage'),
                    reverse('provider_request_detail', args=[self.application.id])):
            self.assertEqual(client.get(url).status_code, 200, url)
        for url in (reverse('add_premium_package'), reverse('edit_premium_package', args=[self.package.id])):
            self.assertEqual(client.get(url).status_code, 403, url)

    def test_superusers_can_reach_everything(self):
        client = self.client_for(self.superuser)
        for url in self.admin_urls():
            self.assertEqual(client.get(url).status_code, 200, url)

    def test_pending_purchases_are_only_listed_for_superusers(self):
        self.assertNotIn('pending_purchases', self.client_for(self.basic).get(reverse('premium_packages')).context)
        self.assertEqual(self.client_for(self.basic).get(reverse('manage_premium')).status_code, 403)
        self.assertEqual(self.client_for(self.moderator).get(reverse('manage_premium')).status_code, 403)
        response = self.client_for(self.superuser).get(reverse('manage_premium'))
        self.assertIn(self.purchase, response.context['pending_purchases'])

    def test_only_providers_can_upload(self):
        self.assertEqual(self.client_for(self.basic).get(reverse('upload_note')).status_code, 403)
        self.assertEqual(self.client_for(self.provider).get(reverse('upload_note')).status_code, 200)


class StateChangeRequiresPostTests(SecurityTestCase):
    def test_get_on_state_changing_urls_is_rejected(self):
        cases = [
            (self.superuser, reverse('approve_purchase', args=[self.purchase.id])),
            (self.superuser, reverse('reject_purchase', args=[self.purchase.id])),
            (self.superuser, reverse('delete_premium_package', args=[self.package.id])),
            (self.moderator, reverse('provider_request_action', args=[self.application.id, 'accept'])),
            (self.basic, reverse('follow_provider', args=[self.provider.id])),
            (self.basic, reverse('unfollow_provider', args=[self.provider.id])),
        ]
        for user, url in cases:
            self.assertEqual(self.client_for(user).get(url).status_code, 405, url)

        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, PremiumPurchase.Status.PENDING)
        self.assertTrue(PremiumPackage.objects.filter(id=self.package.id).exists())
        self.unverified_note.refresh_from_db()
        self.assertFalse(self.unverified_note.is_verified)
        self.applicant.refresh_from_db()
        self.assertEqual(self.applicant.user_type, 'basic')

    def test_post_with_csrf_token_still_works(self):
        response = self.client_for(self.superuser).post(reverse('approve_purchase', args=[self.purchase.id]))
        self.assertEqual(response.status_code, 302)
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, PremiumPurchase.Status.APPROVED)

    def test_post_without_csrf_token_is_refused(self):
        client = self.client_for(self.superuser, enforce_csrf_checks=True)
        response = client.post(reverse('approve_purchase', args=[self.purchase.id]))
        self.assertEqual(response.status_code, 403)
        self.purchase.refresh_from_db()
        self.assertEqual(self.purchase.status, PremiumPurchase.Status.PENDING)

    def test_logout_needs_post(self):
        client = self.client_for(self.basic)
        response = client.get(reverse('logout'))  # e.g. a link planted on another site
        self.assertRedirects(response, reverse('home'))
        self.assertIn('_auth_user_id', client.session)

        response = client.post(reverse('logout'))
        self.assertRedirects(response, reverse('home'))
        self.assertNotIn('_auth_user_id', client.session)


class NoteVisibilityTests(SecurityTestCase):
    def test_opening_a_note_requires_login(self):
        response = self.client_for(None).get(reverse('note_detail', args=[self.verified_note.id]))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('account_login'), response['Location'])

    def test_unverified_notes_are_hidden_from_other_users(self):
        url = reverse('note_detail', args=[self.unverified_note.id])
        self.assertEqual(self.client_for(self.basic).get(url).status_code, 404)
        self.assertEqual(self.client_for(self.other_provider).get(url).status_code, 404)

    def test_owner_and_moderator_can_preview_unverified_notes(self):
        url = reverse('note_detail', args=[self.unverified_note.id])
        self.assertEqual(self.client_for(self.provider).get(url).status_code, 200)
        self.assertEqual(self.client_for(self.moderator).get(url).status_code, 200)

    def test_verified_notes_are_visible_to_members(self):
        url = reverse('note_detail', args=[self.verified_note.id])
        self.assertEqual(self.client_for(self.basic).get(url).status_code, 200)

    def test_note_listing_stays_public_and_hides_unverified(self):
        response = self.client_for(None).get(reverse('subject_detail', args=[self.subject.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Published note')
        self.assertNotContains(response, 'Pending note')

    def test_cannot_comment_on_or_rate_unverified_notes(self):
        client = self.client_for(self.basic)
        self.assertEqual(client.post(reverse('comment_on_note', args=[self.unverified_note.id]),
                                     {'comment': 'hi'}).status_code, 404)
        self.assertEqual(client.post(reverse('rate_note', args=[self.unverified_note.id]),
                                     {'score': '5'}).status_code, 404)


class ProtectedFileTests(SecurityTestCase):
    def test_note_files_need_login(self):
        response = self.client_for(None).get(reverse('note_file', args=[self.verified_note.id]))
        self.assertEqual(response.status_code, 302)

    def test_published_note_file_is_served_inline(self):
        response = self.client_for(self.basic).get(reverse('note_file', args=[self.verified_note.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response['Content-Disposition'].startswith('inline'))
        self.assertEqual(b''.join(response.streaming_content), PDF_BYTES)

    def test_unverified_files_are_hidden_except_from_owner_and_moderators(self):
        note_url = reverse('note_file', args=[self.unverified_note.id])
        extra_url = reverse('note_extra_file', args=[self.unverified_extra.id])
        for url in (note_url, extra_url):
            self.assertEqual(self.client_for(self.basic).get(url).status_code, 404, url)
            self.assertEqual(self.client_for(self.provider).get(url).status_code, 200, url)
            self.assertEqual(self.client_for(self.moderator).get(url).status_code, 200, url)

    def test_notesolve_files_are_private_to_the_two_parties(self):
        attachment = reverse('notesolve_file', args=[self.solve_file.id])
        solution = reverse('notesolve_solution_file', args=[self.solution.id])
        for url in (attachment, solution):
            self.assertEqual(self.client_for(self.basic).get(url).status_code, 200, url)
            self.assertEqual(self.client_for(self.provider).get(url).status_code, 200, url)
            self.assertEqual(self.client_for(self.other_provider).get(url).status_code, 404, url)
            self.assertEqual(self.client_for(self.moderator).get(url).status_code, 404, url)

    def test_unsafe_legacy_files_are_forced_to_download(self):
        legacy = Note.objects.create(
            topic=self.topic, provider=self.provider, note_type='pdf', caption='c', year=1, semester=1,
            university='Test U', name='Legacy', is_verified=True,
        )
        legacy.file.save('legacy.html', ContentFile(b'<script>alert(1)</script>'))
        response = self.client_for(self.basic).get(reverse('note_file', args=[legacy.id]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response['Content-Disposition'].startswith('attachment'))

    def test_files_can_be_embedded_by_this_site_only(self):
        response = self.client_for(self.basic).get(reverse('note_file', args=[self.verified_note.id]))
        self.assertEqual(response['X-Frame-Options'], 'SAMEORIGIN')


class NoteSolveIsolationTests(SecurityTestCase):
    def test_other_providers_cannot_open_a_request(self):
        url = reverse('solve_request', args=[self.solve_request.id])
        self.assertEqual(self.client_for(self.other_provider).get(url).status_code, 404)

    def test_other_providers_cannot_delete_a_request(self):
        url = reverse('solve_request', args=[self.solve_request.id])
        self.client_for(self.other_provider).post(url, {'action': 'reject'})
        self.assertTrue(NoteSolveRequest.objects.filter(id=self.solve_request.id).exists())

    def test_the_requested_provider_can_open_it(self):
        url = reverse('solve_request', args=[self.solve_request.id])
        NoteSolveSolution.objects.filter(id=self.solution.id).delete()  # otherwise it redirects as already solved
        self.assertEqual(self.client_for(self.provider).get(url).status_code, 200)

    def test_bad_attachment_does_not_create_a_request(self):
        self.make_premium(self.basic)
        before = NoteSolveRequest.objects.count()
        self.client_for(self.basic).post(reverse('request_to_provider', args=[self.provider.id]), {
            'university': 'U', 'department': 'CSE', 'semester': '1', 'year': '1', 'subject': 's',
            'topic': 't', 'problem_description': 'p',
            'file': SimpleUploadedFile('evil.pdf', b'<html>not a pdf</html>'),
        })
        self.assertEqual(NoteSolveRequest.objects.count(), before)


class UploadValidationTests(SecurityTestCase):
    def form(self, upload):
        data = {'name': 'n', 'caption': 'c', 'note_type': 'pdf', 'year': 1, 'semester': 1,
                'university': 'Test U', 'subject': self.subject.id}
        return NoteUploadForm(data, {'file': upload})

    def assertRejected(self, upload):
        form = self.form(upload)
        self.assertFalse(form.is_valid())
        self.assertIn('file', form.errors)

    def test_accepts_real_pdf_and_png(self):
        self.assertTrue(self.form(pdf_upload()).is_valid())
        self.assertTrue(self.form(SimpleUploadedFile('pic.png', png_bytes())).is_valid())

    def test_rejects_disallowed_extensions(self):
        self.assertRejected(SimpleUploadedFile('page.html', b'<html></html>'))
        self.assertRejected(SimpleUploadedFile('image.svg', b'<svg xmlns="http://www.w3.org/2000/svg"/>'))
        self.assertRejected(SimpleUploadedFile('tool.exe', b'MZ\x90\x00'))

    def test_rejects_content_that_does_not_match_the_extension(self):
        self.assertRejected(SimpleUploadedFile('fake.pdf', b'<html><script>alert(1)</script></html>'))
        self.assertRejected(SimpleUploadedFile('pic.jpg', png_bytes()))

    def test_rejects_corrupt_images(self):
        self.assertRejected(SimpleUploadedFile('broken.png', b'\x89PNG\r\n\x1a\n' + b'garbage' * 10))

    def test_rejects_files_over_the_size_limit(self):
        with mock.patch('core.validators.MAX_UPLOAD_SIZE', 10):
            self.assertRejected(pdf_upload())


class NoteEditReviewTests(SecurityTestCase):
    def edit(self, **files):
        data = {'name': 'Published note', 'caption': 'updated caption', 'note_type': 'pdf', 'year': 1,
                'semester': 1, 'university': 'Test U', 'subject': self.subject.id, **files}
        return self.client_for(self.provider).post(reverse('edit_note', args=[self.verified_note.id]), data)

    def test_text_only_edit_stays_published(self):
        self.edit()
        self.verified_note.refresh_from_db()
        self.assertEqual(self.verified_note.caption, 'updated caption')
        self.assertTrue(self.verified_note.is_verified)

    def test_new_file_goes_back_to_review(self):
        self.edit(file=pdf_upload('replacement.pdf'))
        self.verified_note.refresh_from_db()
        self.assertFalse(self.verified_note.is_verified)

    def test_other_users_cannot_edit(self):
        response = self.client_for(self.other_provider).get(reverse('edit_note', args=[self.verified_note.id]))
        self.assertEqual(response.status_code, 403)


class OpenRedirectTests(SecurityTestCase):
    def test_add_subject_ignores_external_next(self):
        response = self.client_for(self.provider).post(
            reverse('add_subject') + '?next=https://evil.example/',
            {'name': 'Chemistry', 'year': 1, 'semester': 1, 'university': 'Test U'},
        )
        self.assertRedirects(response, reverse('subject_list'), fetch_redirect_response=False)

    def test_add_subject_keeps_internal_next(self):
        response = self.client_for(self.provider).post(
            reverse('add_subject') + '?next=/upload/',
            {'name': 'Biology', 'year': 1, 'semester': 1, 'university': 'Test U'},
        )
        biology = Subject.objects.get(name='Biology')
        self.assertRedirects(response, f'/upload/?subject={biology.id}', fetch_redirect_response=False)
