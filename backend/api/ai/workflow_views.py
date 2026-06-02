from __future__ import annotations

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.ai.models import (
    CounterDraft,
    NegotiationComment,
    ReviewResult,
    WorkflowShareLink,
    WorkflowState,
)
from backend.api.contracts.permissions import contract_party_response, is_party
from backend.contracts.models import Contract, ContractVersion


PREPARED_CONTRACT_STATES = {
    "prepared",
    "ready",
    "ready_to_send",
    "ready_for_negotiation",
    "sent",
    "countered",
    "in_negotiation",
    "negotiating",
    "awaiting_signature",
}

NEGOTIATION_CONTRACT_STATUSES = {
    "sent",
}


def _display_name(user):
    if not user:
        return ""
    full_name = getattr(user, "get_full_name", lambda: "")()
    return full_name or getattr(user, "email", "") or getattr(user, "username", "")


def _workflow_completed_states():
    return [
        WorkflowState.STATE_UPLOADED,
        WorkflowState.STATE_VERSION_CREATED,
    ]


def _workflow_pending_states():
    return [
        WorkflowState.STATE_SENT_TO_COUNTERPARTY,
        WorkflowState.STATE_COUNTERPARTY_VIEWED,
        WorkflowState.STATE_COUNTERPARTY_REQUESTED_CHANGES,
        WorkflowState.STATE_ACCEPTED,
        WorkflowState.STATE_REJECTED,
        WorkflowState.STATE_SIGNED,
    ]


def _mark_workflow_version_created(workflow):
    now = timezone.now().isoformat()
    workflow.current_state = WorkflowState.STATE_VERSION_CREATED
    workflow.completed_states = _workflow_completed_states()
    workflow.pending_states = _workflow_pending_states()
    timestamps = dict(workflow.state_timestamps or {})
    timestamps.setdefault(WorkflowState.STATE_UPLOADED, now)
    timestamps.setdefault(WorkflowState.STATE_VERSION_CREATED, now)
    workflow.state_timestamps = timestamps
    return workflow


def _get_latest_contract_version(contract):
    return contract.versions.order_by("-version_number", "-created_at").first()


def _is_contract_negotiation_ready(contract):
    state = (contract.state or "").lower()
    status_value = (contract.status or "").lower()
    return state in PREPARED_CONTRACT_STATES or status_value in NEGOTIATION_CONTRACT_STATUSES


def _serialize_review_result(review):
    if not review:
        return None
    return {
        "id": str(review.id),
        "summary": review.summary,
        "identified_risks": review.identified_risks or [],
        "unclear_clauses": review.unclear_clauses or [],
        "negotiation_opportunities": review.negotiation_opportunities or [],
        "suggested_changes": review.suggested_changes or [],
        "key_terms": review.key_terms or {},
        "questions": review.questions or [],
        "ai_metadata": review.ai_metadata or {},
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "updated_at": review.updated_at.isoformat() if review.updated_at else None,
    }


def _serialize_counter_draft(counter_draft):
    return {
        "id": str(counter_draft.id),
        "status": counter_draft.status,
        "generated_revised_contract": counter_draft.generated_revised_contract,
        "selected_requested_changes": counter_draft.selected_requested_changes or [],
        "user_negotiation_instructions": counter_draft.user_negotiation_instructions,
        "summary": counter_draft.summary,
        "concerning_clauses": counter_draft.concerning_clauses or [],
        "negotiation_strategy": counter_draft.negotiation_strategy or {},
        "ai_metadata": counter_draft.ai_metadata or {},
        "approved_at": counter_draft.approved_at.isoformat() if counter_draft.approved_at else None,
        "created_version_id": str(counter_draft.created_version_id) if counter_draft.created_version_id else None,
        "created_at": counter_draft.created_at.isoformat() if counter_draft.created_at else None,
        "updated_at": counter_draft.updated_at.isoformat() if counter_draft.updated_at else None,
    }


def _serialize_last_activity(workflow):
    activity = None
    contract = workflow.contract
    if contract and hasattr(contract, "activity_log"):
        activity = contract.activity_log.order_by("-created_at").first()
    if not activity:
        return None
    return {
        "id": str(activity.id),
        "activity_type": activity.activity_type,
        "description": activity.description,
        "created_at": activity.created_at.isoformat() if activity.created_at else None,
    }


