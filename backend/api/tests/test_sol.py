# backend/api/tests/test_sol.py
#
# Tests for the Sol (sou-sou / tontine / susu) domain.

from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backend.billing.models import SubscriptionPlan, UserSubscription
from backend.sol.models import Sol, SolMember, SolContract, SolPayout, SolContribution, SolTip, SolNote

from .helpers import authed_client, make_subscription, make_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_sol(manager, **kwargs):
    defaults = {
        "name": "Test Sol",
        "frequency": "monthly",
        "contribution_amount": Decimal("100.00"),
        "currency": "USD",
        "tip_expectation": Decimal("20.00"),
        "start_date": timezone.now().date(),
        "primary_manager": manager,
    }
    defaults.update(kwargs)
    return Sol.objects.create(**defaults)


def make_member(sol, hand_number=1, name="Alice", email="alice@example.com", phone="555-1234", **kwargs):
    return SolMember.objects.create(
        sol=sol,
        name=name,
        email=email,
        phone=phone,
        hand_number=hand_number,
        **kwargs,
    )


def make_payout(sol, cycle_number=1, hand_number=1, recipient=None, expected_date=None):
    if expected_date is None:
        expected_date = timezone.now().date()
    active_count = sol.members.filter(is_active=True).count()
    return SolPayout.objects.create(
        sol=sol,
        cycle_number=cycle_number,
        hand_number=hand_number,
        recipient=recipient,
        expected_date=expected_date,
        expected_amount=sol.contribution_amount * max(active_count - 1, 1),
    )


# ---------------------------------------------------------------------------
# Gate tests
# ---------------------------------------------------------------------------

class SolGateTests(TestCase):

    def setUp(self):
        self.manager = make_user("manager_gate", "manager_gate@example.com")
        self.basic_user = make_user("basic_gate", "basic_gate@example.com")

        # Give manager a Sol-eligible subscription
        make_subscription(self.manager)

        # Give basic_user a non-Sol plan
        plan, _ = SubscriptionPlan.objects.get_or_create(
            slug="starter",
            defaults={
                "display_name": "Starter",
                "price_monthly": Decimal("10.00"),
                "has_sol": False,
            },
        )
        UserSubscription.objects.create(
            user=self.basic_user,
            plan=plan,
            status="active",
            billing_period="monthly",
            current_period_start=timezone.now(),
        )

    def test_no_subscription_cannot_create_sol(self):
        user = make_user("nosub_gate", "nosub_gate@example.com")
        r = authed_client(user).post("/api/sol/", {
            "name": "My Sol", "frequency": "monthly",
            "contribution_amount": "100", "start_date": "2026-05-01",
        }, format="json")
        self.assertEqual(r.status_code, 403)

    def test_non_sol_plan_cannot_create_sol(self):
        r = authed_client(self.basic_user).post("/api/sol/", {
            "name": "My Sol", "frequency": "monthly",
            "contribution_amount": "100", "start_date": "2026-05-01",
        }, format="json")
        self.assertEqual(r.status_code, 403)

    def test_sol_eligible_plan_can_create_sol(self):
        r = authed_client(self.manager).post("/api/sol/", {
            "name": "My Sol", "frequency": "monthly",
            "contribution_amount": "100", "start_date": "2026-05-01",
        }, format="json")
        self.assertEqual(r.status_code, 201)


# ---------------------------------------------------------------------------
# Sol Creation
# ---------------------------------------------------------------------------

