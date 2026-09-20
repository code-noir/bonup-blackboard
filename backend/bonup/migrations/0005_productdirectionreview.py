from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bonup", "0004_productdirectionruntime"),
    ]

    operations = [
        migrations.AddField(
            model_name="productdirectiontask",
            name="review_id",
            field=models.UUIDField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="productdirectiontask",
            name="review_digest",
            field=models.CharField(blank=True, max_length=64, null=True),
        ),
    ]
