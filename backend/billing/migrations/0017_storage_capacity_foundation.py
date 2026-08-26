# backend/billing/migrations/0017_storage_capacity_foundation.py

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

GIB = 1024 ** 3
BLACKBOD_INCLUDED_STORAGE_BYTES = 8 * GIB

STORAGE_PRODUCTS = {
    "storage-8gb": ("bonUP Storage +8 GiB", 8 * GIB),
    "storage-88gb": ("bonUP Storage +88 GiB", 88 * GIB),
    "storage-288gb": ("bonUP Storage +288 GiB", 288 * GIB),
}


def seed_storage_foundation(apps, schema_editor):
    Product = apps.get_model("billing", "Product")
    ToolProductMetadata = apps.get_model("billing", "ToolProductMetadata")
    StorageProductMetadata = apps.get_model("billing", "StorageProductMetadata")

    blackbod = Product.objects.get(slug="blackbod")
    blackbod.name = "Blackbòd"
    blackbod.product_type = "tool"
    blackbod.active = True
    blackbod.monthly_price = "49.00"
    blackbod.annual_price = "490.00"
    blackbod.save(update_fields=["name", "product_type", "active", "monthly_price", "annual_price", "updated_at"])

    ToolProductMetadata.objects.update_or_create(
        product=blackbod,
        defaults={
            "tool_slug": "blackbod",
            "ai_capable": True,
            "included_storage_bytes": BLACKBOD_INCLUDED_STORAGE_BYTES,
            "included_ai_allowance": "starter",
        },
    )

    for slug, (name, capacity_bytes) in STORAGE_PRODUCTS.items():
        product, _ = Product.objects.update_or_create(
            slug=slug,
            defaults={
                "name": name,
                "product_type": "storage",
                "active": True,
                "description": "Permanent additional bonUP Storage capacity.",
                "monthly_price": None,
                "annual_price": None,
            },
        )
        StorageProductMetadata.objects.update_or_create(
            product=product,
            defaults={"capacity_bytes": capacity_bytes},
        )


def unseed_storage_foundation(apps, schema_editor):
    Product = apps.get_model("billing", "Product")
    ToolProductMetadata = apps.get_model("billing", "ToolProductMetadata")

    Product.objects.filter(slug__in=STORAGE_PRODUCTS.keys()).delete()
    Product.objects.filter(slug="blackbod").update(monthly_price=None, annual_price=None)
    ToolProductMetadata.objects.filter(tool_slug="blackbod").update(
        included_storage_bytes=0,
        included_ai_allowance="",
    )


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0016_toolentitlement_origin"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="toolproductmetadata",
            name="included_ai_allowance",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.AddField(
            model_name="toolproductmetadata",
            name="included_storage_bytes",
            field=models.PositiveBigIntegerField(default=0),
        ),
        migrations.CreateModel(
            name="StorageCapacityGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("capacity_bytes", models.PositiveBigIntegerField()),
                ("origin", models.CharField(choices=[("purchase", "Purchase"), ("operator_adjustment", "Operator Adjustment")], max_length=40)),
                ("granted_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("expires_at", models.DateTimeField(blank=True, null=True)),
                ("status", models.CharField(choices=[("active", "Active"), ("revoked", "Revoked"), ("expired", "Expired")], default="active", max_length=20)),
                ("reason", models.CharField(blank=True, default="", max_length=255)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("product", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="storage_capacity_grants", to="billing.product")),
                ("source_item", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="storage_capacity_grants", to="billing.packageitem")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="storage_capacity_grants", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-granted_at", "-id"],
            },
        ),
        migrations.AddConstraint(
            model_name="storagecapacitygrant",
            constraint=models.CheckConstraint(condition=models.Q(("capacity_bytes__gt", 0)), name="storage_grant_capacity_pos"),
        ),
        migrations.RunPython(seed_storage_foundation, reverse_code=unseed_storage_foundation),
    ]
