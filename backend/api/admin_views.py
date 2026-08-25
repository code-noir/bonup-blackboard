# backend/api/admin_views.py
#
# Internal admin API endpoints.
# All views require an operator-scoped JWT.

import re

from django.contrib.auth import get_user_model
from django.db.models import Max, Q
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.activity.models import ContractActivity
from backend.api.operator.permissions import IsOperator
from backend.api.contracts.services.visibility_service import can_user_see_contract_on_dashboard
from backend.billing.models import SubscriptionPlan, UserSubscription
from backend.contracts.models import Contract, ContractObligation, ContractServiceObligation
from backend.sol.models import Sol
from backend.users.models import BusinessEntity

User = get_user_model()

_PAGE_SIZE = 50


def _display_name(user):
    if user is None:
        return "-"
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return full_name or user.email or "Unknown user"


def _compact_text(value, max_length=96):
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    sentence_endings = [idx for idx in [text.find("."), text.find(";")] if idx >= 0]
    sentence_end = min(sentence_endings) if sentence_endings else -1
    if sentence_end > 0 and sentence_end <= max_length:
        text = text[:sentence_end + 1]
    if len(text) <= max_length:
        return text
    return text[:max_length - 1].rstrip() + "..."


def _operator_obligation_label(value):
    text = " ".join(str(value or "").split())
    if not text:
        return ""
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    candidate = text
    for marker in (
        "Service Provider",
        "Contractor",
        "Provider",
        "Client",
        "Customer",
        "Buyer",
        "Seller",
    ):
        index = candidate.find(marker)
        if index > 8:
            candidate = candidate[:index]
            break
    candidate = candidate.strip(" -:.;")
    if candidate.isupper():
        candidate = candidate.title()
    unsafe_terms = (
        "agreement",
        "scope of services",
        "{{",
        "}}",
        "between",
        "agrees to",
        "whereas",
    )
    lowered = candidate.lower()
    if any(term in lowered for term in unsafe_terms):
        return ""
    if len(candidate) > 64 or len(candidate.split()) > 7:
        return ""
    if candidate and not candidate[0].isupper():
        return ""
    return candidate


def _bon_id(user):
    if user is None:
        return None
    try:
        return user.bon_profile.bon_id
    except Exception:
        return None


def _contract_party_q(user):
    return Q(initiator=user) | Q(counterparty_email=user.email)


def _obligation_party_q(user):
    return Q(contract__initiator=user) | Q(contract__counterparty_email=user.email)


def _participant_contracts_for_user(user):
    return (
        Contract.objects
        .filter(_contract_party_q(user))
        .select_related("initiator", "initiator__bon_profile")
        .prefetch_related("agreement_exchanges")
        .distinct()
    )


def _accessible_contracts_for_user(user):
    return [
        contract
        for contract in _participant_contracts_for_user(user)
        if can_user_see_contract_on_dashboard(contract, user)
    ]


def _agreement_role(contract, user):
    if contract.initiator_id == user.id:
        return "Initiator"
    if (contract.counterparty_email or "").strip().lower() == (user.email or "").strip().lower():
        return "Counterparty"
    return "Participant"


def _contract_obligation_count(contract):
    return (
        ContractObligation.objects.filter(contract=contract).count()
        + ContractServiceObligation.objects.filter(contract=contract).count()
    )


def _contract_last_activity_at(contract):
    return ContractActivity.objects.filter(contract=contract).aggregate(last_activity=Max("created_at"))["last_activity"]


def _agreement_metrics_for_user(user):
    participant_contracts = list(_participant_contracts_for_user(user))
    accessible_contracts = [
        contract
        for contract in participant_contracts
        if can_user_see_contract_on_dashboard(contract, user)
    ]
    return {
        "agreements_created": Contract.objects.filter(initiator=user).count(),
        "agreements_participating": len(participant_contracts),
        "agreements_accessible": len(accessible_contracts),
        "signed_agreements": sum(1 for contract in accessible_contracts if contract.status == "signed"),
        "draft_agreements": sum(1 for contract in accessible_contracts if contract.status == "draft"),
        "archived_agreements": sum(1 for contract in accessible_contracts if contract.status == "archived"),
    }


