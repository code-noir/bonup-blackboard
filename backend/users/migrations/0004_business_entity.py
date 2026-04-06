# backend/users/migrations/0004_business_entity.py

import uuid
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0003_bonuserprofile_language"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BusinessEntity",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("owner", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="business_entities",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("name", models.CharField(max_length=200)),
                ("business_type", models.CharField(
                    choices=[
                        ("LLC", "LLC"),
                        ("Corporation", "Corporation"),
                        ("Sole Proprietor", "Sole Proprietor"),
                        ("Partnership", "Partnership"),
                        ("Non-Profit", "Non-Profit"),
                        ("Trust", "Trust"),
                        ("S-Corp", "S-Corp"),
                        ("C-Corp", "C-Corp"),
                        ("Other", "Other"),
                    ],
                    max_length=30,
                )),
                ("description", models.CharField(blank=True, default="", max_length=300)),
                ("industry", models.CharField(blank=True, default="", max_length=100)),
                ("address", models.CharField(blank=True, max_length=300, null=True)),
                ("website", models.URLField(blank=True, null=True)),
                ("founded_date", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name_plural": "business entities",
                "ordering": ["name"],
            },
        ),
    ]
