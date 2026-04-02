# backend/billing/apps.py

from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.billing"
    label = "billing"
