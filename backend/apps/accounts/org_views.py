"""Organization self-service API for team members and owners."""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Max
from django.utils import timezone
from django.utils.text import slugify
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.notifications.tasks import send_notification_email

from .url_safety import UnsafeURLError, validate_outbound_url

from .models import (
    Organization,
    OrganizationMember,
    OrganizationTechnologyGrant,
    PendingOrgInvite,
)

User = get_user_model()
logger = logging.getLogger(__name__)

# Plan codes that include team/organization seats. The seat checkout flow uses
# the "enterprise" Plan, and Contact-Sales deals are marked "won".
TEAM_PLAN_CODES = ("enterprise",)


def team_eligibility(user) -> dict:
    """Decide whether ``user`` may create a team and how many seats they get.

    A user qualifies for self-service team creation when ANY of the following
    holds (most→least privileged):

      * staff / superuser (platform operators);
      * an admin-granted complimentary access flag;
      * an active platform Subscription on a team/enterprise plan;
      * a "won" Contact-Sales inquiry tied to their email (negotiated team deal);
      * they already own/administer at least one organization (can spin up more).

    Returns a dict ``{eligible, reason, seat_limit, owned_count}`` that both the
    create endpoint and the "My Teams" listing use, so the gating rule lives in
    exactly one place.
    """
    default_seats = int(getattr(settings, "DEFAULT_TEAM_SEATS", 10) or 10)

    if user.is_staff or user.is_superuser:
        return {"eligible": True, "reason": "staff", "seat_limit": default_seats}

    # Admin-granted complimentary access (treated as full access elsewhere).
    try:
        from apps.billing.subscription_utils import user_has_complimentary_access

        if user_has_complimentary_access(user):
            return {"eligible": True, "reason": "complimentary", "seat_limit": default_seats}
    except Exception:
        pass

    # Already owns/admins an org → allowed to create additional teams.
    owned = OrganizationMember.objects.filter(
        user=user, role__in=("owner", "admin"), organization__is_active=True,
    ).count()
    if owned:
        return {"eligible": True, "reason": "existing_owner", "seat_limit": default_seats, "owned_count": owned}

    # Active team/enterprise platform subscription.
    try:
        from apps.billing.models import Subscription

        sub = (
            Subscription.objects.filter(user=user, is_active=True)
            .select_related("plan")
            .first()
        )
        if sub and sub.plan and sub.plan.code in TEAM_PLAN_CODES:
            if not sub.expires_at or sub.expires_at > timezone.now():
                return {"eligible": True, "reason": "team_plan", "seat_limit": default_seats}
    except Exception:
        pass

    # Won Contact-Sales deal matching the user's email.
    try:
        from apps.billing.models import SalesInquiry

        if user.email and SalesInquiry.objects.filter(
            work_email__iexact=user.email, status="won",
        ).exists():
            return {"eligible": True, "reason": "sales_deal", "seat_limit": default_seats}
    except Exception:
        pass

    return {
        "eligible": False,
        "reason": "no_team_plan",
        "seat_limit": 0,
        "owned_count": owned,
    }


def _unique_org_slug(name: str) -> str:
    """Slugify ``name`` and guarantee uniqueness against existing orgs."""
    base = slugify(name)[:60] or f"team-{secrets.token_hex(3)}"
    slug = base
    i = 2
    while Organization.objects.filter(slug=slug).exists():
        suffix = f"-{i}"
        slug = f"{base[: 60 - len(suffix)]}{suffix}"
        i += 1
    return slug


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
    # Carry the invite token in the link (audit Z2-2). It was minted, stored and
    # passed to the template, but the action URL omitted it and the template never
    # rendered it — so the token could not reach the invitee, and redemption had
    # nothing to match on but the email address.
    if is_new_user:
        action_url = f"{frontend}/register?email={email}"
        if token:
            action_url += f"&invite_token={token}"
    else:
        action_url = f"{frontend}/login"
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
        eligibility = team_eligibility(request.user)
        return Response({
            "organizations": data,
            # Frontend gating: whether to surface the "Create a team" flow.
            "can_create_team": eligibility["eligible"],
            "create_team_reason": eligibility["reason"],
            "default_seat_limit": eligibility["seat_limit"],
        })


