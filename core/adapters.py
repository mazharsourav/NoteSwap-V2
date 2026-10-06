"""django-allauth hooks (ACCOUNT_ADAPTER in settings)."""
import logging

from allauth.account.adapter import DefaultAccountAdapter
from django.core.exceptions import ValidationError

from .logs import client_ip, mask_email, security


class AccountAdapter(DefaultAccountAdapter):
    def pre_authenticate(self, request, **credentials):
        """Runs before each sign-in attempt; refuses it once ACCOUNT_RATE_LIMITS is used up.
        A refusal (someone guessing passwords, or a user who forgot theirs) is logged."""
        try:
            super().pre_authenticate(request, **credentials)
        except ValidationError:
            tried = credentials.get('username') or credentials.get('email') or '-'
            security('login.locked', level=logging.WARNING, tried=mask_email(tried), ip=client_ip(request))
            raise
