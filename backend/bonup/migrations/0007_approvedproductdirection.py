from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bonup", "0006_agentcontroleventinbox"),
    ]

    operations = [
        migrations.CreateModel(
            name="ApprovedProductDirection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_id", models.UUIDField(unique=True)),
                ("event_digest", models.CharField(max_length=64)),
                ("agent_control_task_id", models.CharField(max_length=64)),
                ("agent_id", models.CharField(max_length=16)),
                ("proposal_id", models.UUIDField()),
                ("proposal_digest", models.CharField(max_length=64)),
                ("artifact_id", models.CharField(max_length=64)),
                ("artifact_digest", models.CharField(max_length=64)),
                ("review_id", models.UUIDField()),
                ("review_digest", models.CharField(max_length=64)),
                ("resulting_knowledge_state", models.CharField(max_length=32)),
                ("event_occurred_at", models.DateTimeField()),
                ("title", models.CharField(max_length=4096)),
                ("objective", models.CharField(max_length=4096)),
                ("proposed_requirement", models.TextField()),
                ("acceptance_intent", models.JSONField(default=list)),
                ("projected_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-event_occurred_at", "-projected_at"]},
        ),
    ]
