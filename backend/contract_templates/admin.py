# backend/contract_templates/admin.py

from django.contrib import admin
from .models import (
    ContractTemplate,
    TemplateGuidedField,
    TemplateClause,
    TemplateObligationPattern,
)


class TemplateGuidedFieldInline(admin.TabularInline):
    model = TemplateGuidedField
    extra = 0
    fields = ("order", "field_key", "label", "field_type", "choices", "is_required")
    ordering = ("order",)


class TemplateClauseInline(admin.StackedInline):
    model = TemplateClause
    extra = 0
    fields = (
        "order",
        "clause_type",
        "title",
        "body",
        "is_required",
        "is_conditional",
        "condition_description",
    )
    ordering = ("order",)


class TemplateObligationPatternInline(admin.StackedInline):
    model = TemplateObligationPattern
    extra = 0
    max_num = 1
    fields = (
        "obligation_type",
        "frequency_type",
        "amount_token",
        "installments_token",
        "interval_days_token",
    )


@admin.register(ContractTemplate)
class ContractTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "subcategory", "structure_type", "tier_required", "is_active")
    list_filter = ("category", "structure_type", "tier_required", "is_active")
    search_fields = ("name", "category", "subcategory", "description")
    inlines = [TemplateGuidedFieldInline, TemplateClauseInline, TemplateObligationPatternInline]
    readonly_fields = ("id", "created_at", "updated_at")


@admin.register(TemplateGuidedField)
class TemplateGuidedFieldAdmin(admin.ModelAdmin):
    list_display = ("template", "field_key", "label", "field_type", "is_required", "order")
    list_filter = ("template", "field_type", "is_required")
    search_fields = ("field_key", "label")


@admin.register(TemplateClause)
class TemplateClauseAdmin(admin.ModelAdmin):
    list_display = ("template", "title", "clause_type", "is_required", "is_conditional", "order")
    list_filter = ("template", "clause_type", "is_required", "is_conditional")
    search_fields = ("title", "body")


@admin.register(TemplateObligationPattern)
class TemplateObligationPatternAdmin(admin.ModelAdmin):
    list_display = ("template", "obligation_type", "frequency_type", "amount_token", "installments_token")
