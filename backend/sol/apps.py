# backend/sol/apps.py

from django.apps import AppConfig


class SolConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.sol"
    label = "sol"
