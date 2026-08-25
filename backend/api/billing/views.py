# backend/api/billing/views.py

import logging

from django.conf import settings
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.authentication import BasicAuthentication
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from backend.billing.models import Invoice, SubscriptionPlan, UserSubscription
from backend.billing.gates import get_effective_blackbod_tier, is_trial_valid
from backend.billing.stripe_client import stripe_configured

logger = logging.getLogger(__name__)


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
        "trial_start": sub.trial_start,
        "trial_end": sub.trial_end,
        "is_trial_valid": is_trial_valid(sub),
        "effective_blackbod_tier": get_effective_blackbod_tier(sub.user),
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
    POST   — create or change subscription plan (dev/test only when Stripe not configured)
    DELETE — cancel subscription
    """

    def get(self, request):
        try:
            sub = UserSubscription.objects.select_related("plan").get(user=request.user)
        except UserSubscription.DoesNotExist:
            return Response({"subscription": None})
        return Response(_serialize_subscription(sub))

    def post(self, request):
        # When Stripe is configured, direct DB plan changes are disabled.
        # Clients should use POST /api/billing/checkout/ instead.
        if stripe_configured():
            return Response(
                {
                    "error": "Direct plan changes are disabled. Use POST /api/billing/checkout/ to start a Stripe Checkout session.",
                    "checkout_url": "/api/billing/checkout/",
                },
                status=status.HTTP_403_FORBIDDEN,
            )

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
        trial_valid = is_trial_valid(sub)
        trial_expired = (is_trial and not trial_valid) or sub.status == "no_subscription"

        return Response({
            "is_trial": is_trial,
            "trial_expired": trial_expired,
            "trial_contracts_remaining": sub.trial_contracts_remaining if is_trial else 0,
            "trial_start": sub.trial_start,
            "trial_end": sub.trial_end,
            "is_trial_valid": trial_valid,
            "effective_blackbod_tier": get_effective_blackbod_tier(request.user),
            "plan": sub.plan.slug,
            "status": sub.status,
        })


# ---------------------------------------------------------------------------
# POST /api/billing/checkout/
# ---------------------------------------------------------------------------

class CheckoutSessionAPIView(APIView):
    """
    Create a Stripe Checkout Session for a new or upgraded subscription.

    Required body fields:
      plan_slug    — one of: starter, professional, business, anchor
      success_url  — absolute URL Stripe redirects to on success
      cancel_url   — absolute URL Stripe redirects to on cancel
    """

    def post(self, request):
        if not stripe_configured():
            return Response(
                {"error": "Stripe is not configured. Set STRIPE_SECRET_KEY in the environment."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        from backend.billing.services import CHECKOUT_ALLOWED_PLANS, create_checkout_session
        import stripe as _stripe

        plan_slug = request.data.get("plan_slug", "").strip()
        success_url = request.data.get("success_url", "").strip()
        cancel_url = request.data.get("cancel_url", "").strip()

        if not plan_slug:
            return Response({"error": "plan_slug is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not success_url or not cancel_url:
            return Response(
                {"error": "success_url and cancel_url are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if plan_slug not in CHECKOUT_ALLOWED_PLANS:
            return Response(
                {"error": f"plan_slug must be one of: {', '.join(sorted(CHECKOUT_ALLOWED_PLANS))}."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            session = create_checkout_session(
                user=request.user,
                plan_slug=plan_slug,
                success_url=success_url,
                cancel_url=cancel_url,
            )
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except _stripe.error.StripeError as exc:
            logger.error("Stripe error creating checkout session: %s", exc)
            return Response(
                {"error": "Payment provider error. Please try again later."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"checkout_url": session["url"]}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# POST /api/billing/portal/
# ---------------------------------------------------------------------------

class BillingPortalAPIView(APIView):
    """
    Create a Stripe Billing Portal Session so the user can manage or cancel
    their subscription.

    Required body field:
      return_url — absolute URL to redirect back to after the portal session
    """

    def post(self, request):
        if not stripe_configured():
            return Response(
                {"error": "Stripe is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        from backend.billing.services import create_portal_session
        import stripe as _stripe

        return_url = request.data.get("return_url", "").strip()
        if not return_url:
            return Response({"error": "return_url is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            session = create_portal_session(user=request.user, return_url=return_url)
        except ValueError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        except _stripe.error.StripeError as exc:
            logger.error("Stripe error creating portal session: %s", exc)
            return Response(
                {"error": "Payment provider error. Please try again later."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({"portal_url": session["url"]}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# POST /api/billing/webhook/
# ---------------------------------------------------------------------------

class WebhookAPIView(APIView):
    """
    Stripe webhook endpoint.

    Authentication is intentionally bypassed — Stripe signs the payload with
    STRIPE_WEBHOOK_SECRET and we verify the signature before processing.
    CSRF is also bypassed because Stripe sends raw POST bodies.
    """

    authentication_classes = []
    permission_classes = [AllowAny]

    @csrf_exempt
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        import stripe as _stripe
        from backend.billing import services

        webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
        payload = request.body
        sig_header = request.META.get("HTTP_STRIPE_SIGNATURE", "")

        if not webhook_secret:
            logger.error("Webhook received but STRIPE_WEBHOOK_SECRET is not configured.")
            return Response(
                {"error": "Webhook secret is not configured."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        stripe_mod = services.get_stripe()
        try:
            event = stripe_mod.Webhook.construct_event(payload, sig_header, webhook_secret)
        except ValueError:
            return Response({"error": "Invalid payload."}, status=status.HTTP_400_BAD_REQUEST)
        except _stripe.error.SignatureVerificationError:
            return Response({"error": "Invalid signature."}, status=status.HTTP_400_BAD_REQUEST)

        event_type = event.get("type", "")
        data_object = (event.get("data") or {}).get("object") or {}

        _HANDLERS = {
            "checkout.session.completed":       services.handle_checkout_completed,
            "customer.subscription.updated":    services.handle_subscription_updated,
            "customer.subscription.deleted":    services.handle_subscription_deleted,
            "invoice.paid":                     services.handle_invoice_paid,
            "invoice.payment_failed":           services.handle_invoice_payment_failed,
        }

        handler = _HANDLERS.get(event_type)
        if handler:
            try:
                handler(data_object)
            except Exception as exc:
                logger.exception("Webhook handler error for %s: %s", event_type, exc)
                # Return 200 to prevent Stripe from retrying for application errors
        else:
            logger.debug("Unhandled Stripe event: %s", event_type)

        return Response({"received": True})
