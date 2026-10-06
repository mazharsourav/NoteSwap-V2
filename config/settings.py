"""
NoteSwap settings.

All environment-specific values come from environment variables, optionally
loaded from a `.env` file in the project root (see `.env.example`).
DEBUG is off unless explicitly enabled.
"""
import sys
from email.utils import parseaddr
from pathlib import Path

import environ
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

# === SECURITY ===
SECRET_KEY = env('DJANGO_SECRET_KEY')
if len(SECRET_KEY) < 50 or SECRET_KEY == 'change-me':
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must be set to a random value of at least 50 characters.')
DEBUG = env.bool('DJANGO_DEBUG', default=False)
ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=[])
CSRF_TRUSTED_ORIGINS = env.list('DJANGO_CSRF_TRUSTED_ORIGINS', default=[])

# === INSTALLED APPS ===
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'core',
]

# === MIDDLEWARE ===
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

# === URL CONFIG ===
ROOT_URLCONF = 'config.urls'

# === TEMPLATES ===
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.premium_status',
                'core.context_processors.notifications',
                'core.context_processors.sign_in_options',
                'core.context_processors.site_credits',
                'core.context_processors.navigation',
            ],
        },
    },
]

# === WSGI ===
WSGI_APPLICATION = 'config.wsgi.application'

# === DATABASE ===
# Defaults to the local SQLite dev database; set DATABASE_URL for anything else.
DATABASES = {
    'default': env.db('DATABASE_URL', default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}"),
}

# === AUTH ===
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

AUTH_USER_MODEL = 'core.CustomUser'
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',  # Django admin login
    'allauth.account.auth_backends.AuthenticationBackend',  # site login: username or email
]
LOGIN_URL = 'account_login'
LOGIN_REDIRECT_URL = 'home'

# === ACCOUNTS (django-allauth) ===
# Sign up / sign in / email verification / password reset live under /accounts/.
ACCOUNT_LOGIN_METHODS = {'username', 'email'}
ACCOUNT_SIGNUP_FIELDS = ['username*', 'email*', 'password1*', 'password2*']
ACCOUNT_SIGNUP_FORM_CLASS = 'core.forms.SignupProfileForm'  # name, university, gender
ACCOUNT_UNIQUE_EMAIL = True
# 'mandatory': new accounts must click the link in the verification email before signing in.
ACCOUNT_EMAIL_VERIFICATION = env('DJANGO_EMAIL_VERIFICATION', default='mandatory')
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[NoteSwap] '
ACCOUNT_LOGOUT_REDIRECT_URL = 'home'
# Same lockout as before: 5 failed sign-ins per account in 15 minutes (plus 10/min per IP).
ACCOUNT_RATE_LIMITS = {'login_failed': '10/m/ip,5/15m/key'}
ACCOUNT_ADAPTER = 'core.adapters.AccountAdapter'  # logs lockouts (core.security)

# Google sign-in. Leave the two variables empty to hide the Google button.
GOOGLE_CLIENT_ID = env('GOOGLE_CLIENT_ID', default='')
GOOGLE_CLIENT_SECRET = env('GOOGLE_CLIENT_SECRET', default='')
SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'prompt': 'select_account'},
        'APPS': [{'client_id': GOOGLE_CLIENT_ID, 'secret': GOOGLE_CLIENT_SECRET}] if GOOGLE_CLIENT_ID else [],
    },
}
# New Google users first see a short "complete your profile" form (university, gender, username).
SOCIALACCOUNT_AUTO_SIGNUP = False
SOCIALACCOUNT_LOGIN_ON_GET = False  # the Google button POSTs, so no extra confirmation page

# Footer credit "Built by NAME" linking to the developer's portfolio. Set the name to empty to hide it.
DEVELOPER_NAME = env('NOTESWAP_DEVELOPER_NAME', default='Mazharul Islam Sourav')
DEVELOPER_URL = env('NOTESWAP_DEVELOPER_URL', default='https://mazharsourav.me')

# === EMAIL ===
# Default prints emails in the runserver terminal. For real sending set EMAIL_URL, e.g.
# smtp+tls://LOGIN:SMTP_KEY@smtp-relay.brevo.com:587
EMAIL_CONFIG = env.email_url('EMAIL_URL', default='consolemail://')
vars().update(EMAIL_CONFIG)
DEFAULT_FROM_EMAIL = env('DJANGO_DEFAULT_FROM_EMAIL', default='NoteSwap <no-reply@noteswap.local>')
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# Base address for links in emails sent outside a request (Premium reminders). Set it to the
# real https:// address when the site is hosted; required when DEBUG is off, so emails
# never link to 127.0.0.1 by mistake.
SITE_URL = (env('NOTESWAP_SITE_URL', default='') or ('http://127.0.0.1:8000' if DEBUG else '')).rstrip('/')
if not SITE_URL.startswith(('http://', 'https://')):
    raise ImproperlyConfigured(
        'NOTESWAP_SITE_URL must be set to the site address (e.g. https://noteswap.com) when DJANGO_DEBUG is off.')

# === LOGGING ===
# Everything goes to the console (hosts save it to their error log). Optional files, each kept
# under 5 MB x 5 old copies: DJANGO_LOG_FILE gets everything, DJANGO_AUDIT_LOG_FILE only the
# "who did what" and security lines. Helpers and logger names: core/logs.py.
# With DEBUG off, errors are also emailed to DJANGO_ADMINS ("Name <a@b.com>, c@d.com").
def admins_from(entries):
    """["Name <a@b.com>", "c@d.com"] -> [("Name", "a@b.com"), ("c@d.com", "c@d.com")]"""
    pairs = (parseaddr(entry) for entry in entries)
    return [(name or address, address) for name, address in pairs if '@' in address]


