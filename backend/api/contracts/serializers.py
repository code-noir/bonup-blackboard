# backend/api/contracts/serializers.py

from rest_framework import serializers
from backend.contracts.models import Contract


class ContractSerializer(serializers.ModelSerializer):

    class Meta:
        model = Contract
        fields = [
            "id",
            "initiator",
            "counterparty_email",
            "structure_type",
            "max_versions",
            "created_at",
            "is_active",
        ]
        read_only_fields = ["id", "created_at", "initiator"]

