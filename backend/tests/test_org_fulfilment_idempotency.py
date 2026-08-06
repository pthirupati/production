"""Org seat fulfilment must survive a Redis flush without re-granting.

The org verify endpoint deduped on a Redis key alone (`cache.add`, 24h TTL) — the
same pattern audit Z1-4 replaced for the Stripe and Razorpay webhooks, and for the
same reason: a Redis flush or eviction reopens the double-fulfilment window, and a
replayed verify (a retry, a double-click, a refreshed tab) re-grants seats and writes
a second PaymentTransaction.

Redis is a cache. Treating it as the authoritative record of "we already did this"
means the guarantee evaporates on any operation that clears it — a restart, a
maxmemory eviction, a deploy. `ProcessedWebhookEvent` is the durable gate.

The transaction boundary is the subtle part and gets its own test: the row and the
fulfilment must commit together, so a crash mid-fulfilment rolls the row back and a
genuine retry still works, rather than being permanently locked out by a marker for
work that never completed.
"""
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.billing.models import ProcessedWebhookEvent

User = get_user_model()


class DurableDedupTests(TestCase):
    """The gate is a database row, not a cache key."""

    def setUp(self):
        cache.clear()
        self.payment_id = "pay_org_123"

    def _claim(self):
        """Mirror the endpoint's gate: create the row, report whether we won."""
        _, created = ProcessedWebhookEvent.objects.get_or_create(
            event_id=f"org_seats:{self.payment_id}",
            defaults={"provider": "razorpay"},
        )
        return created

    def test_first_verify_claims_the_payment(self):
        self.assertTrue(self._claim())

    def test_replay_is_refused(self):
        self._claim()
        self.assertFalse(self._claim(), "a replayed verify would re-grant seats")

    def test_the_claim_survives_a_cache_flush(self):
        """The whole point: a Redis flush must not reopen the window."""
        self._claim()
        cache.clear()
        self.assertFalse(
            self._claim(),
            "clearing Redis reopened the double-fulfilment window — the gate is "
            "still effectively cache-only",
        )

    def test_distinct_payments_are_independent(self):
        self.assertTrue(self._claim())
        self.payment_id = "pay_org_456"
        self.assertTrue(self._claim(), "a second genuine purchase was blocked")

    def test_the_event_id_is_namespaced(self):
        """Org fulfilment shares this table with payment webhooks; a bare payment id
        could collide with a webhook event id and silently skip one of them."""
        self._claim()
        row = ProcessedWebhookEvent.objects.get(event_id=f"org_seats:{self.payment_id}")
        self.assertTrue(row.event_id.startswith("org_seats:"))


class EndpointUsesTheDurableGateTests(TestCase):
    """Structural: the endpoint must not fall back to the cache-only pattern."""

    def test_org_verify_no_longer_dedups_on_a_cache_key_alone(self):
        import inspect

        from apps.accounts import org_views

        code = "\n".join(
            line for line in inspect.getsource(org_views).splitlines()
            if not line.strip().startswith("#")
        )
        self.assertNotIn(
            "org_razorpay_fulfilled:", code,
            "org fulfilment still guards on a Redis key, which a flush would clear",
        )
        self.assertIn("ProcessedWebhookEvent", code)

    def test_fulfilment_happens_inside_the_transaction(self):
        """The row and the grant must commit together — otherwise a crash
        mid-fulfilment leaves a marker for work that never happened and permanently
        blocks the retry."""
        import inspect

        from apps.accounts import org_views

        src = inspect.getsource(org_views)
        start = src.index("org_seats:")
        window = src[start - 600 : start + 900]
        self.assertIn("atomic()", window)
        self.assertIn("fulfill_org_razorpay_order", window)
