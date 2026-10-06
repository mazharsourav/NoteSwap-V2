"""
Who-did-what logs, part 2 (part 1, Premium, is test_audit.py).
L4: moderation (notes, extra files, provider applications, NoteSolve answers, the inbox).
L5: accounts and security (sign-ins, lockouts, sign-ups, passwords, role changes, refused access).
L6: content (uploads, edits, deletes, courses, NoteSolve requests, zip downloads, refused files).
"""
from datetime import timedelta
from io import BytesIO

from allauth.account import signals as account_signals
from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core.models import InboxMessage, Note, NoteFile, NoteSolveRequest, ProviderRequest, Subject

from .test_accounts import SIGNUP, verified
from .test_audit import AuditTestCase
from .test_rules import APPLICATION
from .test_security import PASSWORD, make_user, pdf_upload


# ========== L4: moderation ==========
class NoteReviewAuditTests(AuditTestCase):
    def review(self, user, **data):
        return self.post(user, 'verify_notes', data=data)

    def test_published_by_the_moderator(self):
        lines = self.audit_lines(self.review(self.moderator, verify_type='main', action='verify',
                                             note_ids=[self.unverified_note.id]))
        self.assertEqual(lines, [f'note.published note={self.unverified_note.id} name="Pending note" '
                                 f'provider=provider by=moderator'])

    def test_rejected_with_reason(self):
        lines = self.audit_lines(self.review(self.moderator, verify_type='main', action='reject',
                                             note_ids=[self.unverified_note.id], reason='Blurry'))
        self.assertEqual(lines, [f'note.rejected note={self.unverified_note.id} name="Pending note" '
                                 f'provider=provider by=moderator reason=Blurry'])

    def test_admin_actions_name_the_admin(self):
        lines = self.audit_lines(self.post(self.superuser, 'admin:core_note_changelist', data={
            'action': 'verify_notes', '_selected_action': [self.unverified_note.id]}))
        self.assertEqual(lines, [f'note.published note={self.unverified_note.id} name="Pending note" '
                                 f'provider=provider by=root'])

    def test_extra_files_approved_or_removed(self):
        lines = self.audit_lines(self.review(self.moderator, verify_type='extra', action='verify',
                                             file_ids=[self.unverified_extra.id, 'x']))
        self.assertEqual(lines, [f'note.files_approved files={self.unverified_extra.id} by=moderator'])
        spare = NoteFile.objects.create(note=self.verified_note, file=pdf_upload('spare.pdf'))
        lines = self.audit_lines(self.review(self.moderator, verify_type='extra', action='reject', file_ids=[spare.id]))
        self.assertEqual(lines, [f'note.files_removed files={spare.id} by=moderator'])

    def test_nothing_to_do_logs_nothing(self):
        self.assertNoAudit(self.review(self.moderator, verify_type='extra', action='verify', file_ids=[999999]))


class ProviderApplicationAuditTests(AuditTestCase):
    def test_applied_then_accepted_which_changes_the_role(self):
        newcomer = make_user('newcomer')
        lines = self.audit_lines(self.post(newcomer, 'become_provider', data=APPLICATION))
        application = ProviderRequest.objects.get(user=newcomer)
        self.assertEqual(lines, [f'provider.applied application={application.id} user=newcomer'])

        accept = self.post(self.moderator, 'provider_request_action', application.id, 'accept')
        with self.assertLogs('core.security', 'WARNING') as security:
            lines = self.audit_lines(accept)
        self.assertEqual(lines, [f'provider.accepted application={application.id} user=newcomer by=moderator'])
        self.assertEqual(security.records[0].getMessage(), 'role.changed user=newcomer before=basic after=provider')

    def test_rejected_refused_during_the_wait_then_reapplied(self):
        reject = self.post(self.moderator, 'provider_request_action', self.application.id, 'reject',
                           data={'reason': 'CGPA missing'})
        self.assertEqual(self.audit_lines(reject), [
            f'provider.rejected application={self.application.id} user=applicant by=moderator reason="CGPA missing"'])
        self.assertEqual(self.audit_lines(self.post(self.applicant, 'become_provider', data=APPLICATION)),
                         ['provider.apply_refused user=applicant why=cooldown'])
        ProviderRequest.objects.filter(id=self.application.id).update(reviewed_at=timezone.now() - timedelta(days=31))
        self.assertEqual(self.audit_lines(self.post(self.applicant, 'become_provider', data=APPLICATION)),
                         [f'provider.reapplied application={self.application.id} user=applicant'])


