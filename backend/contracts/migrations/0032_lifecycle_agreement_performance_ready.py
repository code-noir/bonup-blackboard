# Generated for Agreement Performance handoff

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contracts", "0031_lifecycle_item_user_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="lifecycleagreement",
            name="performance_ready",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="lifecycleagreement",
            name="performance_ready_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="lifecycleagreement",
            name="performance_ready_by",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="performance_ready_lifecycle_agreements", to=settings.AUTH_USER_MODEL),
        ),
    ]