def _serialize_workflow(workflow):
    review = getattr(workflow, "review_result", None)
    return {
        "id": str(workflow.id),
        "contract_id": str(workflow.contract_id) if workflow.contract_id else None,
        "source_label": workflow.source_label,
        "current_state": workflow.current_state,
        "completed_states": workflow.completed_states or [],
        "pending_states": workflow.pending_states or [],
        "state_timestamps": workflow.state_timestamps or {},
        "created_version_id": str(workflow.created_version_id) if workflow.created_version_id else None,
        "sent_to_counterparty_email": workflow.sent_to_counterparty_email,
        "counterparty_email": workflow.counterparty_email,
        "counterparty_user_id": str(workflow.counterparty_user_id) if workflow.counterparty_user_id else None,
        "counterparty_requested_changes": workflow.counterparty_requested_changes or [],
        "last_activity": _serialize_last_activity(workflow),
        "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
        "updated_at": workflow.updated_at.isoformat() if workflow.updated_at else None,
        "review_result": _serialize_review_result(review),
        "counter_drafts": [
            _serialize_counter_draft(counter_draft)
            for counter_draft in workflow.counter_drafts.order_by("-created_at")
        ],
    }


def _serialize_comment(comment):
    author = comment.author
    return {
        "id": str(comment.id),
        "author_email": getattr(author, "email", "") if author else "",
        "author_name": _display_name(author),
        "comment_type": comment.comment_type,
        "clause_reference": comment.clause_reference,
        "body": comment.body,
        "created_at": comment.created_at.isoformat() if comment.created_at else None,
    }


def _serialize_active_version(version):
    if not version:
        return None
    return {
        "id": str(version.id),
        "version_number": version.version_number,
        "status": version.status,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }


def _serialize_invite_context(share_link):
    workflow = share_link.workflow
    version = workflow.created_version or _get_latest_contract_version(workflow.contract)
    initiator = workflow.user
    return {
        "token": str(share_link.token),
        "workflow_id": str(workflow.id),
        "source_label": workflow.source_label,
        "current_state": workflow.current_state,
        "counterparty_email": share_link.counterparty_email or workflow.counterparty_email,
        "initiator_name": _display_name(initiator),
        "active_version": _serialize_active_version(version),
    }


def _shared_workflow_allowed(user, workflow):
    if not user or not user.is_authenticated:
        return False
    email = getattr(user, "email", "")
    return (
        workflow.counterparty_user_id == user.pk
        or bool(email and email == workflow.counterparty_email)
        or bool(email and email == workflow.sent_to_counterparty_email)
    )


def _get_owner_workflow(user, workflow_id):
    return get_object_or_404(WorkflowState, id=workflow_id, user=user)


def _get_counterparty_workflow(user, workflow_id):
    workflow = get_object_or_404(WorkflowState, id=workflow_id)
    if not _shared_workflow_allowed(user, workflow):
        return None
    return workflow


def _workflow_urls(request, workflow):
    redirect_url = f"/workflows/{workflow.id}"
    api_url = reverse("ai-workflow-detail", kwargs={"workflow_id": workflow.id})
    return {
        "redirect_url": redirect_url,
        "api_url": request.build_absolute_uri(api_url) if request else api_url,
    }


def _get_or_create_workflow_for_contract(contract, user):
    if not _is_contract_negotiation_ready(contract):
        return None, False, Response(
            {"error": "Prepare the contract before opening negotiation."},
            status=status.HTTP_409_CONFLICT,
        )

    latest_version = _get_latest_contract_version(contract)
    if latest_version is None:
        return None, False, Response(
            {"error": "The prepared contract has no saved version to negotiate."},
            status=status.HTTP_409_CONFLICT,
        )

    if latest_version.version_number > contract.max_versions:
        return None, False, Response(
            {"error": "This contract has reached the maximum version limit."},
            status=status.HTTP_409_CONFLICT,
        )

    with transaction.atomic():
        Contract.objects.select_for_update().get(pk=contract.pk)
        workflow = (
            WorkflowState.objects.select_for_update()
            .filter(user=user, contract=contract, created_version=latest_version)
            .order_by("-updated_at")
            .first()
        )
        if workflow:
            return workflow, False, None

        workflow = WorkflowState(
            user=user,
            contract=contract,
            created_version=latest_version,
            source_label=contract.title or contract.description or "Prepared contract",
            counterparty_email=contract.counterparty_email or "",
            sent_to_counterparty_email="",
        )
        _mark_workflow_version_created(workflow)
        workflow.save()
        return workflow, True, None


class WorkflowListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        workflows = (
            WorkflowState.objects.filter(user=request.user)
            .select_related("contract", "created_version", "counterparty_user")
            .prefetch_related("counter_drafts")
            .order_by("-updated_at")
        )
        return Response({"results": [_serialize_workflow(workflow) for workflow in workflows]})

    def post(self, request):
        contract_id = request.data.get("contract_id")
        if contract_id:
            contract = get_object_or_404(Contract, pk=contract_id)
            if not is_party(request.user, contract):
                return contract_party_response()
            workflow, created, error_response = _get_or_create_workflow_for_contract(contract, request.user)
            if error_response:
                return error_response
            payload = _serialize_workflow(workflow)
            payload["created"] = created
            payload.update(_workflow_urls(request, workflow))
            return Response(payload, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

        workflow = WorkflowState(
            user=request.user,
            source_label=request.data.get("source_label") or "Agreement workflow",
            counterparty_email=request.data.get("counterparty_email") or "",
        ).initialize()
        workflow.save()
        return Response(_serialize_workflow(workflow), status=status.HTTP_201_CREATED)


class WorkflowForContractAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        contract_id = request.data.get("contract_id")
        if not contract_id:
            return Response({"error": "contract_id is required."}, status=status.HTTP_400_BAD_REQUEST)

        contract = get_object_or_404(Contract, pk=contract_id)
        if not is_party(request.user, contract):
            return contract_party_response()

        workflow, created, error_response = _get_or_create_workflow_for_contract(contract, request.user)
        if error_response:
            return error_response

        urls = _workflow_urls(request, workflow)
        return Response(
            {
                "workflow_id": str(workflow.id),
                "contract_id": str(contract.id),
                "created_version_id": str(workflow.created_version_id) if workflow.created_version_id else None,
                "created": created,
                "redirect_url": urls["redirect_url"],
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class WorkflowDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workflow_id):
        workflow = _get_owner_workflow(request.user, workflow_id)
        return Response(_serialize_workflow(workflow))


class WorkflowAdvanceAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workflow_id):
        workflow = _get_owner_workflow(request.user, workflow_id)
        next_state = request.data.get("state")
        if not next_state:
            return Response({"error": "state is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            workflow.advance_to(next_state)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        workflow.save(update_fields=["current_state", "completed_states", "pending_states", "state_timestamps", "updated_at"])
        return Response(_serialize_workflow(workflow))


class WorkflowSendAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workflow_id):
        workflow = _get_owner_workflow(request.user, workflow_id)
        email = request.data.get("counterparty_email") or workflow.counterparty_email
        if not email:
            return Response({"error": "counterparty_email is required."}, status=status.HTTP_400_BAD_REQUEST)

        workflow.counterparty_email = email
        workflow.sent_to_counterparty_email = email
        workflow.mark_state(
            WorkflowState.STATE_SENT_TO_COUNTERPARTY,
            completed_states=[
                WorkflowState.STATE_UPLOADED,
                WorkflowState.STATE_VERSION_CREATED,
                WorkflowState.STATE_SENT_TO_COUNTERPARTY,
            ],
            pending_states=[
                WorkflowState.STATE_COUNTERPARTY_VIEWED,
                WorkflowState.STATE_COUNTERPARTY_REQUESTED_CHANGES,
                WorkflowState.STATE_ACCEPTED,
                WorkflowState.STATE_REJECTED,
                WorkflowState.STATE_SIGNED,
            ],
        )
        workflow.save(
            update_fields=[
                "current_state",
                "completed_states",
                "pending_states",
                "state_timestamps",
                "counterparty_email",
                "sent_to_counterparty_email",
                "updated_at",
            ]
        )
        return Response(_serialize_workflow(workflow))


class WorkflowShareLinkCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workflow_id):
        workflow = _get_owner_workflow(request.user, workflow_id)
        email = request.data.get("counterparty_email") or workflow.counterparty_email
        if not email:
            return Response({"error": "counterparty_email is required."}, status=status.HTTP_400_BAD_REQUEST)

        workflow.counterparty_email = email
        workflow.sent_to_counterparty_email = email
        if workflow.current_state == WorkflowState.STATE_VERSION_CREATED:
            workflow.mark_state(
                WorkflowState.STATE_SENT_TO_COUNTERPARTY,
                completed_states=[
                    WorkflowState.STATE_UPLOADED,
                    WorkflowState.STATE_VERSION_CREATED,
                    WorkflowState.STATE_SENT_TO_COUNTERPARTY,
                ],
                pending_states=[
                    WorkflowState.STATE_COUNTERPARTY_VIEWED,
                    WorkflowState.STATE_COUNTERPARTY_REQUESTED_CHANGES,
                    WorkflowState.STATE_ACCEPTED,
                    WorkflowState.STATE_REJECTED,
                    WorkflowState.STATE_SIGNED,
                ],
            )
        workflow.save(
            update_fields=[
                "current_state",
                "completed_states",
                "pending_states",
                "state_timestamps",
                "counterparty_email",
                "sent_to_counterparty_email",
                "updated_at",
            ]
        )

        share_link = WorkflowShareLink.objects.create(
            workflow=workflow,
            counterparty_email=email,
            expires_at=WorkflowShareLink.default_expires_at(),
            created_by=request.user,
        )
        invite_path = reverse("ai-workflow-share-detail", kwargs={"token": share_link.token})
        invite_page = f"/workflow/invite/{share_link.token}"
        shared_page = f"/shared/workflows/{workflow.id}"
        return Response(
            {
                "invite_url": request.build_absolute_uri(invite_page),
                "api_invite_url": request.build_absolute_uri(invite_path),
                "shared_workflow_url": request.build_absolute_uri(shared_page),
                "counterparty_email": email,
                "email_sent": False,
            },
            status=status.HTTP_201_CREATED,
        )


class WorkflowShareLinkDetailAPIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        share_link = get_object_or_404(WorkflowShareLink.objects.select_related("workflow", "workflow__user"), token=token)
        if not share_link.is_active:
            return Response({"error": "This workflow invite is expired or revoked."}, status=status.HTTP_410_GONE)
        return Response(_serialize_invite_context(share_link))


class WorkflowShareLinkAcceptAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        share_link = get_object_or_404(WorkflowShareLink.objects.select_related("workflow"), token=token)
        if not share_link.is_active:
            return Response({"error": "This workflow invite is expired or revoked."}, status=status.HTTP_410_GONE)

        workflow = share_link.workflow
        expected_email = share_link.counterparty_email or workflow.counterparty_email
        if expected_email and expected_email != request.user.email:
            return Response({"error": "Sign in with the invited counterparty email to accept this workflow."}, status=status.HTTP_403_FORBIDDEN)

        workflow.counterparty_user = request.user
        workflow.counterparty_email = expected_email or request.user.email
        workflow.sent_to_counterparty_email = workflow.sent_to_counterparty_email or expected_email or request.user.email
        if workflow.current_state == WorkflowState.STATE_SENT_TO_COUNTERPARTY:
            workflow.mark_state(
                WorkflowState.STATE_COUNTERPARTY_VIEWED,
                completed_states=[
                    WorkflowState.STATE_UPLOADED,
                    WorkflowState.STATE_VERSION_CREATED,
                    WorkflowState.STATE_SENT_TO_COUNTERPARTY,
                    WorkflowState.STATE_COUNTERPARTY_VIEWED,
                ],
                pending_states=[
                    WorkflowState.STATE_COUNTERPARTY_REQUESTED_CHANGES,
                    WorkflowState.STATE_ACCEPTED,
                    WorkflowState.STATE_REJECTED,
                    WorkflowState.STATE_SIGNED,
                ],
            )
        workflow.save(
            update_fields=[
                "counterparty_user",
                "counterparty_email",
                "sent_to_counterparty_email",
                "current_state",
                "completed_states",
                "pending_states",
                "state_timestamps",
                "updated_at",
            ]
        )
        return Response({"workflow_id": str(workflow.id), "redirect_url": f"/shared/workflows/{workflow.id}"})


class WorkflowCommentsListCreateAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workflow_id):
        workflow = _get_owner_workflow(request.user, workflow_id)
        comments = workflow.negotiation_comments.select_related("author").order_by("created_at")
        return Response({"results": [_serialize_comment(comment) for comment in comments]})

    def post(self, request, workflow_id):
        workflow = _get_owner_workflow(request.user, workflow_id)
        body = (request.data.get("body") or "").strip()
        if not body:
            return Response({"error": "Comment body is required."}, status=status.HTTP_400_BAD_REQUEST)
        comment_type = request.data.get("comment_type") or NegotiationComment.COMMENT_TYPE_GENERAL
        valid_types = {choice[0] for choice in NegotiationComment.COMMENT_TYPE_CHOICES}
        if comment_type not in valid_types:
            return Response({"error": "Invalid comment_type."}, status=status.HTTP_400_BAD_REQUEST)
        comment = NegotiationComment.objects.create(
            workflow=workflow,
            version=workflow.created_version,
            author=request.user,
            comment_type=comment_type,
            clause_reference=request.data.get("clause_reference") or "",
            body=body,
        )
        return Response(_serialize_comment(comment), status=status.HTTP_201_CREATED)


class CounterpartyWorkflowDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, workflow_id):
        workflow = _get_counterparty_workflow(request.user, workflow_id)
        if not workflow:
            return Response({"error": "You do not have access to this workflow."}, status=status.HTTP_403_FORBIDDEN)
        return Response({"workflow": _serialize_workflow(workflow)})


class CounterpartyWorkflowActionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, workflow_id, action):
        workflow = _get_counterparty_workflow(request.user, workflow_id)
        if not workflow:
            return Response({"error": "You do not have access to this workflow."}, status=status.HTTP_403_FORBIDDEN)

        if action == "accept":
            workflow.mark_state(
                WorkflowState.STATE_ACCEPTED,
                completed_states=[
                    WorkflowState.STATE_UPLOADED,
                    WorkflowState.STATE_VERSION_CREATED,
                    WorkflowState.STATE_SENT_TO_COUNTERPARTY,
                    WorkflowState.STATE_COUNTERPARTY_VIEWED,
                    WorkflowState.STATE_ACCEPTED,
                ],
                pending_states=[WorkflowState.STATE_SIGNED],
            )
        elif action == "reject":
            workflow.mark_state(
                WorkflowState.STATE_REJECTED,
                completed_states=[
                    WorkflowState.STATE_UPLOADED,
                    WorkflowState.STATE_VERSION_CREATED,
                    WorkflowState.STATE_SENT_TO_COUNTERPARTY,
                    WorkflowState.STATE_COUNTERPARTY_VIEWED,
                    WorkflowState.STATE_REJECTED,
                ],
                pending_states=[],
            )
        elif action == "request-changes":
            requested_changes = request.data.get("requested_changes") or []
            if isinstance(requested_changes, str):
                requested_changes = [{"body": requested_changes}]
            workflow.counterparty_requested_changes = requested_changes
            workflow.mark_state(
                WorkflowState.STATE_COUNTERPARTY_REQUESTED_CHANGES,
                completed_states=[
                    WorkflowState.STATE_UPLOADED,
                    WorkflowState.STATE_VERSION_CREATED,
                    WorkflowState.STATE_SENT_TO_COUNTERPARTY,
                    WorkflowState.STATE_COUNTERPARTY_VIEWED,
                    WorkflowState.STATE_COUNTERPARTY_REQUESTED_CHANGES,
                ],
                pending_states=[
                    WorkflowState.STATE_ACCEPTED,
                    WorkflowState.STATE_REJECTED,
                    WorkflowState.STATE_SIGNED,
                ],
            )
        else:
            return Response({"error": "Unsupported workflow action."}, status=status.HTTP_400_BAD_REQUEST)

        workflow.save(
            update_fields=[
                "current_state",
                "completed_states",
                "pending_states",
                "state_timestamps",
                "counterparty_requested_changes",
                "updated_at",
            ]
        )
        return Response({"workflow": _serialize_workflow(workflow)})


class CounterDraftApproveAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, draft_id):
        counter_draft = get_object_or_404(CounterDraft.objects.select_related("workflow", "workflow__contract"), id=draft_id)
        workflow = counter_draft.workflow
        if workflow.user_id != request.user.pk:
            return Response({"error": "You do not have access to this counter draft."}, status=status.HTTP_403_FORBIDDEN)
        if counter_draft.status == CounterDraft.STATUS_APPROVED:
            return Response(_serialize_counter_draft(counter_draft))
        if not workflow.contract:
            return Response({"error": "Counter draft is not linked to a contract."}, status=status.HTTP_409_CONFLICT)
        if workflow.contract.versions.count() >= workflow.contract.max_versions:
            return Response({"error": "This contract has reached the maximum version limit."}, status=status.HTTP_409_CONFLICT)

        latest_version = _get_latest_contract_version(workflow.contract)
        new_version = ContractVersion.objects.create(
            contract=workflow.contract,
            version_number=(latest_version.version_number + 1) if latest_version else 1,
            created_by=request.user,
            previous_version=latest_version,
            status="draft",
            content_snapshot=counter_draft.generated_revised_contract or "",
        )
        counter_draft.status = CounterDraft.STATUS_APPROVED
        counter_draft.approved_at = timezone.now()
        counter_draft.created_version = new_version
        counter_draft.save(update_fields=["status", "approved_at", "created_version", "updated_at"])
        workflow.created_version = new_version
        workflow.mark_state(
            WorkflowState.STATE_VERSION_CREATED,
            completed_states=_workflow_completed_states(),
            pending_states=_workflow_pending_states(),
        )
        workflow.save(update_fields=["created_version", "current_state", "completed_states", "pending_states", "state_timestamps", "updated_at"])
        return Response(_serialize_counter_draft(counter_draft))
