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
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from .models import (
    CommercialEntitlementStatus,
    Invoice,
    Product,
    StoreCheckout,
    StoreCheckoutStatus,
    StoragePurchase,
    StoragePurchaseStatus,
    SubscriptionPlan,
    ToolEntitlement,
    ToolEntitlementOrigin,
    UserSubscription,
)
from .stripe_client import get_stripe
from .store_quote import build_store_quote

logger = logging.getLogger(__name__)

# Plans that can be purchased through Stripe Checkout.
# trial, sol_member, and per_contract are not self-serve Checkout plans.
# Legacy slugs are retained so existing Stripe metadata/price configuration can
# continue to resolve until the external Stripe migration is handled separately.
CHECKOUT_ALLOWED_PLANS = {"basic", "professional", "advanced", "starter", "business", "anchor"}

_LEGACY_CHECKOUT_PLAN_MAP = {
    "starter": "basic",
    "business": "advanced",
}
_STRIPE_PRICE_ID_FALLBACK_SLUGS = {
    "basic": "starter",
    "advanced": "business",
}


def canonical_plan_slug(plan_slug):
    """Return the launch-era internal plan slug for supported legacy slugs."""
    return _LEGACY_CHECKOUT_PLAN_MAP.get(plan_slug, plan_slug)

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
        price_id = price_ids.get(_STRIPE_PRICE_ID_FALLBACK_SLUGS.get(plan_slug, ""), "")
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
            "plan_slug": canonical_plan_slug(plan_slug),
            "legacy_plan_slug": plan_slug,
        },
        subscription_data={
            "metadata": {
                "bonup_user_id": str(user.id),
                "plan_slug": canonical_plan_slug(plan_slug),
                "legacy_plan_slug": plan_slug,
            }
        },
    )
    return session


def _money(value):
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _money_to_cents(value):
    return int((_money(value) * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))


def _frontend_base_url():
    return getattr(settings, "FRONTEND_URL", "http://localhost:5173").rstrip("/")


def _quote_recurring_amount(quote):
    recurring = quote["totals"]["recurring"]
    return _money(recurring["monthly"]) + _money(recurring["annual"])


def _checkout_mode_for_quote(quote):
    has_recurring = any(item.get("charge_type") == "recurring" for item in quote["items"])
    return "subscription" if has_recurring else "payment"


def _line_item_for_quote_item(item):
    unit_amount = _money_to_cents(item["amount"])
    price_data = {
        "currency": item["currency"].lower(),
        "unit_amount": unit_amount,
        "product_data": {
            "name": item["name"],
            "metadata": {
                "bonup_product_slug": item["product_slug"],
                "bonup_product_kind": item["kind"],
            },
        },
    }
    if item.get("charge_type") == "recurring":
        interval = "year" if item["billing_interval"] == "annual" else "month"
        price_data["recurring"] = {"interval": interval}
    return {"price_data": price_data, "quantity": 1}


def _safe_checkout_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def get_or_create_store_stripe_customer(user):
    try:
        sub = UserSubscription.objects.get(user=user)
        if sub.stripe_customer_id:
            return sub.stripe_customer_id
    except UserSubscription.DoesNotExist:
        pass

    prior = StoreCheckout.objects.filter(user=user).exclude(stripe_customer_id="").order_by("-created_at", "-id").first()
    if prior is not None:
        return prior.stripe_customer_id

    stripe = get_stripe()
    customer = stripe.Customer.create(
        email=user.email,
        metadata={"bonup_user_id": str(user.id)},
    )
    return customer["id"]


def create_store_checkout_session(user, selection):
    quote = build_store_quote(user=user, selection=selection)
    if not quote["items"] or _money(quote["totals"]["due_today"]) <= Decimal("0.00"):
        raise ValidationError({"selection": "Select at least one payable Store product."})

    mode = _checkout_mode_for_quote(quote)
    customer_id = get_or_create_store_stripe_customer(user)
    checkout = StoreCheckout.objects.create(
        user=user,
        status=StoreCheckoutStatus.PENDING,
        currency=quote["currency"],
        recurring_amount_snapshot=_quote_recurring_amount(quote),
        one_time_amount_snapshot=_money(quote["totals"]["one_time"]),
        due_today_snapshot=_money(quote["totals"]["due_today"]),
        selection_snapshot=selection,
        quote_snapshot=quote,
        stripe_customer_id=customer_id,
    )

    success_url = f"{_frontend_base_url()}/store/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{_frontend_base_url()}/store/review"
    metadata = {"bonup_checkout_id": str(checkout.id)}
    session_kwargs = {
        "customer": customer_id,
        "mode": mode,
        "line_items": [_line_item_for_quote_item(item) for item in quote["items"]],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": str(checkout.id),
        "metadata": metadata,
        "payment_method_types": ["card"],
    }
    if mode == "subscription":
        session_kwargs["subscription_data"] = {"metadata": metadata}
    else:
        session_kwargs["payment_intent_data"] = {"metadata": metadata}

    stripe = get_stripe()
    session = stripe.checkout.Session.create(
        **session_kwargs,
        idempotency_key=f"store_checkout_{checkout.id}",
    )
    checkout.stripe_checkout_session_id = session["id"]
    checkout.status = StoreCheckoutStatus.CHECKOUT_CREATED
    checkout.save(update_fields=["stripe_checkout_session_id", "status", "updated_at"])
    return checkout, session


