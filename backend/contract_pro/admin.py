# backend/contract_pro/admin.py

from django.contrib import admin

from .models import (
    ContractProAccessGrant,
    ContractProContractAssignment,
    ContractProOversightEvent,
    ContractProPermissionRule,
)


@admin.register(ContractProAccessGrant)
class ContractProAccessGrantAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "business",
        "contract_pro_user",
        "access_kind",
        "access_scope",
        "access_status",
        "granted_at",
    )
    list_filter = ("access_kind", "access_scope", "access_status")
    readonly_fields = ("id", "granted_at")


@admin.register(ContractProContractAssignment)
class ContractProContractAssignmentAdmin(admin.ModelAdmin):
    list_display = ("id", "grant", "contract", "assigned_at", "unassigned_at")
    readonly_fields = ("id", "assigned_at")


@admin.register(ContractProPermissionRule)
class ContractProPermissionRuleAdmin(admin.ModelAdmin):
    list_display = ("id", "grant", "action", "state", "contract", "set_at")
    list_filter = ("state", "action")
    readonly_fields = ("id", "set_at")


@admin.register(ContractProOversightEvent)
class ContractProOversightEventAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "business", "contract", "grant", "actor", "created_at")
    list_filter = ("event_type",)
    readonly_fields = ("id", "created_at")
