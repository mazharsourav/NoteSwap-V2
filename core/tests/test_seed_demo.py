"""`manage.py seed_demo`: demo accounts, UAP courses, sample notes; safe to run twice."""
from io import StringIO

from allauth.account.models import EmailAddress
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings

from core import demo_data
from core.models import (CustomUser, Follow, Note, NoteSolveRequest, Notification, PremiumPackage, Rating,
                         Subject)
from core.tests.test_security import MEDIA_ROOT

STRONG = 'Seed-test-pass!42'


def seed(*args):
    out = StringIO()
    call_command('seed_demo', *args, stdout=out)
    return out.getvalue()


@override_settings(MEDIA_ROOT=MEDIA_ROOT)
class SeedDemoTests(TestCase):
    def test_creates_the_whole_demo(self):
        seed('--admin-email', 'owner@example.com', '--admin-password', STRONG, '--demo-password', STRONG)

        admin = CustomUser.objects.get(username='admin')
        self.assertTrue(admin.is_superuser and admin.is_staff)
        self.assertEqual(CustomUser.objects.get(username='demo_moderator').user_type, 'moderator')
        self.assertEqual(CustomUser.objects.filter(user_type='provider').count(), 3)
        self.assertTrue(CustomUser.objects.get(username='demo_premium').is_premium)
        self.assertFalse(CustomUser.objects.get(username='demo_basic').is_premium)
        # Every account can sign in: confirmed email and the given password.
        for user in CustomUser.objects.all():
            self.assertTrue(EmailAddress.objects.filter(user=user, verified=True, primary=True).exists())
            self.assertTrue(user.check_password(STRONG))

        self.assertEqual(Subject.objects.count(), len(demo_data.COURSES))
        self.assertEqual(Note.objects.count(), len(demo_data.NOTES))
        self.assertEqual(Note.objects.filter(is_verified=True).count(),
                         sum(1 for note in demo_data.NOTES if note[3]))
        note = Note.objects.get(course_code='CSE 211')
        self.assertEqual((note.university, note.year, note.semester, note.note_type), ('UAP', 2, 2, 'pdf'))
        self.assertEqual(note.subject.name, 'Database Systems')
        with note.file.open('rb') as handle:
            self.assertTrue(handle.read().startswith(b'%PDF-1.4'))

        self.assertEqual(PremiumPackage.objects.count(), len(demo_data.PREMIUM_PACKAGES))
        self.assertTrue(Rating.objects.exists() and Follow.objects.exists())
        self.assertTrue(Notification.objects.filter(kind=Notification.Kind.NEW_NOTE).exists())
        self.assertEqual(NoteSolveRequest.objects.count(), 1)

    def test_running_twice_changes_nothing(self):
        seed('--admin-password', STRONG, '--demo-password', STRONG)
        counts = [model.objects.count() for model in (CustomUser, Subject, Note, Rating, Follow, PremiumPackage)]
        out = seed('--admin-password', 'Another-pass-99!', '--demo-password', 'Another-pass-99!')
        self.assertEqual(counts, [model.objects.count() for model in
                                  (CustomUser, Subject, Note, Rating, Follow, PremiumPackage)])
        self.assertTrue(CustomUser.objects.get(username='demo_basic').check_password(STRONG))  # unchanged
        self.assertIn('already exists, password unchanged', out)

    def test_generated_passwords_are_printed_once(self):
        out = seed()
        self.assertIn('Generated passwords', out)
        self.assertNotIn('Generated passwords', seed())  # nothing new was set

    def test_weak_password_refused(self):
        with self.assertRaisesMessage(CommandError, 'too weak'):
            seed('--demo-password', '123')
        self.assertFalse(CustomUser.objects.exists())

    def test_no_admin(self):
        seed('--no-admin', '--demo-password', STRONG)
        self.assertFalse(CustomUser.objects.filter(is_superuser=True).exists())

    def test_course_list_matches_the_uap_page(self):
        codes = [course[0] for course in demo_data.COURSES]
        self.assertEqual(len(codes), 59)
        self.assertEqual(len(set(codes)), 59)
        self.assertEqual(len({course[1] for course in demo_data.COURSES}), 59)  # course names are unique
        for code, *_ in demo_data.NOTES:
            self.assertIn(code, codes)
