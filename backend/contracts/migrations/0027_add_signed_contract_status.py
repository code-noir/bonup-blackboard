from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0026_lifecycle_foundation"),
    ]

    operations = [
        migrations.AlterField(
            model_name="contract",
            name="status",
            field=models.CharField(
                choices=[
                    ("draft", "Draft"),
                    ("sent", "Sent"),
                    ("signed", "Signed"),
                    ("active", "Active"),
                    ("completed", "Completed"),
                    ("archived", "Archived"),
                ],
                default="draft",
                max_length=20,
            ),
        ),
    ]
