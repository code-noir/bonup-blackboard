# backend/api/obligation_templates/views.py

from rest_framework.response import Response
from rest_framework.viewsets import ViewSet

from backend.contract_templates.models import ObligationTemplate


class ObligationTemplatesViewSet(ViewSet):
    """
    GET /api/obligation-templates/ — list active obligation templates
    """

    def list(self, request):
        qs = ObligationTemplate.objects.filter(is_active=True).select_related(
            "contract_template"
        )

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        return Response([_serialize(t) for t in qs])


def _serialize(t):
    return {
        "id": str(t.id),
        "name": t.name,
        "description": t.description,
        "content": t.content,
        "category": t.category,
        "contract_template_id": str(t.contract_template_id) if t.contract_template_id else None,
    }
