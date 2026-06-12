from rest_framework import serializers

from backend.agreement_exchange.models import AgreementExchangeRequest
from backend.agreement_exchange.services import extract_contract_sections




class AgreementExchangeFromWorkflowSerializer(serializers.Serializer):
    workflow_id = serializers.UUIDField()

class AgreementExchangeCreateSerializer(serializers.Serializer):
    contract_id = serializers.UUIDField()
    contract_version_id = serializers.UUIDField()
    counterparty_email = serializers.EmailField()


class AgreementExchangeRequestSerializer(serializers.ModelSerializer):
    requested_by_email = serializers.EmailField(read_only=True)

    class Meta:
        model = AgreementExchangeRequest
        fields = [
            "id",
            "exchange",
            "requested_by_user",
            "requested_by_email",
            "target_section_id",
            "target_section_title",
            "request_category",
            "action_type",
            "template_key",
            "proposed_text",
            "reason",
            "status",
            "initiator_response",
            "pending_next_version_text",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "exchange",
            "requested_by_user",
            "requested_by_email",
            "status",
            "initiator_response",
            "pending_next_version_text",
            "created_at",
            "updated_at",
        ]

    def validate_proposed_text(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("proposed_text is required.")
        return value


class AgreementExchangeRequestResponseSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["accept", "edit", "reject"])
    final_text = serializers.CharField(required=False, allow_blank=True)
    initiator_response = serializers.CharField(required=False, allow_blank=True)


class AgreementExchangeRestartSerializer(serializers.Serializer):
    source_version_id = serializers.UUIDField()
    counterparty_email = serializers.EmailField(required=False, allow_blank=True)


class AgreementExchangeRejectSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)


class AgreementExchangeSignSerializer(serializers.Serializer):
    typed_name = serializers.CharField(required=False, allow_blank=True)
    signature_text = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if not (attrs.get("typed_name") or attrs.get("signature_text")):
            raise serializers.ValidationError("typed_name or signature_text is required.")
        return attrs
