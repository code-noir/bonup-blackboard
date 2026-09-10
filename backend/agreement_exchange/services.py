import json
import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from backend.agreement_exchange.change_applicator import apply_request_to_snapshot
from backend.agreement_exchange.models import (
    AgreementExchange,
    AgreementExchangeEvent,
    AgreementExchangeRequest,
    AgreementExchangeSignature,
)
from backend.agreement_exchange.notifications import find_user_by_email, notify_exchange_recipient
from backend.ai.models import WorkflowState
from backend.api.contracts.services.visibility_service import can_user_see_exchange
from backend.contracts.models import Contract, ContractVersion
from backend.contracts.section_normalizer import normalize_contract_sections

User = get_user_model()
logger = logging.getLogger(__name__)


class AgreementExchangeResolveError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def extract_snapshot(version):
    raw = getattr(version, "content_snapshot", version) or ""
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {"content_html": raw, "sections": []}
    return parsed if isinstance(parsed, dict) else {"content_html": raw, "sections": []}


def extract_contract_sections(content_snapshot):
    return normalize_contract_sections(content_snapshot)


def _snapshot_full_html(snapshot):
    for key in ("editor_html", "final_editor_html", "content_html", "html", "body", "text"):
        value = snapshot.get(key)
        if isinstance(value, str) and value.strip():
            return value
    sections = snapshot.get("sections")
    if isinstance(sections, list):
        section_html = "".join(
            str(section.get("content_html") or section.get("html") or section.get("body") or section.get("text") or "")
            for section in sections
            if isinstance(section, dict)
        ).strip()
        if section_html:
            return section_html
    clauses = snapshot.get("clauses")
    if isinstance(clauses, list):
        clause_text = "\n\n".join(
            str(clause.get("body") or "")
            for clause in clauses
            if isinstance(clause, dict) and str(clause.get("body") or "").strip()
        ).strip()
        if clause_text:
            return clause_text
    return ""


def _snapshot_has_full_content(snapshot):
    return bool(_snapshot_full_html(snapshot).strip())


def _staged_snapshot_is_ready(snapshot):
    latest_update = snapshot.get("agreement_exchange_latest_update")
    return _snapshot_has_full_content(snapshot) and isinstance(latest_update, dict) and bool(latest_update.get("request_id"))


def _require_staged_snapshot_ready(snapshot):
    if not _snapshot_has_full_content(snapshot):
        raise ValueError("The current contract version has no full contract content to stage.")
    latest_update = snapshot.get("agreement_exchange_latest_update")
    if not isinstance(latest_update, dict) or not latest_update.get("request_id"):
        raise ValueError("The staged version is missing request context.")


def _update_draft_staged_version_snapshot(staged_version, snapshot):
    if staged_version.status != "draft":
        raise ValueError("Only draft staged versions can be edited.")
    content_snapshot = json.dumps(snapshot) if isinstance(snapshot, dict) else snapshot
    updated = ContractVersion.objects.filter(pk=staged_version.pk, status="draft").update(content_snapshot=content_snapshot)
    if not updated:
        raise ValueError("The staged version could not be updated.")
    staged_version.content_snapshot = content_snapshot
    return staged_version


def _resolved_full_snapshot_for_staging(exchange):
    candidates = []
    current = exchange.current_contract_version
    seen = set()
    while current and current.id not in seen:
        seen.add(current.id)
        candidates.append(current)
        current = current.previous_version
    if exchange.source_contract_version_id and exchange.source_contract_version_id not in seen:
        candidates.append(exchange.source_contract_version)

    fallback = extract_snapshot(exchange.current_contract_version)
    for version in candidates:
        snapshot = extract_snapshot(version)
        if _snapshot_has_full_content(snapshot):
            if not str(snapshot.get("editor_html") or "").strip():
                snapshot["editor_html"] = _snapshot_full_html(snapshot)
            snapshot.setdefault("sections", [])
            return snapshot
    return fallback


def _reviewed_update_snapshot(base_snapshot, change_request, *, decision, final_text, initiator_response):
    reviewed_text = final_text or change_request.proposed_text
    snapshot = apply_request_to_snapshot(base_snapshot, change_request, accepted_text=reviewed_text)
    latest_update = snapshot.get("agreement_exchange_latest_update")
    if isinstance(latest_update, dict):
        latest_update["decision"] = decision
        latest_update["initiator_response"] = initiator_response or ""
    updates = snapshot.get("agreement_exchange_updates")
    if isinstance(updates, list) and updates:
        updates[-1] = latest_update
    return json.dumps(snapshot)


def _manual_edit_snapshot(base_snapshot, change_request, *, decision, initiator_response):
    snapshot = extract_snapshot(base_snapshot)
    if not str(snapshot.get("editor_html") or "").strip():
        full_html = _snapshot_full_html(snapshot)
        if full_html:
            snapshot["editor_html"] = full_html
    metadata = {
        "source": "agreement_exchange",
        "request_id": str(change_request.id),
        "target_section_id": change_request.target_section_id,
        "target_section_title": change_request.target_section_title,
        "request_category": change_request.request_category,
        "action_type": change_request.action_type,
        "proposed_text": change_request.proposed_text,
        "matched_by": None,
        "fallback_used": False,
        "application_status": "manual_edit_required",
        "decision": decision,
        "initiator_response": initiator_response or "",
    }
    updates = snapshot.get("agreement_exchange_updates")
    if not isinstance(updates, list):
        updates = []
    snapshot["agreement_exchange_updates"] = [*updates, metadata]
    snapshot["agreement_exchange_latest_update"] = metadata
    return json.dumps(snapshot)


def exchange_local_version_number(exchange, version=None):
    current = version or exchange.current_contract_version
    source_id = exchange.source_contract_version_id or exchange.current_contract_version_id
    number = 1
    seen = set()
    while current and current.id != source_id and current.previous_version_id and current.id not in seen:
        seen.add(current.id)
        number += 1
        current = current.previous_version
    return number


def next_contract_version_number(contract):
    latest = contract.versions.order_by("-version_number").first()
    return (latest.version_number if latest else 0) + 1


def _version_update_metadata(version):
    snapshot = extract_snapshot(version)
    latest_update = snapshot.get("agreement_exchange_latest_update")
    return latest_update if isinstance(latest_update, dict) else {}


def _staged_update_version(exchange, change_request):
    version = exchange.staged_contract_version
    if version is None:
        return None
    if version.contract_id != exchange.contract_id or version.previous_version_id != exchange.current_contract_version_id:
        return None
    metadata = _version_update_metadata(version)
    if metadata.get("request_id") == str(change_request.id) and metadata.get("staged_for_agreement_exchange"):
        return version
    return None


