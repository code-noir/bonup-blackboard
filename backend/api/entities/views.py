# backend/api/entities/views.py
#
# BusinessEntity CRUD API.
# All endpoints require authentication (global default).

from django.shortcuts import get_object_or_404
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.billing.gates import can_create_business_entity, max_businesses
from backend.users.models import BusinessEntity


class BusinessEntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessEntity
        fields = [
            "id",
            "name",
            "business_type",
            "description",
            "industry",
            "address",
            "website",
            "founded_date",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class EntityListCreateView(APIView):
    """GET /api/entities/  POST /api/entities/"""

    def get(self, request):
        entities = BusinessEntity.objects.filter(
            owner=request.user, is_active=True
        )
        serializer = BusinessEntitySerializer(entities, many=True)
        return Response({
            "count": entities.count(),
            "max_allowed": max_businesses(request.user),
            "results": serializer.data,
        })

    def post(self, request):
        allowed, msg = can_create_business_entity(request.user)
        if not allowed:
            return Response({"error": msg}, status=status.HTTP_403_FORBIDDEN)

        serializer = BusinessEntitySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entity = serializer.save(owner=request.user)
        return Response(BusinessEntitySerializer(entity).data, status=status.HTTP_201_CREATED)


class EntityDetailView(APIView):
    """GET/PUT/DELETE /api/entities/{id}/"""

    def _get_entity(self, request, entity_id):
        return get_object_or_404(BusinessEntity, pk=entity_id, owner=request.user)

    def get(self, request, entity_id):
        entity = self._get_entity(request, entity_id)
        return Response(BusinessEntitySerializer(entity).data)

    def put(self, request, entity_id):
        entity = self._get_entity(request, entity_id)
        serializer = BusinessEntitySerializer(entity, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(BusinessEntitySerializer(entity).data)

    def delete(self, request, entity_id):
        entity = self._get_entity(request, entity_id)
        entity.is_active = False
        entity.save(update_fields=["is_active", "updated_at"])
        return Response({"status": "deactivated"})
