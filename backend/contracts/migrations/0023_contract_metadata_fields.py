from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0022_contract_entity"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="title",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="contract",
            name="contract_type",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="contract",
            name="language",
            field=models.CharField(blank=True, default="English", max_length=50),
        ),
        migrations.AddField(
            model_name="contract",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contract",
            name="end_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="contract",
            name="value",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=20, null=True),
        ),
        migrations.AddField(
            model_name="contract",
            name="jurisdiction",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="contract",
            name="governing_law",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.AddField(
            model_name="contract",
            name="confidentiality",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="contract",
            name="dispute_resolution",
            field=models.CharField(blank=True, default="", max_length=100),
        ),
        migrations.AddField(
            model_name="contract",
            name="description",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="contract",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("sent", "Sent"),
                    ("active", "Active"),
                    ("completed", "Completed"),
                    ("archived", "Archived"),
                ],
                default="draft",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="contract",
            name="version",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
