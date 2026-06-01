"""Canonical Blackboard contract schema helpers.

This module defines the stable in-memory shape used by the snapshot adapter.
It intentionally does not depend on Django models so it can be used from tests,
services, and future API layers without changing runtime behavior today.
"""

SCHEMA_VERSION = "blackboard_contract_schema.v1"

SOURCE_TYPE_EDITOR_HTML = "editor_html"
SOURCE_TYPE_FINAL_EDITOR_HTML = "final_editor_html"
SOURCE_TYPE_TEMPLATE_CLAUSES = "template_clauses"
SOURCE_TYPE_PREPARED_TERMS = "prepared_terms"
SOURCE_TYPE_SECTIONS = "sections"
SOURCE_TYPE_RAW_CONTENT = "raw_content"
SOURCE_TYPE_LEGACY_TEXT = "legacy_text"


def empty_contract_identity():
    return {
        "title": "",
        "contract_type": "",
        "description": "",
        "structure_type": "",
        "start_date": None,
        "end_date": None,
        "currency": "",
        "jurisdiction": "",
        "governing_law": "",
        "source_type": "",
    }


def empty_extraction_report():
    return {
        "adapter": "snapshot_adapter",
        "adapter_version": SCHEMA_VERSION,
        "source_types": [],
        "warnings": [],
        "normalization_actions": [],
        "ignored_content": [],
    }


def empty_lifecycle_terms():
    return {
        "activation_criteria": [],
        "signature_requirements": [],
        "post_signature_obligations": [],
        "change_order_policy": None,
    }


def empty_render_cache():
    return {
        "editor_html": "",
        "final_editor_html": "",
        "raw_content": "",
        "plain_text": "",
        "sections": [],
        "prepared_terms": {},
    }


def empty_schema():
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_identity": empty_contract_identity(),
        "participants": [],
        "clauses": [],
        "payment_obligations": [],
        "service_obligations": [],
        "termination_terms": None,
        "dispute_terms": None,
        "resolution_terms": None,
        "notices": None,
        "governing_law": None,
        "lifecycle_terms": empty_lifecycle_terms(),
        "missing_unresolved_fields": [],
        "extraction_report": empty_extraction_report(),
        "source_provenance": [],
        "render_cache": empty_render_cache(),
    }


def make_missing_field(field_path, reason, severity="warning", source_context=""):
    return {
        "field_path": field_path,
        "reason": reason,
        "severity": severity,
        "source_context": source_context,
    }


def make_source_provenance(
    source_type,
    source_field="",
    clause_id=None,
    extraction_method="snapshot_adapter",
    raw_excerpt="",
):
    return {
        "source_type": source_type,
        "source_field": source_field,
        "clause_id": clause_id,
        "extraction_method": extraction_method,
        "raw_excerpt": raw_excerpt,
    }
