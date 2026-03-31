# backend/contract_templates/services/template_instantiation_service.py

import json
from datetime import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime
from django.utils import timezone

from backend.contract_templates.models import ContractTemplate
from backend.contracts.models import (
    Contract,
    ContractVersion,
    ContractObligation,
    ContractServiceObligation,
)
from backend.engine.lifecycle_core.obligations.primitives import PaymentObligation
from backend.engine.lifecycle_core.scheduler.obligation_scheduler import (
    ObligationScheduler,
)

User = get_user_model()

_FREQUENCY_INTERVAL_DEFAULTS = {
    "one_time": 1,
    "per_session": 7,
    "weekly": 7,
    "monthly": 30,
    "installment": 30,
}


class TemplateInstantiationError(Exception):
    pass


class TemplateInstantiationService:
    """
    Instantiates a ContractTemplate into a live Contract.

    Responsibilities:
    - Validate required guided field values
    - Render clause token bodies
    - Create Contract + draft ContractVersion
    - Generate and persist obligations when both parties are known users
    """

    def instantiate(self, template_id, guided_field_values, initiator, counterparty_email, start_date_str):
        """
        Returns a dict with keys:
            contract, version, payment_obligations, service_obligations, counterparty_found
        """
        template = self._load_template(template_id)
        self._validate_required_fields(template, guided_field_values)

        token_context = self._build_token_context(guided_field_values, initiator, counterparty_email)
        rendered_clauses = self._render_clauses(template, token_context)
        start_date = self._parse_start_date(start_date_str)

        counterparty_user = User.objects.filter(email=counterparty_email).first()

        with transaction.atomic():
            contract = Contract.objects.create(
                initiator=initiator,
                counterparty_email=counterparty_email,
                structure_type=template.structure_type,
            )

            content_snapshot = json.dumps({
                "template_id": str(template.id),
                "template_name": template.name,
                "category": template.category,
                "subcategory": template.subcategory,
                "guided_field_values": guided_field_values,
                "clauses": rendered_clauses,
            }, indent=2)

            version = ContractVersion.objects.create(
                contract=contract,
                version_number=1,
                created_by=initiator,
                content_snapshot=content_snapshot,
                status="draft",
            )

            payment_obligations, service_obligations = self._create_obligations(
                template, token_context, contract, version, initiator, counterparty_user, start_date
            )

        return {
            "contract": contract,
            "version": version,
            "payment_obligations": payment_obligations,
            "service_obligations": service_obligations,
            "counterparty_found": counterparty_user is not None,
        }

    # ------------------------------------------------------------------
    # PRIVATE HELPERS
    # ------------------------------------------------------------------

    def _load_template(self, template_id):
        try:
            return ContractTemplate.objects.prefetch_related(
                "guided_fields", "clauses"
            ).select_related("obligation_pattern").get(id=template_id, is_active=True)
        except ContractTemplate.DoesNotExist:
            raise TemplateInstantiationError(f"Template {template_id} not found or inactive.")

    def _validate_required_fields(self, template, values):
        missing = []
        for field in template.guided_fields.filter(is_required=True):
            if field.field_key not in values or values[field.field_key] in (None, ""):
                missing.append(field.field_key)
        if missing:
            raise TemplateInstantiationError(
                f"Missing required guided fields: {', '.join(missing)}"
            )

    def _build_token_context(self, guided_field_values, initiator, counterparty_email):
        ctx = {k: str(v) for k, v in guided_field_values.items()}

        # Computed tokens
        rate_str = ctx.get("rate_per_session")
        sessions_str = ctx.get("num_sessions")
        if rate_str and sessions_str:
            try:
                total = Decimal(str(rate_str)) * Decimal(str(sessions_str))
                ctx["total_package_value"] = str(total)
            except Exception:
                pass

        # Context tokens
        initiator_name = initiator.get_full_name().strip() or initiator.email
        ctx["initiator_name"] = initiator_name
        ctx["counterparty_name"] = counterparty_email

        return ctx

    def _render_clauses(self, template, token_context):
        rendered = []
        for clause in template.clauses.all():
            body = clause.body
            for key, value in token_context.items():
                body = body.replace("{{" + key + "}}", str(value))
            rendered.append({
                "clause_type": clause.clause_type,
                "title": clause.title,
                "body": body,
                "is_required": clause.is_required,
                "is_conditional": clause.is_conditional,
                "order": clause.order,
            })
        return rendered

    def _parse_start_date(self, start_date_str):
        if not start_date_str:
            return timezone.now()

        dt = parse_datetime(str(start_date_str))
        if dt:
            return dt

        d = parse_date(str(start_date_str))
        if d:
            return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)

        raise TemplateInstantiationError(
            f"Invalid start_date format: '{start_date_str}'. Use YYYY-MM-DD or ISO datetime."
        )

    def _create_obligations(self, template, token_context, contract, version, initiator, counterparty_user, start_date):
        payment_obligations = []
        service_obligations = []

        try:
            pattern = template.obligation_pattern
        except Exception:
            return payment_obligations, service_obligations

        if not counterparty_user:
            return payment_obligations, service_obligations

        amount_str = token_context.get(pattern.amount_token, "0") if pattern.amount_token else "0"
        installments_str = token_context.get(pattern.installments_token, "1") if pattern.installments_token else "1"

        try:
            rate = Decimal(str(amount_str))
            installments = max(1, int(installments_str))
        except (ValueError, TypeError) as exc:
            raise TemplateInstantiationError(
                f"Could not parse obligation amounts from tokens: {exc}"
            )

        total_amount = rate * installments

        if pattern.interval_days_token and pattern.interval_days_token in token_context:
            try:
                interval_days = int(token_context[pattern.interval_days_token])
            except (ValueError, TypeError):
                interval_days = _FREQUENCY_INTERVAL_DEFAULTS.get(pattern.frequency_type, 7)
        else:
            interval_days = _FREQUENCY_INTERVAL_DEFAULTS.get(pattern.frequency_type, 7)

        engine_obligations = ObligationScheduler.generate_parallel_schedule(
            obligor_id=initiator.pk,
            obligee_id=counterparty_user.pk,
            total_amount=total_amount,
            installments=installments,
            start_date=start_date,
            interval_days=interval_days,
            service_description=template.name,
        )

        installment_num = 1
        for ob in engine_obligations:
            if isinstance(ob, PaymentObligation):
                if pattern.obligation_type in ("payment", "both"):
                    payment_obligations.append(
                        ContractObligation.objects.create(
                            contract=contract,
                            version=version,
                            obligor_id=ob.obligor_id,
                            obligee_id=ob.obligee_id,
                            installment_number=installment_num,
                            amount_due=ob.amount_due,
                            due_date=ob.due_date,
                            state="active",
                        )
                    )
                    installment_num += 1
            else:
                if pattern.obligation_type in ("service", "both"):
                    service_obligations.append(
                        ContractServiceObligation.objects.create(
                            contract=contract,
                            version=version,
                            obligor_id=ob.obligor_id,
                            obligee_id=ob.obligee_id,
                            description=ob.description,
                            due_date=ob.due_date,
                            state="active",
                        )
                    )

        return payment_obligations, service_obligations
