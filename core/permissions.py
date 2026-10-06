"""
Role checks and view decorators.

Roles:
- superuser: full control (packages, payments, users) and everything below
- moderator: content moderation (verify notes/files, review provider applications)
- provider:  publishes notes and answers NoteSolve requests
- basic:     everyone else

Premium is not a role: it's paid time on the account (CustomUser.is_premium) that
unlocks NoteSolve for asking questions.

Anonymous users are sent to the login page; signed-in users without the
required role get a 403 (logged as access.denied by core.views.pages.permission_denied).
"""
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .logs import security

PREMIUM_NEEDED = "You need Premium to ask questions on NoteSolve."


def is_superadmin(user):
    return user.is_authenticated and user.is_superuser


def is_moderator(user):
    return user.is_authenticated and (user.is_superuser or user.user_type == 'moderator')


def is_provider(user):
    return user.is_authenticated and (user.is_superuser or user.user_type == 'provider')


def is_premium(user):
    return user.is_authenticated and user.is_premium


def can_manage_note(user, note):
    """Owner or moderator: may see the note and its files even before verification."""
    return user.is_authenticated and (note.provider_id == user.id or is_moderator(user))


def can_view_note(user, note):
    return user.is_authenticated and (note.is_verified or can_manage_note(user, note))


def role_required(check):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not check(request.user):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


superuser_required = role_required(is_superadmin)
moderator_required = role_required(is_moderator)
provider_required = role_required(is_provider)


def premium_required(view):
    """Signed-in users without active Premium go back to the home page with a message."""
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not is_premium(request.user):
            security('access.denied', user=request.user.username, path=request.path, needs='premium')
            messages.error(request, PREMIUM_NEEDED)
            return redirect('home')
        return view(request, *args, **kwargs)
    return wrapper
