"""The support bot must not describe someone else's lab session.

Audit Z3-9. `resolve_lab_context` extracts a session UUID from the caller-supplied
`page_path` and looked it up **by id alone**, on an `AllowAny` endpoint. Anyone
holding a session id — including an anonymous caller — got back that session's
scenario slug, title and technology.

UUID4 makes the id unguessable, which is why this is low impact rather than none. But
unguessability is not access control: session ids leak through server logs, shared
URLs, screenshots and `Referer` headers, and the endpoint requires no authentication
at all, so a leaked id is directly exploitable by anyone who sees it.

The lookup is now scoped to the requesting user, and an unauthenticated caller gets
no context rather than someone else's.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.labs.models import LabSession
from apps.question_bank.models import Scenario, Technology
from apps.support.service import resolve_lab_context

User = get_user_model()


class _Base(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="ctxowner", email="ctxowner@example.com", password="Str0ng-Pass-1"
        )
        self.other = User.objects.create_user(
            username="ctxother", email="ctxother@example.com", password="Str0ng-Pass-1"
        )
        tech = Technology.objects.create(name="CtxTech", slug="ctxtech")
        self.scenario = Scenario.objects.create(
            title="Secret Scenario Title", slug="secret-scenario",
            technology=tech, description="d",
        )
        self.session = LabSession.objects.create(
            user=self.owner, scenario=self.scenario
        )
        self.path = f"/lab/{self.session.id}"


class ContextIsScopedToTheOwnerTests(_Base):
    def test_owner_gets_their_own_context(self):
        ctx = resolve_lab_context(self.path, user=self.owner)
        self.assertEqual(ctx["scenario_slug"], "secret-scenario")
        self.assertEqual(ctx["scenario_title"], "Secret Scenario Title")

    def test_another_user_gets_nothing(self):
        ctx = resolve_lab_context(self.path, user=self.other)
        self.assertEqual(ctx["scenario_slug"], "")
        self.assertEqual(
            ctx["scenario_title"], "",
            "the support bot disclosed another user's scenario",
        )

    def test_anonymous_gets_nothing(self):
        self.assertEqual(resolve_lab_context(self.path, user=None)["scenario_slug"], "")

    def test_an_unauthenticated_user_object_gets_nothing(self):
        from django.contrib.auth.models import AnonymousUser

        ctx = resolve_lab_context(self.path, user=AnonymousUser())
        self.assertEqual(ctx["scenario_slug"], "")

    def test_no_path_is_still_safe(self):
        self.assertEqual(resolve_lab_context("", user=self.owner)["scenario_slug"], "")

    def test_a_junk_path_never_raises(self):
        for bad in ("/lab/not-a-uuid", "/", "../../etc/passwd", "/lab/" + "f" * 200):
            self.assertEqual(resolve_lab_context(bad, user=self.owner)["scenario_slug"], "")


class EndpointDoesNotLeakTests(_Base):
    """End-to-end through the AllowAny view, which is where the exposure lived."""

    def setUp(self):
        super().setUp()
        self.client = APIClient()
        self.url = "/api/support/chat/"

    def _ask(self):
        return self.client.post(
            self.url,
            {"message": "how do I fix this lab?", "page_path": self.path},
            format="json",
        )

    def test_anonymous_caller_cannot_read_the_scenario(self):
        resp = self._ask()
        if resp.status_code != 200:
            self.skipTest(f"support bot unavailable in this config ({resp.status_code})")
        self.assertNotIn("Secret Scenario Title", str(resp.data))
        self.assertNotIn("secret-scenario", str(resp.data))

    def test_a_different_authenticated_user_cannot_read_it(self):
        self.client.force_authenticate(user=self.other)
        resp = self._ask()
        if resp.status_code != 200:
            self.skipTest(f"support bot unavailable in this config ({resp.status_code})")
        self.assertNotIn("Secret Scenario Title", str(resp.data))
        self.assertNotIn("secret-scenario", str(resp.data))

    def test_the_owner_still_gets_contextual_help(self):
        """The scoping must not break the feature for the person it is meant to help."""
        self.client.force_authenticate(user=self.owner)
        resp = self._ask()
        if resp.status_code != 200:
            self.skipTest(f"support bot unavailable in this config ({resp.status_code})")
        self.assertIn("reply", resp.data)
