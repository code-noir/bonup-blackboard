# backend/api/tests/test_sol_pdf.py
#
# Tests for Sol PDF export endpoints.

import io
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backend.sol.models import Sol, SolMember, SolContract, SolPayout, SolContribution, SolNote, SolTip

from .helpers import authed_client, make_subscription, make_user


# ---------------------------------------------------------------------------
# Helpers (duplicated locally to keep this file self-contained)
# ---------------------------------------------------------------------------

def make_sol(manager, **kwargs):
    defaults = {
        "name": "PDF Test Sol",
        "description": "A Sol group used for PDF export testing.",
        "frequency": "monthly",
        "contribution_amount": Decimal("200.00"),
        "currency": "USD",
        "tip_expectation": Decimal("25.00"),
        "start_date": timezone.now().date(),
        "primary_manager": manager,
    }
    defaults.update(kwargs)
    return Sol.objects.create(**defaults)


def make_member(sol, hand_number, name, email, bonup_user=None):
    return SolMember.objects.create(
        sol=sol,
        bonup_user=bonup_user,
        name=name,
        email=email,
        phone="555-0000",
        hand_number=hand_number,
        is_bonup_member=(bonup_user is not None),
    )


def make_contract(sol, member):
    return SolContract.objects.create(
        sol=sol,
        member=member,
        agreed_contribution_amount=sol.contribution_amount,
        agreed_hand_number=member.hand_number,
        agreed_tip_amount=sol.tip_expectation,
        contract_text=f"SOL PARTICIPATION AGREEMENT\nMember: {member.name}\nHand Number: {member.hand_number}\nbonUP is a record-keeping platform only.",
    )


def make_payout(sol, cycle_number, hand_number, recipient, expected_date=None):
    if expected_date is None:
        expected_date = timezone.now().date()
    active = sol.members.filter(is_active=True).count()
    return SolPayout.objects.create(
        sol=sol,
        cycle_number=cycle_number,
        hand_number=hand_number,
        recipient=recipient,
        expected_date=expected_date,
        expected_amount=sol.contribution_amount * max(active - 1, 1),
    )


# ---------------------------------------------------------------------------
# Manager PDF export
# ---------------------------------------------------------------------------

class SolManagerExportTests(TestCase):

    def setUp(self):
        self.manager = make_user("mgr_pdf", "mgr_pdf@example.com")
        make_subscription(self.manager)
        self.sol = make_sol(self.manager)
        self.m1 = make_member(self.sol, 1, "Alice Dupont", "alice_pdf@example.com")
        self.m2 = make_member(self.sol, 2, "Bob Michel", "bob_pdf@example.com")
        self.payout = make_payout(self.sol, 1, 1, self.m1)
        SolContribution.objects.create(
            sol=self.sol, payout=self.payout, member=self.m2,
            amount=Decimal("200.00"), due_date=self.payout.expected_date, status="paid",
        )
        SolNote.objects.create(sol=self.sol, author=self.manager, text="Bob always pays on time.")
        SolTip.objects.create(
            sol=self.sol, from_member=self.m2, to_manager=self.manager,
            amount=Decimal("25.00"), currency="USD", note="Thank you!",
        )

    def test_manager_export_returns_200(self):
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/export/pdf/")
        self.assertEqual(r.status_code, 200)

    def test_manager_export_content_type_is_pdf(self):
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/export/pdf/")
        self.assertEqual(r["Content-Type"], "application/pdf")

    def test_manager_export_content_disposition_filename(self):
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/export/pdf/")
        self.assertIn("attachment", r["Content-Disposition"])
        self.assertIn(self.sol.sol_id, r["Content-Disposition"])
        self.assertIn(".pdf", r["Content-Disposition"])

    def test_manager_export_produces_nonempty_pdf(self):
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/export/pdf/")
        content = b"".join(r.streaming_content) if hasattr(r, "streaming_content") else r.content
        self.assertGreater(len(content), 1000)
        # PDF magic bytes
        self.assertTrue(content.startswith(b"%PDF"))

    def test_non_manager_cannot_export(self):
        stranger = make_user("stranger_pdf", "stranger_pdf@example.com")
        r = authed_client(stranger).get(f"/api/sol/{self.sol.id}/export/pdf/")
        self.assertEqual(r.status_code, 403)

    def test_co_manager_can_export(self):
        co = make_user("co_pdf", "co_pdf@example.com")
        make_subscription(co)
        self.sol.co_manager = co
        self.sol.save()
        r = authed_client(co).get(f"/api/sol/{self.sol.id}/export/pdf/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")

    def test_export_with_empty_sol(self):
        """Sol with no payouts or contributions should still export cleanly."""
        empty_sol = make_sol(self.manager, name="Empty Sol")
        r = authed_client(self.manager).get(f"/api/sol/{empty_sol.id}/export/pdf/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")

    def test_export_with_rearranged_payout(self):
        payout2 = make_payout(self.sol, 1, 2, self.m2)
        payout2.was_rearranged = True
        payout2.rearranged_reason = "Alice requested swap"
        payout2.original_recipient = self.m1
        payout2.rearranged_by = self.manager
        payout2.save()
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/export/pdf/")
        self.assertEqual(r.status_code, 200)

    def test_unauthenticated_export_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(f"/api/sol/{self.sol.id}/export/pdf/")
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# Member PDF export
# ---------------------------------------------------------------------------

