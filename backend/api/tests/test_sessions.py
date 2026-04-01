# backend/api/tests/test_sessions.py
#
# Tests for the Live Sessions domain:
# - POST /api/sessions/       — create session
# - GET  /api/sessions/       — list sessions (scoped, filtered)
# - GET  /api/sessions/<id>/  — detail, ownership enforced
# - POST /api/sessions/<id>/join/  — get LiveKit token, auto-activates
# - POST /api/sessions/<id>/end/   — end session, logs activity, returns 409 if already ended
# - GET  /api/contracts/<id>/sessions/ — contract-scoped list

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
# Detail
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
        # Should have two session_held entries: one for create, one for end
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
        # Find the "ended" activity and check duration_seconds is set
        entry = ContractActivity.objects.filter(
            contract=self.contract,
            activity_type="session_held",
            metadata__duration_seconds__isnull=False,
        ).first()
        self.assertIsNotNone(entry)
        self.assertGreaterEqual(entry.metadata["duration_seconds"], 0)


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
