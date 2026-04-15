# backend/api/admin_views.py
#
# Internal admin API endpoints.
# All views require is_staff=True (IsAdminUser).
# Structured so permission can be swapped to a custom role check later.

from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.activity.models import ContractActivity
from backend.billing.models import SubscriptionPlan, UserSubscription
from backend.contracts.models import Contract
from backend.sol.models import Sol
from backend.users.models import BusinessEntity

User = get_user_model()

_PAGE_SIZE = 50


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
    permission_classes = [IsAdminUser]

    def get(self, request):
        return Response({
            "users": User.objects.count(),
            "plans": SubscriptionPlan.objects.filter(is_active=True).count(),
            "subscriptions": UserSubscription.objects.count(),
            "sol_groups": Sol.objects.count(),
            "entities": BusinessEntity.objects.filter(is_active=True).count(),
            "contracts": Contract.objects.count(),
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
    permission_classes = [IsAdminUser]

    def get(self, request):
        q = request.query_params.get("q", "").strip()
        qs = (
            User.objects
            .select_related("subscription__plan", "bon_profile")
            .order_by("-date_joined")
        )
        if q:
            from django.db.models import Q
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
    permission_classes = [IsAdminUser]

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
        contract_count = Contract.objects.filter(initiator=u).count()

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
            "contract_count": contract_count,
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
    permission_classes = [IsAdminUser]

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
    permission_classes = [IsAdminUser]

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
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = BusinessEntity.objects.select_related("owner").order_by("-created_at")
        return _paginate(qs, request, _serialize_entity)


# ---------------------------------------------------------------------------
# GET /api/admin/contracts/
# ---------------------------------------------------------------------------

def _serialize_contract(c):
    return {
        "id": str(c.id),
        "title": c.title or "(untitled)",
        "initiator_id": c.initiator_id,
        "counterparty_email": c.counterparty_email,
        "entity_type": c.entity_type,
        "status": c.status,
        "created_at": c.created_at,
    }


class AdminContractListView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = Contract.objects.select_related("initiator").order_by("-created_at")
        status_filter = request.query_params.get("status", "").strip()
        if status_filter:
            qs = qs.filter(status=status_filter)
        return _paginate(qs, request, _serialize_contract)


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
    permission_classes = [IsAdminUser]

    def get(self, request):
        qs = ContractActivity.objects.order_by("-created_at")
        activity_type = request.query_params.get("activity_type", "").strip()
        if activity_type:
            qs = qs.filter(activity_type=activity_type)
        return _paginate(qs, request, _serialize_activity)
