"""Error pages, user search, note deletion, and routes removed as dead code."""
from django.http import HttpResponse
from django.test import Client, override_settings
from django.urls import NoReverseMatch, path, reverse

from core.models import Note
from core.tests.test_security import SecurityTestCase, make_user


def boom(request):
    raise RuntimeError('deliberate failure for the 500 page test')


def ok(request):
    return HttpResponse('ok')


urlpatterns = [path('boom/', boom), path('ok/', ok)]


class ErrorPageTests(SecurityTestCase):
    @override_settings(DEBUG=False)
    def test_404_page(self):
        response = self.client_for(self.basic).get('/this-page-does-not-exist/')
        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, '404.html')
        self.assertContains(response, 'Page not found', status_code=404)

    def test_403_page(self):
        response = self.client_for(self.basic).get(reverse('verify_notes'))
        self.assertEqual(response.status_code, 403)
        self.assertTemplateUsed(response, '403.html')

    def test_editing_someone_elses_note_shows_the_403_page(self):
        response = self.client_for(self.other_provider).get(reverse('edit_note', args=[self.verified_note.id]))
        self.assertTemplateUsed(response, '403.html')

    @override_settings(DEBUG=False, ROOT_URLCONF=__name__)
    def test_500_page(self):
        response = Client(raise_request_exception=False).get('/boom/')
        self.assertEqual(response.status_code, 500)
        self.assertContains(response, 'Something went wrong', status_code=500)


class SearchTests(SecurityTestCase):
    def search(self, query):
        return self.client_for(self.basic).get(reverse('search_users') + query)

    def test_empty_search_lists_nobody(self):
        response = self.search('')
        self.assertIsNone(response.context['results'])
        self.assertContains(response, 'Type a name or username')

    def test_matches_names_and_excludes_yourself(self):
        make_user('zara_k', first_name='Zara', last_name='Khan')
        self.assertEqual([u.username for u in self.search('?q=khan').context['results']], ['zara_k'])
        self.assertNotIn(self.basic, list(self.search('?q=basic').context['results']))

    def test_results_are_paginated(self):
        for i in range(15):
            make_user(f'match_{i:02}')
        page = self.search('?q=match_').context['results']
        self.assertEqual((len(page), page.paginator.count), (12, 15))


class NoteManagementTests(SecurityTestCase):
    def test_deleting_a_note_returns_to_its_subject(self):
        response = self.client_for(self.provider).post(reverse('delete_note', args=[self.verified_note.id]))
        self.assertRedirects(response, reverse('subject_detail', args=[self.subject.id]))
        self.assertFalse(Note.objects.filter(id=self.verified_note.id).exists())

    def test_only_the_owner_can_manage_files(self):
        url = reverse('note_files', args=[self.verified_note.id])
        self.assertEqual(self.client_for(self.other_provider).get(url).status_code, 403)
        self.assertEqual(self.client_for(self.provider).get(url).status_code, 200)


class RemovedRoutesTests(SecurityTestCase):
    def test_dead_routes_are_gone(self):
        for name in ('post_review', 'verify_action', 'buy_premium', 'send_friend', 'accept_friend_request',
                     'friend_page', 'send_friend_request', 'accept_friend', 'remove_friend'):
            with self.assertRaises(NoReverseMatch, msg=name):
                reverse(name)
        self.assertEqual(self.client_for(self.moderator).post('/verify/1/approve/').status_code, 404)
