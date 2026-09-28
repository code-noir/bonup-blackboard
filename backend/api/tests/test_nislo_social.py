from django.test import TestCase
from rest_framework.test import APIClient

from backend.api.tests.helpers import authed_client, make_user
from backend.community.models import Community, CommunityJoinRequest, CommunityMembership, Friendship
from backend.community.services import create_community


class NisloSocialFoundationTests(TestCase):
    def setUp(self):
        self.alice = make_user("nislo-alice", "nislo-alice@example.com")
        self.bob = make_user("nislo-bob", "nislo-bob@example.com")
        self.charlie = make_user("nislo-charlie", "nislo-charlie@example.com")

    def make_friend(self, first, second, status=Friendship.Status.ACCEPTED):
        user_a, user_b = sorted([first, second], key=lambda user: user.pk)
        return Friendship.objects.create(
            user_a=user_a,
            user_b=user_b,
            requester=first,
            recipient=second,
            status=status,
        )

    def make_community(self, owner=None):
        owner = owner or self.alice
        friend = self.bob if owner != self.bob else self.alice
        if not Friendship.objects.filter(
            status=Friendship.Status.ACCEPTED,
        ).filter(user_a=owner, user_b=friend).exists() and not Friendship.objects.filter(
            status=Friendship.Status.ACCEPTED,
        ).filter(user_a=friend, user_b=owner).exists():
            self.make_friend(owner, friend)
        return create_community(owner=owner, name=f"{owner.username}'s Community")

    def test_self_friend_request_is_rejected(self):
        response = authed_client(self.alice).post(
            "/api/communities/friends/",
            {"bon_id": self.alice.bon_profile.bon_id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Friendship.objects.count(), 0)

    def test_friend_request_acceptance_is_visible_to_both_people(self):
        response = authed_client(self.alice).post(
            "/api/communities/friends/",
            {"bon_id": self.bob.bon_profile.bon_id},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        friendship_id = response.data["id"]
        incoming = authed_client(self.bob).get("/api/communities/friends/")
        self.assertEqual(len(incoming.data["incoming_requests"]), 1)

        accepted = authed_client(self.bob).post(
            f"/api/communities/friends/requests/{friendship_id}/accept/",
            {},
            format="json",
        )

        self.assertEqual(accepted.status_code, 200)
        self.assertEqual(accepted.data["status"], Friendship.Status.ACCEPTED)
        self.assertEqual(len(authed_client(self.alice).get("/api/communities/friends/").data["friends"]), 1)
        self.assertEqual(len(authed_client(self.bob).get("/api/communities/friends/").data["friends"]), 1)

    def test_reverse_pending_request_reuses_existing_relationship(self):
        first = authed_client(self.alice).post(
            "/api/communities/friends/",
            {"bon_id": self.bob.bon_profile.bon_id},
            format="json",
        )
        reverse = authed_client(self.bob).post(
            "/api/communities/friends/",
            {"bon_id": self.alice.bon_profile.bon_id},
            format="json",
        )

        self.assertEqual(first.status_code, 201)
        self.assertEqual(reverse.status_code, 200)
        self.assertEqual(reverse.data["id"], first.data["id"])
        self.assertEqual(Friendship.objects.count(), 1)
        self.assertEqual(Friendship.objects.get().requester_id, self.alice.id)

    def test_accepted_friendship_is_unique(self):
        friendship = self.make_friend(self.alice, self.bob)
        friendship.responded_at = friendship.created_at
        friendship.save(update_fields=["responded_at"])

        response = authed_client(self.bob).post(
            "/api/communities/friends/",
            {"bon_id": self.alice.bon_profile.bon_id},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Friendship.objects.filter(status=Friendship.Status.ACCEPTED).count(), 1)

    def test_community_creation_requires_an_accepted_friend(self):
        response = authed_client(self.alice).post(
            "/api/communities/",
            {"name": "Blocked Community"},
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Community.objects.count(), 0)

        self.make_friend(self.alice, self.bob)
        created = authed_client(self.alice).post(
            "/api/communities/",
            {"name": "Allowed Community"},
            format="json",
        )
        self.assertEqual(created.status_code, 201)
        community = Community.objects.get(pk=created.data["id"])
        membership = CommunityMembership.objects.get(community=community, user=self.alice)
        self.assertEqual(membership.role, CommunityMembership.Role.OWNER)
        self.assertEqual(membership.status, CommunityMembership.Status.ACTIVE)
        self.assertEqual(membership.user.bon_profile.bon_id, self.alice.bon_profile.bon_id)
        self.assertNotEqual(str(membership.id), membership.user.bon_profile.bon_id)

    def test_discovery_profile_exposes_metadata_but_not_private_content(self):
        community = self.make_community()

        profile = authed_client(self.charlie).get(f"/api/communities/discover/{community.id}/")
        private_detail = authed_client(self.charlie).get(f"/api/communities/{community.id}/")

        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data["name"], community.name)
        self.assertIn("member_count", profile.data)
        self.assertNotIn("email", str(profile.data))
        self.assertEqual(private_detail.status_code, 404)

    def test_join_request_approval_is_owner_admin_only_and_creates_membership(self):
        community = self.make_community()
        request = authed_client(self.bob).post(
            f"/api/communities/{community.id}/join-requests/",
            {},
            format="json",
        )
        self.assertEqual(request.status_code, 201)
        request_id = request.data["id"]

        unauthorized = authed_client(self.charlie).post(
            f"/api/communities/join-requests/{request_id}/approve/",
            {},
            format="json",
        )
        self.assertEqual(unauthorized.status_code, 403)

        approved = authed_client(self.alice).post(
            f"/api/communities/join-requests/{request_id}/approve/",
            {},
            format="json",
        )
        self.assertEqual(approved.status_code, 200)
        self.assertEqual(approved.data["status"], CommunityJoinRequest.Status.APPROVED)
        membership = CommunityMembership.objects.get(community=community, user=self.bob)
        self.assertEqual(membership.role, CommunityMembership.Role.MEMBER)
        self.assertEqual(membership.status, CommunityMembership.Status.ACTIVE)

        duplicate = authed_client(self.bob).post(
            f"/api/communities/{community.id}/join-requests/",
            {},
            format="json",
        )
        self.assertEqual(duplicate.status_code, 400)

    def test_community_admin_can_approve_join_request(self):
        community = self.make_community()
        CommunityMembership.objects.create(
            community=community,
            user=self.charlie,
            role=CommunityMembership.Role.ADMIN,
            status=CommunityMembership.Status.ACTIVE,
        )
        request = authed_client(self.bob).post(
            f"/api/communities/{community.id}/join-requests/",
            {},
            format="json",
        )

        approved = authed_client(self.charlie).post(
            f"/api/communities/join-requests/{request.data['id']}/approve/",
            {},
            format="json",
        )

        self.assertEqual(approved.status_code, 200)
        self.assertEqual(
            CommunityMembership.objects.get(community=community, user=self.bob).role,
            CommunityMembership.Role.MEMBER,
        )

    def test_join_request_decline_does_not_create_membership(self):
        community = self.make_community()
        request = authed_client(self.bob).post(
            f"/api/communities/{community.id}/join-requests/",
            {},
            format="json",
        )
        declined = authed_client(self.alice).post(
            f"/api/communities/join-requests/{request.data['id']}/decline/",
            {},
            format="json",
        )

        self.assertEqual(declined.status_code, 200)
        self.assertEqual(declined.data["status"], CommunityJoinRequest.Status.DECLINED)
        self.assertFalse(CommunityMembership.objects.filter(community=community, user=self.bob).exists())

    def test_removed_member_can_request_reactivation_and_approval_reuses_membership(self):
        community = self.make_community()
        membership = CommunityMembership.objects.create(
            community=community,
            user=self.bob,
            role=CommunityMembership.Role.MEMBER,
            status=CommunityMembership.Status.REMOVED,
        )
        request = authed_client(self.bob).post(
            f"/api/communities/{community.id}/join-requests/",
            {},
            format="json",
        )
        approved = authed_client(self.alice).post(
            f"/api/communities/join-requests/{request.data['id']}/approve/",
            {},
            format="json",
        )

        self.assertEqual(approved.status_code, 200)
        membership.refresh_from_db()
        self.assertEqual(membership.status, CommunityMembership.Status.ACTIVE)
        self.assertEqual(CommunityMembership.objects.filter(community=community, user=self.bob).count(), 1)

    def test_people_lookup_is_authenticated_and_privacy_safe(self):
        response = authed_client(self.alice).get(
            f"/api/communities/people/?q={self.bob.bon_profile.bon_id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["bon_id"], self.bob.bon_profile.bon_id)
        self.assertNotIn("email", response.data["results"][0])

        self.assertEqual(APIClient().get("/api/communities/people/?q=bob").status_code, 401)
