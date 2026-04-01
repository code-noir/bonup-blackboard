# backend/api/activity/views.py

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.activity.models import ContractActivity
from backend.contracts.models import Contract
from backend.api.contracts.permissions import contract_party_response, is_party

_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 100


def _paginate(qs, request):
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = min(_MAX_PAGE_SIZE, max(1, int(request.query_params.get("page_size", _DEFAULT_PAGE_SIZE))))
    except (ValueError, TypeError):
        page_size = _DEFAULT_PAGE_SIZE

    total = qs.count()
    offset = (page - 1) * page_size
    results = [_serialize(a) for a in qs[offset:offset + page_size]]
    return Response({
        "count": total,
        "page": page,
        "page_size": page_size,
        "results": results,
    })


def _serialize(activity):
    return {
        "id": str(activity.id),
        "contract_id": str(activity.contract_id),
        "user_id": activity.user_id,
        "activity_type": activity.activity_type,
        "description": activity.description,
        "metadata": activity.metadata,
        "created_at": activity.created_at,
    }


def _party_q(user):
    return Q(contract__initiator=user) | Q(contract__counterparty_email=user.email)


class ActivityListAPIView(APIView):
    """
    GET /api/activity/

    All activity across the authenticated user's contracts.

    Query params:
    - contract_id=<uuid>       narrow to a single contract
    - activity_type=<type>     filter by activity type
    - page=<int>               default 1
    - page_size=<int>          default 20, max 100
    """

    def get(self, request):
        qs = ContractActivity.objects.filter(_party_q(request.user))

        contract_id = request.query_params.get("contract_id")
        if contract_id:
            qs = qs.filter(contract_id=contract_id)

        activity_type = request.query_params.get("activity_type")
        if activity_type:
            qs = qs.filter(activity_type=activity_type)

        return _paginate(qs, request)


class ContractActivityAPIView(APIView):
    """
    GET /api/contracts/<contract_id>/activity/

    Activity for a specific contract. Requires party membership.
    """

    def get(self, request, contract_id):
        contract = get_object_or_404(Contract, pk=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        qs = ContractActivity.objects.filter(contract=contract)
        return _paginate(qs, request)
