from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.conf import settings
from django.shortcuts import get_object_or_404
from django.http import Http404
from django.contrib.auth import get_user_model
from django.core.mail import get_connection, send_mail
from django.db import transaction
from django.utils import timezone

from backend.activity.log import log_activity
from backend.api.contracts.serializers import ContractVersionSerializer
from backend.ai.models import CounterDraft, NegotiationComment, ReviewResult, WorkflowShareLink, WorkflowState

User = get_user_model()

WORKFLOW_TERMINAL_STATES = {
    WorkflowState.STATE_REJECTED,
    WorkflowState.STATE_SIGNED,
}


def _frontend_url() -> str:
    return getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _display_name(user) -> str:
    if user is None:
        return ""
    full_name = getattr(user, "get_full_name", lambda: "")() or ""
    return full_name.strip() or getattr(user, "username", "") or getattr(user, "email", "") or ""


def build_invite_url(token) -> str:
    return f"{_frontend_url()}/workflow/invite/{token}"


def build_shared_workflow_url(workflow_id) -> str:
    return f"{_frontend_url()}/shared/workflows/{workflow_id}"


def get_workflow_active_version(workflow: WorkflowState):
    if workflow.created_version_id:
        return workflow.created_version
    if workflow.contract_id:
        return workflow.contract.versions.order_by("-version_number").first()
    return None


def serialize_version(version):
    if version is None:
        return None
    return ContractVersionSerializer(version).data


def serialize_review_result(review: ReviewResult | None):
    if review is None:
        return None
    conversation_id = str(review.conversation_id) if review.conversation_id else None
    return {
        "id": str(review.id),
        "conversation_id": conversation_id,
        "summary": review.summary,
        "key_terms": review.key_terms or {},
        "identified_risks": review.identified_risks or [],
        "unclear_clauses": review.unclear_clauses or [],
        "negotiation_opportunities": review.negotiation_opportunities or [],
        "suggested_changes": review.suggested_changes or [],
        "questions": review.questions or [],
        "ai_metadata": review.ai_metadata or {},
        "created_at": review.created_at,
        "updated_at": review.updated_at,
    }


def serialize_counter_draft(draft: CounterDraft):
    conversation_id = str(draft.conversation_id) if draft.conversation_id else None
    return {
        "id": str(draft.id),
        "conversation_id": conversation_id,
        "status": draft.status,
        "generated_revised_contract": draft.generated_revised_contract,
        "selected_requested_changes": draft.selected_requested_changes or [],
        "user_negotiation_instructions": draft.user_negotiation_instructions,
        "summary": draft.summary,
        "concerning_clauses": draft.concerning_clauses or [],
        "negotiation_strategy": draft.negotiation_strategy or {},
        "ai_metadata": draft.ai_metadata or {},
        "approved_at": draft.approved_at,
        "created_version_id": str(draft.created_version_id) if draft.created_version_id else None,
        "created_at": draft.created_at,
        "updated_at": draft.updated_at,
    }


def serialize_comment(comment: NegotiationComment):
    author = comment.author
    author_name = _display_name(author)
    return {
        "id": str(comment.id),
        "author_email": getattr(author, "email", "") or "",
        "author_name": author_name,
        "comment_type": comment.comment_type,
        "clause_reference": comment.clause_reference,
        "body": comment.body,
        "created_at": comment.created_at,
        "updated_at": comment.updated_at,
    }


def serialize_last_activity(workflow: WorkflowState):
    if workflow.contract_id is None:
        return None
    activity = workflow.contract.activity_log.first()
    if activity is None:
        return None
    return {
        "activity_type": activity.activity_type,
        "description": activity.description,
        "created_at": activity.created_at,
    }


