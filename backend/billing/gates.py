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
from django.utils import timezone
from django.utils.translation import gettext as _

from .models import UserSubscription

_ACTIVE_STATUSES = {"active", "trialing", "per_contract"}

# Standard error message returned when a PAYG user tries to access a monthly-only feature.
_PAYG_BLOCKED_MSG = "This feature requires a monthly plan. Upgrade to Blackboard Basic ($19/month) to unlock contract management."


def is_payg(user):
    """Returns True if the user is on the Pay As You Go (per_contract) plan."""
    sub = get_user_subscription(user)
    return sub is not None and sub.plan.slug == "per_contract"


def get_user_subscription(user):
    """Return UserSubscription (with plan selected) or None."""
    try:
        return UserSubscription.objects.select_related("plan").get(user=user)
    except UserSubscription.DoesNotExist:
        return None


def can_create_contract(user):
    """
    Returns (allowed: bool, message: str).
    Checks trial limit first, then max_active_contracts plan limit.
    """
    sub = get_user_subscription(user)
    if sub is None:
        return False, _("No active subscription. Please subscribe to create contracts.")
    if sub.status not in _ACTIVE_STATUSES:
        return False, _("Your subscription is not active. Please renew to create contracts.")

    # Trial-specific gate: enforce trial_contracts_remaining regardless of plan limit
    if sub.status == "trialing" and sub.trial_contracts_remaining <= 0:
        return (
            False,
            _("Your free trial has been used. Please subscribe to create more contracts."),
        )

    plan = sub.plan
    if plan.max_active_contracts is None:
        return True, ""
    if sub.contracts_used_this_period >= plan.max_active_contracts:
        return (
            False,
            _("Contract limit reached (%(limit)s). Please upgrade your plan to create more contracts.") % {"limit": plan.max_active_contracts},
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
        return False, _("No active subscription. Please subscribe to create live sessions.")
    if sub.status not in _ACTIVE_STATUSES:
        return False, _("Your subscription is not active.")
    plan = sub.plan
    if plan.max_live_sessions_per_month == 0:
        return False, _("Live sessions are not included in your plan. Please upgrade.")
    if plan.max_live_sessions_per_month is None:
        return True, ""
    if sub.live_sessions_used_this_month >= plan.max_live_sessions_per_month:
        return (
            False,
            _("Monthly session limit reached (%(limit)s). Please upgrade your plan.") % {"limit": plan.max_live_sessions_per_month},
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
        return False, _("No active subscription required to access templates.")
    if sub.status not in _ACTIVE_STATUSES:
        return False, _("Your subscription is not active.")
    plan = sub.plan
    excluded = plan.excluded_categories or []
    if template.category in excluded:
        return (
            False,
            _("Templates in '%(category)s' are not included in your plan. Please upgrade.") % {"category": template.category},
        )
    return True, ""


def can_create_sol(user):
    """
    Returns (allowed: bool, message: str).
    Sol group management requires a plan with has_sol=True (Business or Anchor tier).
    """
    sub = get_user_subscription(user)
    if sub is None:
        return False, _("A Business or Anchor subscription is required to manage a Sol group.")
    if sub.status not in _ACTIVE_STATUSES:
        return False, _("Your subscription is not active.")
    if not sub.plan.has_sol:
        return False, _("Sol group management requires a Business or Anchor subscription.")
    return True, ""


def can_join_sol(user):
    """
    Returns (allowed: bool, message: str).
    Active monthly subscriptions allow joining a Sol group.
    Pay As You Go (per_contract) does not include Sol groups.
    """
    sub = get_user_subscription(user)
    if sub is None:
        return False, _("An active subscription is required to join a Sol group on bonUP.")
    if sub.status not in _ACTIVE_STATUSES:
        return False, _("Your subscription is not active.")
    if sub.plan.slug == "per_contract":
        return False, _(_PAYG_BLOCKED_MSG)
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
        "sol": plan.has_sol,
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


# ---------------------------------------------------------------------------
# Trial helpers
# ---------------------------------------------------------------------------

def start_trial(user):
    """
    Create a business-tier trial subscription for a newly registered user.
    Silently no-ops if:
      - the user already has a subscription, or
      - the business plan does not exist (e.g., before migrations run in tests).
    """
    from .models import SubscriptionPlan

    try:
        plan = SubscriptionPlan.objects.get(slug="business")
    except SubscriptionPlan.DoesNotExist:
        return

    UserSubscription.objects.get_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "trialing",
            "billing_period": "monthly",
            "current_period_start": timezone.now(),
            "trial_contracts_remaining": 1,
        },
    )