def _retrieve_checkout_session(session_id):
    stripe = get_stripe()
    return stripe.checkout.Session.retrieve(session_id, expand=["subscription"])


def _session_payment_is_complete(session):
    return session.get("payment_status") == "paid"


def _session_is_expired(session):
    return session.get("status") == "expired"


def _subscription_period_value(stripe_sub, key):
    import datetime
    if not stripe_sub or not stripe_sub.get(key):
        return None
    return datetime.datetime.fromtimestamp(stripe_sub[key], tz=datetime.timezone.utc)


def _billing_period_for_quote(quote):
    for item in quote["items"]:
        if item.get("kind") == "tool" and item.get("billing_interval") == "annual":
            return "yearly"
    return "monthly"


def _fulfill_blackbod_from_checkout(checkout, session, now):
    tool_items = [item for item in checkout.quote_snapshot.get("items", []) if item.get("kind") == "tool"]
    if not tool_items:
        return None

    product = Product.objects.select_for_update(of=("self",)).get(slug="blackbod", product_type=Product.ProductType.TOOL)
    stripe_subscription = session.get("subscription")
    if isinstance(stripe_subscription, str):
        stripe_subscription_id = stripe_subscription
        stripe_sub = get_stripe().Subscription.retrieve(stripe_subscription_id)
    else:
        stripe_sub = stripe_subscription or {}
        stripe_subscription_id = stripe_sub.get("id", "")

    stripe_customer_id = session.get("customer") or checkout.stripe_customer_id
    starts_at = _subscription_period_value(stripe_sub, "current_period_start") or now
    ends_at = _subscription_period_value(stripe_sub, "current_period_end")
    billing_period = _billing_period_for_quote(checkout.quote_snapshot)

    plan = SubscriptionPlan.objects.get(slug="advanced")
    UserSubscription.objects.update_or_create(
        user=checkout.user,
        defaults={
            "plan": plan,
            "status": "active",
            "billing_period": billing_period,
            "current_period_start": starts_at,
            "current_period_end": ends_at,
            "stripe_customer_id": stripe_customer_id or "",
            "stripe_subscription_id": stripe_subscription_id or "",
        },
    )

    entitlement = ToolEntitlement.objects.filter(
        user=checkout.user,
        product=product,
        status=CommercialEntitlementStatus.ACTIVE,
        starts_at__lte=now,
    ).filter(models.Q(ends_at__isnull=True) | models.Q(ends_at__gt=now)).order_by("starts_at", "id").first()
    if entitlement is None:
        entitlement = ToolEntitlement.objects.create(
            user=checkout.user,
            product=product,
            status=CommercialEntitlementStatus.ACTIVE,
            origin=ToolEntitlementOrigin.LEGACY_SUBSCRIPTION,
            starts_at=starts_at,
            ends_at=ends_at,
        )
    checkout.tool_entitlement = entitlement
    checkout.stripe_subscription_id = stripe_subscription_id or checkout.stripe_subscription_id
    checkout.stripe_customer_id = stripe_customer_id or checkout.stripe_customer_id
    return entitlement


def _fulfill_storage_from_checkout(checkout, session, now):
    storage_items = [item for item in checkout.quote_snapshot.get("items", []) if item.get("kind") == "storage"]
    if not storage_items:
        return None
    if checkout.storage_purchase_id:
        from .storage_commerce import complete_storage_purchase
        return complete_storage_purchase(checkout.storage_purchase, now=now)

    item = storage_items[0]
    product = Product.objects.select_for_update(of=("self",)).get(slug=item["product_slug"], product_type=Product.ProductType.STORAGE)
    payment_reference = session.get("payment_intent") or session.get("id") or ""
    purchase = StoragePurchase.objects.create(
        user=checkout.user,
        product=product,
        product_price=None,
        capacity_bytes_snapshot=item["capacity_bytes"],
        capacity_label_snapshot=item["name"],
        price_amount_snapshot=_money(item["amount"]),
        currency_snapshot=item["currency"],
        status=StoragePurchaseStatus.PENDING,
        purchased_at=now,
        payment_reference=payment_reference,
        metadata={"store_checkout_id": checkout.id, "stripe_checkout_session_id": session.get("id")},
    )
    from .storage_commerce import complete_storage_purchase
    completed = complete_storage_purchase(purchase, now=now)
    checkout.storage_purchase = completed
    checkout.stripe_payment_intent_id = session.get("payment_intent") or checkout.stripe_payment_intent_id
    return completed