def serialize_workflow(workflow: WorkflowState):
    review = None
    try:
        review = workflow.review_result
    except ReviewResult.DoesNotExist:
        review = None

    return {
        "id": str(workflow.id),
        "contract_id": str(workflow.contract_id) if workflow.contract_id else None,
        "source_label": workflow.source_label or (workflow.contract.title if workflow.contract_id else "Agreement workflow"),
        "current_state": workflow.current_state,
        "completed_states": workflow.completed_states or [],
        "pending_states": workflow.pending_states or [],
        "state_timestamps": workflow.state_timestamps or {},
        "created_version_id": str(workflow.created_version_id) if workflow.created_version_id else None,
        "sent_to_counterparty_email": workflow.sent_to_counterparty_email or "",
        "counterparty_email": workflow.counterparty_email or "",
        "counterparty_user_id": workflow.counterparty_user_id,
        "counterparty_requested_changes": workflow.counterparty_requested_changes or [],
        "last_activity": serialize_last_activity(workflow),
        "created_at": workflow.created_at,
        "updated_at": workflow.updated_at,
        "review_result": serialize_review_result(review),
        "counter_drafts": [serialize_counter_draft(draft) for draft in workflow.counter_drafts.all()],
    }


def serialize_shared_workflow(workflow: WorkflowState):
    return {
        "workflow": serialize_workflow(workflow),
        "active_version": serialize_version(get_workflow_active_version(workflow)),
    }


def serialize_invite_context(workflow: WorkflowState, share_link: WorkflowShareLink):
    return {
        "token": str(share_link.token),
        "workflow_id": str(workflow.id),
        "source_label": workflow.source_label or (workflow.contract.title if workflow.contract_id else "Agreement workflow"),
        "current_state": workflow.current_state,
        "counterparty_email": share_link.counterparty_email or workflow.counterparty_email or "",
        "initiator_name": _display_name(workflow.user),
        "active_version": serialize_version(get_workflow_active_version(workflow)),
    }


def serialize_share_link_result(workflow: WorkflowState, share_link: WorkflowShareLink, email_sent: bool):
    invite_url = build_invite_url(share_link.token)
    shared_url = build_shared_workflow_url(workflow.id)
    return {
        "workflow_id": str(workflow.id),
        "invite_url": invite_url,
        "counterparty_email": share_link.counterparty_email or workflow.counterparty_email or "",
        "shared_workflow_url": shared_url,
        "email_sent": email_sent,
        "invite_email": share_link.counterparty_email or workflow.counterparty_email or "",
        "invite_subject": f"bonUP contract invite: {workflow.source_label or 'Agreement'}",
    }


def ensure_workflow_for_contract(contract, initiator, source_label: str | None = None):
    workflow = (
        WorkflowState.objects.filter(contract=contract, user=initiator)
        .order_by("-updated_at")
        .first()
    )
    if workflow is not None:
        if source_label and not workflow.source_label:
            workflow.source_label = source_label
            workflow.save(update_fields=["source_label", "updated_at"])
        return workflow, False

    workflow = WorkflowState.objects.create(
        user=initiator,
        contract=contract,
        source_label=source_label or contract.title or "Prepared contract",
    )
    workflow.initialize()
    workflow.completed_states = [WorkflowState.STATE_UPLOADED, WorkflowState.STATE_VERSION_CREATED]
    workflow.pending_states = [
        WorkflowState.STATE_SENT_TO_COUNTERPARTY,
        WorkflowState.STATE_COUNTERPARTY_VIEWED,
        WorkflowState.STATE_COUNTERPARTY_REQUESTED_CHANGES,
        WorkflowState.STATE_ACCEPTED,
        WorkflowState.STATE_REJECTED,
        WorkflowState.STATE_SIGNED,
    ]
    workflow.current_state = WorkflowState.STATE_VERSION_CREATED
    workflow.state_timestamps = {
        WorkflowState.STATE_UPLOADED: timezone.now().isoformat(),
        WorkflowState.STATE_VERSION_CREATED: timezone.now().isoformat(),
    }
    workflow.save(update_fields=["source_label", "completed_states", "pending_states", "current_state", "state_timestamps", "updated_at"])
    return workflow, True


