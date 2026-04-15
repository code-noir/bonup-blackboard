# backend/users/migrations/0008_pending_signup.py
#
# Schema migration: adds PendingSignup — the pre-verification staging table
# for new account registrations.  A real User + BonUserProfile + bonID are
# only created after the user clicks the verification link in their email.

import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0007_backfill_assignedbonid'),
    ]

    operations = [
        migrations.CreateModel(
            name='PendingSignup',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('first_name', models.CharField(max_length=150)),
                ('last_name', models.CharField(max_length=150)),
                ('email', models.EmailField(unique=True)),
                ('password_hash', models.CharField(max_length=128)),
                ('token', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('expires_at', models.DateTimeField()),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
    ]
