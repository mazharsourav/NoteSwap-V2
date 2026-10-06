"""
Accounts (django-allauth): sign up with email verification, sign in by username or
email, lockout, password reset, and Google sign-in with the "complete your profile" step.
"""
import re
from unittest import mock
from urllib.parse import parse_qs, urlparse

from allauth.account.models import EmailAddress
from allauth.socialaccount.models import SocialAccount
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse

from core.models import CustomUser
from core.tests.test_security import PASSWORD, SecurityTestCase, make_user

SIGNUP = {
    'username': 'newcomer', 'email': 'new@example.com', 'first_name': 'Nadia', 'last_name': 'Islam',
    'university': 'BRAC University', 'gender': 'female', 'password1': PASSWORD, 'password2': PASSWORD,
}


def verified(user, email=None):
    """Give a test user a verified email address, as every real account has."""
    email = email or f'{user.username}@example.com'
    user.email = email
    user.save(update_fields=['email'])
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user


def link_in_last_email(path_fragment):
    match = re.search(r'https?://testserver(' + re.escape(path_fragment) + r'\S*)', mail.outbox[-1].body)
    assert match, mail.outbox[-1].body
    return match.group(1)


class SignupTests(SecurityTestCase):
    def setUp(self):
        cache.clear()

    @override_settings(GOOGLE_CLIENT_ID='')  # independent of the keys in the local .env
    def test_signup_page_shows_the_profile_fields(self):
        response = self.client_for(None).get(reverse('account_signup'))
        for field in ('username', 'email', 'first_name', 'last_name', 'university_choice', 'university_other',
                      'gender', 'password1'):
            self.assertContains(response, f'name="{field}"')
        self.assertContains(response, 'University of Asia Pacific (UAP)')  # the university list
        self.assertNotContains(response, 'google-btn')  # no Google button without keys

    def test_signup_creates_a_basic_user_and_sends_a_verification_email(self):
        client = self.client_for(None)
        response = client.post(reverse('account_signup'), {**SIGNUP, 'user_type': 'moderator'})
        self.assertRedirects(response, reverse('account_email_verification_sent'), fetch_redirect_response=False)

        user = CustomUser.objects.get(username='newcomer')
        self.assertEqual((user.first_name, user.university, user.gender, user.user_type),
                         ('Nadia', 'BRACU', 'Female', 'basic'))  # matched to the university list and the gender choice
        self.assertFalse(EmailAddress.objects.get(user=user).verified)
        self.assertNotIn('_auth_user_id', client.session)  # not signed in until verified

        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['new@example.com'])
        self.assertIn('NoteSwap', mail.outbox[0].subject + mail.outbox[0].body)

    def test_confirming_the_email_signs_you_in_and_returns_to_next(self):
        client = self.client_for(None)
        target = reverse('note_detail', args=[self.verified_note.id])
        client.post(f"{reverse('account_signup')}?next={target}", SIGNUP)

        confirm_url = link_in_last_email('/accounts/confirm-email/')
        self.assertEqual(client.get(confirm_url).status_code, 200)  # shows a Confirm button
        response = client.post(confirm_url)
        self.assertRedirects(response, target, fetch_redirect_response=False)
        self.assertTrue(EmailAddress.objects.get(email='new@example.com').verified)
        self.assertIn('_auth_user_id', client.session)

    def test_signup_ignores_external_next(self):
        client = self.client_for(None)
        client.post(f"{reverse('account_signup')}?next=https://evil.example/", SIGNUP)
        response = client.post(link_in_last_email('/accounts/confirm-email/'))
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_email_already_in_use_creates_nothing_and_warns_the_owner(self):
        # To stop strangers finding out who has an account, the page looks the same as a
        # normal sign-up; the address owner gets an "you already have an account" email.
        verified(make_user('taken'), 'new@example.com')
        response = self.client_for(None).post(reverse('account_signup'), SIGNUP)
        self.assertRedirects(response, reverse('account_email_verification_sent'), fetch_redirect_response=False)
        self.assertFalse(CustomUser.objects.filter(username='newcomer').exists())
        self.assertEqual(mail.outbox[-1].to, ['new@example.com'])
        self.assertIn('already', mail.outbox[-1].body)

    def test_missing_profile_fields_show_errors(self):
        response = self.client_for(None).post(reverse('account_signup'), {**SIGNUP, 'university': ''})
        self.assertContains(response, 'class="field-error"')
        self.assertFalse(CustomUser.objects.filter(username='newcomer').exists())

    def test_old_register_and_login_urls_redirect(self):
        client = self.client_for(None)
        self.assertRedirects(client.get('/register/?next=/providers/'), reverse('account_signup') + '?next=/providers/',
                             fetch_redirect_response=False)
        self.assertRedirects(client.get('/login/'), reverse('account_login'), fetch_redirect_response=False)


