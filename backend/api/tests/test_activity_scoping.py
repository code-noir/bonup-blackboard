# backend/api/tests/test_activity_scoping.py
#
# B4 — Activity contract-id filter scoping.
#
# GET /api/activity/ applies _party_q(user) as its base filter before any
# additional query params. When a user passes ?contract_id=<id> for a
# contract they are not a party to, the _party_q gate excludes that
# contract's activity from the base queryset, so the contract_id filter
# narrows over an already-empty set — returning an empty result.
#
# This verifies that the filter cannot be used to enumerate or read
# activity from contracts the caller has no party relationship with.

from django.test import TestCase

from backend.activity.models import ContractActivity
from .helpers import authed_client, make_contract, make_user


class ActivityContractIdFilterScopingTests(TestCase):
    """
    GET /api/activity/?contract_id=<id>

    When the requested contract_id belongs to a contract the caller is not
    a party to, the response is an empty result — not a 403 and not leaking
    any activity records from that contract.
    """

    def setUp(self):
        self.alice = make_user("alice_as", "alice_as@example.com")
        self.stranger = make_user("stranger_as", "stranger_as@example.com")

        # Stranger's contract — Alice has no party relationship to it.
        self.stranger_contract = make_contract(
            self.stranger, "other_as@example.com"
        )
        # Seed activity on the stranger's contract.
        ContractActivity.objects.create(
            contract=self.stranger_contract,
            user=self.stranger,
            activity_type="contract_created",
            description="Stranger's contract created.",
        )

        self.client = authed_client(self.alice)

    def test_contract_id_filter_for_non_party_contract_returns_empty(self):
        """
        Alice is not a party to the stranger's contract.
        Passing ?contract_id=<stranger_contract_id> returns an empty result —
        no activity is leaked and no error is raised.
        """
        response = self.client.get(
            f"/api/activity/?contract_id={self.stranger_contract.id}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(response.data["results"], [])
