import json
from html import escape

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404

from backend.agreement_exchange.models import (
    AgreementExchange,
    AgreementExchangeEvent,
    AgreementExchangeRequest,
    AgreementExchangeSignature,
)
from backend.agreement_exchange.notifications import find_user_by_email, notify_exchange_recipient
from backend.ai.models import WorkflowState
from backend.contracts.models import Contract, ContractVersion

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
    if not content_snapshot:
        return []
    if isinstance(content_snapshot, str):
        try:
            snapshot = json.loads(content_snapshot)
        except (TypeError, ValueError):
            return []
    else:
        snapshot = content_snapshot
    if not isinstance(snapshot, dict):
        return []
    sections = snapshot.get("sections")
    if not isinstance(sections, list):
        return []
    normalized = []
    for index, section in enumerate(sections, start=1):
        if not isinstance(section, dict):
            continue
        title = section.get("name") or section.get("title") or section.get("heading") or ""
        if not title:
            continue
        normalized.append({
            "id": str(section.get("id") or section.get("section_id") or index),
            "title": str(title),
            "name": str(title),
            "number": section.get("number") or index,
            "content_html": section.get("content_html") or section.get("html") or section.get("body") or "",
        })
    return normalized


def _paragraph_html(value):
    lines = [line.strip() for line in str(value or "").splitlines()]
    blocks = []
    current = []
    for line in lines:
        if line:
            current.append(line)
        elif current:
            blocks.append(" ".join(current))
            current = []
    if current:
        blocks.append(" ".join(current))
    return "".join(f"<p>{escape(block)}</p>" for block in blocks)


def _reviewed_update_snapshot(previous_version, change_request, *, decision, final_text, initiator_response):
    snapshot = dict(extract_snapshot(previous_version))
    reviewed_text = final_text or change_request.proposed_text
    update = {
        "source": "agreement_exchange",
        "request_id": str(change_request.id),
        "decision": decision,
        "target_section_id": change_request.target_section_id,
        "target_section_title": change_request.target_section_title,
        "request_category": change_request.request_category,
        "action_type": change_request.action_type,
        "proposed_text": reviewed_text,
        "initiator_response": initiator_response or "",
    }
    existing_updates = snapshot.get("agreement_exchange_updates")
    if not isinstance(existing_updates, list):
        existing_updates = []
    snapshot["agreement_exchange_updates"] = [*existing_updates, update]
    snapshot["agreement_exchange_latest_update"] = update

    base_html = (
        snapshot.get("editor_html")
        or snapshot.get("final_editor_html")
        or snapshot.get("content_html")
        or snapshot.get("html")
        or previous_version.content_snapshot
        or ""
    )
    if not str(base_html).lstrip().startswith("<"):
        base_html = _paragraph_html(base_html)

    update_html = (
        '<section data-agreement-exchange-update="true" '
        f'data-request-id="{escape(str(change_request.id))}" '
        'style="margin-top:24px;padding-top:16px;border-top:1px solid #CBD5E1;">'
        '<h2>Agreement Exchange Update</h2>'
        f'<p><strong>Target section:</strong> {escape(change_request.target_section_title or "General")}</p>'
        f'<p><strong>Action:</strong> {escape(change_request.action_type.replace("_", " "))}</p>'
        f'{_paragraph_html(reviewed_text)}'
        f'{_paragraph_html(initiator_response) if initiator_response else ""}'
        '</section>'
    )
    snapshot["editor_html"] = f"{base_html}{update_html}"
    return json.dumps(snapshot)


def _create_exchange_version_from_request(exchange, change_request, *, decision, final_text, initiator_response, actor):
    contract = exchange.contract
    existing_count = contract.versions.count()
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
        version_number=existing_count + 1,
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
    return {
        "id": str(version.id),
        "contract_id": str(exchange.contract_id),
        "title": exchange.contract.title or "Untitled agreement",
        "version_label": f"v{version.version_number}",
        "version_number": version.version_number,
        "status": version.status,
        "content_html": content_html,
        "sections": sections,
    }


def viewer_role(exchange, user):
    if not user or not getattr(user, "is_authenticated", False):
        return "unknown"
    if exchange.initiator_id == user.id:
        return "initiator"
    user_email = (getattr(user, "email", "") or "").lower()
    if exchange.counterparty_user_id == user.id or user_email == (exchange.counterparty_email or "").lower():
        return "counterparty"
    return "unknown"


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
    if role == "initiator" and exchange.current_actor == AgreementExchange.ACTOR_INITIATOR:
        return ["accept_request", "edit_request", "reject_request"]
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


def notify_initiator(exchange, message, metadata=None):
    return notify_exchange_recipient(
        user=exchange.initiator,
        notification_type="contract_updated",
        message=message,
        contract=exchange.contract,
        metadata=metadata or {},
    )


