"""Manage dashboard counts and the inbox (moderators and superusers)."""
from django.urls import reverse

from core.models import InboxMessage
from core.tests.test_security import SecurityTestCase


class DashboardTests(SecurityTestCase):
    def setUp(self):
        InboxMessage.objects.create(kind='contact', name='Open', email='o@example.com', message='Help')
        InboxMessage.objects.create(kind='feedback', name='Done', email='d@example.com', message='Thanks',
                                    is_resolved=True)

    def test_moderator_sees_moderation_counts_only(self):
        response = self.client_for(self.moderator).get(reverse('Manage'))
        counts = response.context['counts']
        self.assertEqual(
            (counts['pending_notes'], counts['pending_files'], counts['pending_applications'], counts['open_messages']),
            (1, 1, 1, 1),
        )
        self.assertNotIn('pending_purchases', counts)
        self.assertNotContains(response, 'Premium orders')
        self.assertContains(response, reverse('inbox'))

    def test_superuser_also_sees_premium_counts(self):
        response = self.client_for(self.superuser).get(reverse('Manage'))
        self.assertEqual(response.context['counts']['pending_purchases'], 1)
        self.assertContains(response, 'Premium orders')


class InboxTests(SecurityTestCase):
    def setUp(self):
        self.contact = InboxMessage.objects.create(kind='contact', name='Rafi', email='r@example.com', message='Hi')
        self.feedback = InboxMessage.objects.create(kind='feedback', name='Mina', email='m@example.com', message='Nice')
        self.resolved = InboxMessage.objects.create(kind='question', name='Old', email='x@example.com', message='?',
                                                    is_resolved=True)

    def listed(self, user, query=''):
        response = self.client_for(user).get(reverse('inbox') + query)
        self.assertEqual(response.status_code, 200)
        return list(response.context['page'])

    def test_access(self):
        self.assertEqual(self.client_for(None).get(reverse('inbox')).status_code, 302)
        self.assertEqual(self.client_for(self.basic).get(reverse('inbox')).status_code, 403)
        self.assertEqual(self.client_for(self.provider).get(reverse('inbox')).status_code, 403)
        self.listed(self.moderator)
        self.listed(self.superuser)

    def test_shows_open_messages_by_default(self):
        self.assertEqual(set(self.listed(self.moderator)), {self.contact, self.feedback})

    def test_filters(self):
        self.assertEqual(self.listed(self.moderator, '?status=resolved'), [self.resolved])
        self.assertEqual(len(self.listed(self.moderator, '?status=all')), 3)
        self.assertEqual(self.listed(self.moderator, '?kind=feedback'), [self.feedback])
        self.assertEqual(len(self.listed(self.moderator, '?status=bogus&kind=bogus')), 3)  # bad values = no filter

    def test_resolve_and_reopen(self):
        url = reverse('inbox_toggle', args=[self.contact.id])
        self.assertEqual(self.client_for(self.moderator).get(url).status_code, 405)
        response = self.client_for(self.moderator).post(url + '?next=/manage/inbox/?status=all')
        self.assertRedirects(response, '/manage/inbox/?status=all', fetch_redirect_response=False)
        self.contact.refresh_from_db()
        self.assertTrue(self.contact.is_resolved)
        self.client_for(self.moderator).post(url)
        self.contact.refresh_from_db()
        self.assertFalse(self.contact.is_resolved)

    def test_toggle_ignores_external_next_and_needs_moderator(self):
        url = reverse('inbox_toggle', args=[self.contact.id])
        response = self.client_for(self.moderator).post(url + '?next=https://evil.example/')
        self.assertRedirects(response, reverse('inbox'), fetch_redirect_response=False)
        self.assertEqual(self.client_for(self.basic).post(url).status_code, 403)
