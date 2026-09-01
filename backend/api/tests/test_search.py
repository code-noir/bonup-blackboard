# backend/api/tests/test_search.py
#
# Tests for the comprehensive Search domain:
#   GET /api/search/?q=                 global — 10 domains
#   GET /api/search/contracts/?q=       contracts + filters
#   GET /api/search/obligations/?q=     obligations + filters
#   GET /api/search/payments/?q=        payments + filters
#   GET /api/search/sessions/?q=        sessions + filter
#   GET /api/search/documents/?q=       documents
#   GET /api/search/templates/?q=       templates + category filter
#   GET /api/search/sol/?q=             Sol groups + filters

import uuid
from unittest.mock import patch
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from backend.contract_templates.models import ContractTemplate
from backend.contracts.models import (
    Contract,
    ContractObligation,
    ContractServiceObligation,
    ContractVersion,
)
from backend.documents.models import ContractDocument
from backend.notifications.models import Notification
from backend.payments.models import Payment
from backend.sessions.models import LiveSession
from backend.sol.models import Sol, SolMember
from backend.uploads.models import Upload
from .helpers import authed_client, make_contract, make_user, make_subscription, make_version

GLOBAL_URL = "/api/search/"
CONTRACT_URL = "/api/search/contracts/"
OBLIGATION_URL = "/api/search/obligations/"
PAYMENT_URL = "/api/search/payments/"
SESSION_URL = "/api/search/sessions/"
DOCUMENT_URL = "/api/search/documents/"
TEMPLATE_URL = "/api/search/templates/"
SOL_URL = "/api/search/sol/"


# ---------------------------------------------------------------------------
# Shared builders
# ---------------------------------------------------------------------------

def make_template(name="Service Agreement", category="legal", subcategory="general"):
    return ContractTemplate.objects.create(
        name=name, category=category, subcategory=subcategory,
        description="A test template.", structure_type="ONE_TIME",
        is_active=True, tier_required="free",
    )


def make_payment(contract, payer, payee, status="draft", reference=None):
    return Payment.objects.create(
        contract=contract, payer=payer, payee=payee,
        amount=Decimal("100.00"), status=status,
        reference=reference,
    )


def make_session(contract, created_by, title="Test Session", status="scheduled"):
    return LiveSession.objects.create(
        contract=contract, created_by=created_by,
        title=title, room_name=f"room-{uuid.uuid4().hex[:8]}", status=status,
    )


def make_service_obligation(contract, version, obligor, obligee, description="Deliver work"):
    return ContractServiceObligation.objects.create(
        contract=contract, version=version, obligor=obligor, obligee=obligee,
        description=description, due_date=timezone.now(),
    )


def make_payment_obligation(contract, version, obligor, obligee):
    return ContractObligation.objects.create(
        contract=contract, version=version, obligor=obligor, obligee=obligee,
        installment_number=1, amount_due=Decimal("500.00"), due_date=timezone.now(),
    )


def make_upload(user, file_name="report.pdf", file_type="pdf"):
    return Upload.objects.create(
        user=user, file_url="https://example.com/file.pdf",
        file_name=file_name, file_type=file_type, file_size=1024,
        storage_key="",
    )


def make_document(contract, upload, attached_by, title="Contract Doc"):
    return ContractDocument.objects.create(
        contract=contract, upload=upload, attached_by=attached_by, title=title,
    )


def make_notification(user, title="Alert", message="Something happened"):
    return Notification.objects.create(
        user=user, notification_type="contract_created",
        title=title, message=message,
    )


# ---------------------------------------------------------------------------
# Global Search
# ---------------------------------------------------------------------------

