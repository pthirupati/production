"""Org webhook delivery guarantees (audit S5, docs/AUDIT_2026_08_TODO.md:145-151).

The SSRF guard in apps/accounts/url_safety.py validates the URL we are *about* to
request. Two things can defeat that after validation passes, and neither had a
test before this file:

1. Redirects. ``requests.post`` follows them by default, so a public host the org
   owner controls can answer 302 → http://169.254.169.254/ and reach instance
   metadata without ever storing an unsafe URL.
2. Regression of the async move. ``fire_org_webhook`` must enqueue, not POST on
   the request path; if the Celery task import in celery_app/tasks.py were lost
   the code would silently degrade back to inline sending.
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.accounts.models import Organization
from apps.accounts.webhooks import _post_org_webhook, fire_org_webhook

User = get_user_model()


class _FakeResponse:
    """Mimics the bits of requests.Response that _post_org_webhook touches."""

    def __init__(self, status_code):
        self.status_code = status_code
        self.ok = 200 <= status_code < 400
        self.is_redirect = status_code in (301, 302, 303, 307, 308)
        self.is_permanent_redirect = status_code in (301, 308)


class OrgWebhookRedirectTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            username="redirect-owner", email="redirect@example.com", password="x"
        )
        self.org = Organization.objects.create(
            name="Redirect Co",
            slug="redirect-co",
            owner=owner,
            webhook_url="https://hooks.example.com/fixitlab",
        )

    def test_post_does_not_follow_redirects(self):
        """A redirect off the validated host must not be followed."""
        with patch("apps.accounts.webhooks.requests.post") as mock_post:
            mock_post.return_value = _FakeResponse(302)
            result = _post_org_webhook(self.org, "lab.completed", {"lab": "x"})

        self.assertFalse(
            result,
            "A 302 from the webhook target must be reported as a failed delivery, "
            "not followed to wherever it points.",
        )
        _, kwargs = mock_post.call_args
        self.assertIs(
            kwargs.get("allow_redirects"),
            False,
            "requests.post must be called with allow_redirects=False; following a "
            "redirect bypasses validate_outbound_url entirely (SSRF).",
        )

    def test_successful_post_still_reported_ok(self):
        """Guard against fixing the redirect hole by breaking normal delivery."""
        with patch("apps.accounts.webhooks.requests.post") as mock_post:
            mock_post.return_value = _FakeResponse(200)
            self.assertTrue(_post_org_webhook(self.org, "lab.completed", {"lab": "x"}))


class OrgWebhookAsyncTests(TestCase):
    def setUp(self):
        owner = User.objects.create_user(
            username="async-owner", email="async@example.com", password="x"
        )
        self.org = Organization.objects.create(
            name="Async Co",
            slug="async-co",
            owner=owner,
            webhook_url="https://hooks.example.com/fixitlab",
        )

    def test_fire_enqueues_instead_of_posting_inline(self):
        """fire_org_webhook must hand off to Celery, never POST on the request path."""
        with patch("apps.accounts.webhooks.deliver_org_webhook.delay") as mock_delay, \
                patch("apps.accounts.webhooks.requests.post") as mock_post:
            self.assertTrue(fire_org_webhook(self.org, "lab.completed", {"lab": "x"}))

        mock_delay.assert_called_once()
        mock_post.assert_not_called()

    def test_no_webhook_url_is_a_noop(self):
        self.org.webhook_url = ""
        self.org.save(update_fields=["webhook_url"])
        with patch("apps.accounts.webhooks.deliver_org_webhook.delay") as mock_delay:
            self.assertFalse(fire_org_webhook(self.org, "lab.completed", {}))
        mock_delay.assert_not_called()
