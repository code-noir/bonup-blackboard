# backend/users/signals.py
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone

from backend.users.models import AssignedBonId, BonUserProfile


User = get_user_model()


@receiver(post_save, sender=User)
def create_bon_user_profile(sender, instance, created, **kwargs):
    """Create a BonUserProfile (and its bonID) the first time a User is saved."""
    if created:
        BonUserProfile.objects.get_or_create(user=instance)


@receiver(pre_delete, sender=BonUserProfile)
def retire_bon_id_on_profile_delete(sender, instance, **kwargs):
    """
    Before a BonUserProfile row is destroyed (by direct deletion or by User
    CASCADE), mark the corresponding AssignedBonId ledger entry as retired.

    This is the enforcement point for the lifetime bonID rule under hard
    deletion: the ledger row survives, the sequence never resets to this
    value, and the bonID is permanently reserved even though the user no
    longer exists in the database.

    NOTE ON PREFERRED CLOSURE
    -------------------------
    Normal account closure should use soft-delete (User.is_active=False).
    Soft-delete does not trigger this signal; the BonUserProfile row and
    the bonID attachment to the account remain intact, and the account can
    be restored trivially.  Hard deletion should only be used for legal
    erasure requests or purging confirmed test/dev data before launch.
    """
    AssignedBonId.objects.filter(bon_id=instance.bon_id).update(
        status=AssignedBonId.STATUS_RETIRED,
        retired_at=timezone.now(),
        retirement_reason=AssignedBonId.REASON_HARD_DELETED,
    )