class GlobalSearchTests(TestCase):

    def setUp(self):
        self.user = make_user("gs_user", "gs_user@example.com")
        self.other = make_user("gs_other", "gs_other@bonup.com")
        self.client = authed_client(self.user)

    def test_missing_q_returns_400(self):
        r = self.client.get(GLOBAL_URL)
        self.assertEqual(r.status_code, 400)

    def test_empty_q_returns_400(self):
        r = self.client.get(f"{GLOBAL_URL}?q=")
        self.assertEqual(r.status_code, 400)

    def test_response_has_all_ten_sections(self):
        r = self.client.get(f"{GLOBAL_URL}?q=anything")
        self.assertEqual(r.status_code, 200)
        for section in ("contracts", "obligations", "payments", "sessions",
                        "documents", "uploads", "notifications", "templates", "sol", "users"):
            self.assertIn(section, r.data, f"Missing section: {section}")

    def test_no_results_all_sections_empty(self):
        r = self.client.get(f"{GLOBAL_URL}?q=zzznomatch999")
        self.assertEqual(r.status_code, 200)
        for section in ("contracts", "obligations", "payments", "sessions",
                        "documents", "uploads", "notifications", "templates", "sol", "users"):
            self.assertEqual(r.data[section], [], f"Expected empty list for {section}")

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(f"{GLOBAL_URL}?q=test")
        self.assertEqual(r.status_code, 401)

    # contracts
    def test_global_finds_own_contract(self):
        make_contract(self.user, self.other.email)
        r = self.client.get(f"{GLOBAL_URL}?q={self.other.email}")
        self.assertEqual(len(r.data["contracts"]), 1)

    def test_global_excludes_stranger_contract(self):
        stranger = make_user("gs_stranger", "gs_stranger@example.com")
        make_contract(stranger, "nobody@example.com")
        r = self.client.get(f"{GLOBAL_URL}?q=nobody")
        self.assertEqual(r.data["contracts"], [])

    def test_global_counterparty_sees_contract(self):
        make_contract(self.other, self.user.email)
        token = self.user.email.split("@")[0]
        r = self.client.get(f"{GLOBAL_URL}?q={token}")
        self.assertEqual(len(r.data["contracts"]), 1)

    # uploads
    def test_global_finds_own_upload(self):
        make_upload(self.user, file_name="uniquefilexyz.pdf")
        r = self.client.get(f"{GLOBAL_URL}?q=uniquefilexyz")
        self.assertEqual(len(r.data["uploads"]), 1)

    @patch("backend.uploads.services.default_storage")
    def test_global_upload_result_uses_dynamic_url_when_storage_key_exists(self, mock_storage):
        mock_storage.url.return_value = "https://current-provider.example/uploads/example/file.pdf"
        upload = make_upload(self.user, file_name="uniquefilexyz.pdf")
        upload.storage_key = "uploads/example/file.pdf"
        upload.file_url = "https://old-provider.example/stale.pdf"
        upload.save(update_fields=["storage_key", "file_url"])

        r = self.client.get(f"{GLOBAL_URL}?q=uniquefilexyz")

        self.assertEqual(len(r.data["uploads"]), 1)
        self.assertEqual(
            r.data["uploads"][0]["file_url"],
            "https://current-provider.example/uploads/example/file.pdf",
        )
        mock_storage.url.assert_called_once_with("uploads/example/file.pdf")

    def test_global_excludes_others_upload(self):
        make_upload(self.other, file_name="secretfile.pdf")
        r = self.client.get(f"{GLOBAL_URL}?q=secretfile")
        self.assertEqual(r.data["uploads"], [])

    # notifications
    def test_global_finds_own_notification(self):
        make_notification(self.user, title="Unique Alert XYZ")
        r = self.client.get(f"{GLOBAL_URL}?q=Unique Alert XYZ")
        self.assertEqual(len(r.data["notifications"]), 1)

    def test_global_excludes_others_notification(self):
        make_notification(self.other, title="Other Alert XYZ")
        r = self.client.get(f"{GLOBAL_URL}?q=Other Alert XYZ")
        self.assertEqual(r.data["notifications"], [])

    # payments
    def test_global_finds_payment_by_reference(self):
        contract = make_contract(self.user, self.other.email)
        make_payment(contract, self.user, self.other, reference="REF-UNIQUE-001")
        r = self.client.get(f"{GLOBAL_URL}?q=REF-UNIQUE-001")
        self.assertEqual(len(r.data["payments"]), 1)

    # sessions
    def test_global_finds_session_by_title(self):
        contract = make_contract(self.user, self.other.email)
        make_session(contract, self.user, title="Unique Session XYZ")
        r = self.client.get(f"{GLOBAL_URL}?q=Unique Session XYZ")
        self.assertEqual(len(r.data["sessions"]), 1)

    # templates
    def test_global_finds_template(self):
        make_template(name="NDA Agreement XYZ")
        r = self.client.get(f"{GLOBAL_URL}?q=NDA Agreement XYZ")
        self.assertEqual(len(r.data["templates"]), 1)

    # users
    def test_global_finds_user_by_username(self):
        r = self.client.get(f"{GLOBAL_URL}?q=gs_other")
        self.assertGreater(len(r.data["users"]), 0)
        usernames = [u["username"] for u in r.data["users"]]
        self.assertIn("gs_other", usernames)

    def test_global_excludes_self_from_users(self):
        r = self.client.get(f"{GLOBAL_URL}?q=gs_user")
        usernames = [u["username"] for u in r.data["users"]]
        self.assertNotIn("gs_user", usernames)

    # obligations
    def test_global_finds_service_obligation_by_description(self):
        contract = make_contract(self.user, self.other.email)
        version = make_version(contract, self.user)
        make_service_obligation(contract, version, self.user, self.other, "DeliverUniqueWork")
        r = self.client.get(f"{GLOBAL_URL}?q=DeliverUniqueWork")
        self.assertEqual(len(r.data["obligations"]), 1)
        self.assertEqual(r.data["obligations"][0]["obligation_type"], "service")

    # documents
    def test_global_finds_document_by_title(self):
        contract = make_contract(self.user, self.other.email)
        upload = make_upload(self.user)
        make_document(contract, upload, self.user, title="UniqueTitleABC")
        r = self.client.get(f"{GLOBAL_URL}?q=UniqueTitleABC")
        self.assertEqual(len(r.data["documents"]), 1)