def _obligation_querysets_for_user(user):
    party_q = _obligation_party_q(user)
    return (
        ContractObligation.objects.filter(party_q),
        ContractServiceObligation.objects.filter(party_q),
    )


def _obligation_metrics_for_user(user):
    payment_qs, service_qs = _obligation_querysets_for_user(user)
    open_payment_qs = payment_qs.exclude(state="resolved")
    open_service_qs = service_qs.exclude(state="resolved")
    return {
        "open_obligations": open_payment_qs.count() + open_service_qs.count(),
        "resolved_obligations": payment_qs.filter(state="resolved").count() + service_qs.filter(state="resolved").count(),
        "completed_obligations": payment_qs.filter(state="resolved").count() + service_qs.filter(state="resolved").count(),
        "assigned_open_obligations": (
            open_payment_qs.filter(obligor=user).count()
            + open_service_qs.filter(obligor=user).count()
        ),
        "payment_obligations": payment_qs.count(),
        "service_obligations": service_qs.count(),
        "overdue_obligations": payment_qs.filter(state="overdue").count() + service_qs.filter(state="overdue").count(),
    }


def _serialize_admin_agreement(contract, user=None):
    initiator = contract.initiator
    role = _agreement_role(contract, user) if user is not None else None
    return {
        "id": str(contract.id),
        "title": contract.title or "Untitled agreement",
        "role": role,
        "status": contract.status,
        "initiator_name": _display_name(initiator),
        "initiator_email": initiator.email if initiator else None,
        "initiator_bon_id": _bon_id(initiator),
        "counterparty": contract.counterparty_name or contract.counterparty_email or "-",
        "counterparty_email": contract.counterparty_email,
        "entity_type": contract.entity_type,
        "obligation_count": _contract_obligation_count(contract),
        "last_activity_at": _contract_last_activity_at(contract),
        "created_at": contract.created_at,
    }


def _serialize_admin_obligation(obligation, obligation_type):
    contract = obligation.contract
    obligor = obligation.obligor
    title = "Payment obligation" if obligation_type == "payment" else "Service obligation"
    return {
        "id": str(obligation.id),
        "agreement_id": str(contract.id),
        "agreement_title": contract.title or "Untitled agreement",
        "agreement_status": contract.status,
        "counterparty": contract.counterparty_name or contract.counterparty_email or "-",
        "obligation": title,
        "type": obligation_type,
        "assigned_user": _display_name(obligor),
        "assigned_user_email": obligor.email if obligor else None,
        "due_date": obligation.due_date,
        "completion_date": getattr(obligation, "completed_at", None),
        "status": obligation.state,
        "created_at": obligation.created_at,
        "last_updated": obligation.updated_at,
        "internal_reference": str(obligation.id),
    }


def _admin_obligations_queryset():
    payment_items = [
        _serialize_admin_obligation(obligation, "payment")
        for obligation in ContractObligation.objects.select_related("contract", "obligor").all()
    ]
    service_items = [
        _serialize_admin_obligation(obligation, "service")
        for obligation in ContractServiceObligation.objects.select_related("contract", "obligor").all()
    ]
    return sorted(
        payment_items + service_items,
        key=lambda item: (item["due_date"] is None, item["due_date"]),
    )


def _paginate_list(items, request):
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    total = len(items)
    offset = (page - 1) * _PAGE_SIZE
    return Response({
        "count": total,
        "page": page,
        "page_size": _PAGE_SIZE,
        "results": items[offset: offset + _PAGE_SIZE],
    })


def _paginate(qs, request, serialize_fn):
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (ValueError, TypeError):
        page = 1
    total = qs.count()
    offset = (page - 1) * _PAGE_SIZE
    results = [serialize_fn(obj) for obj in qs[offset: offset + _PAGE_SIZE]]
    return Response({
        "count": total,
        "page": page,
        "page_size": _PAGE_SIZE,
        "results": results,
    })


# ---------------------------------------------------------------------------
# GET /api/admin/summary/
# ---------------------------------------------------------------------------