class SolCreateTests(TestCase):

    def setUp(self):
        self.manager = make_user("mgr_create", "mgr_create@example.com")
        make_subscription(self.manager)

    def test_create_sol_returns_201(self):
        r = authed_client(self.manager).post("/api/sol/", {
            "name": "Haitian Sol Group",
            "frequency": "monthly",
            "contribution_amount": "500.00",
            "tip_expectation": "50.00",
            "start_date": "2026-05-01",
            "currency": "HTG",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["name"], "Haitian Sol Group")
        self.assertEqual(r.data["currency"], "HTG")
        self.assertTrue(r.data["sol_id"].startswith("SOL-"))

    def test_create_sol_missing_required_fields(self):
        r = authed_client(self.manager).post("/api/sol/", {
            "name": "Incomplete Sol",
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_list_sol_groups(self):
        make_sol(self.manager, name="Sol A")
        make_sol(self.manager, name="Sol B")
        r = authed_client(self.manager).get("/api/sol/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["results"]), 2)

    def test_sol_detail_forbidden_for_non_manager(self):
        sol = make_sol(self.manager)
        stranger = make_user("stranger_create", "stranger_create@example.com")
        r = authed_client(stranger).get(f"/api/sol/{sol.id}/")
        self.assertEqual(r.status_code, 403)

    def test_patch_sol_status(self):
        sol = make_sol(self.manager)
        r = authed_client(self.manager).patch(f"/api/sol/{sol.id}/", {"status": "paused"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "paused")

    def test_sol_id_format(self):
        sol = make_sol(self.manager)
        self.assertRegex(sol.sol_id, r"^SOL-[0-9A-F]{8}$")


# ---------------------------------------------------------------------------
# Member Addition & Contract Generation
# ---------------------------------------------------------------------------

class SolMemberTests(TestCase):

    def setUp(self):
        self.manager = make_user("mgr_member", "mgr_member@example.com")
        make_subscription(self.manager)
        self.sol = make_sol(self.manager)

    def test_add_member_creates_contract(self):
        r = authed_client(self.manager).post(f"/api/sol/{self.sol.id}/members/", {
            "name": "Alice Joseph",
            "email": "alice_joseph@example.com",
            "phone": "555-0001",
            "hand_number": 1,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["name"], "Alice Joseph")
        self.assertEqual(r.data["hand_number"], 1)

        # Contract auto-created
        member = SolMember.objects.get(sol=self.sol, hand_number=1)
        self.assertTrue(SolContract.objects.filter(member=member).exists())

    def test_contract_text_contains_key_info(self):
        authed_client(self.manager).post(f"/api/sol/{self.sol.id}/members/", {
            "name": "Bob Toussaint",
            "email": "bob_tss@example.com",
            "phone": "555-0002",
            "hand_number": 2,
        }, format="json")
        member = SolMember.objects.get(sol=self.sol, hand_number=2)
        contract = SolContract.objects.get(member=member)
        self.assertIn("Bob Toussaint", contract.contract_text)
        self.assertIn("Hand Number: 2", contract.contract_text)
        self.assertIn("bonUP is a record-keeping", contract.contract_text)
        self.assertIn("100.00", contract.contract_text)

    def test_duplicate_hand_number_rejected(self):
        make_member(self.sol, hand_number=1)
        r = authed_client(self.manager).post(f"/api/sol/{self.sol.id}/members/", {
            "name": "Duplicate",
            "email": "dup@example.com",
            "phone": "555-9999",
            "hand_number": 1,
        }, format="json")
        self.assertEqual(r.status_code, 400)

    def test_deactivate_member(self):
        member = make_member(self.sol, hand_number=1)
        r = authed_client(self.manager).delete(f"/api/sol/{self.sol.id}/members/{member.id}/")
        self.assertEqual(r.status_code, 200)
        member.refresh_from_db()
        self.assertFalse(member.is_active)

    def test_get_member_contract(self):
        authed_client(self.manager).post(f"/api/sol/{self.sol.id}/members/", {
            "name": "Carol Pierre",
            "email": "carol_p@example.com",
            "phone": "555-0003",
            "hand_number": 3,
        }, format="json")
        member = SolMember.objects.get(sol=self.sol, hand_number=3)
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/members/{member.id}/contract/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["hand_number"], 3)
        self.assertIn("contract_text", r.data)

    def test_bonup_user_linked_on_email_match(self):
        bonup_user = make_user("bonup_member", "bonup_member@example.com")
        make_subscription(bonup_user)
        r = authed_client(self.manager).post(f"/api/sol/{self.sol.id}/members/", {
            "name": "BonUP Member",
            "email": "bonup_member@example.com",
            "phone": "555-0099",
            "hand_number": 5,
        }, format="json")
        self.assertEqual(r.status_code, 201)
        member = SolMember.objects.get(sol=self.sol, hand_number=5)
        self.assertEqual(member.bonup_user, bonup_user)
        self.assertTrue(member.is_bonup_member)

    def test_bonup_member_without_subscription_blocked(self):
        no_sub_user = make_user("nosub_member", "nosub_member@example.com")
        r = authed_client(self.manager).post(f"/api/sol/{self.sol.id}/members/", {
            "name": "No Sub",
            "email": "nosub_member@example.com",
            "phone": "555-0100",
            "hand_number": 6,
        }, format="json")
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------------------
# Payout Creation & Contribution Tracking
# ---------------------------------------------------------------------------

class SolPayoutTests(TestCase):

    def setUp(self):
        self.manager = make_user("mgr_payout", "mgr_payout@example.com")
        make_subscription(self.manager)
        self.sol = make_sol(self.manager)
        self.m1 = make_member(self.sol, hand_number=1, name="Alice", email="alice_p@example.com")
        self.m2 = make_member(self.sol, hand_number=2, name="Bob", email="bob_p@example.com")
        self.m3 = make_member(self.sol, hand_number=3, name="Carol", email="carol_p@example.com")

    def test_create_payout_returns_201(self):
        r = authed_client(self.manager).post(f"/api/sol/{self.sol.id}/payouts/", {
            "expected_date": "2026-05-01",
        }, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["hand_number"], 1)
        self.assertEqual(r.data["recipient_name"], "Alice")

    def test_payout_creates_contributions_for_non_recipients(self):
        authed_client(self.manager).post(f"/api/sol/{self.sol.id}/payouts/", {
            "expected_date": "2026-05-01",
        }, format="json")
        payout = SolPayout.objects.get(sol=self.sol, hand_number=1)
        contributions = SolContribution.objects.filter(payout=payout)
        # 3 members, 1 is recipient — 2 contributions
        self.assertEqual(contributions.count(), 2)
        # Recipient (m1) should not have a contribution
        self.assertFalse(contributions.filter(member=self.m1).exists())
        self.assertTrue(contributions.filter(member=self.m2).exists())
        self.assertTrue(contributions.filter(member=self.m3).exists())

    def test_second_payout_goes_to_hand_2(self):
        authed_client(self.manager).post(f"/api/sol/{self.sol.id}/payouts/", {"expected_date": "2026-05-01"}, format="json")
        # Mark first as paid so cycle doesn't stall
        p1 = SolPayout.objects.get(sol=self.sol, hand_number=1)
        p1.status = "paid"
        p1.save()
        r = authed_client(self.manager).post(f"/api/sol/{self.sol.id}/payouts/", {"expected_date": "2026-06-01"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["hand_number"], 2)

    def test_payout_expected_amount(self):
        r = authed_client(self.manager).post(f"/api/sol/{self.sol.id}/payouts/", {
            "expected_date": "2026-05-01",
        }, format="json")
        # 3 members, contribution=100, recipient doesn't pay → 2 × 100 = 200
        self.assertEqual(r.data["expected_amount"], "200.00")

    def test_payout_id_format(self):
        r = authed_client(self.manager).post(f"/api/sol/{self.sol.id}/payouts/", {
            "expected_date": "2026-05-01",
        }, format="json")
        self.assertRegex(r.data["payout_id"], r"^PAY-[0-9A-F]{8}$")

    def test_list_payouts(self):
        make_payout(self.sol, cycle_number=1, hand_number=1, recipient=self.m1)
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/payouts/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["results"]), 1)

    def test_mark_payout_paid(self):
        payout = make_payout(self.sol, cycle_number=1, hand_number=1, recipient=self.m1)
        r = authed_client(self.manager).patch(f"/api/sol/{self.sol.id}/payouts/{payout.id}/", {
            "status": "paid",
            "actual_amount": "200.00",
            "paid_date": "2026-05-02",
        }, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "paid")
        self.m1.refresh_from_db()
        self.assertTrue(self.m1.has_received)

    def test_single_cycle_sol_cannot_create_second_cycle(self):
        # Complete first cycle
        for m, hand in [(self.m1, 1), (self.m2, 2), (self.m3, 3)]:
            p = make_payout(self.sol, cycle_number=1, hand_number=hand, recipient=m)
            p.status = "paid"
            p.save()
        r = authed_client(self.manager).post(f"/api/sol/{self.sol.id}/payouts/", {
            "expected_date": "2026-09-01",
        }, format="json")
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# Contribution Tracking
# ---------------------------------------------------------------------------

class SolContributionTests(TestCase):

    def setUp(self):
        self.manager = make_user("mgr_contrib", "mgr_contrib@example.com")
        make_subscription(self.manager)
        self.sol = make_sol(self.manager)
        self.m1 = make_member(self.sol, hand_number=1, name="Alice", email="alice_c@example.com")
        self.m2 = make_member(self.sol, hand_number=2, name="Bob", email="bob_c@example.com")
        self.payout = make_payout(self.sol, cycle_number=1, hand_number=1, recipient=self.m1)
        # Contribution for m2 (non-recipient)
        self.contrib = SolContribution.objects.create(
            sol=self.sol, payout=self.payout, member=self.m2,
            amount=Decimal("100.00"), due_date=self.payout.expected_date,
        )

    def test_mark_contribution_paid(self):
        url = f"/api/sol/{self.sol.id}/payouts/{self.payout.id}/contributions/{self.contrib.id}/"
        r = authed_client(self.manager).post(url, {"status": "paid", "paid_date": "2026-05-01"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["status"], "paid")

    def test_mark_contribution_late(self):
        url = f"/api/sol/{self.sol.id}/payouts/{self.payout.id}/contributions/{self.contrib.id}/"
        r = authed_client(self.manager).post(url, {"status": "late"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.contrib.refresh_from_db()
        self.assertEqual(self.contrib.status, "late")

    def test_mark_contribution_missed(self):
        url = f"/api/sol/{self.sol.id}/payouts/{self.payout.id}/contributions/{self.contrib.id}/"
        r = authed_client(self.manager).post(url, {"status": "missed", "notes": "Member unreachable"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.contrib.refresh_from_db()
        self.assertEqual(self.contrib.status, "missed")
        self.assertEqual(self.contrib.notes, "Member unreachable")

    def test_invalid_status_rejected(self):
        url = f"/api/sol/{self.sol.id}/payouts/{self.payout.id}/contributions/{self.contrib.id}/"
        r = authed_client(self.manager).post(url, {"status": "bogus"}, format="json")
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# Payout Rearrangement
# ---------------------------------------------------------------------------

class SolRearrangeTests(TestCase):

    def setUp(self):
        self.manager = make_user("mgr_rearrange", "mgr_rearrange@example.com")
        make_subscription(self.manager)
        self.sol = make_sol(self.manager)
        self.m1 = make_member(self.sol, hand_number=1, name="Alice", email="alice_r@example.com")
        self.m2 = make_member(self.sol, hand_number=2, name="Bob", email="bob_r@example.com")
        self.m3 = make_member(self.sol, hand_number=3, name="Carol", email="carol_r@example.com")
        self.payout = make_payout(self.sol, cycle_number=1, hand_number=1, recipient=self.m1)
        SolContribution.objects.bulk_create([
            SolContribution(sol=self.sol, payout=self.payout, member=self.m2,
                            amount=Decimal("100.00"), due_date=self.payout.expected_date),
            SolContribution(sol=self.sol, payout=self.payout, member=self.m3,
                            amount=Decimal("100.00"), due_date=self.payout.expected_date),
        ])

    def test_rearrange_swaps_recipient(self):
        r = authed_client(self.manager).post(
            f"/api/sol/{self.sol.id}/payouts/{self.payout.id}/rearrange/",
            {"new_recipient_id": str(self.m2.id), "reason": "Alice requested swap"},
            format="json",
        )
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["recipient_name"], "Bob")
        self.assertTrue(r.data["was_rearranged"])
        self.assertEqual(r.data["rearranged_reason"], "Alice requested swap")

    def test_rearrange_fixes_contributions(self):
        authed_client(self.manager).post(
            f"/api/sol/{self.sol.id}/payouts/{self.payout.id}/rearrange/",
            {"new_recipient_id": str(self.m2.id), "reason": "Swap"},
            format="json",
        )
        # Bob (new recipient) should NOT have a contribution
        self.assertFalse(SolContribution.objects.filter(payout=self.payout, member=self.m2).exists())
        # Alice (original recipient) should now have a contribution
        self.assertTrue(SolContribution.objects.filter(payout=self.payout, member=self.m1).exists())

    def test_rearrange_requires_new_recipient(self):
        r = authed_client(self.manager).post(
            f"/api/sol/{self.sol.id}/payouts/{self.payout.id}/rearrange/",
            {"reason": "Missing recipient ID"},
            format="json",
        )
        self.assertEqual(r.status_code, 400)

    def test_cannot_rearrange_paid_payout(self):
        self.payout.status = "paid"
        self.payout.save()
        r = authed_client(self.manager).post(
            f"/api/sol/{self.sol.id}/payouts/{self.payout.id}/rearrange/",
            {"new_recipient_id": str(self.m2.id)},
            format="json",
        )
        self.assertEqual(r.status_code, 400)


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class SolDashboardTests(TestCase):

    def setUp(self):
        self.manager = make_user("mgr_dash", "mgr_dash@example.com")
        make_subscription(self.manager)
        self.sol = make_sol(self.manager)
        self.m1 = make_member(self.sol, hand_number=1, name="Alice", email="alice_d@example.com")
        self.m2 = make_member(self.sol, hand_number=2, name="Bob", email="bob_d@example.com")
        self.payout = make_payout(self.sol, cycle_number=1, hand_number=1, recipient=self.m1)
        SolContribution.objects.create(
            sol=self.sol, payout=self.payout, member=self.m2,
            amount=Decimal("100.00"), due_date=self.payout.expected_date, status="paid",
        )

    def test_dashboard_returns_200(self):
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/dashboard/")
        self.assertEqual(r.status_code, 200)

    def test_dashboard_has_expected_fields(self):
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/dashboard/")
        for key in ["total_members", "members_received", "completion_percentage",
                    "current_payout", "contribution_summary", "total_payouts", "paid_payouts"]:
            self.assertIn(key, r.data)

    def test_dashboard_total_members(self):
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/dashboard/")
        self.assertEqual(r.data["total_members"], 2)

    def test_dashboard_contribution_summary_paid(self):
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/dashboard/")
        summary = r.data["contribution_summary"]
        self.assertEqual(summary["paid_count"], 1)
        self.assertEqual(summary["fund_collected"], "100.00")

    def test_dashboard_completion_percentage_zero_at_start(self):
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/dashboard/")
        self.assertEqual(r.data["completion_percentage"], 0.0)

    def test_dashboard_completion_after_one_payout(self):
        self.m1.has_received = True
        self.m1.save()
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/dashboard/")
        self.assertEqual(r.data["completion_percentage"], 50.0)

    def test_non_manager_cannot_see_dashboard(self):
        stranger = make_user("stranger_dash", "stranger_dash@example.com")
        r = authed_client(stranger).get(f"/api/sol/{self.sol.id}/dashboard/")
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------------------
# Notes
# ---------------------------------------------------------------------------

class SolNotesTests(TestCase):

    def setUp(self):
        self.manager = make_user("mgr_notes", "mgr_notes@example.com")
        make_subscription(self.manager)
        self.sol = make_sol(self.manager)

    def test_add_note(self):
        r = authed_client(self.manager).post(
            f"/api/sol/{self.sol.id}/notes/",
            {"text": "Member 2 always pays late."},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["text"], "Member 2 always pays late.")

    def test_list_notes(self):
        SolNote.objects.create(sol=self.sol, author=self.manager, text="Note 1")
        SolNote.objects.create(sol=self.sol, author=self.manager, text="Note 2")
        r = authed_client(self.manager).get(f"/api/sol/{self.sol.id}/notes/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["results"]), 2)

    def test_empty_note_rejected(self):
        r = authed_client(self.manager).post(
            f"/api/sol/{self.sol.id}/notes/", {"text": ""}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_non_manager_cannot_view_notes(self):
        stranger = make_user("stranger_notes", "stranger_notes@example.com")
        r = authed_client(stranger).get(f"/api/sol/{self.sol.id}/notes/")
        self.assertEqual(r.status_code, 403)


# ---------------------------------------------------------------------------
# Member self-service views
# ---------------------------------------------------------------------------

class SolMembershipTests(TestCase):

    def setUp(self):
        self.manager = make_user("mgr_ms", "mgr_ms@example.com")
        make_subscription(self.manager)
        self.member_user = make_user("member_ms", "member_ms@example.com")
        make_subscription(self.member_user)
        self.sol = make_sol(self.manager)
        self.member = SolMember.objects.create(
            sol=self.sol,
            bonup_user=self.member_user,
            name="Member MS",
            email="member_ms@example.com",
            phone="555-8888",
            hand_number=2,
            is_bonup_member=True,
        )
        SolContract.objects.create(
            sol=self.sol,
            member=self.member,
            agreed_contribution_amount=self.sol.contribution_amount,
            agreed_hand_number=2,
            agreed_tip_amount=self.sol.tip_expectation,
            contract_text="Test contract text.",
        )

    def test_list_memberships(self):
        r = authed_client(self.member_user).get("/api/sol/memberships/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["results"]), 1)
        self.assertEqual(r.data["results"][0]["hand_number"], 2)

    def test_membership_detail(self):
        r = authed_client(self.member_user).get(f"/api/sol/memberships/{self.sol.id}/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["hand_number"], 2)
        self.assertIn("contract", r.data)
        self.assertIsNotNone(r.data["contract"])

    def test_non_member_cannot_see_membership_detail(self):
        stranger = make_user("stranger_ms", "stranger_ms@example.com")
        r = authed_client(stranger).get(f"/api/sol/memberships/{self.sol.id}/")
        self.assertEqual(r.status_code, 403)

    def test_member_cannot_see_other_members_info(self):
        # Member sees their Sol detail, not other members' data
        r = authed_client(self.member_user).get(f"/api/sol/memberships/{self.sol.id}/")
        self.assertNotIn("members", r.data)
        self.assertNotIn("notes", r.data)

    def test_membership_shows_contribution_history(self):
        payout = make_payout(self.sol, cycle_number=1, hand_number=1,
                             recipient=make_member(self.sol, hand_number=1, name="X", email="x_ms@example.com"))
        SolContribution.objects.create(
            sol=self.sol, payout=payout, member=self.member,
            amount=Decimal("100.00"), due_date=payout.expected_date, status="paid",
        )
        r = authed_client(self.member_user).get(f"/api/sol/memberships/{self.sol.id}/")
        self.assertEqual(len(r.data["contribution_history"]), 1)
        self.assertEqual(r.data["contribution_history"][0]["status"], "paid")


# ---------------------------------------------------------------------------
# Tips
# ---------------------------------------------------------------------------

class SolTipTests(TestCase):

    def setUp(self):
        self.manager = make_user("mgr_tip", "mgr_tip@example.com")
        make_subscription(self.manager)
        self.tipper = make_user("tipper_tip", "tipper_tip@example.com")
        make_subscription(self.tipper)
        self.sol = make_sol(self.manager)
        self.member = SolMember.objects.create(
            sol=self.sol,
            bonup_user=self.tipper,
            name="Tipper",
            email="tipper_tip@example.com",
            phone="555-7777",
            hand_number=1,
            is_bonup_member=True,
        )

    def test_member_can_record_tip(self):
        r = authed_client(self.tipper).post(
            f"/api/sol/{self.sol.id}/tips/",
            {"amount": "25.00", "note": "Thank you!"},
            format="json",
        )
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.data["amount"], "25.00")
        self.assertEqual(r.data["from_member"], "Tipper")

    def test_tip_missing_amount_rejected(self):
        r = authed_client(self.tipper).post(
            f"/api/sol/{self.sol.id}/tips/", {}, format="json"
        )
        self.assertEqual(r.status_code, 400)

    def test_non_member_cannot_tip(self):
        stranger = make_user("stranger_tip", "stranger_tip@example.com")
        r = authed_client(stranger).post(
            f"/api/sol/{self.sol.id}/tips/", {"amount": "10.00"}, format="json"
        )
        self.assertEqual(r.status_code, 403)

    def test_tip_saved_to_manager(self):
        authed_client(self.tipper).post(
            f"/api/sol/{self.sol.id}/tips/", {"amount": "30.00"}, format="json"
        )
        tip = SolTip.objects.get(sol=self.sol)
        self.assertEqual(tip.to_manager, self.manager)
        self.assertEqual(tip.amount, Decimal("30.00"))
