"""Organization self-service API for team members and owners."""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Max
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.tasks import send_notification_email

from .models import (
    Organization,
    OrganizationMember,
    OrganizationTechnologyGrant,
    PendingOrgInvite,
)

User = get_user_model()
logger = logging.getLogger(__name__)


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


def _pending_invites_payload(org):
    invites = PendingOrgInvite.objects.filter(
        organization=org,
        accepted_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).select_related("invited_by")
    return [
        {
            "id": str(inv.id),
            "email": inv.email,
            "role": inv.role,
            "invited_by": inv.invited_by.email if inv.invited_by else None,
            "expires_at": inv.expires_at.isoformat(),
            "created_at": inv.created_at.isoformat(),
        }
        for inv in invites
    ]


def _member_stats(user):
    from apps.billing.models import TechnologySubscription
    from apps.labs.models import LabSession
    from apps.progress.models import UserScenarioProgress

    progress_qs = UserScenarioProgress.objects.filter(user=user)
    completed = progress_qs.filter(completed=True).count()
    attempts = progress_qs.count()
    labs_started = LabSession.objects.filter(user=user).exclude(status="FAILED").count()
    last_lab = LabSession.objects.filter(user=user).aggregate(last=Max("started_at"))["last"]
    subs = TechnologySubscription.objects.filter(user=user, is_active=True).select_related("technology")
    return {
        "scenarios_completed": completed,
        "total_attempts": attempts,
        "labs_started": labs_started,
        "last_active": last_lab.isoformat() if last_lab else None,
        "subscriptions": [
            {
                "technology": s.technology.name,
                "slug": s.technology.slug,
                "expires_at": s.expires_at.isoformat() if s.expires_at else None,
                "payment_verified": s.payment_verified,
            }
            for s in subs
        ],
    }


def _send_org_invite_email(org, email, inviter, is_new_user, token=None):
    frontend = settings.FRONTEND_URL.rstrip("/")
    action_url = f"{frontend}/register?email={email}" if is_new_user else f"{frontend}/login"
    try:
        send_notification_email.delay(
            subject=f"You've been invited to join {org.name} on FixitLab",
            to_email=email,
            template="emails/org_invite.html",
            context={
                "org_name": org.name,
                "inviter_name": inviter.get_full_name() or inviter.username,
                "is_new_user": is_new_user,
                "action_url": action_url,
                "invite_token": token or "",
            },
        )
    except Exception as exc:
        logger.warning("Failed to queue org invite email to %s: %s", email, exc)


def _send_member_added_email(org, user, inviter):
    frontend = settings.FRONTEND_URL.rstrip("/")
    try:
        send_notification_email.delay(
            subject=f"You've joined {org.name} on FixitLab",
            to_email=user.email,
            template="emails/org_member_added.html",
            context={
                "org_name": org.name,
                "inviter_name": inviter.get_full_name() or inviter.username,
                "team_url": f"{frontend}/team",
            },
        )
    except Exception as exc:
        logger.warning("Failed to queue member-added email to %s: %s", user.email, exc)


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
                **(
                    _member_stats(m.user)
                    if member.role in ("owner", "admin")
                    else {}
                ),
            }
            for m in members
        ]
        if member.role in ("owner", "admin"):
            payload["pending_invites"] = _pending_invites_payload(org)
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

        pending_count = PendingOrgInvite.objects.filter(
            organization=org, accepted_at__isnull=True, expires_at__gt=timezone.now(),
        ).count()
        if org.member_count + pending_count >= org.seat_limit:
            return Response({"error": "Seat limit reached. Contact support to increase seats."}, status=400)

        try:
            user = User.objects.get(email__iexact=email)
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
            _send_org_invite_email(org, email, request.user, is_new_user=True, token=token)
            return Response(
                {
                    "message": f"Invite sent to {email}. They can register with this email to join {org.name}.",
                    "pending_invite": True,
                },
                status=201,
            )

        if OrganizationMember.objects.filter(organization=org, user=user).exists():
            return Response({"error": "User is already a member."}, status=400)

        OrganizationMember.objects.create(
            organization=org, user=user, role=role, invited_email=email
        )
        _send_member_added_email(org, user, request.user)
        return Response({"message": f"{email} added to {org.name}."}, status=201)


