from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bonup", "0005_productdirectionreview"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgentControlEventInbox",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("consumer_name", models.CharField(max_length=64)),
                ("event_id", models.UUIDField()),
                ("event_type", models.CharField(max_length=96)),
                ("event_digest", models.CharField(max_length=64)),
                ("processed_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.AddConstraint(
            model_name="agentcontroleventinbox",
            constraint=models.UniqueConstraint(
                fields=("consumer_name", "event_id"),
                name="bonup_event_inbox_consumer_event_uq",
            ),
        ),
    ]