ADMINS = admins_from(env.list('DJANGO_ADMINS', default=[]))
EMAIL_SUBJECT_PREFIX = '[NoteSwap error] '  # only used for the error emails to ADMINS
DEFAULT_EXCEPTION_REPORTER_FILTER = 'core.logs.SafeReporterFilter'  # hides the login cookie too
LOG_LEVEL = env('DJANGO_LOG_LEVEL', default='INFO').upper()
if LOG_LEVEL not in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
    raise ImproperlyConfigured('DJANGO_LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL.')


def logging_config(level, log_file='', audit_file='', quiet_console=False):
    def file_handler(path):
        path = BASE_DIR / path  # relative paths are inside the project folder
        path.parent.mkdir(parents=True, exist_ok=True)
        return {
            'class': 'logging.handlers.RotatingFileHandler', 'filename': str(path),
            'maxBytes': 5 * 1024 * 1024, 'backupCount': 5, 'encoding': 'utf-8', 'delay': True,
            'formatter': 'standard',
        }

    handlers = {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'standard',
                    **({'level': 'CRITICAL'} if quiet_console else {})},
        'runserver': {'class': 'logging.StreamHandler', 'formatter': 'runserver'},
        'mail_admins': {
            'level': 'ERROR', 'filters': ['require_debug_false'], 'class': 'django.utils.log.AdminEmailHandler',
        },
    }
    if log_file:
        handlers['file'] = file_handler(log_file)
    if audit_file:
        handlers['audit_file'] = file_handler(audit_file)
    audit_handlers = ['audit_file'] if audit_file else []

    return {
        'version': 1,
        'disable_existing_loggers': False,
        'filters': {'require_debug_false': {'()': 'django.utils.log.RequireDebugFalse'}},
        'formatters': {
            'standard': {'format': '{asctime} {levelname} {name} {message}', 'style': '{',
                         'datefmt': '%Y-%m-%d %H:%M:%S'},
            'runserver': {'()': 'django.utils.log.ServerFormatter', 'format': '[{server_time}] {message}', 'style': '{'},
        },
        'handlers': handlers,
        # Loggers below pass their lines up to these handlers.
        'root': {'handlers': ['console', 'mail_admins', *(['file'] if log_file else [])], 'level': 'WARNING'},
        'loggers': {
            'django': {'handlers': [], 'level': 'INFO'},
            # runserver's own "GET /page 200" lines, unchanged (development only).
            'django.server': {'handlers': ['runserver'], 'level': 'INFO', 'propagate': False},
            # Crashes (500) with their traceback. 403/404 are left out: bots cause thousands.
            'django.request': {'level': 'ERROR'},
            # Bad Host header, failed CSRF check, suspicious file path.
            'django.security': {'level': 'WARNING'},
            'django.db.backends': {'level': 'WARNING'},  # SQL queries: far too noisy
            'core': {'level': level},
            'core.audit': {'handlers': audit_handlers},
            'core.security': {'handlers': audit_handlers},
        },
    }


# `manage.py test` keeps the console quiet: tests that check logs capture them (assertLogs).
TESTING = sys.argv[1:2] == ['test']
LOGGING = logging_config(LOG_LEVEL, env('DJANGO_LOG_FILE', default=''), env('DJANGO_AUDIT_LOG_FILE', default=''),
                         quiet_console=TESTING)

# === LOCALIZATION ===
# English only for now. Template text in the site shell is marked with {% translate %}, so a
# second language means: add it to LANGUAGES, add LocaleMiddleware, run makemessages, translate.
LANGUAGE_CODE = 'en'
LANGUAGES = [('en', 'English')]
LOCALE_PATHS = [BASE_DIR / 'locale']
TIME_ZONE = env('DJANGO_TIME_ZONE', default='Asia/Dhaka')
USE_I18N = True
USE_TZ = True

# === STATIC FILES ===
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
if DEBUG:
    # Cache-busting ?v= on CSS/JS links so edits show up without a hard refresh (see core/storage.py).
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'core.storage.DevStaticFilesStorage'},
    }

# === MEDIA FILES ===
MEDIA_URL = '/media/'
MEDIA_ROOT = Path(env('DJANGO_MEDIA_ROOT', default=str(BASE_DIR / 'media')))

# === DEFAULT FIELD ===
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# === PRODUCTION HARDENING ===
# Applied whenever DEBUG is off. Each can be overridden from the environment,
# e.g. to run a production-like build locally without HTTPS.
if not DEBUG:
    SECURE_SSL_REDIRECT = env.bool('DJANGO_SECURE_SSL_REDIRECT', default=True)
    SESSION_COOKIE_SECURE = env.bool('DJANGO_SESSION_COOKIE_SECURE', default=True)
    CSRF_COOKIE_SECURE = env.bool('DJANGO_CSRF_COOKIE_SECURE', default=True)
    # Keep HSTS at 0 until HTTPS is confirmed working on the real domain, then raise it.
    SECURE_HSTS_SECONDS = env.int('DJANGO_SECURE_HSTS_SECONDS', default=0)
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool('DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS', default=False)
    SECURE_HSTS_PRELOAD = env.bool('DJANGO_SECURE_HSTS_PRELOAD', default=False)
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
