from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0023_contract_metadata_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="contract",
            name="counterparty_name",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
        migrations.RenameField(
            model_name="contract",
            old_name="value",
            new_name="contract_value",
        ),
    ]