def _build_staged_snapshot(exchange, change_request, *, decision, final_text, initiator_response):
    base_snapshot = _resolved_full_snapshot_for_staging(exchange)
    if decision == "edit":
        content_snapshot = _manual_edit_snapshot(
            base_snapshot,
            change_request,
            decision=decision,
            initiator_response=initiator_response,
        )
    else:
        content_snapshot = _reviewed_update_snapshot(
            base_snapshot,
            change_request,
            decision=decision,
            final_text=final_text,
            initiator_response=initiator_response,
        )
    snapshot = extract_snapshot(content_snapshot)
    latest_update = snapshot.get("agreement_exchange_latest_update")
    if isinstance(latest_update, dict):
        latest_update["staged_for_agreement_exchange"] = True
        latest_update["sent_to_counterparty"] = False
    updates = snapshot.get("agreement_exchange_updates")
    if isinstance(updates, list) and updates and isinstance(latest_update, dict):
        updates[-1] = latest_update
    _require_staged_snapshot_ready(snapshot)
    return snapshot


def _replace_staged_version_snapshot(exchange, staged_version, change_request, *, decision, final_text, initiator_response):
    if staged_version.status != "draft":
        raise ValueError("Only draft staged versions can be rebuilt.")
    snapshot = _build_staged_snapshot(
        exchange,
        change_request,
        decision=decision,
        final_text=final_text,
        initiator_response=initiator_response,
    )
    return _update_draft_staged_version_snapshot(staged_version, snapshot)


def _create_staged_exchange_version_from_request(exchange, change_request, *, decision, final_text, initiator_response, actor):
    existing = _staged_update_version(exchange, change_request)
    if existing is not None:
        if _staged_snapshot_is_ready(extract_snapshot(existing)):
            return existing
        return _replace_staged_version_snapshot(
            exchange,
            existing,
            change_request,
            decision=decision,
            final_text=final_text,
            initiator_response=initiator_response,
        )

    contract = exchange.contract
    existing_count = exchange_local_version_number(exchange)
    if existing_count >= contract.max_versions:
        raise ValueError(f"Maximum version limit reached ({contract.max_versions}).")

    previous = exchange.current_contract_version
    snapshot = _build_staged_snapshot(
        exchange,
        change_request,
        decision=decision,
        final_text=final_text,
        initiator_response=initiator_response,
    )

    return ContractVersion.objects.create(
        contract=contract,
        version_number=next_contract_version_number(contract),
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        previous_version=previous,
        content_snapshot=json.dumps(snapshot),
        status="draft",
    )


def _finalize_staged_exchange_version(exchange, staged_version, *, full_content_html=""):
    previous = staged_version.previous_version
    if previous is None or previous.contract_id != exchange.contract_id:
        raise ValueError("The staged version is not linked to this contract.")
    if exchange.current_contract_version_id != previous.id:
        raise ValueError("The staged version is no longer based on the current exchange version.")

    if full_content_html:
        snapshot = extract_snapshot(staged_version)
        snapshot["editor_html"] = full_content_html
        latest_update = snapshot.get("agreement_exchange_latest_update")
        if isinstance(latest_update, dict):
            latest_update["manual_full_contract_review"] = True
            latest_update["sent_to_counterparty"] = True
        updates = snapshot.get("agreement_exchange_updates")
        if isinstance(updates, list) and updates and isinstance(latest_update, dict):
            updates[-1] = latest_update
        _update_draft_staged_version_snapshot(staged_version, snapshot)

    if previous.status not in {"signed", "rejected", "archived", "superseded"}:
        previous.superseded = True
        previous.status = "superseded"
        previous.save(update_fields=["superseded", "status"])

    staged_version.status = "sent"
    staged_version.save(update_fields=["status"])
    WorkflowState.objects.filter(
        contract=exchange.contract,
        created_version=previous,
    ).filter(
        Q(counterparty_email__iexact=exchange.counterparty_email)
        | Q(sent_to_counterparty_email__iexact=exchange.counterparty_email)
    ).update(created_version=staged_version)
    return staged_version


def _create_exchange_version_from_request(exchange, change_request, *, decision, final_text, initiator_response, actor):
    staged = _create_staged_exchange_version_from_request(
        exchange,
        change_request,
        decision=decision,
        final_text=final_text,
        initiator_response=initiator_response,
        actor=actor,
    )
    return _finalize_staged_exchange_version(exchange, staged)

def current_contract_payload(exchange):
    version = exchange.current_contract_version
    snapshot = extract_snapshot(version)
    sections = extract_contract_sections(snapshot)
    content_html = (
        snapshot.get("editor_html")
        or snapshot.get("final_editor_html")
        or snapshot.get("content_html")
        or snapshot.get("html")
        or version.content_snapshot
        or ""
    )
    local_number = exchange_local_version_number(exchange, version)
    return {
        "id": str(version.id),
        "contract_id": str(exchange.contract_id),
        "title": exchange.contract.title or "Untitled agreement",
        "version_label": f"v{local_number}",
        "version_number": local_number,
        "source_version_number": version.version_number,
        "status": version.status,
        "content_html": content_html,
        "sections": sections,
    }


def normalize_email(value):
    return (value or "").strip().lower()


def viewer_role(exchange, user):
    if not user or not getattr(user, "is_authenticated", False):
        return "unknown"
    if exchange.initiator_id == user.id:
        return "initiator"
    user_email = normalize_email(getattr(user, "email", ""))
    counterparty_email = normalize_email(exchange.counterparty_email)
    if exchange.counterparty_user_id == user.id or (user_email and user_email == counterparty_email):
        return "counterparty"
    return "unknown"


def bind_counterparty_user_for_viewer(exchange, user, role):
    if role != "counterparty" or exchange.counterparty_user_id:
        return
    if normalize_email(getattr(user, "email", "")) != normalize_email(exchange.counterparty_email):
        return
    exchange.counterparty_user = user
    exchange.save(update_fields=["counterparty_user", "updated_at"])


def exchange_redirect_url(exchange):
    return f"/agreement-exchange/{exchange.id}"


def exchange_notification_metadata(exchange, *, action_type, source_event, extra=None):
    metadata = {
        "exchange_id": str(exchange.id),
        "contract_id": str(exchange.contract_id),
        "contract_version_id": str(exchange.current_contract_version_id),
        "redirect_url": exchange_redirect_url(exchange),
        "action_type": action_type,
        "version_label": f"v{exchange_local_version_number(exchange)}",
        "source_event": source_event,
    }
    if extra:
        metadata.update(extra)
    return metadata


def has_pending_request(exchange):
    return exchange.requests.filter(status=AgreementExchangeRequest.STATUS_PENDING).exists()


def has_staged_update(exchange):
    return bool(
        exchange.staged_contract_version_id
        and exchange.current_actor == AgreementExchange.ACTOR_INITIATOR
        and exchange.status not in {AgreementExchange.STATUS_SIGNED, AgreementExchange.STATUS_REJECTED}
    )