def consume_trial_contract(user):
    """
    Called after a contract is successfully created.
    For trialing users: decrements trial_contracts_remaining by 1.
    When it reaches 0, transitions status to no_subscription.
    No-op for non-trialing users.
    """
    # Decrement only if trialing and still has remaining contracts
    updated = UserSubscription.objects.filter(
        user=user,
        status="trialing",
        trial_contracts_remaining__gt=0,
    ).update(
        trial_contracts_remaining=django_models.F("trial_contracts_remaining") - 1
    )

    if updated:
        # Transition to no_subscription if now exhausted
        UserSubscription.objects.filter(
            user=user,
            status="trialing",
            trial_contracts_remaining=0,
        ).update(status="no_subscription")


# ---------------------------------------------------------------------------
# Business Entity gates
# ---------------------------------------------------------------------------

_MAX_BUSINESSES = {
    # Legacy slugs
    "trial": 1,
    "sol_member": 0,
    "per_contract": 1,
    "starter": 0,
    "professional": 1,
    "business": 4,
    "anchor": 35,
    # Current slugs
    "blackboard_basic": 0,
    "blackboard_pro": 1,
    "blackboard_business": 4,
    "blackboard_enterprise": 35,
}

# Enterprise limit used when no subscription exists (billing not yet wired)
_DEV_MAX_BUSINESSES = 35


def max_businesses(user):
    """Return the maximum number of business entities allowed for this user's plan."""
    sub = get_user_subscription(user)
    if sub is None:
        from django.conf import settings
        return _DEV_MAX_BUSINESSES if settings.DEBUG else 0
    return _MAX_BUSINESSES.get(sub.plan.slug, 0)


def can_create_business_entity(user):
    """
    Returns (allowed: bool, message: str).
    Checks tier limit before allowing a new BusinessEntity to be created.
    """
    from backend.users.models import BusinessEntity

    sub = get_user_subscription(user)
    if sub is None:
        from django.conf import settings
        if not settings.DEBUG:
            return False, _("No active subscription.")
        # In DEBUG: treat as enterprise — enforce only the dev limit
        current = BusinessEntity.objects.filter(owner=user, is_active=True).count()
        if current >= _DEV_MAX_BUSINESSES:
            return False, _("Business entity limit reached (%(limit)s).") % {"limit": _DEV_MAX_BUSINESSES}
        return True, ""
    if sub.status not in _ACTIVE_STATUSES:
        return False, _("Your subscription is not active.")

    max_biz = _MAX_BUSINESSES.get(sub.plan.slug, 0)
    if max_biz == 0:
        return (
            False,
            _("Business entities are not available on your current plan. Upgrade to Blackboard Pro ($149/month) or higher."),
        )

    current = BusinessEntity.objects.filter(owner=user, is_active=True).count()
    if current >= max_biz:
        return (
            False,
            _("Business entity limit reached (%(limit)s). Please upgrade your plan to add more.") % {"limit": max_biz},
        )
    return True, ""


# ---------------------------------------------------------------------------
# Sol Member auto-upgrade / auto-downgrade helpers
# ---------------------------------------------------------------------------

# Plans below sol_member that trigger an auto-upgrade on Sol group join.
# per_contract (PAYG) is excluded: PAYG users cannot join Sol groups.
_LOWER_THAN_SOL_MEMBER = {"trial"}


def auto_upgrade_to_sol_member(user):
    """
    Called when a bonUP user joins a Sol group.
    Upgrades to sol_member plan if user has no subscription or a lower-tier plan.
    No-op for users already on sol_member or any higher plan.
    """
    from .models import SubscriptionPlan

    try:
        sol_plan = SubscriptionPlan.objects.get(slug="sol_member")
    except SubscriptionPlan.DoesNotExist:
        return

    sub = get_user_subscription(user)
    if sub is None:
        UserSubscription.objects.create(
            user=user,
            plan=sol_plan,
            status="active",
            billing_period="monthly",
            current_period_start=timezone.now(),
        )
        return

    if sub.plan.slug in _LOWER_THAN_SOL_MEMBER:
        sub.plan = sol_plan
        sub.status = "active"
        sub.save(update_fields=["plan", "status"])


def auto_downgrade_from_sol_member(user):
    """
    Called when a bonUP user leaves a Sol group.
    If the user is on sol_member and has no remaining active Sol memberships,
    downgrades to the starter (Blackboard Basic) plan.
    """
    from .models import SubscriptionPlan

    sub = get_user_subscription(user)
    if sub is None or sub.plan.slug != "sol_member":
        return

    # Check remaining active Sol memberships
    from backend.sol.models import SolMember
    still_in_sol = SolMember.objects.filter(bonup_user=user, is_active=True).exists()
    if still_in_sol:
        return

    try:
        starter_plan = SubscriptionPlan.objects.get(slug="starter")
    except SubscriptionPlan.DoesNotExist:
        return

    sub.plan = starter_plan
    sub.save(update_fields=["plan"])
