# backend/billing/gates.py
#
# Feature gate helpers for plan-based access control.
#
# All public functions return either a value or a (bool, str) tuple:
#   bool  — allowed or not
#   str   — human-readable reason when blocked (empty string when allowed)
#
# Blackboard build mode: subscription gating disabled for contract creation/testing flows.

from django.db import models as django_models
from datetime import timedelta

from django.utils import timezone
from django.utils.translation import gettext as _

from .models import UserSubscription

_ACTIVE_STATUSES = {"active", "trialing", "per_contract"}

BLACKBOD_TIER_BASIC = "basic"
BLACKBOD_TIER_PROFESSIONAL = "professional"
BLACKBOD_TIER_ADVANCED = "advanced"
BLACKBOD_PAID_TIERS = {
    BLACKBOD_TIER_BASIC,
    BLACKBOD_TIER_PROFESSIONAL,
    BLACKBOD_TIER_ADVANCED,
}
BLACKBOD_TRIAL_DAYS = 14

_LEGACY_BLACKBOD_TIER_MAP = {
    "starter": BLACKBOD_TIER_BASIC,
    "professional": BLACKBOD_TIER_PROFESSIONAL,
    "business": BLACKBOD_TIER_ADVANCED,
}
_BLACKBOD_AI_TIER_BY_EFFECTIVE_TIER = {
    BLACKBOD_TIER_BASIC: "none",
    BLACKBOD_TIER_PROFESSIONAL: "basic",
    BLACKBOD_TIER_ADVANCED: "advanced",
}
_BLACKBOD_FEATURES_BY_EFFECTIVE_TIER = {
    BLACKBOD_TIER_BASIC: {
        "notifications": True,
        "sol": False,
        "priority_support": False,
        "early_access": False,
    },
    BLACKBOD_TIER_PROFESSIONAL: {
        "notifications": True,
        "sol": True,
        "priority_support": False,
        "early_access": False,
    },
    BLACKBOD_TIER_ADVANCED: {
        "notifications": True,
        "sol": True,
        "priority_support": False,
        "early_access": False,
    },
}

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


def normalize_blackbod_tier_slug(slug):
    """Return the launch Blackbòd tier slug for current or supported legacy slugs."""
    if slug in BLACKBOD_PAID_TIERS:
        return slug
    return _LEGACY_BLACKBOD_TIER_MAP.get(slug)


def trial_end_for_start(trial_start):
    """Return the canonical 14-day trial end for a trial start timestamp."""
    return trial_start + timedelta(days=BLACKBOD_TRIAL_DAYS)


def is_trial_valid(subscription, now=None):
    """Return True when a subscription is actively trialing inside its 14-day window."""
    if subscription is None or subscription.status != "trialing":
        return False
    now = now or timezone.now()
    trial_start = subscription.trial_start or subscription.current_period_start
    if trial_start is None:
        return False
    trial_end = subscription.trial_end or trial_end_for_start(trial_start)
    return trial_start <= now < trial_end


def get_effective_blackbod_tier(user, now=None):
    """
    Resolve the authoritative effective Blackbòd entitlement tier.

    Returns one of: basic, professional, advanced, or None. A valid trial
    resolves to professional entitlements without changing the stored plan.
    """
    sub = get_user_subscription(user)
    if sub is None:
        return None
    if sub.status == "trialing":
        return BLACKBOD_TIER_PROFESSIONAL if is_trial_valid(sub, now=now) else None
    if sub.status != "active":
        return None
    return normalize_blackbod_tier_slug(sub.plan.slug)