# ---------------------------------------------------------------------------
# User search prioritization
# ---------------------------------------------------------------------------

class UserSearchPriorityTests(TestCase):

    def setUp(self):
        self.searcher = make_user("priority_searcher", "priority_searcher@example.com")
        self.client = authed_client(self.searcher)

    def test_bon_id_exact_match_returns_first(self):
        target = make_user("bon_target", "bon_target@example.com")
        profile = target.bon_profile
        r = self.client.get(f"{GLOBAL_URL}?q={profile.bon_id}")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.data["users"]), 0)
        self.assertEqual(r.data["users"][0]["bon_id"], profile.bon_id)

    def test_email_exact_match_before_partial(self):
        exact = make_user("email_exact", "exactmatch@example.com")
        partial = make_user("email_partial", "notexactmatch@example.com")
        r = self.client.get(f"{GLOBAL_URL}?q=exactmatch@example.com")
        self.assertGreater(len(r.data["users"]), 0)
        self.assertEqual(r.data["users"][0]["email"], "exactmatch@example.com")

    def test_user_result_includes_email(self):
        target = make_user("email_field_user", "emailfield@example.com")
        r = self.client.get(f"{GLOBAL_URL}?q=emailfield")
        self.assertGreater(len(r.data["users"]), 0)
        self.assertIn("email", r.data["users"][0])

    def test_phone_partial_search(self):
        target = make_user("phone_user", "phone_user@example.com")
        profile = target.bon_profile
        profile.phone = "+15551234567"
        profile.save()
        r = self.client.get(f"{GLOBAL_URL}?q=5551234")
        usernames = [u["username"] for u in r.data["users"]]
        self.assertIn("phone_user", usernames)


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
        self.assertEqual(len(r.data), 1)
        self.assertIn("alpha", r.data[0]["counterparty_email"])

    def test_filter_by_status(self):
        c = make_contract(self.user, self.other.email)
        c.state = "fulfilled"
        c.save()
        make_contract(self.user, self.other.email)
        r = self.client.get(f"{CONTRACT_URL}?status=fulfilled")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["state"], "fulfilled")

    def test_filter_by_structure_type(self):
        make_contract(self.user, self.other.email, structure_type="COLLABORATIVE")
        make_contract(self.user, self.other.email, structure_type="ONE_TIME")
        r = self.client.get(f"{CONTRACT_URL}?structure_type=COLLABORATIVE")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["structure_type"], "COLLABORATIVE")

    def test_date_from_future_returns_empty(self):
        make_contract(self.user, self.other.email)
        r = self.client.get(f"{CONTRACT_URL}?date_from=2099-01-01")
        self.assertEqual(len(r.data), 0)

    def test_date_to_past_returns_empty(self):
        make_contract(self.user, self.other.email)
        r = self.client.get(f"{CONTRACT_URL}?date_to=2000-01-01")
        self.assertEqual(len(r.data), 0)

    def test_date_range_today_returns_result(self):
        make_contract(self.user, self.other.email)
        today = timezone.now().date().isoformat()
        r = self.client.get(f"{CONTRACT_URL}?date_from={today}&date_to={today}")
        self.assertEqual(len(r.data), 1)

    def test_excludes_strangers_contracts(self):
        stranger = make_user("stranger_cs", "stranger_cs@example.com")
        make_contract(stranger, "nobody@example.com")
        r = self.client.get(CONTRACT_URL)
        self.assertEqual(len(r.data), 0)

    def test_combined_q_and_status(self):
        c = make_contract(self.user, "alpha@example.com")
        c.state = "fulfilled"
        c.save()
        make_contract(self.user, "alpha@example.com")
        r = self.client.get(f"{CONTRACT_URL}?q=alpha&status=fulfilled")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["state"], "fulfilled")

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(CONTRACT_URL)
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# Obligation Search
# ---------------------------------------------------------------------------