class OrganizationSettingsView(APIView):
    """PATCH /api/org/<slug>/settings/ — update branding and webhook (owner only)."""
    permission_classes = [IsAuthenticated]

    ALLOWED = ("webhook_url", "webhook_secret", "logo_url", "primary_color", "custom_domain")

    def patch(self, request, slug):
        try:
            org = Organization.objects.get(slug=slug, is_active=True)
            member = OrganizationMember.objects.get(organization=org, user=request.user)
        except (Organization.DoesNotExist, OrganizationMember.DoesNotExist):
            return Response({"error": "Not found or access denied."}, status=404)

        if member.role != "owner":
            return Response({"error": "Only the owner can change org settings."}, status=403)

        update_fields = []
        for field in self.ALLOWED:
            if field in request.data:
                setattr(org, field, request.data[field] or "")
                update_fields.append(field)

        if update_fields:
            org.save(update_fields=update_fields)

        return Response({
            "message": "Settings updated.",
            "webhook_url": org.webhook_url,
            "logo_url": org.logo_url,
            "primary_color": org.primary_color,
            "custom_domain": org.custom_domain,
        })


class OrganizationMemberDetailView(APIView):
    """Per-member analytics for owners/admins."""
    permission_classes = [IsAuthenticated]

    def get(self, request, slug, user_id):
        try:
            org = Organization.objects.get(slug=slug, is_active=True)
            viewer = OrganizationMember.objects.get(organization=org, user=request.user)
            target = OrganizationMember.objects.select_related("user").get(
                organization=org, user_id=user_id,
            )
        except (Organization.DoesNotExist, OrganizationMember.DoesNotExist):
            return Response({"error": "Not found"}, status=404)
        if viewer.role not in ("owner", "admin"):
            return Response({"error": "Owners/admins only"}, status=403)

        stats = _member_stats(target.user)
        return Response({
            "id": target.user_id,
            "email": target.user.email,
            "username": target.user.username,
            "role": target.role,
            "joined_at": target.joined_at.isoformat(),
            "invited_email": target.invited_email or target.user.email,
            **stats,
        })


class OrganizationMemberRemoveView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, slug, user_id):
        try:
            org = Organization.objects.get(slug=slug, is_active=True)
            actor = OrganizationMember.objects.get(organization=org, user=request.user)
            target = OrganizationMember.objects.get(organization=org, user_id=user_id)
        except (Organization.DoesNotExist, OrganizationMember.DoesNotExist):
            return Response({"error": "Not found"}, status=404)

        if actor.role not in ("owner", "admin"):
            return Response({"error": "Only owners and admins can remove members."}, status=403)
        if target.role == "owner":
            return Response({"error": "Cannot remove the organization owner."}, status=400)
        if actor.role == "admin" and target.role == "admin":
            return Response({"error": "Admins cannot remove other admins."}, status=403)
        if target.user_id == request.user.id and actor.role != "owner":
            return Response({"error": "Use leave team or ask the owner."}, status=400)

        target.delete()
        return Response({"message": "Member removed."})


class OrganizationInviteCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, slug, invite_id):
        try:
            org = Organization.objects.get(slug=slug, is_active=True)
            actor = OrganizationMember.objects.get(organization=org, user=request.user)
            invite = PendingOrgInvite.objects.get(
                id=invite_id, organization=org, accepted_at__isnull=True,
            )
        except (Organization.DoesNotExist, OrganizationMember.DoesNotExist, PendingOrgInvite.DoesNotExist):
            return Response({"error": "Invite not found"}, status=404)

        if actor.role not in ("owner", "admin"):
            return Response({"error": "Owners/admins only"}, status=403)

        invite.delete()
        return Response({"message": "Invite cancelled."})


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
            stats = _member_stats(m.user)
            by_member.append({
                "id": m.user_id,
                "email": m.user.email,
                "username": m.user.username,
                "role": m.role,
                "joined_at": m.joined_at.isoformat(),
                **stats,
            })

        pending = _pending_invites_payload(org)

        return Response({
            "organization": org.name,
            "seat_limit": org.seat_limit,
            "member_count": org.member_count,
            "pending_invite_count": len(pending),
            "total_completions": progress.count(),
            "total_labs": labs.count(),
            "members": by_member,
            "pending_invites": pending,
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
