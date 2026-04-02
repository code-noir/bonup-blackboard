"""
ASGI config for bonUP Blackboard.

Handles both HTTP (Django) and WebSocket (Channels) traffic.
"""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.core.settings")

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter

from backend.api.sessions.routing import websocket_urlpatterns

application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": URLRouter(websocket_urlpatterns),
    }
)
