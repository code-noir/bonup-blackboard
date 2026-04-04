# backend/sol/models.py
#
# Sol (sou-sou / tontine / susu) rotating savings group domain.

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from backend.core.currencies import CURRENCY_CHOICES


def _sol_id():
    return "SOL-" + uuid.uuid4().hex[:8].upper()


def _pay_id():
    return "PAY-" + uuid.uuid4().hex[:8].upper()


# ---------------------------------------------------------------------------
# Sol Group
# ---------------------------------------------------------------------------

class Sol(models.Model):

    STATUS_CHOICES = [
        ("active", "Active"),
        ("paused", "Paused"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    FREQUENCY_CHOICES = [
        ("weekly", "Weekly"),
        ("biweekly", "Biweekly"),
        ("monthly", "Monthly"),
    ]

    SOL_TYPE_CHOICES = [
        ("single", "Single Cycle"),
        ("recurring", "Recurring"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sol_id = models.CharField(
        max_length=20,
        unique=True,
        default=_sol_id,
        editable=False,
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

    primary_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="managed_sols",
    )

    co_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="co_managed_sols",
    )

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="active")
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)

    contribution_amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default="USD")
    tip_expectation = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    is_private = models.BooleanField(default=True)
    sol_type = models.CharField(max_length=20, choices=SOL_TYPE_CHOICES, default="single")

    start_date = models.DateField()
    expected_end_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.sol_id} — {self.name}"

    def active_member_count(self):
        return self.members.filter(is_active=True).count()


# ---------------------------------------------------------------------------
# Sol Member
# ---------------------------------------------------------------------------

class SolMember(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sol = models.ForeignKey(Sol, on_delete=models.CASCADE, related_name="members")

    bonup_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sol_memberships",
    )

    name = models.CharField(max_length=200)
    email = models.CharField(max_length=255)
    phone = models.CharField(max_length=50)
    employer = models.CharField(max_length=200, blank=True)
    emergency_contact_name = models.CharField(max_length=200, blank=True)
    emergency_contact_phone = models.CharField(max_length=50, blank=True)

    is_bonup_member = models.BooleanField(default=False)
    hand_number = models.PositiveIntegerField()
    has_received = models.BooleanField(default=False)
    is_manager_participant = models.BooleanField(default=False)

    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["hand_number"]
        unique_together = [("sol", "hand_number")]

    def __str__(self):
        return f"{self.name} (hand #{self.hand_number}) — {self.sol.sol_id}"


# ---------------------------------------------------------------------------
# Sol Contract
# ---------------------------------------------------------------------------

class SolContract(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sol = models.ForeignKey(Sol, on_delete=models.CASCADE, related_name="contracts")
    member = models.OneToOneField(SolMember, on_delete=models.CASCADE, related_name="contract")

    agreed_contribution_amount = models.DecimalField(max_digits=12, decimal_places=2)
    agreed_hand_number = models.PositiveIntegerField()
    agreed_tip_amount = models.DecimalField(max_digits=12, decimal_places=2)
    contract_text = models.TextField()

    signed_by_member = models.BooleanField(default=False)
    signed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Contract — {self.member.name} — {self.sol.sol_id}"


# ---------------------------------------------------------------------------
# Sol Payout
# ---------------------------------------------------------------------------

class SolPayout(models.Model):

    STATUS_CHOICES = [
        ("upcoming", "Upcoming"),
        ("paid", "Paid"),
        ("delayed", "Delayed"),
        ("missed", "Missed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    payout_id = models.CharField(
        max_length=20,
        unique=True,
        default=_pay_id,
        editable=False,
    )

    sol = models.ForeignKey(Sol, on_delete=models.CASCADE, related_name="payouts")

    cycle_number = models.PositiveIntegerField()
    hand_number = models.PositiveIntegerField()
    recipient = models.ForeignKey(
        SolMember,
        on_delete=models.PROTECT,
        related_name="payouts_received",
    )

    expected_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)

    expected_amount = models.DecimalField(max_digits=12, decimal_places=2)
    actual_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="upcoming")

    was_rearranged = models.BooleanField(default=False)
    original_recipient = models.ForeignKey(
        SolMember,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payouts_original",
    )
    rearranged_reason = models.TextField(blank=True)
    rearranged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sol_rearrangements",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["cycle_number", "hand_number"]

    def __str__(self):
        return f"{self.payout_id} — cycle {self.cycle_number} hand #{self.hand_number}"


# ---------------------------------------------------------------------------
# Sol Contribution
# ---------------------------------------------------------------------------

class SolContribution(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("late", "Late"),
        ("missed", "Missed"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sol = models.ForeignKey(Sol, on_delete=models.CASCADE, related_name="contributions")
    payout = models.ForeignKey(SolPayout, on_delete=models.CASCADE, related_name="contributions")
    member = models.ForeignKey(SolMember, on_delete=models.CASCADE, related_name="contributions")

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    due_date = models.DateField()
    paid_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date"]
        unique_together = [("payout", "member")]

    def __str__(self):
        return f"Contribution — {self.member.name} — {self.payout.payout_id} — {self.status}"


# ---------------------------------------------------------------------------
# Sol Tip
# ---------------------------------------------------------------------------

class SolTip(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sol = models.ForeignKey(Sol, on_delete=models.CASCADE, related_name="tips")
    from_member = models.ForeignKey(SolMember, on_delete=models.CASCADE, related_name="tips_given")
    to_manager = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sol_tips_received",
    )

    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default="USD")
    note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Tip — {self.from_member.name} → {self.to_manager} — {self.amount}"


# ---------------------------------------------------------------------------
# Sol Note (manager private notes)
# ---------------------------------------------------------------------------

class SolNote(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    sol = models.ForeignKey(Sol, on_delete=models.CASCADE, related_name="notes")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sol_notes",
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Note — {self.sol.sol_id} — {self.created_at.date()}"
