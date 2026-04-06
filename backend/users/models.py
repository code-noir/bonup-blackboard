#backend/users/models.py
import uuid

from django.conf import settings
from django.db import models, transaction


class ReservedBonId(models.Model):
    """
    Stores reserved/special bonID values that must never be assigned
    to regular users.

    For now, this includes binary-only numbers made entirely of 0 and 1.
    """

    bon_id = models.CharField(
        max_length=13,
        unique=True,
        db_index=True,
        editable=False,
    )

    reason = models.CharField(
        max_length=50,
        default="binary_reserved",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["bon_id"]

    def __str__(self):
        return f"{self.bon_id} ({self.reason})"


class BonUserProfile(models.Model):
    """
    Shared bonUP identity profile.

    - user: internal Django auth user
    - bon_id: external 13-digit bonUP ID
    """

    LANGUAGE_CHOICES = [
        ("en", "English"),
        ("ht", "Haitian Creole"),
        ("es", "Spanish"),
        ("fr", "French"),
        ("pt", "Portuguese"),
        ("ar", "Arabic"),
        ("sw", "Swahili"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="bon_profile",
    )

    bon_id = models.CharField(
        max_length=13,
        unique=True,
        db_index=True,
        editable=False,
    )

    # Contact
    phone = models.CharField(max_length=30, blank=True, null=True)

    # Location
    city = models.CharField(max_length=100, blank=True, null=True)
    state_region = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)

    # Language preference
    language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default="en",
    )

    # Email verification
    email_verified = models.BooleanField(default=False)
    email_verification_token = models.UUIDField(default=None, null=True, blank=True)
    pending_email = models.EmailField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["bon_id"]

    def __str__(self):
        return f"{self.user_id} -> {self.bon_id}"

    def save(self, *args, **kwargs):
        if not self.bon_id:
            self.bon_id = self.generate_next_bon_id()
        return super().save(*args, **kwargs)

    @classmethod
    def format_bon_id(cls, number: int) -> str:
        return f"{number:013d}"

    @classmethod
    def is_reserved_bon_id(cls, bon_id: str) -> bool:
        """
        Reserved if the full 13-digit bon_id contains only 0 and 1.
        Examples:
        0000000000000
        0000000000001
        0000000000010
        0000000000011
        0000000000100
        """
        return set(bon_id).issubset({"0", "1"})

    @classmethod
    def generate_next_bon_id(cls) -> str:
        """
        Generate the next valid 13-digit bon_id in strict sequence.

        Rules:
        - Numbers are checked one by one in order.
        - Binary-only numbers (0/1 only) are reserved.
        - Reserved numbers are stored in ReservedBonId.
        - The first valid non-reserved number is assigned to the next user.
        """

        with transaction.atomic():
            last_profile = cls.objects.select_for_update().order_by("-bon_id").first()
            last_reserved = ReservedBonId.objects.select_for_update().order_by("-bon_id").first()

            last_assigned_number = int(last_profile.bon_id) if last_profile else -1
            last_reserved_number = int(last_reserved.bon_id) if last_reserved else -1

            next_number = max(last_assigned_number, last_reserved_number) + 1

            while True:
                candidate = cls.format_bon_id(next_number)

                if cls.is_reserved_bon_id(candidate):
                    ReservedBonId.objects.get_or_create(
                        bon_id=candidate,
                        defaults={"reason": "binary_reserved"},
                    )
                    next_number += 1
                    continue

                return candidate


# ============================================================
# USER BILLING INFO
# ============================================================

class UserBillingInfo(models.Model):
    """
    Billing address for a bonUP user.
    Separate from identity and location — updated independently.
    """

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="billing_info",
    )

    billing_name = models.CharField(max_length=200, blank=True, null=True)
    address_line_1 = models.CharField(max_length=255, blank=True, null=True)
    address_line_2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state_region = models.CharField(max_length=100, blank=True, null=True)
    country = models.CharField(max_length=100, blank=True, null=True)
    postal_code = models.CharField(max_length=20, blank=True, null=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"BillingInfo({self.user_id})"


# ============================================================
# USER INVITATION
# ============================================================

class BusinessEntity(models.Model):
    """
    A business entity that a user can contract under.
    Tier limits enforced via billing.gates.can_create_business_entity().
    """

    BUSINESS_TYPE_CHOICES = [
        ("LLC", "LLC"),
        ("Corporation", "Corporation"),
        ("Sole Proprietor", "Sole Proprietor"),
        ("Partnership", "Partnership"),
        ("Non-Profit", "Non-Profit"),
        ("Trust", "Trust"),
        ("S-Corp", "S-Corp"),
        ("C-Corp", "C-Corp"),
        ("Other", "Other"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_entities",
    )

    name = models.CharField(max_length=200)
    business_type = models.CharField(max_length=30, choices=BUSINESS_TYPE_CHOICES)
    description = models.CharField(max_length=300, blank=True, default="")
    industry = models.CharField(max_length=100, blank=True, default="")
    address = models.CharField(max_length=300, null=True, blank=True)
    website = models.URLField(null=True, blank=True)
    founded_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "business entities"

    def __str__(self):
        return f"{self.name} ({self.business_type}) — {self.owner_id}"


# ============================================================
# USER INVITATION
# ============================================================

class UserInvitation(models.Model):
    """
    Invitation sent by an existing user to a non-registered email.
    Powers the invite flow: send → validate token → accept (register).
    """

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("expired", "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    inviter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_invitations",
    )

    invitee_email = models.EmailField()
    invitee_name = models.CharField(max_length=200)

    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    def __str__(self):
        return f"Invitation({self.invitee_email}, {self.status})"