def screen_state(exchange, role):
    if exchange.status == AgreementExchange.STATUS_DRAFT:
        return "initiator_send_initial_version" if role == "initiator" else "counterparty_not_sent"
    if exchange.status == AgreementExchange.STATUS_SIGNED:
        return "signed"
    if exchange.status == AgreementExchange.STATUS_REJECTED:
        return "rejected"
    if has_staged_update(exchange):
        return "initiator_editing" if role == "initiator" else "counterparty_waiting"
    if exchange.status == AgreementExchange.STATUS_INITIATOR_REVIEW:
        return "initiator_review_requested_change" if role == "initiator" else "counterparty_waiting"
    if exchange.status == AgreementExchange.STATUS_INITIATOR_EDITING:
        return "initiator_editing" if role == "initiator" else "counterparty_waiting"
    if exchange.status == AgreementExchange.STATUS_UPDATED_VERSION_SENT:
        return "counterparty_review_updated_version" if role == "counterparty" else "initiator_waiting"
    if exchange.status == AgreementExchange.STATUS_READY_TO_SIGN:
        return "ready_to_sign"
    if exchange.current_actor == AgreementExchange.ACTOR_INITIATOR:
        return "initiator_waiting" if role != "initiator" else "initiator_review_requested_change"
    if exchange.current_actor == AgreementExchange.ACTOR_COUNTERPARTY:
        return "counterparty_review" if role == "counterparty" else "initiator_waiting"
    return "counterparty_waiting"


def available_actions(exchange, role):
    if exchange.status in {AgreementExchange.STATUS_SIGNED, AgreementExchange.STATUS_REJECTED}:
        return []
    if exchange.status == AgreementExchange.STATUS_DRAFT:
        return ["send_initial_version"] if role == "initiator" and exchange.current_actor == AgreementExchange.ACTOR_INITIATOR else []
    if role == "counterparty" and exchange.current_actor == AgreementExchange.ACTOR_COUNTERPARTY:
        return ["sign", "request_change", "reject"]
    if role == "initiator" and has_staged_update(exchange):
        return ["save_staged_version", "send_updated_version", "reject"]
    if (
        role == "initiator"
        and exchange.current_actor == AgreementExchange.ACTOR_INITIATOR
        and exchange.status == AgreementExchange.STATUS_INITIATOR_REVIEW
        and has_pending_request(exchange)
    ):
        return ["apply_change", "edit_updated_version", "reject"]
    return []



def staged_update_payload(exchange, user):
    if viewer_role(exchange, user) != "initiator":
        return None
    version = exchange.staged_contract_version
    if version is None:
        return None
    pending = exchange.requests.filter(status__in=[
        AgreementExchangeRequest.STATUS_ACCEPTED,
        AgreementExchangeRequest.STATUS_EDITED,
        AgreementExchangeRequest.STATUS_PENDING,
    ]).order_by("-updated_at", "-created_at").first()
    if pending is None:
        return None
    snapshot = extract_snapshot(version)
    sections = extract_contract_sections(snapshot)
    content_html = (
        snapshot.get("editor_html")
        or snapshot.get("final_editor_html")
        or snapshot.get("content_html")
        or snapshot.get("html")
        or version.content_snapshot
    )
    return {
        "id": str(version.id),
        "contract_id": str(version.contract_id),
        "request_id": str(pending.id),
        "title": version.contract.title or "Untitled contract",
        "version_label": f"v{exchange_local_version_number(exchange, version)}",
        "version_number": version.version_number,
        "status": version.status,
        "content_html": content_html,
        "sections": sections,
    }


def _repair_staged_update_for_initiator_detail(exchange, user, role):
    if role != "initiator" or not has_staged_update(exchange):
        return exchange
    staged_version = exchange.staged_contract_version
    if staged_version is None or staged_version.status != "draft":
        return exchange
    if _staged_snapshot_is_ready(extract_snapshot(staged_version)):
        return exchange

    try:
        with transaction.atomic():
            locked_exchange = load_exchange(exchange.id, for_update=True)
            if not has_staged_update(locked_exchange):
                return exchange
            locked_staged_version = locked_exchange.staged_contract_version
            if locked_staged_version is None or locked_staged_version.status != "draft":
                return exchange
            if _staged_snapshot_is_ready(extract_snapshot(locked_staged_version)):
                return locked_exchange

            change_request = _request_for_staged_version(locked_exchange, locked_staged_version)
            if change_request is None:
                return locked_exchange

            decision = "edit" if change_request.status in {
                AgreementExchangeRequest.STATUS_EDITED,
                AgreementExchangeRequest.STATUS_PENDING,
            } else "accept"
            final_text = change_request.pending_next_version_text or change_request.proposed_text
            _replace_staged_version_snapshot(
                locked_exchange,
                locked_staged_version,
                change_request,
                decision=decision,
                final_text=final_text,
                initiator_response=change_request.initiator_response or "",
            )
            return load_exchange(locked_exchange.id)
    except Exception:
        logger.error("Agreement Exchange staged update auto-repair failed", extra={"exchange_id": str(exchange.id)})
        return exchange


def serialize_user(user):
    if not user:
        return None
    return {"id": str(user.id), "email": user.email, "name": " ".join(part for part in [user.first_name, user.last_name] if part).strip()}


def serialize_request(change_request):
    return {
        "id": str(change_request.id),
        "exchange": str(change_request.exchange_id),
        "requested_by_user": str(change_request.requested_by_user_id) if change_request.requested_by_user_id else None,
        "requested_by_email": change_request.requested_by_email,
        "target_section_id": change_request.target_section_id,
        "target_section_title": change_request.target_section_title,
        "request_category": change_request.request_category,
        "action_type": change_request.action_type,
        "template_key": change_request.template_key,
        "proposed_text": change_request.proposed_text,
        "reason": change_request.reason,
        "status": change_request.status,
        "initiator_response": change_request.initiator_response,
        "pending_next_version_text": change_request.pending_next_version_text,
        "created_at": change_request.created_at,
        "updated_at": change_request.updated_at,
    }


def serialize_event(event):
    return {
        "id": str(event.id),
        "actor": {"user_id": str(event.actor_user_id), "email": event.actor_user.email} if event.actor_user_id else {"email": event.actor_email},
        "actor_role": event.actor_role,
        "event_type": event.event_type,
        "message": event.message,
        "metadata": event.metadata,
        "created_at": event.created_at,
    }


def serialize_signature(signature):
    return {
        "id": str(signature.id),
        "signer_user": str(signature.signer_user_id) if signature.signer_user_id else None,
        "signer_email": signature.signer_email,
        "signer_role": signature.signer_role,
        "signed_version": str(signature.signed_version_id),
        "typed_name": signature.typed_name,
        "signature_text": signature.signature_text,
        "signed_at": signature.signed_at,
    }


def exchange_summary(exchange):
    return {
        "id": str(exchange.id),
        "contract_id": str(exchange.contract_id),
        "current_contract_version_id": str(exchange.current_contract_version_id),
        "staged_contract_version_id": str(exchange.staged_contract_version_id) if exchange.staged_contract_version_id else None,
        "source_contract_version_id": str(exchange.source_contract_version_id) if exchange.source_contract_version_id else None,
        "restarted_from_exchange_id": str(exchange.restarted_from_exchange_id) if exchange.restarted_from_exchange_id else None,
        "initiator": serialize_user(exchange.initiator),
        "counterparty_email": exchange.counterparty_email,
        "counterparty_user": serialize_user(exchange.counterparty_user),
        "status": exchange.status,
        "current_actor": exchange.current_actor,
        "created_at": exchange.created_at,
        "updated_at": exchange.updated_at,
    }