class CreateOrganizationView(APIView):
    """POST /api/org/create/ — self-service team creation (subscription-gated).

    The authenticated user becomes the org ``owner``. Only users whose
    subscription/plan qualifies (see ``team_eligibility``) may create a team;
    seat limit is derived from their entitlement.
    """

    permission_classes = [IsAuthenticated]

    MAX_NAME_LEN = 200

    def post(self, request):
        eligibility = team_eligibility(request.user)
        if not eligibility["eligible"]:
            return Response(
                {
                    "error": "A team or enterprise plan is required to create a team. "
                    "Upgrade your plan or contact sales to get started.",
                    "error_code": "team_plan_required",
                },
                status=403,
            )

        name = (request.data.get("name") or "").strip()
        if not name:
            return Response({"error": "Team name is required."}, status=400)
        if len(name) > self.MAX_NAME_LEN:
            name = name[: self.MAX_NAME_LEN]

        billing_email = (request.data.get("billing_email") or request.user.email or "").strip().lower()

        # Allow caller to request fewer seats than entitled, never more.
        requested_seats = request.data.get("seat_limit")
        seat_limit = eligibility["seat_limit"]
        try:
            if requested_seats is not None:
                seat_limit = min(int(requested_seats), eligibility["seat_limit"])
        except (TypeError, ValueError):
            pass
        seat_limit = max(seat_limit, 1)

        with transaction.atomic():
            org = Organization.objects.create(
                name=name,
                slug=_unique_org_slug(name),
                owner=request.user,
                seat_limit=seat_limit,
                billing_email=billing_email,
            )
            membership = OrganizationMember.objects.create(
                organization=org,
                user=request.user,
                role="owner",
                invited_email=request.user.email or "",
            )

        logger.info(
            "Organization '%s' (%s) created by %s [reason=%s, seats=%s]",
            org.name, org.slug, request.user.email, eligibility["reason"], seat_limit,
        )

        payload = _org_payload(org, membership)
        payload["members"] = [
            {
                "id": request.user.id,
                "email": request.user.email,
                "username": request.user.username,
                "role": "owner",
                "joined_at": membership.joined_at.isoformat(),
            }
        ]
        payload["pending_invites"] = []
        return Response(payload, status=201)


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

    def delete(self, request, slug):
        """Permanently delete the team (owner only).

        Cascades remove memberships, pending invites and technology grants
        (all FK on_delete=CASCADE to Organization).
        """
        org, member = self._membership(request.user, slug)
        if not org or not member:
            return Response({"error": "Organization not found or access denied."}, status=404)
        if member.role != "owner":
            return Response({"error": "Only the owner can delete the team."}, status=403)

        name = org.name
        org.delete()
        logger.info("Organization '%s' (%s) deleted by owner %s.", name, slug, request.user.email)
        return Response({"message": f"Team {name} deleted."})


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
            if field not in request.data:
                continue
            value = request.data[field] or ""
            # SSRF guard. save(update_fields=...) skips full_clean(), so URLField
            # validation never ran here — and the server POSTs to webhook_url
            # synchronously from the lab-completion path. An org owner could aim
            # it at cloud instance metadata, Vault, or Postgres and trigger it by
            # finishing a lab. Resolve and reject non-public targets before store.
            if field == "webhook_url":
                try:
                    value = validate_outbound_url(value)
                except UnsafeURLError as exc:
                    logger.warning(
                        "Rejected unsafe org webhook_url for org=%s user=%s: %s",
                        org.slug, request.user.id, exc,
                    )
                    return Response(
                        {"error": f"Invalid webhook URL: {exc}"},
                        status=400,
                    )
            setattr(org, field, value)
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
            # Non-owners leaving should use the self-service leave endpoint; the
            # owner never reaches here because their own role is "owner" (blocked
            # above by the target.role == "owner" guard).
            return Response({"error": "Use leave team or ask the owner."}, status=400)

        target.delete()
        return Response({"message": "Member removed."})


