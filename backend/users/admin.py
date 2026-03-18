#backend/users/admin.py
from django.contrib import admin

from backend.users.models import BonUserProfile


@admin.register(BonUserProfile)
class BonUserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "bon_id", "created_at")
    search_fields = ("bon_id", "user__username", "user__email")
    readonly_fields = ("bon_id", "created_at")


