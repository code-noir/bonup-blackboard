# backend/billing/migrations/0014_seed_blackbod_product.py

from django.db import migrations


def seed_blackbod_product(apps, schema_editor):
    Product = apps.get_model("billing", "Product")
    ToolProductMetadata = apps.get_model("billing", "ToolProductMetadata")

    product, _ = Product.objects.update_or_create(
        slug="blackbod",
        defaults={
            "name": "Blackbòd",
            "product_type": "tool",
            "active": True,
            "description": "The complete Blackbòd contract tool.",
            "monthly_price": None,
            "annual_price": None,
        },
    )
    ToolProductMetadata.objects.update_or_create(
        product=product,
        defaults={
            "tool_slug": "blackbod",
            "ai_capable": True,
        },
    )


def unseed_blackbod_product(apps, schema_editor):
    Product = apps.get_model("billing", "Product")
    Product.objects.filter(slug="blackbod").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0013_product_customerpackage_packageitem_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_blackbod_product, reverse_code=unseed_blackbod_product),
    ]
