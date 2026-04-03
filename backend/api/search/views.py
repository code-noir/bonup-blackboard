# backend/api/search/views.py

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.contracts.models import Contract
from backend.contract_templates.models import ContractTemplate
from backend.users.models import BonUserProfile

User = get_user_model()

GLOBAL_RESULT_LIMIT = 10


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_contract(c):
    return {
        "id": str(c.id),
        "counterparty_email": c.counterparty_email,
        "structure_type": c.structure_type,
        "state": c.state,
        "is_active": c.is_active,
        "created_at": c.created_at,
    }


def _serialize_template(t):
    return {
        "id": str(t.id),
        "name": t.name,
        "category": t.category,
        "subcategory": t.subcategory,
        "structure_type": t.structure_type,
        "tier_required": t.tier_required,
    }


def _serialize_user(profile):
    return {
        "bon_id": profile.bon_id,
        "username": profile.user.username,
        "first_name": profile.user.first_name,
        "last_name": profile.user.last_name,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _party_q(user):
    return Q(initiator=user) | Q(counterparty_email=user.email)


# ---------------------------------------------------------------------------
# GET /api/search/?q=
# ---------------------------------------------------------------------------

class GlobalSearchView(APIView):

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        if not q:
            return Response({"error": "q parameter is required"}, status=status.HTTP_400_BAD_REQUEST)

        contracts = (
            Contract.objects
            .filter(_party_q(request.user))
            .filter(
                Q(counterparty_email__icontains=q)
                | Q(structure_type__icontains=q)
                | Q(state__icontains=q)
            )
            .order_by("-created_at")[:GLOBAL_RESULT_LIMIT]
        )

        templates = (
            ContractTemplate.objects
            .filter(is_active=True)
            .filter(
                Q(name__icontains=q)
                | Q(category__icontains=q)
                | Q(subcategory__icontains=q)
            )
            .order_by("name")[:GLOBAL_RESULT_LIMIT]
        )

        users = (
            BonUserProfile.objects
            .select_related("user")
            .exclude(user=request.user)
            .filter(
                Q(bon_id__icontains=q)
                | Q(user__username__icontains=q)
                | Q(user__first_name__icontains=q)
                | Q(user__last_name__icontains=q)
            )
            .order_by("bon_id")[:GLOBAL_RESULT_LIMIT]
        )

        return Response({
            "contracts": [_serialize_contract(c) for c in contracts],
            "templates": [_serialize_template(t) for t in templates],
            "users": [_serialize_user(p) for p in users],
        })


# ---------------------------------------------------------------------------
# GET /api/search/contracts/?q=&status=&structure_type=&date_from=&date_to=
# ---------------------------------------------------------------------------

class ContractSearchView(APIView):

    def get(self, request):
        q = request.query_params.get("q", "").strip()

        qs = Contract.objects.filter(_party_q(request.user))

        if q:
            qs = qs.filter(
                Q(counterparty_email__icontains=q)
                | Q(structure_type__icontains=q)
                | Q(state__icontains=q)
            )

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(state=status_filter)

        structure_type = request.query_params.get("structure_type")
        if structure_type:
            qs = qs.filter(structure_type=structure_type)

        date_from = request.query_params.get("date_from")
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)

        date_to = request.query_params.get("date_to")
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        qs = qs.order_by("-created_at")

        return Response([_serialize_contract(c) for c in qs])


# ---------------------------------------------------------------------------
# GET /api/search/templates/?q=&category=
# ---------------------------------------------------------------------------

class TemplateSearchView(APIView):

    def get(self, request):
        q = request.query_params.get("q", "").strip()

        qs = ContractTemplate.objects.filter(is_active=True)

        if q:
            qs = qs.filter(
                Q(name__icontains=q)
                | Q(category__icontains=q)
                | Q(subcategory__icontains=q)
            )

        category = request.query_params.get("category")
        if category:
            qs = qs.filter(category=category)

        qs = qs.order_by("name")

        return Response([_serialize_template(t) for t in qs])
