from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.operator.permissions import IsOperator
from backend.bonup.models import ProductDirectionTask

from .serializers import ProductDirectionTaskSerializer
from .proposal import ProposalReadFailure, read_product_direction_proposal
from .runtime import (
    ProductRuntimeFailure,
    ProductRuntimeUnavailable,
    agent_control_task_id_for,
    runtime_request_for,
    submit_product_direction_task,
)


_DEFAULT_PAGE_SIZE = 50
_MAX_PAGE_SIZE = 100


def _page_value(value, default, maximum=None):
    try:
        result = int(value)
    except (TypeError, ValueError):
        result = default
    result = max(1, result)
    return min(maximum, result) if maximum is not None else result


class ProductDirectionTaskListCreateView(APIView):
    permission_classes = [IsOperator]

    def get(self, request):
        page = _page_value(request.query_params.get("page", 1), 1)
        page_size = _page_value(
            request.query_params.get("page_size", _DEFAULT_PAGE_SIZE),
            _DEFAULT_PAGE_SIZE,
            _MAX_PAGE_SIZE,
        )
        tasks = ProductDirectionTask.objects.select_related("created_by")
        total = tasks.count()
        offset = (page - 1) * page_size
        results = ProductDirectionTaskSerializer(
            tasks[offset : offset + page_size], many=True
        ).data
        return Response({
            "count": total,
            "page": page,
            "page_size": page_size,
            "results": results,
        })

    def post(self, request):
        serializer = ProductDirectionTaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        task = serializer.save(created_by=request.administrator)
        return Response(
            ProductDirectionTaskSerializer(task).data,
            status=status.HTTP_201_CREATED,
        )


class ProductDirectionTaskDetailView(APIView):
    permission_classes = [IsOperator]

    def get(self, request, task_id):
        task = get_object_or_404(
            ProductDirectionTask.objects.select_related("created_by"),
            pk=task_id,
        )
        return Response(ProductDirectionTaskSerializer(task).data)


class ProductDirectionTaskProposalView(APIView):
    """Expose only the verified product proposal projection."""

    permission_classes = [IsOperator]

    def get(self, request, task_id):
        task = get_object_or_404(ProductDirectionTask, pk=task_id)
        try:
            proposal = read_product_direction_proposal(task)
        except ProposalReadFailure as error:
            http_status = (
                status.HTTP_404_NOT_FOUND
                if error.reason == "PROPOSAL_NOT_AVAILABLE"
                else status.HTTP_409_CONFLICT
            )
            return Response({"reason": error.reason}, status=http_status)
        return Response(proposal)


class ProductDirectionTaskSubmitView(APIView):
    """Claim one submitted task, then invoke only the trusted PROD seam."""

    permission_classes = [IsOperator]

    def post(self, request, task_id):
        if request.data:
            return Response(
                {"detail": "Runtime controls are not accepted by this action."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            task = get_object_or_404(
                ProductDirectionTask.objects.select_for_update(), pk=task_id)
            if task.status != ProductDirectionTask.STATUS_SUBMITTED:
                return Response(
                    {
                        "detail": "Product-direction task is not submit-ready.",
                        "task": ProductDirectionTaskSerializer(task).data,
                    },
                    status=status.HTTP_409_CONFLICT,
                )
            task.agent_control_task_id = agent_control_task_id_for(task.id)
            task.status = ProductDirectionTask.STATUS_RUNNING
            task.runtime_failure_reason = None
            task.save(update_fields=[
                "agent_control_task_id", "status", "runtime_failure_reason", "updated_at",
            ])

        runtime_request = runtime_request_for(task)
        try:
            result = submit_product_direction_task(runtime_request)
        except ProductRuntimeUnavailable:
            return self._block(task.id, "RUNTIME_UNAVAILABLE", status.HTTP_503_SERVICE_UNAVAILABLE)
        except ProductRuntimeFailure as error:
            return self._block(task.id, error.reason, status.HTTP_502_BAD_GATEWAY)

        with transaction.atomic():
            task = ProductDirectionTask.objects.select_for_update().get(pk=task.id)
            task.status = ProductDirectionTask.STATUS_WORKING_PROPOSAL
            task.proposal_artifact_id = result.proposal_artifact_id
            task.proposal_id = result.proposal_id
            task.proposal_digest = result.proposal_digest
            task.runtime_failure_reason = None
            task.save(update_fields=[
                "status", "proposal_artifact_id", "proposal_id", "proposal_digest",
                "runtime_failure_reason", "updated_at",
            ])
        return Response(ProductDirectionTaskSerializer(task).data)

    @staticmethod
    def _block(task_id, reason, http_status):
        with transaction.atomic():
            task = ProductDirectionTask.objects.select_for_update().get(pk=task_id)
            task.status = ProductDirectionTask.STATUS_BLOCKED
            task.runtime_failure_reason = reason
            task.save(update_fields=["status", "runtime_failure_reason", "updated_at"])
        return Response(
            {
                "detail": "Trusted PROD-01 runtime did not produce a proposal.",
                "reason": reason,
                "task": ProductDirectionTaskSerializer(task).data,
            },
            status=http_status,
        )