class NoteSolveAnswerAuditTests(AuditTestCase):
    def setUp(self):
        self.pending = NoteSolveRequest.objects.create(
            user=self.basic, requested_to=self.provider, university='Test U', department='CSE',
            semester='1', year=1, subject='Physics', topic='Optics', problem_description='help',
        )

    def test_rejected_with_reason(self):
        lines = self.audit_lines(self.post(self.provider, 'solve_request', self.pending.id,
                                           data={'action': 'reject', 'reason': 'Not my subject'}))
        self.assertEqual(lines, [f'notesolve.rejected request={self.pending.id} student=basic by=provider '
                                 f'reason="Not my subject"'])

    def test_solved(self):
        lines = self.audit_lines(self.post(self.provider, 'solve_request', self.pending.id,
                                           data={'solution_text': 'Use Snell’s law.'}))
        self.assertEqual(len(lines), 1)
        self.assertRegex(lines[0], rf'^notesolve\.solved request={self.pending.id} solution=\d+ student=basic '
                                   r'by=provider files=0$')


class InboxAuditTests(AuditTestCase):
    def test_received_without_the_message_text(self):
        lines = self.audit_lines(lambda: self.client_for(None).post(reverse('contact'), {
            'name': 'Visitor', 'email': 'v@example.com', 'message': 'My secret question'}))
        message = InboxMessage.objects.get(name='Visitor')
        self.assertEqual(lines, [f'inbox.received message={message.id} kind=contact user=-'])

    def test_resolved_and_reopened(self):
        message = InboxMessage.objects.create(kind='contact', name='Rafi', email='r@example.com', message='Hi')
        toggle = self.post(self.moderator, 'inbox_toggle', message.id)
        self.assertEqual(self.audit_lines(toggle), [f'inbox.resolved messages={message.id} by=moderator'])
        self.assertEqual(self.audit_lines(toggle), [f'inbox.reopened messages={message.id} by=moderator'])

    def test_admin_mark_resolved(self):
        message = InboxMessage.objects.create(kind='contact', name='Rafi', email='r@example.com', message='Hi')
        lines = self.audit_lines(self.post(self.superuser, 'admin:core_inboxmessage_changelist', data={
            'action': 'mark_resolved', '_selected_action': [message.id]}))
        self.assertEqual(lines, [f'inbox.resolved messages={message.id} by=root'])


# ========== L5: accounts and security ==========
class SignInSecurityTests(AuditTestCase):
    def setUp(self):
        cache.clear()  # allauth's sign-in rate limits
        verified(self.basic)

    def sign_in(self, login, password=PASSWORD, client=None):
        client = client or self.client_for(None)
        return lambda: client.post(reverse('account_login'), {'login': login, 'password': password})

    def test_sign_in(self):
        self.assertEqual(self.security_lines(self.sign_in('basic'), starting='login'),
                         ['login.ok user=basic method=password ip=127.0.0.1'])

    def test_failed_sign_in_masks_an_email(self):
        with self.assertLogs('core.security', 'WARNING') as logs:
            self.sign_in('basic', 'wrong')()
            self.sign_in('basic@example.com', 'wrong')()
        self.assertEqual([record.getMessage() for record in logs.records], [
            'login.failed tried=basic ip=127.0.0.1', 'login.failed tried=b***@example.com ip=127.0.0.1'])

    def test_lockout(self):
        client = self.client_for(None)
        for _ in range(5):
            self.sign_in('basic', 'wrong', client)()
        lines = self.security_lines(self.sign_in('basic', client=client), starting='login.locked')
        self.assertEqual(lines, ['login.locked tried=basic ip=127.0.0.1'])

    def test_logout(self):
        self.assertEqual(self.security_lines(self.post(self.basic, 'logout')), ['logout user=basic ip=127.0.0.1'])

    def test_django_admin_sign_in(self):
        lines = self.security_lines(lambda: self.client_for(None).post(
            reverse('admin:login'), {'username': 'root', 'password': PASSWORD}), starting='login')
        self.assertEqual(lines, ['login.ok user=root method=admin ip=127.0.0.1'])

    def test_passwords_never_reach_the_logs(self):
        with self.assertLogs('core', 'INFO') as logs:
            self.sign_in('basic', 'Wrong-pass-123')()
            self.sign_in('basic')()
        text = '\n'.join(logs.output)
        self.assertIn('login.ok', text)
        self.assertNotIn('Wrong-pass-123', text)
        self.assertNotIn(PASSWORD, text)


