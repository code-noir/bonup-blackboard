# backend/api/payment_templates/views.py

from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from backend.contract_templates.models import PaymentTemplate


class PaymentTemplatesViewSet(ViewSet):
    """
    GET /api/payment-templates/ — list active payment templates
    """

    def list(self, request):
        qs = PaymentTemplate.objects.filter(is_active=True).select_related(
            "contract_template"
        )

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        schedule_type = request.query_params.get("schedule_type")
        if schedule_type:
            qs = qs.filter(schedule_type=schedule_type)

        return Response([_serialize(t) for t in qs])


def _serialize(t):
    return {
        "id": str(t.id),
        "name": t.name,
        "description": t.description,
        "content": t.content,
        "schedule_type": t.schedule_type,
        "category": t.category,
        "contract_template_id": str(t.contract_template_id) if t.contract_template_id else None,
    }
