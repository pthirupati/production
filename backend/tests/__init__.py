"""
FixitLab — Comprehensive Backend Test Suite
=============================================
Tests for: Auth, Profile, Models, Permissions, API endpoints,
Validators, Serializers, Middleware, and Edge Cases.

Run:
  cd backend
  python manage.py test tests --settings=config.test_settings -v2
"""

import json
from datetime import timedelta

from django.test import TestCase, override_settings
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient, APITestCase
from rest_framework import status

from apps.accounts.models import Profile, PasswordResetToken, EmailVerificationOTP
from apps.accounts.serializers import RegisterSerializer, LoginSerializer
from apps.question_bank.models import Technology, Tag, Scenario
from apps.labs.models import LabSession
from apps.progress.models import UserScenarioProgress, UserAchievement
from apps.hints.models import Hint
from apps.audit.models import AuditLog
from apps.notifications.models import Notification


# ═════════════════════════════════════════════
# Helper mixins
# ═════════════════════════════════════════════
class AuthMixin:
    """Create test users and obtain JWT tokens."""

    def create_user(self, email="user@test.com", password="TestP@ssw0rd!", is_staff=False):
        user = User.objects.create_user(
            username=email, email=email, password=password, is_staff=is_staff
        )
        return user

    def get_tokens(self, email="user@test.com", password="TestP@ssw0rd!"):
        resp = self.client.post("/api/auth/login/", {"email": email, "password": password})
        return resp.data.get("access"), resp.data.get("refresh")

    def auth_client(self, user=None, email="user@test.com", password="TestP@ssw0rd!"):
        if user is None:
            try:
                user = User.objects.get(email=email)
            except User.DoesNotExist:
                user = self.create_user(email, password)
        access, _ = self.get_tokens(email, password)
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        return client, user


class ScenarioMixin:
    """Create test scenarios with supporting objects."""

    def create_tech(self, name="Linux"):
        return Technology.objects.create(name=name, slug=name.lower())

    def create_scenario(self, tech=None, slug="broken-nginx", **kwargs):
        if tech is None:
            tech = self.create_tech()
        defaults = {
            "technology": tech,
            "slug": slug,
            "title": "Broken Nginx",
            "category": "Web Server",
            "difficulty": "easy",
            "scenario_type": "fix",
            "description": "Fix the broken Nginx config.",
            "time_limit": 900,
            "max_score": 100,
            "is_active": True,
        }
        defaults.update(kwargs)
        return Scenario.objects.create(**defaults)


# ═════════════════════════════════════════════
# 1. Model Tests
# ═════════════════════════════════════════════
class ProfileModelTest(TestCase, AuthMixin):
    def test_profile_auto_created_on_user_create(self):
        user = self.create_user()
        self.assertTrue(Profile.objects.filter(user=user).exists())

    def test_profile_str(self):
        user = self.create_user()
        self.assertEqual(str(user.profile), user.username)


class PasswordResetTokenTest(TestCase, AuthMixin):
    def test_generate_token(self):
        user = self.create_user()
        instance, raw = PasswordResetToken.generate_token(user)
        self.assertTrue(len(raw) > 20)
        self.assertTrue(instance.is_valid)
        self.assertFalse(instance.is_expired)

    def test_expired_token(self):
        user = self.create_user()
        instance, raw = PasswordResetToken.generate_token(user)
        instance.expires_at = timezone.now() - timedelta(hours=1)
        instance.save()
        self.assertTrue(instance.is_expired)
        self.assertFalse(instance.is_valid)

    def test_used_token(self):
        user = self.create_user()
        instance, raw = PasswordResetToken.generate_token(user)
        instance.used = True
        instance.save()
        self.assertFalse(instance.is_valid)


class TechnologyModelTest(TestCase):
    def test_auto_slug(self):
        tech = Technology.objects.create(name="Docker Compose")
        self.assertEqual(tech.slug, "docker-compose")

    def test_str(self):
        tech = Technology.objects.create(name="Linux", slug="linux")
        self.assertEqual(str(tech), "Linux")


