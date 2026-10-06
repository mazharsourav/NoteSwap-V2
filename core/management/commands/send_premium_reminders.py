"""Run once a day (cron or the host's scheduler): Premium "ends in a week" and "has ended" notices."""
import logging
import time

from django.core.management.base import BaseCommand

from core.notifications import send_premium_reminders

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Send Premium "ends in a week" reminders (bell + email) and "has ended" notices (bell).'

    def handle(self, *args, **options):
        # Logged, because nobody watches a scheduled job's screen: a crash is an ERROR (emailed
        # to ADMINS) and still fails the job, so the host's scheduler shows it too.
        started = time.monotonic()
        logger.info('Premium reminders: started')
        try:
            reminded, ended = send_premium_reminders()
        except Exception:
            logger.exception('Premium reminders: crashed after %.1fs', time.monotonic() - started)
            raise
        logger.info('Premium reminders: done in %.1fs, %d ending soon, %d ended',
                    time.monotonic() - started, reminded, ended)
        self.stdout.write(f'Premium reminders: {reminded} ending soon, {ended} ended.')
