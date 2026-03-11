# backend/api/contracts/serializers.py

from rest_framework import serializers
from backend.contracts.models import Contract


class ContractSerializer(serializers.ModelSerializer):

    class Meta:
        model = Contract
        fields = "__all__"