class ObligationSearchTests(TestCase):

    def setUp(self):
        self.user = make_user("obs_user", "obs_user@example.com")
        self.other = make_user("obs_other", "obs_other@example.com")
        self.contract = make_contract(self.user, self.other.email)
        self.version = make_version(self.contract, self.user)
        self.client = authed_client(self.user)

    def test_no_q_returns_own_obligations(self):
        make_payment_obligation(self.contract, self.version, self.user, self.other)
        make_service_obligation(self.contract, self.version, self.user, self.other)
        r = self.client.get(OBLIGATION_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_obligation_type_payment_returns_only_payment(self):
        make_payment_obligation(self.contract, self.version, self.user, self.other)
        make_service_obligation(self.contract, self.version, self.user, self.other)
        r = self.client.get(f"{OBLIGATION_URL}?obligation_type=payment")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all(o["obligation_type"] == "payment" for o in r.data))

    def test_obligation_type_service_returns_only_service(self):
        make_payment_obligation(self.contract, self.version, self.user, self.other)
        make_service_obligation(self.contract, self.version, self.user, self.other)
        r = self.client.get(f"{OBLIGATION_URL}?obligation_type=service")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(all(o["obligation_type"] == "service" for o in r.data))

    def test_q_matches_service_description(self):
        make_service_obligation(
            self.contract, self.version, self.user, self.other, "DeliverUniqueThing"
        )
        r = self.client.get(f"{OBLIGATION_URL}?q=DeliverUniqueThing")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["obligation_type"], "service")

    def test_status_filter(self):
        o = make_service_obligation(self.contract, self.version, self.user, self.other)
        o.state = "resolved"
        o.save()
        make_service_obligation(self.contract, self.version, self.user, self.other)
        r = self.client.get(f"{OBLIGATION_URL}?obligation_type=service&status=resolved")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["state"], "resolved")

    def test_excludes_strangers_obligations(self):
        stranger = make_user("obs_stranger", "obs_stranger@example.com")
        stranger_other = make_user("obs_stranger_other", "obs_stranger_other@example.com")
        sc = make_contract(stranger, stranger_other.email)
        sv = make_version(sc, stranger)
        make_service_obligation(sc, sv, stranger, stranger_other, "StrangerWork")
        r = self.client.get(f"{OBLIGATION_URL}?q=StrangerWork")
        self.assertEqual(r.data, [])

    def test_obligation_result_has_expected_fields(self):
        make_payment_obligation(self.contract, self.version, self.user, self.other)
        r = self.client.get(f"{OBLIGATION_URL}?obligation_type=payment")
        item = r.data[0]
        for field in ("id", "obligation_type", "contract_id", "state", "amount_due", "due_date"):
            self.assertIn(field, item)

    def test_service_obligation_result_has_description(self):
        make_service_obligation(self.contract, self.version, self.user, self.other, "Task")
        r = self.client.get(f"{OBLIGATION_URL}?obligation_type=service")
        self.assertIn("description", r.data[0])

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(OBLIGATION_URL)
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# Payment Search
# ---------------------------------------------------------------------------

