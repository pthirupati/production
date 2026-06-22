from django.test import TestCase, override_settings
from django.urls import reverse
from django.conf import settings
from django.core.cache import cache
import json, hmac, hashlib
from apps.billing.models import PaymentTransaction, TechnologySubscription
from django.contrib.auth import get_user_model

User = get_user_model()

@override_settings(ROOT_URLCONF='config.urls', MIGRATION_MODULES={"billing": None}, SECURE_SSL_REDIRECT=False)
class BillingWebhookTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(username='webhookuser', email='user@test.com', password='password')
        # Ensure billing_paymenttransaction table exists for tests (no migrations in CI)
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(
                '''
                CREATE TABLE IF NOT EXISTS billing_paymenttransaction (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    amount NUMERIC,
                    currency VARCHAR(3),
                    payment_method VARCHAR(20),
                    status VARCHAR(20),
                    idempotency_key VARCHAR(128),
                    gateway_order_id VARCHAR(200),
                    gateway_payment_id VARCHAR(200),
                    gateway_response TEXT,
                    created_at DATETIME,
                    updated_at DATETIME,
                    verified_at DATETIME,
                    error_message TEXT
                );
                '''
            )

    def test_razorpay_webhook_payment_captured_marks_transaction_success(self):
        # Prepare a fake transaction object and mock manager methods
        class FakeTx:
            def __init__(self):
                self.id = 'fake-tx-1'
                self.user = self_user
                self.amount = 100.00
                self.currency = 'INR'
                self.status = 'processing'
                self.gateway_payment_id = None
                # The capture handler now MERGES the payment entity into the
                # existing gateway_response (to preserve order/product metadata),
                # so the mock must expose a dict here.
                self.gateway_response = {}
                self.tech_subscription = None
                self.plan = None

            def refresh_from_db(self):
                return

            def save(self, *args, **kwargs):
                return

            def mark_success(self, gateway_payment_id=None, gateway_response=None):
                self.status = 'success'
                if gateway_payment_id:
                    self.gateway_payment_id = gateway_payment_id
                if gateway_response is not None:
                    self.gateway_response = gateway_response

        self_user = self.user
        fake_tx = FakeTx()

        # Mock PaymentTransaction manager to provide .filter(...).first() and .select_for_update().get()
        from unittest.mock import patch, MagicMock
        mock_mgr = MagicMock()
        mock_mgr.filter.return_value = MagicMock(first=MagicMock(return_value=fake_tx))
        mock_mgr.select_for_update.return_value = MagicMock(get=MagicMock(return_value=fake_tx))

        event = {
            "event": "payment.captured",
            "payload": {
                "payment": {
                    "entity": {
                        "id": "pay_test_123",
                        "order_id": "order_test_123",
                        "amount": 10000,
                        "currency": "INR",
                        "status": "captured",
                    }
                }
            }
        }
        payload = json.dumps(event).encode()
        secret = 'test_razor_secret'

        # Compute signature expected by our webhook verifier
        signature = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

        with patch('apps.billing.models.PaymentTransaction.objects', new=mock_mgr):
            # RAZORPAY_WEBHOOK_SECRET must be set — the webhook handler uses this
            # to verify signatures (separate from RAZORPAY_KEY_SECRET).
            with override_settings(RAZORPAY_KEY_SECRET=secret, RAZORPAY_WEBHOOK_SECRET=secret):
                url = reverse('razorpay_webhook')
                resp = self.client.post(url, data=payload, content_type='application/json', HTTP_X_RAZORPAY_SIGNATURE=signature)
                self.assertEqual(resp.status_code, 200)

                # Verify fake_tx was marked success
                self.assertEqual(fake_tx.status, 'success')
                self.assertEqual(fake_tx.gateway_payment_id, 'pay_test_123')

    def test_stripe_webhook_checkout_completed_marks_transaction_success(self):
        # Prepare a fake transaction and mock manager methods for Stripe
        class FakeTx2:
            def __init__(self):
                self.id = 'fake-tx-2'
                self.user = self_user2
                self.amount = 49.99
                self.currency = 'USD'
                self.status = 'processing'
                self.gateway_payment_id = None
                self.tech_subscription = None
                self.plan = None
                self.gateway_response = {}

            def mark_failed(self, message=""):
                self.status = "failed"
                return

            def refresh_from_db(self):
                return

            def save(self, *args, **kwargs):
                return

            def mark_success(self, gateway_payment_id=None, gateway_response=None):
                self.status = 'success'
                if gateway_payment_id:
                    self.gateway_payment_id = gateway_payment_id

        self_user2 = self.user
        fake_tx2 = FakeTx2()

        from unittest.mock import patch, MagicMock
        mock_filter2 = MagicMock()
        mock_filter2.first.return_value = fake_tx2
        # Stripe constructs event with id and type and data.object
        event = {
            'id': 'evt_test_1',
            'type': 'checkout.session.completed',
            'data': {
                'object': {
                    'id': 'cs_test_123',
                    'amount_total': int(fake_tx2.amount * 100),
                    'metadata': {},
                    'payment_intent': 'pi_test_123'
                }
            }
        }
        payload = json.dumps(event).encode()

        # Patch stripe.Webhook.construct_event to return our event object and patch PaymentTransaction.objects
        import stripe
        from unittest.mock import patch

        mock_mgr2 = MagicMock()
        mock_mgr2.filter.return_value = mock_filter2
        select_lock = MagicMock()
        select_lock.get.return_value = fake_tx2
        mock_mgr2.select_for_update.return_value = select_lock

        # Also patch retrieve to return a valid session with amount_total and payment_intent
        from types import SimpleNamespace
        stripe_session = SimpleNamespace(
            id='cs_test_123',
            amount_total=int(fake_tx2.amount * 100),
            payment_intent='pi_test_123'
        )

        with patch.object(stripe.Webhook, 'construct_event', return_value=event):
            with patch.object(stripe.checkout.Session, 'retrieve', return_value=stripe_session):
                with patch('apps.billing.models.PaymentTransaction.objects', new=mock_mgr2):
                    with patch(
                        'apps.billing.payment_controller.PaymentService._activate_subscription'
                    ):
                        with override_settings(STRIPE_WEBHOOK_SECRET='whsec_test', STRIPE_SECRET_KEY='sk_test'):
                            url = reverse('stripe_webhook')
                            resp = self.client.post(
                                url,
                                data=payload,
                                content_type='application/json',
                                HTTP_STRIPE_SIGNATURE='t=1,v1=signature',
                            )
                            self.assertEqual(resp.status_code, 200)

                            self.assertEqual(fake_tx2.status, 'success')
                            self.assertTrue(
                                fake_tx2.gateway_payment_id in ('pi_test_123', 'cs_test_123')
                            )


