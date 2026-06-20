"""
Teams / Org "Contact Sales" + custom-pricing flow.

Public endpoint:
  POST /api/billing/sales/inquiry/   (AllowAny, throttled)
    Saves a SalesInquiry and emails (a) the sales inbox and (b) the submitter
    a confirmation. Email failures are logged but never 500 the request.

Admin endpoints (staff only):
  GET   /api/admin/sales/                 list inquiries (optional ?status=)
  PATCH /api/admin/sales/<uuid:pk>/       update status and/or custom quote
"""
import logging

from django.conf import settings
from django.utils.html import strip_tags
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from common.throttles import StrictAnonRateThrottle
from apps.adminpanel.permissions import IsPlatformAdmin
from .models import SalesInquiry

logger = logging.getLogger(__name__)

# Reasonable upper bounds so a single field can't blow up the DB / emails.
_MAX_LEN = {
    "full_name": 150,
    "organization": 200,
    "work_email": 254,
    "company": 200,
    "phone": 50,
    "team_size": 50,
    "message": 5000,
}

VALID_STATUSES = {c[0] for c in SalesInquiry.STATUS_CHOICES}
VALID_CURRENCIES = {"USD", "INR", "EUR", "GBP", "AUD", "CAD", "SGD", "AED"}


def _clean(value, field):
    """Strip HTML/whitespace and clamp length."""
    text = strip_tags(str(value or "")).strip()
    return text[: _MAX_LEN.get(field, 255)]


def _inquiry_json(inq):
    return {
        "id": str(inq.id),
        "full_name": inq.full_name,
        "organization": inq.organization,
        "work_email": inq.work_email,
        "company": inq.company,
        "phone": inq.phone,
        "team_size": inq.team_size,
        "message": inq.message,
        "status": inq.status,
        "handled_by": inq.handled_by.username if inq.handled_by else None,
        "custom_quote_amount": (
            str(inq.custom_quote_amount) if inq.custom_quote_amount is not None else None
        ),
        "custom_quote_currency": inq.custom_quote_currency,
        "custom_quote_notes": inq.custom_quote_notes,
        "custom_quote_valid_until": (
            inq.custom_quote_valid_until.isoformat()
            if hasattr(inq.custom_quote_valid_until, "isoformat")
            else (inq.custom_quote_valid_until or None)
        ),
        "has_quote": inq.has_quote,
        "created_at": inq.created_at.isoformat(),
        "updated_at": inq.updated_at.isoformat(),
    }


def _send_inquiry_emails(inq):
    """
    Send the admin notification + submitter confirmation.

    Uses the configured mail backend via notifications.email.send_email, which
    already swallows delivery errors (returns False, never raises) and logs to
    EmailLog. We additionally wrap the whole thing so a missing template or any
    unexpected error can never bubble up into the request/response cycle.
    """
    try:
        from apps.notifications.email import send_email

        sales_inbox = getattr(settings, "SALES_INBOX", "fixitlab.admin@gmail.com")
        admin_url = f"{settings.FRONTEND_URL}/admin/sales"

        # 1) Notify the sales/admin inbox.
        send_email(
            subject=f"[FixitLab Sales] New inquiry from {inq.organization}",
            to_email=sales_inbox,
            template="emails/sales_inquiry_admin.html",
            context={
                "full_name": inq.full_name,
                "organization": inq.organization,
                "work_email": inq.work_email,
                "company": inq.company,
                "phone": inq.phone,
                "team_size": inq.team_size,
                "message": inq.message,
                "admin_url": admin_url,
            },
        )

        # 2) Confirmation to the submitter so they can reply over email.
        send_email(
            subject="We received your FixitLab Teams inquiry",
            to_email=inq.work_email,
            template="emails/sales_inquiry_confirmation.html",
            context={
                "full_name": inq.full_name,
                "organization": inq.organization,
                "team_size": inq.team_size,
                "sales_inbox": sales_inbox,
            },
        )
    except Exception as e:  # pragma: no cover - defensive; emails must never 500
        logger.error("Sales inquiry email dispatch failed: %s", e)


