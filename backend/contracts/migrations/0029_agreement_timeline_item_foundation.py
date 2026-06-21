# Generated for Agreement Timeline management foundation

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contracts", "0028_lifecycle_agreement_setup_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="lifecycleitem",
            name="created_by",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="created_lifecycle_items",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddField(
            model_name="lifecycleitem",
            name="visibility",
            field=models.CharField(
                choices=[("parties", "Both Parties"), ("owner", "Owner Only")],
                default="parties",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="lifecycleitem",
            name="item_type",
            field=models.CharField(
                choices=[
                    ("obligation", "Obligation"),
                    ("responsibility", "Responsibility"),
                    ("payment", "Payment"),
                    ("deadline", "Deadline"),
                    ("due_date", "Due Date"),
                    ("service", "Service"),
                    ("service_work", "Service Work"),
                    ("notice", "Notice"),
                    ("document", "Document"),
                    ("risk", "Risk"),
                    ("change_order", "Change Order"),
                    ("add_on", "Add-On"),
                    ("note", "Note"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="lifecycleitem",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("proposed", "Proposed"),
                    ("completed", "Completed"),
                    ("confirmed", "Confirmed"),
                    ("rejected", "Rejected"),
                    ("overdue", "Overdue"),
                    ("cancelled", "Cancelled"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
    ]
