# backend/api/billing/views.py

from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.billing.models import Invoice, SubscriptionPlan, UserSubscription


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_plan(plan):
    return {
        "slug": plan.slug,
        "display_name": plan.display_name,
        "price_monthly": str(plan.price_monthly),
        "price_yearly": str(plan.price_yearly) if plan.price_yearly is not None else None,
        "max_active_contracts": plan.max_active_contracts,
        "max_live_sessions_per_month": plan.max_live_sessions_per_month,
        "has_lifecycle": plan.has_lifecycle,
        "has_notifications": plan.has_notifications,
        "has_negotiation_prep": plan.has_negotiation_prep,
        "all_templates": plan.all_templates,
        "excluded_categories": plan.excluded_categories,
        "templates_per_category": plan.templates_per_category,
        "ai_tier": plan.ai_tier,
        "has_priority_support": plan.has_priority_support,
        "has_early_access": plan.has_early_access,
    }


def _serialize_subscription(sub):
    return {
        "id": sub.id,
        "plan": _serialize_plan(sub.plan),
        "status": sub.status,
        "billing_period": sub.billing_period,
        "current_period_start": sub.current_period_start,
        "current_period_end": sub.current_period_end,
        "contracts_used_this_period": sub.contracts_used_this_period,
        "live_sessions_used_this_month": sub.live_sessions_used_this_month,
        "created_at": sub.created_at,
        "updated_at": sub.updated_at,
    }


def _serialize_invoice(inv):
    return {
        "id": inv.id,
        "amount": str(inv.amount),
        "currency": inv.currency,
        "status": inv.status,
        "description": inv.description,
        "created_at": inv.created_at,
        "paid_at": inv.paid_at,
    }


# ---------------------------------------------------------------------------
# GET /api/billing/plans/
# ---------------------------------------------------------------------------

class PlanListAPIView(APIView):
    """List all active subscription plans."""

    def get(self, request):
        plans = SubscriptionPlan.objects.filter(is_active=True)
        return Response([_serialize_plan(p) for p in plans])


# ---------------------------------------------------------------------------
# GET/POST/DELETE /api/billing/subscription/
# ---------------------------------------------------------------------------

class SubscriptionAPIView(APIView):
    """
    GET    — current user's subscription and usage stats
    POST   — create or change subscription plan
    DELETE — cancel subscription
    """

    def get(self, request):
        try:
            sub = UserSubscription.objects.select_related("plan").get(user=request.user)
        except UserSubscription.DoesNotExist:
            return Response({"subscription": None})
        return Response(_serialize_subscription(sub))

    def post(self, request):
        plan_slug = request.data.get("plan_slug", "").strip()
        billing_period = request.data.get("billing_period", "monthly").strip()

        if not plan_slug:
            return Response(
                {"error": "plan_slug is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        valid_periods = ["monthly", "yearly", "per_contract"]
        if billing_period not in valid_periods:
            return Response(
                {"error": f"billing_period must be one of: {', '.join(valid_periods)}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            plan = SubscriptionPlan.objects.get(slug=plan_slug, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            return Response({"error": "Plan not found."}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()

        try:
            sub = UserSubscription.objects.select_related("plan").get(user=request.user)
            sub.plan = plan
            sub.billing_period = billing_period
            sub.status = "per_contract" if plan.slug == "per_contract" else "active"
            sub.current_period_start = now
            sub.current_period_end = None
            sub.contracts_used_this_period = 0
            sub.live_sessions_used_this_month = 0
            sub.save()
        except UserSubscription.DoesNotExist:
            sub_status = "per_contract" if plan.slug == "per_contract" else "active"
            sub = UserSubscription.objects.create(
                user=request.user,
                plan=plan,
                status=sub_status,
                billing_period=billing_period,
                current_period_start=now,
            )

        return Response(_serialize_subscription(sub), status=status.HTTP_201_CREATED)

    def delete(self, request):
        try:
            sub = UserSubscription.objects.get(user=request.user)
        except UserSubscription.DoesNotExist:
            return Response(
                {"error": "No active subscription."},
                status=status.HTTP_404_NOT_FOUND,
            )
        sub.status = "cancelled"
        sub.save(update_fields=["status", "updated_at"])
        return Response({"status": "cancelled"})


# ---------------------------------------------------------------------------
# GET /api/billing/invoices/
# ---------------------------------------------------------------------------

class InvoiceListAPIView(APIView):
    """Paginated invoice list for the authenticated user."""

    PAGE_SIZE = 20

    def get(self, request):
        qs = Invoice.objects.filter(user=request.user).order_by("-created_at")
        try:
            page = max(1, int(request.query_params.get("page", 1)))
        except (ValueError, TypeError):
            page = 1

        total = qs.count()
        offset = (page - 1) * self.PAGE_SIZE
        invoices = qs[offset : offset + self.PAGE_SIZE]

        return Response({
            "count": total,
            "page": page,
            "page_size": self.PAGE_SIZE,
            "results": [_serialize_invoice(i) for i in invoices],
        })


# ---------------------------------------------------------------------------
# GET /api/billing/usage/
# ---------------------------------------------------------------------------

class UsageAPIView(APIView):
    """Current period usage stats."""

    def get(self, request):
        try:
            sub = UserSubscription.objects.select_related("plan").get(user=request.user)
        except UserSubscription.DoesNotExist:
            return Response({"subscription": None, "usage": None})

        plan = sub.plan
        return Response({
            "contracts_used": sub.contracts_used_this_period,
            "contracts_limit": plan.max_active_contracts,
            "sessions_used_this_month": sub.live_sessions_used_this_month,
            "sessions_limit_per_month": plan.max_live_sessions_per_month,
            "billing_period": sub.billing_period,
            "current_period_start": sub.current_period_start,
            "current_period_end": sub.current_period_end,
        })


# ---------------------------------------------------------------------------
# GET /api/billing/trial/
# ---------------------------------------------------------------------------

class TrialStatusAPIView(APIView):
    """Trial status and remaining contracts for the authenticated user."""

    def get(self, request):
        try:
            sub = UserSubscription.objects.select_related("plan").get(user=request.user)
        except UserSubscription.DoesNotExist:
            return Response({
                "is_trial": False,
                "trial_expired": False,
                "trial_contracts_remaining": 0,
                "plan": None,
                "status": None,
            })

        is_trial = sub.status == "trialing"
        trial_expired = sub.status == "no_subscription"

        return Response({
            "is_trial": is_trial,
            "trial_expired": trial_expired,
            "trial_contracts_remaining": sub.trial_contracts_remaining if is_trial else 0,
            "plan": sub.plan.slug,
            "status": sub.status,
        })