class OrganizationLeaveView(APIView):
    """DELETE /api/org/<slug>/leave/ — the authenticated member leaves the team.

    Any member (member/admin) may leave on their own. The owner cannot leave
    while owning the team (they must transfer ownership or delete the team);
    this also enforces the last-owner safeguard since ``Organization.owner`` is
    a single field, so there is always exactly one owner membership.
    """

    permission_classes = [IsAuthenticated]

    def delete(self, request, slug):
        try:
            org = Organization.objects.get(slug=slug, is_active=True)
            membership = OrganizationMember.objects.get(organization=org, user=request.user)
        except (Organization.DoesNotExist, OrganizationMember.DoesNotExist):
            return Response({"error": "Not found"}, status=404)

        if membership.role == "owner":
            return Response(
                {
                    "error": "The owner cannot leave the team. Transfer ownership "
                    "or delete the team instead.",
                },
                status=400,
            )

        membership.delete()
        logger.info("User %s left organization '%s' (%s).", request.user.email, org.name, org.slug)
        return Response({"message": f"You have left {org.name}."})


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

        # PRODUCTION_AUDIT FIN-03: a valid handshake signature can exist for a
        # payment that is only `authorized`/`created`/`failed`. Confirm with the
        # gateway that the payment is actually CAPTURED for this order at the
        # expected amount BEFORE granting any seats — consistent with the
        # technology-subscription verify path.
        from apps.billing.razorpay_fulfillment import verify_razorpay_payment_captured

        try:
            expected_amount_inr = int(notes.get("amount_inr") or 0)
        except (TypeError, ValueError):
            expected_amount_inr = 0
        if expected_amount_inr <= 0:
            # Fallback to the order's own amount (paise → INR) so this still works
            # for any order created before amount_inr was added to notes.
            try:
                expected_amount_inr = int(order.get("amount", 0)) // 100
            except (TypeError, ValueError):
                expected_amount_inr = 0

        if not verify_razorpay_payment_captured(order_id, payment_id, expected_amount_inr):
            return Response(
                {"error": "Payment not captured. Seats were not granted."},
                status=400,
            )

        from django.db import transaction as db_transaction

        from apps.billing.extended_views import fulfill_org_razorpay_order
        from apps.billing.models import ProcessedWebhookEvent

        # Idempotent + race-safe under a duplicate verify / double-click.
        #
        # This used to dedup on a Redis key alone (`cache.add`, 24h TTL) — the same
        # pattern audit Z1-4 replaced for the Stripe and Razorpay webhooks, because a
        # Redis flush or eviction reopens the double-fulfilment window and a replay
        # re-grants seats. ProcessedWebhookEvent is the durable, authoritative gate;
        # creating the row and fulfilling inside one transaction means a replay finds
        # the row (created=False) and skips fulfilment entirely, while a crash
        # mid-fulfilment rolls the row back so a genuine retry still works.
        already = {
            "verified": True,
            "organization": org.name,
            "seats": org.seat_limit,
            "already_fulfilled": True,
        }
        with db_transaction.atomic():
            _, created = ProcessedWebhookEvent.objects.get_or_create(
                event_id=f"org_seats:{payment_id}",
                defaults={"provider": "razorpay"},
            )
            if not created:
                logger.info("Duplicate org fulfilment ignored (db): %s", payment_id)
                return Response(already)
            fulfill_org_razorpay_order(notes, payment_id=payment_id, order_id=order_id)
        return Response({"verified": True, "organization": org.name, "seats": org.seat_limit})
