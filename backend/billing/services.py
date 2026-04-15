# backend/billing/services.py
#
# Stripe integration service layer.
#
# Responsibilities:
#   - Create Stripe Checkout Sessions (new subscription)
#   - Create Stripe Billing Portal Sessions (manage / cancel)
#   - Handle incoming webhooks dispatched from the API layer
#   - Keep UserSubscription and Invoice records in sync with Stripe
#
# All functions that touch Stripe are only reachable when STRIPE_SECRET_KEY is
# set.  The stripe_configured() guard is enforced at the view layer; these
# functions assume the caller has already checked.

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Invoice, SubscriptionPlan, UserSubscription
from .stripe_client import get_stripe

logger = logging.getLogger(__name__)

# Plans that can be purchased through Stripe Checkout.
# trial, sol_member, and per_contract are not self-serve Checkout plans.
CHECKOUT_ALLOWED_PLANS = {"starter", "professional", "business", "anchor"}

# Map Stripe subscription status → local UserSubscription.status
_STRIPE_TO_LOCAL_STATUS = {
    "active":   "active",
    "trialing": "trialing",
    "past_due": "past_due",
    "canceled": "cancelled",
    "unpaid":   "past_due",
    "incomplete": "past_due",
    "incomplete_expired": "cancelled",
    "paused":   "past_due",
}


# ---------------------------------------------------------------------------
# Customer helpers
# ---------------------------------------------------------------------------

def get_or_create_stripe_customer(user):
    """
    Return the Stripe customer_id for this user, creating one in Stripe if
    the user does not yet have one stored locally.
    """
    stripe = get_stripe()

    try:
        sub = UserSubscription.objects.get(user=user)
        if sub.stripe_customer_id:
            return sub.stripe_customer_id
    except UserSubscription.DoesNotExist:
        sub = None

    # Create a new Stripe customer
    customer = stripe.Customer.create(
        email=user.email,
        metadata={"bonup_user_id": str(user.id)},
    )
    customer_id = customer["id"]

    if sub is not None:
        UserSubscription.objects.filter(user=user).update(stripe_customer_id=customer_id)
    # If there is no local sub yet, the customer_id will be stored when the
    # webhook fires after checkout completion.

    return customer_id


# ---------------------------------------------------------------------------
# Checkout / Portal sessions
# ---------------------------------------------------------------------------

def create_checkout_session(user, plan_slug, success_url, cancel_url):
    """
    Create a Stripe Checkout Session for a new or upgraded subscription.

    Returns the Stripe Session object (dict-like).
    Raises ValueError for invalid plan slugs.
    Raises stripe.error.StripeError for Stripe-side failures.
    """
    if plan_slug not in CHECKOUT_ALLOWED_PLANS:
        raise ValueError(f"Plan '{plan_slug}' is not available via Checkout.")

    price_ids = getattr(settings, "STRIPE_PRICE_IDS", {})
    price_id = price_ids.get(plan_slug, "")
    if not price_id:
        raise ValueError(
            f"No Stripe price ID configured for plan '{plan_slug}'. "
            "Set STRIPE_PRICE_ID_* in your environment."
        )

    stripe = get_stripe()
    customer_id = get_or_create_stripe_customer(user)

    session = stripe.checkout.Session.create(
        customer=customer_id,
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "bonup_user_id": str(user.id),
            "plan_slug": plan_slug,
        },
        subscription_data={
            "metadata": {
                "bonup_user_id": str(user.id),
                "plan_slug": plan_slug,
            }
        },
    )
    return session


def create_portal_session(user, return_url):
    """
    Create a Stripe Billing Portal Session so the user can manage or cancel
    their subscription directly in Stripe's hosted UI.

    Returns the Stripe Session object.
    Raises ValueError if the user has no Stripe customer ID.
    """
    stripe = get_stripe()

    try:
        sub = UserSubscription.objects.get(user=user)
        customer_id = sub.stripe_customer_id
    except UserSubscription.DoesNotExist:
        customer_id = None

    if not customer_id:
        raise ValueError("No Stripe customer found for this user.")

    session = stripe.billing_portal.Session.create(
        customer=customer_id,
        return_url=return_url,
    )
    return session


# ---------------------------------------------------------------------------
# Webhook handlers
# ---------------------------------------------------------------------------

def handle_checkout_completed(session):
    """
    Fired when a Stripe Checkout Session completes successfully.
    Sync the resulting subscription to our local DB.
    """
    metadata = session.get("metadata") or {}
    bonup_user_id = metadata.get("bonup_user_id")
    plan_slug = metadata.get("plan_slug")

    if not bonup_user_id or not plan_slug:
        logger.warning("checkout.session.completed missing metadata: %s", session.get("id"))
        return

    stripe_subscription_id = session.get("subscription")
    stripe_customer_id = session.get("customer")

    stripe = get_stripe()
    try:
        stripe_sub = stripe.Subscription.retrieve(stripe_subscription_id)
    except Exception as exc:
        logger.error("Failed to retrieve Stripe subscription %s: %s", stripe_subscription_id, exc)
        return

    _sync_subscription_from_stripe(
        bonup_user_id=bonup_user_id,
        plan_slug=plan_slug,
        stripe_sub=stripe_sub,
        stripe_customer_id=stripe_customer_id,
    )


