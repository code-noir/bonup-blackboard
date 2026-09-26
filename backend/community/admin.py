from django.contrib import admin

from backend.community.models import Community, CommunityMembership


@admin.register(Community)
class CommunityAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "is_private", "created_at", "updated_at")
    list_filter = ("is_private", "created_at")
    search_fields = ("name", "description", "owner__username", "owner__email")
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(CommunityMembership)
class CommunityMembershipAdmin(admin.ModelAdmin):
    list_display = ("community", "user", "role", "status", "joined_at", "removed_at")
    list_filter = ("role", "status", "joined_at")
    search_fields = (
        "community__name",
        "user__username",
        "user__email",
    )
    readonly_fields = ("id", "created_at", "updated_at")
