"""
Logging helpers. The logging setup itself is LOGGING in config/settings.py.

Three loggers:
  core           errors and problems (each module uses logging.getLogger(__name__))
  core.audit     who did what: money, moderation, content         -> audit()
  core.security  sign-ins, refused access, suspicious requests    -> security()

audit() and security() write one searchable line per event:
  premium.approved order=12 user=alice by=admin1 reason="Paid twice"

Never pass passwords, tokens, links from emails, file contents or message text.
"""
import logging
import re

from django.views.debug import SafeExceptionReporterFilter

audit_logger = logging.getLogger('core.audit')
security_logger = logging.getLogger('core.security')

MAX_VALUE_LENGTH = 200


def clean(value):
    """One line, at most MAX_VALUE_LENGTH characters. Collapsing line breaks means text a user
    typed (a rejection reason, a title) can never start a fake log line."""
    text = ' '.join(str(value).split())
    if len(text) > MAX_VALUE_LENGTH:
        text = text[:MAX_VALUE_LENGTH - 3] + '...'
    return text


def _quoted(value):
    text = clean(value)
    if not text or any(char in text for char in ' ="'):
        text = '"' + text.replace('"', "'") + '"'
    return text


def event_line(event, fields):
    return ' '.join([event, *(f'{key}={_quoted(value)}' for key, value in fields.items())])


def who(user):
    """How a person appears in the logs: their username, or "-" for nobody / a visitor."""
    return user.username if user is not None and user.is_authenticated else '-'


def client_ip(request):
    # The address the request came from. Behind the host's proxy this becomes the proxy's
    # address; the real visitor header is set up at hosting time (logs L7).
    if request is None:
        return '-'
    return request.META.get('REMOTE_ADDR') or '-'


def mask_email(text):
    """'student@example.com' -> 's***@example.com'. Anything without an @ is returned as it is."""
    text = str(text or '')
    local, at, domain = text.partition('@')
    return f'{local[:1]}***@{domain}' if at else text


def audit(event, level=logging.INFO, **fields):
    if audit_logger.isEnabledFor(level):
        audit_logger.log(level, '%s', event_line(event, fields))


def security(event, level=logging.INFO, **fields):
    if security_logger.isEnabledFor(level):
        security_logger.log(level, '%s', event_line(event, fields))


class SafeReporterFilter(SafeExceptionReporterFilter):
    """Error emails to ADMINS: Django already hides settings, cookies and headers whose names
    look secret (KEY, TOKEN, PASS...), but not the login cookie `sessionid`, which would let
    anyone reading the email sign in as that user. SESSION is added to the list."""
    hidden_settings = re.compile('API|AUTH|TOKEN|KEY|SECRET|PASS|SIGNATURE|HTTP_COOKIE|SESSION', flags=re.I)
