from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bonup", "0003_productdirectiontask"),
    ]

    operations = [
        migrations.AddField(
            model_name="productdirectiontask",
            name="proposal_artifact_id",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="productdirectiontask",
            name="proposal_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="productdirectiontask",
            name="proposal_digest",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
        migrations.AddField(
            model_name="productdirectiontask",
            name="runtime_failure_reason",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
