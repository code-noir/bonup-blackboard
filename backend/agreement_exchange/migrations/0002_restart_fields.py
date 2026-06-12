# Generated for Agreement Exchange restart support

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("agreement_exchange", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="agreementexchange",
            name="restarted_from_exchange",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="restarted_exchanges", to="agreement_exchange.agreementexchange"),
        ),
        migrations.AddField(
            model_name="agreementexchange",
            name="source_contract_version",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="agreement_exchange_restarts", to="contracts.contractversion"),
        ),
    ]
