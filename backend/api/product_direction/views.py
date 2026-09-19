from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.api.operator.permissions import IsOperator
from backend.bonup.models import ProductDirectionTask

from .serializers import ProductDirectionTaskSerializer


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
