"""Content boundaries exercised through real operator View-As JWT authentication."""
import hashlib
import uuid
from unittest.mock import patch

from django.core.files.base import ContentFile
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken

from backend.ai.models import AIConversation, CounterDraft, ReviewResult, WorkflowState
from backend.contracts.models import LifecycleAgreement, LifecycleItem, LifecycleItemAttachment
from backend.documents.models import ContractDocument
from backend.negotiation_prep.models import PrepDocument, PrepSession
from backend.operator.models import OperatorViewAsSession
from backend.operator.services import operator_token_pair
from backend.uploads.models import Upload, VaultShare
from .helpers import make_contract, make_user, make_version
from .test_operator_auth import make_administrator
from .test_uploads import _managed_upload


class OperatorFilePrivacyTests(TestCase):
    def setUp(self):
        self.customer = make_user("privacy-customer", "privacy-customer@example.com")
        self.party = make_user("privacy-party", "privacy-party@example.com")
        self.administrator = make_administrator()
        self.operator = self.bearer(operator_token_pair(self.administrator)["access"])
        started = self.operator.post(f"/api/operator/view-as/{self.customer.pk}/", {}, format="json")
        self.assertEqual(started.status_code, 201)
        self.session_id = started.data["view_as_session_id"]
        self.view_as = self.bearer(started.data["access"])
        self.normal = self.bearer(str(AccessToken.for_user(self.customer)))
        self.upload = _managed_upload(self.customer)
        self.contract = make_contract(self.customer, self.party.email)
        self.document = ContractDocument.objects.create(
            contract=self.contract, upload=self.upload, attached_by=self.customer, title="Fixture attachment",
        )

    @staticmethod
    def bearer(token):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        return client

    def test_delivery_get_head_and_format_variants_deny_before_storage(self):
        with patch("backend.uploads.services.default_storage") as storage:
            for suffix in ["/delivery/", "/delivery.json"]:
                for method in ["get", "head"]:
                    with self.subTest(suffix=suffix, method=method):
                        response = getattr(self.view_as, method)(f"/api/uploads/{self.upload.id}{suffix}")
                        self.assertEqual(response.status_code, 403)
            storage.open.assert_not_called()
            storage.url.assert_not_called()

    def test_upload_list_suppresses_canonical_and_legacy_urls_without_generating(self):
        Upload.objects.create(user=self.customer, file_name="legacy fixture", file_type="pdf",
                              file_size=1, file_url="https://example.invalid/legacy")
        with patch("backend.uploads.services.default_storage") as storage:
            for query in ["", "?canonical=true", "?canonical=false"]:
                response = self.view_as.get("/api/uploads/" + query)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.data)
                for item in response.data:
                    self.assertIsNone(item["file_url"])
                    self.assertIn("file_size", item)
            storage.url.assert_not_called()
            storage.open.assert_not_called()

    def test_contract_and_search_metadata_suppress_urls(self):
        paths = [f"/api/contracts/{self.contract.id}/documents/", "/api/search/documents/", "/api/search/?q=file"]
        with patch("backend.uploads.services.default_storage") as storage:
            for path in paths:
                response = self.view_as.get(path)
                self.assertEqual(response.status_code, 200)
                rows = response.data if isinstance(response.data, list) else response.data["documents"] + response.data["uploads"]
                self.assertTrue(rows)
                for row in rows:
                    self.assertIsNone(row["file_url"])
                    self.assertIn("id", row)
            storage.open.assert_not_called()
            storage.url.assert_not_called()

    def test_prep_url_only_documents_preserve_metadata_without_urls(self):
        prep = PrepSession.objects.create(owner=self.customer, title="Fixture prep")
        PrepDocument.objects.create(prep_session=prep, title="Fixture", file_type="pdf",
                                    file_url="https://example.invalid/prep")
        path = f"/api/prep/{prep.id}/"
        response = self.view_as.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["title"], prep.title)
        self.assertIsNone(response.data["documents"][0]["file_url"])
        self.assertIsNone(self.normal.get(path).data["documents"][0]["file_url"])

    def test_lifecycle_urls_suppressed_before_url_generation(self):
        version = make_version(self.contract, self.customer, status="signed")
        agreement = LifecycleAgreement.objects.create(contract=self.contract, signed_version=version, owner=self.customer)
        item = LifecycleItem.objects.create(lifecycle_agreement=agreement, item_type="payment", title="Fixture item")
        LifecycleItemAttachment.objects.create(lifecycle_item=item, lifecycle_agreement=agreement,
            contract=self.contract, uploaded_by=self.customer, file="fixture-proof", original_filename="Fixture")
        path = f"/api/lifecycle/items/{item.id}/attachments/"
        storage = LifecycleItemAttachment._meta.get_field("file").storage
        with patch.object(storage, "url", return_value="https://example.invalid/proof") as url:
            response = self.view_as.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data["results"][0]["file_url"], "")
            url.assert_not_called()
            row = self.normal.get(path).data["results"][0]
            self.assertEqual(row["file_url"], f"{path}{row['id']}/delivery/")
            url.assert_not_called()

    def test_ai_messages_suppressed_but_metadata_and_customer_messages_preserved(self):
        conversation = AIConversation.objects.create(user=self.customer, messages=[{"role": "user", "content": "fixture extracted text"}])
        path = f"/api/ai/conversations/{conversation.id}/"
        response = self.view_as.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["messages"], [])
        self.assertEqual(response.data["message_count"], 1)
        self.assertEqual(self.normal.get(path).data["messages"], conversation.messages)

    def test_workflow_derived_content_suppressed_for_owner_and_counterparty(self):
        workflow = WorkflowState.objects.create(user=self.customer, counterparty_email=self.customer.email,
                                                counterparty_requested_changes=["fixture clause"])
        ReviewResult.objects.create(workflow=workflow, summary="fixture extracted review")
        CounterDraft.objects.create(workflow=workflow, generated_revised_contract="fixture derived draft")
        paths = ["/api/ai/workflows/", f"/api/ai/workflows/{workflow.id}/",
                 f"/api/ai/counterparty/workflows/{workflow.id}/"]
        for path in paths:
            response = self.view_as.get(path)
            self.assertEqual(response.status_code, 200)
            data = response.data
            data = data["results"][0] if "results" in data else data.get("workflow", data)
            self.assertEqual(data["id"], str(workflow.id))
            self.assertIsNone(data["review_result"])
            self.assertEqual(data["counter_drafts"], [])
            self.assertEqual(data["counterparty_requested_changes"], [])
        normal = self.normal.get(paths[1]).data
        self.assertEqual(normal["review_result"]["summary"], "fixture extracted review")
        self.assertEqual(normal["counter_drafts"][0]["generated_revised_contract"], "fixture derived draft")

    def test_pdf_get_and_head_deny_before_generation(self):
        with patch("backend.api.sol.pdf_views._base_doc") as generate:
            for path in [f"/api/sol/{uuid.uuid4()}/export/pdf/", f"/api/sol/memberships/{uuid.uuid4()}/export/pdf/"]:
                for method in ["get", "head"]:
                    response = getattr(self.view_as, method)(path)
                    self.assertEqual(response.status_code, 403)
            generate.assert_not_called()

    def test_public_share_view_as_denied_anonymous_and_customer_preserved(self):
        token = "fixture-public-capability"
        share = VaultShare.objects.create(owner=self.customer, stored_object=self.upload.stored_object,
                                           token_hash=hashlib.sha256(token.encode()).hexdigest())
        path = f"/api/uploads/shares/{token}/"
        with patch("backend.uploads.services.default_storage") as storage:
            for route in [path, path + "delivery/", path.rstrip("/") + ".json", path + "delivery.json"]:
                for method in ["get", "head"]:
                    self.assertEqual(getattr(self.view_as, method)(route).status_code, 403)
            storage.open.assert_not_called()
            storage.url.assert_not_called()
            storage.size.return_value = 7
            storage.open.side_effect = lambda *args: ContentFile(b"fixture")
            for client in [APIClient(), self.normal]:
                self.assertEqual(client.get(path).status_code, 200)
                response = client.get(path + "delivery/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b"".join(response.streaming_content), b"fixture")
                self.assertNotIn("Location", response)
        listing = self.view_as.get(f"/api/uploads/{self.upload.id}/shares/")
        self.assertEqual(listing.status_code, 200)
        self.assertEqual(listing.data[0]["id"], str(share.id))
        self.assertNotIn(token, str(listing.data))
        self.assertNotIn("share_url", listing.data[0])

    def test_mutations_still_blocked_without_content_side_effects_and_exit_works(self):
        prefix = f"/api/uploads/{self.upload.id}/"
        with patch("backend.uploads.services.default_storage") as storage, \
             patch("backend.api.uploads.views.send_email") as email, \
             patch("backend.api.uploads.views.zipfile.ZipFile") as archive:
            for path in ["/api/uploads/", "/api/uploads/bulk-download/", prefix + "email/", prefix + "shares/",
                         prefix + "duplicate/", f"/api/contracts/{self.contract.id}/documents/"]:
                self.assertEqual(self.view_as.post(path, {}, format="json").status_code, 403)
            for method in ["put", "patch", "delete"]:
                self.assertEqual(getattr(self.view_as, method)(prefix, {}, format="json").status_code, 403)
            storage.open.assert_not_called()
            storage.url.assert_not_called()
            storage.save.assert_not_called()
            email.assert_not_called()
            archive.assert_not_called()
        self.assertEqual(self.view_as.get("/api/users/me/").status_code, 200)
        self.assertEqual(self.view_as.get("/api/operator/me/").status_code, 403)
        self.assertEqual(self.operator.get("/api/uploads/").status_code, 403)
        self.assertEqual(self.view_as.post("/api/operator/view-as/exit/", {}, format="json").status_code, 200)
        self.assertIsNotNone(OperatorViewAsSession.objects.get(pk=self.session_id).ended_at)
        self.assertEqual(self.operator.get("/api/operator/me/").status_code, 200)

    def test_customer_delivery_and_both_contract_parties_keep_access(self):
        with patch("backend.uploads.services.default_storage") as storage:
            storage.size.return_value = len(b"fixture bytes")
            storage.open.return_value = ContentFile(b"fixture bytes")
            response = self.normal.get(f"/api/uploads/{self.upload.id}/delivery/")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(b"".join(response.streaming_content), b"fixture bytes")
            storage.url.return_value = "https://example.invalid/current"
            self.assertEqual(self.normal.get("/api/uploads/").data[0]["file_url"], f"/api/uploads/{self.upload.pk}/delivery/")
            for user in [self.customer, self.party]:
                client = self.bearer(str(AccessToken.for_user(user)))
                response = client.get(f"/api/contracts/{self.contract.id}/documents/")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.data[0]["file_url"], f"/api/contracts/{self.contract.pk}/documents/{self.document.pk}/delivery/")
            self.assertTrue(ContractDocument.objects.filter(pk=self.document.pk).exists())