class AccountSecurityTests(AuditTestCase):
    def test_sign_up(self):
        lines = self.security_lines(lambda: self.client_for(None).post(reverse('account_signup'), SIGNUP),
                                    starting='signup')
        self.assertEqual(lines, ['signup user=newcomer method=password ip=127.0.0.1'])

    def test_email_verified(self):
        address = EmailAddress.objects.create(user=self.basic, email='basic@example.com', verified=True)
        lines = self.security_lines(lambda: account_signals.email_confirmed.send(
            sender=EmailAddress, request=None, email_address=address))
        self.assertEqual(lines, ['email.verified user=basic'])

    def test_password_changed(self):
        verified(self.basic)
        lines = self.security_lines(self.post(self.basic, 'account_change_password', data={
            'oldpassword': PASSWORD, 'password1': 'An0ther-strong-pass!', 'password2': 'An0ther-strong-pass!'}),
            starting='password')
        self.assertEqual(lines, ['password.changed user=basic ip=127.0.0.1'])

    def test_new_staff_account_and_blocking_are_role_changes(self):
        with self.assertLogs('core.security', 'WARNING') as logs:
            boss = make_user('boss', is_staff=True, is_superuser=True)
            boss.is_active = False
            boss.save()
        self.assertEqual([record.getMessage() for record in logs.records], [
            'role.changed user=boss before="new account" after=basic,is_staff,is_superuser',
            'role.changed user=boss before=basic,is_staff,is_superuser after=basic,is_staff,is_superuser,blocked',
        ])

    def test_ordinary_saves_are_not_role_changes(self):
        with self.assertNoLogs('core.security'):
            make_user('plain')
            self.basic.first_name = 'New'
            self.basic.save()
        with self.assertNumQueries(1):  # last_login on every sign-in: no extra lookup
            self.basic.save(update_fields=['last_login'])

    def test_profile_edit_names_fields_only(self):
        lines = self.audit_lines(self.post(self.basic, 'edit_profile', data={
            'first_name': 'Secretname', 'last_name': 'U', 'university': 'Test U', 'gender': 'Other'}))
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0].startswith('profile.edited user=basic fields='))
        self.assertIn('first_name', lines[0])
        self.assertNotIn('Secretname', lines[0])


