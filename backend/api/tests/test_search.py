# backend/api/tests/test_search.py
#
# Tests for the Search domain:
#   GET /api/search/?q=               global search: contracts + templates + users
#   GET /api/search/contracts/?q=     contract search + filters
#   GET /api/search/templates/?q=     template search + category filter

from django.test import TestCase
from django.utils import timezone

from backend.contract_templates.models import ContractTemplate
from backend.contracts.models import Contract
from .helpers import authed_client, make_contract, make_user

GLOBAL_URL = "/api/search/"
CONTRACT_URL = "/api/search/contracts/"
TEMPLATE_URL = "/api/search/templates/"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_template(name="Service Agreement", category="legal", subcategory="general"):
    return ContractTemplate.objects.create(
        name=name,
        category=category,
        subcategory=subcategory,
        description="A test template.",
        structure_type="ONE_TIME",
        is_active=True,
        tier_required="free",
    )


# ---------------------------------------------------------------------------
# Global Search
# ---------------------------------------------------------------------------

class GlobalSearchTests(TestCase):

    def setUp(self):
        self.user = make_user("searcher", "searcher@example.com")
        self.other = make_user("other_gs", "other_gs@bonup.com")
        self.stranger = make_user("stranger_gs", "stranger_gs@example.com")
        self.client = authed_client(self.user)

    def test_missing_q_returns_400(self):
        r = self.client.get(GLOBAL_URL)
        self.assertEqual(r.status_code, 400)

    def test_empty_q_returns_400(self):
        r = self.client.get(f"{GLOBAL_URL}?q=")
        self.assertEqual(r.status_code, 400)

    def test_response_has_three_sections(self):
        r = self.client.get(f"{GLOBAL_URL}?q=anything")
        self.assertEqual(r.status_code, 200)
        self.assertIn("contracts", r.data)
        self.assertIn("templates", r.data)
        self.assertIn("users", r.data)

    def test_contract_section_returns_party_contracts(self):
        make_contract(self.user, self.other.email)
        r = self.client.get(f"{GLOBAL_URL}?q={self.other.email}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["contracts"]), 1)

    def test_contract_section_excludes_non_party_contracts(self):
        make_contract(self.other, self.stranger.email)
        r = self.client.get(f"{GLOBAL_URL}?q={self.stranger.email}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["contracts"]), 0)

    def test_contract_section_matches_structure_type(self):
        make_contract(self.user, self.other.email, structure_type="ONGOING")
        r = self.client.get(f"{GLOBAL_URL}?q=ONGOING")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["contracts"]), 1)

    def test_template_section_returns_matching_templates(self):
        make_template(name="NDA Agreement", category="legal")
        r = self.client.get(f"{GLOBAL_URL}?q=NDA")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["templates"]), 1)
        self.assertEqual(r.data["templates"][0]["name"], "NDA Agreement")

    def test_template_section_matches_category(self):
        make_template(name="Health Service", category="health_wellness")
        r = self.client.get(f"{GLOBAL_URL}?q=health")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(any(t["category"] == "health_wellness" for t in r.data["templates"]))

    def test_template_section_excludes_inactive(self):
        t = make_template(name="Inactive Template")
        t.is_active = False
        t.save()
        r = self.client.get(f"{GLOBAL_URL}?q=Inactive")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["templates"]), 0)

    def test_user_section_returns_matching_users(self):
        r = self.client.get(f"{GLOBAL_URL}?q=other_gs")
        self.assertEqual(r.status_code, 200)
        usernames = [u["username"] for u in r.data["users"]]
        self.assertIn("other_gs", usernames)

    def test_user_section_excludes_self(self):
        r = self.client.get(f"{GLOBAL_URL}?q=searcher")
        self.assertEqual(r.status_code, 200)
        usernames = [u["username"] for u in r.data["users"]]
        self.assertNotIn("searcher", usernames)

    def test_user_section_matches_bon_id(self):
        profile = self.other.bon_profile
        r = self.client.get(f"{GLOBAL_URL}?q={profile.bon_id}")
        self.assertEqual(r.status_code, 200)
        bon_ids = [u["bon_id"] for u in r.data["users"]]
        self.assertIn(profile.bon_id, bon_ids)

    def test_user_result_has_expected_fields(self):
        r = self.client.get(f"{GLOBAL_URL}?q=other_gs")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(len(r.data["users"]) > 0)
        user_item = r.data["users"][0]
        for field in ("bon_id", "username", "first_name", "last_name"):
            self.assertIn(field, user_item)

    def test_contract_result_has_expected_fields(self):
        make_contract(self.user, self.other.email)
        r = self.client.get(f"{GLOBAL_URL}?q={self.other.email}")
        item = r.data["contracts"][0]
        for field in ("id", "counterparty_email", "structure_type", "state", "is_active", "created_at"):
            self.assertIn(field, item)

    def test_no_results_returns_empty_sections(self):
        r = self.client.get(f"{GLOBAL_URL}?q=zzznomatch999")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["contracts"], [])
        self.assertEqual(r.data["templates"], [])
        self.assertEqual(r.data["users"], [])

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(f"{GLOBAL_URL}?q=test")
        self.assertEqual(r.status_code, 401)

    def test_counterparty_sees_contract_in_results(self):
        # user is the counterparty; contract.counterparty_email == user.email
        make_contract(self.other, self.user.email)
        client = authed_client(self.user)
        # search by a token that appears in the user's own email (the counterparty_email stored on the contract)
        token = self.user.email.split("@")[0]  # e.g. "searcher"
        r = client.get(f"{GLOBAL_URL}?q={token}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["contracts"]), 1)


# ---------------------------------------------------------------------------
# Contract Search
# ---------------------------------------------------------------------------

class ContractSearchTests(TestCase):

    def setUp(self):
        self.user = make_user("cs_user", "cs_user@example.com")
        self.other = make_user("cs_other", "cs_other@example.com")
        self.client = authed_client(self.user)

    def test_no_q_returns_all_own_contracts(self):
        make_contract(self.user, self.other.email)
        make_contract(self.user, self.other.email)
        r = self.client.get(CONTRACT_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_q_filters_by_counterparty_email(self):
        make_contract(self.user, "alpha@example.com")
        make_contract(self.user, "beta@example.com")
        r = self.client.get(f"{CONTRACT_URL}?q=alpha")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertIn("alpha@example.com", r.data[0]["counterparty_email"])

    def test_q_filters_by_structure_type(self):
        make_contract(self.user, self.other.email, structure_type="ONGOING")
        make_contract(self.user, self.other.email, structure_type="ONE_TIME")
        r = self.client.get(f"{CONTRACT_URL}?q=ONGOING")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["structure_type"], "ONGOING")

    def test_filter_by_status(self):
        c = make_contract(self.user, self.other.email)
        c.state = "fulfilled"
        c.save()
        make_contract(self.user, self.other.email)  # state=active
        r = self.client.get(f"{CONTRACT_URL}?status=fulfilled")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["state"], "fulfilled")

    def test_filter_by_structure_type(self):
        make_contract(self.user, self.other.email, structure_type="COLLABORATIVE")
        make_contract(self.user, self.other.email, structure_type="ONE_TIME")
        r = self.client.get(f"{CONTRACT_URL}?structure_type=COLLABORATIVE")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["structure_type"], "COLLABORATIVE")

    def test_filter_by_date_from(self):
        c = make_contract(self.user, self.other.email)
        future_date = "2099-01-01"
        r = self.client.get(f"{CONTRACT_URL}?date_from={future_date}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 0)

    def test_filter_by_date_to(self):
        make_contract(self.user, self.other.email)
        past_date = "2000-01-01"
        r = self.client.get(f"{CONTRACT_URL}?date_to={past_date}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 0)

    def test_date_range_includes_today(self):
        make_contract(self.user, self.other.email)
        today = timezone.now().date().isoformat()
        r = self.client.get(f"{CONTRACT_URL}?date_from={today}&date_to={today}")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_excludes_strangers_contracts(self):
        stranger = make_user("stranger_cs", "stranger_cs@example.com")
        make_contract(stranger, "nobody@example.com")
        r = self.client.get(CONTRACT_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 0)

    def test_combined_q_and_status_filter(self):
        c1 = make_contract(self.user, "alpha@example.com")
        c1.state = "fulfilled"
        c1.save()
        c2 = make_contract(self.user, "alpha@example.com")  # state=active
        r = self.client.get(f"{CONTRACT_URL}?q=alpha&status=fulfilled")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["state"], "fulfilled")

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(CONTRACT_URL)
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# Template Search
# ---------------------------------------------------------------------------

class TemplateSearchTests(TestCase):

    def setUp(self):
        self.user = make_user("ts_user", "ts_user@example.com")
        self.client = authed_client(self.user)

    def test_no_q_returns_all_active_templates(self):
        make_template("Template A", "legal")
        make_template("Template B", "health_wellness")
        r = self.client.get(TEMPLATE_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_inactive_templates_excluded(self):
        t = make_template("Hidden")
        t.is_active = False
        t.save()
        r = self.client.get(TEMPLATE_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 0)

    def test_q_matches_name(self):
        make_template("Freelance Contract", "creative_services")
        make_template("NDA", "legal")
        r = self.client.get(f"{TEMPLATE_URL}?q=Freelance")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["name"], "Freelance Contract")

    def test_q_matches_category(self):
        make_template("Doc A", "creative_services", "photography")
        make_template("Doc B", "legal", "nda")
        r = self.client.get(f"{TEMPLATE_URL}?q=creative")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["category"], "creative_services")

    def test_q_matches_subcategory(self):
        make_template("Doc C", "creative_services", "videography")
        make_template("Doc D", "legal", "other")
        r = self.client.get(f"{TEMPLATE_URL}?q=video")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_filter_by_category(self):
        make_template("Legal Doc", "legal")
        make_template("Health Doc", "health_wellness")
        r = self.client.get(f"{TEMPLATE_URL}?category=legal")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["category"], "legal")

    def test_combined_q_and_category(self):
        make_template("Legal NDA", "legal", "nda")
        make_template("Legal Service", "legal", "service")
        make_template("Health NDA", "health_wellness", "nda")
        r = self.client.get(f"{TEMPLATE_URL}?q=NDA&category=legal")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["name"], "Legal NDA")

    def test_no_results_returns_empty_list(self):
        r = self.client.get(f"{TEMPLATE_URL}?q=zzznomatch999")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [])

    def test_result_has_expected_fields(self):
        make_template("Field Check", "legal")
        r = self.client.get(f"{TEMPLATE_URL}?q=Field")
        item = r.data[0]
        for field in ("id", "name", "category", "subcategory", "structure_type", "tier_required"):
            self.assertIn(field, item)

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(TEMPLATE_URL)
        self.assertEqual(r.status_code, 401)
