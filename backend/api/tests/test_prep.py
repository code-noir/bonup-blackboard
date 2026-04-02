# backend/api/tests/test_prep.py
#
# Tests for the NegotiationPrep domain:
# - POST   /api/prep/                            — create prep session
# - GET    /api/prep/                            — list (owner-scoped)
# - GET    /api/prep/<id>/                       — detail with documents + notes
# - PATCH  /api/prep/<id>/                       — update title/notes
# - DELETE /api/prep/<id>/                       — delete
# - POST   /api/prep/<id>/documents/             — add document
# - DELETE /api/prep/<id>/documents/<doc_id>/    — remove document
# - POST   /api/prep/<id>/notes/                 — add note
# - PATCH  /api/prep/<id>/notes/<note_id>/       — update note
# - DELETE /api/prep/<id>/notes/<note_id>/       — delete note
# - Privacy: only owner may access; both parties of a contract may create
#   separate prep sessions linked to the same live session

from django.test import TestCase

from backend.negotiation_prep.models import PrepDocument, PrepNote, PrepSession

from .helpers import authed_client, make_contract, make_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_session(client, **kwargs):
    return client.post("/api/prep/", kwargs, format="json")


def _make_prep(user, title="My prep", notes="", live_session_id=None):
    data = {"title": title, "notes": notes}
    if live_session_id:
        data["live_session_id"] = str(live_session_id)
    r = authed_client(user).post("/api/prep/", data, format="json")
    return r


