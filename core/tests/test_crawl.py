"""
Every page, as every role, must answer without a server error.

Allowed answers: 200 (page), 302 (redirect), 403 (no permission), 404 (not
found / hidden), 405 (wrong method). Anything else, or an exception, fails.
"""
from django.test import Client
from django.urls import reverse

from core.models import Follow, Notification
from core.tests.test_security import SecurityTestCase

ALLOWED = {200, 302, 403, 404, 405}


class CrawlTests(SecurityTestCase):
    def urls(self):
        note, extra = self.verified_note, self.unverified_extra
        return [
            reverse(name, args=args) for name, args in [
                ('home', []), ('account_signup', []), ('account_login', []), ('logout', []),
                ('account_reset_password', []), ('account_email', []), ('account_change_password', []), ('profile', []), ('edit_profile', []),
                ('upload_note', []), ('verify_notes', []), ('subject_list', []),
                ('subject_detail', [self.subject.id]),
                ('note_detail', [note.id]), ('note_detail', [self.unverified_note.id]),
                ('edit_note', [note.id]), ('delete_note', [note.id]), ('note_files', [note.id]),
                ('add_subject', []),
                ('become_provider', []), ('provider_requests', []), ('provider_request_detail', [self.application.id]),
                ('provider_profile', [self.provider.id]), ('user_profile', [self.basic.id]),
                ('help_center', []), ('ask_question', []), ('send_feedback', []), ('terms_of_use', []),
                ('about', []), ('contact', []), ('following', []), ('notifications', []), ('search_users', []), ('providers', []),
                ('notesolve_dashboard', []), ('solve_request', [self.solve_request.id]),
                ('provider_solved_requests', []), ('premium_packages', []), ('add_premium_package', []),
                ('edit_premium_package', [self.package.id]), ('purchase_premium_package', [self.package.id]),
                ('checkout_pending', []), ('Manage', []), ('inbox', []), ('manage_premium', []),
                ('search', []), ('help_article', ['finding-notes']), ('socialaccount_connections', []),
                ('note_file', [note.id]), ('note_extra_file', [extra.id]),
                ('notesolve_file', [self.solve_file.id]), ('notesolve_solution_file', [self.solution.id]),
            ]
        ] + ['/search/?q=a', '/subjects/?q=phys&sort=year_desc', '/premium/approve/999/', '/notes/search/?q=opt',
             f'/subject/{self.subject.id}/?q=opt&sort=newest',  # old topic links: test_notes_pages
             f'/provider/{self.provider.id}/?tab=about', '/providers/?q=prov&sort=name', '/notesolve/?provider=1']

    def test_no_page_errors_for_any_role(self):
        Follow.objects.create(follower=self.basic, provider=self.provider)
        Notification.objects.create(recipient=self.basic, kind='new_note', actor=self.provider, note=self.verified_note)
        Notification.objects.create(recipient=self.provider, kind='new_follower', actor=self.basic)
        roles = {
            'anonymous': None, 'basic': self.basic, 'provider': self.provider,
            'moderator': self.moderator, 'superuser': self.superuser,
        }
        failures = []
        for role, user in roles.items():
            client = Client(raise_request_exception=False)
            if user:
                client.force_login(user)
            for url in self.urls():
                status = client.get(url).status_code
                if status not in ALLOWED:
                    failures.append(f'{role:10} {url} -> {status}')
        self.assertEqual(failures, [], '\n' + '\n'.join(failures))
