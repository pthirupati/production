"""An admin-set password must meet the same policy as a user-chosen one.

Audit Z2-6. The admin user-detail endpoint validated a new password with a bare
`len(new_password) < 8`, bypassing `AUTH_PASSWORD_VALIDATORS` entirely — which
requires **10** characters and rejects common, all-numeric, and
user-attribute-similar passwords. So an operator could set `password` or `12345678`:
values the platform refuses to let the account holder choose for themselves.

Admin resets are exactly the passwords most likely to be weak, because they are typed
quickly during a support call and then read aloud or pasted into a chat. Holding them
to a *lower* bar than self-service inverts the risk.

The route is asserted rather than guarded with `skipTest`: a wrong URL must fail here,
not silently pass. (Written after doing precisely that in
`test_interview_entitlement_audit` and shipping six vacuous tests.)
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

User = get_user_model()


class AdminPasswordPolicyTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="pwadmin", email="pwadmin@example.com",
            password="Str0ng-Pass-1", is_staff=True, is_superuser=True,
        )
        self.target = User.objects.create_user(
            username="pwtarget", email="pwtarget@example.com", password="Str0ng-Pass-1"
        )
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin)
        self.url = f"/api/admin/users/{self.target.id}/"

    def _set_password(self, pw):
        # AdminUserDetailView exposes get/put/delete — not patch. A PATCH returned 405,
        # which the hard route assertion surfaced immediately instead of skipping.
        resp = self.client.put(self.url, {"new_password": pw}, format="json")
        self.assertNotEqual(
            resp.status_code, 404,
            f"{self.url} is not routed — this test must fail on a wrong URL rather "
            "than pass by skipping",
        )
        return resp

    def _password_changed_to(self, pw):
        self.target.refresh_from_db()
        return self.target.check_password(pw)

    # ── the values the old `len < 8` let through ─────────────────────────────
    def test_a_common_password_is_rejected(self):
        resp = self._set_password("password")
        self.assertEqual(resp.status_code, 400, "admin set a top-10 common password")
        self.assertFalse(self._password_changed_to("password"))

    def test_an_all_numeric_password_is_rejected(self):
        resp = self._set_password("12345678")
        self.assertEqual(resp.status_code, 400)
        self.assertFalse(self._password_changed_to("12345678"))

    def test_an_eight_character_password_is_rejected(self):
        """The chain requires 10; the old check allowed 8."""
        resp = self._set_password("Ab3!xY9z")
        self.assertEqual(resp.status_code, 400)

    def test_a_password_similar_to_the_username_is_rejected(self):
        resp = self._set_password("pwtarget123")
        self.assertEqual(resp.status_code, 400)

    def test_the_error_explains_why(self):
        """An operator who cannot see the reason will retry with another weak value."""
        resp = self._set_password("password")
        self.assertTrue(str(resp.data.get("error", "")).strip())

    # ── a legitimate reset still works ───────────────────────────────────────
    def test_a_strong_password_is_accepted(self):
        resp = self._set_password("Quix0tic-Harbour-71")
        self.assertIn(resp.status_code, (200, 202), getattr(resp, "data", resp))
        self.assertTrue(
            self._password_changed_to("Quix0tic-Harbour-71"),
            "a policy-compliant admin reset did not take effect",
        )

    def test_omitting_the_field_leaves_the_password_alone(self):
        resp = self.client.put(self.url, {"phone_number": "+911234567890"}, format="json")
        self.assertNotEqual(resp.status_code, 404)
        self.assertTrue(
            self._password_changed_to("Str0ng-Pass-1"),
            "an unrelated admin edit changed the user's password",
        )


class PolicyMatchesSelfServiceTests(TestCase):
    """The admin path and the user-facing reset must not drift apart again."""

    def test_both_paths_use_the_configured_validator_chain(self):
        import inspect

        from apps.accounts import views as account_views
        from apps.adminpanel import views as admin_views

        for module in (account_views, admin_views):
            src = inspect.getsource(module)
            self.assertIn(
                "validate_password", src,
                f"{module.__name__} no longer runs the configured password chain",
            )

    def test_the_admin_path_has_no_ad_hoc_length_check(self):
        import inspect

        from apps.adminpanel import views as admin_views

        code = "\n".join(
            line for line in inspect.getsource(admin_views).splitlines()
            if not line.strip().startswith("#")
        )
        self.assertNotIn(
            "len(new_password) < 8", code,
            "the ad-hoc 8-character check is back, bypassing the validator chain",
        )
