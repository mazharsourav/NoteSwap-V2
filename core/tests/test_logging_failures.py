"""
Logs L2: failures that used to vanish are now logged. Image sizes that can't be read, odd
errors behind "this image is damaged", files missing from storage, failed file clean-up,
email sends (without addresses) and the daily Premium job.
"""
import os
from io import StringIO
from unittest import mock

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.urls import reverse

from core import emails
from core.models import Note, NoteFile
from core.validators import log_if_unexpected, validate_upload
from core.views._helpers import image_size

from .test_security import SecurityTestCase, pdf_upload, png_bytes


class ImageErrorTests(SecurityTestCase):
    def test_unreadable_image_size_is_a_warning(self):
        with self.assertLogs('core.views._helpers', 'WARNING') as logs:
            self.assertIsNone(image_size(Note(file='notes/missing.png').file))
        self.assertIn('Could not read the size of image notes/missing.png', logs.output[0])

    def test_a_damaged_image_is_the_user_s_problem_and_not_logged(self):
        broken = SimpleUploadedFile('photo.png', b'\x89PNG\r\n\x1a\n' + b'not really a png')
        with self.assertNoLogs('core.validators', 'WARNING'):
            with self.assertRaisesMessage(ValidationError, 'damaged or not a valid image'):
                validate_upload(broken)

    def test_an_unexpected_error_is_logged_with_its_traceback_and_the_user_gets_the_same_message(self):
        upload = SimpleUploadedFile('photo.png', png_bytes())
        with mock.patch('core.validators.Image.open', side_effect=RuntimeError('bug in our code')):
            with self.assertLogs('core.validators', 'WARNING') as logs:
                with self.assertRaisesMessage(ValidationError, 'damaged or not a valid image'):
                    validate_upload(upload)
        self.assertIn("Unexpected error while reading the uploaded image 'photo.png'", logs.output[0])
        self.assertIn('RuntimeError: bug in our code', logs.output[0])

    def test_which_errors_count_as_a_bad_image(self):
        with self.assertNoLogs('core.validators'):
            log_if_unexpected(OSError('cannot identify image file'), 'x')
            log_if_unexpected(SyntaxError('broken PNG file'), 'x')
        with self.assertLogs('core.validators', 'WARNING'):
            log_if_unexpected(KeyError('mode'), 'x')


class MissingFileTests(SecurityTestCase):
    def setUp(self):
        self.note = Note.objects.create(
            name='Lost note', is_verified=True, file=pdf_upload('lost.pdf'), topic=self.topic,
            provider=self.provider, note_type='pdf', caption='c', year=1, semester=1, university='Test U',
        )
        self.stored_name = self.note.file.name
        os.remove(self.note.file.path)

    def test_missing_file_is_a_404_and_an_error(self):
        with self.assertLogs('core.views.files', 'ERROR') as logs:
            response = self.client_for(self.basic).get(reverse('note_file', args=[self.note.id]))
        self.assertEqual(response.status_code, 404)
        self.assertIn(f'Note #{self.note.id}: file missing from storage: {self.stored_name}', logs.output[0])

    def test_zip_still_downloads_and_the_missing_file_is_logged(self):
        with self.assertLogs('core.views.files', 'ERROR') as logs:
            response = self.client_for(self.basic).get(reverse('note_zip', args=[self.note.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn('file missing from storage', logs.output[0])


class FileCleanupTests(SecurityTestCase):
    def test_a_failed_delete_is_logged_and_does_not_break_the_page(self):
        extra = NoteFile.objects.create(note=self.verified_note, file=pdf_upload('stuck.pdf'))
        with mock.patch('django.core.files.storage.FileSystemStorage.delete', side_effect=PermissionError('in use')):
            with self.assertLogs('core.file_cleanup', 'ERROR') as logs:
                with self.captureOnCommitCallbacks(execute=True):
                    extra.delete()
        self.assertIn(f'Could not delete {extra.file.name} from storage (NoteFile.file)', logs.output[0])
        self.assertIn('PermissionError: in use', logs.output[0])


class EmailLogTests(SecurityTestCase):
    def send(self):
        with self.captureOnCommitCallbacks(execute=True):
            emails.send(['student@example.com'], 'Your Premium ends soon', 'premium_ending',
                        {'user': self.basic, 'link': 'http://x/'})

    def test_sent_emails_are_counted_not_listed(self):
        with self.assertLogs('core.emails', 'INFO') as logs:
            self.send()
        self.assertEqual(logs.records[0].getMessage(), 'Sent the premium_ending email to 1 address(es)')

    def test_failed_email_is_an_error_without_the_address(self):
        with mock.patch('core.emails.send_mail', side_effect=ConnectionRefusedError('smtp down')):
            with self.assertLogs('core.emails', 'ERROR') as logs:
                self.send()
        self.assertIn('Could not send the premium_ending email to 1 address(es)', logs.output[0])
        self.assertNotIn('student@example.com', '\n'.join(logs.output))


class ReminderJobLogTests(SecurityTestCase):
    def test_start_and_finish_are_logged(self):
        with self.assertLogs('core.management.commands.send_premium_reminders', 'INFO') as logs:
            call_command('send_premium_reminders', stdout=StringIO())
        self.assertEqual(logs.records[0].getMessage(), 'Premium reminders: started')
        self.assertRegex(logs.records[-1].getMessage(), r'^Premium reminders: done in [\d.]+s, 0 ending soon, 0 ended$')

    def test_a_crash_is_logged_and_still_fails_the_job(self):
        target = 'core.management.commands.send_premium_reminders.send_premium_reminders'
        with mock.patch(target, side_effect=RuntimeError('database gone')):
            with self.assertLogs('core.management.commands.send_premium_reminders', 'ERROR') as logs:
                with self.assertRaises(RuntimeError):
                    call_command('send_premium_reminders', stdout=StringIO())
        self.assertIn('Premium reminders: crashed', logs.output[0])
        self.assertIn('RuntimeError: database gone', logs.output[0])
