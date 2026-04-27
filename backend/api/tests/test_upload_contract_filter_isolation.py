# backend/api/tests/test_upload_contract_filter_isolation.py
#
# B3 — Upload contract-filter isolation.
#
# The upload list base query is filter(user=request.user). The optional
# ?contract_id= filter is applied additively within that owner-scoped set.
#
# Scenario: two parties to the same contract each tag their own upload with
# that contract's ID. Each user's filtered list must return only their own
# upload — the party filter must not leak the other user's uploads.

from django.test import TestCase

from backend.uploads.models import Upload
from .helpers import authed_client, make_contract, make_user

UPLOAD_URL = "/api/uploads/"


def make_upload(user, contract=None):
    return Upload.objects.create(
        user=user,
        file_url="https://example.com/file.pdf",
        file_name="file.pdf",
        file_type="pdf",
        file_size=1024,
        storage_key="uploads/test/file.pdf",
        related_contract=contract,
    )


class UploadContractFilterIsolationTests(TestCase):
    """
    GET /api/uploads/?contract_id=<id>

    When both the initiator and the counterparty have uploads tagged to the
    same contract, each user's filtered list returns only their own upload.
    The ?contract_id filter cannot surface another party's uploads.
    """

    def setUp(self):
        self.initiator = make_user("init_filter", "init_filter@example.com")
        self.counterparty = make_user("cp_filter", "cp_filter@example.com")
        self.contract = make_contract(self.initiator, self.counterparty.email)

        # Both parties tag an upload to the same contract.
        self.initiator_upload = make_upload(self.initiator, contract=self.contract)
        self.counterparty_upload = make_upload(self.counterparty, contract=self.contract)

    def test_contract_id_filter_returns_only_own_uploads_not_other_partys(self):
        """
        Initiator's filtered list contains only the initiator's upload.
        Counterparty's filtered list contains only the counterparty's upload.
        Neither list leaks the other party's upload.
        """
        url = f"{UPLOAD_URL}?contract_id={self.contract.id}"

        initiator_response = authed_client(self.initiator).get(url)
        self.assertEqual(initiator_response.status_code, 200)
        initiator_ids = {item["id"] for item in initiator_response.data}
        self.assertIn(str(self.initiator_upload.id), initiator_ids)
        self.assertNotIn(str(self.counterparty_upload.id), initiator_ids)

        counterparty_response = authed_client(self.counterparty).get(url)
        self.assertEqual(counterparty_response.status_code, 200)
        counterparty_ids = {item["id"] for item in counterparty_response.data}
        self.assertIn(str(self.counterparty_upload.id), counterparty_ids)
        self.assertNotIn(str(self.initiator_upload.id), counterparty_ids)