def exchange_detail(exchange, user):
    role = viewer_role(exchange, user)
    bind_counterparty_user_for_viewer(exchange, user, role)
    exchange = _repair_staged_update_for_initiator_detail(exchange, user, role)
    return {
        "exchange": exchange_summary(exchange),
        "viewer_role": role,
        "screen_state": screen_state(exchange, role),
        "current_contract": current_contract_payload(exchange),
        "staged_update": staged_update_payload(exchange, user),
        "requests": [serialize_request(item) for item in exchange.requests.all()],
        "events": [serialize_event(item) for item in exchange.events.all()],
        "signatures": [serialize_signature(item) for item in exchange.signatures.all()],
        "available_actions": available_actions(exchange, role),
    }


def _display_name(user=None, email="", fallback="Someone"):
    if user is not None:
        name = " ".join(part for part in [getattr(user, "first_name", ""), getattr(user, "last_name", "")] if part).strip()
        if name:
            return name
        if getattr(user, "email", ""):
            return user.email
    return email or fallback


def _contract_title(exchange):
    return exchange.contract.title or f"Contract {str(exchange.contract_id)[-8:]}"


def _exchange_notification_message(exchange, *, actor_label, action_text, actor_prefix="From"):
    return "\n".join([
        f"Contract: {_contract_title(exchange)}",
        f"{actor_prefix}: {actor_label}",
        f"Action: {action_text}",
    ])


def _notification_metadata(exchange, *, action_type, source_event, actor_label, action_text, extra=None):
    metadata = exchange_notification_metadata(exchange, action_type=action_type, source_event=source_event, extra=extra)
    metadata["contract_title"] = _contract_title(exchange)
    metadata["actor_label"] = actor_label
    metadata["action_text"] = action_text
    return metadata


def create_event(exchange, *, actor_user=None, actor_email="", actor_role="system", event_type, message, metadata=None):
    return AgreementExchangeEvent.objects.create(
        exchange=exchange,
        actor_user=actor_user,
        actor_email=actor_email or None,
        actor_role=actor_role,
        event_type=event_type,
        message=message,
        metadata=metadata or {},
    )


def notify_initiator(exchange, message, metadata=None, title=""):
    return notify_exchange_recipient(
        user=exchange.initiator,
        notification_type="agreement_exchange",
        title=title,
        message=message,
        contract=exchange.contract,
        metadata=metadata or {},
    )


def notify_counterparty(exchange, message, metadata=None, title=""):
    recipient = exchange.counterparty_user or find_user_by_email(exchange.counterparty_email)
    return notify_exchange_recipient(
        user=recipient,
        email=exchange.counterparty_email,
        notification_type="agreement_exchange",
        title=title,
        message=message,
        contract=exchange.contract,
        metadata=metadata or {},
    )


def load_exchange(exchange_id, for_update=False):
    queryset = AgreementExchange.objects.select_related("contract", "current_contract_version", "staged_contract_version", "source_contract_version", "restarted_from_exchange", "initiator", "counterparty_user").prefetch_related("requests", "events", "signatures")
    if for_update:
        queryset = queryset.select_for_update(of=("self",))
    return get_object_or_404(queryset, pk=exchange_id)


def workflow_access_allowed(workflow, user):
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if workflow.user_id == user.id:
        return True
    user_email = (getattr(user, "email", "") or "").lower()
    return (
        workflow.counterparty_user_id == user.id
        or bool(user_email and user_email == (workflow.counterparty_email or "").lower())
        or bool(user_email and user_email == (workflow.sent_to_counterparty_email or "").lower())
    )


def get_workflow_contract_version(workflow):
    if workflow.created_version_id:
        return workflow.created_version
    if workflow.contract_id:
        return workflow.contract.versions.order_by("-version_number", "-created_at").first()
    return None


ACTIVE_PENDING_STATUSES = {
    AgreementExchange.STATUS_SENT,
    AgreementExchange.STATUS_VIEWED,
    AgreementExchange.STATUS_COUNTERPARTY_REVIEW,
    AgreementExchange.STATUS_CHANGES_REQUESTED,
    AgreementExchange.STATUS_INITIATOR_REVIEW,
    AgreementExchange.STATUS_INITIATOR_EDITING,
    AgreementExchange.STATUS_UPDATED_VERSION_SENT,
    AgreementExchange.STATUS_READY_TO_SIGN,
}

TERMINAL_STATUSES = {
    AgreementExchange.STATUS_SIGNED,
    AgreementExchange.STATUS_REJECTED,
}


def _exchange_open_rank(exchange, version=None, user=None):
    role = viewer_role(exchange, user) if user is not None else "unknown"
    is_active_pending = exchange.status in ACTIVE_PENDING_STATUSES and exchange.current_actor in {
        AgreementExchange.ACTOR_INITIATOR,
        AgreementExchange.ACTOR_COUNTERPARTY,
    }
    if is_active_pending and role != "unknown" and exchange.current_actor == role:
        status_rank = 0
    elif is_active_pending and role != "unknown":
        status_rank = 1
    elif exchange.status == AgreementExchange.STATUS_DRAFT and role == "initiator":
        status_rank = 2
    elif exchange.status in TERMINAL_STATUSES and role != "unknown":
        status_rank = 3
    elif is_active_pending:
        status_rank = 4
    elif exchange.status == AgreementExchange.STATUS_DRAFT:
        status_rank = 5
    else:
        status_rank = 6

    version_id = getattr(version, "id", None)
    if version_id is None or exchange.current_contract_version_id == version_id:
        version_rank = 0
    elif exchange.source_contract_version_id == version_id:
        version_rank = 1
    else:
        version_rank = 2
    updated_rank = -exchange.updated_at.timestamp() if exchange.updated_at else 0
    return (status_rank, version_rank, updated_rank)


