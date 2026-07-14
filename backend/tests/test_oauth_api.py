"""OAuth API endpoints — config, start redirect, callback URL consistency."""

from unittest import mock
from urllib.parse import parse_qs, urlparse

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.accounts.oauth_urls import oauth_callback_url
from apps.accounts.oauth_state import issue_oauth_state

User = get_user_model()


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
        # login_url now points at the server-side start endpoint, which builds
        # the GitHub authorize URL (redirect_uri + CSRF nonce state) server-side
        # instead of exposing it to the client.
        self.assertIn("/api/auth/social/start/github/", gh["login_url"])
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
        self.assertTrue(params["state"][0].startswith("login:"))
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
        self.assertTrue(params["state"][0].startswith("register:"))


@override_settings(
    ROOT_URLCONF="config.urls", SECURE_SSL_REDIRECT=False,
    FRONTEND_URL="https://fixitlab.in",
    GOOGLE_CLIENT_ID="google-test-id", GOOGLE_CLIENT_SECRET="google-test-secret",
)
class GoogleOAuthEmailVerificationTests(TestCase):
    """SECURITY_AUDIT A-03: Google OAuth must not link to an existing account on
    an UNVERIFIED provider email (account-takeover prevention)."""

    def setUp(self):
        self.client = APIClient()
        # Pre-existing local account owning the victim's email.
        self.victim = User.objects.create_user(
            username="victim", email="victim@corp.com", password="Victim123!x"
        )

    def _mock_google(self, *, email, email_verified):
        """Patch the token-exchange POST + userinfo GET that the view makes."""
        token_resp = mock.Mock()
        token_resp.json.return_value = {"access_token": "ya29.fake", "id_token": "jwt.fake"}
        info_resp = mock.Mock()
        info_resp.json.return_value = {
            "sub": "google-uid-999",
            "email": email,
            "name": "Mallory",
            "email_verified": email_verified,
        }
        post_patch = mock.patch("requests.post", return_value=token_resp)
        get_patch = mock.patch("requests.get", return_value=info_resp)
        return post_patch, get_patch

    def test_unverified_email_does_not_link_to_existing_account(self):
        post_patch, get_patch = self._mock_google(email="victim@corp.com", email_verified=False)
        with post_patch, get_patch:
            resp = self.client.post(
                "/api/auth/social/google/",
                {"code": "auth-code", "intent": "login", "state": issue_oauth_state("login")},
                format="json",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        # Must be rejected — no token issued, no social link to the victim.
        self.assertEqual(resp.status_code, 403, getattr(resp, "data", resp.content))
        self.assertEqual(resp.data.get("error_code"), "email_not_verified")
        from apps.accounts.models import SocialAccount
        self.assertFalse(
            SocialAccount.objects.filter(provider="google", user=self.victim).exists()
        )

    def test_verified_email_links_to_existing_account(self):
        post_patch, get_patch = self._mock_google(email="victim@corp.com", email_verified=True)
        with post_patch, get_patch:
            resp = self.client.post(
                "/api/auth/social/google/",
                {"code": "auth-code", "intent": "login", "state": issue_oauth_state("login")},
                format="json",
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(resp.status_code, 200, getattr(resp, "data", resp.content))
        self.assertEqual(resp.data["user"]["email"], "victim@corp.com")
        from apps.accounts.models import SocialAccount
        self.assertTrue(
            SocialAccount.objects.filter(provider="google", user=self.victim).exists()
        )
