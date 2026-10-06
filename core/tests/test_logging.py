"""
Logging setup (logs L1): the LOGGING settings, the core/logs.py helpers, error emails to
ADMINS without the login cookie, and the optional log files.
"""
import logging
import logging.config
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core import mail
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import path

from config import urls as site_urls
from config.settings import admins_from, logging_config
from core.logs import MAX_VALUE_LENGTH, SafeReporterFilter, audit, event_line, security

from .test_security import PASSWORD, make_user

ADMINS = [('Admin', 'admin@example.com')]


def crash(request):
    raise RuntimeError('boom for the logging test')


urlpatterns = [path('crash/', crash), *site_urls.urlpatterns]  # the error pages link to real pages


class Collect(logging.Handler):
    """Records what reaches a logger's handlers, without changing the logger's level
    (assertLogs lowers the level, which would hide what the real settings let through)."""

    def __init__(self, logger_name):
        super().__init__()
        self.records = []
        self.logger = logging.getLogger(logger_name)

    def emit(self, record):
        self.records.append(record)

    def __enter__(self):
        self.logger.addHandler(self)
        return self.records

    def __exit__(self, *exc):
        self.logger.removeHandler(self)


class EventLineTests(SimpleTestCase):
    def test_key_value_line(self):
        self.assertEqual(event_line('premium.approved', {'order': 12, 'by': 'admin1'}),
                         'premium.approved order=12 by=admin1')

    def test_values_with_spaces_or_quotes_are_quoted(self):
        self.assertEqual(event_line('note.rejected', {'reason': 'Too "blurry" scan'}),
                         'note.rejected reason="Too \'blurry\' scan"')
        self.assertEqual(event_line('x', {'reason': ''}), 'x reason=""')

    def test_typed_text_cannot_start_a_fake_log_line(self):
        line = event_line('note.rejected', {'reason': 'ok\n2026-10-06 INFO core.audit premium.approved'})
        self.assertNotIn('\n', line)
        self.assertNotIn('\r', event_line('x', {'reason': 'a\r\nb'}))

    def test_long_values_are_cut(self):
        line = event_line('x', {'reason': 'word ' * 200})
        value = line.split('=', 1)[1].strip('"')
        self.assertEqual(len(value), MAX_VALUE_LENGTH)
        self.assertTrue(value.endswith('...'))

    def test_audit_and_security_use_their_own_loggers(self):
        with self.assertLogs('core.audit', 'INFO') as logs:
            audit('premium.approved', order=1)
        self.assertEqual(logs.records[0].getMessage(), 'premium.approved order=1')
        with self.assertLogs('core.security', 'WARNING') as logs:
            security('login.failed', level=logging.WARNING, username='x')
        self.assertEqual(logs.records[0].levelname, 'WARNING')


class AdminsSettingTests(SimpleTestCase):
    def test_names_and_bare_addresses(self):
        self.assertEqual(admins_from(['Mazhar <m@example.com>', 'b@example.com', 'not an email', '']),
                         [('Mazhar', 'm@example.com'), ('b@example.com', 'b@example.com')])


class LevelTests(SimpleTestCase):
    def test_levels(self):
        level = logging.getLogger
        self.assertEqual(level('core').getEffectiveLevel(), logging.INFO)
        self.assertEqual(level('core.audit').getEffectiveLevel(), logging.INFO)
        self.assertEqual(level('core.views.notes').getEffectiveLevel(), logging.INFO)
        self.assertEqual(level('django.request').getEffectiveLevel(), logging.ERROR)
        self.assertEqual(level('django.security').getEffectiveLevel(), logging.WARNING)
        self.assertEqual(level('django.db.backends').getEffectiveLevel(), logging.WARNING)
        self.assertEqual(settings.DEFAULT_EXCEPTION_REPORTER_FILTER, 'core.logs.SafeReporterFilter')

    def test_console_is_quiet_only_while_testing(self):
        self.assertTrue(settings.TESTING)
        self.assertEqual(settings.LOGGING['handlers']['console']['level'], 'CRITICAL')
        self.assertNotIn('level', logging_config('INFO')['handlers']['console'])

    def test_runserver_lines_keep_their_own_format(self):
        server = logging.getLogger('django.server')
        self.assertFalse(server.propagate)
        self.assertEqual(type(server.handlers[0].formatter).__name__, 'ServerFormatter')