class AdminSummaryView(APIView):
    permission_classes = [IsOperator]

    def get(self, request):
        return Response({
            "users": User.objects.count(),
            "plans": SubscriptionPlan.objects.filter(is_active=True).count(),
            "subscriptions": UserSubscription.objects.count(),
            "sol_groups": Sol.objects.count(),
            "entities": BusinessEntity.objects.filter(is_active=True).count(),
            "contracts": Contract.objects.count(),
            "obligations": ContractObligation.objects.count() + ContractServiceObligation.objects.count(),
            "activity_events": ContractActivity.objects.count(),
        })


# ---------------------------------------------------------------------------
# GET /api/admin/users/
# ---------------------------------------------------------------------------

def _serialize_user(u):
    try:
        sub = u.subscription
        plan_slug = sub.plan.slug
        plan_display = sub.plan.display_name
        sub_status = sub.status
    except Exception:
        plan_slug = None
        plan_display = None
        sub_status = None

    try:
        bon_id = u.bon_profile.bon_id
    except Exception:
        bon_id = None

    biz_count = BusinessEntity.objects.filter(owner=u, is_active=True).count()

    return {
        "id": u.id,
        "email": u.email,
        "first_name": u.first_name,
        "last_name": u.last_name,
        "is_staff": u.is_staff,
        "date_joined": u.date_joined,
        "bon_id": bon_id,
        "plan": plan_slug,
        "plan_display": plan_display,
        "subscription_status": sub_status,
        "business_count": biz_count,
    }


class AdminUserListView(APIView):
    permission_classes = [IsOperator]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        qs = (
            User.objects
            .select_related("subscription__plan", "bon_profile")
            .order_by("-date_joined")
        )
        if q:
            qs = qs.filter(
                Q(email__icontains=q) |
                Q(first_name__icontains=q) | Q(last_name__icontains=q) |
                Q(bon_profile__bon_id__icontains=q)
            )
        return _paginate(qs, request, _serialize_user)


# ---------------------------------------------------------------------------
# GET /api/admin/users/<pk>/
# ---------------------------------------------------------------------------

class AdminUserDetailView(APIView):
    permission_classes = [IsOperator]

    def get(self, request, pk):
        u = get_object_or_404(
            User.objects.select_related("subscription__plan", "bon_profile"),
            pk=pk,
        )

        try:
            sub = u.subscription
            plan_slug = sub.plan.slug
            plan_display = sub.plan.display_name
            sub_status = sub.status
            is_trialing = sub.status == "trialing"
            trial_remaining = sub.trial_contracts_remaining if is_trialing else None
        except Exception:
            plan_slug = None
            plan_display = None
            sub_status = None
            is_trialing = False
            trial_remaining = None

        try:
            bon_id = u.bon_profile.bon_id
        except Exception:
            bon_id = None

        biz_count = BusinessEntity.objects.filter(owner=u, is_active=True).count()
        agreement_metrics = _agreement_metrics_for_user(u)
        obligation_metrics = _obligation_metrics_for_user(u)
        user_agreements = sorted(
            _accessible_contracts_for_user(u),
            key=lambda contract: contract.created_at,
            reverse=True,
        )[:50]
        payment_qs, service_qs = _obligation_querysets_for_user(u)
        user_obligations = sorted(
            [
                _serialize_admin_obligation(obligation, "payment")
                for obligation in payment_qs.select_related("contract", "obligor")
            ]
            + [
                _serialize_admin_obligation(obligation, "service")
                for obligation in service_qs.select_related("contract", "obligor")
            ],
            key=lambda item: (item["due_date"] is None, item["due_date"]),
        )[:50]

        return Response({
            "id": u.id,
            "email": u.email,
            "first_name": u.first_name,
            "last_name": u.last_name,
            "is_staff": u.is_staff,
            "date_joined": u.date_joined,
            "bon_id": bon_id,
            "plan": plan_slug,
            "plan_display": plan_display,
            "subscription_status": sub_status,
            "is_trialing": is_trialing,
            "trial_remaining": trial_remaining,
            "business_count": biz_count,
            "contract_count": agreement_metrics["agreements_created"],
            **agreement_metrics,
            **obligation_metrics,
            "agreements": [_serialize_admin_agreement(contract, u) for contract in user_agreements],
            "obligations": user_obligations,
        })


# ---------------------------------------------------------------------------
# GET /api/admin/subscriptions/
# ---------------------------------------------------------------------------

