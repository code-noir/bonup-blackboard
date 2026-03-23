# backend/api/contracts/serializers.py

from rest_framework import serializers
from backend.contracts.models import Contract


class ContractSerializer(serializers.ModelSerializer):

    class Meta:
        model = Contract
        fields = "__all__"

class ObligationExecutionSessionSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    status = serializers.CharField(read_only=True)
    started_at = serializers.DateTimeField()
    ended_at = serializers.DateTimeField(allow_null=True, read_only=True)


class OpenExecutionSessionSerializer(serializers.Serializer):
    started_at = serializers.DateTimeField(required=False)

class RecordExecutionItemSerializer(serializers.Serializer):
    task = serializers.CharField()
    observation = serializers.CharField()
    summary = serializers.CharField()
    estimated_duration_minutes = serializers.IntegerField(min_value=0)
    estimated_cost_amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    estimated_cost_currency = serializers.CharField()
    planned_execution_time = serializers.DateTimeField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False)


class ExecutionDecisionSerializer(serializers.Serializer):
    decision_status = serializers.CharField()
    authorization_mode = serializers.CharField()
    billing_mode = serializers.CharField()
    promotion_suggestion = serializers.CharField()
    required_next_step = serializers.CharField()
    rationale = serializers.CharField()
    proof_tags = serializers.ListField(child=serializers.CharField())


class ObligationExecutionEventSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    event_type = serializers.CharField(read_only=True)
    task = serializers.CharField(allow_null=True, read_only=True)
    observation = serializers.CharField(allow_null=True, read_only=True)
    summary = serializers.CharField(read_only=True)
    estimated_duration_minutes = serializers.IntegerField(allow_null=True, read_only=True)
    estimated_cost_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        allow_null=True,
        read_only=True,
    )
    estimated_cost_currency = serializers.CharField(allow_null=True, read_only=True)
    planned_execution_time = serializers.DateTimeField(allow_null=True, read_only=True)
    metadata = serializers.JSONField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)


class CloseExecutionSessionSerializer(serializers.Serializer):
    ended_at = serializers.DateTimeField(required=False)

class ApprovalRequestCreateSerializer(serializers.Serializer):
    execution_event_id = serializers.UUIDField()
    summary = serializers.CharField()
    requested_by_id = serializers.IntegerField(required=False, allow_null=True)
    requested_from_id = serializers.IntegerField(required=False, allow_null=True)
    metadata = serializers.JSONField(required=False)


class ApprovalRequestSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    approval_type = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)
    metadata = serializers.JSONField(read_only=True)
    requested_at = serializers.DateTimeField(read_only=True)
    decided_at = serializers.DateTimeField(read_only=True, allow_null=True)
    execution_event_id = serializers.UUIDField(read_only=True, allow_null=True)
    payment_obligation_id = serializers.UUIDField(read_only=True, allow_null=True)
    service_obligation_id = serializers.UUIDField(read_only=True, allow_null=True)


class ApprovalDecisionSerializer(serializers.Serializer):
    pass

class AutoApprovalRequestSerializer(serializers.Serializer):
    id = serializers.UUIDField(read_only=True)
    approval_type = serializers.CharField(read_only=True)
    status = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)
    metadata = serializers.JSONField(read_only=True)
    requested_at = serializers.DateTimeField(read_only=True)
    decided_at = serializers.DateTimeField(read_only=True, allow_null=True)
    execution_event_id = serializers.UUIDField(read_only=True, allow_null=True)
    payment_obligation_id = serializers.UUIDField(read_only=True, allow_null=True)
    service_obligation_id = serializers.UUIDField(read_only=True, allow_null=True)


class PromoteExecutionEventSerializer(serializers.Serializer):
    summary = serializers.CharField(required=False, allow_blank=True)
    due_date = serializers.DateTimeField(required=False)


class ObligationPromotionSerializer(serializers.Serializer):
    promotion_id = serializers.UUIDField(read_only=True)
    promotion_type = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)
    source_execution_event_id = serializers.UUIDField(read_only=True)
    parent_service_obligation_id = serializers.UUIDField(
        read_only=True, allow_null=True
    )
    promoted_service_obligation_id = serializers.UUIDField(
        read_only=True, allow_null=True
    )
    created_at = serializers.DateTimeField(read_only=True)


class PromotedServiceObligationSerializer(serializers.Serializer):
    obligation_id = serializers.UUIDField(read_only=True)
    contract_id = serializers.UUIDField(read_only=True)
    description = serializers.CharField(read_only=True)
    due_date = serializers.DateTimeField(read_only=True)
    state = serializers.CharField(read_only=True)
    obligor_id = serializers.IntegerField(read_only=True)
    obligee_id = serializers.IntegerField(read_only=True)



class ValueAdjustmentCreateSerializer(serializers.Serializer):
    execution_event_id = serializers.UUIDField(required=False, allow_null=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    summary = serializers.CharField()


class ValueAdjustmentSerializer(serializers.Serializer):
    adjustment_id = serializers.UUIDField(read_only=True)
    event_id = serializers.UUIDField(read_only=True, allow_null=True)
    payment_obligation_id = serializers.UUIDField(read_only=True, allow_null=True)
    service_obligation_id = serializers.UUIDField(read_only=True, allow_null=True)
    adjustment_type = serializers.CharField(read_only=True)
    mode = serializers.CharField(read_only=True)
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    currency = serializers.CharField(read_only=True)
    summary = serializers.CharField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)