@override_settings(
    RAZORPAY_KEY_ID='rzp_test',
    RAZORPAY_KEY_SECRET='test_razor_secret',
    ROOT_URLCONF='config.urls',
    SECURE_SSL_REDIRECT=False,
)
class VerifyRazorpayPaymentTests(TestCase):
    """VerifyRazorpayPaymentView signature + amount validation."""

    def setUp(self):
        from rest_framework.test import APIClient
        from apps.question_bank.models import Technology
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='payuser', email='pay@test.com', password='password',
        )
        self.client.force_authenticate(user=self.user)
        self.tech = Technology.objects.create(
            name='Docker', icon='box', price=499, is_active=True,
        )

    def _valid_signature(self, order_id, payment_id):
        message = f"{order_id}|{payment_id}"
        return hmac.new(
            b'test_razor_secret', message.encode(), hashlib.sha256,
        ).hexdigest()

    def test_rejects_amount_mismatch(self):
        from unittest.mock import patch, MagicMock
        order_id = 'order_abc'
        payment_id = 'pay_abc'
        url = reverse('razorpay_verify')

        mock_payment = {
            'order_id': order_id,
            'amount': 10000,  # ₹100 — technology price is ₹499
            'status': 'captured',
        }
        mock_client = MagicMock()
        mock_client.payment.fetch.return_value = mock_payment

        with patch('razorpay.Client', return_value=mock_client):
            resp = self.client.post(url, data={
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': self._valid_signature(order_id, payment_id),
                'technology_id': self.tech.id,
            }, content_type='application/json')

        self.assertEqual(resp.status_code, 400)
        self.assertIn('amount', resp.json().get('error', '').lower())

    def test_accepts_matching_payment(self):
        from unittest.mock import patch, MagicMock
        order_id = 'order_ok'
        payment_id = 'pay_ok'
        url = reverse('razorpay_verify')

        mock_payment = {
            'order_id': order_id,
            'amount': 49900,
            'status': 'captured',
        }
        mock_client = MagicMock()
        mock_client.payment.fetch.return_value = mock_payment

        with patch('razorpay.Client', return_value=mock_client):
            resp = self.client.post(url, data={
                'razorpay_order_id': order_id,
                'razorpay_payment_id': payment_id,
                'razorpay_signature': self._valid_signature(order_id, payment_id),
                'technology_id': self.tech.id,
            }, content_type='application/json')

        self.assertEqual(resp.status_code, 201)
        self.assertTrue(resp.json().get('payment_verified'))

