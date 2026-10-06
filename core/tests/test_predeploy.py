"""Pre-deploy checks: robots.txt and the NOTESWAP_SITE_URL guard."""
import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class RobotsTxtTests(SimpleTestCase):
    def test_served_as_plain_text(self):
        response = self.client.get('/robots.txt')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/plain')
        self.assertTrue(response.content.decode().startswith('User-agent: *\n'))

    def test_private_areas_blocked_public_pages_allowed(self):
        lines = self.client.get('/robots.txt').content.decode().splitlines()
        for private in ('/admin/', '/accounts/', '/manage_dash/', '/files/', '/notesolve/'):
            self.assertIn(f'Disallow: {private}', lines)
        for public in ('/', '/subjects/', '/notes/', '/providers/', '/premium/', '/help/'):
            self.assertNotIn(f'Disallow: {public}', lines)


class SiteUrlSettingTests(SimpleTestCase):
    def load_settings(self, **env):
        """Import the settings in a fresh Python with the given environment."""
        environment = {**os.environ, 'DJANGO_SECRET_KEY': 's' * 60, 'DJANGO_ALLOWED_HOSTS': 'example.com', **env}
        return subprocess.run(
            [sys.executable, '-c', 'import config.settings as s; print(s.SITE_URL)'],
            cwd=settings.BASE_DIR, env=environment, capture_output=True, text=True,
        )

    def test_required_when_debug_off(self):
        result = self.load_settings(DJANGO_DEBUG='False', NOTESWAP_SITE_URL='')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('NOTESWAP_SITE_URL must be set', result.stderr)

    def test_set_when_debug_off(self):
        result = self.load_settings(DJANGO_DEBUG='False', NOTESWAP_SITE_URL='https://noteswap.com/')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'https://noteswap.com')

    def test_local_default_when_debug_on(self):
        result = self.load_settings(DJANGO_DEBUG='True', NOTESWAP_SITE_URL='')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'http://127.0.0.1:8000')