class TagModelTest(TestCase):
    def test_auto_slug(self):
        tag = Tag.objects.create(name="Nginx Config")
        self.assertEqual(tag.slug, "nginx-config")


class ScenarioModelTest(TestCase, ScenarioMixin):
    def test_create_scenario(self):
        s = self.create_scenario()
        self.assertEqual(str(s.slug), "broken-nginx")
        self.assertTrue(s.is_active)

    def test_scenario_with_tags(self):
        s = self.create_scenario()
        tag = Tag.objects.create(name="nginx")
        s.tags.add(tag)
        self.assertEqual(s.tags.count(), 1)


class LabSessionModelTest(TestCase, AuthMixin, ScenarioMixin):
    def test_create_lab_session(self):
        user = self.create_user()
        scenario = self.create_scenario()
        lab = LabSession.objects.create(user=user, scenario=scenario, status="RUNNING")
        self.assertFalse(lab.is_expired)

    def test_lab_expired(self):
        user = self.create_user()
        scenario = self.create_scenario()
        lab = LabSession.objects.create(
            user=user, scenario=scenario, status="RUNNING", duration_limit=1
        )
        # Manually set started_at to past
        LabSession.objects.filter(pk=lab.pk).update(
            started_at=timezone.now() - timedelta(seconds=60)
        )
        lab.refresh_from_db()
        self.assertTrue(lab.is_expired)


class HintModelTest(TestCase, ScenarioMixin):
    def test_hint_creation(self):
        s = self.create_scenario()
        h = Hint.objects.create(scenario=s, order=1, content="Check the error log", penalty=10)
        self.assertEqual(str(h), f"{s.slug} - Hint 1")


class AuditLogModelTest(TestCase, AuthMixin):
    def test_audit_log_creation(self):
        user = self.create_user()
        log = AuditLog.objects.create(
            user=user, action="login", resource="/api/auth/login/"
        )
        self.assertIn("login", str(log))


class NotificationModelTest(TestCase, AuthMixin):
    def test_notification_creation(self):
        user = self.create_user()
        n = Notification.objects.create(
            user=user, type="welcome", title="Welcome!", message="Hey there"
        )
        self.assertFalse(n.read)
        self.assertIn("welcome", str(n))


class UserScenarioProgressTest(TestCase, AuthMixin, ScenarioMixin):
    def test_progress_creation(self):
        user = self.create_user()
        scenario = self.create_scenario()
        progress = UserScenarioProgress.objects.create(
            user=user, scenario=scenario, attempts=1, completed=True, best_score=85
        )
        self.assertEqual(progress.best_score, 85)

    def test_unique_constraint(self):
        user = self.create_user()
        scenario = self.create_scenario()
        UserScenarioProgress.objects.create(user=user, scenario=scenario)
        with self.assertRaises(Exception):
            UserScenarioProgress.objects.create(user=user, scenario=scenario)


class UserAchievementTest(TestCase, AuthMixin):
    def test_achievement_creation(self):
        user = self.create_user()
        ach = UserAchievement.objects.create(user=user, achievement="first_solve")
        self.assertEqual(ach.achievement, "first_solve")


# ═════════════════════════════════════════════
# 2. Serializer Tests
# ═════════════════════════════════════════════
class RegisterSerializerTest(TestCase):
    def test_valid_data(self):
        data = {"email": "new@test.com", "password": "Test123!@", "accepted_legal": True}
        s = RegisterSerializer(data=data)
        self.assertTrue(s.is_valid(), s.errors)

    def test_short_password(self):
        data = {"email": "new@test.com", "password": "short", "accepted_legal": True}
        s = RegisterSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_duplicate_email(self):
        User.objects.create_user(username="x@test.com", email="x@test.com", password="Test123!")
        data = {"email": "x@test.com", "password": "Test123!@", "accepted_legal": True}
        s = RegisterSerializer(data=data)
        self.assertFalse(s.is_valid())

    def test_create_user(self):
        data = {
            "email": "new@test.com",
            "password": "Test123!@",
            "phone_number": "+1234567890",
            "accepted_legal": True,
        }
        s = RegisterSerializer(data=data)
        s.is_valid(raise_exception=True)
        user = s.save()
        self.assertEqual(user.email, "new@test.com")
        self.assertTrue(Profile.objects.filter(user=user).exists())