class PaymentSearchTests(TestCase):

    def setUp(self):
        self.user = make_user("ps_user", "ps_user@example.com")
        self.other = make_user("ps_other", "ps_other@example.com")
        self.contract = make_contract(self.user, self.other.email)
        self.client = authed_client(self.user)

    def test_no_q_returns_own_payments(self):
        make_payment(self.contract, self.user, self.other)
        make_payment(self.contract, self.other, self.user)
        r = self.client.get(PAYMENT_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_q_matches_reference(self):
        make_payment(self.contract, self.user, self.other, reference="INV-UNIQUE-XYZ")
        make_payment(self.contract, self.user, self.other)
        r = self.client.get(f"{PAYMENT_URL}?q=INV-UNIQUE-XYZ")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["reference"], "INV-UNIQUE-XYZ")

    def test_q_matches_status(self):
        p = make_payment(self.contract, self.user, self.other, status="confirmed")
        make_payment(self.contract, self.user, self.other, status="draft")
        r = self.client.get(f"{PAYMENT_URL}?q=confirmed")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["status"], "confirmed")

    def test_status_filter(self):
        make_payment(self.contract, self.user, self.other, status="confirmed")
        make_payment(self.contract, self.user, self.other, status="draft")
        r = self.client.get(f"{PAYMENT_URL}?status=confirmed")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["status"], "confirmed")

    def test_excludes_strangers_payments(self):
        stranger = make_user("ps_stranger", "ps_stranger@example.com")
        stranger_other = make_user("ps_stranger2", "ps_stranger2@example.com")
        sc = make_contract(stranger, stranger_other.email)
        make_payment(sc, stranger, stranger_other)
        r = self.client.get(PAYMENT_URL)
        self.assertEqual(len(r.data), 0)

    def test_payee_also_sees_payment(self):
        make_payment(self.contract, self.other, self.user)
        r = self.client.get(PAYMENT_URL)
        self.assertEqual(len(r.data), 1)

    def test_result_has_expected_fields(self):
        make_payment(self.contract, self.user, self.other)
        r = self.client.get(PAYMENT_URL)
        item = r.data[0]
        for field in ("id", "contract_id", "amount", "currency", "status",
                      "payment_method", "reference", "created_at"):
            self.assertIn(field, item)

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(PAYMENT_URL)
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# Session Search
# ---------------------------------------------------------------------------

class SessionSearchTests(TestCase):

    def setUp(self):
        self.user = make_user("ss_user", "ss_user@example.com")
        self.other = make_user("ss_other", "ss_other@example.com")
        self.contract = make_contract(self.user, self.other.email)
        self.client = authed_client(self.user)

    def test_no_q_returns_own_sessions(self):
        make_session(self.contract, self.user)
        r = self.client.get(SESSION_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_q_matches_title(self):
        make_session(self.contract, self.user, title="Negotiation XYZ")
        make_session(self.contract, self.user, title="Other Session")
        r = self.client.get(f"{SESSION_URL}?q=Negotiation XYZ")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["title"], "Negotiation XYZ")

    def test_status_filter(self):
        make_session(self.contract, self.user, status="ended")
        make_session(self.contract, self.user, status="scheduled")
        r = self.client.get(f"{SESSION_URL}?status=ended")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["status"], "ended")

    def test_counterparty_sees_session(self):
        make_session(self.contract, self.user)
        client = authed_client(self.other)
        r = client.get(SESSION_URL)
        self.assertEqual(len(r.data), 1)

    def test_excludes_strangers_sessions(self):
        stranger = make_user("ss_stranger", "ss_stranger@example.com")
        stranger_other = make_user("ss_stranger_other", "ss_stranger_other@example.com")
        sc = make_contract(stranger, stranger_other.email)
        make_session(sc, stranger)
        r = self.client.get(SESSION_URL)
        self.assertEqual(len(r.data), 0)

    def test_result_has_expected_fields(self):
        make_session(self.contract, self.user, title="Field Check")
        r = self.client.get(SESSION_URL)
        item = r.data[0]
        for field in ("id", "contract_id", "title", "status", "created_at"):
            self.assertIn(field, item)

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(SESSION_URL)
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# Document Search
# ---------------------------------------------------------------------------

