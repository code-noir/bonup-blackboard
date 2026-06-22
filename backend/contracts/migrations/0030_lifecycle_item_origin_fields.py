from django.db import migrations, models
import django.db.models.deletion


def backfill_lifecycle_item_origin_fields(apps, schema_editor):
    LifecycleItem = apps.get_model("contracts", "LifecycleItem")
    LifecycleItem.objects.update(
        source_type="manual",
        is_contract_derived=False,
        locked_fields=[],
    )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0029_agreement_timeline_item_foundation"),
    ]

    operations = [
        migrations.AddField(
            model_name="lifecycleitem",
            name="source_type",
            field=models.CharField(choices=[("manual", "Manual"), ("original_contract", "Original Contract"), ("contract_obligation", "Contract Obligation"), ("contract_service_obligation", "Contract Service Obligation"), ("payment_record", "Payment Record"), ("change_order", "Change Order"), ("add_on", "Add-On"), ("system", "System")], default="manual", max_length=40),
        ),
        migrations.AddField(
            model_name="lifecycleitem",
            name="source_id",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="lifecycleitem",
            name="source_label",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="lifecycleitem",
            name="source_version",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lifecycle_items", to="contracts.contractversion"),
        ),
        migrations.AddField(
            model_name="lifecycleitem",
            name="source_exchange",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="lifecycle_items", to="agreement_exchange.agreementexchange"),
        ),
        migrations.AddField(
            model_name="lifecycleitem",
            name="is_contract_derived",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="lifecycleitem",
            name="locked_fields",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.RunPython(backfill_lifecycle_item_origin_fields, noop_reverse),
    ]
