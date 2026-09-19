import django.db.models.deletion
import uuid
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bonup", "0002_entity_soulentity"),
        ("operator", "0003_administrator_user_binding"),
    ]

    operations = [
        migrations.CreateModel(
            name="ProductDirectionTask",
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
                    "agent_control_task_id",
                    models.CharField(
                        blank=True,
                        help_text="Set only by a future trusted Agent Control integration.",
                        max_length=64,
                        null=True,
                        unique=True,
                    ),
                ),
                ("agent_id", models.CharField(default="PROD-01", editable=False, max_length=16)),
                ("objective", models.CharField(max_length=4096)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("SUBMITTED", "Submitted"),
                            ("RUNNING", "Running"),
                            ("WORKING_PROPOSAL", "Working proposal"),
                            ("AWAITING_FOUNDER_REVIEW", "Awaiting Founder review"),
                            ("APPROVED_INTERNAL", "Approved internal"),
                            ("REJECTED", "Rejected"),
                            ("CHANGES_REQUESTED", "Changes requested"),
                            ("BLOCKED", "Blocked"),
                        ],
                        default="SUBMITTED",
                        max_length=32,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="product_direction_tasks",
                        to="operator.administratoraccount",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="productdirectiontask",
            index=models.Index(
                fields=["status", "-created_at"],
                name="bonup_prod_dir_status_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="productdirectiontask",
            constraint=models.CheckConstraint(
                condition=models.Q(agent_id="PROD-01"),
                name="product_direction_agent_prod01",
            ),
        ),
    ]
