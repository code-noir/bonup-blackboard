# backend/api/tests/test_version_negotiation.py
#
# Version negotiation rules:
# - Only the initiator may create versions.
# - Only the counterparty may sign or reject.
# - Max 3 versions per contract (configurable via max_versions).
# - Contract is locked once a signed version exists.
# - Signing / rejecting a terminal version returns 409.

from django.test import TestCase

from .helpers import authed_client, make_contract, make_user, make_version


class VersionCreateTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.charlie = make_user("charlie", "charlie@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")

    def _create_url(self):
        return f"/api/contracts/{self.contract.id}/versions/"

    def test_initiator_can_create_version(self):
        r = authed_client(self.alice).post(
            self._create_url(), {"content_snapshot": "v1"}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        self.assertIn("version", r.data)

    def test_counterparty_cannot_create_version(self):
        r = authed_client(self.bob).post(
            self._create_url(), {"content_snapshot": "v1"}, format="json"
        )
        self.assertEqual(r.status_code, 403)

    def test_stranger_cannot_create_version(self):
        r = authed_client(self.charlie).post(
            self._create_url(), {"content_snapshot": "v1"}, format="json"
        )
        self.assertEqual(r.status_code, 403)

    def test_missing_content_snapshot_returns_400(self):
        r = authed_client(self.alice).post(self._create_url(), {}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_max_versions_enforced(self):
        # Pre-create max_versions (3) versions directly — bypasses view so we
        # can prime the state without going through API each time.
        for i in range(3):
            make_version(self.contract, self.alice, content_snapshot=f"v{i + 1}")

        # The 4th attempt via API must be rejected.
        r = authed_client(self.alice).post(
            self._create_url(), {"content_snapshot": "v4"}, format="json"
        )
        self.assertEqual(r.status_code, 409)

    def test_cannot_create_version_after_signing(self):
        v = make_version(self.contract, self.alice)
        v.status = "signed"
        v.save(update_fields=["status"])

        r = authed_client(self.alice).post(
            self._create_url(), {"content_snapshot": "v2"}, format="json"
        )
        self.assertEqual(r.status_code, 403)

    def test_warning_included_at_penultimate_version(self):
        """Creating version 2 of 3 should include a warning."""
        make_version(self.contract, self.alice, content_snapshot="v1")
        r = authed_client(self.alice).post(
            self._create_url(), {"content_snapshot": "v2"}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        self.assertIn("warning", r.data)

    def test_warning_included_at_final_version(self):
        """Creating version 3 of 3 should include a final warning."""
        make_version(self.contract, self.alice, content_snapshot="v1")
        make_version(self.contract, self.alice, content_snapshot="v2")
        r = authed_client(self.alice).post(
            self._create_url(), {"content_snapshot": "v3"}, format="json"
        )
        self.assertEqual(r.status_code, 201)
        self.assertIn("warning", r.data)


class VersionSignTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.charlie = make_user("charlie", "charlie@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")
        self.version = make_version(self.contract, self.alice)

    def _sign_url(self):
        return f"/api/contracts/{self.contract.id}/versions/{self.version.id}/sign/"

    def test_counterparty_can_sign_version(self):
        r = authed_client(self.bob).post(self._sign_url())
        self.assertEqual(r.status_code, 200)
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "signed")

    def test_initiator_cannot_sign_version(self):
        r = authed_client(self.alice).post(self._sign_url())
        self.assertEqual(r.status_code, 403)

    def test_stranger_cannot_sign_version(self):
        r = authed_client(self.charlie).post(self._sign_url())
        self.assertEqual(r.status_code, 403)

    def test_cannot_sign_already_signed_version(self):
        self.version.status = "signed"
        self.version.save(update_fields=["status"])
        r = authed_client(self.bob).post(self._sign_url())
        self.assertEqual(r.status_code, 409)

    def test_cannot_sign_rejected_version(self):
        self.version.status = "rejected"
        self.version.save(update_fields=["status"])
        r = authed_client(self.bob).post(self._sign_url())
        self.assertEqual(r.status_code, 409)

    def test_cannot_sign_superseded_version(self):
        self.version.status = "superseded"
        self.version.save(update_fields=["status"])
        r = authed_client(self.bob).post(self._sign_url())
        self.assertEqual(r.status_code, 409)


class VersionRejectTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice", "alice@example.com")
        self.bob = make_user("bob", "bob@example.com")
        self.charlie = make_user("charlie", "charlie@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob@example.com")
        self.version = make_version(self.contract, self.alice)

    def _reject_url(self):
        return f"/api/contracts/{self.contract.id}/versions/{self.version.id}/reject/"

    def test_counterparty_can_reject_version(self):
        r = authed_client(self.bob).post(self._reject_url())
        self.assertEqual(r.status_code, 200)
        self.version.refresh_from_db()
        self.assertEqual(self.version.status, "rejected")

    def test_initiator_cannot_reject_version(self):
        r = authed_client(self.alice).post(self._reject_url())
        self.assertEqual(r.status_code, 403)

    def test_stranger_cannot_reject_version(self):
        r = authed_client(self.charlie).post(self._reject_url())
        self.assertEqual(r.status_code, 403)

    def test_cannot_reject_already_signed_version(self):
        self.version.status = "signed"
        self.version.save(update_fields=["status"])
        r = authed_client(self.bob).post(self._reject_url())
        self.assertEqual(r.status_code, 409)

    def test_cannot_reject_already_rejected_version(self):
        self.version.status = "rejected"
        self.version.save(update_fields=["status"])
        r = authed_client(self.bob).post(self._reject_url())
        self.assertEqual(r.status_code, 409)

    def test_warning_on_final_version_rejection(self):
        """Rejecting the final allowed version should include a 'cannot proceed' warning."""
        # Use a contract with max_versions=1 so the single version is the last allowed.
        contract = make_contract(self.alice, counterparty_email="bob@example.com", max_versions=1)
        from backend.contracts.models import ContractVersion
        version = ContractVersion.objects.create(
            contract=contract,
            version_number=1,
            created_by=self.alice,
            content_snapshot="final version",
            status="draft",
        )
        url = f"/api/contracts/{contract.id}/versions/{version.id}/reject/"
        r = authed_client(self.bob).post(url)
        self.assertEqual(r.status_code, 200)
        self.assertIn("warning", r.data)