class DocumentSearchTests(TestCase):

    def setUp(self):
        self.user = make_user("ds_user", "ds_user@example.com")
        self.other = make_user("ds_other", "ds_other@example.com")
        self.contract = make_contract(self.user, self.other.email)
        self.upload = make_upload(self.user)
        self.client = authed_client(self.user)

    def test_no_q_returns_own_documents(self):
        make_document(self.contract, self.upload, self.user)
        r = self.client.get(DOCUMENT_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 1)

    def test_q_matches_title(self):
        make_document(self.contract, self.upload, self.user, "UniqueDocTitle")
        make_document(self.contract, self.upload, self.user, "OtherDoc")
        r = self.client.get(f"{DOCUMENT_URL}?q=UniqueDocTitle")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["title"], "UniqueDocTitle")

    def test_q_matches_file_name(self):
        upload = make_upload(self.user, file_name="uniquefilename.pdf")
        make_document(self.contract, upload, self.user, "Doc with Unique File")
        r = self.client.get(f"{DOCUMENT_URL}?q=uniquefilename")
        self.assertEqual(len(r.data), 1)

    def test_counterparty_sees_documents(self):
        make_document(self.contract, self.upload, self.user)
        client = authed_client(self.other)
        r = client.get(DOCUMENT_URL)
        self.assertEqual(len(r.data), 1)

    def test_excludes_strangers_documents(self):
        stranger = make_user("ds_stranger", "ds_stranger@example.com")
        stranger_other = make_user("ds_stranger_other", "ds_stranger_other@example.com")
        sc = make_contract(stranger, stranger_other.email)
        sup = make_upload(stranger)
        make_document(sc, sup, stranger, "Stranger Doc")
        r = self.client.get(f"{DOCUMENT_URL}?q=Stranger Doc")
        self.assertEqual(r.data, [])

    def test_result_has_expected_fields(self):
        make_document(self.contract, self.upload, self.user, "Field Doc")
        r = self.client.get(DOCUMENT_URL)
        item = r.data[0]
        for field in ("id", "contract_id", "title", "description",
                      "file_name", "file_url", "is_proof", "attached_at"):
            self.assertIn(field, item)

    @patch("backend.uploads.services.default_storage")
    def test_document_result_uses_dynamic_upload_url_when_storage_key_exists(self, mock_storage):
        mock_storage.url.return_value = "https://current-provider.example/uploads/example/file.pdf"
        self.upload.storage_key = "uploads/example/file.pdf"
        self.upload.file_url = "https://old-provider.example/stale.pdf"
        self.upload.save(update_fields=["storage_key", "file_url"])
        make_document(self.contract, self.upload, self.user, "Dynamic URL Doc")

        r = self.client.get(DOCUMENT_URL)

        self.assertEqual(r.status_code, 200)
        self.assertEqual(
            r.data[0]["file_url"],
            "https://current-provider.example/uploads/example/file.pdf",
        )
        mock_storage.url.assert_called_once_with("uploads/example/file.pdf")

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(DOCUMENT_URL)
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
        self.assertEqual(len(r.data), 0)

    def test_q_matches_name(self):
        make_template("Freelance Contract", "creative_services")
        make_template("NDA", "legal")
        r = self.client.get(f"{TEMPLATE_URL}?q=Freelance")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["name"], "Freelance Contract")

    def test_q_matches_category(self):
        make_template("Doc A", "creative_services", "photography")
        make_template("Doc B", "legal", "nda")
        r = self.client.get(f"{TEMPLATE_URL}?q=creative")
        self.assertEqual(len(r.data), 1)

    def test_filter_by_category(self):
        make_template("Legal Doc", "legal")
        make_template("Health Doc", "health_wellness")
        r = self.client.get(f"{TEMPLATE_URL}?category=legal")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["category"], "legal")

    def test_combined_q_and_category(self):
        make_template("Legal NDA", "legal", "nda")
        make_template("Legal Service", "legal", "service")
        make_template("Health NDA", "health_wellness", "nda")
        r = self.client.get(f"{TEMPLATE_URL}?q=NDA&category=legal")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["name"], "Legal NDA")

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(TEMPLATE_URL)
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# Sol Search helpers
# ---------------------------------------------------------------------------

