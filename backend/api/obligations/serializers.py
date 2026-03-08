from rest_framework import serializers
from backend.contracts.models import Obligation


class ObligationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Obligation
        fields = "__all__"