def prime_workflow_for_invite(workflow: WorkflowState, counterparty_email: str | None = None):
    workflow.sent_to_counterparty_email = counterparty_email or workflow.counterparty_email or ""
    workflow.counterparty_email = workflow.sent_to_counterparty_email
    workflow.current_state = WorkflowState.STATE_SENT_TO_COUNTERPARTY
    workflow.completed_states = [
        WorkflowState.STATE_UPLOADED,
        WorkflowState.STATE_VERSION_CREATED,
        WorkflowState.STATE_SENT_TO_COUNTERPARTY,
    ]
    workflow.pending_states = [
        WorkflowState.STATE_COUNTERPARTY_VIEWED,
        WorkflowState.STATE_COUNTERPARTY_REQUESTED_CHANGES,
        WorkflowState.STATE_ACCEPTED,
        WorkflowState.STATE_REJECTED,
        WorkflowState.STATE_SIGNED,
    ]
    workflow.state_timestamps = dict(workflow.state_timestamps or {})
    workflow.state_timestamps[WorkflowState.STATE_SENT_TO_COUNTERPARTY] = timezone.now().isoformat()
    return workflow


def create_share_link_and_send_email(*, workflow: WorkflowState, counterparty_email: str, created_by, subject_prefix: str = "bonUP contract invite"):
    share_link = WorkflowShareLink.objects.create(
        workflow=workflow,
        counterparty_email=counterparty_email,
        expires_at=WorkflowShareLink.default_expires_at(),
        created_by=created_by,
    )
    invite_url = build_invite_url(share_link.token)
    shared_url = build_shared_workflow_url(workflow.id)
    subject = f"{subject_prefix}: {workflow.source_label or 'Agreement'}"
    body = (
        f"Hello,\n\n"
        f"You have been invited to review an agreement on bonUP.\n\n"
        f"Agreement: {workflow.source_label or 'Agreement'}\n"
        f"Open the invite link below to continue:\n\n"
        f"{invite_url}\n\n"
        f"Shared workspace: {shared_url}\n\n"
        f"If you were not expecting this email, you can ignore it.\n\n"
        f"— The bonUP team"
    )
    connection = None
    if getattr(settings, "RESEND_API_KEY", ""):
        connection = get_connection("backend.core.email_backends.ResendEmailBackend")

    sent_count = send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[counterparty_email],
        fail_silently=False,
        connection=connection,
    )
    email_sent = sent_count > 0
    if not email_sent:
        raise RuntimeError("Invite email could not be sent.")
    return share_link, serialize_share_link_result(workflow, share_link, email_sent=email_sent)


def upsert_review_result(*, workflow: WorkflowState, conversation, parsed: dict, ai_metadata: dict | None = None):
    review, _created = ReviewResult.objects.get_or_create(workflow=workflow)
    review.conversation = conversation
    review.summary = parsed.get("summary", "")
    review.key_terms = parsed.get("key_terms", {})
    review.identified_risks = parsed.get("red_flags", parsed.get("identified_risks", []))
    review.unclear_clauses = parsed.get("unclear_clauses", [])
    review.negotiation_opportunities = parsed.get("negotiation_opportunities", [])
    review.suggested_changes = parsed.get("suggested_changes", [])
    review.questions = parsed.get("questions", [])
    if ai_metadata is not None:
        review.ai_metadata = ai_metadata
    review.save()
    return review


def upsert_counter_draft(*, workflow: WorkflowState, conversation, parsed: dict, selected_requested_changes: list[str], user_negotiation_instructions: str = ""):
    draft, _created = CounterDraft.objects.get_or_create(workflow=workflow)
    draft.conversation = conversation
    draft.generated_revised_contract = parsed.get("revised_contract", "")
    draft.selected_requested_changes = selected_requested_changes or []
    draft.user_negotiation_instructions = user_negotiation_instructions or ""
    draft.summary = parsed.get("summary", "")
    draft.concerning_clauses = parsed.get("concerning_clauses", [])
    draft.negotiation_strategy = parsed.get("negotiation_strategy", {})
    draft.ai_metadata = parsed.get("ai_metadata", {}) if isinstance(parsed.get("ai_metadata"), dict) else {}
    draft.status = CounterDraft.STATUS_DRAFT
    draft.save()
    return draft


