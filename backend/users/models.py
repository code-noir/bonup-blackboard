# backend/users/models.py
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction


class PendingSignup(models.Model):
    """
    Temporary record created when a user submits the signup form.

    A real User account, BonUserProfile, and bonID are NOT created until the
    user clicks the verification link in their email.  After successful
    verification this record is deleted.

    LIFETIME
    --------
    Expires after 24 hours.  A new token can be requested via the
    resend-verification endpoint.

    SECURITY
    --------
    The password is stored hashed (Django's PBKDF2 by default).  The
    verification token is a UUID; it is single-use — the row is deleted on
    success.
    """

    EXPIRY_HOURS = 24

    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=128)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"PendingSignup({self.email})"


class ReservedBonId(models.Model):
    """
    Stores bonID values that must never be assigned to users.

    Scope: binary-only numbers (strings consisting entirely of the digits
    0 and 1).  Examples: 0000000000000, 0000000000001, 0000000000010.

    Do NOT add retired/historical bonIDs here.  Those belong in AssignedBonId.
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


class AssignedBonId(models.Model):
    """
    Permanent historical ledger of every bonID ever assigned to a person.

    PURPOSE
    -------
    This table is the authoritative source of sequence truth for bonID
    generation.  generate_next_bon_id() reads the highest bon_id here (rather
    than from BonUserProfile) so that deleting a user can never reset the
    sequence and cause a previously-used bonID to be reissued.

    LIFETIME RULE
    -------------
    Once a bonID appears in this table it is permanent.  Rows are never
    deleted.  When an account is closed or hard-deleted the row is updated
    to status="retired"; it is never removed.

    DELETION BEHAVIOUR
    ------------------
    A pre_delete signal on BonUserProfile marks the corresponding ledger row
    as retired before the profile row is destroyed by CASCADE.  The bonID
    is therefore permanently retired even if the original User row no longer
    exists.

    PREFERRED CLOSURE PATH
    ----------------------
    Prefer soft-delete (User.is_active=False) over hard deletion.
    Soft-delete keeps BonUserProfile intact, preserves the bonID attachment
    to the account, and enables trivial restoration with the same bonID.
    Hard deletion triggers the pre_delete signal and retires the bonID.

    IDENTITY SNAPSHOT
    -----------------
    Email, first name, and last name are captured at assignment time.
    These fields have no foreign-key dependency on User so they survive
    deletion.  email_snapshot is the primary anchor for account restoration:
    a returning user who re-registers with the same email can be matched back
    to their historical bonID.

    GDPR / ERASURE
    --------------
    If a legal erasure request requires removing personal data, scrub
    email_snapshot / first_name_snapshot / last_name_snapshot and set
    user_id_at_assignment=None.  The bon_id, assigned_at, and status columns
    must be retained as they are sequencing records, not personal data.
    """

    STATUS_ACTIVE = "active"
    STATUS_RETIRED = "retired"
    STATUS_CHOICES = [
        (STATUS_ACTIVE, "Active"),
        (STATUS_RETIRED, "Retired"),
    ]

    REASON_HARD_DELETED = "hard_deleted"
    REASON_SOFT_DEACTIVATED = "soft_deactivated"
    REASON_ADMIN_ACTION = "admin_action"

    bon_id = models.CharField(
        max_length=13,
        unique=True,
        db_index=True,
        editable=False,
        help_text="The 13-digit bonID. Immutable once written.",
    )

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default=STATUS_ACTIVE,
    )

    # ── Identity snapshot (no FK — must survive User deletion) ────────────
    user_id_at_assignment = models.BigIntegerField(
        null=True,
        blank=True,
        help_text=(
            "Django User PK at assignment time.  Nullable because the user "
            "may be hard-deleted later; this record must outlive them."
        ),
    )
    email_snapshot = models.EmailField(
        null=True,
        blank=True,
        help_text="Email at assignment. Primary anchor for account restoration.",
    )
    first_name_snapshot = models.CharField(max_length=150, null=True, blank=True)
    last_name_snapshot = models.CharField(max_length=150, null=True, blank=True)

    # ── Timestamps ────────────────────────────────────────────────────────
    assigned_at = models.DateTimeField(auto_now_add=True)
    retired_at = models.DateTimeField(null=True, blank=True)
    retirement_reason = models.CharField(max_length=30, null=True, blank=True)

    class Meta:
        ordering = ["bon_id"]
        verbose_name = "Assigned bonID"
        verbose_name_plural = "Assigned bonIDs"

    def __str__(self):
        return f"{self.bon_id} ({self.status})"


class BonUserProfile(models.Model):
    """
    Shared bonUP identity profile.

    - user:   internal Django auth user (one-to-one)
    - bon_id: external 13-digit bonID assigned at signup, permanent

    bonID generation
    ----------------
    Assigned in save() via generate_next_bon_id() the first time a profile
    is created.  The assignment is also written into AssignedBonId (the
    permanent historical ledger) inside the same atomic transaction, so the
    bonID is recorded even if the profile row is later deleted.

    Once set, bon_id is never changed.  The editable=False field flag and
    the `if not self.bon_id` guard in save() both enforce this.
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
            # Wrap generation + ledger write + profile save in one atomic block
            # so all three commit together or all roll back together.
            with transaction.atomic():
                self.bon_id = self.generate_next_bon_id()

                # Snapshot the user's identity at the moment of assignment.
                # Accessed via the FK while the data is available; falls back
                # gracefully if the user hasn't been saved yet.
                try:
                    user = self.user
                    email_snap = user.email
                    first_snap = user.first_name
                    last_snap = user.last_name
                except Exception:
                    email_snap = first_snap = last_snap = None

                AssignedBonId.objects.create(
                    bon_id=self.bon_id,
                    status=AssignedBonId.STATUS_ACTIVE,
                    user_id_at_assignment=self.user_id,
                    email_snapshot=email_snap,
                    first_name_snapshot=first_snap,
                    last_name_snapshot=last_snap,
                )

                return super().save(*args, **kwargs)

        return super().save(*args, **kwargs)

    # ── bonID generation helpers ──────────────────────────────────────────

    @classmethod
    def format_bon_id(cls, number: int) -> str:
        return f"{number:013d}"

    @classmethod
    def is_reserved_bon_id(cls, bon_id: str) -> bool:
        """
        True if the candidate contains only the digits 0 and 1 (binary-only).

        Examples of reserved values:
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
        Generate the next valid 13-digit bonID in strict ascending sequence.

        Source of truth
        ---------------
        Reads the maximum bon_id from AssignedBonId (permanent historical
        ledger), not from BonUserProfile.  This ensures the sequence never
        goes backwards after a user is hard-deleted: the ledger retains
        retired entries, so deleted bonIDs are permanently excluded from
        future assignments.

        Binary reservations
        -------------------
        Candidates whose digits are exclusively 0 and 1 are reserved and
        written to ReservedBonId, then skipped.  On a completely clean
        system (empty ledger, empty reserved table), the first valid bonID
        produced is 0000000000002.

        Concurrency
        -----------
        Both tables are locked with select_for_update() inside transaction.atomic()
        so concurrent registrations produce strictly distinct values.
        """
        with transaction.atomic():
            last_ledger = (
                AssignedBonId.objects.select_for_update().order_by("-bon_id").first()
            )
            last_reserved = (
                ReservedBonId.objects.select_for_update().order_by("-bon_id").first()
            )

            last_ledger_number = int(last_ledger.bon_id) if last_ledger else -1
            last_reserved_number = int(last_reserved.bon_id) if last_reserved else -1

            next_number = max(last_ledger_number, last_reserved_number) + 1

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
# BUSINESS ENTITY
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

    # bonUP Entity layer pointer (AG2b).
    # Nullable: existing rows are backfilled by migration 0010.
    # on_delete=SET_NULL: BusinessEntity is the primary record; losing the
    # Entity pointer does not destroy the BusinessEntity.
    # Do not change this FK target until AG6 migration is scheduled.
    entity = models.OneToOneField(
        "bonup.Entity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="business_entity",
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

    def save(self, *args, **kwargs):
        if not self.entity_id:
            # First save for this BusinessEntity — create the matching bonUP
            # Entity row atomically so both commit or both roll back.
            # Local import avoids circular dependency (bonup does not import users).
            from backend.bonup.models import Entity
            with transaction.atomic():
                entity = Entity.objects.create(
                    entity_type=Entity.ENTITY_TYPE_BUSINESS
                )
                self.entity_id = entity.pk
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

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
