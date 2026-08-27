# Generated for bonUP storage launch pricing catalog.

from datetime import datetime, timezone
from decimal import Decimal

from django.db import migrations, models


LAUNCH_EFFECTIVE_FROM = datetime(2026, 8, 27, tzinfo=timezone.utc)

STORAGE_LAUNCH_PRICES = {
    "storage-8gb": Decimal("18.00"),
    "storage-88gb": Decimal("118.00"),
    "storage-288gb": Decimal("388.00"),
}


def seed_storage_launch_prices(apps, schema_editor):
    Product = apps.get_model("billing", "Product")
    ProductPrice = apps.get_model("billing", "ProductPrice")

    for slug, amount in STORAGE_LAUNCH_PRICES.items():
        product = Product.objects.get(slug=slug)
        ProductPrice.objects.filter(
            product=product,
            price_type="one_time",
            currency="USD",
            active=True,
        ).filter(
            models.Q(effective_until__isnull=True) | models.Q(effective_until__gt=LAUNCH_EFFECTIVE_FROM)
        ).exclude(
            effective_from=LAUNCH_EFFECTIVE_FROM,
        ).update(
            active=False,
            effective_until=LAUNCH_EFFECTIVE_FROM,
        )

        ProductPrice.objects.update_or_create(
            product=product,
            price_type="one_time",
            currency="USD",
            effective_from=LAUNCH_EFFECTIVE_FROM,
            defaults={
                "amount": amount,
                "active": True,
                "effective_until": None,
            },
        )


def unseed_storage_launch_prices(apps, schema_editor):
    Product = apps.get_model("billing", "Product")
    ProductPrice = apps.get_model("billing", "ProductPrice")

    products = Product.objects.filter(slug__in=STORAGE_LAUNCH_PRICES.keys())
    ProductPrice.objects.filter(
        product__in=products,
        price_type="one_time",
        currency="USD",
        effective_from=LAUNCH_EFFECTIVE_FROM,
    ).update(
        active=False,
        effective_until=LAUNCH_EFFECTIVE_FROM,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0018_storage_commerce_accounting"),
    ]

    operations = [
        migrations.RunPython(seed_storage_launch_prices, reverse_code=unseed_storage_launch_prices),
    ]
