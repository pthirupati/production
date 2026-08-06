"""A pending org invite must not hand out privilege on an email match alone.

Audit Z2-2. `PendingOrgInvite.token` is minted with `secrets.token_urlsafe(32)`,
stored `unique=True`, and passed to the invite email — and **nothing ever validated
it**. Redemption at registration matched on `email__iexact` and granted
`invite.role` verbatim, so for the full 14-day window a pending invite silently made
whoever next registered that address an organisation **admin**. A typo'd invite, or
an address that changes hands, was enough.

Measured before changing anything, because the obvious fix would have broken the
feature: the invite email's action URL was `/register?email=...` with **no token in
it**. The token was passed to the template and never rendered, so it could not reach
the invitee — requiring it outright would have blocked every legitimate invite.

So: the token is now in the URL, and an email match confers **member** only. The
invited role is honoured when the request carries the matching token. Auto-join still
works without it — the feature keeps working, it just cannot grant privilege.
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import (
    EmailVerificationOTP,
    Organization,
    OrganizationMember,
    PendingOrgInvite,
)

User = get_user_model()
EMAIL = "invitee@example.com"


class _InviteBase(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="Str0ng-Pass-1"
        )
        self.org = Organization.objects.create(
            name="Acme Eng", slug="acme-eng", owner=self.owner
        )
        self.client = APIClient()

    def _invite(self, role="admin", token="tok-" + "a" * 28):
        return PendingOrgInvite.objects.create(
            organization=self.org, email=EMAIL, role=role,
            invited_by=self.owner, token=token,
            expires_at=timezone.now() + timedelta(days=14),
        )

    def _register(self, **extra):
        """Register EMAIL through the real endpoint, with a verified OTP session."""
        from django.contrib.auth.hashers import make_password

        EmailVerificationOTP.objects.create(
            email=EMAIL, code_hash=make_password("123456"), verified=True,
            session_token="invite-sess-token",
            expires_at=timezone.now() + timedelta(minutes=30),
        )
        payload = {
            "email": EMAIL,
            "password": "GoodP@ss99!",
            "session_token": "invite-sess-token",
        }
        payload.update(extra)
        return self.client.post("/api/auth/register/", payload, format="json")

    def _role(self):
        m = OrganizationMember.objects.filter(
            organization=self.org, user__email=EMAIL
        ).first()
        return m.role if m else None


class EmailMatchCannotGrantPrivilegeTests(_InviteBase):
    def test_admin_invite_without_token_joins_as_member(self):
        self._invite(role="admin")
        resp = self._register()
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            self._role(), "member",
            "an email match alone made the user an organisation admin",
        )

    def test_owner_invite_without_token_joins_as_member(self):
        self._invite(role="owner")
        self._register()
        self.assertEqual(self._role(), "member")

    def test_a_wrong_token_does_not_elevate(self):
        self._invite(role="admin", token="real-token-" + "b" * 20)
        self._register(invite_token="guessed-token")
        self.assertEqual(self._role(), "member")

    def test_an_empty_token_does_not_elevate(self):
        self._invite(role="admin")
        self._register(invite_token="")
        self.assertEqual(self._role(), "member")


class ValidTokenHonoursTheInvitedRoleTests(_InviteBase):
    def test_matching_token_grants_admin(self):
        invite = self._invite(role="admin")
        resp = self._register(invite_token=invite.token)
        self.assertEqual(resp.status_code, 201, resp.data)
        self.assertEqual(
            self._role(), "admin",
            "a legitimate invitee with the emailed token was denied their role",
        )


class TheFeatureStillWorksTests(_InviteBase):
    """The fix must not break auto-join — that was the whole reason the token could
    not simply be made mandatory."""

    def test_member_invite_still_auto_joins_without_a_token(self):
        self._invite(role="member")
        self._register()
        self.assertEqual(self._role(), "member")

    def test_invite_is_marked_accepted(self):
        invite = self._invite(role="member")
        self._register()
        invite.refresh_from_db()
        self.assertIsNotNone(invite.accepted_at)

    def test_expired_invite_confers_nothing(self):
        invite = self._invite(role="member")
        PendingOrgInvite.objects.filter(pk=invite.pk).update(
            expires_at=timezone.now() - timedelta(days=1)
        )
        self._register()
        self.assertIsNone(self._role())


class InviteEmailCarriesTheTokenTests(TestCase):
    """The token has to reach the invitee, or the elevation path is unreachable and
    every invited admin silently lands as a member."""

    def test_registration_url_includes_the_token(self):
        from unittest import mock

        from apps.accounts import org_views

        owner = User.objects.create_user(
            username="o2", email="o2@example.com", password="Str0ng-Pass-1"
        )
        org = Organization.objects.create(name="Beta", slug="beta", owner=owner)
        with mock.patch.object(org_views, "send_notification_email") as task:
            task.delay = mock.MagicMock()
            org_views._send_org_invite_email(
                org, EMAIL, owner, is_new_user=True, token="tok-xyz",
            )
        ctx = task.delay.call_args.kwargs["context"]
        self.assertIn("invite_token=tok-xyz", ctx["action_url"])

    def test_existing_user_link_goes_to_login_without_a_token(self):
        from unittest import mock

        from apps.accounts import org_views

        owner = User.objects.create_user(
            username="o3", email="o3@example.com", password="Str0ng-Pass-1"
        )
        org = Organization.objects.create(name="Gamma", slug="gamma", owner=owner)
        with mock.patch.object(org_views, "send_notification_email") as task:
            task.delay = mock.MagicMock()
            org_views._send_org_invite_email(
                org, EMAIL, owner, is_new_user=False, token="tok-xyz",
            )
        ctx = task.delay.call_args.kwargs["context"]
        self.assertNotIn("invite_token", ctx["action_url"])


class LegacyOrderCurrencyTests(TestCase):
    """Audit Z1-10 — the client used to choose the currency.

    `payment_controller.py` read `request.data.get("currency", "INR")` three lines
    below a comment insisting the price must never be trusted from the client. Amount
    and currency are one fact, not two: posting {"currency": "USD"} produced a $499
    order for a ₹499 product (~83x), and it then PASSED verification, because
    payment_service compares the payment against the currency stored on the order.
    """

    @staticmethod
    def _code_lines(module):
        """Source with comment lines removed.

        The first version of this test matched its own documentation: the fix's
        explanatory comment quotes the old `request.data.get("currency", "INR")`, so
        scanning raw source reported a second offending site that does not exist. A
        structural test has to look at code, not prose.
        """
        import inspect

        return "\n".join(
            line for line in inspect.getsource(module).splitlines()
            if not line.strip().startswith("#")
        )

    def test_controller_does_not_read_currency_from_the_request(self):
        from apps.billing import payment_controller

        code = self._code_lines(payment_controller)
        self.assertNotIn(
            'request.data.get("currency"', code,
            "the legacy order path takes the currency from the client again",
        )
        self.assertNotIn("request.data.get('currency'", code)

    def test_currency_is_pinned_to_inr(self):
        from apps.billing import payment_controller

        self.assertIn('currency = "INR"', self._code_lines(payment_controller))
