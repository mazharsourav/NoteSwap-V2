"""
Query counts must not grow with the amount of data on a page.

Each test counts the queries for a page, adds more rows of the kind the page
lists, and checks the count is unchanged (no query per row).
"""
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from core.models import (
    Follow, InboxMessage, Note, NoteSolveFile, Notification, NoteSolveRequest, Rating, Review,
)
from core.tests.test_security import SecurityTestCase, make_user, pdf_upload


class QueryCountTests(SecurityTestCase):
    def queries(self, client, url):
        client.get(url)  # warm up the session
        with CaptureQueriesContext(connection) as ctx:
            response = client.get(url)
        self.assertEqual(response.status_code, 200, url)
        return len(ctx.captured_queries)

    def add_providers_with_notes(self, count):
        for i in range(count):
            author = make_user(f'extra_provider_{i}', user_type='provider')
            note = Note.objects.create(
                topic=self.topic, provider=author, note_type='pdf', caption='c', year=1, semester=1,
                university='Test U', name=f'Extra {i}', is_verified=True, file=pdf_upload(f'extra{i}.pdf'),
            )
            Rating.objects.create(note=note, user=self.basic, score=4)
            Review.objects.create(user=author, comment=f'Review {i}')

    def test_home_and_providers_pages(self):
        anonymous, member = self.client_for(None), self.client_for(self.basic)
        before = [self.queries(anonymous, '/'), self.queries(member, '/'), self.queries(member, '/providers/')]
        self.add_providers_with_notes(5)
        after = [self.queries(anonymous, '/'), self.queries(member, '/'), self.queries(member, '/providers/')]
        self.assertEqual(before, after)
        self.assertLessEqual(before[0], 6)

    def test_subject_page(self):
        client = self.client_for(self.basic)
        urls = [reverse('subject_list'), reverse('subject_detail', args=[self.subject.id])]
        before = [self.queries(client, url) for url in urls]
        self.add_providers_with_notes(5)
        self.assertEqual(before, [self.queries(client, url) for url in urls])

    def test_note_detail_page(self):
        client = self.client_for(self.basic)
        url = reverse('note_detail', args=[self.verified_note.id])
        before = self.queries(client, url)
        for i in range(5):
            commenter = make_user(f'commenter_{i}')
            self.verified_note.notecomment_set.create(user=commenter, comment=f'c{i}')
        self.assertEqual(before, self.queries(client, url))

    def test_notesolve_dashboard(self):
        self.make_premium(self.basic)
        client = self.client_for(self.basic)
        before = self.queries(client, reverse('notesolve_dashboard'))
        for i in range(5):
            request = NoteSolveRequest.objects.create(
                user=self.basic, requested_to=self.other_provider, university='U', department='CSE',
                semester='1', year=1, subject=f's{i}', topic='t', problem_description='p',
            )
            NoteSolveFile.objects.create(solve_request=request, file=pdf_upload(f'q{i}.pdf'))
        self.assertEqual(before, self.queries(client, reverse('notesolve_dashboard')))

    def test_following_and_notification_pages(self):
        urls = [reverse('following'), reverse('notifications'), reverse('providers')]
        Follow.objects.create(follower=self.basic, provider=self.provider)
        Notification.objects.create(recipient=self.basic, kind='new_note', actor=self.provider, note=self.verified_note)
        client = self.client_for(self.basic)
        before = [self.queries(client, url) for url in urls]
        self.add_providers_with_notes(5)
        for author in Note.objects.exclude(provider=self.provider).values_list('provider', flat=True):
            Follow.objects.create(follower=self.basic, provider_id=author)
        for note in Note.objects.all():
            Notification.objects.create(recipient=self.basic, kind='new_note', actor=note.provider, note=note)
            Notification.objects.create(recipient=self.basic, kind='new_follower', actor=note.provider)
        self.assertEqual(before, [self.queries(client, url) for url in urls])

    def test_inbox_page(self):
        InboxMessage.objects.create(kind='contact', name='first', email='e@example.com', message='m', user=self.basic)
        client = self.client_for(self.moderator)
        before = self.queries(client, reverse('inbox'))
        for i in range(8):
            InboxMessage.objects.create(kind='contact', name=f'n{i}', email='e@example.com', message='m',
                                        user=make_user(f'sender_{i}'))
        self.assertEqual(before, self.queries(client, reverse('inbox')))
