"""Creating in-app notifications (shown under the navbar bell), plus the few that also email.
Premium changes are also written to the audit log here, so the Manage pages and the Django admin
actions (which both come through these functions) are logged the same way."""
import logging
from collections import defaultdict
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import emails
from .logs import audit, who
from .models import CustomUser, Follow, Note, Notification

# Premium: remind this long before it ends; tell users it ended if that happened this recently
# (older endings are skipped so a first run doesn't announce long-gone Premium).
PREMIUM_REMINDER_BEFORE = timedelta(days=7)
PREMIUM_ENDED_LOOKBACK = timedelta(days=7)

Kind = Notification.Kind


def _day(moment):
    return timezone.localtime(moment).strftime('%Y-%m-%d') if moment else '-'


def _name(user):
    return user.username if user else '-'


def _for_log(notes):
    return notes.select_related('provider').only('id', 'name', 'provider_id', 'provider__username')


@transaction.atomic
def publish_notes(notes, by=None):
    """
    Mark notes as verified and tell their providers' followers.

    `notes` is a queryset of Note. Each note is announced only the first time it is
    published, not again when it returns from re-review after a file change.
    `by` (the moderator) goes into the audit log.
    Returns the number of notes that were published by this call.
    """
    pending = list(_for_log(notes.filter(is_verified=False)))
    if not pending:
        return 0
    Note.objects.filter(id__in=[note.id for note in pending]).update(
        is_verified=True, rejected_at=None, rejection_reason='',
    )

    announced = set(
        Notification.objects.filter(kind=Kind.NEW_NOTE, note__in=pending).order_by().values_list('note_id', flat=True)
    )
    followers = defaultdict(list)
    for provider_id, follower_id in Follow.objects.filter(
        provider_id__in={note.provider_id for note in pending}
    ).values_list('provider_id', 'follower_id'):
        followers[provider_id].append(follower_id)

    Notification.objects.bulk_create([
        Notification(recipient_id=follower_id, kind=Kind.NEW_NOTE, actor_id=note.provider_id, note_id=note.id)
        for note in pending if note.id not in announced
        for follower_id in followers[note.provider_id]
    ])
    for note in pending:
        audit('note.published', note=note.id, name=note.name, provider=note.provider.username, by=who(by))
    return len(pending)


@transaction.atomic
def reject_notes(notes, reason, by=None):
    """
    Mark notes as rejected with a reason and tell each provider. The note stays (hidden from
    readers); the provider sees the reason on it and can fix it and send it for review again.
    Returns the number of notes rejected.
    """
    pending = list(_for_log(notes.awaiting_review()))
    if not pending:
        return 0
    Note.objects.filter(id__in=[note.id for note in pending]).update(
        rejected_at=timezone.now(), rejection_reason=reason,
    )
    Notification.objects.bulk_create([
        Notification(recipient_id=note.provider_id, kind=Kind.NOTE_REJECTED, note_id=note.id) for note in pending
    ])
    for note in pending:
        audit('note.rejected', note=note.id, name=note.name, provider=note.provider.username, by=who(by),
              reason=reason)
    return len(pending)


def notify_new_follower(follow):
    # At most one per follower: unfollowing removes it (withdraw_new_follower), so
    # following and unfollowing repeatedly can't pile up notifications.
    Notification.objects.get_or_create(
        recipient_id=follow.provider_id, kind=Kind.NEW_FOLLOWER, actor_id=follow.follower_id,
    )


def withdraw_new_follower(follower, provider):
    """Remove the 'started following you' notification when someone unfollows."""
    Notification.objects.filter(recipient=provider, kind=Kind.NEW_FOLLOWER, actor=follower).delete()


