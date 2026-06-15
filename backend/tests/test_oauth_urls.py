from django.test import TestCase, override_settings

from apps.accounts.oauth_urls import canonical_frontend_url, oauth_callback_url


class OAuthCallbackUrlTests(TestCase):
    @override_settings(FRONTEND_URL="https://fixitlab.in/")
    def test_canonical_frontend_url_strips_trailing_slash(self):
        self.assertEqual(canonical_frontend_url(), "https://fixitlab.in")

    @override_settings(FRONTEND_URL="https://fixitlab.in")
    def test_oauth_callback_url_github(self):
        self.assertEqual(
            oauth_callback_url("github"),
            "https://fixitlab.in/auth/callback/github",
        )

    @override_settings(FRONTEND_URL="https://fixitlab.in")
    def test_oauth_callback_url_google(self):
        self.assertEqual(
            oauth_callback_url("google"),
            "https://fixitlab.in/auth/callback/google",
        )