class SolMemberExportTests(TestCase):

    def setUp(self):
        self.manager = make_user("mgr_mem_pdf", "mgr_mem_pdf@example.com")
        make_subscription(self.manager)
        self.member_user = make_user("member_mem_pdf", "member_mem_pdf@example.com")
        make_subscription(self.member_user)
        self.sol = make_sol(self.manager)
        self.m1 = make_member(self.sol, 1, "Alice PDF", "alice_mp@example.com")
        self.m2 = make_member(self.sol, 2, "Bob PDF", "member_mem_pdf@example.com",
                              bonup_user=self.member_user)
        make_contract(self.sol, self.m2)

        self.payout = make_payout(self.sol, 1, 1, self.m1)
        SolContribution.objects.create(
            sol=self.sol, payout=self.payout, member=self.m2,
            amount=Decimal("200.00"), due_date=self.payout.expected_date, status="paid",
            paid_date=timezone.now().date(),
        )

    def test_member_export_returns_200(self):
        r = authed_client(self.member_user).get(f"/api/sol/memberships/{self.sol.id}/export/pdf/")
        self.assertEqual(r.status_code, 200)

    def test_member_export_content_type_is_pdf(self):
        r = authed_client(self.member_user).get(f"/api/sol/memberships/{self.sol.id}/export/pdf/")
        self.assertEqual(r["Content-Type"], "application/pdf")

    def test_member_export_content_disposition(self):
        r = authed_client(self.member_user).get(f"/api/sol/memberships/{self.sol.id}/export/pdf/")
        cd = r["Content-Disposition"]
        self.assertIn("attachment", cd)
        self.assertIn(self.sol.sol_id, cd)
        self.assertIn("hand2", cd)
        self.assertIn(".pdf", cd)

    def test_member_export_produces_valid_pdf(self):
        r = authed_client(self.member_user).get(f"/api/sol/memberships/{self.sol.id}/export/pdf/")
        content = b"".join(r.streaming_content) if hasattr(r, "streaming_content") else r.content
        self.assertGreater(len(content), 500)
        self.assertTrue(content.startswith(b"%PDF"))

    def test_non_member_cannot_export_member_pdf(self):
        stranger = make_user("stranger_mem_pdf", "stranger_mem_pdf@example.com")
        r = authed_client(stranger).get(f"/api/sol/memberships/{self.sol.id}/export/pdf/")
        self.assertEqual(r.status_code, 403)

    def test_manager_cannot_use_member_export_without_membership(self):
        """Manager who is NOT a SolMember should be denied the member export endpoint."""
        r = authed_client(self.manager).get(f"/api/sol/memberships/{self.sol.id}/export/pdf/")
        self.assertEqual(r.status_code, 403)

    def test_member_export_with_upcoming_payout(self):
        upcoming = make_payout(self.sol, 1, 2, self.m2,
                               expected_date=timezone.now().date())
        r = authed_client(self.member_user).get(f"/api/sol/memberships/{self.sol.id}/export/pdf/")
        self.assertEqual(r.status_code, 200)

    def test_member_export_without_contract(self):
        """Member without a contract record should still export (contract section omitted)."""
        no_contract_user = make_user("no_contract_pdf", "no_contract_pdf@example.com")
        make_subscription(no_contract_user)
        m3 = make_member(self.sol, 3, "No Contract", "no_contract_pdf@example.com",
                         bonup_user=no_contract_user)
        r = authed_client(no_contract_user).get(f"/api/sol/memberships/{self.sol.id}/export/pdf/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")

    def test_unauthenticated_member_export_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(f"/api/sol/memberships/{self.sol.id}/export/pdf/")
        self.assertEqual(r.status_code, 401)