def _make_live_session(user, contract):
    from backend.sessions.models import LiveSession
    import uuid
    session_uuid = uuid.uuid4()
    return LiveSession.objects.create(
        id=session_uuid,
        contract=contract,
        created_by=user,
        room_name=f"bonup-{session_uuid}",
    )


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class PrepCreateTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_pc", "alice_pc@example.com")
        self.bob = make_user("bob_pc", "bob_pc@example.com")

    def test_create_minimal(self):
        r = _make_prep(self.alice, title="Contract review")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["title"], "Contract review")
        self.assertEqual(r.data["live_session_id"], None)
        self.assertEqual(r.data["owner_id"], self.alice.pk)

    def test_create_with_notes(self):
        r = _make_prep(self.alice, title="T", notes="Key points to raise")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["notes"], "Key points to raise")

    def test_create_linked_to_live_session(self):
        contract = make_contract(self.alice, counterparty_email="bob_pc@example.com")
        ls = _make_live_session(self.alice, contract)
        r = _make_prep(self.alice, title="Session prep", live_session_id=ls.id)
        self.assertEqual(r.status_code, 201)
        self.assertEqual(str(r.data["live_session_id"]), str(ls.id))

    def test_create_missing_title_returns_400(self):
        r = authed_client(self.alice).post("/api/prep/", {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_create_blank_title_returns_400(self):
        r = authed_client(self.alice).post("/api/prep/", {"title": "  "}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_create_nonexistent_live_session_returns_404(self):
        r = authed_client(self.alice).post(
            "/api/prep/",
            {"title": "T", "live_session_id": "00000000-0000-0000-0000-000000000000"},
            format="json",
        )
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class PrepListTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_pl", "alice_pl@example.com")
        self.bob = make_user("bob_pl", "bob_pl@example.com")
        _make_prep(self.alice, title="Alice prep 1")
        _make_prep(self.alice, title="Alice prep 2")
        _make_prep(self.bob, title="Bob prep")

    def test_returns_only_own_preps(self):
        r = authed_client(self.alice).get("/api/prep/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_bob_sees_only_own(self):
        r = authed_client(self.bob).get("/api/prep/")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["title"], "Bob prep")

    def test_empty_list_when_no_preps(self):
        charlie = make_user("charlie_pl", "charlie_pl@example.com")
        r = authed_client(charlie).get("/api/prep/")
        self.assertEqual(len(r.data), 0)


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

class PrepDetailTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_pd", "alice_pd@example.com")
        self.bob = make_user("bob_pd", "bob_pd@example.com")
        r = _make_prep(self.alice, title="Detail test")
        self.prep_id = r.data["id"]

    def test_owner_can_retrieve(self):
        r = authed_client(self.alice).get(f"/api/prep/{self.prep_id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["title"], "Detail test")
        self.assertIn("documents", r.data)
        self.assertIn("notes_list", r.data)

    def test_non_owner_gets_404(self):
        r = authed_client(self.bob).get(f"/api/prep/{self.prep_id}/")
        self.assertEqual(r.status_code, 404)

    def test_nonexistent_prep_returns_404(self):
        r = authed_client(self.alice).get(
            "/api/prep/00000000-0000-0000-0000-000000000000/"
        )
        self.assertEqual(r.status_code, 404)

    def test_documents_and_notes_in_detail(self):
        # Add a document and a note, then check detail includes them
        authed_client(self.alice).post(
            f"/api/prep/{self.prep_id}/documents/",
            {"title": "Agenda", "file_url": "https://cdn.example.com/agenda.pdf", "file_type": "pdf"},
            format="json",
        )
        authed_client(self.alice).post(
            f"/api/prep/{self.prep_id}/notes/",
            {"content": "Ask about payment terms", "order": 1},
            format="json",
        )
        r = authed_client(self.alice).get(f"/api/prep/{self.prep_id}/")
        self.assertEqual(len(r.data["documents"]), 1)
        self.assertEqual(len(r.data["notes_list"]), 1)


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class PrepUpdateTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_pu", "alice_pu@example.com")
        self.bob = make_user("bob_pu", "bob_pu@example.com")
        r = _make_prep(self.alice, title="Original")
        self.prep_id = r.data["id"]

    def test_patch_title(self):
        r = authed_client(self.alice).patch(
            f"/api/prep/{self.prep_id}/", {"title": "Revised"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["title"], "Revised")

    def test_patch_notes(self):
        r = authed_client(self.alice).patch(
            f"/api/prep/{self.prep_id}/", {"notes": "Updated notes"}, format="json"
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["notes"], "Updated notes")

    def test_patch_blank_title_returns_400(self):
        r = authed_client(self.alice).patch(
            f"/api/prep/{self.prep_id}/", {"title": ""}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_non_owner_cannot_patch(self):
        r = authed_client(self.bob).patch(
            f"/api/prep/{self.prep_id}/", {"title": "Hijack"}, format="json"
        )
        self.assertEqual(r.status_code, 404)


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class PrepDeleteTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_pdel", "alice_pdel@example.com")
        self.bob = make_user("bob_pdel", "bob_pdel@example.com")
        r = _make_prep(self.alice, title="To delete")
        self.prep_id = r.data["id"]

    def test_owner_can_delete(self):
        r = authed_client(self.alice).delete(f"/api/prep/{self.prep_id}/")
        self.assertEqual(r.status_code, 204)
        self.assertFalse(PrepSession.objects.filter(id=self.prep_id).exists())

    def test_non_owner_cannot_delete(self):
        r = authed_client(self.bob).delete(f"/api/prep/{self.prep_id}/")
        self.assertEqual(r.status_code, 404)
        self.assertTrue(PrepSession.objects.filter(id=self.prep_id).exists())

    def test_delete_cascades_documents_and_notes(self):
        authed_client(self.alice).post(
            f"/api/prep/{self.prep_id}/documents/",
            {"title": "Doc", "file_url": "https://x.com/d.pdf", "file_type": "pdf"},
            format="json",
        )
        authed_client(self.alice).post(
            f"/api/prep/{self.prep_id}/notes/",
            {"content": "Note"},
            format="json",
        )
        authed_client(self.alice).delete(f"/api/prep/{self.prep_id}/")
        self.assertEqual(PrepDocument.objects.filter(prep_session_id=self.prep_id).count(), 0)
        self.assertEqual(PrepNote.objects.filter(prep_session_id=self.prep_id).count(), 0)


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------

class PrepDocumentTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_doc", "alice_doc@example.com")
        self.bob = make_user("bob_doc", "bob_doc@example.com")
        r = _make_prep(self.alice, title="Doc test")
        self.prep_id = r.data["id"]

    def _add_doc(self, user=None, **kwargs):
        data = {
            "title": "Slide deck",
            "file_url": "https://cdn.example.com/deck.pdf",
            "file_type": "pdf",
        }
        data.update(kwargs)
        u = user or self.alice
        return authed_client(u).post(f"/api/prep/{self.prep_id}/documents/", data, format="json")

    def test_add_document(self):
        r = self._add_doc()
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["file_type"], "pdf")
        self.assertEqual(PrepDocument.objects.filter(prep_session_id=self.prep_id).count(), 1)

    def test_all_file_types_accepted(self):
        for ft in ("pdf", "image", "video", "slides"):
            r = self._add_doc(file_type=ft, title=ft)
            self.assertEqual(r.status_code, 201, ft)

    def test_invalid_file_type_returns_400(self):
        r = self._add_doc(file_type="docx")
        self.assertEqual(r.status_code, 400)

    def test_missing_title_returns_400(self):
        r = authed_client(self.alice).post(
            f"/api/prep/{self.prep_id}/documents/",
            {"file_url": "https://x.com/f.pdf", "file_type": "pdf"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_missing_file_url_returns_400(self):
        r = authed_client(self.alice).post(
            f"/api/prep/{self.prep_id}/documents/",
            {"title": "X", "file_type": "pdf"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_non_owner_cannot_add_document(self):
        r = self._add_doc(user=self.bob)
        self.assertEqual(r.status_code, 404)

    def test_delete_document(self):
        r = self._add_doc()
        doc_id = r.data["id"]
        rd = authed_client(self.alice).delete(
            f"/api/prep/{self.prep_id}/documents/{doc_id}/"
        )
        self.assertEqual(rd.status_code, 204)
        self.assertFalse(PrepDocument.objects.filter(id=doc_id).exists())

    def test_non_owner_cannot_delete_document(self):
        r = self._add_doc()
        doc_id = r.data["id"]
        rd = authed_client(self.bob).delete(
            f"/api/prep/{self.prep_id}/documents/{doc_id}/"
        )
        self.assertEqual(rd.status_code, 404)
        self.assertTrue(PrepDocument.objects.filter(id=doc_id).exists())


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

class PrepNoteTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_note", "alice_note@example.com")
        self.bob = make_user("bob_note", "bob_note@example.com")
        r = _make_prep(self.alice, title="Note test")
        self.prep_id = r.data["id"]

    def _add_note(self, user=None, content="Important point", order=0):
        u = user or self.alice
        return authed_client(u).post(
            f"/api/prep/{self.prep_id}/notes/",
            {"content": content, "order": order},
            format="json",
        )

    def test_add_note(self):
        r = self._add_note(content="Clarify indemnity clause")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["content"], "Clarify indemnity clause")
        self.assertEqual(r.data["order"], 0)

    def test_note_order_respected(self):
        self._add_note(content="First", order=1)
        self._add_note(content="Second", order=2)
        r = authed_client(self.alice).get(f"/api/prep/{self.prep_id}/")
        orders = [n["order"] for n in r.data["notes_list"]]
        self.assertEqual(orders, sorted(orders))

    def test_missing_content_returns_400(self):
        r = authed_client(self.alice).post(
            f"/api/prep/{self.prep_id}/notes/", {}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_non_owner_cannot_add_note(self):
        r = self._add_note(user=self.bob)
        self.assertEqual(r.status_code, 404)

    def test_patch_note_content(self):
        r = self._add_note(content="Draft")
        note_id = r.data["id"]
        rp = authed_client(self.alice).patch(
            f"/api/prep/{self.prep_id}/notes/{note_id}/",
            {"content": "Revised"},
            format="json",
        )
        self.assertEqual(rp.status_code, 200)
        self.assertEqual(rp.data["content"], "Revised")
        self.assertEqual(PrepNote.objects.get(id=note_id).content, "Revised")

    def test_patch_note_order(self):
        r = self._add_note(order=5)
        note_id = r.data["id"]
        rp = authed_client(self.alice).patch(
            f"/api/prep/{self.prep_id}/notes/{note_id}/",
            {"order": 10},
            format="json",
        )
        self.assertEqual(rp.status_code, 200)
        self.assertEqual(rp.data["order"], 10)

    def test_patch_blank_content_returns_400(self):
        r = self._add_note()
        note_id = r.data["id"]
        rp = authed_client(self.alice).patch(
            f"/api/prep/{self.prep_id}/notes/{note_id}/",
            {"content": ""},
            format="json",
        )
        self.assertEqual(rp.status_code, 400)

    def test_non_owner_cannot_patch_note(self):
        r = self._add_note()
        note_id = r.data["id"]
        rp = authed_client(self.bob).patch(
            f"/api/prep/{self.prep_id}/notes/{note_id}/",
            {"content": "Hijack"},
            format="json",
        )
        self.assertEqual(rp.status_code, 404)

    def test_delete_note(self):
        r = self._add_note()
        note_id = r.data["id"]
        rd = authed_client(self.alice).delete(
            f"/api/prep/{self.prep_id}/notes/{note_id}/"
        )
        self.assertEqual(rd.status_code, 204)
        self.assertFalse(PrepNote.objects.filter(id=note_id).exists())

    def test_non_owner_cannot_delete_note(self):
        r = self._add_note()
        note_id = r.data["id"]
        rd = authed_client(self.bob).delete(
            f"/api/prep/{self.prep_id}/notes/{note_id}/"
        )
        self.assertEqual(rd.status_code, 404)
        self.assertTrue(PrepNote.objects.filter(id=note_id).exists())


# ---------------------------------------------------------------------------
# Privacy — both parties may create independent prep sessions
# ---------------------------------------------------------------------------

class PrepPrivacyTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_priv", "alice_priv@example.com")
        self.bob = make_user("bob_priv", "bob_priv@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_priv@example.com")
        self.live_session = _make_live_session(self.alice, self.contract)

    def test_both_parties_can_create_prep_for_same_live_session(self):
        r_alice = _make_prep(
            self.alice, title="Alice prep", live_session_id=self.live_session.id
        )
        r_bob = _make_prep(
            self.bob, title="Bob prep", live_session_id=self.live_session.id
        )
        self.assertEqual(r_alice.status_code, 201)
        self.assertEqual(r_bob.status_code, 201)

    def test_alice_cannot_see_bobs_prep(self):
        r_bob = _make_prep(self.bob, title="Bob private")
        bob_prep_id = r_bob.data["id"]
        r = authed_client(self.alice).get(f"/api/prep/{bob_prep_id}/")
        self.assertEqual(r.status_code, 404)

    def test_bob_cannot_see_alices_prep(self):
        r_alice = _make_prep(self.alice, title="Alice private")
        alice_prep_id = r_alice.data["id"]
        r = authed_client(self.bob).get(f"/api/prep/{alice_prep_id}/")
        self.assertEqual(r.status_code, 404)

    def test_alice_list_does_not_include_bobs_prep(self):
        _make_prep(self.alice, title="Mine")
        _make_prep(self.bob, title="Not mine")
        r = authed_client(self.alice).get("/api/prep/")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["title"], "Mine")

    def test_prep_sessions_linked_to_same_live_session_are_independent(self):
        r_a = _make_prep(self.alice, title="Alice", live_session_id=self.live_session.id)
        r_b = _make_prep(self.bob, title="Bob", live_session_id=self.live_session.id)

        # Both exist in DB linked to same live session
        count = PrepSession.objects.filter(live_session=self.live_session).count()
        self.assertEqual(count, 2)

        # But each party sees only their own
        self.assertEqual(len(authed_client(self.alice).get("/api/prep/").data), 1)
        self.assertEqual(len(authed_client(self.bob).get("/api/prep/").data), 1)