def make_sol(manager, name="Test Sol", status="active", frequency="monthly"):
    from decimal import Decimal
    return Sol.objects.create(
        name=name,
        description=f"A test Sol group: {name}",
        frequency=frequency,
        contribution_amount=Decimal("200.00"),
        currency="USD",
        tip_expectation=Decimal("25.00"),
        start_date=timezone.now().date(),
        primary_manager=manager,
        status=status,
    )


def make_sol_member(sol, hand_number, name, email, bonup_user=None):
    return SolMember.objects.create(
        sol=sol,
        bonup_user=bonup_user,
        name=name,
        email=email,
        phone="555-0001",
        hand_number=hand_number,
        is_bonup_member=(bonup_user is not None),
    )


# ---------------------------------------------------------------------------
# Global search — Sol section
# ---------------------------------------------------------------------------

class GlobalSearchSolTests(TestCase):

    def setUp(self):
        self.manager = make_user("gs_sol_mgr", "gs_sol_mgr@example.com")
        make_subscription(self.manager)
        self.member_user = make_user("gs_sol_mem", "gs_sol_mem@example.com")
        make_subscription(self.member_user)
        self.sol = make_sol(self.manager, name="Friday Tontine")
        make_sol_member(self.sol, 1, "Alice Sol", "alice_sol@example.com",
                        bonup_user=self.member_user)

    def test_manager_finds_sol_by_name(self):
        r = authed_client(self.manager).get(f"{GLOBAL_URL}?q=Friday")
        self.assertEqual(r.status_code, 200)
        self.assertIn("sol", r.data)
        self.assertEqual(len(r.data["sol"]), 1)
        self.assertEqual(r.data["sol"][0]["name"], "Friday Tontine")

    def test_member_finds_sol_by_name(self):
        r = authed_client(self.member_user).get(f"{GLOBAL_URL}?q=Friday")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data["sol"]), 1)

    def test_stranger_cannot_find_sol(self):
        stranger = make_user("gs_sol_stranger", "gs_sol_stranger@example.com")
        r = authed_client(stranger).get(f"{GLOBAL_URL}?q=Friday")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["sol"], [])

    def test_sol_result_fields(self):
        r = authed_client(self.manager).get(f"{GLOBAL_URL}?q=Friday")
        item = r.data["sol"][0]
        for field in ("id", "sol_id", "name", "status", "frequency",
                      "contribution_amount", "currency", "active_member_count"):
            self.assertIn(field, item, f"Missing field: {field}")

    def test_finds_sol_by_sol_id(self):
        r = authed_client(self.manager).get(f"{GLOBAL_URL}?q={self.sol.sol_id}")
        self.assertEqual(len(r.data["sol"]), 1)


# ---------------------------------------------------------------------------
# Sol Search endpoint — GET /api/search/sol/
# ---------------------------------------------------------------------------

