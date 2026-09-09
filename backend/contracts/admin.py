# backend/contracts/admin.py
from django.contrib import admin
from .models import Contract, ContractExtractionCandidate, ContractExtractionRun, ContractObligation, Obligation

from backend.documents.services import delete_contracts


@admin.register(Contract)
class ContractAdmin(admin.ModelAdmin):
    def delete_model(self, request, obj):
        delete_contracts([obj.pk])

    def delete_queryset(self, request, queryset):
        delete_contracts(list(queryset.values_list("pk", flat=True)))

admin.site.register(Obligation)
admin.site.register(ContractObligation)


@admin.register(ContractExtractionRun)
class ContractExtractionRunAdmin(admin.ModelAdmin):
    list_display = ("id", "contract", "stage", "source_kind", "status", "engine_name", "created_at", "completed_at")
    list_filter = ("stage", "source_kind", "status", "created_at")
    search_fields = ("contract__title", "source_hash", "engine_name", "engine_version")


@admin.register(ContractExtractionCandidate)
class ContractExtractionCandidateAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "candidate_type", "review_status", "contract", "due_date", "confidence_score", "created_at")
    list_filter = ("candidate_type", "review_status", "created_at")
    search_fields = ("title", "description", "contract__title", "source_clause_key", "source_clause_text")



