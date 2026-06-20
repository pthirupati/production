"""
Tests for the Teams/Org "Contact Sales" flow.

Covers:
  - public POST /api/sales/inquiry/ saves the inquiry, attempts BOTH emails
    (admin notification + submitter confirmation), and returns 201
  - bad input → 400 (never 500)
  - the public endpoint never 500s even if email dispatch raises
  - admin can list inquiries and set a custom quote (status auto-advances)
  - non-admin / anonymous users are forbidden from the admin endpoints
"""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APITestCase

from apps.billing.models import SalesInquiry

User = get_user_model()

VALID_PAYLOAD = {
    "full_name": "Jane Doe",
    "organization": "Acme Inc.",
    "work_email": "jane@acme.com",
    "company": "Acme Holdings",
    "phone": "+1 555 010 1234",
    "team_size": "51–200",
    "message": "We'd like 80 seats for our SRE team.",
}


@override_settings(SKIP_EMAIL_TESTS=False, SALES_INBOX="sales@fixitlab.test")
class PublicSalesInquiryTests(APITestCase):
    url = "/api/sales/inquiry/"

    def setUp(self):
        mail.outbox = []

    def test_submit_saves_and_sends_two_emails(self):
        res = self.client.post(self.url, VALID_PAYLOAD, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        # Saved.
        self.assertEqual(SalesInquiry.objects.count(), 1)
        inq = SalesInquiry.objects.first()
        self.assertEqual(inq.organization, "Acme Inc.")
        self.assertEqual(inq.work_email, "jane@acme.com")
        self.assertEqual(inq.status, "new")

        # Two emails attempted: admin inbox + submitter confirmation.
        self.assertEqual(len(mail.outbox), 2)
        recipients = {r for m in mail.outbox for r in m.to}
        self.assertIn("sales@fixitlab.test", recipients)
        self.assertIn("jane@acme.com", recipients)

    def test_missing_required_fields_returns_400_not_500(self):
        res = self.client.post(
            self.url,
            {"full_name": "", "organization": "", "work_email": ""},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SalesInquiry.objects.count(), 0)

    def test_invalid_email_returns_400(self):
        payload = dict(VALID_PAYLOAD, work_email="not-an-email")
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(SalesInquiry.objects.count(), 0)

    def test_email_failure_does_not_500_and_still_saves(self):
        # Even if email dispatch blows up, the request must succeed and save.
        with patch(
            "apps.billing.sales_views._send_inquiry_emails",
            side_effect=RuntimeError("smtp down"),
        ):
            res = self.client.post(self.url, VALID_PAYLOAD, format="json")
        self.assertNotEqual(res.status_code, 500)
        self.assertIn(res.status_code, (201, 202))
        self.assertEqual(SalesInquiry.objects.count(), 1)


class AdminSalesInquiryTests(APITestCase):
    list_url = "/api/admin/sales/"

    def setUp(self):
        self.staff = User.objects.create_user(
            username="admin", email="admin@test.com", password="Admin123!", is_staff=True,
        )
        self.regular = User.objects.create_user(
            username="bob", email="bob@test.com", password="Pass123!", is_staff=False,
        )
        self.inq = SalesInquiry.objects.create(
            full_name="Jane Doe", organization="Acme Inc.", work_email="jane@acme.com",
        )

    def detail_url(self, pk):
        return f"/api/admin/sales/{pk}/"

    def test_non_admin_forbidden_from_list(self):
        self.client.force_authenticate(user=self.regular)
        res = self.client.get(self.list_url)
        self.assertIn(res.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED))

    def test_anonymous_forbidden_from_list(self):
        res = self.client.get(self.list_url)
        self.assertIn(res.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED))

    def test_non_admin_forbidden_from_patch(self):
        self.client.force_authenticate(user=self.regular)
        res = self.client.patch(self.detail_url(self.inq.id), {"status": "won"}, format="json")
        self.assertIn(res.status_code, (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED))
        self.inq.refresh_from_db()
        self.assertEqual(self.inq.status, "new")

    def test_admin_can_list(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.get(self.list_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res.json()["inquiries"]), 1)

    def test_admin_can_set_custom_quote(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.patch(
            self.detail_url(self.inq.id),
            {
                "custom_quote_amount": "4999.00",
                "custom_quote_currency": "USD",
                "custom_quote_notes": "80 seats, annual",
                "custom_quote_valid_until": "2026-12-31",
            },
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.inq.refresh_from_db()
        self.assertEqual(str(self.inq.custom_quote_amount), "4999.00")
        self.assertEqual(self.inq.custom_quote_currency, "USD")
        # Setting a quote auto-advances status to "quoted".
        self.assertEqual(self.inq.status, "quoted")
        # handled_by is recorded.
        self.assertEqual(self.inq.handled_by, self.staff)

    def test_admin_invalid_status_returns_400(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.patch(self.detail_url(self.inq.id), {"status": "bogus"}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_admin_invalid_quote_amount_returns_400(self):
        self.client.force_authenticate(user=self.staff)
        res = self.client.patch(
            self.detail_url(self.inq.id), {"custom_quote_amount": "abc"}, format="json"
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
