import re

from rest_framework import serializers

from backend.bonup.models import ProductDirectionTask


_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    re.compile(r"\b(?:sk|ghp|xox[baprs])-[A-Za-z0-9_-]{16,}\b"),
    re.compile(
        r"(?i)\b(?:password|api[_ -]?key|private[_ -]?key|client[_ -]?secret)\s*[:=]\s*\S+"
    ),
)


class ProductDirectionTaskSerializer(serializers.ModelSerializer):
    task_id = serializers.UUIDField(source="id", read_only=True)
    created_by = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ProductDirectionTask
        fields = [
            "task_id",
            "agent_control_task_id",
            "agent_id",
            "objective",
            "status",
            "proposal_artifact_id",
            "proposal_id",
            "proposal_digest",
            "runtime_failure_reason",
            "created_by",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "task_id",
            "agent_control_task_id",
            "agent_id",
            "status",
            "proposal_artifact_id",
            "proposal_id",
            "proposal_digest",
            "runtime_failure_reason",
            "created_by",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):
        supplied = set(self.initial_data or {})
        if supplied != {"objective"}:
            raise serializers.ValidationError(
                {"detail": "Only objective may be supplied for a new product-direction task."}
            )
        return attrs

    def validate_objective(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Objective is required.")
        if any(pattern.search(value) for pattern in _SECRET_PATTERNS):
            raise serializers.ValidationError("Objective cannot contain credentials or private keys.")
        return value

    def get_created_by(self, obj):
        administrator = obj.created_by
        return {
            "id": administrator.pk,
            "email": administrator.email,
            "display_name": " ".join(
                part for part in [administrator.first_name, administrator.last_name] if part
            ).strip() or administrator.email,
        }