class SolSearchViewTests(TestCase):

    def setUp(self):
        self.manager = make_user("ss_sol_mgr", "ss_sol_mgr@example.com")
        make_subscription(self.manager)
        self.member_user = make_user("ss_sol_mem", "ss_sol_mem@example.com")
        make_subscription(self.member_user)
        self.sol_active = make_sol(self.manager, name="Alpha Sol", status="active", frequency="monthly")
        self.sol_paused = make_sol(self.manager, name="Beta Sol", status="paused", frequency="weekly")
        make_sol_member(self.sol_active, 1, "Bob Sol", "bob_sol@example.com",
                        bonup_user=self.member_user)

    def test_no_q_returns_all_managed_sols(self):
        r = authed_client(self.manager).get(SOL_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data), 2)

    def test_q_matches_name(self):
        r = authed_client(self.manager).get(f"{SOL_URL}?q=Alpha")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["name"], "Alpha Sol")

    def test_status_filter(self):
        r = authed_client(self.manager).get(f"{SOL_URL}?status=paused")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["status"], "paused")

    def test_frequency_filter(self):
        r = authed_client(self.manager).get(f"{SOL_URL}?frequency=weekly")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["frequency"], "weekly")

    def test_member_sees_their_sol(self):
        r = authed_client(self.member_user).get(SOL_URL)
        self.assertEqual(r.status_code, 200)
        names = [s["name"] for s in r.data]
        self.assertIn("Alpha Sol", names)

    def test_member_cannot_see_sols_they_dont_belong_to(self):
        r = authed_client(self.member_user).get(SOL_URL)
        names = [s["name"] for s in r.data]
        self.assertNotIn("Beta Sol", names)

    def test_stranger_sees_empty(self):
        stranger = make_user("ss_sol_stranger", "ss_sol_stranger@example.com")
        r = authed_client(stranger).get(SOL_URL)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data, [])

    def test_combined_q_and_status(self):
        r = authed_client(self.manager).get(f"{SOL_URL}?q=Beta&status=paused")
        self.assertEqual(len(r.data), 1)
        self.assertEqual(r.data[0]["name"], "Beta Sol")

    def test_result_fields(self):
        r = authed_client(self.manager).get(f"{SOL_URL}?q=Alpha")
        item = r.data[0]
        for field in ("id", "sol_id", "name", "description", "status",
                      "frequency", "contribution_amount", "currency",
                      "active_member_count", "created_at"):
            self.assertIn(field, item)

    def test_unauthenticated_returns_401(self):
        from rest_framework.test import APIClient
        r = APIClient().get(SOL_URL)
        self.assertEqual(r.status_code, 401)


# ---------------------------------------------------------------------------
# User search — SolMember lookup
# ---------------------------------------------------------------------------

class UserSearchSolMemberTests(TestCase):

    def setUp(self):
        self.manager = make_user("us_sol_mgr", "us_sol_mgr@example.com")
        make_subscription(self.manager)
        self.sol = make_sol(self.manager, name="Search Test Sol")
        make_sol_member(self.sol, 1, "Carla Tontine", "carla_tontine@example.com")
        make_sol_member(self.sol, 2, "Dave Sol", "dave_sol@example.com")

    def test_search_finds_sol_member_by_name(self):
        r = authed_client(self.manager).get(f"{GLOBAL_URL}?q=Carla Tontine")
        users = r.data["users"]
        sources = [u.get("source") for u in users]
        self.assertIn("sol_member", sources)
        names = [u.get("name") for u in users if u.get("source") == "sol_member"]
        self.assertIn("Carla Tontine", names)

    def test_search_finds_sol_member_by_email(self):
        r = authed_client(self.manager).get(f"{GLOBAL_URL}?q=carla_tontine")
        users = r.data["users"]
        sol_members = [u for u in users if u.get("source") == "sol_member"]
        self.assertEqual(len(sol_members), 1)
        self.assertEqual(sol_members[0]["email"], "carla_tontine@example.com")

    def test_sol_member_result_has_expected_fields(self):
        r = authed_client(self.manager).get(f"{GLOBAL_URL}?q=Carla")
        sol_members = [u for u in r.data["users"] if u.get("source") == "sol_member"]
        self.assertGreater(len(sol_members), 0)
        item = sol_members[0]
        for field in ("source", "id", "name", "email", "phone", "sol_id", "sol_name", "hand_number"):
            self.assertIn(field, item)

    def test_stranger_cannot_find_sol_members(self):
        stranger = make_user("us_sol_stranger", "us_sol_stranger@example.com")
        r = authed_client(stranger).get(f"{GLOBAL_URL}?q=Carla Tontine")
        sol_members = [u for u in r.data["users"] if u.get("source") == "sol_member"]
        self.assertEqual(sol_members, [])
