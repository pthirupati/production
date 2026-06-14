"""Email dispatch, OTP, and notification delivery tests."""
from datetime import timedelta
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import EmailVerificationOTP
from apps.accounts.views import GitHubCallbackView
from apps.notifications.models import EmailLog

User = get_user_model()


class EmailDispatchTest(APITestCase):
    @patch("apps.notifications.tasks.send_notification_email")
    def test_dispatch_queues_celery_task(self, mock_task):
        mock_task.delay = MagicMock(return_value=MagicMock(id="task-1"))
        from apps.notifications.email_dispatch import dispatch_notification_email

        ok = dispatch_notification_email(
            subject="Test",
            to_email="user@test.com",
            template="emails/otp_verification.html",
            context={"otp_code": "123456"},
        )
        self.assertTrue(ok)
        mock_task.delay.assert_called_once()

    @patch("apps.notifications.email._deliver", return_value="smtp")
    def test_send_email_logs_success(self, mock_deliver):
        from apps.notifications.email import send_email

        ok = send_email(
            subject="Hello",
            to_email="user@test.com",
            template="emails/otp_verification.html",
            context={"otp_code": "123456", "expires_minutes": 2},
        )
        self.assertTrue(ok)
        self.assertTrue(EmailLog.objects.filter(to_email="user@test.com", status="sent").exists())

    @patch("apps.notifications.email._deliver")
    def test_send_email_logs_failure(self, mock_deliver):
        mock_deliver.side_effect = RuntimeError("SMTP blocked")
        from apps.notifications.email import send_email

        ok = send_email(
            subject="Hello",
            to_email="fail@test.com",
            template="emails/otp_verification.html",
            context={"otp_code": "123456", "expires_minutes": 2},
        )
        self.assertFalse(ok)
        log = EmailLog.objects.filter(to_email="fail@test.com").first()
        self.assertIsNotNone(log)
        self.assertEqual(log.status, "failed")


