from django.test import TestCase, override_settings

from apps.accounts.oauth_urls import (
    canonical_frontend_url,
    github_authorize_url,
    oauth_callback_url,
)


class OAuthCallbackUrlTests(TestCase):
    @override_settings(FRONTEND_URL="https://www.fixitlab.in", GITHUB_CLIENT_ID="gh-test-id")
    def test_canonical_frontend_url_strips_www(self):
        self.assertEqual(canonical_frontend_url(), "https://fixitlab.in")

    @override_settings(FRONTEND_URL="https://fixitlab.in/", GITHUB_CLIENT_ID="gh-test-id")
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

    @override_settings(FRONTEND_URL="https://fixitlab.in", GITHUB_CLIENT_ID="gh-test-id")
    def test_github_authorize_url_uses_canonical_callback(self):
        url = github_authorize_url(intent="login")
        self.assertIn("client_id=gh-test-id", url)
        self.assertIn(
            "redirect_uri=https%3A%2F%2Ffixitlab.in%2Fauth%2Fcallback%2Fgithub",
            url,
        )
        self.assertIn("state=login", url)

    @override_settings(FRONTEND_URL="  https://fixitlab.in/  ", GITHUB_CLIENT_ID="gh-test-id")
    def test_canonical_frontend_url_strips_whitespace(self):
        self.assertEqual(canonical_frontend_url(), "https://fixitlab.in")
