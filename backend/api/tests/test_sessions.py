# backend/api/tests/test_sessions.py
#
# Tests for the Live Sessions domain:
# - POST /api/sessions/       — create session
# - GET  /api/sessions/       — list sessions (scoped, filtered)
# - GET  /api/sessions/<id>/  — detail, ownership enforced
# - PATCH /api/sessions/<id>/ — update title/scheduled_at, 409 if not scheduled
# - POST /api/sessions/<id>/cancel/ — cancel scheduled session, 409 if not scheduled
# - POST /api/sessions/<id>/join/  — get LiveKit token, auto-activates
# - POST /api/sessions/<id>/end/   — end session, logs activity, returns 409 if already ended
# - POST /api/sessions/<id>/broadcast/ — initiator broadcasts content, 403 for counterparty
# - GET  /api/contracts/<id>/sessions/ — contract-scoped list
# - WebSocket ws/sessions/<id>/ — JWT auth, party check, editor_update, session_ended

from backend.activity.models import ContractActivity
from backend.sessions.models import LiveSession

from .helpers import authed_client, make_contract, make_user, make_version


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_session(client, contract_id, **kwargs):
    body = {"contract_id": str(contract_id)}
    body.update(kwargs)
    return client.post("/api/sessions/", body, format="json")


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class SessionCreateTests(__import__("django.test", fromlist=["TestCase"]).TestCase):

    def setUp(self):
        self.alice = make_user("alice_sc", "alice_sc@example.com")
        self.bob = make_user("bob_sc", "bob_sc@example.com")
        self.charlie = make_user("charlie_sc", "charlie_sc@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_sc@example.com")

    def test_initiator_can_create_session(self):
        r = _create_session(authed_client(self.alice), self.contract.id)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["status"], "scheduled")
        self.assertIn("room_name", r.data)
        self.assertIn("livekit_host", r.data)
        self.assertEqual(str(r.data["contract_id"]), str(self.contract.id))

    def test_counterparty_can_create_session(self):
        r = _create_session(authed_client(self.bob), self.contract.id)
        self.assertEqual(r.status_code, 201)

    def test_stranger_cannot_create_session(self):
        r = _create_session(authed_client(self.charlie), self.contract.id)
        self.assertEqual(r.status_code, 403)

    def test_missing_contract_id_returns_400(self):
        r = authed_client(self.alice).post("/api/sessions/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_nonexistent_contract_returns_404(self):
        r = _create_session(
            authed_client(self.alice),
            "00000000-0000-0000-0000-000000000000",
        )
        self.assertEqual(r.status_code, 404)

    def test_with_version_links_version(self):
        version = make_version(self.contract, self.alice)
        r = _create_session(
            authed_client(self.alice),
            self.contract.id,
            version_id=str(version.id),
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(str(r.data["version_id"]), str(version.id))

    def test_with_title(self):
        r = _create_session(authed_client(self.alice), self.contract.id, title="First negotiation")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["title"], "First negotiation")

    def test_room_name_is_unique_per_session(self):
        r1 = _create_session(authed_client(self.alice), self.contract.id)
        r2 = _create_session(authed_client(self.alice), self.contract.id)
        self.assertNotEqual(r1.data["room_name"], r2.data["room_name"])

    def test_create_logs_activity(self):
        _create_session(authed_client(self.alice), self.contract.id)
        self.assertTrue(
            ContractActivity.objects.filter(
                contract=self.contract, activity_type="session_held"
            ).exists()
        )


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class SessionListTests(__import__("django.test", fromlist=["TestCase"]).TestCase):

    def setUp(self):
        self.alice = make_user("alice_sl", "alice_sl@example.com")
        self.bob = make_user("bob_sl", "bob_sl@example.com")
        self.charlie = make_user("charlie_sl", "charlie_sl@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_sl@example.com")
        _create_session(authed_client(self.alice), self.contract.id)

    def test_initiator_sees_own_sessions(self):
        r = authed_client(self.alice).get("/api/sessions/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_counterparty_sees_shared_sessions(self):
        r = authed_client(self.bob).get("/api/sessions/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_stranger_sees_nothing(self):
        r = authed_client(self.charlie).get("/api/sessions/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 0)

    def test_contract_id_filter(self):
        other_contract = make_contract(self.alice, counterparty_email="other_sl@example.com")
        _create_session(authed_client(self.alice), other_contract.id)

        r = authed_client(self.alice).get(f"/api/sessions/?contract_id={self.contract.id}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(str(r.data[0]["contract_id"]), str(self.contract.id))

    def test_status_filter(self):
        r = authed_client(self.alice).get("/api/sessions/?status=scheduled")
        self.assertEqual(r.status_code, 200)
        for s in r.data:
            self.assertEqual(s["status"], "scheduled")


# ---------------------------------------------------------------------------
# Detail + Update (PATCH)
# ---------------------------------------------------------------------------

class SessionDetailTests(__import__("django.test", fromlist=["TestCase"]).TestCase):

    def setUp(self):
        self.alice = make_user("alice_sd", "alice_sd@example.com")
        self.bob = make_user("bob_sd", "bob_sd@example.com")
        self.charlie = make_user("charlie_sd", "charlie_sd@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_sd@example.com")
        r = _create_session(authed_client(self.alice), self.contract.id)
        self.session_id = r.data["id"]

    def test_initiator_can_retrieve(self):
        r = authed_client(self.alice).get(f"/api/sessions/{self.session_id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["id"], self.session_id)

    def test_counterparty_can_retrieve(self):
        r = authed_client(self.bob).get(f"/api/sessions/{self.session_id}/")
        self.assertEqual(r.status_code, 200)

    def test_stranger_cannot_retrieve(self):
        r = authed_client(self.charlie).get(f"/api/sessions/{self.session_id}/")
        self.assertEqual(r.status_code, 403)

    def test_nonexistent_returns_404(self):
        r = authed_client(self.alice).get(
            "/api/sessions/00000000-0000-0000-0000-000000000000/"
        )
        self.assertEqual(r.status_code, 404)


class SessionUpdateTests(__import__("django.test", fromlist=["TestCase"]).TestCase):

    def setUp(self):
        self.alice = make_user("alice_su", "alice_su@example.com")
        self.bob = make_user("bob_su", "bob_su@example.com")
        self.charlie = make_user("charlie_su", "charlie_su@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_su@example.com")
        r = _create_session(authed_client(self.alice), self.contract.id)
        self.session_id = r.data["id"]

    def test_patch_title(self):
        r = authed_client(self.alice).patch(
            f"/api/sessions/{self.session_id}/",
            {"title": "Renegotiation call"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["title"], "Renegotiation call")
        session = LiveSession.objects.get(id=self.session_id)
        self.assertEqual(session.title, "Renegotiation call")

    def test_patch_scheduled_at(self):
        r = authed_client(self.alice).patch(
            f"/api/sessions/{self.session_id}/",
            {"scheduled_at": "2026-05-01T10:00:00Z"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertIsNotNone(r.data["scheduled_at"])

    def test_counterparty_can_patch(self):
        r = authed_client(self.bob).patch(
            f"/api/sessions/{self.session_id}/",
            {"title": "Bob updated this"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["title"], "Bob updated this")

    def test_stranger_cannot_patch(self):
        r = authed_client(self.charlie).patch(
            f"/api/sessions/{self.session_id}/",
            {"title": "Intruder"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_patch_active_session_returns_409(self):
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/join/")
        r = authed_client(self.alice).patch(
            f"/api/sessions/{self.session_id}/",
            {"title": "Too late"},
            format="json",
        )
        self.assertEqual(r.status_code, 409)

    def test_patch_ended_session_returns_409(self):
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/end/")
        r = authed_client(self.alice).patch(
            f"/api/sessions/{self.session_id}/",
            {"title": "Too late"},
            format="json",
        )
        self.assertEqual(r.status_code, 409)


# ---------------------------------------------------------------------------
# Cancel
# ---------------------------------------------------------------------------

class SessionCancelTests(__import__("django.test", fromlist=["TestCase"]).TestCase):

    def setUp(self):
        self.alice = make_user("alice_sx", "alice_sx@example.com")
        self.bob = make_user("bob_sx", "bob_sx@example.com")
        self.charlie = make_user("charlie_sx", "charlie_sx@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_sx@example.com")
        r = _create_session(authed_client(self.alice), self.contract.id)
        self.session_id = r.data["id"]

    def test_cancel_scheduled_session(self):
        r = authed_client(self.alice).post(f"/api/sessions/{self.session_id}/cancel/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "cancelled")
        session = LiveSession.objects.get(id=self.session_id)
        self.assertEqual(session.status, "cancelled")

    def test_counterparty_can_cancel(self):
        r = authed_client(self.bob).post(f"/api/sessions/{self.session_id}/cancel/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "cancelled")

    def test_stranger_cannot_cancel(self):
        r = authed_client(self.charlie).post(f"/api/sessions/{self.session_id}/cancel/")
        self.assertEqual(r.status_code, 403)

    def test_cancel_active_session_returns_409(self):
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/join/")
        r = authed_client(self.alice).post(f"/api/sessions/{self.session_id}/cancel/")
        self.assertEqual(r.status_code, 409)

    def test_cancel_ended_session_returns_409(self):
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/end/")
        r = authed_client(self.alice).post(f"/api/sessions/{self.session_id}/cancel/")
        self.assertEqual(r.status_code, 409)

    def test_cancel_logs_activity(self):
        # setUp already triggers one session_held (create); cancel adds another
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/cancel/")
        count = ContractActivity.objects.filter(
            contract=self.contract, activity_type="session_held"
        ).count()
        self.assertEqual(count, 2)

    def test_double_cancel_returns_409(self):
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/cancel/")
        r = authed_client(self.alice).post(f"/api/sessions/{self.session_id}/cancel/")
        self.assertEqual(r.status_code, 409)


# ---------------------------------------------------------------------------
# Join
# ---------------------------------------------------------------------------

class SessionJoinTests(__import__("django.test", fromlist=["TestCase"]).TestCase):

    def setUp(self):
        self.alice = make_user("alice_sj", "alice_sj@example.com")
        self.bob = make_user("bob_sj", "bob_sj@example.com")
        self.charlie = make_user("charlie_sj", "charlie_sj@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_sj@example.com")
        r = _create_session(authed_client(self.alice), self.contract.id)
        self.session_id = r.data["id"]

    def test_join_returns_token_and_host(self):
        r = authed_client(self.alice).post(f"/api/sessions/{self.session_id}/join/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.data)
        self.assertIn("livekit_host", r.data)
        self.assertIn("room_name", r.data)
        self.assertTrue(len(r.data["token"]) > 10)

    def test_join_activates_scheduled_session(self):
        r = authed_client(self.alice).post(f"/api/sessions/{self.session_id}/join/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "active")

        session = LiveSession.objects.get(id=self.session_id)
        self.assertEqual(session.status, "active")
        self.assertIsNotNone(session.started_at)

    def test_join_already_active_session_returns_token(self):
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/join/")
        r = authed_client(self.bob).post(f"/api/sessions/{self.session_id}/join/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("token", r.data)

    def test_join_ended_session_returns_409(self):
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/end/")
        r = authed_client(self.alice).post(f"/api/sessions/{self.session_id}/join/")
        self.assertEqual(r.status_code, 409)

    def test_join_cancelled_session_returns_409(self):
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/cancel/")
        r = authed_client(self.alice).post(f"/api/sessions/{self.session_id}/join/")
        self.assertEqual(r.status_code, 409)

    def test_stranger_cannot_join(self):
        r = authed_client(self.charlie).post(f"/api/sessions/{self.session_id}/join/")
        self.assertEqual(r.status_code, 403)

    def test_counterparty_gets_own_token(self):
        r_alice = authed_client(self.alice).post(f"/api/sessions/{self.session_id}/join/")
        r_bob = authed_client(self.bob).post(f"/api/sessions/{self.session_id}/join/")
        self.assertNotEqual(r_alice.data["token"], r_bob.data["token"])


# ---------------------------------------------------------------------------
# End
# ---------------------------------------------------------------------------

class SessionEndTests(__import__("django.test", fromlist=["TestCase"]).TestCase):

    def setUp(self):
        self.alice = make_user("alice_se", "alice_se@example.com")
        self.bob = make_user("bob_se", "bob_se@example.com")
        self.charlie = make_user("charlie_se", "charlie_se@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_se@example.com")
        r = _create_session(authed_client(self.alice), self.contract.id)
        self.session_id = r.data["id"]

    def test_end_session(self):
        r = authed_client(self.alice).post(f"/api/sessions/{self.session_id}/end/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "ended")

        session = LiveSession.objects.get(id=self.session_id)
        self.assertEqual(session.status, "ended")
        self.assertIsNotNone(session.ended_at)

    def test_end_logs_activity(self):
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/end/")
        count = ContractActivity.objects.filter(
            contract=self.contract, activity_type="session_held"
        ).count()
        self.assertEqual(count, 2)

    def test_end_already_ended_returns_409(self):
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/end/")
        r = authed_client(self.alice).post(f"/api/sessions/{self.session_id}/end/")
        self.assertEqual(r.status_code, 409)

    def test_counterparty_can_end_session(self):
        r = authed_client(self.bob).post(f"/api/sessions/{self.session_id}/end/")
        self.assertEqual(r.status_code, 200)

    def test_stranger_cannot_end_session(self):
        r = authed_client(self.charlie).post(f"/api/sessions/{self.session_id}/end/")
        self.assertEqual(r.status_code, 403)

    def test_end_after_join_records_duration(self):
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/join/")
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/end/")
        entry = ContractActivity.objects.filter(
            contract=self.contract,
            activity_type="session_held",
            metadata__duration_seconds__isnull=False,
        ).first()
        self.assertIsNotNone(entry)
        self.assertGreaterEqual(entry.metadata["duration_seconds"], 0)


# ---------------------------------------------------------------------------
# Broadcast
# ---------------------------------------------------------------------------

class SessionBroadcastTests(__import__("django.test", fromlist=["TestCase"]).TestCase):

    def setUp(self):
        self.alice = make_user("alice_sb", "alice_sb@example.com")
        self.bob = make_user("bob_sb", "bob_sb@example.com")
        self.charlie = make_user("charlie_sb", "charlie_sb@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_sb@example.com")
        r = _create_session(authed_client(self.alice), self.contract.id)
        self.session_id = r.data["id"]
        # activate
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/join/")

    def test_initiator_can_broadcast(self):
        r = authed_client(self.alice).post(
            f"/api/sessions/{self.session_id}/broadcast/",
            {"content": "Updated clause 3."},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["broadcasted"])

    def test_counterparty_cannot_broadcast(self):
        r = authed_client(self.bob).post(
            f"/api/sessions/{self.session_id}/broadcast/",
            {"content": "Counterparty edit"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_stranger_cannot_broadcast(self):
        r = authed_client(self.charlie).post(
            f"/api/sessions/{self.session_id}/broadcast/",
            {"content": "Hack"},
            format="json",
        )
        self.assertEqual(r.status_code, 403)

    def test_broadcast_on_non_active_session_returns_409(self):
        # End the session first
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/end/")
        r = authed_client(self.alice).post(
            f"/api/sessions/{self.session_id}/broadcast/",
            {"content": "Too late"},
            format="json",
        )
        self.assertEqual(r.status_code, 409)

    def test_broadcast_on_scheduled_session_returns_409(self):
        r2 = _create_session(authed_client(self.alice), self.contract.id)
        sid2 = r2.data["id"]
        r = authed_client(self.alice).post(
            f"/api/sessions/{sid2}/broadcast/",
            {"content": "Not active yet"},
            format="json",
        )
        self.assertEqual(r.status_code, 409)


# ---------------------------------------------------------------------------
# Contract-scoped session list
# ---------------------------------------------------------------------------

class ContractSessionListTests(__import__("django.test", fromlist=["TestCase"]).TestCase):

    def setUp(self):
        self.alice = make_user("alice_csl", "alice_csl@example.com")
        self.bob = make_user("bob_csl", "bob_csl@example.com")
        self.charlie = make_user("charlie_csl", "charlie_csl@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_csl@example.com")
        _create_session(authed_client(self.alice), self.contract.id)
        _create_session(authed_client(self.alice), self.contract.id)

    def test_initiator_sees_all_contract_sessions(self):
        r = authed_client(self.alice).get(f"/api/contracts/{self.contract.id}/sessions/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_counterparty_sees_all_contract_sessions(self):
        r = authed_client(self.bob).get(f"/api/contracts/{self.contract.id}/sessions/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_stranger_cannot_see_contract_sessions(self):
        r = authed_client(self.charlie).get(f"/api/contracts/{self.contract.id}/sessions/")
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------------------
# WebSocket consumer
# ---------------------------------------------------------------------------

class SessionConsumerTests(
    __import__("django.test", fromlist=["TransactionTestCase"]).TransactionTestCase
):
    """
    WebSocket consumer tests use TransactionTestCase so that data created in
    setUp is committed to the DB and visible to the async ORM calls that
    run in background threads inside database_sync_to_async.
    """

    def setUp(self):
        self.alice = make_user("alice_ws", "alice_ws@example.com")
        self.bob = make_user("bob_ws", "bob_ws@example.com")
        self.charlie = make_user("charlie_ws", "charlie_ws@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_ws@example.com")
        r = _create_session(authed_client(self.alice), self.contract.id)
        self.session_id = r.data["id"]
        # Activate the session so the consumer will accept connections.
        authed_client(self.alice).post(f"/api/sessions/{self.session_id}/join/")

    def _token(self, user):
        from rest_framework_simplejwt.tokens import AccessToken
        return str(AccessToken.for_user(user))

    def _ws_url(self, user=None, session_id=None, token=None):
        sid = session_id or self.session_id
        tok = token if token is not None else self._token(user or self.alice)
        return f"ws/sessions/{sid}/?token={tok}"

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def test_party_can_connect(self):
        from asgiref.sync import async_to_sync
        async_to_sync(self._assert_connects)(self.alice)

    def test_counterparty_can_connect(self):
        from asgiref.sync import async_to_sync
        async_to_sync(self._assert_connects)(self.bob)

    def test_no_token_rejected(self):
        from asgiref.sync import async_to_sync
        async_to_sync(self._assert_rejected)(f"ws/sessions/{self.session_id}/", 4001)

    def test_invalid_token_rejected(self):
        from asgiref.sync import async_to_sync
        async_to_sync(self._assert_rejected)(
            f"ws/sessions/{self.session_id}/?token=notavalidjwt", 4001
        )

    def test_stranger_rejected(self):
        from asgiref.sync import async_to_sync
        async_to_sync(self._assert_rejected)(self._ws_url(self.charlie), 4003)

    def test_scheduled_session_rejected(self):
        from asgiref.sync import async_to_sync
        # Create a new session (still scheduled, not active)
        r = _create_session(authed_client(self.alice), self.contract.id)
        sid = r.data["id"]
        async_to_sync(self._assert_rejected)(self._ws_url(self.alice, session_id=sid), 4002)

    def test_nonexistent_session_rejected(self):
        from asgiref.sync import async_to_sync
        fake_sid = "00000000-0000-0000-0000-000000000001"
        async_to_sync(self._assert_rejected)(self._ws_url(self.alice, session_id=fake_sid), 4002)

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    def test_initiator_editor_update_broadcast(self):
        import json
        from asgiref.sync import async_to_sync
        async_to_sync(self._test_editor_update)()

    def test_counterparty_editor_update_ignored(self):
        import json
        from asgiref.sync import async_to_sync
        async_to_sync(self._test_counterparty_cannot_broadcast)()

    def test_session_ended_event_received(self):
        from asgiref.sync import async_to_sync
        async_to_sync(self._test_session_ended_event)()

    # ------------------------------------------------------------------
    # Async helpers
    # ------------------------------------------------------------------

    async def _assert_connects(self, user):
        from channels.testing import WebsocketCommunicator
        from backend.core.asgi import application
        communicator = WebsocketCommunicator(application, self._ws_url(user))
        connected, _ = await communicator.connect()
        self.assertTrue(connected)
        await communicator.disconnect()

    async def _assert_rejected(self, url, expected_code):
        from channels.testing import WebsocketCommunicator
        from backend.core.asgi import application
        communicator = WebsocketCommunicator(application, url)
        connected, code = await communicator.connect()
        self.assertFalse(connected)
        self.assertEqual(code, expected_code)

    async def _test_editor_update(self):
        import json
        from channels.testing import WebsocketCommunicator
        from backend.core.asgi import application

        alice_comm = WebsocketCommunicator(application, self._ws_url(self.alice))
        bob_comm = WebsocketCommunicator(application, self._ws_url(self.bob))

        connected_a, _ = await alice_comm.connect()
        connected_b, _ = await bob_comm.connect()
        self.assertTrue(connected_a)
        self.assertTrue(connected_b)

        # Alice (initiator) sends editor_update
        await alice_comm.send_json_to({"type": "editor_update", "content": "Clause 4 amended."})

        # Both Alice and Bob should receive the broadcast
        msg_a = await alice_comm.receive_json_from()
        msg_b = await bob_comm.receive_json_from()

        self.assertEqual(msg_a["type"], "editor_update")
        self.assertEqual(msg_a["content"], "Clause 4 amended.")
        self.assertEqual(msg_b["type"], "editor_update")
        self.assertEqual(msg_b["content"], "Clause 4 amended.")

        await alice_comm.disconnect()
        await bob_comm.disconnect()

    async def _test_counterparty_cannot_broadcast(self):
        import json
        from channels.testing import WebsocketCommunicator
        from backend.core.asgi import application

        alice_comm = WebsocketCommunicator(application, self._ws_url(self.alice))
        bob_comm = WebsocketCommunicator(application, self._ws_url(self.bob))

        await alice_comm.connect()
        await bob_comm.connect()

        # Bob (counterparty) sends editor_update — should be silently ignored
        await bob_comm.send_json_to({"type": "editor_update", "content": "Sneaky edit"})

        # Alice should receive nothing
        self.assertTrue(await alice_comm.receive_nothing())

        await alice_comm.disconnect()
        await bob_comm.disconnect()

    async def _test_session_ended_event(self):
        from asgiref.sync import sync_to_async
        from channels.testing import WebsocketCommunicator
        from backend.core.asgi import application

        alice_comm = WebsocketCommunicator(application, self._ws_url(self.alice))
        connected, _ = await alice_comm.connect()
        self.assertTrue(connected)

        # End the session via the HTTP endpoint (sync client wrapped for async context).
        client = authed_client(self.alice)
        await sync_to_async(client.post)(f"/api/sessions/{self.session_id}/end/")

        msg = await alice_comm.receive_json_from()
        self.assertEqual(msg["type"], "session_ended")
        # Consumer should close after sending session_ended
        await alice_comm.disconnect()
