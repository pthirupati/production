"""OAuth API endpoints — config, start redirect, callback URL consistency."""

from urllib.parse import parse_qs, urlparse

from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.oauth_urls import oauth_callback_url


class SocialAuthConfigAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    @override_settings(FRONTEND_URL="https://fixitlab.in", GITHUB_CLIENT_ID="gh-test-id", GOOGLE_CLIENT_ID="")
    def test_social_config_returns_canonical_github_callback(self):
        resp = self.client.get("/api/auth/social/config/")
        self.assertEqual(resp.status_code, 200)
        gh = resp.data["github"]
        self.assertTrue(gh["enabled"])
        self.assertEqual(gh["callback_url"], "https://fixitlab.in/auth/callback/github")
        self.assertIn("redirect_uri=https%3A%2F%2Ffixitlab.in%2Fauth%2Fcallback%2Fgithub", gh["login_url"])
        self.assertIn("oauth_setup_note", resp.data)
        self.assertIn("https://fixitlab.in/auth/callback/github", resp.data["oauth_setup_note"])

    @override_settings(
        FRONTEND_URL="https://www.fixitlab.in",
        GITHUB_OAUTH_CALLBACK_URL="https://fixitlab.in/auth/callback/github",
        GITHUB_CLIENT_ID="gh-test-id",
    )
    def test_social_config_honors_explicit_github_callback_override(self):
        resp = self.client.get("/api/auth/social/config/")
        self.assertEqual(resp.data["github"]["callback_url"], "https://fixitlab.in/auth/callback/github")
        self.assertEqual(resp.data["frontend_url"], "https://fixitlab.in")


class SocialOAuthStartAPITest(TestCase):
    def setUp(self):
        self.client = APIClient()

    @override_settings(FRONTEND_URL="https://fixitlab.in", GITHUB_CLIENT_ID="gh-test-id")
    def test_github_start_redirects_with_matching_redirect_uri(self):
        resp = self.client.get("/api/auth/social/start/github/?intent=login")
        self.assertEqual(resp.status_code, 302)
        location = resp["Location"]
        self.assertTrue(location.startswith("https://github.com/login/oauth/authorize?"))
        parsed = urlparse(location)
        params = parse_qs(parsed.query)
        self.assertEqual(params["client_id"], ["gh-test-id"])
        self.assertEqual(params["state"], ["login"])
        self.assertEqual(
            params["redirect_uri"],
            [oauth_callback_url("github")],
        )

    @override_settings(FRONTEND_URL="https://fixitlab.in", GITHUB_CLIENT_ID="")
    def test_github_start_returns_501_when_unconfigured(self):
        resp = self.client.get("/api/auth/social/start/github/")
        self.assertEqual(resp.status_code, 501)

    @override_settings(FRONTEND_URL="https://fixitlab.in", GOOGLE_CLIENT_ID="google-test-id")
    def test_google_start_redirects_with_matching_redirect_uri(self):
        resp = self.client.get("/api/auth/social/start/google/?intent=register")
        self.assertEqual(resp.status_code, 302)
        parsed = urlparse(resp["Location"])
        params = parse_qs(parsed.query)
        self.assertEqual(params["redirect_uri"], [oauth_callback_url("google")])
        self.assertEqual(params["state"], ["register"])
