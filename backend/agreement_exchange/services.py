import json

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


class AgreementExchangeResolveError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__(message)


def extract_snapshot(version):
    raw = getattr(version, "content_snapshot", "") or ""
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return {"content_html": raw, "sections": []}
    return parsed if isinstance(parsed, dict) else {"content_html": raw, "sections": []}


def extract_contract_sections(content_snapshot):
    return normalize_contract_sections(content_snapshot)


def _reviewed_update_snapshot(previous_version, change_request, *, decision, final_text, initiator_response):
    reviewed_text = final_text or change_request.proposed_text
    snapshot = apply_request_to_snapshot(extract_snapshot(previous_version), change_request, accepted_text=reviewed_text)
    latest_update = snapshot.get("agreement_exchange_latest_update")
    if isinstance(latest_update, dict):
        latest_update["decision"] = decision
        latest_update["initiator_response"] = initiator_response or ""
    updates = snapshot.get("agreement_exchange_updates")
    if isinstance(updates, list) and updates:
        updates[-1] = latest_update
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


def _create_exchange_version_from_request(exchange, change_request, *, decision, final_text, initiator_response, actor):
    contract = exchange.contract
    existing_count = exchange_local_version_number(exchange)
    if existing_count >= contract.max_versions:
        raise ValueError(f"Maximum version limit reached ({contract.max_versions}).")

    previous = exchange.current_contract_version
    content_snapshot = _reviewed_update_snapshot(
        previous,
        change_request,
        decision=decision,
        final_text=final_text,
        initiator_response=initiator_response,
    )
    if previous.status not in {"signed", "rejected", "archived", "superseded"}:
        previous.superseded = True
        previous.status = "superseded"
        previous.save(update_fields=["superseded", "status"])

    new_version = ContractVersion.objects.create(
        contract=contract,
        version_number=next_contract_version_number(contract),
        created_by=actor if getattr(actor, "is_authenticated", False) else None,
        previous_version=previous,
        content_snapshot=content_snapshot,
        status="sent",
    )
    WorkflowState.objects.filter(
        contract=contract,
        created_version=previous,
    ).filter(
        Q(counterparty_email__iexact=exchange.counterparty_email)
        | Q(sent_to_counterparty_email__iexact=exchange.counterparty_email)
    ).update(created_version=new_version)
    return new_version


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


