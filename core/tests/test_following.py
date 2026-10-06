"""Following providers and in-app notifications (Phase 5, replacing Friends)."""
from django.urls import reverse

from core.models import Follow, Note, Notification
from core.notifications import publish_notes
from core.tests.test_security import SecurityTestCase, make_user, pdf_upload

Kind = Notification.Kind


class FollowTests(SecurityTestCase):
    def follow(self, user, provider, query=''):
        return self.client_for(user).post(reverse('follow_provider', args=[provider.id]) + query)

    def unfollow(self, user, provider, query=''):
        return self.client_for(user).post(reverse('unfollow_provider', args=[provider.id]) + query)

    def test_needs_login_and_post(self):
        url = reverse('follow_provider', args=[self.provider.id])
        response = self.client_for(None).post(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('account_login'), response['Location'])
        self.assertEqual(self.client_for(self.basic).get(url).status_code, 405)
        self.assertFalse(Follow.objects.exists())

    def test_follow_creates_a_follow_and_tells_the_provider(self):
        response = self.follow(self.basic, self.provider)
        self.assertRedirects(response, reverse('provider_profile', args=[self.provider.id]),
                             fetch_redirect_response=False)
        self.assertTrue(Follow.objects.filter(follower=self.basic, provider=self.provider).exists())
        notification = Notification.objects.get(recipient=self.provider)
        self.assertEqual((notification.kind, notification.actor), (Kind.NEW_FOLLOWER, self.basic))
        self.assertEqual(notification.url, reverse('user_profile', args=[self.basic.id]))

    def test_following_twice_changes_nothing(self):
        self.follow(self.basic, self.provider)
        self.follow(self.basic, self.provider)
        self.assertEqual(Follow.objects.count(), 1)
        self.assertEqual(Notification.objects.count(), 1)

    def test_only_providers_can_be_followed(self):
        self.assertEqual(self.follow(self.provider, self.basic).status_code, 404)
        self.assertEqual(self.follow(self.basic, self.moderator).status_code, 404)
        self.follow(self.provider, self.provider)
        self.assertFalse(Follow.objects.exists())

    def test_unfollow_removes_the_follow_and_its_notification(self):
        self.follow(self.basic, self.provider)
        response = self.unfollow(self.basic, self.provider)
        self.assertRedirects(response, reverse('following'), fetch_redirect_response=False)
        self.assertFalse(Follow.objects.exists())
        self.assertFalse(Notification.objects.exists())

    def test_follow_unfollow_loops_do_not_pile_up_notifications(self):
        for _ in range(3):
            self.follow(self.basic, self.provider)
            self.unfollow(self.basic, self.provider)
        self.follow(self.basic, self.provider)
        self.assertEqual(Notification.objects.filter(recipient=self.provider).count(), 1)

    def test_next_returns_to_the_page_but_never_off_site(self):
        response = self.follow(self.basic, self.provider, '?next=/providers/')
        self.assertRedirects(response, '/providers/', fetch_redirect_response=False)
        response = self.unfollow(self.basic, self.provider, '?next=https://evil.example/')
        self.assertRedirects(response, reverse('following'), fetch_redirect_response=False)


class PublishingNotifiesFollowersTests(SecurityTestCase):
    def setUp(self):
        self.fan = make_user('fan')
        Follow.objects.create(follower=self.fan, provider=self.provider)
        Follow.objects.create(follower=self.basic, provider=self.other_provider)  # follows someone else

    def approve(self, *notes):
        return self.client_for(self.moderator).post(
            reverse('verify_notes'), {'verify_type': 'main', 'note_ids': [note.id for note in notes]},
        )

    def test_followers_hear_about_a_newly_published_note(self):
        self.approve(self.unverified_note)
        self.unverified_note.refresh_from_db()
        self.assertTrue(self.unverified_note.is_verified)

        notification = Notification.objects.get()
        self.assertEqual((notification.recipient, notification.kind, notification.note),
                         (self.fan, Kind.NEW_NOTE, self.unverified_note))
        self.assertIn('Pending note', notification.text)
        self.assertEqual(notification.url, reverse('note_detail', args=[self.unverified_note.id]))

    def test_a_note_is_announced_only_once(self):
        self.approve(self.unverified_note)
        Note.objects.filter(id=self.unverified_note.id).update(is_verified=False)  # file changed, back in review
        self.approve(self.unverified_note)
        self.approve(self.verified_note)  # already published: nothing to announce
        self.assertEqual(Notification.objects.count(), 1)

    def test_django_admin_approval_also_notifies(self):
        self.client_for(self.superuser).post(reverse('admin:core_note_changelist'), {
            'action': 'verify_notes', '_selected_action': [self.unverified_note.id],
        })
        self.assertEqual(Notification.objects.filter(recipient=self.fan, kind=Kind.NEW_NOTE).count(), 1)

    def test_publishing_several_notes_is_one_bulk_insert(self):
        others = [make_user(f'fan_{i}') for i in range(3)]
        Follow.objects.bulk_create([Follow(follower=user, provider=self.provider) for user in others])
        extra = Note.objects.create(
            topic=self.topic, provider=self.provider, note_type='pdf', caption='c', year=1, semester=1,
            university='Test U', name='Second', file=pdf_upload('second.pdf'),
        )
        # savepoint, pending notes, update, already announced, followers, one insert, release
        with self.assertNumQueries(7):
            published = publish_notes(Note.objects.filter(id__in=[self.unverified_note.id, extra.id]))
        self.assertEqual(published, 2)
        self.assertEqual(Notification.objects.count(), 8)  # 2 notes x 4 followers


