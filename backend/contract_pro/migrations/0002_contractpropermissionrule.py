# backend/contract_pro/migrations/0002_contractpropermissionrule.py

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contract_pro", "0001_initial"),
        ("contracts", "0025_fix_lawwn_entity"),
    ]

    operations = [
        migrations.CreateModel(
            name="ContractProPermissionRule",
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
                ("action", models.CharField(max_length=60)),
                (
                    "state",
                    models.CharField(
                        choices=[
                            ("accessible", "Accessible"),
                            ("blocked", "Blocked"),
                        ],
                        max_length=20,
                    ),
                ),
                ("set_at", models.DateTimeField(auto_now_add=True)),
                (
                    "contract",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="contract_pro_permission_rules",
                        to="contracts.contract",
                    ),
                ),
                (
                    "grant",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="permission_rules",
                        to="contract_pro.contractproaccessgrant",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="contractpropermissionrule",
            constraint=models.UniqueConstraint(
                fields=["grant", "action", "contract"],
                name="unique_permission_rule_per_grant_action_contract",
            ),
        ),
    ]
