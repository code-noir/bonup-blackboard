# backend/users/migrations/0009_businessentity_entity_pointer.py
#
# Schema migration: add nullable bonUP Entity pointer to BusinessEntity.
# Part of AG2b — bonUP authority foundation build sequence.
#
# Data backfill (creating Entity rows and setting the pointer) is in
# the separate migration 0010_backfill_businessentity_entity.py.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('bonup', '0002_entity_soulentity'),
        ('users', '0008_pending_signup'),
    ]

    operations = [
        migrations.AddField(
            model_name='businessentity',
            name='entity',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='business_entity',
                to='bonup.entity',
            ),
        ),
    ]
