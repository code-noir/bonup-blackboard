from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.http import Http404
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied
from rest_framework.test import APIClient

from backend.api.tests.helpers import authed_client, make_user
from backend.community.models import Community, CommunityJoinRequest, CommunityMembership, Friendship
from backend.community.permissions import (
    community_resource_or_404,
    get_active_membership,
    require_community_role,
)
from backend.community.services import create_community


class CommunityFoundationTests(TestCase):
    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.charlie = make_user("charlie", "charlie@example.com")
        Friendship.objects.create(
            user_a=self.alice,
            user_b=self.bob,
            requester=self.alice,
            recipient=self.bob,
            status=Friendship.Status.ACCEPTED,
        )
        Friendship.objects.create(
            user_a=self.alice,
            user_b=self.charlie,
            requester=self.alice,
            recipient=self.charlie,
            status=Friendship.Status.ACCEPTED,
        )
        Friendship.objects.create(
            user_a=self.bob,
            user_b=self.charlie,
            requester=self.bob,
            recipient=self.charlie,
            status=Friendship.Status.ACCEPTED,
        )

    def create_community(self, owner=None, name="Private Community"):
        return create_community(owner=owner or self.alice, name=name)

    def test_creator_becomes_active_owner(self):
        community = self.create_community()

        membership = CommunityMembership.objects.get(
            community=community,
            user=self.alice,
        )

        self.assertEqual(community.owner_id, self.alice.id)
        self.assertEqual(membership.role, CommunityMembership.Role.OWNER)
        self.assertEqual(membership.status, CommunityMembership.Status.ACTIVE)

    def test_community_and_owner_membership_are_atomic(self):
        with patch(
            "backend.community.services.CommunityMembership.objects.create",
            side_effect=RuntimeError("membership write failed"),
        ):
            with self.assertRaises(RuntimeError):
                self.create_community()

        self.assertEqual(Community.objects.count(), 0)
        self.assertEqual(CommunityMembership.objects.count(), 0)

    def test_duplicate_membership_is_rejected(self):
        community = self.create_community()

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CommunityMembership.objects.create(
                    community=community,
                    user=self.alice,
                    role=CommunityMembership.Role.MEMBER,
                    status=CommunityMembership.Status.ACTIVE,
                )

    def test_active_member_can_retrieve_community(self):
        community = self.create_community()
        CommunityMembership.objects.create(
            community=community,
            user=self.bob,
            role=CommunityMembership.Role.MEMBER,
            status=CommunityMembership.Status.ACTIVE,
        )

        response = authed_client(self.bob).get(f"/api/communities/{community.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], str(community.id))

    def test_owner_can_update_identity_without_replacing_community(self):
        community = self.create_community(name="Original name")
        original_id = community.id
        original_owner_id = community.owner_id
        original_private = community.is_private
        original_discoverable = community.is_discoverable
        CommunityMembership.objects.create(
            community=community,
            user=self.bob,
            role=CommunityMembership.Role.MEMBER,
            status=CommunityMembership.Status.ACTIVE,
        )
        CommunityJoinRequest.objects.create(community=community, user=self.charlie)

        response = authed_client(self.alice).patch(
            f"/api/communities/{community.id}/",
            {"name": "  Updated name  ", "description": "Updated description."},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        community.refresh_from_db()
        self.assertEqual(community.id, original_id)
        self.assertEqual(community.owner_id, original_owner_id)
        self.assertEqual(community.name, "Updated name")
        self.assertEqual(community.description, "Updated description.")
        self.assertEqual(community.is_private, original_private)
        self.assertEqual(community.is_discoverable, original_discoverable)
        self.assertTrue(
            CommunityMembership.objects.filter(
                community=community,
                user=self.bob,
                status=CommunityMembership.Status.ACTIVE,
            ).exists()
        )
        self.assertTrue(CommunityJoinRequest.objects.filter(community=community, user=self.charlie).exists())

    def test_admin_cannot_update_identity(self):
        community = self.create_community()
        CommunityMembership.objects.create(
            community=community,
            user=self.bob,
            role=CommunityMembership.Role.ADMIN,
            status=CommunityMembership.Status.ACTIVE,
        )

        response = authed_client(self.bob).patch(
            f"/api/communities/{community.id}/",
            {"name": "Admin rename"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        community.refresh_from_db()
        self.assertEqual(community.name, "Private Community")

    def test_member_cannot_update_identity(self):
        community = self.create_community()
        CommunityMembership.objects.create(
            community=community,
            user=self.bob,
            role=CommunityMembership.Role.MEMBER,
            status=CommunityMembership.Status.ACTIVE,
        )

        response = authed_client(self.bob).patch(
            f"/api/communities/{community.id}/",
            {"name": "Member rename"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        community.refresh_from_db()
        self.assertEqual(community.name, "Private Community")

    def test_non_member_cannot_update_identity(self):
        community = self.create_community()

        response = authed_client(self.bob).patch(
            f"/api/communities/{community.id}/",
            {"name": "Unauthorized rename"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        community.refresh_from_db()
        self.assertEqual(community.name, "Private Community")

    def test_owner_cannot_update_another_community(self):
        community_a = self.create_community(name="Community A")
        community_b = self.create_community(owner=self.bob, name="Community B")

        response = authed_client(self.alice).patch(
            f"/api/communities/{community_b.id}/",
            {"name": "Cross-community rename"},
            format="json",
        )

        self.assertEqual(response.status_code, 404)
        community_b.refresh_from_db()
        self.assertEqual(community_b.name, "Community B")
        self.assertNotEqual(community_a.id, community_b.id)

    def test_owner_identity_update_rejects_blank_name_without_mutation(self):
        community = self.create_community(name="Stable name")

        response = authed_client(self.alice).patch(
            f"/api/communities/{community.id}/",
            {"name": "   ", "description": "Should not save"},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        community.refresh_from_db()
        self.assertEqual(community.name, "Stable name")
        self.assertEqual(community.description, "")

    def test_active_member_can_retrieve_workspace_members(self):
        community = self.create_community()
        CommunityMembership.objects.create(
            community=community,
            user=self.bob,
            role=CommunityMembership.Role.ADMIN,
            status=CommunityMembership.Status.ACTIVE,
        )

        response = authed_client(self.bob).get(f"/api/communities/{community.id}/members/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["current_member_role"], CommunityMembership.Role.ADMIN)
        self.assertEqual(response.data["member_count"], 2)
        self.assertEqual(
            {member["role"] for member in response.data["members"]},
            {CommunityMembership.Role.OWNER, CommunityMembership.Role.ADMIN},
        )

    def test_non_member_cannot_retrieve_private_community(self):
        community = self.create_community()

        response = authed_client(self.bob).get(f"/api/communities/{community.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertNotIn("Private Community", response.content.decode())

    def test_non_member_cannot_retrieve_workspace_members(self):
        community = self.create_community()

        response = authed_client(self.bob).get(f"/api/communities/{community.id}/members/")

        self.assertEqual(response.status_code, 404)

    def test_member_of_community_a_cannot_retrieve_community_b(self):
        community_a = self.create_community(name="Community A")
        community_b = self.create_community(owner=self.bob, name="Community B")

        response = authed_client(self.alice).get(f"/api/communities/{community_b.id}/")

        self.assertEqual(response.status_code, 404)
        self.assertNotEqual(str(community_a.id), str(community_b.id))

    def test_removed_member_cannot_retrieve_community(self):
        community = self.create_community()
        membership = CommunityMembership.objects.create(
            community=community,
            user=self.bob,
            role=CommunityMembership.Role.MEMBER,
            status=CommunityMembership.Status.REMOVED,
        )

        response = authed_client(self.bob).get(f"/api/communities/{community.id}/")
        members_response = authed_client(self.bob).get(f"/api/communities/{community.id}/members/")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(members_response.status_code, 404)
        self.assertIsNone(get_active_membership(self.bob, community.id))
        self.assertEqual(membership.status, CommunityMembership.Status.REMOVED)

    def test_list_contains_only_active_memberships(self):
        active_owned = self.create_community(name="Owned")
        active_member = self.create_community(owner=self.bob, name="Active Member")
        removed_member = self.create_community(owner=self.charlie, name="Removed Member")
        CommunityMembership.objects.create(
            community=active_member,
            user=self.alice,
            role=CommunityMembership.Role.MEMBER,
            status=CommunityMembership.Status.ACTIVE,
        )
        CommunityMembership.objects.create(
            community=removed_member,
            user=self.alice,
            role=CommunityMembership.Role.MEMBER,
            status=CommunityMembership.Status.REMOVED,
        )

        response = authed_client(self.alice).get("/api/communities/")

        self.assertEqual(response.status_code, 200)
        listed_ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(listed_ids, {str(active_owned.id), str(active_member.id)})

    def test_caller_cannot_forge_owner_identity(self):
        response = authed_client(self.alice).post(
            "/api/communities/",
            {
                "name": "Owned by Alice",
                "owner": self.bob.id,
                "owner_id": self.bob.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        community = Community.objects.get(id=response.data["id"])
        self.assertEqual(community.owner_id, self.alice.id)
        self.assertTrue(
            CommunityMembership.objects.filter(
                community=community,
                user=self.alice,
                role=CommunityMembership.Role.OWNER,
                status=CommunityMembership.Status.ACTIVE,
            ).exists()
        )
        self.assertFalse(CommunityMembership.objects.filter(community=community, user=self.bob).exists())

    def test_role_helper_accepts_correct_role(self):
        community = self.create_community()

        membership = require_community_role(
            self.alice,
            community.id,
            [CommunityMembership.Role.OWNER, CommunityMembership.Role.ADMIN],
        )

        self.assertEqual(membership.role, CommunityMembership.Role.OWNER)

    def test_role_helper_rejects_insufficient_role(self):
        community = self.create_community()

        with self.assertRaises(PermissionDenied):
            require_community_role(self.alice, community.id, [CommunityMembership.Role.ADMIN])

    def test_unauthenticated_access_is_denied(self):
        client = APIClient()

        list_response = client.get("/api/communities/")
        create_response = client.post("/api/communities/", {"name": "No access"}, format="json")

        self.assertEqual(list_response.status_code, 401)
        self.assertEqual(create_response.status_code, 401)

    def test_community_resource_helper_rejects_mismatched_community_id(self):
        community = self.create_community()
        other_community = self.create_community(owner=self.bob, name="Other")

        with self.assertRaises(Http404):
            community_resource_or_404(community.id, other_community.id)

        membership = CommunityMembership.objects.get(community=community, user=self.alice)
        with self.assertRaises(Http404):
            community_resource_or_404(
                membership.id,
                other_community.id,
                resource_model=CommunityMembership,
            )
