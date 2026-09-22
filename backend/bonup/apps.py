# backend/bonup/apps.py

from django.apps import AppConfig


class BonupConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.bonup"
    verbose_name = "bonUP"

    def ready(self):
        from backend.api.product_direction.composition import (
            configure_from_installed_agent_control,
        )
        configure_from_installed_agent_control()
