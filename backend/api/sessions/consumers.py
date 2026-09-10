# backend/api/sessions/consumers.py
#
# SessionConsumer — real-time broadcast during a Live Session.
#
# WebSocket URL:  ws/sessions/<session_id>/?token=<jwt_access_token>
#
# Authentication:
#   JWT access token passed as ?token= query parameter (browsers cannot
#   set Authorization headers on WebSocket connections).
#
# Connection close codes:
#   4001 — invalid or missing token
#   4002 — session does not exist or is not active
#   4003 — user is not a party to the contract
#   4004 — action requires initiator role
#
# Events (client → server):
#   { "type": "editor_update", "content": "<text>" }
#       Initiator only.  Broadcasts current contract content to all participants.
#
#   { "type": "slide_update", "slide_index": 0, "slide_url": "https://..." }
#       Either party.  Broadcasts the current slide to all participants.
#
#   { "type": "presentation_control", "controller": "initiator" | "counterparty" }
#       Initiator only.  Grants/revokes presentation control.
#       Non-initiator sending this is disconnected with code 4004.
#
# Events (server → client):
#   { "type": "editor_update", "content": "...", "sender_id": "..." }
#   { "type": "slide_update", "slide_index": N, "slide_url": "...", "sender_id": "..." }
#   { "type": "presentation_control", "controller": "initiator" | "counterparty" }
#   { "type": "session_ended" }
#       Consumer closes after sending.

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
        # _is_party / _is_initiator use the already-fetched select_related("contract")
        # so they are plain sync checks — no DB round trip.
        if not self._is_party():
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

        event_type = data.get("type")

        if event_type == "editor_update":
            # Initiator only.
            if self._is_initiator():
                await self.channel_layer.group_send(
                    self.group_name,
                    {
                        "type": "session.editor_update",
                        "content": data.get("content", ""),
                        "sender_id": str(self.user.id),
                    },
                )

        elif event_type == "slide_update":
            # Either party may broadcast slide position.
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "session.slide_update",
                    "slide_index": data.get("slide_index", 0),
                    "slide_url": data.get("slide_url", ""),
                    "sender_id": str(self.user.id),
                },
            )

        elif event_type == "presentation_control":
            # Only initiator may grant or revoke presentation control.
            if not self._is_initiator():
                await self.close(code=4004)
                return
            controller = data.get("controller", "initiator")
            if controller not in ("initiator", "counterparty"):
                return
            await self._update_presentation_controller(controller)
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "session.presentation_control",
                    "controller": controller,
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

    async def session_slide_update(self, event):
        """Relay slide position broadcast to this client."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "slide_update",
                    "slide_index": event["slide_index"],
                    "slide_url": event["slide_url"],
                    "sender_id": event["sender_id"],
                }
            )
        )

    async def session_presentation_control(self, event):
        """Relay presentation control change to this client."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "presentation_control",
                    "controller": event["controller"],
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
            if token.get("auth_context") is not None:
                return None
            User = get_user_model()
            return await User.objects.aget(id=token["user_id"], is_active=True)
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

    def _is_party(self):
        """Uses the contract already loaded via select_related at connect time."""
        contract = self.session.contract
        return (
            contract.initiator_id == self.user.pk
            or contract.counterparty_email == self.user.email
        )

    def _is_initiator(self):
        """Uses the contract already loaded via select_related at connect time."""
        return self.session.contract.initiator_id == self.user.pk

    @database_sync_to_async
    def _update_presentation_controller(self, controller):
        from backend.sessions.models import LiveSession
        LiveSession.objects.filter(id=self.session_id).update(
            presentation_controller=controller
        )
