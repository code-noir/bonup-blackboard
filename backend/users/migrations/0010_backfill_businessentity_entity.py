# backend/users/migrations/0010_backfill_businessentity_entity.py
#
# Data migration: create one bonUP Entity row (entity_type='business_entity')
# for each existing BusinessEntity row and set the entity pointer.
# Part of AG2b — bonUP authority foundation build sequence.
#
# FORWARD
# -------
# For every BusinessEntity that does not yet have an Entity pointer:
#   1. Create an Entity row with entity_type='business_entity'.
#   2. Set business_entity.entity_id to the new Entity's pk.
# Uses bulk_create for Entity rows then batch-updates the pointer.
#
# REVERSE
# -------
# Clears all BusinessEntity.entity pointers, then deletes all Entity rows
# with entity_type='business_entity'.
# Safe at this migration stage: the only source of business_entity type
# Entity rows is this migration. No other creation path exists yet.

import uuid as uuid_module

from django.db import migrations


def backfill_entity_pointers(apps, schema_editor):
    BusinessEntity = apps.get_model('users', 'BusinessEntity')
    Entity = apps.get_model('bonup', 'Entity')

    # Only backfill rows that don't already have a pointer (idempotent-safe).
    rows = list(BusinessEntity.objects.filter(entity__isnull=True))

    if not rows:
        return

    # Build Entity objects (no DB write yet).
    entity_objects = [
        Entity(
            id=uuid_module.uuid4(),
            entity_type='business_entity',
        )
        for _ in rows
    ]

    # Write Entity rows in one query.
    Entity.objects.bulk_create(entity_objects)

    # Pair each BusinessEntity with its new Entity row and update the pointer.
    for business_entity, entity in zip(rows, entity_objects):
        business_entity.entity_id = entity.pk

    BusinessEntity.objects.bulk_update(rows, fields=['entity_id'])

    print(
        f"\n  [MIGRATION 0010] Backfilled {len(rows)} "
        f"BusinessEntity → Entity pointer(s)."
    )


def reverse_backfill(apps, schema_editor):
    BusinessEntity = apps.get_model('users', 'BusinessEntity')
    Entity = apps.get_model('bonup', 'Entity')

    # Clear the pointers first (avoids SET_NULL FK constraint issues on delete).
    BusinessEntity.objects.update(entity_id=None)

    # Delete all business_entity type Entity rows.
    # At this migration stage these were all created by the forward function.
    Entity.objects.filter(entity_type='business_entity').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0009_businessentity_entity_pointer'),
    ]

    operations = [
        migrations.RunPython(backfill_entity_pointers, reverse_backfill),
    ]