class AccessDeniedTests(AuditTestCase):
    def denied(self, user, url):
        with self.assertLogs('core.security', 'INFO') as logs:
            response = self.client_for(user).get(url)
        return response, logs.records[0].getMessage()

    def test_wrong_role_is_a_403_and_logged(self):
        url = reverse('verify_notes')
        response, line = self.denied(self.basic, url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(line, f'access.denied user=basic path={url}')

    def test_someone_elses_note(self):
        url = reverse('edit_note', args=[self.verified_note.id])
        response, line = self.denied(self.other_provider, url)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(line, f'access.denied user=other_provider path={url}')

    def test_premium_needed(self):
        url = reverse('request_to_provider', args=[self.provider.id])
        self.assertEqual(self.denied(self.basic, url)[1], f'access.denied user=basic path={url} needs=premium')

    def test_provider_pages_for_students(self):
        url = reverse('provider_solved_requests')
        self.assertEqual(self.denied(self.basic, url)[1], f'access.denied user=basic path={url} needs=provider')


# ========== L6: content ==========
class NoteContentAuditTests(AuditTestCase):
    def note_form(self, **changes):
        return {'name': 'Waves', 'caption': 'c', 'term': '1-1', 'university': 'Test U', 'subject': self.subject.id,
                'file': pdf_upload('waves.pdf'), **changes}

    def test_uploaded(self):
        lines = self.audit_lines(self.post(self.provider, 'upload_note', data=self.note_form()))
        note = Note.objects.get(name='Waves')
        self.assertEqual(lines, [f'note.uploaded note={note.id} name=Waves course={self.subject.id} type=pdf by=provider'])

    def test_refused_file_names_the_reason(self):
        fake = SimpleUploadedFile('notes.pdf', b'this is not a pdf')
        lines = self.audit_lines(self.post(self.provider, 'upload_note', data=self.note_form(file=fake)))
        self.assertEqual(lines, ['upload.refused file=notes.pdf size_kb=0 why="contents do not match the name"'])
        self.assertFalse(Note.objects.filter(name='Waves').exists())

    def test_new_file_sends_a_published_note_back_to_review(self):
        edit = self.post(self.provider, 'edit_note', self.verified_note.id,
                         data=self.note_form(name='Published note', file=pdf_upload('new.pdf')))
        lines = self.audit_lines(edit)
        self.assertEqual(len(lines), 1)
        self.assertRegex(lines[0], rf'^note\.edited note={self.verified_note.id} fields=\S*file\S* '
                                   r'back_to_review="new file" by=provider$')

    def test_resubmitted_and_deleted(self):
        Note.objects.filter(id=self.unverified_note.id).update(rejected_at=timezone.now(), rejection_reason='x')
        self.assertEqual(self.audit_lines(self.post(self.provider, 'resubmit_note', self.unverified_note.id)),
                         [f'note.resubmitted note={self.unverified_note.id} by=provider'])
        self.assertEqual(self.audit_lines(self.post(self.provider, 'delete_note', self.unverified_note.id)),
                         [f'note.deleted note={self.unverified_note.id} name="Pending note" by=provider'])

    def test_extra_files_added_and_deleted(self):
        add = self.post(self.provider, 'note_files', self.verified_note.id,
                        data={'files': [pdf_upload('p1.pdf'), pdf_upload('p2.pdf')]})
        self.assertEqual(self.audit_lines(add), [f'note.files_added note={self.verified_note.id} count=2 by=provider'])
        extra = NoteFile.objects.filter(note=self.verified_note).latest('id')
        delete = self.post(self.provider, 'delete_note_file', self.verified_note.id, extra.id)
        self.assertEqual(self.audit_lines(delete),
                         [f'note.file_deleted note={self.verified_note.id} file={extra.id} by=provider'])

    def test_course_created(self):
        lines = self.audit_lines(self.post(self.provider, 'add_subject', data={'name': 'Optics II'}))
        course = Subject.objects.get(name='Optics II')
        self.assertEqual(lines, [f'course.created course={course.id} name="Optics II" by=provider'])

    def test_zip_download(self):
        lines = self.audit_lines(lambda: self.client_for(self.basic).get(
            reverse('note_zip', args=[self.verified_note.id])))
        self.assertEqual(lines, [f'download.zip note={self.verified_note.id} files=1 user=basic'])


class NoteSolveRequestAuditTests(AuditTestCase):
    def test_sent_and_resent(self):
        self.make_premium(self.basic)
        lines = self.audit_lines(self.post(self.basic, 'notesolve_dashboard', data={
            'provider_id': self.provider.id, 'university': 'Test U', 'department': 'CSE', 'semester': '1',
            'year': 1, 'subject': 'Physics', 'topic': 'Optics', 'problem_description': 'help'}))
        sent = NoteSolveRequest.objects.filter(user=self.basic).latest('id')
        self.assertEqual(lines, [f'notesolve.sent request={sent.id} user=basic to=provider files=0'])

        NoteSolveRequest.objects.filter(id=sent.id).update(status=NoteSolveRequest.Status.REJECTED)
        lines = self.audit_lines(self.post(self.basic, 'resend_solve_request', sent.id,
                                           data={'provider_id': self.other_provider.id}))
        self.assertEqual(lines, [f'notesolve.resent request={sent.id} user=basic to=other_provider'])


class ProfilePhotoRefusedTests(AuditTestCase):
    def test_wrong_photo_type(self):
        # A real image, but a GIF (Django's own image check refuses non-images before ours runs).
        gif = BytesIO()
        Image.new('RGB', (4, 4)).save(gif, 'GIF')
        lines = self.audit_lines(self.post(self.basic, 'edit_profile', data={
            'first_name': 'B', 'last_name': 'U', 'university': 'Test U', 'gender': 'Other',
            'profile_picture': SimpleUploadedFile('me.gif', gif.getvalue())}))
        self.assertIn('upload.refused file=me.gif size_kb=0 why="photo type"', lines)
