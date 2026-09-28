from rest_framework import serializers

from backend.community.models import Community, CommunityJoinRequest


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
            "is_discoverable",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "owner",
            "is_private",
            "is_discoverable",
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


class CommunityJoinRequestSerializer(serializers.ModelSerializer):
    community_name = serializers.CharField(source="community.name", read_only=True)
    requester_name = serializers.SerializerMethodField()
    reviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = CommunityJoinRequest
        fields = [
            "id",
            "community",
            "community_name",
            "user",
            "requester_name",
            "status",
            "reviewer_name",
            "created_at",
            "reviewed_at",
        ]

    def get_requester_name(self, obj):
        return " ".join(filter(None, [obj.user.first_name, obj.user.last_name])) or obj.user.username

    def get_reviewer_name(self, obj):
        if not obj.reviewed_by:
            return None
        return " ".join(filter(None, [obj.reviewed_by.first_name, obj.reviewed_by.last_name])) or obj.reviewed_by.username
