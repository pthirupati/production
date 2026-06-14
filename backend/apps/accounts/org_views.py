"""Organization self-service API for team members and owners."""

from django.contrib.auth import get_user_model
from django.utils.text import slugify
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Organization, OrganizationMember, OrganizationTechnologyGrant

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
            return Response(
                {
                    "error": (
                        f"No FixitLab account found for {email}. "
                        "Ask them to register first, then invite again."
                    ),
                    "error_code": "user_not_registered",
                },
                status=400,
            )

        if OrganizationMember.objects.filter(organization=org, user=user).exists():
            return Response({"error": "User is already a member."}, status=400)

        OrganizationMember.objects.create(
            organization=org, user=user, role=role, invited_email=email
        )
        return Response({"message": f"{email} added to {org.name}."}, status=201)