# ═════════════════════════════════════════════
# 3. Auth API Tests
# ═════════════════════════════════════════════
class RegisterAPITest(APITestCase, AuthMixin):
    def test_register_success(self):
        # Registration requires a verified OTP session_token
        from django.contrib.auth.hashers import make_password

        otp = EmailVerificationOTP.objects.create(
            email="newuser@test.com",
            code_hash=make_password("123456"),  # stored hashed (Z4-11)
            verified=True,
            session_token="test-session-token-abc",
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        resp = self.client.post("/api/auth/register/", {
            "email": "newuser@test.com",
            "password": "GoodP@ss99!",
            "session_token": "test-session-token-abc",
            "accepted_legal": True,
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        self.assertIn("access", resp.data)
        self.assertIn("refresh", resp.data)
        self.assertEqual(resp.data["user"]["email"], "newuser@test.com")

    def test_register_duplicate(self):
        self.create_user(email="dup@test.com")
        resp = self.client.post("/api/auth/register/", {
            "email": "dup@test.com", "password": "GoodP@ss99!"
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_weak_password(self):
        resp = self.client.post("/api/auth/register/", {
            "email": "weak@test.com", "password": "123"
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class LoginAPITest(APITestCase, AuthMixin):
    def test_login_success(self):
        self.create_user()
        resp = self.client.post("/api/auth/login/", {
            "email": "user@test.com", "password": "TestP@ssw0rd!"
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)

    def test_login_wrong_password(self):
        self.create_user()
        resp = self.client.post("/api/auth/login/", {
            "email": "user@test.com", "password": "wrongpass"
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_login_nonexistent_user(self):
        resp = self.client.post("/api/auth/login/", {
            "email": "nobody@test.com", "password": "pass"
        })
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class LogoutAPITest(APITestCase, AuthMixin):
    def test_logout_blacklists_token(self):
        self.create_user()
        access, refresh = self.get_tokens()
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = self.client.post("/api/auth/logout/", {"refresh": refresh})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

        # Try to use blacklisted refresh token
        resp = self.client.post("/api/auth/refresh/", {"refresh": refresh})
        self.assertIn(resp.status_code, [400, 401])


class TokenRefreshAPITest(APITestCase, AuthMixin):
    def test_refresh_success(self):
        self.create_user()
        _, refresh = self.get_tokens()
        resp = self.client.post("/api/auth/refresh/", {"refresh": refresh})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("access", resp.data)


class ProfileAPITest(APITestCase, AuthMixin):
    def test_get_profile(self):
        client, user = self.auth_client()
        resp = client.get("/api/auth/profile/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["email"], "user@test.com")

    def test_update_profile(self):
        client, user = self.auth_client()
        resp = client.put("/api/auth/profile/", {
            "username": "newname", "phone_number": "+1234567890"
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["username"], "newname")

    def test_profile_unauthenticated(self):
        resp = self.client.get("/api/auth/profile/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class ChangePasswordAPITest(APITestCase, AuthMixin):
    def test_change_password(self):
        client, user = self.auth_client()
        resp = client.post("/api/auth/change-password/", {
            "old_password": "TestP@ssw0rd!",
            "new_password": "NewP@ssw0rd!!"
        })
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_change_password_wrong_old(self):
        client, user = self.auth_client()
        resp = client.post("/api/auth/change-password/", {
            "old_password": "wrongwrong",
            "new_password": "NewP@ssw0rd!!"
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_too_short(self):
        client, user = self.auth_client()
        resp = client.post("/api/auth/change-password/", {
            "old_password": "TestP@ssw0rd!",
            "new_password": "short"
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)


class ForgotPasswordAPITest(APITestCase, AuthMixin):
    def test_forgot_password(self):
        self.create_user()
        resp = self.client.post("/api/auth/forgot-password/", {"email": "user@test.com"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_forgot_password_nonexistent(self):
        """Unknown emails are indistinguishable from known ones.

        REVERSES an owner-requested product decision (audit Z2-5), so it is worth
        stating the reason rather than just flipping the assertion. The old
        behaviour returned 404 "No active account found" to give the user explicit
        feedback — a defensible trade for a generic SaaS.

        It is not defensible here. The endpoint is AllowAny, so the 404 let anyone
        with curl ask "does this person have a FixitLab account?", and because
        FixitLab sells interview practice, a yes reveals that a named individual is
        preparing for interviews. A colleague or a current employer can run that
        check. The usual enumeration argument is about credential stuffing; the
        leak here is membership itself.

        The UX intent behind the original decision survives in the copy: a mistyped
        address still gets "check the address or sign up". See
        `tests/test_password_reset_enumeration.py` for the full three-path
        comparison (unknown / known / mail-failure).
        """
        resp = self.client.post("/api/auth/forgot-password/", {"email": "nobody@test.com"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        known = self.client.post("/api/auth/forgot-password/", {"email": "user@test.com"})
        self.assertEqual(resp.data, known.data)


# ═════════════════════════════════════════════
# 4. Health Check Tests
# ═════════════════════════════════════════════
class HealthCheckTest(APITestCase):
    def test_health_endpoint(self):
        resp = self.client.get("/api/health/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.json()["status"], "ok")

    def test_health_no_auth_required(self):
        resp = self.client.get("/api/health/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ═════════════════════════════════════════════
# 5. Scenarios API Tests
# ═════════════════════════════════════════════
class ScenariosAPITest(APITestCase, AuthMixin, ScenarioMixin):
    def test_list_scenarios_authenticated(self):
        self.create_scenario()
        client, _ = self.auth_client()
        resp = client.get("/api/scenarios/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_list_scenarios_unauthenticated(self):
        """Scenarios list is publicly accessible (AllowAny or IsAuthenticatedOrReadOnly)."""
        self.create_scenario()
        resp = self.client.get("/api/scenarios/")
        self.assertIn(resp.status_code, [status.HTTP_200_OK, status.HTTP_401_UNAUTHORIZED])

    def test_scenario_detail(self):
        s = self.create_scenario()
        client, _ = self.auth_client()
        resp = client.get(f"/api/scenarios/{s.slug}/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ═════════════════════════════════════════════
# 6. Question Bank Permissions Tests
# ═════════════════════════════════════════════
class QuestionBankPermissionsTest(APITestCase, AuthMixin, ScenarioMixin):
    def test_non_admin_cannot_create_technology(self):
        client, _ = self.auth_client()
        resp = client.post("/api/question_bank/technologies/", {
            "name": "Hacker", "slug": "hack"
        })
        self.assertEqual(resp.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_can_read_technologies(self):
        self.create_tech()
        client, _ = self.auth_client()
        resp = client.get("/api/question_bank/technologies/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_can_create_technology(self):
        admin = self.create_user(email="admin@test.com", is_staff=True)
        client, _ = self.auth_client(email="admin@test.com")
        resp = client.post("/api/question_bank/technologies/", {
            "name": "NewTech", "slug": "newtech"
        })
        self.assertIn(resp.status_code, [200, 201])


# ═════════════════════════════════════════════
# 7. Progress & Achievements API Tests
# ═════════════════════════════════════════════
class ProgressAPITest(APITestCase, AuthMixin, ScenarioMixin):
    def test_progress_endpoint(self):
        client, _ = self.auth_client()
        resp = client.get("/api/progress/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_achievements_endpoint(self):
        client, _ = self.auth_client()
        resp = client.get("/api/achievements/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_leaderboard_endpoint(self):
        client, _ = self.auth_client()
        resp = client.get("/api/leaderboard/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ═════════════════════════════════════════════
# 8. Notification API Tests
# ═════════════════════════════════════════════
class NotificationAPITest(APITestCase, AuthMixin):
    def test_list_notifications(self):
        client, user = self.auth_client()
        Notification.objects.create(user=user, type="welcome", title="Welcome!")
        resp = client.get("/api/notifications/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["unread_count"], 1)
        self.assertEqual(len(resp.data["notifications"]), 1)

    def test_mark_read(self):
        client, user = self.auth_client()
        n = Notification.objects.create(user=user, type="system", title="Test")
        resp = client.post(f"/api/notifications/{n.id}/read/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        n.refresh_from_db()
        self.assertTrue(n.read)

    def test_mark_all_read(self):
        client, user = self.auth_client()
        Notification.objects.create(user=user, type="system", title="A")
        Notification.objects.create(user=user, type="system", title="B")
        resp = client.post("/api/notifications/read/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(Notification.objects.filter(user=user, read=False).count(), 0)

    def test_notifications_unauthenticated(self):
        resp = self.client.get("/api/notifications/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


# ═════════════════════════════════════════════
# 9. Admin API Tests
# ═════════════════════════════════════════════
class AdminAPITest(APITestCase, AuthMixin, ScenarioMixin):
    def setUp(self):
        self.admin = self.create_user(email="admin@test.com", is_staff=True)
        self.admin_client, _ = self.auth_client(email="admin@test.com")

    def test_admin_overview(self):
        resp = self.admin_client.get("/api/admin/overview/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertIn("users", resp.data)
        self.assertIn("scenarios", resp.data)
        self.assertIn("labs", resp.data)

    def test_admin_users_list(self):
        resp = self.admin_client.get("/api/admin/users/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)

    def test_admin_blocked_for_non_staff(self):
        client, _ = self.auth_client(email="regular@test.com")
        resp = client.get("/api/admin/overview/")
        # The admin surface is closed to non-staff. Either response means
        # "blocked": 403 when the request is authenticated-but-not-staff, or 401
        # under the cookie-JWT + CSRF-header auth path (SECURITY_AUDIT A-01).
        # This matches the convention in tests/test_admin_panel.py.
        self.assertIn(
            resp.status_code,
            [status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED],
        )

    def test_admin_create_user(self):
        resp = self.admin_client.post("/api/admin/users/", {
            "email": "created@test.com",
            "password": "Created123!",
        })
        self.assertIn(resp.status_code, [200, 201])

    def test_admin_export_users_csv(self):
        resp = self.admin_client.get("/api/admin/export/users/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["Content-Type"], "text/csv")

    def test_admin_export_labs_csv(self):
        resp = self.admin_client.get("/api/admin/export/labs/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp["Content-Type"], "text/csv")

    def test_admin_system_health(self):
        resp = self.admin_client.get("/api/admin/health/")
        self.assertEqual(resp.status_code, status.HTTP_200_OK)


# ═════════════════════════════════════════════
# 10. Edge Cases
# ═════════════════════════════════════════════
class EdgeCaseTests(APITestCase, AuthMixin):
    def test_invalid_json_body(self):
        resp = self.client.post(
            "/api/auth/login/",
            data="not json",
            content_type="application/json"
        )
        self.assertIn(resp.status_code, [400, 415])

    def test_method_not_allowed(self):
        resp = self.client.delete("/api/auth/login/")
        self.assertEqual(resp.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_trailing_slash_redirect(self):
        """Django should 301 to the slash version."""
        resp = self.client.get("/api/health", follow=False)
        self.assertIn(resp.status_code, [200, 301])

    def test_nonexistent_api_route(self):
        client, _ = self.auth_client()
        resp = client.get("/api/this-does-not-exist/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
