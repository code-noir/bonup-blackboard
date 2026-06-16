from django.db import migrations, models


def lifecycle_setup_forward(apps, schema_editor):
    LifecycleAgreement = apps.get_model("contracts", "LifecycleAgreement")
    LifecycleEvent = apps.get_model("contracts", "LifecycleEvent")

    setup_only_ids = []
    for agreement in LifecycleAgreement.objects.filter(status="active", metadata__source="signed_contract"):
        event_types = set(
            LifecycleEvent.objects
            .filter(lifecycle_agreement_id=agreement.id)
            .values_list("event_type", flat=True)
        )
        if event_types.issubset({"lifecycle_started", "timeline_setup_started"}):
            setup_only_ids.append(agreement.id)

    if setup_only_ids:
        LifecycleAgreement.objects.filter(id__in=setup_only_ids).update(status="setup")

    LifecycleEvent.objects.filter(event_type="lifecycle_started", title="Lifecycle started").update(
        event_type="timeline_setup_started",
        title="Timeline setup started",
        description="Agreement Timeline setup was opened for the signed contract.",
    )


def lifecycle_setup_reverse(apps, schema_editor):
    LifecycleAgreement = apps.get_model("contracts", "LifecycleAgreement")
    LifecycleEvent = apps.get_model("contracts", "LifecycleEvent")
    LifecycleAgreement.objects.filter(status="setup").update(status="active")
    LifecycleEvent.objects.filter(event_type="timeline_setup_started", title="Timeline setup started").update(
        event_type="lifecycle_started",
        title="Lifecycle started",
        description="Lifecycle tracking was opened for the signed contract.",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("contracts", "0027_add_signed_contract_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="lifecycleagreement",
            name="status",
            field=models.CharField(
                choices=[
                    ("setup", "Setup"),
                    ("active", "Active"),
                    ("completed", "Completed"),
                    ("archived", "Archived"),
                ],
                default="setup",
                max_length=20,
            ),
        ),
        migrations.RunPython(lifecycle_setup_forward, lifecycle_setup_reverse),
    ]
