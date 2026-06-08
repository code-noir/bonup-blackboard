# Generated for Agreement Exchange MVP

import uuid

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("contracts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AgreementExchange",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("counterparty_email", models.EmailField(max_length=254)),
                ("status", models.CharField(choices=[("draft", "Draft"), ("sent", "Sent"), ("viewed", "Viewed"), ("counterparty_review", "Counterparty review"), ("changes_requested", "Changes requested"), ("initiator_review", "Initiator review"), ("updated_version_sent", "Updated version sent"), ("ready_to_sign", "Ready to sign"), ("signed", "Signed"), ("rejected", "Rejected")], default="draft", max_length=32)),
                ("current_actor", models.CharField(choices=[("initiator", "Initiator"), ("counterparty", "Counterparty"), ("none", "None")], default="initiator", max_length=16)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("contract", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="agreement_exchanges", to="contracts.contract")),
                ("counterparty_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="counterparty_agreement_exchanges", to=settings.AUTH_USER_MODEL)),
                ("current_contract_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="agreement_exchanges", to="contracts.contractversion")),
                ("initiator", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="initiated_agreement_exchanges", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="AgreementExchangeEvent",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("actor_email", models.EmailField(blank=True, max_length=254, null=True)),
                ("actor_role", models.CharField(choices=[("initiator", "Initiator"), ("counterparty", "Counterparty"), ("system", "System")], default="system", max_length=16)),
                ("event_type", models.CharField(max_length=80)),
                ("message", models.TextField(blank=True, default="")),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="agreement_exchange_events", to=settings.AUTH_USER_MODEL)),
                ("exchange", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="agreement_exchange.agreementexchange")),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="AgreementExchangeRequest",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("requested_by_email", models.EmailField(blank=True, default="", max_length=254)),
                ("target_section_id", models.CharField(blank=True, max_length=128, null=True)),
                ("target_section_title", models.CharField(blank=True, default="", max_length=255)),
                ("request_category", models.CharField(choices=[("recitals_background", "Recitals / Background"), ("terms_and_conditions", "Terms and Conditions"), ("obligations", "Obligations"), ("payment_terms", "Payment Terms"), ("confidentiality", "Confidentiality"), ("intellectual_property", "Intellectual Property"), ("termination", "Termination"), ("dispute_resolution", "Dispute resolution"), ("governing_law", "Governing Law")], default="recitals_background", max_length=40)),
                ("action_type", models.CharField(choices=[("replace_clause", "Replace clause"), ("add_clause", "Add clause"), ("remove_clause", "Remove clause"), ("clarify_clause", "Clarify clause")], max_length=32)),
                ("template_key", models.CharField(blank=True, max_length=80, null=True)),
                ("proposed_text", models.TextField()),
                ("reason", models.TextField(blank=True, null=True)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("accepted", "Accepted"), ("edited", "Edited"), ("rejected", "Rejected"), ("withdrawn", "Withdrawn")], default="pending", max_length=16)),
                ("initiator_response", models.TextField(blank=True, null=True)),
                ("pending_next_version_text", models.TextField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("exchange", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="requests", to="agreement_exchange.agreementexchange")),
                ("requested_by_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="agreement_exchange_requests", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["created_at"],
            },
        ),
        migrations.CreateModel(
            name="AgreementExchangeSignature",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("signer_email", models.EmailField(max_length=254)),
                ("signer_role", models.CharField(choices=[("initiator", "Initiator"), ("counterparty", "Counterparty")], max_length=16)),
                ("typed_name", models.CharField(blank=True, max_length=255, null=True)),
                ("signature_text", models.TextField(blank=True, null=True)),
                ("signed_at", models.DateTimeField(auto_now_add=True)),
                ("ip_address", models.GenericIPAddressField(blank=True, null=True)),
                ("user_agent", models.TextField(blank=True, null=True)),
                ("exchange", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="signatures", to="agreement_exchange.agreementexchange")),
                ("signed_version", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="agreement_exchange_signatures", to="contracts.contractversion")),
                ("signer_user", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="agreement_exchange_signatures", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["signed_at"],
            },
        ),
        migrations.AddIndex(
            model_name="agreementexchange",
            index=models.Index(fields=["contract", "current_contract_version", "counterparty_email"], name="agreement_e_contrac_940777_idx"),
        ),
        migrations.AddIndex(
            model_name="agreementexchange",
            index=models.Index(fields=["initiator", "status"], name="agreement_e_initiat_f568de_idx"),
        ),
        migrations.AddIndex(
            model_name="agreementexchangeevent",
            index=models.Index(fields=["exchange", "created_at"], name="agreement_e_exchang_39dc32_idx"),
        ),
        migrations.AddIndex(
            model_name="agreementexchangerequest",
            index=models.Index(fields=["exchange", "status"], name="agreement_e_exchang_97ff73_idx"),
        ),
        migrations.AddIndex(
            model_name="agreementexchangerequest",
            index=models.Index(fields=["request_category"], name="agreement_e_request_822e16_idx"),
        ),
        migrations.AddIndex(
            model_name="agreementexchangesignature",
            index=models.Index(fields=["exchange", "signer_role"], name="agreement_e_exchang_067782_idx"),
        ),
    ]