def notify_counterparty(exchange, message, metadata=None):
    recipient = exchange.counterparty_user or find_user_by_email(exchange.counterparty_email)
    return notify_exchange_recipient(
        user=recipient,
        email=exchange.counterparty_email,
        notification_type="version_created",
        message=message,
        contract=exchange.contract,
        metadata=metadata or {},
    )


def load_exchange(exchange_id, for_update=False):
    queryset = AgreementExchange.objects.select_related("contract", "current_contract_version", "initiator", "counterparty_user").prefetch_related("requests", "events", "signatures")
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

    version = get_workflow_contract_version(workflow)
    if version is None:
        raise AgreementExchangeResolveError("contract_version_missing", "Workflow contract has no version available for Agreement Exchange.")

    counterparty_email = workflow.counterparty_email or workflow.sent_to_counterparty_email or workflow.contract.counterparty_email or ""
    if not counterparty_email:
        raise AgreementExchangeResolveError("counterparty_missing", "Workflow does not have a counterparty email.")

    counterparty_user = workflow.counterparty_user or find_user_by_email(counterparty_email)
    exchange = (
        AgreementExchange.objects.filter(
            contract=workflow.contract,
            current_contract_version=version,
            counterparty_email__iexact=counterparty_email,
        )
        .order_by("-updated_at", "-created_at")
        .first()
    )
    created = exchange is None
    if created:
        exchange = AgreementExchange.objects.create(
            contract=workflow.contract,
            current_contract_version=version,
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
    exchange, created = AgreementExchange.objects.get_or_create(
        contract=contract,
        current_contract_version=version,
        counterparty_email=counterparty_email,
        defaults={
            "initiator": user,
            "counterparty_user": counterparty_user,
            "status": AgreementExchange.STATUS_DRAFT,
            "current_actor": AgreementExchange.ACTOR_INITIATOR,
        },
    )
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
    notification = notify_counterparty(
        exchange,
        f"You have been invited to review {exchange.contract.title or 'an agreement'} on bonUP: /agreement-exchange/{exchange.id}",
        {"exchange_id": str(exchange.id), "contract_version_id": str(exchange.current_contract_version_id)},
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
    if exchange.status in {AgreementExchange.STATUS_SENT, AgreementExchange.STATUS_VIEWED}:
        exchange.status = AgreementExchange.STATUS_COUNTERPARTY_REVIEW
    exchange.current_actor = AgreementExchange.ACTOR_COUNTERPARTY
    exchange.save(update_fields=["status", "current_actor", "updated_at"])
    create_event(
        exchange,
        actor_user=user,
        actor_email=getattr(user, "email", "") or exchange.counterparty_email,
        actor_role=viewer_role(exchange, user) if viewer_role(exchange, user) != "unknown" else "counterparty",
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
    redirect_url = f"/agreement-exchange/{exchange.id}"
    notification = notify_initiator(
        exchange,
        f"A counterparty requested changes to {exchange.contract.title or 'an agreement'}. Open it at {redirect_url}.",
        {"exchange_id": str(exchange.id), "request_id": str(change_request.id), "redirect_url": redirect_url},
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
    notification = notify_counterparty(exchange, message, {"exchange_id": str(exchange.id), "request_id": str(change_request.id)})
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
def reject_exchange(*, exchange_id, user, reason=""):
    exchange = load_exchange(exchange_id, for_update=True)
    role = viewer_role(exchange, user)
    if exchange.status == AgreementExchange.STATUS_DRAFT:
        raise PermissionError("The initial version has not been sent to the counterparty yet.")
    exchange.status = AgreementExchange.STATUS_REJECTED
    exchange.current_actor = AgreementExchange.ACTOR_NONE
    exchange.save(update_fields=["status", "current_actor", "updated_at"])
    message = reason or "Agreement Exchange was rejected."
    recipient_result = notify_initiator(exchange, message, {"exchange_id": str(exchange.id)}) if role == "counterparty" else notify_counterparty(exchange, message, {"exchange_id": str(exchange.id)})
    create_event(
        exchange,
        actor_user=user,
        actor_email=getattr(user, "email", "") or (exchange.counterparty_email if role == "counterparty" else ""),
        actor_role=role if role in {"initiator", "counterparty"} else "system",
        event_type="exchange_rejected",
        message=message,
        metadata={"reason": reason, "notification": recipient_result},
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
    notification = notify_initiator(exchange, f"{signer_email or 'A participant'} signed {exchange.contract.title or 'an agreement'}.", {"exchange_id": str(exchange.id), "signature_id": str(signature.id)}) if role == "counterparty" else notify_counterparty(exchange, "Agreement Exchange was signed.", {"exchange_id": str(exchange.id), "signature_id": str(signature.id)})
    create_event(
        exchange,
        actor_user=user,
        actor_email=signer_email,
        actor_role=role,
        event_type="signed",
        message="Agreement Exchange was signed using the Agreement Exchange MVP signature flow.",
        metadata={"signature_id": str(signature.id), "mvp_signature": True, "notification": notification},
    )
    return load_exchange(exchange.id), signature
