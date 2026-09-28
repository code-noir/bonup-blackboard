import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Community(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="owned_communities",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True, default="")
    is_private = models.BooleanField(default=True, editable=False)
    is_discoverable = models.BooleanField(default=True, editable=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name


class CommunityMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MODERATOR = "moderator", "Moderator"
        MEMBER = "member", "Member"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REMOVED = "removed", "Removed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="community_memberships",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.MEMBER)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
    )
    joined_at = models.DateTimeField(default=timezone.now)
    removed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["community", "user"],
                name="community_membership_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["community", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user_id} — {self.community_id} ({self.role})"


class Friendship(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # user_a/user_b are stored in ascending Django-user-ID order.  This gives
    # one database identity to either direction of a person pair.
    user_a = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="friendships_as_a",
    )
    user_b = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="friendships_as_b",
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="friend_requests_sent",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="friend_requests_received",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user_a", "user_b"],
                name="friendship_pair_unique",
            ),
            models.CheckConstraint(
                condition=~models.Q(user_a=models.F("user_b")),
                name="friendship_no_self",
            ),
        ]
        indexes = [
            models.Index(fields=["user_a", "status"]),
            models.Index(fields=["user_b", "status"]),
            models.Index(fields=["recipient", "status"]),
        ]

    def __str__(self):
        return f"{self.requester_id} → {self.recipient_id} ({self.status})"


class CommunityJoinRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    community = models.ForeignKey(
        Community,
        on_delete=models.CASCADE,
        related_name="join_requests",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="community_join_requests",
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_community_join_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["community", "user"],
                condition=models.Q(status="pending"),
                name="community_join_request_pending_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["community", "status"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"{self.user_id} → {self.community_id} ({self.status})"
