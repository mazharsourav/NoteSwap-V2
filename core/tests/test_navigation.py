"""Public browsing, login and logout redirects, and site-wide settings."""
from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Note, Subject, Topic
from core.tests.test_security import MEDIA_ROOT, make_user, pdf_upload


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class NavigationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.member = make_user('member')
        provider = make_user('author', user_type='provider')
        subject = Subject.objects.create(name='Maths', year=1, semester=1, university='Test U')
        topic = Topic.objects.create(subject=subject, name='Algebra', year=1, semester=1, university='Test U')
        cls.note = Note.objects.create(
            topic=topic, provider=provider, note_type='pdf', caption='c', year=1, semester=1,
            university='Test U', name='Featured', is_verified=True, file=pdf_upload(),
        )

    def test_notes_link_goes_to_public_subject_list_when_signed_out(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, f'href="{reverse("subject_list")}">Notes<')
        self.assertEqual(self.client.get(reverse('subject_list')).status_code, 200)

    def test_signed_out_read_more_goes_to_login_then_back_to_the_note(self):
        note_url = reverse('note_detail', args=[self.note.id])
        response = self.client.get(reverse('home'))
        self.assertContains(response, f'href="{note_url}"')
        response = self.client.get(note_url)
        self.assertRedirects(response, f"{reverse('account_login')}?next={note_url}")

    def test_logout_link_posts_and_lands_on_home(self):
        self.client.force_login(self.member)
        response = self.client.get(reverse('home'))
        self.assertContains(response, f'data-post-url="{reverse("logout")}"')
        self.assertContains(response, 'id="post-action-form"')
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('home'))
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_time_zone_is_bangladesh(self):
        self.assertEqual(settings.TIME_ZONE, 'Asia/Dhaka')
