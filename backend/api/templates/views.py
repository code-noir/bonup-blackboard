# backend/api/templates/views.py

from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from django.shortcuts import get_object_or_404

from backend.contract_templates.models import ContractTemplate
from backend.contract_templates.services.template_instantiation_service import (
    TemplateInstantiationService,
    TemplateInstantiationError,
)


class TemplatesViewSet(ViewSet):
    """
    GET  /api/templates/           — list active templates
    GET  /api/templates/<id>/      — template detail with guided fields and clauses
    POST /api/templates/<id>/instantiate/ — create contract from template
    """

    def list(self, request):
        """
        Returns all active templates, optionally filtered by ?tier=.
        """
        qs = ContractTemplate.objects.filter(is_active=True).prefetch_related(
            "guided_fields", "clauses"
        )

        tier = request.query_params.get("tier")
        if tier:
            qs = qs.filter(tier_required=tier)

        templates = [_serialize_template_summary(t) for t in qs]
        return Response(templates)

    def retrieve(self, request, pk=None):
        """
        Returns a single template with all guided fields and clauses.
        """
        template = get_object_or_404(
            ContractTemplate.objects.prefetch_related("guided_fields", "clauses"),
            pk=pk,
            is_active=True,
        )
        return Response(_serialize_template_detail(template))

    @action(detail=True, methods=["post"], url_path="instantiate")
    def instantiate(self, request, pk=None):
        """
        Instantiates a template into a live Contract.

        Expected body:
        {
            "counterparty_email": "client@example.com",
            "start_date": "2026-04-01",
            "guided_field_values": { ... }
        }
        """
        counterparty_email = request.data.get("counterparty_email", "").strip()
        start_date = request.data.get("start_date", "").strip()
        guided_field_values = request.data.get("guided_field_values", {})

        if not counterparty_email:
            return Response(
                {"error": "counterparty_email is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not start_date:
            return Response(
                {"error": "start_date is required (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not isinstance(guided_field_values, dict):
            return Response(
                {"error": "guided_field_values must be an object."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = TemplateInstantiationService()
        try:
            result = service.instantiate(
                template_id=pk,
                guided_field_values=guided_field_values,
                initiator=request.user,
                counterparty_email=counterparty_email,
                start_date_str=start_date,
            )
        except TemplateInstantiationError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        contract = result["contract"]
        version = result["version"]
        payment_obligations = result["payment_obligations"]
        service_obligations = result["service_obligations"]
        counterparty_found = result["counterparty_found"]

        return Response(
            {
                "contract_id": str(contract.id),
                "contract_structure_type": contract.structure_type,
                "counterparty_email": contract.counterparty_email,
                "version_id": str(version.id),
                "version_number": version.version_number,
                "version_status": version.status,
                "payment_obligations_created": len(payment_obligations),
                "service_obligations_created": len(service_obligations),
                "counterparty_found": counterparty_found,
                "note": (
                    None if counterparty_found
                    else "Counterparty email not registered. "
                         "Obligations will be created when both parties are known users."
                ),
                "payment_obligations": [
                    {
                        "id": str(ob.id),
                        "installment_number": ob.installment_number,
                        "amount_due": str(ob.amount_due),
                        "due_date": ob.due_date.isoformat(),
                        "state": ob.state,
                    }
                    for ob in payment_obligations
                ],
                "service_obligations": [
                    {
                        "id": str(ob.id),
                        "description": ob.description,
                        "due_date": ob.due_date.isoformat(),
                        "state": ob.state,
                    }
                    for ob in service_obligations
                ],
            },
            status=status.HTTP_201_CREATED,
        )


# ------------------------------------------------------------------
# SERIALIZATION HELPERS
# ------------------------------------------------------------------

def _serialize_template_summary(template):
    return {
        "id": str(template.id),
        "category": template.category,
        "subcategory": template.subcategory,
        "name": template.name,
        "description": template.description,
        "structure_type": template.structure_type,
        "tier_required": template.tier_required,
    }


def _serialize_template_detail(template):
    data = _serialize_template_summary(template)
    data["guided_fields"] = [
        {
            "id": str(f.id),
            "field_key": f.field_key,
            "label": f.label,
            "field_type": f.field_type,
            "choices": f.choices,
            "is_required": f.is_required,
            "order": f.order,
        }
        for f in template.guided_fields.all()
    ]
    data["clauses"] = [
        {
            "id": str(c.id),
            "clause_type": c.clause_type,
            "title": c.title,
            "body": c.body,
            "is_required": c.is_required,
            "is_conditional": c.is_conditional,
            "condition_description": c.condition_description,
            "order": c.order,
        }
        for c in template.clauses.all()
    ]
    return data