class SalesInquiryView(APIView):
    """Public Contact Sales submission. Must never 500."""

    permission_classes = [AllowAny]
    throttle_classes = [StrictAnonRateThrottle]

    def post(self, request):
        try:
            data = request.data if isinstance(request.data, dict) else {}

            full_name = _clean(data.get("full_name"), "full_name")
            organization = _clean(data.get("organization"), "organization")
            work_email = _clean(data.get("work_email"), "work_email")
            company = _clean(data.get("company"), "company")
            phone = _clean(data.get("phone"), "phone")
            team_size = _clean(data.get("team_size"), "team_size")
            message = _clean(data.get("message"), "message")

            # Required fields.
            if not full_name or not organization or not work_email:
                return Response(
                    {"error": "Full name, organization, and work email are required."},
                    status=400,
                )
            # Lightweight email sanity check.
            if "@" not in work_email or "." not in work_email.split("@")[-1]:
                return Response({"error": "Please provide a valid work email."}, status=400)

            inquiry = SalesInquiry.objects.create(
                full_name=full_name,
                organization=organization,
                work_email=work_email,
                company=company,
                phone=phone,
                team_size=team_size,
                message=message,
            )

            # Best-effort emails — never block or fail the save.
            _send_inquiry_emails(inquiry)

            return Response(
                {
                    "id": str(inquiry.id),
                    "message": "Thanks! Our team will email you shortly to discuss pricing.",
                },
                status=201,
            )
        except Exception as e:  # pragma: no cover - last-resort guard
            logger.error("SalesInquiryView failed: %s", e)
            # Never surface a 500 on the public endpoint.
            return Response(
                {"message": "Thanks! Our team will email you shortly."},
                status=202,
            )


class AdminSalesInquiriesView(APIView):
    """Staff-only list of sales inquiries."""

    permission_classes = [IsPlatformAdmin]

    def get(self, request):
        qs = SalesInquiry.objects.all()
        status_filter = (request.query_params.get("status") or "").strip()
        if status_filter and status_filter in VALID_STATUSES:
            qs = qs.filter(status=status_filter)

        inquiries = [_inquiry_json(i) for i in qs.select_related("handled_by")[:500]]
        counts = {s: 0 for s in VALID_STATUSES}
        for i in SalesInquiry.objects.values_list("status", flat=True):
            if i in counts:
                counts[i] += 1
        return Response({"inquiries": inquiries, "counts": counts})


class AdminSalesInquiryDetailView(APIView):
    """Staff-only: update status and/or set a custom quote."""

    permission_classes = [IsPlatformAdmin]

    def patch(self, request, pk):
        try:
            inquiry = SalesInquiry.objects.get(pk=pk)
        except (SalesInquiry.DoesNotExist, ValueError, Exception):
            return Response({"error": "Inquiry not found"}, status=404)

        data = request.data if isinstance(request.data, dict) else {}

        # Status.
        if "status" in data:
            new_status = (data.get("status") or "").strip()
            if new_status not in VALID_STATUSES:
                return Response({"error": "Invalid status."}, status=400)
            inquiry.status = new_status

        # Custom quote.
        if "custom_quote_amount" in data:
            raw = data.get("custom_quote_amount")
            if raw in (None, ""):
                inquiry.custom_quote_amount = None
            else:
                try:
                    amount = float(raw)
                except (TypeError, ValueError):
                    return Response({"error": "Quote amount must be a number."}, status=400)
                if amount < 0:
                    return Response({"error": "Quote amount cannot be negative."}, status=400)
                inquiry.custom_quote_amount = amount
                # Setting a quote implies the inquiry has been quoted.
                if inquiry.status in ("new", "contacted"):
                    inquiry.status = "quoted"

        if "custom_quote_currency" in data:
            currency = (data.get("custom_quote_currency") or "USD").strip().upper()[:3]
            if currency and currency not in VALID_CURRENCIES:
                return Response({"error": "Unsupported currency."}, status=400)
            inquiry.custom_quote_currency = currency or "USD"

        if "custom_quote_notes" in data:
            inquiry.custom_quote_notes = strip_tags(str(data.get("custom_quote_notes") or "")).strip()[:5000]

        if "custom_quote_valid_until" in data:
            inquiry.custom_quote_valid_until = data.get("custom_quote_valid_until") or None

        inquiry.handled_by = request.user
        inquiry.save()
        return Response(_inquiry_json(inquiry))
