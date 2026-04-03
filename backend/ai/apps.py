# backend/ai/apps.py

from django.apps import AppConfig


class AIConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.ai"
    label = "ai"