@override_settings(ROOT_URLCONF=__name__, ADMINS=ADMINS)
class RequestLoggingTests(TestCase):
    def setUp(self):
        self.client = Client(raise_request_exception=False)

    def test_404_is_not_logged_or_emailed(self):
        with Collect('django.request') as records:
            self.assertEqual(self.client.get('/no-such-page/').status_code, 404)
        self.assertEqual(records, [])
        self.assertEqual(mail.outbox, [])

    def test_crash_is_logged_with_traceback_and_emailed_without_the_login_cookie(self):
        self.client.login(username=make_user('crasher').username, password=PASSWORD)
        session_id = self.client.cookies[settings.SESSION_COOKIE_NAME].value
        with Collect('django.request') as records:
            self.assertEqual(self.client.get('/crash/').status_code, 500)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].levelname, 'ERROR')
        self.assertIsNotNone(records[0].exc_info)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.to, ['admin@example.com'])
        self.assertTrue(email.subject.startswith('[NoteSwap error] '))
        self.assertIn('boom for the logging test', email.body)
        self.assertNotIn(session_id, email.body)


@override_settings(ADMINS=ADMINS)
class ErrorEmailTests(SimpleTestCase):
    def test_errors_from_our_code_are_emailed(self):
        logging.getLogger('core.file_cleanup').error('Could not delete %s', 'notes/x.pdf')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Could not delete notes/x.pdf', mail.outbox[0].subject)

    def test_info_and_warnings_are_not_emailed(self):
        audit('premium.approved', order=1)
        logging.getLogger('core').warning('just a warning')
        self.assertEqual(mail.outbox, [])

    @override_settings(DEBUG=True)
    def test_no_emails_while_developing(self):
        logging.getLogger('core').error('local error')
        self.assertEqual(mail.outbox, [])

    def test_reporter_filter_hides_the_login_cookie(self):
        request = RequestFactory().get('/')
        request.COOKIES = {'sessionid': 'secret-session', 'csrftoken': 'secret-csrf', 'theme': 'dark'}
        cookies = SafeReporterFilter().get_safe_cookies(request)
        self.assertNotIn('secret-session', cookies.values())
        self.assertNotIn('secret-csrf', cookies.values())
        self.assertEqual(cookies['theme'], 'dark')


class LogFileTests(SimpleTestCase):
    def setUp(self):
        self.folder = Path(tempfile.mkdtemp(prefix='noteswap-test-logs-'))
        self.addCleanup(shutil.rmtree, self.folder, ignore_errors=True)
        # Put the real settings back (this also closes the test's log files).
        self.addCleanup(logging.config.dictConfig, settings.LOGGING)

    def test_main_file_gets_everything_and_audit_file_only_audit_and_security(self):
        main, audit_file = self.folder / 'sub' / 'noteswap.log', self.folder / 'audit.log'
        logging.config.dictConfig(logging_config('INFO', main, audit_file, quiet_console=True))
        audit('premium.approved', order=7)
        security('login.failed', level=logging.WARNING, username='x')
        logging.getLogger('core.emails').warning('something odd')
        logging.getLogger('core').debug('hidden at INFO')
        for handler in logging.getLogger().handlers + logging.getLogger('core.audit').handlers:
            handler.flush()

        main_text = main.read_text(encoding='utf-8')
        self.assertIn('INFO core.audit premium.approved order=7', main_text)
        self.assertIn('WARNING core.security login.failed username=x', main_text)
        self.assertIn('WARNING core.emails something odd', main_text)
        self.assertNotIn('hidden at INFO', main_text)

        audit_text = audit_file.read_text(encoding='utf-8')
        self.assertIn('premium.approved order=7', audit_text)
        self.assertIn('login.failed username=x', audit_text)
        self.assertNotIn('something odd', audit_text)

    def test_files_are_capped(self):
        config = logging_config('INFO', self.folder / 'a.log', self.folder / 'b.log')
        for name in ('file', 'audit_file'):
            self.assertEqual(config['handlers'][name]['maxBytes'], 5 * 1024 * 1024)
            self.assertEqual(config['handlers'][name]['backupCount'], 5)

    def test_no_files_unless_asked(self):
        config = logging_config('INFO')
        self.assertNotIn('file', config['handlers'])
        self.assertEqual(config['loggers']['core.audit']['handlers'], [])
