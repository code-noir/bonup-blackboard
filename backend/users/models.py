#backend/users/models.py
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















