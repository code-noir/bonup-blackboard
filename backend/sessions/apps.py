# backend/sessions/apps.py

from django.apps import AppConfig


class SessionsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "backend.sessions"
    label = "live_sessions"