class LoginTests(SecurityTestCase):
    def setUp(self):
        cache.clear()
        verified(self.basic)

    def login(self, client, login, password=PASSWORD, query=''):
        return client.post(reverse('account_login') + query, {'login': login, 'password': password})

    def test_sign_in_with_username_or_email(self):
        for identifier in ('basic', 'basic@example.com'):
            client = self.client_for(None)
            self.assertRedirects(self.login(client, identifier), reverse('home'), fetch_redirect_response=False)
            self.assertEqual(int(client.session['_auth_user_id']), self.basic.id)

    def test_next_is_kept_but_never_off_site(self):
        target = reverse('note_detail', args=[self.verified_note.id])
        response = self.login(self.client_for(None), 'basic', query=f'?next={target}')
        self.assertRedirects(response, target, fetch_redirect_response=False)
        response = self.login(self.client_for(None), 'basic', query='?next=https://evil.example/')
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)

    def test_wrong_password_shows_an_error(self):
        response = self.login(self.client_for(None), 'basic', 'wrong')
        self.assertContains(response, 'login-error')
        self.assertContains(response, 'not correct')

    def test_lockout_after_five_failures(self):
        client = self.client_for(None)
        for _ in range(5):
            self.login(client, 'basic', 'wrong')
        response = self.login(client, 'basic')  # right password, but locked out
        self.assertContains(response, 'Too many failed login attempts')
        self.assertNotIn('_auth_user_id', client.session)

    def test_unverified_email_must_be_confirmed_first(self):
        user = make_user('fresh', email='fresh@example.com')
        EmailAddress.objects.create(user=user, email='fresh@example.com', verified=False, primary=True)
        client = self.client_for(None)
        response = self.login(client, 'fresh')
        self.assertRedirects(response, reverse('account_email_verification_sent'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', client.session)
        self.assertEqual(mail.outbox[-1].to, ['fresh@example.com'])

    def test_account_without_any_email_is_asked_for_one_not_crashed(self):
        make_user('noemail')
        client = self.client_for(None)
        response = self.login(client, 'noemail')
        self.assertLess(response.status_code, 500)
        self.assertNotIn('_auth_user_id', client.session)

    def test_login_page_links(self):
        response = self.client_for(None).get(reverse('account_login'))
        self.assertContains(response, reverse('account_reset_password'))
        self.assertContains(response, reverse('account_signup'))
        self.assertContains(response, 'name="login"')


class PasswordResetTests(SecurityTestCase):
    def setUp(self):
        cache.clear()
        verified(self.basic)

    def test_reset_by_email_link(self):
        client = self.client_for(None)
        response = client.post(reverse('account_reset_password'), {'email': 'basic@example.com'})
        self.assertRedirects(response, reverse('account_reset_password_done'), fetch_redirect_response=False)
        self.assertEqual(mail.outbox[-1].to, ['basic@example.com'])

        response = client.get(link_in_last_email('/accounts/password/reset/key/'))
        set_password_url = response['Location']  # the key moves into the session
        new_password = 'An0ther-strong-pass!'
        response = client.post(set_password_url, {'password1': new_password, 'password2': new_password})
        self.assertEqual(response.status_code, 302)

        self.basic.refresh_from_db()
        self.assertTrue(self.basic.check_password(new_password))

    def test_unknown_email_does_not_reveal_anything(self):
        response = self.client_for(None).post(reverse('account_reset_password'), {'email': 'nobody@example.com'})
        self.assertRedirects(response, reverse('account_reset_password_done'), fetch_redirect_response=False)

    def test_signed_in_users_can_change_their_password(self):
        client = self.client_for(self.basic)
        response = client.get(reverse('profile'))
        self.assertContains(response, reverse('account_change_password'))
        self.assertContains(response, reverse('account_email'))
        new_password = 'Third-strong-pass!9'
        client.post(reverse('account_change_password'), {
            'oldpassword': PASSWORD, 'password1': new_password, 'password2': new_password,
        })
        self.basic.refresh_from_db()
        self.assertTrue(self.basic.check_password(new_password))


GOOGLE = {
    'GOOGLE_CLIENT_ID': 'test-client-id',
    'SOCIALACCOUNT_PROVIDERS': {'google': {
        'SCOPE': ['profile', 'email'],
        'APPS': [{'client_id': 'test-client-id', 'secret': 'test-secret'}],
    }},
}
GOOGLE_PROFILE = {
    'sub': '1234567890', 'email': 'rafi.ahmed@example.com', 'email_verified': True,
    'given_name': 'Rafi', 'family_name': 'Ahmed',
}


@override_settings(**GOOGLE)
class GoogleSignInTests(SecurityTestCase):
    """The real allauth flow; only the two calls to Google's servers are faked."""

    def setUp(self):
        cache.clear()

    def google_callback(self, client, profile=GOOGLE_PROFILE):
        response = client.post(reverse('google_login'))
        authorize = urlparse(response['Location'])
        self.assertEqual(authorize.netloc, 'accounts.google.com')
        query = parse_qs(authorize.query)
        self.assertEqual(query['client_id'], ['test-client-id'])
        with mock.patch('allauth.socialaccount.providers.oauth2.client.OAuth2Client.get_access_token',
                        return_value={'access_token': 'token', 'expires_in': 3600}), \
             mock.patch('allauth.socialaccount.providers.google.views.GoogleOAuth2Adapter._fetch_user_info',
                        return_value=dict(profile)):
            return client.get(reverse('google_callback'), {'code': 'abc', 'state': query['state'][0]})

    def test_buttons_appear_when_configured(self):
        for url in (reverse('account_login'), reverse('account_signup')):
            response = self.client_for(None).get(url)
            self.assertContains(response, f'action="{reverse("google_login")}"')
            self.assertContains(response, 'with Google')

    def test_new_google_user_completes_profile_then_is_signed_in(self):
        client = self.client_for(None)
        response = self.google_callback(client)
        self.assertRedirects(response, reverse('socialaccount_signup'), fetch_redirect_response=False)

        page = client.get(reverse('socialaccount_signup'))
        self.assertContains(page, 'Complete your profile')
        self.assertEqual(page.context['form'].initial.get('first_name'), 'Rafi')

        response = client.post(reverse('socialaccount_signup'), {
            'username': 'rafi', 'email': 'rafi.ahmed@example.com', 'first_name': 'Rafi', 'last_name': 'Ahmed',
            'university': 'NSU', 'gender': 'male', 'user_type': 'moderator',
        })
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        user = CustomUser.objects.get(username='rafi')
        self.assertEqual((user.university, user.user_type), ('NSU', 'basic'))
        self.assertFalse(user.has_usable_password())
        self.assertTrue(EmailAddress.objects.get(user=user).verified)  # Google already verified it
        self.assertTrue(SocialAccount.objects.filter(user=user, provider='google', uid='1234567890').exists())
        self.assertEqual(int(client.session['_auth_user_id']), user.id)
        self.assertEqual(len(mail.outbox), 0)  # no verification email needed

    def test_returning_google_user_is_signed_in_directly(self):
        user = verified(make_user('rafi'), 'rafi.ahmed@example.com')
        SocialAccount.objects.create(user=user, provider='google', uid='1234567890')
        client = self.client_for(None)
        response = self.google_callback(client)
        self.assertRedirects(response, reverse('home'), fetch_redirect_response=False)
        self.assertEqual(int(client.session['_auth_user_id']), user.id)

    def test_google_cannot_take_over_an_existing_account_with_the_same_email(self):
        existing = verified(make_user('owner'), 'rafi.ahmed@example.com')
        client = self.client_for(None)
        self.google_callback(client)
        self.assertNotIn('_auth_user_id', client.session)
        response = client.post(reverse('socialaccount_signup'), {
            'username': 'intruder', 'email': 'rafi.ahmed@example.com', 'first_name': 'R', 'last_name': 'A',
            'university': 'NSU', 'gender': 'male',
        })
        # Nothing is created or linked; the address owner is emailed to sign in to their account.
        self.assertRedirects(response, reverse('account_email_verification_sent'), fetch_redirect_response=False)
        self.assertFalse(SocialAccount.objects.exists())
        self.assertFalse(CustomUser.objects.filter(username='intruder').exists())
        self.assertNotIn('_auth_user_id', client.session)
        self.assertEqual((mail.outbox[-1].to, mail.outbox[-1].subject),
                         ([existing.email], '[NoteSwap] Account Already Exists'))