# ========== Premium ==========
def premium_order_placed(purchase):
    """Tell every superuser (bell + email) that an order is waiting for its payment check."""
    audit('premium.ordered', order=purchase.id, user=_name(purchase.user), package=purchase.package_name,
          amount=purchase.amount, months=purchase.duration_in_months)
    admins = list(CustomUser.objects.filter(is_superuser=True, is_active=True))
    Notification.objects.bulk_create([
        Notification(recipient=admin, kind=Kind.PREMIUM_ORDER, actor_id=purchase.user_id, purchase=purchase)
        for admin in admins
    ])
    student = purchase.user
    emails.send([admin.email for admin in admins],
                f'New Premium order from {student.get_full_name() or student.username}', 'premium_order',
                {'purchase': purchase, 'student': student, 'link': emails.site_link('manage_premium')})


def _order_handled(purchase):
    # The other admins' "new order" notifications are done with once someone reviews it.
    Notification.objects.filter(kind=Kind.PREMIUM_ORDER, purchase=purchase).update(is_read=True)


def approve_purchase(purchase, reviewer):
    """Approve (adds the months), then tell the student. False if it was already reviewed."""
    with transaction.atomic():
        if not purchase.approve(reviewer):
            _already_handled(purchase, reviewer, 'approve')
            return False
        _order_handled(purchase)
        Notification.objects.create(recipient=purchase.user, kind=Kind.PREMIUM_APPROVED, purchase=purchase)
        emails.send([purchase.user.email], 'Your Premium is active', 'premium_approved',
                    {'user': purchase.user, 'purchase': purchase, 'link': emails.site_link('notesolve_dashboard')})
    audit('premium.approved', order=purchase.id, user=_name(purchase.user), by=_name(reviewer),
          amount=purchase.amount, months=purchase.duration_in_months,
          starts=_day(purchase.starts_at), ends=_day(purchase.ends_at))
    return True


def reject_purchase(purchase, reason, reviewer):
    """Reject with a reason, then tell the student. False if it was already reviewed."""
    with transaction.atomic():
        if not purchase.reject(reason, reviewer):
            _already_handled(purchase, reviewer, 'reject')
            return False
        _order_handled(purchase)
        Notification.objects.create(recipient=purchase.user, kind=Kind.PREMIUM_REJECTED, purchase=purchase)
        emails.send([purchase.user.email], "Your Premium order wasn't approved", 'premium_rejected',
                    {'user': purchase.user, 'purchase': purchase, 'link': emails.site_link('premium_packages')})
    audit('premium.rejected', order=purchase.id, user=_name(purchase.user), by=_name(reviewer), reason=reason)
    return True


def _already_handled(purchase, reviewer, action):
    # Two admins on the same order at once, or a double click: harmless, but worth seeing.
    audit('premium.already_handled', level=logging.WARNING, order=purchase.id, by=_name(reviewer), tried=action)


def send_premium_reminders(now=None):
    """
    Daily job (`manage.py send_premium_reminders`): "ends in a week" (bell + email) and
    "has ended" (bell only). Safe to run any number of times: each Premium end date gets at
    most one of each, and a renewal (a later end date) gets its own.
    Returns (reminded, ended) counts.
    """
    now = now or timezone.now()
    reminded = ended = 0
    for user in CustomUser.objects.filter(premium_until__gt=now, premium_until__lte=now + PREMIUM_REMINDER_BEFORE):
        already = Notification.objects.filter(
            recipient=user, kind=Kind.PREMIUM_ENDING, created_at__gte=user.premium_until - PREMIUM_REMINDER_BEFORE,
        ).exists()
        if not already:
            Notification.objects.create(recipient=user, kind=Kind.PREMIUM_ENDING)
            emails.send([user.email], 'Your Premium ends soon', 'premium_ending',
                        {'user': user, 'link': emails.site_link('premium_packages')})
            audit('premium.reminded', user=user.username, ends=_day(user.premium_until))
            reminded += 1
    for user in CustomUser.objects.filter(premium_until__lte=now, premium_until__gt=now - PREMIUM_ENDED_LOOKBACK):
        if not Notification.objects.filter(recipient=user, kind=Kind.PREMIUM_ENDED,
                                           created_at__gte=user.premium_until).exists():
            Notification.objects.create(recipient=user, kind=Kind.PREMIUM_ENDED)
            audit('premium.ended', user=user.username, ended=_day(user.premium_until))
            ended += 1
    return reminded, ended