def resolve_active_exchange_for_contract_and_user(contract, user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    email = normalize_email(getattr(user, "email", ""))
    filters = Q(contract=contract) & (Q(initiator=user) | Q(counterparty_user=user))
    if email:
        filters |= Q(contract=contract, counterparty_email__iexact=email)
    candidates = list(
        AgreementExchange.objects.filter(filters)
        .select_related("current_contract_version", "source_contract_version", "initiator", "counterparty_user")
        .prefetch_related("requests")
    )
    visible_candidates = [
        exchange
        for exchange in candidates
        if can_user_see_exchange(exchange, user)
    ]
    if not visible_candidates:
        return None
    return sorted(visible_candidates, key=lambda exchange: _exchange_open_rank(exchange, user=user))[0]


def find_existing_exchange_for_open(*, contract, version, counterparty_email, user=None):
    candidate = resolve_active_exchange_for_contract_and_user(contract, user) if user is not None else None
    if candidate is not None:
        return candidate
    candidates = list(
        AgreementExchange.objects.filter(
            contract=contract,
            counterparty_email__iexact=counterparty_email,
        ).select_related("current_contract_version", "source_contract_version", "initiator", "counterparty_user")
    )
    if not candidates:
        return None
    return sorted(candidates, key=lambda exchange: _exchange_open_rank(exchange, version=version, user=user))[0]


@transaction.atomic
def create_or_open_from_workflow(*, user, workflow_id):
    try:
        workflow = (
            WorkflowState.objects.select_related("contract", "created_version", "user", "counterparty_user")
            .get(pk=workflow_id)
        )
    except WorkflowState.DoesNotExist as exc:
        raise AgreementExchangeResolveError("workflow_not_found", "Workflow was not found.") from exc

    if not workflow_access_allowed(workflow, user):
        raise AgreementExchangeResolveError("permission_denied", "You do not have access to this workflow.")
    if not workflow.contract_id:
        raise AgreementExchangeResolveError("contract_missing", "Workflow is not linked to a contract.")

    if workflow.user_id != user.id:
        exchange = resolve_active_exchange_for_contract_and_user(workflow.contract, user)
        if exchange is not None:
            return load_exchange(exchange.id)
        raise AgreementExchangeResolveError("permission_denied", "Agreement Exchange is not available yet.")

    version = get_workflow_contract_version(workflow)
    if version is None:
        raise AgreementExchangeResolveError("contract_version_missing", "Workflow contract has no version available for Agreement Exchange.")

    counterparty_email = workflow.counterparty_email or workflow.sent_to_counterparty_email or workflow.contract.counterparty_email or ""
    if not counterparty_email:
        raise AgreementExchangeResolveError("counterparty_missing", "Workflow does not have a counterparty email.")

    counterparty_user = workflow.counterparty_user or find_user_by_email(counterparty_email)
    exchange = find_existing_exchange_for_open(
        contract=workflow.contract,
        version=version,
        counterparty_email=counterparty_email,
        user=user,
    )
    created = exchange is None
    if created:
        exchange = AgreementExchange.objects.create(
            contract=workflow.contract,
            current_contract_version=version,
            source_contract_version=version,
            counterparty_email=counterparty_email,
            initiator=workflow.user,
            counterparty_user=counterparty_user,
            status=AgreementExchange.STATUS_DRAFT,
            current_actor=AgreementExchange.ACTOR_INITIATOR,
        )
    update_fields = []
    if exchange.initiator_id != workflow.user_id:
        exchange.initiator = workflow.user
        update_fields.append("initiator")
    if counterparty_user and exchange.counterparty_user_id != counterparty_user.id:
        exchange.counterparty_user = counterparty_user
        update_fields.append("counterparty_user")
    if update_fields:
        update_fields.append("updated_at")
        exchange.save(update_fields=update_fields)

    if created:
        create_event(
            exchange,
            actor_user=user,
            actor_email=getattr(user, "email", ""),
            actor_role="initiator" if workflow.user_id == user.id else "system",
            event_type="exchange_opened_from_workflow",
            message="Agreement Exchange was opened from the workflow route.",
            metadata={"workflow_id": str(workflow.id)},
        )

    return load_exchange(exchange.id)


@transaction.atomic
def create_or_open_exchange(*, user, contract_id, contract_version_id, counterparty_email):
    contract = get_object_or_404(Contract, pk=contract_id)
    version = get_object_or_404(ContractVersion, pk=contract_version_id, contract=contract)
    counterparty_user = find_user_by_email(counterparty_email)
    exchange = find_existing_exchange_for_open(
        contract=contract,
        version=version,
        counterparty_email=counterparty_email,
        user=user,
    )
    created = exchange is None
    if created:
        exchange = AgreementExchange.objects.create(
            contract=contract,
            current_contract_version=version,
            counterparty_email=counterparty_email,
            initiator=user,
            counterparty_user=counterparty_user,
            source_contract_version=version,
            status=AgreementExchange.STATUS_DRAFT,
            current_actor=AgreementExchange.ACTOR_INITIATOR,
        )
    elif counterparty_user and exchange.counterparty_user_id != counterparty_user.id:
        exchange.counterparty_user = counterparty_user
        exchange.save(update_fields=["counterparty_user", "updated_at"])
    if created:
        create_event(
            exchange,
            actor_user=user,
            actor_email=getattr(user, "email", ""),
            actor_role="initiator",
            event_type="exchange_created",
            message="Agreement Exchange was created for initiator review before sending.",
            metadata={"initial_state": AgreementExchange.STATUS_DRAFT},
        )
    return load_exchange(exchange.id)


@transaction.atomic
def send_initial_version(*, exchange_id, user):
    exchange = load_exchange(exchange_id, for_update=True)
    if viewer_role(exchange, user) != "initiator":
        raise PermissionError("Only the initiator can send the initial version.")
    if exchange.status != AgreementExchange.STATUS_DRAFT or exchange.current_actor != AgreementExchange.ACTOR_INITIATOR:
        raise ValueError("Initial version can only be sent from the pre-send initiator state.")

    exchange.status = AgreementExchange.STATUS_COUNTERPARTY_REVIEW
    exchange.current_actor = AgreementExchange.ACTOR_COUNTERPARTY
    exchange.save(update_fields=["status", "current_actor", "updated_at"])
    redirect_url = exchange_redirect_url(exchange)
    actor_label = _display_name(user, getattr(user, "email", ""), "Initiator")
    action_text = "Review and respond"
    notification = notify_counterparty(
        exchange,
        _exchange_notification_message(exchange, actor_label=actor_label, action_text=action_text),
        _notification_metadata(
            exchange,
            action_type="review_initial_version",
            source_event="initial_version_sent",
            actor_label=actor_label,
            action_text=action_text,
        ),
        title="Initial version sent",
    )
    create_event(
        exchange,
        actor_user=user,
        actor_email=getattr(user, "email", ""),
        actor_role="initiator",
        event_type="initial_version_sent",
        message="Initiator sent Version 1 to the counterparty.",
        metadata={
            "notification": notification,
            "version_id": str(exchange.current_contract_version_id),
            "version_number": exchange.current_contract_version.version_number,
        },
    )
    return load_exchange(exchange.id)


@transaction.atomic
def mark_viewed(*, exchange_id, user):
    exchange = load_exchange(exchange_id, for_update=True)
    if exchange.status == AgreementExchange.STATUS_DRAFT:
        return load_exchange(exchange.id)
    role = viewer_role(exchange, user)
    create_event(
        exchange,
        actor_user=user,
        actor_email=getattr(user, "email", "") or exchange.counterparty_email,
        actor_role=role if role != "unknown" else "counterparty",
        event_type="exchange_viewed",
        message="Agreement Exchange was viewed.",
    )
    return load_exchange(exchange.id)


@transaction.atomic
def create_change_request(*, exchange_id, user, validated_data):
    exchange = load_exchange(exchange_id, for_update=True)
    if exchange.status == AgreementExchange.STATUS_DRAFT:
        raise ValueError("The initial version has not been sent to the counterparty yet.")
    role = viewer_role(exchange, user)
    if role != "counterparty" or exchange.current_actor != AgreementExchange.ACTOR_COUNTERPARTY:
        raise PermissionError("Only the counterparty can request changes while it is their turn.")
    requester_email = getattr(user, "email", "") or exchange.counterparty_email
    change_request = AgreementExchangeRequest.objects.create(
        exchange=exchange,
        requested_by_user=user if getattr(user, "is_authenticated", False) else None,
        requested_by_email=requester_email,
        **validated_data,
    )
    exchange.status = AgreementExchange.STATUS_INITIATOR_REVIEW
    exchange.current_actor = AgreementExchange.ACTOR_INITIATOR
    exchange.save(update_fields=["status", "current_actor", "updated_at"])
    redirect_url = exchange_redirect_url(exchange)
    actor_label = _display_name(user, requester_email, "Counterparty")
    action_text = "Accept, edit, or reject"
    notification = notify_initiator(
        exchange,
        _exchange_notification_message(exchange, actor_label=actor_label, action_text=action_text),
        _notification_metadata(
            exchange,
            action_type="respond_to_change_request",
            source_event="counterparty_request_created",
            actor_label=actor_label,
            action_text=action_text,
            extra={"request_id": str(change_request.id)},
        ),
        title="Change request received",
    )
    create_event(
        exchange,
        actor_user=user,
        actor_email=requester_email,
        actor_role=role if role != "unknown" else "counterparty",
        event_type="counterparty_request_created",
        message="Counterparty requested a structured change.",
        metadata={"request_id": str(change_request.id), "request_category": change_request.request_category, "redirect_url": redirect_url, "notification": notification},
    )
    return load_exchange(exchange.id), change_request


@transaction.atomic
def respond_to_request(*, exchange_id, request_id, user, decision, final_text="", initiator_response=""):
    exchange = load_exchange(exchange_id, for_update=True)
    change_request = get_object_or_404(AgreementExchangeRequest.objects.select_for_update(), pk=request_id, exchange=exchange)
    if decision not in {"accept", "edit", "reject"}:
        raise ValueError("decision must be accept, edit, or reject")
    if viewer_role(exchange, user) != "initiator":
        raise PermissionError("Only the initiator can respond to requested changes.")
    if exchange.status not in {AgreementExchange.STATUS_INITIATOR_REVIEW, AgreementExchange.STATUS_INITIATOR_EDITING} or exchange.current_actor != AgreementExchange.ACTOR_INITIATOR:
        raise PermissionError("Requested changes can only be answered while it is the initiator's turn.")
    if change_request.status not in {AgreementExchangeRequest.STATUS_PENDING, AgreementExchangeRequest.STATUS_ACCEPTED, AgreementExchangeRequest.STATUS_EDITED}:
        raise ValueError("Only pending or staged requested changes can be answered.")

    metadata = {"request_id": str(change_request.id), "decision": decision, "version_creation": "not_wired_mvp"}
    if decision == "reject":
        staged_version = exchange.staged_contract_version
        change_request.status = AgreementExchangeRequest.STATUS_REJECTED
        change_request.initiator_response = initiator_response or "Request rejected."
        change_request.save(update_fields=["status", "initiator_response", "updated_at"])
        if staged_version and staged_version.status == "draft":
            staged_version.status = "archived"
            staged_version.save(update_fields=["status"])
        exchange.staged_contract_version = None
        exchange.status = AgreementExchange.STATUS_COUNTERPARTY_REVIEW
        exchange.current_actor = AgreementExchange.ACTOR_COUNTERPARTY
        exchange.save(update_fields=["staged_contract_version", "status", "current_actor", "updated_at"])
        redirect_url = exchange_redirect_url(exchange)
        actor_label = _display_name(user, getattr(user, "email", ""), "Initiator")
        action_text = "View response"
        notification = notify_counterparty(
            exchange,
            _exchange_notification_message(exchange, actor_label=actor_label, action_text=action_text),
            _notification_metadata(
                exchange,
                action_type="change_request_rejected",
                source_event="request_response_sent",
                actor_label=actor_label,
                action_text=action_text,
                extra={"request_id": str(change_request.id), "decision": decision},
            ),
            title="Change request rejected",
        )
        metadata["redirect_url"] = redirect_url
        metadata["notification"] = notification
        create_event(
            exchange,
            actor_user=user,
            actor_email=getattr(user, "email", ""),
            actor_role="initiator",
            event_type="initiator_request_rejected",
            message="Initiator rejected the requested change.",
            metadata=metadata,
        )
        return load_exchange(exchange.id), change_request

    change_request.status = AgreementExchangeRequest.STATUS_ACCEPTED if decision == "accept" else AgreementExchangeRequest.STATUS_EDITED
    change_request.initiator_response = initiator_response or ("Request accepted for review." if decision == "accept" else "Request staged for manual editing.")
    change_request.pending_next_version_text = final_text or change_request.proposed_text
    staged_version = _create_staged_exchange_version_from_request(
        exchange,
        change_request,
        decision=decision,
        final_text=change_request.pending_next_version_text,
        initiator_response=change_request.initiator_response,
        actor=user,
    )
    change_request.save(update_fields=["status", "initiator_response", "pending_next_version_text", "updated_at"])
    exchange.staged_contract_version = staged_version
    exchange.status = AgreementExchange.STATUS_INITIATOR_EDITING
    exchange.current_actor = AgreementExchange.ACTOR_INITIATOR
    exchange.save(update_fields=["staged_contract_version", "status", "current_actor", "updated_at"])
    metadata.update({
        "pending_next_version_text": change_request.pending_next_version_text,
        "version_creation": "contract_version_staged",
        "staged_version_id": str(staged_version.id),
        "version_number": staged_version.version_number,
        "previous_version_id": str(staged_version.previous_version_id) if staged_version.previous_version_id else None,
    })
    create_event(
        exchange,
        actor_user=user,
        actor_email=getattr(user, "email", ""),
        actor_role="initiator",
        event_type="initiator_update_staged",
        message="Initiator staged an updated contract version for review before sending.",
        metadata=metadata,
    )
    return load_exchange(exchange.id), change_request


def _request_for_staged_version(exchange, staged_version):
    metadata = _version_update_metadata(staged_version)
    request_id = metadata.get("request_id")
    if request_id:
        return get_object_or_404(AgreementExchangeRequest.objects.select_for_update(), pk=request_id, exchange=exchange)
    return exchange.requests.select_for_update().filter(status__in=[
        AgreementExchangeRequest.STATUS_ACCEPTED,
        AgreementExchangeRequest.STATUS_EDITED,
        AgreementExchangeRequest.STATUS_PENDING,
    ]).order_by("-updated_at", "-created_at").first()


def _ensure_staged_request_context(staged_version, change_request):
    snapshot = extract_snapshot(staged_version)
    latest_update = snapshot.get("agreement_exchange_latest_update")
    if not isinstance(latest_update, dict):
        latest_update = {}
    latest_update.update({
        "source": "agreement_exchange",
        "request_id": str(change_request.id),
        "target_section_id": change_request.target_section_id,
        "target_section_title": change_request.target_section_title,
        "request_category": change_request.request_category,
        "action_type": change_request.action_type,
        "proposed_text": change_request.proposed_text,
        "staged_for_agreement_exchange": True,
        "sent_to_counterparty": False,
    })
    updates = snapshot.get("agreement_exchange_updates")
    if not isinstance(updates, list):
        updates = []
    if updates:
        updates[-1] = latest_update
    else:
        updates.append(latest_update)
    snapshot["agreement_exchange_updates"] = updates
    snapshot["agreement_exchange_latest_update"] = latest_update
    return snapshot


def _validate_staged_update_for_initiator(exchange, user, staged_version_id=None):
    if viewer_role(exchange, user) != "initiator":
        raise PermissionError("Only the initiator can edit the updated version.")
    if exchange.current_actor != AgreementExchange.ACTOR_INITIATOR or exchange.status not in {AgreementExchange.STATUS_INITIATOR_REVIEW, AgreementExchange.STATUS_INITIATOR_EDITING}:
        raise PermissionError("Updated versions can only be edited while the initiator is editing the staged version.")
    if not exchange.staged_contract_version_id:
        raise ValueError("This exchange does not have a staged version.")
    if staged_version_id and str(exchange.staged_contract_version_id) != str(staged_version_id):
        raise ValueError("The staged version does not match this exchange.")

    staged_version = get_object_or_404(
        ContractVersion.objects.select_for_update(),
        pk=exchange.staged_contract_version_id,
        contract=exchange.contract,
        status="draft",
    )
    if staged_version.previous_version_id != exchange.current_contract_version_id:
        raise ValueError("The staged version is no longer based on the current exchange version.")
    change_request = _request_for_staged_version(exchange, staged_version)
    if change_request is None:
        raise ValueError("The staged version is missing request context.")
    if change_request.status == AgreementExchangeRequest.STATUS_PENDING:
        change_request.status = AgreementExchangeRequest.STATUS_EDITED
        change_request.initiator_response = change_request.initiator_response or "Request staged for manual editing."
        change_request.pending_next_version_text = change_request.pending_next_version_text or change_request.proposed_text
        change_request.save(update_fields=["status", "initiator_response", "pending_next_version_text", "updated_at"])
    if change_request.status not in {AgreementExchangeRequest.STATUS_ACCEPTED, AgreementExchangeRequest.STATUS_EDITED}:
        raise ValueError("The requested change has not been staged for editing.")
    if not _version_update_metadata(staged_version).get("request_id"):
        _update_draft_staged_version_snapshot(staged_version, _ensure_staged_request_context(staged_version, change_request))
    return staged_version, change_request


@transaction.atomic
def rebuild_staged_updated_version(*, exchange_id, user):
    exchange = load_exchange(exchange_id, for_update=True)
    staged_version, change_request = _validate_staged_update_for_initiator(exchange, user)
    decision = "edit" if change_request.status == AgreementExchangeRequest.STATUS_EDITED else "accept"
    final_text = change_request.pending_next_version_text or change_request.proposed_text
    staged_version = _replace_staged_version_snapshot(
        exchange,
        staged_version,
        change_request,
        decision=decision,
        final_text=final_text,
        initiator_response=change_request.initiator_response or "",
    )
    exchange.status = AgreementExchange.STATUS_INITIATOR_EDITING
    exchange.current_actor = AgreementExchange.ACTOR_INITIATOR
    exchange.save(update_fields=["status", "current_actor", "updated_at"])
    create_event(
        exchange,
        actor_user=user,
        actor_email=getattr(user, "email", ""),
        actor_role="initiator",
        event_type="staged_update_rebuilt",
        message="Initiator rebuilt the staged updated contract version from the current contract.",
        metadata={"request_id": str(change_request.id), "staged_version_id": str(staged_version.id)},
    )
    return load_exchange(exchange.id), change_request


@transaction.atomic
def save_staged_updated_version(*, exchange_id, user, staged_version_id, full_content_html=""):
    exchange = load_exchange(exchange_id, for_update=True)
    staged_version, change_request = _validate_staged_update_for_initiator(exchange, user, staged_version_id)
    if not str(full_content_html or "").strip():
        raise ValueError("full_content_html is required.")

    snapshot = _ensure_staged_request_context(staged_version, change_request)
    snapshot["editor_html"] = full_content_html
    latest_update = snapshot.get("agreement_exchange_latest_update")
    if isinstance(latest_update, dict):
        latest_update["manual_full_contract_review"] = True
        latest_update["staged_saved"] = True
        latest_update["sent_to_counterparty"] = False
    updates = snapshot.get("agreement_exchange_updates")
    if isinstance(updates, list) and updates and isinstance(latest_update, dict):
        updates[-1] = latest_update
    _require_staged_snapshot_ready(snapshot)
    _update_draft_staged_version_snapshot(staged_version, snapshot)
    create_event(
        exchange,
        actor_user=user,
        actor_email=getattr(user, "email", ""),
        actor_role="initiator",
        event_type="staged_update_saved",
        message="Initiator saved the staged updated contract version.",
        metadata={"request_id": str(change_request.id), "staged_version_id": str(staged_version.id)},
    )
    return load_exchange(exchange.id), change_request


@transaction.atomic
def send_staged_updated_version(*, exchange_id, user, staged_version_id=None, message_to_counterparty="", full_content_html=""):
    exchange = load_exchange(exchange_id, for_update=True)
    staged_version, change_request = _validate_staged_update_for_initiator(exchange, user, staged_version_id)
    snapshot = _ensure_staged_request_context(staged_version, change_request)
    if full_content_html:
        snapshot["editor_html"] = full_content_html
    _require_staged_snapshot_ready(snapshot)
    _update_draft_staged_version_snapshot(staged_version, snapshot)

    final_version = _finalize_staged_exchange_version(exchange, staged_version, full_content_html="")
    exchange.current_contract_version = final_version
    exchange.staged_contract_version = None
    exchange.status = AgreementExchange.STATUS_COUNTERPARTY_REVIEW
    exchange.current_actor = AgreementExchange.ACTOR_COUNTERPARTY
    exchange.save(update_fields=["current_contract_version", "staged_contract_version", "status", "current_actor", "updated_at"])

    redirect_url = exchange_redirect_url(exchange)
    actor_label = _display_name(user, getattr(user, "email", ""), "Initiator")
    action_text = "Review changes"
    notification = notify_counterparty(
        exchange,
        _exchange_notification_message(exchange, actor_label=actor_label, action_text=action_text),
        _notification_metadata(
            exchange,
            action_type="review_updated_version",
            source_event="request_response_sent",
            actor_label=actor_label,
            action_text=action_text,
            extra={"request_id": str(change_request.id), "staged_version_id": str(final_version.id)},
        ),
        title="Updated version ready for review",
    )
    create_event(
        exchange,
        actor_user=user,
        actor_email=getattr(user, "email", ""),
        actor_role="initiator",
        event_type="updated_version_sent",
        message="Initiator sent the reviewed updated contract version to the counterparty.",
        metadata={
            "request_id": str(change_request.id),
            "version_id": str(final_version.id),
            "version_number": final_version.version_number,
            "message_to_counterparty": message_to_counterparty,
            "redirect_url": redirect_url,
            "notification": notification,
        },
    )
    return load_exchange(exchange.id), change_request


@transaction.atomic
def restart_exchange_from_version(*, exchange_id, source_version_id, user, counterparty_email=""):
    old_exchange = load_exchange(exchange_id, for_update=True)
    if viewer_role(old_exchange, user) != "initiator":
        raise PermissionError("Only the initiator can restart a rejected Agreement Exchange.")
    if old_exchange.status != AgreementExchange.STATUS_REJECTED:
        raise ValueError("Only rejected Agreement Exchanges can be restarted.")

    source_version = get_object_or_404(
        ContractVersion,
        pk=source_version_id,
        contract=old_exchange.contract,
    )
    if not _version_belongs_to_exchange_history(old_exchange, source_version):
        raise ValueError("Selected source version is not part of this Agreement Exchange history.")

    restart_counterparty_email = counterparty_email or old_exchange.counterparty_email
    counterparty_user = old_exchange.counterparty_user or find_user_by_email(restart_counterparty_email)
    new_exchange = AgreementExchange.objects.create(
        contract=old_exchange.contract,
        current_contract_version=source_version,
        source_contract_version=source_version,
        restarted_from_exchange=old_exchange,
        counterparty_email=restart_counterparty_email,
        initiator=old_exchange.initiator,
        counterparty_user=counterparty_user,
        status=AgreementExchange.STATUS_DRAFT,
        current_actor=AgreementExchange.ACTOR_INITIATOR,
    )
    create_event(
        old_exchange,
        actor_user=user,
        actor_email=getattr(user, "email", ""),
        actor_role="initiator",
        event_type="exchange_restarted",
        message="Restarted as a new Agreement Exchange.",
        metadata={
            "new_exchange_id": str(new_exchange.id),
            "source_version_id": str(source_version.id),
            "source_version_number": source_version.version_number,
        },
    )
    create_event(
        new_exchange,
        actor_user=user,
        actor_email=getattr(user, "email", ""),
        actor_role="initiator",
        event_type="exchange_restarted_from_rejected",
        message="Restarted from a rejected Agreement Exchange.",
        metadata={
            "source_exchange_id": str(old_exchange.id),
            "source_version_id": str(source_version.id),
            "source_version_number": source_version.version_number,
        },
    )
    return load_exchange(new_exchange.id)


def _version_belongs_to_exchange_history(exchange, source_version):
    current = exchange.current_contract_version
    seen = set()
    while current and current.id not in seen:
        if current.id == source_version.id:
            return True
        seen.add(current.id)
        current = current.previous_version
    return False


@transaction.atomic
def reject_exchange(*, exchange_id, user, reason=""):
    exchange = load_exchange(exchange_id, for_update=True)
    role = viewer_role(exchange, user)
    if exchange.status == AgreementExchange.STATUS_DRAFT:
        raise PermissionError("The initial version has not been sent to the counterparty yet.")
    exchange.status = AgreementExchange.STATUS_REJECTED
    exchange.current_actor = AgreementExchange.ACTOR_NONE
    exchange.save(update_fields=["status", "current_actor", "updated_at"])
    message = reason or "Agreement Exchange was rejected."
    redirect_url = exchange_redirect_url(exchange)
    actor_label = _display_name(user, getattr(user, "email", ""), "Counterparty" if role == "counterparty" else "Initiator")
    action_text = "View negotiation"
    notification_metadata = _notification_metadata(
        exchange,
        action_type="exchange_rejected",
        source_event="exchange_rejected",
        actor_label=actor_label,
        action_text=action_text,
    )
    notification_message = _exchange_notification_message(
        exchange,
        actor_label=actor_label,
        action_text=action_text,
        actor_prefix="Rejected by",
    )
    recipient_result = notify_initiator(exchange, notification_message, notification_metadata, title="Contract rejected") if role == "counterparty" else notify_counterparty(exchange, notification_message, notification_metadata, title="Contract rejected")
    create_event(
        exchange,
        actor_user=user,
        actor_email=getattr(user, "email", "") or (exchange.counterparty_email if role == "counterparty" else ""),
        actor_role=role if role in {"initiator", "counterparty"} else "system",
        event_type="exchange_rejected",
        message=message,
        metadata={"reason": reason, "redirect_url": redirect_url, "notification": recipient_result},
    )
    return load_exchange(exchange.id)


@transaction.atomic
def sign_exchange(*, exchange_id, user, typed_name="", signature_text="", ip_address=None, user_agent=""):
    exchange = load_exchange(exchange_id, for_update=True)
    role = viewer_role(exchange, user)
    if exchange.status == AgreementExchange.STATUS_DRAFT:
        raise PermissionError("The initial version has not been sent to the counterparty yet.")
    if role not in {"initiator", "counterparty"}:
        raise PermissionError("Only an exchange participant can sign.")
    signer_email = getattr(user, "email", "") or (exchange.counterparty_email if role == "counterparty" else "")
    signature = AgreementExchangeSignature.objects.create(
        exchange=exchange,
        signer_user=user if getattr(user, "is_authenticated", False) else None,
        signer_email=signer_email,
        signer_role=role,
        signed_version=exchange.current_contract_version,
        typed_name=typed_name,
        signature_text=signature_text,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    current_version = exchange.current_contract_version
    contract = exchange.contract
    if current_version.status != "signed":
        current_version.status = "signed"
        current_version.save(update_fields=["status"])
    if contract.status != "signed":
        contract.status = "signed"
        contract.save(update_fields=["status"])
    exchange.status = AgreementExchange.STATUS_SIGNED
    exchange.current_actor = AgreementExchange.ACTOR_NONE
    exchange.save(update_fields=["status", "current_actor", "updated_at"])
    redirect_url = f"/lifecycle?contract={contract.id}"
    actor_label = _display_name(user, signer_email, "Counterparty" if role == "counterparty" else "Initiator")
    action_text = "Open Agreement Timeline"
    notification_metadata = _notification_metadata(
        exchange,
        action_type="exchange_signed",
        source_event="signed",
        actor_label=actor_label,
        action_text=action_text,
        extra={"signature_id": str(signature.id), "redirect_url": redirect_url},
    )
    notification_message = _exchange_notification_message(
        exchange,
        actor_label=actor_label,
        action_text=action_text,
        actor_prefix="Signed by",
    )
    notification = notify_initiator(exchange, notification_message, notification_metadata, title="Contract signed") if role == "counterparty" else notify_counterparty(exchange, notification_message, notification_metadata, title="Contract signed")
    create_event(
        exchange,
        actor_user=user,
        actor_email=signer_email,
        actor_role=role,
        event_type="signed",
        message="Agreement Exchange was signed using the Agreement Exchange MVP signature flow.",
        metadata={"signature_id": str(signature.id), "mvp_signature": True, "redirect_url": redirect_url, "notification": notification},
    )
    return load_exchange(exchange.id), signature