class SendOTPAPITest(APITestCase):
    @patch("apps.notifications.gmail_api.is_gmail_api_configured", return_value=True)
    @patch("apps.accounts.views.dispatch_notification_email", return_value=True)
    def test_send_otp_success(self, mock_dispatch, _mock_gmail):
        resp = self.client.post("/api/auth/send-otp/", {"email": "new@test.com"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("session_token", resp.data)
        self.assertIn("expires_at", resp.data)
        self.assertEqual(resp.data["expires_in_seconds"], 120)
        mock_dispatch.assert_called_once()
        self.assertTrue(
            EmailVerificationOTP.objects.filter(email="new@test.com").exists()
        )

    def test_send_otp_duplicate_email(self):
        User.objects.create_user(
            username="exists@test.com", email="exists@test.com", password="Test123!@"
        )
        resp = self.client.post("/api/auth/send-otp/", {"email": "exists@test.com"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["error_code"], "email_exists")

    def test_send_otp_invalid_email(self):
        resp = self.client.post("/api/auth/send-otp/", {"email": "not-an-email"})
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(
        GMAIL_OAUTH_CLIENT_ID="",
        GMAIL_OAUTH_CLIENT_SECRET="",
        GMAIL_OAUTH_REFRESH_TOKEN="",
        SENDGRID_API_KEY="",
        EMAIL_HOST_USER="",
        EMAIL_HOST="mailhog",
    )
    def test_send_otp_no_email_config(self):
        resp = self.client.post("/api/auth/send-otp/", {"email": "nobody@test.com"})
        self.assertEqual(resp.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(resp.data["error_code"], "email_unavailable")


class VerifyOTPAPITest(APITestCase):
    def _create_otp(self, code="654321", minutes=2):
        return EmailVerificationOTP.objects.create(
            email="verify@test.com",
            code=code,
            session_token="sess-token-xyz",
            expires_at=timezone.now() + timedelta(minutes=minutes),
        )

    def test_verify_otp_success(self):
        self._create_otp()
        resp = self.client.post("/api/auth/verify-otp/", {
            "session_token": "sess-token-xyz",
            "code": "654321",
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        otp = EmailVerificationOTP.objects.get(session_token="sess-token-xyz")
        self.assertTrue(otp.verified)

    def test_verify_otp_invalid_code(self):
        self._create_otp()
        resp = self.client.post("/api/auth/verify-otp/", {
            "session_token": "sess-token-xyz",
            "code": "000000",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["error_code"], "otp_invalid")

    def test_verify_otp_expired(self):
        self._create_otp(minutes=-1)
        resp = self.client.post("/api/auth/verify-otp/", {
            "session_token": "sess-token-xyz",
            "code": "654321",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["error_code"], "otp_expired")


class RegisterWithOTPTest(APITestCase):
    def test_register_requires_verified_otp(self):
        resp = self.client.post("/api/auth/register/", {
            "email": "reg@test.com",
            "password": "GoodP@ss99!",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_email_after_verify(self):
        User.objects.create_user(
            username="taken@test.com", email="taken@test.com", password="Test123!@"
        )
        EmailVerificationOTP.objects.create(
            email="taken@test.com",
            code="111111",
            verified=True,
            session_token="verified-token",
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        resp = self.client.post("/api/auth/register/", {
            "email": "taken@test.com",
            "password": "GoodP@ss99!",
            "session_token": "verified-token",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data["error_code"], "email_exists")

    @patch("apps.accounts.views.send_notification_email")
    def test_register_success_with_verified_otp(self, mock_welcome):
        mock_welcome.delay = MagicMock()
        EmailVerificationOTP.objects.create(
            email="fresh@test.com",
            code="222222",
            verified=True,
            session_token="fresh-token",
            expires_at=timezone.now() + timedelta(minutes=5),
        )
        resp = self.client.post("/api/auth/register/", {
            "email": "fresh@test.com",
            "password": "GoodP@ss99!",
            "session_token": "fresh-token",
            "phone_number": "+12345678901",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="fresh@test.com").exists())


class ForgotPasswordEmailTest(APITestCase):
    @patch("apps.accounts.views.dispatch_notification_email", return_value=True)
    def test_forgot_password_queues_email(self, mock_dispatch):
        User.objects.create_user(
            username="reset@test.com", email="reset@test.com", password="Test123!@"
        )
        resp = self.client.post("/api/auth/forgot-password/", {"email": "reset@test.com"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        mock_dispatch.assert_called_once()


class SocialLoginAPITest(APITestCase):
    def test_resolve_social_login_no_account(self):
        user, err = GitHubCallbackView._resolve_social_login(
            "github", "999", "newoauth@test.com", "New User"
        )
        self.assertIsNone(user)
        self.assertIsNotNone(err)
        self.assertEqual(err.status_code, 403)
        self.assertEqual(err.data["error_code"], "registration_required")

    def test_resolve_social_login_links_existing_email(self):
        user = User.objects.create_user(username="link@test.com", email="link@test.com", password="Test123!@")
        resolved, err = GitHubCallbackView._resolve_social_login(
            "google", "google-uid-1", "link@test.com", "Link User"
        )
        self.assertIsNone(err)
        self.assertEqual(resolved.id, user.id)
        self.assertTrue(user.social_accounts.filter(provider="google").exists())

    def test_resolve_social_login_existing_social_account(self):
        user = User.objects.create_user(username="soc@test.com", email="soc@test.com", password="Test123!@")
        from apps.accounts.models import SocialAccount
        SocialAccount.objects.create(user=user, provider="github", provider_uid="gh-123")
        resolved, err = GitHubCallbackView._resolve_social_login(
            "github", "gh-123", "soc@test.com", "Soc User"
        )
        self.assertIsNone(err)
        self.assertEqual(resolved.id, user.id)