def screen_state(exchange, role):
    if exchange.status == AgreementExchange.STATUS_DRAFT:
        return "initiator_send_initial_version" if role == "initiator" else "counterparty_not_sent"
    if exchange.status == AgreementExchange.STATUS_SIGNED:
        return "signed"
    if exchange.status == AgreementExchange.STATUS_REJECTED:
        return "rejected"
    if exchange.status == AgreementExchange.STATUS_INITIATOR_REVIEW:
        return "initiator_review_requested_change" if role == "initiator" else "counterparty_waiting"
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
    if (
        role == "initiator"
        and exchange.current_actor == AgreementExchange.ACTOR_INITIATOR
        and exchange.status == AgreementExchange.STATUS_INITIATOR_REVIEW
        and has_pending_request(exchange)
    ):
        return ["accept", "edit", "reject"]
    return []


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
    return {
        "exchange": exchange_summary(exchange),
        "viewer_role": role,
        "screen_state": screen_state(exchange, role),
        "current_contract": current_contract_payload(exchange),
        "requests": [serialize_request(item) for item in exchange.requests.all()],
        "events": [serialize_event(item) for item in exchange.events.all()],
        "signatures": [serialize_signature(item) for item in exchange.signatures.all()],
        "available_actions": available_actions(exchange, role),
    }


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
    queryset = AgreementExchange.objects.select_related("contract", "current_contract_version", "source_contract_version", "restarted_from_exchange", "initiator", "counterparty_user").prefetch_related("requests", "events", "signatures")
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
    notification = notify_counterparty(
        exchange,
        "Version 1 is ready for review.",
        exchange_notification_metadata(exchange, action_type="review_initial_version", source_event="initial_version_sent"),
        title="Version 1 is ready for review",
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
    notification = notify_initiator(
        exchange,
        "Counterparty requested a change.",
        exchange_notification_metadata(
            exchange,
            action_type="respond_to_change_request",
            source_event="counterparty_request_created",
            extra={"request_id": str(change_request.id)},
        ),
        title="Counterparty requested a change",
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
    if exchange.status != AgreementExchange.STATUS_INITIATOR_REVIEW or exchange.current_actor != AgreementExchange.ACTOR_INITIATOR:
        raise PermissionError("Requested changes can only be answered while it is the initiator's turn.")
    if change_request.status != AgreementExchangeRequest.STATUS_PENDING:
        raise ValueError("Only pending requested changes can be answered.")

    metadata = {"request_id": str(change_request.id), "decision": decision, "version_creation": "not_wired_mvp"}
    if decision == "reject":
        change_request.status = AgreementExchangeRequest.STATUS_REJECTED
        change_request.initiator_response = initiator_response or "Request rejected."
        change_request.save(update_fields=["status", "initiator_response", "updated_at"])
        exchange.status = AgreementExchange.STATUS_COUNTERPARTY_REVIEW
        exchange.current_actor = AgreementExchange.ACTOR_COUNTERPARTY
        event_type = "initiator_request_rejected"
        message = "Initiator rejected the requested change."
    else:
        change_request.status = AgreementExchangeRequest.STATUS_ACCEPTED if decision == "accept" else AgreementExchangeRequest.STATUS_EDITED
        change_request.initiator_response = initiator_response or ("Request accepted." if decision == "accept" else "Request edited and sent back.")
        change_request.pending_next_version_text = final_text or change_request.proposed_text
        new_version = _create_exchange_version_from_request(
            exchange,
            change_request,
            decision=decision,
            final_text=change_request.pending_next_version_text,
            initiator_response=change_request.initiator_response,
            actor=user,
        )
        change_request.save(update_fields=["status", "initiator_response", "pending_next_version_text", "updated_at"])
        exchange.current_contract_version = new_version
        exchange.status = AgreementExchange.STATUS_UPDATED_VERSION_SENT
        exchange.current_actor = AgreementExchange.ACTOR_COUNTERPARTY
        metadata["pending_next_version_text"] = change_request.pending_next_version_text
        metadata["version_creation"] = "contract_version_created"
        metadata["version_id"] = str(new_version.id)
        metadata["version_number"] = new_version.version_number
        metadata["previous_version_id"] = str(new_version.previous_version_id) if new_version.previous_version_id else None
        event_type = "initiator_request_accepted" if decision == "accept" else "initiator_request_edited"
        message = "Initiator accepted the requested change." if decision == "accept" else "Initiator edited the requested change and sent an update."

    update_fields = ["status", "current_actor", "updated_at"]
    if decision != "reject":
        update_fields.append("current_contract_version")
    exchange.save(update_fields=update_fields)
    redirect_url = exchange_redirect_url(exchange)
    notification = notify_counterparty(
        exchange,
        "Updated version is ready for review." if decision != "reject" else "Your change request was rejected.",
        exchange_notification_metadata(
            exchange,
            action_type="review_updated_version" if decision != "reject" else "change_request_rejected",
            source_event="request_response_sent",
            extra={"request_id": str(change_request.id), "decision": decision},
        ),
        title="Updated version is ready for review" if decision != "reject" else "Change request rejected",
    )
    metadata["redirect_url"] = redirect_url
    metadata["notification"] = notification
    create_event(
        exchange,
        actor_user=user,
        actor_email=getattr(user, "email", ""),
        actor_role="initiator",
        event_type=event_type,
        message=message,
        metadata=metadata,
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
    notification_metadata = exchange_notification_metadata(exchange, action_type="exchange_rejected", source_event="exchange_rejected")
    recipient_result = notify_initiator(exchange, "Agreement was rejected.", notification_metadata, title="Agreement was rejected") if role == "counterparty" else notify_counterparty(exchange, "Agreement was rejected.", notification_metadata, title="Agreement was rejected")
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
    exchange.status = AgreementExchange.STATUS_SIGNED
    exchange.current_actor = AgreementExchange.ACTOR_NONE
    exchange.save(update_fields=["status", "current_actor", "updated_at"])
    redirect_url = exchange_redirect_url(exchange)
    notification_metadata = exchange_notification_metadata(
        exchange,
        action_type="exchange_signed",
        source_event="signed",
        extra={"signature_id": str(signature.id)},
    )
    notification = notify_initiator(exchange, "Agreement was signed.", notification_metadata, title="Agreement was signed") if role == "counterparty" else notify_counterparty(exchange, "Agreement was signed.", notification_metadata, title="Agreement was signed")
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
