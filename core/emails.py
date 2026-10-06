"""
Emails, only for things people need to hear about even when they're not on the site:
Premium approved / rejected / ending soon, and new Premium orders for admins.
Everything else is a bell notification only (core/notifications.py).
"""
import logging

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)


def site_link(url_name, *args):
    return settings.SITE_URL + reverse(url_name, args=args)


def send(recipients, subject, template, context=None):
    """Send `templates/emails/<template>.txt` once the current transaction commits.

    Addresses that are empty are skipped. A failed send is logged and never breaks the page.
    Logs name the template and count the recipients; addresses and subjects (which can hold a
    student's name) stay out of the logs.
    """
    recipients = sorted({address for address in recipients if address})
    if not recipients:
        return
    body = render_to_string(f'emails/{template}.txt', {'site_url': settings.SITE_URL, **(context or {})})

    def deliver():
        try:
            send_mail(f'[NoteSwap] {subject}', body, None, recipients)
        except Exception:
            logger.exception('Could not send the %s email to %d address(es)', template, len(recipients))
        else:
            logger.info('Sent the %s email to %d address(es)', template, len(recipients))

    transaction.on_commit(deliver)
