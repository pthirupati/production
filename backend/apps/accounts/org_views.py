"""Organization self-service API for team members and owners."""

import secrets
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db.models import Count
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Organization,
    OrganizationMember,
    OrganizationTechnologyGrant,
    PendingOrgInvite,
)

User = get_user_model()


def _org_payload(org, membership=None):
    grants = OrganizationTechnologyGrant.objects.filter(
        organization=org, is_active=True
    ).select_related("technology")
    return {
        "id": str(org.id),
        "name": org.name,
        "slug": org.slug,
        "seat_limit": org.seat_limit,
        "member_count": org.member_count,
        "billing_email": org.billing_email,
        "role": membership.role if membership else None,
        "technologies": [
            {
                "id": g.technology_id,
                "name": g.technology.name,
                "slug": g.technology.slug,
                "expires_at": g.expires_at.isoformat() if g.expires_at else None,
            }
            for g in grants
            if g.is_valid_now()
        ],
    }


class MyOrganizationsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        memberships = (
            OrganizationMember.objects.filter(user=request.user, organization__is_active=True)
            .select_related("organization", "organization__owner")
        )
        data = [
            _org_payload(m.organization, m)
            for m in memberships
        ]
        return Response({"organizations": data})


class OrganizationDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _membership(self, user, slug):
        try:
            org = Organization.objects.get(slug=slug, is_active=True)
        except Organization.DoesNotExist:
            return None, None
        try:
            member = OrganizationMember.objects.get(organization=org, user=user)
        except OrganizationMember.DoesNotExist:
            return org, None
        return org, member

    def get(self, request, slug):
        org, member = self._membership(request.user, slug)
        if not org or not member:
            return Response({"error": "Organization not found or access denied."}, status=404)
        members = OrganizationMember.objects.filter(organization=org).select_related("user")
        payload = _org_payload(org, member)
        payload["members"] = [
            {
                "id": m.user_id,
                "email": m.user.email,
                "username": m.user.username,
                "role": m.role,
                "joined_at": m.joined_at.isoformat(),
            }
            for m in members
        ]
        return Response(payload)

    def post(self, request, slug):
        """Invite/add member by email (owner/admin only)."""
        org, member = self._membership(request.user, slug)
        if not org or not member:
            return Response({"error": "Organization not found or access denied."}, status=404)
        if member.role not in ("owner", "admin"):
            return Response({"error": "Only owners and admins can invite members."}, status=403)

        email = (request.data.get("email") or "").strip().lower()
        role = request.data.get("role", "member")
        if role not in ("member", "admin"):
            role = "member"
        if not email:
            return Response({"error": "Email is required."}, status=400)

        if org.member_count >= org.seat_limit:
            return Response({"error": "Seat limit reached. Contact support to increase seats."}, status=400)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            token = secrets.token_urlsafe(32)
            PendingOrgInvite.objects.update_or_create(
                organization=org,
                email=email,
                defaults={
                    "role": role,
                    "token": token,
                    "invited_by": request.user,
                    "expires_at": timezone.now() + timedelta(days=14),
                    "accepted_at": None,
                },
            )
            return Response(
                {
                    "message": f"Invite sent to {email}. They can register with this email to join {org.name}.",
                    "pending_invite": True,
                    "invite_token": token,
                },
                status=201,
            )

        if OrganizationMember.objects.filter(organization=org, user=user).exists():
            return Response({"error": "User is already a member."}, status=400)

        OrganizationMember.objects.create(
            organization=org, user=user, role=role, invited_email=email
        )
        return Response({"message": f"{email} added to {org.name}."}, status=201)


class OrganizationAnalyticsView(APIView):
    """Completion and lab stats for org owners/admins."""
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        from apps.labs.models import LabSession
        from apps.progress.models import UserScenarioProgress

        try:
            org = Organization.objects.get(slug=slug, is_active=True)
            member = OrganizationMember.objects.get(organization=org, user=request.user)
        except (Organization.DoesNotExist, OrganizationMember.DoesNotExist):
            return Response({"error": "Access denied"}, status=404)
        if member.role not in ("owner", "admin"):
            return Response({"error": "Owners/admins only"}, status=403)

        member_users = User.objects.filter(
            id__in=OrganizationMember.objects.filter(organization=org).values_list("user_id", flat=True),
        )
        progress = UserScenarioProgress.objects.filter(user__in=member_users, completed=True)
        labs = LabSession.objects.filter(user__in=member_users).exclude(status="FAILED")

        by_member = []
        for m in OrganizationMember.objects.filter(organization=org).select_related("user"):
            u = m.user
            completed = progress.filter(user=u).count()
            attempts = UserScenarioProgress.objects.filter(user=u).aggregate(
                total=Count("id"),
            )["total"]
            by_member.append({
                "email": u.email,
                "username": u.username,
                "role": m.role,
                "scenarios_completed": completed,
                "total_attempts": attempts or 0,
                "labs_started": labs.filter(user=u).count(),
            })

        return Response({
            "organization": org.name,
            "seat_limit": org.seat_limit,
            "member_count": org.member_count,
            "total_completions": progress.count(),
            "total_labs": labs.count(),
            "members": by_member,
        })


class OrganizationRazorpayVerifyView(APIView):
    """Verify org seat checkout after Razorpay payment."""
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        import hmac
        import hashlib
        from django.conf import settings as dj_settings

        order_id = request.data.get("razorpay_order_id")
        payment_id = request.data.get("razorpay_payment_id")
        signature = request.data.get("razorpay_signature")
        if not all([order_id, payment_id, signature]):
            return Response({"error": "Missing payment fields"}, status=400)

        try:
            org = Organization.objects.get(slug=slug, is_active=True)
            OrganizationMember.objects.get(organization=org, user=request.user, role__in=("owner", "admin"))
        except (Organization.DoesNotExist, OrganizationMember.DoesNotExist):
            return Response({"error": "Access denied"}, status=403)

        secret = dj_settings.RAZORPAY_KEY_SECRET
        if not secret:
            return Response({"error": "Gateway not configured"}, status=503)
        body = f"{order_id}|{payment_id}"
        expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return Response({"error": "Invalid signature"}, status=400)

        import razorpay
        client = razorpay.Client(auth=(dj_settings.RAZORPAY_KEY_ID, secret))
        order = client.order.fetch(order_id)
        notes = order.get("notes") or {}
        if notes.get("checkout_type") != "organization" or notes.get("org_slug") != slug:
            return Response({"error": "Order mismatch"}, status=400)

        from apps.billing.extended_views import fulfill_org_razorpay_order
        fulfill_org_razorpay_order(notes)
        return Response({"verified": True, "organization": org.name, "seats": org.seat_limit})
