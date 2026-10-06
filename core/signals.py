"""
Security log (core.security) for accounts: sign-ins, sign-outs, sign-ups, email and password
changes, Google accounts, and any change to what a user is allowed to do (their role).

Connected in CoreConfig.ready(). Lockouts are logged by core.adapters.AccountAdapter.
Failed sign-ins show what was typed as the username; an email address is masked.
"""
import logging

from allauth.account import signals as account_signals
from allauth.socialaccount import signals as social_signals
from django.contrib.auth import signals as auth_signals
from django.db.models.signals import pre_save
from django.urls import reverse

from .logs import client_ip, mask_email, security, who
from .models import CustomUser

# What a user may do. A change to any of these is a WARNING, wherever it comes from
# (an accepted provider application, the Django admin, the shell).
ROLE_FIELDS = ('user_type', 'is_staff', 'is_superuser', 'is_active')


def _method(kwargs):
    return 'google' if kwargs.get('sociallogin') else 'password'


def site_login(sender, request, user, **kwargs):
    security('login.ok', user=user.username, method=_method(kwargs), ip=client_ip(request))


def admin_login(sender, request, user, **kwargs):
    # Django's own sign-in signal is also sent for allauth's sign-ins (logged above) and by tests'
    # force_login. Only the Django admin's sign-in page is logged from here.
    if request is not None and request.path.startswith(reverse('admin:index')):
        security('login.ok', user=user.username, method='admin', ip=client_ip(request))


def login_failed(sender, credentials, request=None, **kwargs):
    tried = credentials.get('username') or credentials.get('email') or '-'
    security('login.failed', level=logging.WARNING, tried=mask_email(tried), ip=client_ip(request))


def logged_out(sender, request, user, **kwargs):
    if user is not None:
        security('logout', user=user.username, ip=client_ip(request))


def signed_up(sender, request, user, **kwargs):
    security('signup', user=user.username, method=_method(kwargs), ip=client_ip(request))


def email_confirmed(sender, request, email_address, **kwargs):
    security('email.verified', user=email_address.user.username)


def password_event(event):
    def handler(sender, request, user, **kwargs):
        security(event, user=user.username, ip=client_ip(request))
    return handler


def google_added(sender, request, sociallogin, **kwargs):
    security('google.connected', user=who(sociallogin.user), ip=client_ip(request))


def google_removed(sender, request, socialaccount, **kwargs):
    security('google.disconnected', user=socialaccount.user.username, ip=client_ip(request))


def role_changes(sender, instance, update_fields=None, raw=False, **kwargs):
    if raw:
        return  # loading fixtures
    if update_fields is not None and not set(update_fields) & set(ROLE_FIELDS):
        return  # e.g. last_login on every sign-in: no extra query
    if instance.pk is None:
        old = None
    else:
        old = CustomUser.objects.filter(pk=instance.pk).values(*ROLE_FIELDS).first()
    new = {field: getattr(instance, field) for field in ROLE_FIELDS}
    if old is None:
        # A new account: only worth a line when it starts with more than a basic user's rights.
        if new['user_type'] != 'basic' or new['is_staff'] or new['is_superuser']:
            security('role.changed', level=logging.WARNING, user=instance.username, before='new account',
                     after=_role_text(new))
        return
    if old != new:
        security('role.changed', level=logging.WARNING, user=instance.username,
                 before=_role_text(old), after=_role_text(new))


def _role_text(values):
    flags = [name for name in ('is_staff', 'is_superuser') if values[name]]
    if not values['is_active']:
        flags.append('blocked')
    return ','.join([values['user_type'], *flags])


# (signal, handler) pairs. weak=False: the password handlers are made on the fly and would
# otherwise be garbage-collected.
CONNECTIONS = [
    (account_signals.user_logged_in, site_login),
    (auth_signals.user_logged_in, admin_login),
    (auth_signals.user_login_failed, login_failed),
    (auth_signals.user_logged_out, logged_out),
    (account_signals.user_signed_up, signed_up),
    (account_signals.email_confirmed, email_confirmed),
    (account_signals.password_changed, password_event('password.changed')),
    (account_signals.password_set, password_event('password.set')),
    (account_signals.password_reset, password_event('password.reset')),
    (social_signals.social_account_added, google_added),
    (social_signals.social_account_removed, google_removed),
]


def connect():
    for number, (signal, handler) in enumerate(CONNECTIONS):
        signal.connect(handler, weak=False, dispatch_uid=f'security-log-{number}')
    pre_save.connect(role_changes, sender=CustomUser, dispatch_uid='security-log-roles')