def _serialize_sub(sub):
    return {
        "id": sub.id,
        "user_id": sub.user_id,
        "plan": sub.plan.slug,
        "plan_display": sub.plan.display_name,
        "status": sub.status,
        "billing_period": sub.billing_period,
        "contracts_used": sub.contracts_used_this_period,
        "sessions_used": sub.live_sessions_used_this_month,
        "is_trialing": sub.status == "trialing",
        "trial_remaining": sub.trial_contracts_remaining,
        "current_period_start": sub.current_period_start,
        "stripe_customer_id": sub.stripe_customer_id or None,
    }


class AdminSubscriptionListView(APIView):
    permission_classes = [IsOperator]

    def get(self, request):
        qs = (
            UserSubscription.objects
            .select_related("user", "plan")
            .order_by("-updated_at")
        )
        status_filter = request.query_params.get("status", "").strip()
        if status_filter:
            qs = qs.filter(status=status_filter)
        return _paginate(qs, request, _serialize_sub)


# ---------------------------------------------------------------------------
# GET /api/admin/sol/
# ---------------------------------------------------------------------------

def _serialize_sol(sol):
    return {
        "id": str(sol.id),
        "sol_id": sol.sol_id,
        "name": sol.name,
        "status": sol.status,
        "sol_type": sol.sol_type,
        "frequency": sol.frequency,
        "contribution_amount": str(sol.contribution_amount),
        "currency": sol.currency,
        "active_member_count": sol.active_member_count(),
        "primary_manager_id": sol.primary_manager_id,
        "is_private": sol.is_private,
        "created_at": sol.created_at,
    }


class AdminSolListView(APIView):
    permission_classes = [IsOperator]

    def get(self, request):
        qs = Sol.objects.order_by("-created_at")
        return _paginate(qs, request, _serialize_sol)


# ---------------------------------------------------------------------------
# GET /api/admin/entities/
# ---------------------------------------------------------------------------

def _serialize_entity(e):
    return {
        "id": str(e.id),
        "name": e.name,
        "owner_id": e.owner_id,
        "business_type": e.business_type,
        "industry": e.industry,
        "is_active": e.is_active,
        "created_at": e.created_at,
    }


class AdminEntityListView(APIView):
    permission_classes = [IsOperator]

    def get(self, request):
        qs = BusinessEntity.objects.select_related("owner").order_by("-created_at")
        return _paginate(qs, request, _serialize_entity)


# ---------------------------------------------------------------------------
# GET /api/admin/contracts/
# ---------------------------------------------------------------------------

def _serialize_contract(c):
    return _serialize_admin_agreement(c)


class AdminContractListView(APIView):
    permission_classes = [IsOperator]

    def get(self, request):
        qs = Contract.objects.select_related("initiator", "initiator__bon_profile").order_by("-created_at")
        status_filter = request.query_params.get("status", "").strip()
        if status_filter:
            qs = qs.filter(status=status_filter)
        return _paginate(qs, request, _serialize_contract)



# ---------------------------------------------------------------------------
# GET /api/admin/obligations/
# ---------------------------------------------------------------------------

class AdminObligationListView(APIView):
    permission_classes = [IsOperator]

    def get(self, request):
        obligation_type = request.query_params.get("type", "").strip()
        state_filter = request.query_params.get("state", "").strip()
        items = _admin_obligations_queryset()
        if obligation_type in {"payment", "service"}:
            items = [item for item in items if item["type"] == obligation_type]
        if state_filter:
            items = [item for item in items if item["status"] == state_filter]
        return _paginate_list(items, request)

# ---------------------------------------------------------------------------
# GET /api/admin/activity/
# ---------------------------------------------------------------------------

def _serialize_activity(a):
    return {
        "id": str(a.id),
        "contract_id": str(a.contract_id),
        "user_id": a.user_id,
        "activity_type": a.activity_type,
        "description": a.description,
        "created_at": a.created_at,
    }


class AdminActivityListView(APIView):
    permission_classes = [IsOperator]

    def get(self, request):
        qs = ContractActivity.objects.order_by("-created_at")
        activity_type = request.query_params.get("activity_type", "").strip()
        if activity_type:
            qs = qs.filter(activity_type=activity_type)
        return _paginate(qs, request, _serialize_activity)
