# backend/contract_pro/migrations/0001_initial.py

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("contracts", "0025_fix_lawwn_entity"),
        ("users", "0008_pending_signup"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="ContractProAccessGrant",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "access_kind",
                    models.CharField(
                        choices=[
                            ("full_contract_pro", "Full Contract Pro"),
                            ("temp_contract_pro", "Temp Contract Pro"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "access_scope",
                    models.CharField(
                        choices=[
                            ("business_wide", "Business-wide"),
                            ("selected_contracts_only", "Selected contracts only"),
                        ],
                        max_length=30,
                    ),
                ),
                (
                    "access_status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("active", "Active"),
                            ("declined", "Declined"),
                            ("revoked", "Revoked"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("granted_at", models.DateTimeField(auto_now_add=True)),
                ("accepted_at", models.DateTimeField(blank=True, null=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                (
                    "business",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contract_pro_grants",
                        to="users.businessentity",
                    ),
                ),
                (
                    "contract_pro_user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contract_pro_grants",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="ContractProContractAssignment",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("assigned_at", models.DateTimeField(auto_now_add=True)),
                ("unassigned_at", models.DateTimeField(blank=True, null=True)),
                (
                    "contract",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contract_pro_assignments",
                        to="contracts.contract",
                    ),
                ),
                (
                    "grant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contract_assignments",
                        to="contract_pro.contractproaccessgrant",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="contractproaccessgrant",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    access_status="active",
                    access_kind="full_contract_pro",
                ),
                fields=["business", "access_kind"],
                name="one_active_full_contract_pro_per_business",
            ),
        ),
    ]