def approve_counter_draft(*, draft: CounterDraft, actor):
    workflow = draft.workflow
    contract = workflow.contract
    if contract is None:
        raise ValueError("Counter draft is not linked to a contract.")

    existing_count = contract.versions.count()
    if existing_count >= contract.max_versions:
        raise ValueError(f"Maximum version limit reached ({contract.max_versions}).")

    previous = contract.versions.order_by("-version_number").first()
    if previous and previous.status not in {"signed", "rejected", "archived"}:
        previous.superseded = True
        previous.status = "superseded"
        previous.save(update_fields=["superseded", "status"])

    new_version = contract.versions.create(
        version_number=existing_count + 1,
        created_by=actor,
        previous_version=previous,
        content_snapshot=draft.generated_revised_contract,
        status="draft",
    )
    draft.status = CounterDraft.STATUS_APPROVED
    draft.created_version = new_version
    draft.approved_at = timezone.now()
    draft.save(update_fields=["status", "created_version", "approved_at", "updated_at"])

    workflow.created_version = new_version
    workflow.current_state = WorkflowState.STATE_VERSION_CREATED
    workflow.completed_states = [WorkflowState.STATE_UPLOADED, WorkflowState.STATE_VERSION_CREATED]
    workflow.pending_states = [WorkflowState.STATE_SENT_TO_COUNTERPARTY, WorkflowState.STATE_COUNTERPARTY_VIEWED, WorkflowState.STATE_COUNTERPARTY_REQUESTED_CHANGES, WorkflowState.STATE_ACCEPTED, WorkflowState.STATE_REJECTED, WorkflowState.STATE_SIGNED]
    workflow.state_timestamps = dict(workflow.state_timestamps or {})
    workflow.state_timestamps[WorkflowState.STATE_VERSION_CREATED] = timezone.now().isoformat()
    workflow.save(update_fields=["created_version", "current_state", "completed_states", "pending_states", "state_timestamps", "updated_at"])

    return new_version


def get_workflow_for_user(user, workflow_id):
    return get_object_or_404(
        WorkflowState.objects.select_related("contract", "created_version", "counterparty_user", "user"),
        pk=workflow_id,
        user=user,
    )


def get_counterparty_workflow(workflow_id, user):
    workflow = get_object_or_404(
        WorkflowState.objects.select_related("contract", "created_version", "counterparty_user", "user"),
        pk=workflow_id,
    )
    if not is_counterparty_access_allowed(workflow, user):
        raise Http404
    return workflow


def is_counterparty_access_allowed(workflow: WorkflowState, user) -> bool:
    if user is None:
        return False
    if workflow.counterparty_user_id and workflow.counterparty_user_id == user.pk:
        return True
    if workflow.counterparty_email and workflow.counterparty_email.lower() == (user.email or "").lower():
        return True
    if workflow.sent_to_counterparty_email and workflow.sent_to_counterparty_email.lower() == (user.email or "").lower():
        return True
    if workflow.contract_id and workflow.contract.counterparty_email.lower() == (user.email or "").lower():
        return True
    return False


def get_share_link(token):
    return get_object_or_404(
        WorkflowShareLink.objects.select_related("workflow", "workflow__contract", "created_by", "workflow__user", "workflow__created_version"),
        token=token,
    )


def get_active_version_for_share_link(share_link: WorkflowShareLink):
    return get_workflow_active_version(share_link.workflow)


def log_workflow_contract_update(workflow: WorkflowState, user, description: str, metadata: dict[str, Any]):
    if workflow.contract_id is None:
        return
    log_activity(
        contract=workflow.contract,
        user=user,
        activity_type="contract_updated",
        description=description,
        metadata=metadata,
    )
