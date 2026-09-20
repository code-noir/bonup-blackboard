from rest_framework import serializers

from backend.bonup.models import ApprovedProductDirection


class ApprovedProductDirectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApprovedProductDirection
        fields = [
            "event_id", "event_digest", "agent_control_task_id", "agent_id",
            "proposal_id", "proposal_digest", "artifact_id", "artifact_digest",
            "review_id", "review_digest", "resulting_knowledge_state",
            "event_occurred_at", "title", "objective", "proposed_requirement",
            "acceptance_intent",
        ]
        read_only_fields = fields
