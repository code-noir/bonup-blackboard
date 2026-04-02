# backend/billing/gates.py
#
# Feature gate helpers for plan-based access control.
#
# All public functions return either a value or a (bool, str) tuple:
#   bool  — allowed or not
#   str   — human-readable reason when blocked (empty string when allowed)
#
# None subscription → blocked everywhere. Gates never raise exceptions.

from django.db import models as django_models

from .models import UserSubscription

_ACTIVE_STATUSES = {"active", "trialing", "per_contract"}


def get_user_subscription(user):
    """Return UserSubscription (with plan selected) or None."""
    try:
        return UserSubscription.objects.select_related("plan").get(user=user)
    except UserSubscription.DoesNotExist:
        return None


def can_create_contract(user):
    """
    Returns (allowed: bool, message: str).
    Checks max_active_contracts limit.
    """
    sub = get_user_subscription(user)
    if sub is None:
        return False, "No active subscription. Please subscribe to create contracts."
    if sub.status not in _ACTIVE_STATUSES:
        return False, "Your subscription is not active. Please renew to create contracts."
    plan = sub.plan
    if plan.max_active_contracts is None:
        return True, ""
    if sub.contracts_used_this_period >= plan.max_active_contracts:
        return (
            False,
            f"Contract limit reached ({plan.max_active_contracts}). "
            "Please upgrade your plan to create more contracts.",
        )
    return True, ""


def can_create_session(user):
    """
    Returns (allowed: bool, message: str).
    Checks max_live_sessions_per_month limit.
    0 means live sessions are not included in the plan.
    """
    sub = get_user_subscription(user)
    if sub is None:
        return False, "No active subscription. Please subscribe to create live sessions."
    if sub.status not in _ACTIVE_STATUSES:
        return False, "Your subscription is not active."
    plan = sub.plan
    if plan.max_live_sessions_per_month == 0:
        return False, "Live sessions are not included in your plan. Please upgrade."
    if plan.max_live_sessions_per_month is None:
        return True, ""
    if sub.live_sessions_used_this_month >= plan.max_live_sessions_per_month:
        return (
            False,
            f"Monthly session limit reached ({plan.max_live_sessions_per_month}). "
            "Please upgrade your plan.",
        )
    return True, ""


def can_access_template(user, template):
    """
    Returns (allowed: bool, message: str).
    Enforces excluded_categories. templates_per_category is an instantiation
    limit tracked separately — not a view gate.
    """
    sub = get_user_subscription(user)
    if sub is None:
        return False, "No active subscription required to access templates."
    if sub.status not in _ACTIVE_STATUSES:
        return False, "Your subscription is not active."
    plan = sub.plan
    excluded = plan.excluded_categories or []
    if template.category in excluded:
        return (
            False,
            f"Templates in '{template.category}' are not included in your plan. "
            "Please upgrade.",
        )
    return True, ""


def get_ai_tier(user):
    """Return the user's AI tier: none / basic / advanced / full."""
    sub = get_user_subscription(user)
    if sub is None:
        return "none"
    return sub.plan.ai_tier


def has_feature(user, feature_name):
    """
    Generic feature flag check.

    Supported feature_name values:
      lifecycle, notifications, negotiation_prep,
      priority_support, early_access
    """
    sub = get_user_subscription(user)
    if sub is None:
        return False
    plan = sub.plan
    feature_map = {
        "lifecycle": plan.has_lifecycle,
        "notifications": plan.has_notifications,
        "negotiation_prep": plan.has_negotiation_prep,
        "priority_support": plan.has_priority_support,
        "early_access": plan.has_early_access,
    }
    return feature_map.get(feature_name, False)


# ---------------------------------------------------------------------------
# Usage counter helpers (called by API views after gate passes)
# ---------------------------------------------------------------------------

def increment_contracts_used(user):
    """Atomically increment contracts_used_this_period for the user's subscription."""
    UserSubscription.objects.filter(user=user).update(
        contracts_used_this_period=django_models.F("contracts_used_this_period") + 1
    )


def increment_sessions_used(user):
    """Atomically increment live_sessions_used_this_month for the user's subscription."""
    UserSubscription.objects.filter(user=user).update(
        live_sessions_used_this_month=django_models.F("live_sessions_used_this_month") + 1
    )
