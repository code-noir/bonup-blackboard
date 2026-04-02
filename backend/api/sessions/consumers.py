# backend/api/sessions/consumers.py
#
# SessionConsumer — real-time contract broadcast during a Live Session.
#
# WebSocket URL:  ws/sessions/<session_id>/?token=<jwt_access_token>
#
# Authentication:
#   JWT access token passed as ?token= query parameter (browsers cannot
#   set Authorization headers on WebSocket connections).
#
# Connection rules:
#   - Token must be valid.
#   - Session must exist and be active.
#   - User must be a party to the session's contract.
#
# Events (client → server):
#   { "type": "editor_update", "content": "<text>" }
#       Initiator only.  Broadcasts the current contract content to all
#       connected participants.
#
# Events (server → client):
#   { "type": "editor_update", "content": "...", "sender_id": "..." }
#       Relayed to all group members when initiator sends an update.
#   { "type": "session_ended" }
#       Pushed to all group members when POST /api/sessions/<id>/end/
#       is called.  Consumer closes after sending.

import json
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer


class SessionConsumer(AsyncWebsocketConsumer):

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        self.session_id = self.scope["url_route"]["kwargs"]["session_id"]
        self.group_name = f"session_{self.session_id}"

        # 1. Authenticate via JWT.
        self.user = await self._authenticate()
        if self.user is None:
            await self.close(code=4001)
            return

        # 2. Session must exist and be active.
        self.session = await self._get_active_session()
        if self.session is None:
            await self.close(code=4002)
            return

        # 3. User must be a contract party.
        if not await self._is_party():
            await self.close(code=4003)
            return

        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    # ------------------------------------------------------------------
    # Inbound messages (client → server)
    # ------------------------------------------------------------------

    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
        except (json.JSONDecodeError, TypeError):
            return

        if data.get("type") == "editor_update":
            # Only the initiator may broadcast content updates.
            if await self._is_initiator():
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "session.editor_update",
                        "content": data.get("content", ""),
                        "sender_id": str(self.user.id),
                    },
                )

    # ------------------------------------------------------------------
    # Outbound handlers (channel layer → client)
    # ------------------------------------------------------------------

    async def session_editor_update(self, event):
        """Relay contract content broadcast to this client."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "editor_update",
                    "content": event["content"],
                    "sender_id": event["sender_id"],
                }
            )
        )

    async def session_ended(self, event):
        """Session was ended — notify this client and close."""
        await self.send(text_data=json.dumps({"type": "session_ended"}))
        await self.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _authenticate(self):
        """
        Extract and validate the JWT access token from the query string.
        Returns the User on success, None on any failure.
        """
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.tokens import AccessToken

        query_string = self.scope.get("query_string", b"").decode("utf-8")
        params = parse_qs(query_string)
        token_list = params.get("token", [])
        if not token_list:
            return None

        try:
            token = AccessToken(token_list[0])
            User = get_user_model()
            return await User.objects.aget(id=token["user_id"])
        except Exception:
            return None

    @database_sync_to_async
    def _get_active_session(self):
        from backend.sessions.models import LiveSession

        try:
            return LiveSession.objects.select_related("contract").get(
                id=self.session_id, status="active"
            )
        except LiveSession.DoesNotExist:
            return None

    @database_sync_to_async
    def _is_party(self):
        contract = self.session.contract
        return (
            contract.initiator_id == self.user.pk
            or contract.counterparty_email == self.user.email
        )

    @database_sync_to_async
    def _is_initiator(self):
        return self.session.contract.initiator_id == self.user.pk
