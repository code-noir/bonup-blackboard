# backend/users/migrations/0007_backfill_assignedbonid.py
#
# Data migration: populate AssignedBonId with all bonIDs that are currently
# assigned to BonUserProfile rows.  This establishes the historical ledger
# baseline.  From this point forward:
#   - every new bonID assignment writes a row to AssignedBonId in save()
#   - hard deletion marks the row retired via the pre_delete signal
#   - generate_next_bon_id() reads AssignedBonId for sequence truth

from django.db import migrations


def backfill_assigned_bon_ids(apps, schema_editor):
    """
    Insert one AssignedBonId row for every existing BonUserProfile.

    DIRTY DATA NOTE
    ---------------
    The database contains bon_id 0000000000010 assigned to the user with
    email 'admin@test.com' (user_id=4).  This value contains only the
    digits 0 and 1, making it binary-reserved under the current
    is_reserved_bon_id() rule.  It was assigned before the full binary-
    reservation logic was hardened (the profile for that user was created
    retroactively on 2026-04-05 via a batch backfill; the generator at
    that time did not yet store the entry in ReservedBonId before skipping).

    Historical truth is preserved: 0000000000010 is recorded in the ledger
    as status='active' (it IS currently assigned to a living user row).
    It is NOT added to ReservedBonId because the ledger entry alone prevents
    reuse — the generator uses MAX(AssignedBonId.bon_id), so values below
    the current max are never re-examined.

    The invalid assignment is logged to stdout during migration so it is
    visible in deployment output.
    """
    BonUserProfile = apps.get_model('users', 'BonUserProfile')
    AssignedBonId = apps.get_model('users', 'AssignedBonId')

    profiles = list(BonUserProfile.objects.select_related('user').all())

    if not profiles:
        return  # clean system — nothing to backfill

    records = []
    for profile in profiles:
        user = profile.user
        is_binary_invalid = set(profile.bon_id).issubset({'0', '1'})

        if is_binary_invalid:
            print(
                f"\n  [MIGRATION 0007 WARNING] bon_id {profile.bon_id} is a binary-reserved "
                f"value that was incorrectly assigned to user_id={profile.user_id} "
                f"({user.email}).  Preserving as historical truth in AssignedBonId "
                f"ledger (status=active).  This value will not be reissued."
            )

        records.append(
            AssignedBonId(
                bon_id=profile.bon_id,
                status='active',
                user_id_at_assignment=profile.user_id,
                email_snapshot=user.email,
                first_name_snapshot=user.first_name,
                last_name_snapshot=user.last_name,
                retired_at=None,
                retirement_reason=None,
            )
        )

    AssignedBonId.objects.bulk_create(records)
    print(f"\n  [MIGRATION 0007] Backfilled {len(records)} bonID ledger record(s).")


def reverse_backfill(apps, schema_editor):
    """Remove all backfilled rows (safe to reverse since they were all inserted here)."""
    AssignedBonId = apps.get_model('users', 'AssignedBonId')
    AssignedBonId.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0006_assignedbonid'),
    ]

    operations = [
        migrations.RunPython(backfill_assigned_bon_ids, reverse_backfill),
    ]
