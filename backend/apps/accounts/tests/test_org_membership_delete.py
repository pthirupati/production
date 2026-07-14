"""Tests for team leave / member-remove / team-delete flows.

Covers the self-service DELETE endpoints added for the "My Team" page:

  * a member leaving on their own (self-leave);
  * an admin/owner removing another member;
  * a non-admin being forbidden (403) from removing others;
  * the owner deleting the whole team (cascade).
"""

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from apps.accounts.models import Organization, OrganizationMember

User = get_user_model()


@override_settings(JWT_SESSION_ENFORCEMENT=False)
class OrgMembershipDeleteTest(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="owner", email="owner@example.com", password="pw-owner-123!"
        )
        self.admin = User.objects.create_user(
            username="admin", email="admin@example.com", password="pw-admin-123!"
        )
        self.member = User.objects.create_user(
            username="member", email="member@example.com", password="pw-member-123!"
        )
        self.other_member = User.objects.create_user(
            username="member2", email="member2@example.com", password="pw-member2-123!"
        )

        self.org = Organization.objects.create(
            name="Acme Engineering", slug="acme-eng", owner=self.owner, seat_limit=10
        )
        OrganizationMember.objects.create(organization=self.org, user=self.owner, role="owner")
        OrganizationMember.objects.create(organization=self.org, user=self.admin, role="admin")
        OrganizationMember.objects.create(organization=self.org, user=self.member, role="member")
        OrganizationMember.objects.create(organization=self.org, user=self.other_member, role="member")

    # ---- self-leave ----------------------------------------------------

    def test_member_can_leave_team(self):
        self.client.force_authenticate(self.member)
        resp = self.client.delete(f"/api/org/{self.org.slug}/leave/")
        assert resp.status_code == 200, (resp.status_code, dict(resp.data))
        assert not OrganizationMember.objects.filter(
            organization=self.org, user=self.member
        ).exists()

    def test_owner_cannot_leave_team(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.delete(f"/api/org/{self.org.slug}/leave/")
        assert resp.status_code == 400, (resp.status_code, dict(resp.data))
        # Owner membership must remain intact (last-owner safeguard).
        assert OrganizationMember.objects.filter(
            organization=self.org, user=self.owner, role="owner"
        ).exists()

    def test_leave_requires_membership(self):
        stranger = User.objects.create_user(
            username="stranger", email="stranger@example.com", password="pw-stranger-123!"
        )
        self.client.force_authenticate(stranger)
        resp = self.client.delete(f"/api/org/{self.org.slug}/leave/")
        assert resp.status_code == 404, (resp.status_code, dict(resp.data))

    # ---- admin removes member -----------------------------------------

    def test_admin_removes_member(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(
            f"/api/org/{self.org.slug}/members/{self.member.id}/remove/"
        )
        assert resp.status_code == 200, (resp.status_code, dict(resp.data))
        assert not OrganizationMember.objects.filter(
            organization=self.org, user=self.member
        ).exists()

    def test_non_admin_cannot_remove_member(self):
        self.client.force_authenticate(self.member)
        resp = self.client.delete(
            f"/api/org/{self.org.slug}/members/{self.other_member.id}/remove/"
        )
        assert resp.status_code == 403, (resp.status_code, dict(resp.data))
        # Target must still be a member.
        assert OrganizationMember.objects.filter(
            organization=self.org, user=self.other_member
        ).exists()

    def test_cannot_remove_owner(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(
            f"/api/org/{self.org.slug}/members/{self.owner.id}/remove/"
        )
        assert resp.status_code == 400, (resp.status_code, dict(resp.data))
        assert OrganizationMember.objects.filter(
            organization=self.org, user=self.owner, role="owner"
        ).exists()

    # ---- owner deletes team -------------------------------------------

    def test_owner_deletes_team(self):
        self.client.force_authenticate(self.owner)
        resp = self.client.delete(f"/api/org/{self.org.slug}/")
        assert resp.status_code == 200, (resp.status_code, dict(resp.data))
        assert not Organization.objects.filter(slug="acme-eng").exists()
        # Memberships cascade away with the org.
        assert not OrganizationMember.objects.filter(organization_id=self.org.id).exists()

    def test_admin_cannot_delete_team(self):
        self.client.force_authenticate(self.admin)
        resp = self.client.delete(f"/api/org/{self.org.slug}/")
        assert resp.status_code == 403, (resp.status_code, dict(resp.data))
        assert Organization.objects.filter(slug="acme-eng").exists()

    def test_member_cannot_delete_team(self):
        self.client.force_authenticate(self.member)
        resp = self.client.delete(f"/api/org/{self.org.slug}/")
        assert resp.status_code == 403, (resp.status_code, dict(resp.data))
        assert Organization.objects.filter(slug="acme-eng").exists()
