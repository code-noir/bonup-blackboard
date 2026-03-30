# backend/api/contracts/promotion_views.py

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.contracts.serializers import (
    ObligationPromotionSerializer,
    PromotedServiceObligationSerializer,
    PromoteExecutionEventSerializer,
)
from backend.api.contracts.services.obligation_promotion_service import (
    ObligationPromotionService,
)
from backend.contracts.models import ObligationExecutionEvent
from .permissions import contract_party_response, get_contract_for_object, is_party


class ExecutionEventPromotionAPIView(APIView):
    """
    POST /api/contracts/execution-events/<execution_event_id>/promote/
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ObligationPromotionService()

    def post(self, request, execution_event_id):
        event = get_object_or_404(ObligationExecutionEvent, id=execution_event_id)
        contract = get_contract_for_object(event)
        if not is_party(request.user, contract):
            return contract_party_response()

        serializer = PromoteExecutionEventSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        promotion = self.service.promote_execution_event_to_service_obligation(
            execution_event_id=execution_event_id,
            summary=serializer.validated_data.get("summary") or None,
            due_date=serializer.validated_data.get("due_date"),
        )

        promotion_payload = {
            "promotion_id": promotion.id,
            "promotion_type": promotion.promotion_type,
            "summary": promotion.summary,
            "source_execution_event_id": promotion.source_execution_event_id,
            "parent_service_obligation_id": promotion.parent_service_obligation_id,
            "promoted_service_obligation_id": promotion.promoted_service_obligation_id,
            "created_at": promotion.created_at,
        }

        promoted = promotion.promoted_service_obligation
        promoted_payload = {
            "obligation_id": promoted.id,
            "contract_id": promoted.contract_id,
            "description": promoted.description,
            "due_date": promoted.due_date,
            "state": promoted.state,
            "obligor_id": promoted.obligor_id,
            "obligee_id": promoted.obligee_id,
        }

        return Response(
            {
                "promotion": ObligationPromotionSerializer(promotion_payload).data,
                "promoted_service_obligation": PromotedServiceObligationSerializer(
                    promoted_payload
                ).data,
            },
            status=status.HTTP_201_CREATED,
        )