def can_create_contract(user):
    """
    Returns (allowed: bool, message: str).
    
    Blackboard build mode: subscription gating disabled for contract
    creation/testing. Do not create or mutate subscription rows here.
    """
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
    if sub.status == "trialing" and not is_trial_valid(sub):
        return False, _("Your trial has expired.")
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

    Blackboard build mode: subscription gating disabled for contract template
    browsing/use/testing.
    """
    return True, ""


def can_create_sol(user):
    """
    Returns (allowed: bool, message: str).
    Sol group management requires a paid Pro or higher subscription (has_sol=True).
    Trialing and sol_member plan users do not qualify — trialing is not a paid plan,
    and sol_member is a member tier, not a manager tier.
    """
    sub = get_user_subscription(user)
    if sub is None:
        return False, _("A Pro or higher subscription is required to manage a Sol group.")
    if sub.status not in _ACTIVE_STATUSES:
        return False, _("Your subscription is not active.")
    if sub.status == "trialing":
        return False, _("Sol group management requires a paid Pro or higher subscription.")
    if sub.plan.slug == "sol_member":
        return False, _("Sol group management requires a Pro or higher subscription.")
    if not sub.plan.has_sol:
        return False, _("Sol group management requires a Pro or higher subscription.")
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
    if sub.status == "trialing" and not is_trial_valid(sub):
        return "none"
    effective_tier = get_effective_blackbod_tier(user)
    if effective_tier is not None:
        return _BLACKBOD_AI_TIER_BY_EFFECTIVE_TIER[effective_tier]
    return sub.plan.ai_tier


def has_feature(user, feature_name):
    """
    Generic feature flag check.

    Blackboard build mode: lifecycle and negotiation-prep testing are not
    subscription-gated. Other features keep the existing plan checks.
    """
    if feature_name in {"lifecycle", "negotiation_prep"}:
        return True

    sub = get_user_subscription(user)
    if sub is None:
        return False
    if sub.status == "trialing" and not is_trial_valid(sub):
        return False
    effective_tier = get_effective_blackbod_tier(user)
    if effective_tier is not None:
        return _BLACKBOD_FEATURES_BY_EFFECTIVE_TIER[effective_tier].get(feature_name, False)
    plan = sub.plan
    feature_map = {
        "notifications": plan.has_notifications,
        "sol": plan.has_sol,
        "priority_support": plan.has_priority_support,
        "early_access": plan.has_early_access,
    }
    return feature_map.get(feature_name, False)


# ---------------------------------------------------------------------------
# Usage counter helpers (called by API views after gate passes)
# ---------------------------------------------------------------------------

def increment_contracts_used(user):
    """Blackboard build mode: contract creation must not mutate billing usage."""
    return None


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
    Create a 14-day Blackbòd trial subscription for a newly registered user.
    Silently no-ops if:
      - the user already has a subscription, or
      - the trial plan does not exist (e.g., before migrations run in tests).
    """
    from .models import SubscriptionPlan

    try:
        plan = SubscriptionPlan.objects.get(slug="trial")
    except SubscriptionPlan.DoesNotExist:
        return

    trial_start = timezone.now()
    trial_end = trial_end_for_start(trial_start)
    UserSubscription.objects.get_or_create(
        user=user,
        defaults={
            "plan": plan,
            "status": "trialing",
            "billing_period": "monthly",
            "current_period_start": trial_start,
            "current_period_end": trial_end,
            "trial_start": trial_start,
            "trial_end": trial_end,
            "trial_contracts_remaining": 0,
        },
    )


def consume_trial_contract(user):
    """Blackboard build mode: contract creation must not consume trial state."""
    return None


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
    # Launch slugs
    "basic": 0,
    "advanced": 4,
    # Stale/future slugs retained temporarily for compatibility with older code.
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
    if sub.status == "trialing":
        return _MAX_BUSINESSES["professional"] if is_trial_valid(sub) else 0
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
    if sub.status == "trialing" and not is_trial_valid(sub):
        return False, _("Your trial has expired.")

    max_biz = _MAX_BUSINESSES["professional"] if sub.status == "trialing" else _MAX_BUSINESSES.get(sub.plan.slug, 0)
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
        starter_plan = SubscriptionPlan.objects.get(slug="basic")
    except SubscriptionPlan.DoesNotExist:
        try:
            starter_plan = SubscriptionPlan.objects.get(slug="starter")
        except SubscriptionPlan.DoesNotExist:
            return

    sub.plan = starter_plan
    sub.save(update_fields=["plan"])
