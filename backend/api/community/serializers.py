from rest_framework import serializers

from backend.community.models import Community


class CommunitySerializer(serializers.ModelSerializer):
    owner = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Community
        fields = [
            "id",
            "owner",
            "name",
            "description",
            "is_private",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner",
            "is_private",
            "created_at",
            "updated_at",
        ]


class CommunityCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Community
        fields = ["name", "description"]

    def validate_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Community name is required.")
        return value
