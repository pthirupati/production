"""Payment-safety tests (PRODUCTION_AUDIT FIN-02, FIN-03, idempotency, REL-06).

  * Refund: cannot exceed captured amount; idempotent under a double call (one
    gateway refund, not two); persists the refund id; uses Decimal.
  * Org-seat verify: refuses to grant seats unless the payment is CAPTURED.
  * Webhook / confirm idempotency: a replayed capture does not double-fulfil.
  * Reconciliation: a stuck-but-captured transaction is fulfilled, not failed.
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.billing.models import PaymentTransaction
from apps.question_bank.models import Technology

User = get_user_model()

RZP = dict(
    RAZORPAY_KEY_ID="rzp_test",
    RAZORPAY_KEY_SECRET="test_secret",
    RAZORPAY_WEBHOOK_SECRET="whsec_test",
    ROOT_URLCONF="config.urls",
    SECURE_SSL_REDIRECT=False,
)


@override_settings(**RZP)
class RefundHardeningTest(TestCase):
    """PRODUCTION_AUDIT FIN-02."""

    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            username="refadmin", email="refadmin@test.com", password="Pass123!x",
            is_staff=True, is_superuser=True,
        )
        self.user = User.objects.create_user(
            username="payer", email="payer@test.com", password="Pass123!x",
        )
        self.client.force_authenticate(user=self.admin)
        self.tx = PaymentTransaction.objects.create(
            user=self.user,
            amount=Decimal("499.00"),
            currency="INR",
            payment_method="razorpay",
            status="success",
            idempotency_key="refund-tx-key",
            gateway_order_id="order_ref_1",
            gateway_payment_id="pay_ref_1",
        )

    def _mock_client(self, refund_id="rfnd_1"):
        mc = MagicMock()
        mc.payment.refund.return_value = {"id": refund_id, "status": "processed"}
        return mc

    def test_refund_cannot_exceed_captured(self):
        mc = self._mock_client()
        with patch("razorpay.Client", return_value=mc):
            resp = self.client.post(
                "/api/billing/razorpay/refund/",
                data={"payment_id": "pay_ref_1", "amount": 600},  # > ₹499 captured
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("exceeds", resp.json().get("error", "").lower())
        # No refund call to the gateway, nothing recorded.
        mc.payment.refund.assert_not_called()
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.refunded_amount, Decimal("0"))

    def test_partial_refunds_cannot_cumulatively_exceed_captured(self):
        mc = self._mock_client()
        with patch("razorpay.Client", return_value=mc):
            r1 = self.client.post(
                "/api/billing/razorpay/refund/",
                data={"payment_id": "pay_ref_1", "amount": 300},
                content_type="application/json",
            )
            self.assertEqual(r1.status_code, 201, r1.content)
            # A distinct second partial of 250 would total 550 > 499 → rejected
            # (distinct amount, so this exercises the ceiling, not idempotency).
            r2 = self.client.post(
                "/api/billing/razorpay/refund/",
                data={"payment_id": "pay_ref_1", "amount": 250},
                content_type="application/json",
            )
        self.assertEqual(r2.status_code, 400)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.refunded_amount, Decimal("300.00"))
        # Exactly one gateway refund happened.
        self.assertEqual(mc.payment.refund.call_count, 1)

    def test_refund_is_idempotent_under_double_call(self):
        # Same payment + amount twice (double-click). The derived idempotency key
        # is identical, so the second call must NOT issue a second gateway refund.
        mc = self._mock_client(refund_id="rfnd_dup")
        with patch("razorpay.Client", return_value=mc):
            r1 = self.client.post(
                "/api/billing/razorpay/refund/",
                data={"payment_id": "pay_ref_1", "amount": 100},
                content_type="application/json",
            )
            r2 = self.client.post(
                "/api/billing/razorpay/refund/",
                data={"payment_id": "pay_ref_1", "amount": 100},
                content_type="application/json",
            )
        self.assertEqual(r1.status_code, 201, r1.content)
        self.assertEqual(r2.status_code, 200, r2.content)
        self.assertTrue(r2.json().get("already_refunded"))
        # Only one actual gateway refund + only ₹100 counted, not ₹200.
        self.assertEqual(mc.payment.refund.call_count, 1)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.refunded_amount, Decimal("100.00"))
        # Refund id persisted for audit.
        refunds = (self.tx.gateway_response or {}).get("refunds") or []
        self.assertEqual(len(refunds), 1)
        self.assertEqual(refunds[0]["id"], "rfnd_dup")

    def test_full_refund_marks_status_refunded(self):
        mc = self._mock_client()
        with patch("razorpay.Client", return_value=mc):
            resp = self.client.post(
                "/api/billing/razorpay/refund/",
                data={"payment_id": "pay_ref_1", "amount": 499},
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, "refunded")
        self.assertEqual(self.tx.refunded_amount, Decimal("499.00"))

    def test_refund_requires_existing_transaction(self):
        mc = self._mock_client()
        with patch("razorpay.Client", return_value=mc):
            resp = self.client.post(
                "/api/billing/razorpay/refund/",
                data={"payment_id": "pay_does_not_exist", "amount": 100},
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 404)
        mc.payment.refund.assert_not_called()


@override_settings(**RZP)
class OrgSeatCaptureTest(TestCase):
    """PRODUCTION_AUDIT FIN-03 — seats only granted when payment is captured."""

    def setUp(self):
        from django.core.cache import cache

        from apps.accounts.models import Organization, OrganizationMember

        cache.clear()  # idempotency lock keys are cache-backed; isolate tests
        self.client = APIClient()
        self.owner = User.objects.create_user(
            username="orgowner", email="owner@test.com", password="Pass123!x",
        )
        self.client.force_authenticate(user=self.owner)
        self.org = Organization.objects.create(
            name="Acme", slug="acme", owner=self.owner, seat_limit=5,
        )
        OrganizationMember.objects.create(organization=self.org, user=self.owner, role="owner")

    def _signature(self, order_id, payment_id):
        import hashlib
        import hmac

        return hmac.new(
            b"test_secret", f"{order_id}|{payment_id}".encode(), hashlib.sha256,
        ).hexdigest()

    def _order(self):
        return {
            "id": "order_org_1",
            "amount": 9998 * 100,
            "notes": {
                "checkout_type": "organization",
                "org_id": str(self.org.id),
                "org_slug": "acme",
                "seats": "10",
                "technology_ids": "",
                "user_id": str(self.owner.id),
                "amount_inr": "9998",
            },
        }

    def test_refuses_when_payment_not_captured(self):
        order_id, payment_id = "order_org_1", "pay_org_1"
        mc = MagicMock()
        mc.order.fetch.return_value = self._order()
        # Payment only authorized, NOT captured.
        mc.payment.fetch.return_value = {
            "order_id": order_id, "amount": 9998 * 100, "status": "authorized",
        }
        with patch("razorpay.Client", return_value=mc):
            resp = self.client.post(
                f"/api/org/acme/verify-payment/",
                data={
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": self._signature(order_id, payment_id),
                },
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not captured", resp.json().get("error", "").lower())
        # Seats unchanged.
        self.org.refresh_from_db()
        self.assertEqual(self.org.seat_limit, 5)

    def test_grants_seats_when_captured(self):
        order_id, payment_id = "order_org_1", "pay_org_1"
        mc = MagicMock()
        mc.order.fetch.return_value = self._order()
        mc.payment.fetch.return_value = {
            "order_id": order_id, "amount": 9998 * 100, "status": "captured",
        }
        with patch("razorpay.Client", return_value=mc):
            resp = self.client.post(
                f"/api/org/acme/verify-payment/",
                data={
                    "razorpay_order_id": order_id,
                    "razorpay_payment_id": payment_id,
                    "razorpay_signature": self._signature(order_id, payment_id),
                },
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertTrue(resp.json().get("verified"))
        self.org.refresh_from_db()
        self.assertEqual(self.org.seat_limit, 10)

    def test_double_verify_does_not_double_fulfil(self):
        from django.core.cache import cache

        cache.clear()
        order_id, payment_id = "order_org_1", "pay_org_1"
        mc = MagicMock()
        mc.order.fetch.return_value = self._order()
        mc.payment.fetch.return_value = {
            "order_id": order_id, "amount": 9998 * 100, "status": "captured",
        }
        with patch("razorpay.Client", return_value=mc):
            payload = {
                "razorpay_order_id": order_id,
                "razorpay_payment_id": payment_id,
                "razorpay_signature": self._signature(order_id, payment_id),
            }
            r1 = self.client.post("/api/org/acme/verify-payment/", data=payload, content_type="application/json")
            r2 = self.client.post("/api/org/acme/verify-payment/", data=payload, content_type="application/json")
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.assertTrue(r2.json().get("already_fulfilled"))


@override_settings(**RZP)
class WebhookIdempotencyTest(TestCase):
    """A replayed payment.captured webhook must not double-fulfil."""

    def setUp(self):
        from django.core.cache import cache

        cache.clear()
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="whuser", email="wh@test.com", password="Pass123!x",
        )
        self.tech = Technology.objects.create(
            name="Terraform", icon="tf", price=499, is_active=True,
        )
        from apps.billing.razorpay_fulfillment import create_technology_payment_transaction

        self.order = {"id": "order_wh_1", "amount": 49900, "currency": "INR", "notes": {}}
        self.tx = create_technology_payment_transaction(
            user=self.user, amount=499, order=self.order, technology_id=self.tech.id,
        )

    def _event(self):
        import time

        return {
            "id": "evt_wh_1",
            "event": "payment.captured",
            "created_at": int(time.time()),
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_wh_1",
                        "order_id": "order_wh_1",
                        "amount": 49900,
                        "currency": "INR",
                        "status": "captured",
                    }
                }
            },
        }

    def _post(self, payload_bytes):
        import hashlib
        import hmac

        sig = hmac.new(b"whsec_test", payload_bytes, hashlib.sha256).hexdigest()
        return self.client.post(
            "/api/billing/webhook/razorpay/",
            data=payload_bytes,
            content_type="application/json",
            HTTP_X_RAZORPAY_SIGNATURE=sig,
        )

    def test_replayed_capture_creates_one_subscription(self):
        import json

        from apps.billing.models import TechnologySubscription

        payload = json.dumps(self._event()).encode()
        r1 = self._post(payload)
        self.assertEqual(r1.status_code, 200, r1.content)
        # Replay the SAME event id → cache dedupe returns 'duplicate'.
        r2 = self._post(payload)
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.json().get("status"), "duplicate")

        subs = TechnologySubscription.objects.filter(user=self.user, technology=self.tech)
        self.assertEqual(subs.count(), 1)
        self.assertTrue(subs.first().is_active)
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, "success")

    def test_distinct_replay_after_cache_eviction_still_idempotent(self):
        # Simulate the idempotency cache key being evicted (REL-07) by clearing
        # the cache between two deliveries with DIFFERENT event ids for the SAME
        # captured payment. The per-row status guard must still prevent a second
        # fulfilment.
        import json

        from django.core.cache import cache

        from apps.billing.models import TechnologySubscription

        ev1 = self._event()
        r1 = self._post(json.dumps(ev1).encode())
        self.assertEqual(r1.status_code, 200, r1.content)

        cache.clear()  # evict the webhook idempotency marker
        ev2 = self._event()
        ev2["id"] = "evt_wh_2"  # different event id, same payment id
        r2 = self._post(json.dumps(ev2).encode())
        self.assertEqual(r2.status_code, 200, r2.content)

        subs = TechnologySubscription.objects.filter(user=self.user, technology=self.tech)
        self.assertEqual(subs.count(), 1)


@override_settings(**RZP)
class StuckTransactionReconcileTest(TestCase):
    """PRODUCTION_AUDIT REL-06 — a captured-but-stuck tx is fulfilled, not failed."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="stuckuser", email="stuck@test.com", password="Pass123!x",
        )
        self.tech = Technology.objects.create(
            name="Ansible", icon="ans", price=499, is_active=True,
        )
        from apps.billing.razorpay_fulfillment import create_technology_payment_transaction

        order = {"id": "order_stuck_1", "amount": 49900, "currency": "INR", "notes": {}}
        self.tx = create_technology_payment_transaction(
            user=self.user, amount=499, order=order, technology_id=self.tech.id,
        )
        # Force it old enough to be 'stuck'.
        from django.utils import timezone
        from datetime import timedelta

        PaymentTransaction.objects.filter(pk=self.tx.pk).update(
            updated_at=timezone.now() - timedelta(hours=12),
        )

    def test_captured_stuck_tx_is_fulfilled_not_failed(self):
        from apps.billing.models import TechnologySubscription
        from apps.billing.tasks import _reconcile_or_fail_one

        mc = MagicMock()
        mc.order.payments.return_value = {
            "items": [
                {"id": "pay_stuck_1", "order_id": "order_stuck_1", "amount": 49900, "status": "captured"}
            ]
        }
        mc.payment.fetch.return_value = {
            "order_id": "order_stuck_1", "amount": 49900, "status": "captured",
        }
        self.tx.refresh_from_db()
        with patch("razorpay.Client", return_value=mc):
            result = _reconcile_or_fail_one(self.tx)
        self.assertEqual(result, "captured")
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, "success")
        self.assertTrue(
            TechnologySubscription.objects.filter(user=self.user, technology=self.tech, is_active=True).exists()
        )

    def test_abandoned_tx_with_no_payment_is_failed(self):
        from apps.billing.tasks import _reconcile_or_fail_one

        mc = MagicMock()
        mc.order.payments.return_value = {"items": []}  # user never paid
        self.tx.refresh_from_db()
        with patch("razorpay.Client", return_value=mc):
            result = _reconcile_or_fail_one(self.tx)
        self.assertEqual(result, "failed")
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, "failed")

    def test_authorized_only_tx_is_left_processing(self):
        from apps.billing.tasks import _reconcile_or_fail_one

        mc = MagicMock()
        mc.order.payments.return_value = {
            "items": [{"id": "pay_x", "order_id": "order_stuck_1", "amount": 49900, "status": "authorized"}]
        }
        self.tx.refresh_from_db()
        with patch("razorpay.Client", return_value=mc):
            result = _reconcile_or_fail_one(self.tx)
        self.assertEqual(result, "authorized")
        self.tx.refresh_from_db()
        self.assertEqual(self.tx.status, "processing")  # NOT failed