def fulfill_store_checkout_session(session_or_id):
    session_id = session_or_id if isinstance(session_or_id, str) else session_or_id.get("id")
    if not session_id:
        logger.warning("Store checkout webhook missing Checkout Session id.")
        return None
    session = _retrieve_checkout_session(session_id)
    metadata = session.get("metadata") or {}
    checkout_id = _safe_checkout_id(metadata.get("bonup_checkout_id"))

    with transaction.atomic():
        qs = StoreCheckout.objects.select_for_update(of=("self",)).select_related("user", "storage_purchase")
        checkout = qs.filter(stripe_checkout_session_id=session_id).first()
        if checkout is None and checkout_id is not None:
            checkout = qs.filter(id=checkout_id).first()
        if checkout is None:
            logger.warning("Store checkout webhook for unknown session %s.", session_id)
            return None
        if checkout.stripe_checkout_session_id and checkout.stripe_checkout_session_id != session_id:
            logger.warning("Store checkout session mismatch for checkout %s.", checkout.id)
            return checkout
        if checkout.status == StoreCheckoutStatus.FULFILLED:
            return checkout
        if _session_is_expired(session):
            checkout.status = StoreCheckoutStatus.EXPIRED
            checkout.save(update_fields=["status", "updated_at"])
            return checkout
        if not _session_payment_is_complete(session):
            checkout.status = StoreCheckoutStatus.FAILED if session.get("payment_status") == "unpaid" else StoreCheckoutStatus.CHECKOUT_CREATED
            checkout.save(update_fields=["status", "updated_at"])
            return checkout

        now = timezone.now()
        checkout.status = StoreCheckoutStatus.PAID
        checkout.stripe_checkout_session_id = session_id
        checkout.stripe_customer_id = session.get("customer") or checkout.stripe_customer_id
        _fulfill_blackbod_from_checkout(checkout, session, now)
        _fulfill_storage_from_checkout(checkout, session, now)
        checkout.status = StoreCheckoutStatus.FULFILLED
        checkout.fulfilled_at = checkout.fulfilled_at or now
        checkout.save(update_fields=[
            "status",
            "stripe_checkout_session_id",
            "stripe_customer_id",
            "stripe_subscription_id",
            "stripe_payment_intent_id",
            "tool_entitlement",
            "storage_purchase",
            "fulfilled_at",
            "updated_at",
        ])
        return checkout


def mark_store_checkout_failed(session_or_id):
    session_id = session_or_id if isinstance(session_or_id, str) else session_or_id.get("id")
    if not session_id:
        return None
    with transaction.atomic():
        checkout = StoreCheckout.objects.select_for_update(of=("self",)).filter(stripe_checkout_session_id=session_id).first()
        if checkout is None or checkout.status == StoreCheckoutStatus.FULFILLED:
            return checkout
        checkout.status = StoreCheckoutStatus.EXPIRED if (not isinstance(session_or_id, str) and session_or_id.get("status") == "expired") else StoreCheckoutStatus.FAILED
        checkout.save(update_fields=["status", "updated_at"])
        return checkout


def safe_store_checkout_status(user, session_id):
    checkout = StoreCheckout.objects.filter(user=user, stripe_checkout_session_id=session_id).first()
    if checkout is None:
        return None
    items = []
    for item in checkout.quote_snapshot.get("items", []):
        if item.get("kind") in {"tool", "storage"}:
            items.append({
                "kind": item["kind"],
                "product_slug": item["product_slug"],
                "name": item["name"],
                "capacity_gib": item.get("capacity_gib"),
                "billing_interval": item.get("billing_interval"),
            })
    return {
        "status": checkout.status,
        "currency": checkout.currency,
        "due_today": str(checkout.due_today_snapshot),
        "fulfilled": checkout.status == StoreCheckoutStatus.FULFILLED,
        "items": items,
        "created_at": checkout.created_at,
        "fulfilled_at": checkout.fulfilled_at,
    }


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
    plan_slug = canonical_plan_slug(plan_slug)

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
    plan_slug = canonical_plan_slug(plan_slug)

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

    plan_slug = canonical_plan_slug(plan_slug)
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
        return canonical_plan_slug(reverse.get(price_id, "starter"))
    return "basic"


def _user_id_from_customer(stripe_customer_id):
    """Look up our local user_id from a Stripe customer_id."""
    if not stripe_customer_id:
        return None
    try:
        sub = UserSubscription.objects.get(stripe_customer_id=stripe_customer_id)
        return sub.user_id
    except UserSubscription.DoesNotExist:
        return None