def handle_subscription_updated(stripe_sub):
    """
    Fired when a Stripe subscription is updated (plan change, renewal, etc.).
    Updates local status and period dates.
    """
    metadata = stripe_sub.get("metadata") or {}
    bonup_user_id = metadata.get("bonup_user_id")
    plan_slug = metadata.get("plan_slug")

    if not bonup_user_id:
        logger.warning("customer.subscription.updated missing bonup_user_id: %s", stripe_sub.get("id"))
        return

    # If plan_slug not in metadata, derive it from the price ID
    if not plan_slug:
        plan_slug = _plan_slug_from_stripe_sub(stripe_sub)

    _sync_subscription_from_stripe(
        bonup_user_id=bonup_user_id,
        plan_slug=plan_slug,
        stripe_sub=stripe_sub,
        stripe_customer_id=stripe_sub.get("customer"),
    )


def handle_subscription_deleted(stripe_sub):
    """
    Fired when a Stripe subscription is cancelled/deleted.
    Sets local status to 'cancelled'.
    """
    metadata = stripe_sub.get("metadata") or {}
    bonup_user_id = metadata.get("bonup_user_id")

    if not bonup_user_id:
        stripe_sub_id = stripe_sub.get("id")
        # Try to find by stripe_subscription_id
        updated = UserSubscription.objects.filter(
            stripe_subscription_id=stripe_sub_id
        ).update(status="cancelled", updated_at=timezone.now())
        if not updated:
            logger.warning("subscription.deleted: no local sub found for %s", stripe_sub_id)
        return

    UserSubscription.objects.filter(user_id=bonup_user_id).update(
        status="cancelled",
        updated_at=timezone.now(),
    )


def handle_invoice_paid(stripe_invoice):
    """
    Fired when a Stripe invoice is paid.
    Creates or updates the local Invoice record.
    """
    stripe_invoice_id = stripe_invoice.get("id")
    stripe_customer_id = stripe_invoice.get("customer")
    amount_paid = stripe_invoice.get("amount_paid", 0)  # cents
    currency = (stripe_invoice.get("currency") or "usd").upper()

    bonup_user_id = _user_id_from_customer(stripe_customer_id)
    if not bonup_user_id:
        logger.warning("invoice.paid: no local user for customer %s", stripe_customer_id)
        return

    from decimal import Decimal
    amount_decimal = Decimal(str(amount_paid)) / Decimal("100")

    with transaction.atomic():
        Invoice.objects.update_or_create(
            stripe_invoice_id=stripe_invoice_id,
            defaults={
                "user_id": bonup_user_id,
                "amount": amount_decimal,
                "currency": currency,
                "status": "paid",
                "description": stripe_invoice.get("description") or "Stripe invoice",
                "paid_at": timezone.now(),
            },
        )
        # Also reset the subscription counter on renewal
        UserSubscription.objects.filter(user_id=bonup_user_id).update(
            contracts_used_this_period=0,
            live_sessions_used_this_month=0,
        )


def handle_invoice_payment_failed(stripe_invoice):
    """
    Fired when a Stripe invoice payment fails.
    Marks subscription as past_due.
    """
    stripe_customer_id = stripe_invoice.get("customer")
    bonup_user_id = _user_id_from_customer(stripe_customer_id)
    if not bonup_user_id:
        logger.warning("invoice.payment_failed: no local user for customer %s", stripe_customer_id)
        return

    UserSubscription.objects.filter(user_id=bonup_user_id).update(
        status="past_due",
        updated_at=timezone.now(),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _sync_subscription_from_stripe(bonup_user_id, plan_slug, stripe_sub, stripe_customer_id):
    """Write/update local UserSubscription from a Stripe Subscription object."""
    from django.contrib.auth import get_user_model
    User = get_user_model()

    try:
        plan = SubscriptionPlan.objects.get(slug=plan_slug)
    except SubscriptionPlan.DoesNotExist:
        logger.error("_sync_subscription_from_stripe: unknown plan slug '%s'", plan_slug)
        return

    stripe_status = stripe_sub.get("status", "active")
    local_status = _STRIPE_TO_LOCAL_STATUS.get(stripe_status, "active")

    # Stripe timestamps are Unix ints
    import datetime
    current_period_start = datetime.datetime.fromtimestamp(
        stripe_sub["current_period_start"], tz=datetime.timezone.utc
    ) if stripe_sub.get("current_period_start") else timezone.now()

    current_period_end = datetime.datetime.fromtimestamp(
        stripe_sub["current_period_end"], tz=datetime.timezone.utc
    ) if stripe_sub.get("current_period_end") else None

    stripe_subscription_id = stripe_sub.get("id")

    with transaction.atomic():
        UserSubscription.objects.update_or_create(
            user_id=bonup_user_id,
            defaults={
                "plan": plan,
                "status": local_status,
                "billing_period": "monthly",
                "current_period_start": current_period_start,
                "current_period_end": current_period_end,
                "stripe_customer_id": stripe_customer_id or "",
                "stripe_subscription_id": stripe_subscription_id or "",
            },
        )


def _plan_slug_from_stripe_sub(stripe_sub):
    """
    Try to derive the plan slug from a Stripe subscription's price ID.
    Falls back to 'starter' if not found.
    """
    price_ids = getattr(settings, "STRIPE_PRICE_IDS", {})
    # Invert: price_id → slug
    reverse = {v: k for k, v in price_ids.items() if v}

    items = stripe_sub.get("items", {}).get("data", [])
    if items:
        price_id = items[0].get("price", {}).get("id", "")
        return reverse.get(price_id, "starter")
    return "starter"


def _user_id_from_customer(stripe_customer_id):
    """Look up our local user_id from a Stripe customer_id."""
    if not stripe_customer_id:
        return None
    try:
        sub = UserSubscription.objects.get(stripe_customer_id=stripe_customer_id)
        return sub.user_id
    except UserSubscription.DoesNotExist:
        return None