class NotificationPageTests(SecurityTestCase):
    def setUp(self):
        self.mine = Notification.objects.create(recipient=self.basic, kind=Kind.NEW_NOTE, actor=self.provider,
                                                note=self.verified_note)
        self.other = Notification.objects.create(recipient=self.provider, kind=Kind.NEW_FOLLOWER, actor=self.basic)

    def test_needs_login(self):
        self.assertEqual(self.client_for(None).get(reverse('notifications')).status_code, 302)

    def test_navbar_shows_the_unread_count(self):
        response = self.client_for(self.basic).get(reverse('home'))
        self.assertEqual(response.context['unread_notifications'], 1)
        self.assertContains(response, 'class="notif-badge">1<')

    def test_shows_only_your_notifications_and_marks_them_read(self):
        client = self.client_for(self.basic)
        response = client.get(reverse('notifications'))
        self.assertEqual(list(response.context['page']), [self.mine])
        self.assertContains(response, 'notification-item--unread')
        self.assertContains(response, 'published a new note')
        self.assertEqual(response.context['unread_notifications'], 0)  # bell clears on this page

        self.mine.refresh_from_db()
        self.other.refresh_from_db()
        self.assertTrue(self.mine.is_read)
        self.assertFalse(self.other.is_read)
        self.assertNotContains(client.get(reverse('notifications')), 'notification-item--unread')

    def test_deleting_a_note_removes_its_notifications(self):
        self.verified_note.delete()
        self.assertFalse(Notification.objects.filter(id=self.mine.id).exists())


class FollowPagesTests(SecurityTestCase):
    def setUp(self):
        Follow.objects.create(follower=self.basic, provider=self.provider)

    def test_following_page_lists_followed_providers(self):
        response = self.client_for(self.basic).get(reverse('following'))
        providers = list(response.context['page'])
        self.assertEqual(providers, [self.provider])
        self.assertEqual(providers[0].note_count, 1)  # only the published note
        self.assertContains(response, 'Unfollow')

    def test_following_page_when_following_nobody(self):
        response = self.client_for(self.other_provider).get(reverse('following'))
        self.assertContains(response, "You aren't following any providers yet.")

    def test_provider_page_shows_followers_and_button_state(self):
        url = reverse('provider_profile', args=[self.provider.id])
        response = self.client_for(self.basic).get(url)
        self.assertEqual(response.context['follower_count'], 1)
        self.assertContains(response, '<dt>follower</dt><dd>1</dd>')
        self.assertContains(response, 'follow-btn--following')

        response = self.client_for(self.other_provider).get(url)
        self.assertContains(response, reverse('follow_provider', args=[self.provider.id]))

        response = self.client_for(None).get(url)  # signed out: log in, then come back
        self.assertContains(response, f'{reverse("account_login")}?next=/provider/{self.provider.id}/')

        response = self.client_for(self.provider).get(url)  # no button on your own page
        self.assertNotContains(response, 'follow-btn')

    def test_provider_list_marks_who_you_follow(self):
        response = self.client_for(self.basic).get(reverse('providers'))
        self.assertEqual(response.context['followed_ids'], {self.provider.id})
        counts = {item['provider'].id: item['follower_count'] for item in response.context['provider_data']}
        self.assertEqual(counts, {self.provider.id: 1, self.other_provider.id: 0})

    def test_follow_button_only_on_provider_user_pages(self):
        client = self.client_for(self.basic)
        self.assertContains(client.get(reverse('user_profile', args=[self.provider.id])), 'follow-btn--following')
        self.assertNotContains(client.get(reverse('user_profile', args=[self.moderator.id])), 'follow-btn')

    def test_profile_shows_counts(self):
        response = self.client_for(self.basic).get(reverse('profile'))
        self.assertContains(response, 'Following (1)')
        response = self.client_for(self.provider).get(reverse('profile'))
        self.assertContains(response, '1 follower. Followers are notified')
