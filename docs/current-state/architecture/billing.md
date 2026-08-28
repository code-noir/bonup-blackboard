# Billing Architecture

> Status: Generated from code
> Source of truth: current code first, docs second
> Generated: 2026-05-06

---

## 1. Overview

The billing domain manages subscription plans, Stripe-based payment flows, and feature gate enforcement. `SubscriptionPlan` rows define the feature set and limits for each tier; `UserSubscription` records link each user to one plan at a time and track per-period usage counters; `Invoice` records are written when Stripe confirms payment. New subscriptions are initiated through a Stripe Checkout Session (`POST /api/billing/checkout/`); existing subscribers manage or cancel via a Stripe Billing Portal Session (`POST /api/billing/portal/`). Stripe delivers lifecycle events (subscription created, updated, cancelled, invoice paid/failed) to `POST /api/billing/webhook/`, which verifies the signature and dispatches to one of five handlers that keep local state in sync. Feature access across all other domains is resolved exclusively through gate functions in `backend/billing/gates.py` — no domain inspects plan fields directly. A trial lifecycle (`start_trial`, `consume_trial_contract`) and a Sol-group auto-upgrade/auto-downgrade lifecycle (`auto_upgrade_to_sol_member`, `auto_downgrade_from_sol_member`) are also defined here.

---

## 2. Models

### 2.1 SubscriptionPlan

**File:** `backend/billing/models.py:9`

| Field | Type | Notes |
|---|---|---|
| `slug` | `SlugField(max_length=50, unique=True)` | Plan identifier used by gates and Stripe price mapping |
| `display_name` | `CharField(max_length=100)` | Human-readable label |
| `price_monthly` | `DecimalField(max_digits=8, decimal_places=2)` | |
| `price_yearly` | `DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)` | |
| `max_active_contracts` | `PositiveIntegerField(null=True, blank=True)` | `null` = unlimited |
| `max_live_sessions_per_month` | `PositiveIntegerField(null=True, blank=True)` | `null` = unlimited; `0` = feature not included |
| `has_lifecycle` | `BooleanField(default=False)` | |
| `has_notifications` | `BooleanField(default=False)` | |
| `has_negotiation_prep` | `BooleanField(default=False)` | |
| `all_templates` | `BooleanField(default=False)` | |
| `excluded_categories` | `JSONField(default=list)` | Categories blocked on this plan |
| `templates_per_category` | `PositiveIntegerField(null=True, blank=True)` | Instantiation limit; not a view gate |
| `has_sol` | `BooleanField(default=False)` | Sol group management eligibility |
| `ai_tier` | `CharField(max_length=20, choices=AI_TIER_CHOICES, default="none")` | See AI tier choices below |
| `has_priority_support` | `BooleanField(default=False)` | |
| `has_early_access` | `BooleanField(default=False)` | |
| `is_active` | `BooleanField(default=True)` | Only active plans are returned by `GET /api/billing/plans/` |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

**AI tier choices** (`backend/billing/models.py:11`):

| Value | Label |
|---|---|
| `none` | None |
| `basic` | Basic |
| `advanced` | Advanced |
| `full` | Full |

**Meta:** `ordering = ["price_monthly"]` (`backend/billing/models.py:48`)

**Plan slugs referenced in code** — sources noted per slug:

| Slug | Referenced in |
|---|---|
| `starter` | `services.py:28`, `gates.py:269`, `gates.py:386` |
| `professional` | `services.py:28`, `gates.py:265` |
| `business` | `services.py:28`, `gates.py:213`, `gates.py:267` |
| `anchor` | `services.py:28`, `gates.py:268` |
| `per_contract` | `gates.py:26`, `gates.py:147`, `gates.py:263` |
| `sol_member` | `gates.py:128`, `gates.py:339`, `gates.py:372` |
| `trial` | `gates.py:262`, `gates.py:330` (legacy slug, see §9) |
| `blackboard_basic` | `gates.py:269` (current slug, see §9) |
| `blackboard_pro` | `gates.py:270` |
| `blackboard_business` | `gates.py:271` |
| `blackboard_enterprise` | `gates.py:272` |

No plan fixture or seed data is present in the codebase. See §9 (Current Gaps).

---

### 2.2 UserSubscription

**File:** `backend/billing/models.py:55`

One row per user (`OneToOneField` to User). `plan` is a `ForeignKey` with `on_delete=PROTECT`.

| Field | Type | Notes |
|---|---|---|
| `user` | `OneToOneField(User, related_name="subscription")` | |
| `plan` | `ForeignKey(SubscriptionPlan, on_delete=PROTECT, related_name="subscriptions")` | |
| `status` | `CharField(max_length=20, choices=STATUS_CHOICES, default="active")` | See choices below |
| `billing_period` | `CharField(max_length=20, choices=BILLING_PERIOD_CHOICES, default="monthly")` | See choices below |
| `current_period_start` | `DateTimeField` | Required; set by both webhook sync and direct POST |
| `current_period_end` | `DateTimeField(null=True, blank=True)` | Set by Stripe sync; `null` for non-Stripe subs |
| `contracts_used_this_period` | `PositiveIntegerField(default=0)` | Reset to 0 on `invoice.paid`; incremented by `increment_contracts_used` |
| `live_sessions_used_this_month` | `PositiveIntegerField(default=0)` | Reset to 0 on `invoice.paid`; incremented by `increment_sessions_used` |
| `trial_contracts_remaining` | `PositiveIntegerField(default=0)` | Relevant only when `status="trialing"` |
| `stripe_customer_id` | `CharField(max_length=255, blank=True, default="")` | Empty string for non-Stripe subs |
| `stripe_subscription_id` | `CharField(max_length=255, blank=True, default="")` | Empty string for non-Stripe subs |
| `created_at` | `DateTimeField(auto_now_add=True)` | |
| `updated_at` | `DateTimeField(auto_now=True)` | |

**Status choices** (`backend/billing/models.py:57`):

| Value | Meaning |
|---|---|
| `active` | Subscription is active |
| `cancelled` | Cancelled (locally or via Stripe) |
| `past_due` | Payment failed or subscription is past due |
| `trialing` | On a free trial |
| `per_contract` | Pay-as-you-go; set when plan slug is `per_contract` |
| `no_subscription` | Trial exhausted; no active plan |

**Billing period choices** (`backend/billing/models.py:66`):

| Value |
|---|
| `monthly` |
| `yearly` |
| `per_contract` |

**Meta:** `ordering = ["-created_at"]` (`backend/billing/models.py:107`)

---

### 2.3 Invoice

**File:** `backend/billing/models.py:113`

| Field | Type | Notes |
|---|---|---|
| `user` | `ForeignKey(User, on_delete=CASCADE, related_name="invoices")` | |
| `subscription` | `ForeignKey(UserSubscription, on_delete=SET_NULL, null=True, blank=True, related_name="invoices")` | Set null on sub deletion |
| `amount` | `DecimalField(max_digits=10, decimal_places=2)` | Converted from Stripe cents at write time |
| `currency` | `CharField(max_length=3, default="USD")` | Uppercased from Stripe currency string |
| `status` | `CharField(max_length=20, choices=STATUS_CHOICES, default="pending")` | See choices below |
| `description` | `TextField(blank=True, default="")` | From Stripe invoice `description` field, or `"Stripe invoice"` |
| `stripe_invoice_id` | `CharField(max_length=255, blank=True, default="")` | Used as the upsert key in `handle_invoice_paid` |
| `created_at` | `DateTimeField(auto_now_add=True)` | |
| `paid_at` | `DateTimeField(null=True, blank=True)` | Set to `timezone.now()` when Stripe fires `invoice.paid` |

**Status choices** (`backend/billing/models.py:115`):

| Value |
|---|
| `pending` |
| `paid` |
| `failed` |

**Meta:** `ordering = ["-created_at"]` (`backend/billing/models.py:142`)

---

## 3. Core Concepts

### 3.1 What a plan is

`SubscriptionPlan` is a database record. Every feature flag, limit, and tier setting is stored as a model field. The set of plan slugs that can be purchased through Stripe Checkout is hardcoded in `services.py:28` as `{"starter", "professional", "business", "anchor"}`. Plans outside that set (`trial`, `sol_member`, `per_contract`, legacy slugs) are not self-serve.

### 3.2 What a subscription is

`UserSubscription` is a one-to-one record per user. It stores the current plan, status, billing period, usage counters, and Stripe IDs. When Stripe is active, the subscription state is authoritative at Stripe and reflected locally by webhooks. When Stripe is not configured, the subscription state is written directly by `SubscriptionAPIView.post()`.

### 3.3 Feature resolution

Feature access is resolved exclusively through functions in `backend/billing/gates.py`. No domain reads `UserSubscription` or `SubscriptionPlan` directly. Two resolution paths exist:

- **Boolean feature flags**: `has_feature(user, feature_name)` (`gates.py:159`) returns the value of the corresponding `has_*` field on the plan. Supported `feature_name` values: `lifecycle`, `notifications`, `negotiation_prep`, `sol`, `priority_support`, `early_access`.
- **Resource creation gates**: `can_create_contract`, `can_create_session`, `can_create_sol`, `can_join_sol`, `can_access_template`, `can_create_business_entity` each return `(bool, str)`. A `False` result includes a human-readable message the caller may surface to the user.

All gate functions catch `UserSubscription.DoesNotExist` and return a blocked result rather than raising. (`gates.py:9`)

### 3.4 Usage tracking

Two counters on `UserSubscription` track current-period usage: `contracts_used_this_period` and `live_sessions_used_this_month`. Both are incremented atomically via `F()` expressions (`gates.py:187–196`). Both are reset to 0 when `handle_invoice_paid` fires (`services.py:263–266`). Both are reset to 0 when `SubscriptionAPIView.post()` directly writes a plan change (`views.py:143–144`).

### 3.5 Stripe-dependent vs. Stripe-independent paths

`stripe_configured()` (`stripe_client.py:17`) returns `True` if `STRIPE_SECRET_KEY` is non-empty. When `True`:
- `SubscriptionAPIView.post()` returns `HTTP 403` and refuses to write a plan directly (`views.py:104`).
- `CheckoutSessionAPIView.post()` and `BillingPortalAPIView.post()` are the only subscription-modification paths.

When `False`:
- `SubscriptionAPIView.post()` writes plan and status directly to `UserSubscription` without Stripe involvement.
- `CheckoutSessionAPIView.post()` and `BillingPortalAPIView.post()` return `HTTP 503`.

### 3.6 Trial lifecycle

`start_trial(user)` (`gates.py:204`) creates a `UserSubscription` with `status="trialing"`, `plan=business`, and `trial_contracts_remaining=1`. It is idempotent (uses `get_or_create`). **`start_trial` is not called from any production code path — it is only called from tests** (`backend/api/tests/test_billing.py`). See §9.

`consume_trial_contract(user)` (`gates.py:230`) decrements `trial_contracts_remaining` by 1 for trialing users. When it reaches 0, status transitions to `no_subscription`. It is called after a contract is created in `backend/api/contracts/viewsets/contract_viewset.py:48` and in two places in `backend/api/ai/views.py` (lines 222 and 311 and 727).

### 3.7 Sol auto-upgrade / auto-downgrade

`auto_upgrade_to_sol_member(user)` (`gates.py:333`) is called when a user joins a Sol group. If the user has no subscription or is on a plan listed in `_LOWER_THAN_SOL_MEMBER` (currently only `{"trial"}`), the subscription is written to `sol_member/active`. No-op for users already at `sol_member` or higher.

`auto_downgrade_from_sol_member(user)` (`gates.py:363`) is called when a user leaves a Sol group. If the user is on `sol_member` and has no remaining active `SolMember` rows, the plan is downgraded to `starter`. No-op otherwise.

Both are called from `backend/api/sol/views.py:15`.

---

## 4. Current Behavior (API Routes)

Default permission class for all routes is `IsAuthenticated` (DRF project default). The webhook endpoint overrides this; see §5.

### Route 1 — `GET /api/billing/plans/`

| | |
|---|---|
| **View** | `PlanListAPIView.get` (`views.py:78`) |
| **Permission** | `IsAuthenticated` (project default) |
| **What it does** | Returns all `SubscriptionPlan` rows where `is_active=True`, ordered by `price_monthly`. No pagination. |
| **State transitions** | None |
| **Side effects** | None |

---

### Route 2 — `GET /api/billing/subscription/`

| | |
|---|---|
| **View** | `SubscriptionAPIView.get` (`views.py:94`) |
| **Permission** | `IsAuthenticated` |
| **What it does** | Returns the calling user's `UserSubscription` with the embedded plan object. Returns `{"subscription": null}` if no subscription exists. |
| **State transitions** | None |
| **Side effects** | None |

---

### Route 3 — `POST /api/billing/subscription/`

| | |
|---|---|
| **View** | `SubscriptionAPIView.post` (`views.py:101`) |
| **Permission** | `IsAuthenticated` |
| **What it does** | When `STRIPE_SECRET_KEY` is set: returns `HTTP 403` with a redirect hint to `/api/billing/checkout/`. When not set: creates or updates `UserSubscription` directly. Accepts `plan_slug` and `billing_period`. Sets `status` to `"per_contract"` when `plan_slug == "per_contract"`, otherwise `"active"`. Resets usage counters. |
| **State transitions** | Creates or updates `UserSubscription`. |
| **Side effects** | No Stripe calls. |

---

### Route 4 — `DELETE /api/billing/subscription/`

| | |
|---|---|
| **View** | `SubscriptionAPIView.delete` (`views.py:158`) |
| **Permission** | `IsAuthenticated` |
| **What it does** | Sets the calling user's `UserSubscription.status` to `"cancelled"`. Returns `{"status": "cancelled"}`. Returns `HTTP 404` if no subscription exists. |
| **State transitions** | `UserSubscription.status → "cancelled"` |
| **Side effects** | No Stripe calls. Does not cancel the Stripe subscription. |

---

### Route 5 — `GET /api/billing/invoices/`

| | |
|---|---|
| **View** | `InvoiceListAPIView.get` (`views.py:180`) |
| **Permission** | `IsAuthenticated` |
| **What it does** | Returns a paginated list of `Invoice` rows for the calling user, ordered by `-created_at`. Page size is 20 (`views.py:178`). Accepts `?page=N` query param. Response includes `count`, `page`, `page_size`, `results`. |
| **State transitions** | None |
| **Side effects** | None |

---

### Route 6 — `GET /api/billing/usage/`

| | |
|---|---|
| **View** | `UsageAPIView.get` (`views.py:206`) |
| **Permission** | `IsAuthenticated` |
| **What it does** | Returns `contracts_used`, `contracts_limit`, `sessions_used_this_month`, `sessions_limit_per_month`, `billing_period`, `current_period_start`, `current_period_end` from the calling user's subscription and plan. Returns `{"subscription": null, "usage": null}` if no subscription. |
| **State transitions** | None |
| **Side effects** | None |

---

### Route 7 — `GET /api/billing/trial/`

| | |
|---|---|
| **View** | `TrialStatusAPIView.get` (`views.py:231`) |
| **Permission** | `IsAuthenticated` |
| **What it does** | Returns `is_trial` (status == "trialing"), `trial_expired` (status == "no_subscription"), `trial_contracts_remaining`, `plan` (slug), `status`. Returns defaults with `false`/`0`/`null` if no subscription exists. |
| **State transitions** | None |
| **Side effects** | None |

---

### Route 8 — `POST /api/billing/checkout/`

| | |
|---|---|
| **View** | `CheckoutSessionAPIView.post` (`views.py:269`) |
| **Permission** | `IsAuthenticated` |
| **What it does** | Requires `STRIPE_SECRET_KEY` (returns `HTTP 503` if absent). Accepts `plan_slug`, `success_url`, `cancel_url`. `plan_slug` must be in `CHECKOUT_ALLOWED_PLANS` (`{"starter", "professional", "business", "anchor"}`). Calls `create_checkout_session` which calls `get_or_create_stripe_customer` and then `stripe.checkout.Session.create`. Returns `{"checkout_url": session["url"]}` with `HTTP 201`. |
| **State transitions** | May create `stripe_customer_id` on `UserSubscription` (via `get_or_create_stripe_customer`). Subscription state is updated by the subsequent webhook. |
| **Side effects** | Stripe API call. May create a Stripe Customer object. |

---

### Route 9 — `POST /api/billing/portal/`

| | |
|---|---|
| **View** | `BillingPortalAPIView.post` (`views.py:328`) |
| **Permission** | `IsAuthenticated` |
| **What it does** | Requires `STRIPE_SECRET_KEY` (returns `HTTP 503` if absent). Accepts `return_url`. Requires user to have a `stripe_customer_id` on their subscription (returns `HTTP 400` via `ValueError` if not). Calls `create_portal_session` → `stripe.billing_portal.Session.create`. Returns `{"portal_url": session["url"]}` with `HTTP 201`. |
| **State transitions** | None locally; subscription changes via the portal are delivered by webhook. |
| **Side effects** | Stripe API call. |

---

### Route 10 — `POST /api/billing/webhook/`

| | |
|---|---|
| **View** | `WebhookAPIView.post` (`views.py:376`) |
| **Permission** | `AllowAny` — no authentication (`authentication_classes = []`, `permission_classes = [AllowAny]`, `@csrf_exempt`) |
| **What it does** | See §5 (Webhook Flow). |
| **State transitions** | See §5. |
| **Side effects** | See §5. |

---

## 5. Webhook Flow

**Entry point:** `POST /api/billing/webhook/` → `WebhookAPIView.post` (`views.py:376`)

### Signature verification

1. Reads `STRIPE_WEBHOOK_SECRET` from settings (`views.py:380`). If absent, returns `HTTP 503`.
2. Reads raw `request.body` and `HTTP_STRIPE_SIGNATURE` header.
3. Calls `stripe.Webhook.construct_event(payload, sig_header, webhook_secret)` (`views.py:393`).
4. `ValueError` (invalid payload) → `HTTP 400`.
5. `SignatureVerificationError` → `HTTP 400`.

### Dispatch table

(`views.py:402`)

| Stripe event | Handler |
|---|---|
| `checkout.session.completed` | `services.handle_checkout_completed` |
| `customer.subscription.updated` | `services.handle_subscription_updated` |
| `customer.subscription.deleted` | `services.handle_subscription_deleted` |
| `invoice.paid` | `services.handle_invoice_paid` |
| `invoice.payment_failed` | `services.handle_invoice_payment_failed` |
| All other events | Logged at DEBUG; no action taken |

### Handler behavior

**`handle_checkout_completed(session)`** (`services.py:152`)
- Reads `bonup_user_id` and `plan_slug` from session `metadata`. Logs a warning and returns if either is missing.
- Retrieves the Stripe Subscription by ID from Stripe API.
- Calls `_sync_subscription_from_stripe` to write/update the local `UserSubscription`.

**`handle_subscription_updated(stripe_sub)`** (`services.py:183`)
- Reads `bonup_user_id` from `metadata`. Logs a warning and returns if missing.
- Derives `plan_slug` from metadata if present; otherwise calls `_plan_slug_from_stripe_sub` to reverse-look up the Stripe price ID against `STRIPE_PRICE_IDS`. Falls back to `"starter"` if not found (`services.py:343`).
- Calls `_sync_subscription_from_stripe`.

**`handle_subscription_deleted(stripe_sub)`** (`services.py:208`)
- Reads `bonup_user_id` from `metadata`. If present, sets `status="cancelled"` on the matching `UserSubscription` by `user_id`.
- If `bonup_user_id` is absent, falls back to looking up by `stripe_subscription_id`. Logs a warning if no record found.

**`handle_invoice_paid(stripe_invoice)`** (`services.py:232`)
- Resolves `user_id` from `stripe_customer_id` via `_user_id_from_customer`. Logs a warning and returns if not found.
- In a single `transaction.atomic`: upserts `Invoice` by `stripe_invoice_id` with `status="paid"` and `paid_at=timezone.now()`; resets `contracts_used_this_period=0` and `live_sessions_used_this_month=0` on the user's `UserSubscription`.
- Amount is converted from Stripe cents (integer) to `Decimal` by dividing by 100 (`services.py:248`).

**`handle_invoice_payment_failed(stripe_invoice)`** (`services.py:269`)
- Resolves `user_id` from `stripe_customer_id`. Logs a warning and returns if not found.
- Sets `status="past_due"` on the user's `UserSubscription`.

### Error handling

Application-level exceptions inside any handler are caught and logged at ERROR level (`views.py:415`). The view always returns `HTTP 200 {"received": true}` after signature verification, even on handler errors, to prevent Stripe from retrying. (`views.py:417` comment)

### Internal helpers

**`_sync_subscription_from_stripe(bonup_user_id, plan_slug, stripe_sub, stripe_customer_id)`** (`services.py:290`)  
Maps Stripe status to local status using `_STRIPE_TO_LOCAL_STATUS` (`services.py:31`). Converts Unix timestamps to UTC `datetime`. Calls `update_or_create` on `UserSubscription` by `user_id`. Always sets `billing_period="monthly"` regardless of the Stripe interval. See §9.

**`_plan_slug_from_stripe_sub(stripe_sub)`** (`services.py:331`)  
Inverts `STRIPE_PRICE_IDS` dict, looks up the first line-item price ID, returns slug or `"starter"`.

**`_user_id_from_customer(stripe_customer_id)`** (`services.py:347`)  
Looks up `UserSubscription` by `stripe_customer_id`, returns `user_id` or `None`.

**Stripe status → local status mapping** (`services.py:31`):

| Stripe status | Local status |
|---|---|
| `active` | `active` |
| `trialing` | `trialing` |
| `past_due` | `past_due` |
| `canceled` | `cancelled` |
| `unpaid` | `past_due` |
| `incomplete` | `past_due` |
| `incomplete_expired` | `cancelled` |
| `paused` | `past_due` |

---

## 6. Feature Gates

All gate functions are in `backend/billing/gates.py`. None raise exceptions. All handle `UserSubscription.DoesNotExist` internally.

Active statuses checked by most gates (`gates.py:17`): `{"active", "trialing", "per_contract"}`

| Function | Signature | Purpose |
|---|---|---|
| `get_user_subscription(user)` | `→ UserSubscription \| None` | Returns `UserSubscription.select_related("plan")` or `None`. Shared lookup used by most other gates. (`gates.py:29`) |
| `is_payg(user)` | `→ bool` | Returns `True` if the user's plan slug is `"per_contract"`. (`gates.py:23`) |
| `can_create_contract(user)` | `→ (bool, str)` | Checks: subscription exists, status is active, trial not exhausted (for trialing), `max_active_contracts` not exceeded. (`gates.py:37`) |
| `can_create_session(user)` | `→ (bool, str)` | Checks: subscription exists, status is active, `max_live_sessions_per_month` is not `0` (not included), not exceeded. (`gates.py:66`) |
| `can_access_template(user, template)` | `→ (bool, str)` | Checks: subscription exists (bypassed in `DEBUG`), status is active, template's category not in `plan.excluded_categories`. (`gates.py:90`) |
| `can_create_sol(user)` | `→ (bool, str)` | Checks: subscription exists, active, not trialing, not `sol_member` plan, `plan.has_sol=True`. (`gates.py:114`) |
| `can_join_sol(user)` | `→ (bool, str)` | Checks: subscription exists, active, plan slug is not `"per_contract"`. (`gates.py:135`) |
| `get_ai_tier(user)` | `→ str` | Returns `plan.ai_tier` or `"none"` if no subscription. (`gates.py:151`) |
| `has_feature(user, feature_name)` | `→ bool` | Generic flag check against plan `has_*` fields. Supported keys: `lifecycle`, `notifications`, `negotiation_prep`, `sol`, `priority_support`, `early_access`. Returns `False` for unknown keys. (`gates.py:159`) |
| `increment_contracts_used(user)` | `→ None` | Atomic `F()+1` on `contracts_used_this_period`. (`gates.py:186`) |
| `increment_sessions_used(user)` | `→ None` | Atomic `F()+1` on `live_sessions_used_this_month`. (`gates.py:192`) |
| `start_trial(user)` | `→ None` | Creates `UserSubscription` with `status="trialing"`, `plan=business`, `trial_contracts_remaining=1`. Idempotent. (`gates.py:204`) |
| `consume_trial_contract(user)` | `→ None` | Decrements `trial_contracts_remaining` for trialing users; transitions to `no_subscription` at 0. (`gates.py:230`) |
| `max_businesses(user)` | `→ int` | Returns max business entities from `_MAX_BUSINESSES` dict keyed by plan slug. Returns `_DEV_MAX_BUSINESSES` (35) in `DEBUG` with no subscription; returns 0 in prod with no subscription. (`gates.py:279`) |
| `can_create_business_entity(user)` | `→ (bool, str)` | Checks active status, then checks current `BusinessEntity` count against `_MAX_BUSINESSES[plan.slug]`. (`gates.py:288`) |
| `auto_upgrade_to_sol_member(user)` | `→ None` | Upgrades to `sol_member` plan on Sol group join for users with no sub or a sub in `_LOWER_THAN_SOL_MEMBER`. (`gates.py:333`) |
| `auto_downgrade_from_sol_member(user)` | `→ None` | Downgrades `sol_member` → `starter` when user leaves all Sol groups. (`gates.py:363`) |

### Cross-domain consumer table

The following files import from `backend/billing/gates` in production code (excluding test files):

| File | Gates consumed |
|---|---|
| `backend/api/contracts/viewsets/contract_viewset.py:9` | `can_create_contract`, `consume_trial_contract`, `increment_contracts_used` |
| `backend/api/sessions/views.py:15` | `can_create_session`, `increment_sessions_used` |
| `backend/api/templates/views.py:10` | `can_access_template` |
| `backend/api/obligations/views.py:54` | `has_feature` (checked against `"lifecycle"` at line 117) |
| `backend/api/payments/views.py:19` | `has_feature` (checked against `"lifecycle"` at lines 110, 119) |
| `backend/api/prep/views.py:14` | `has_feature` (checked against `"negotiation_prep"` at lines 81, 87) |
| `backend/api/sol/views.py:15` | `can_create_sol`, `can_join_sol`, `auto_upgrade_to_sol_member`, `auto_downgrade_from_sol_member` |
| `backend/api/entities/views.py:11` | `can_create_business_entity`, `max_businesses` |
| `backend/api/ai/views.py:21` | `get_ai_tier`, `get_user_subscription`, `has_feature` |
| `backend/api/ai/views.py:195,235,723` | `can_create_contract`, `increment_contracts_used`, `consume_trial_contract` (inline imports at 3 call sites) |
| `backend/api/users/serializers.py:150` | `max_businesses` (inline import in serializer method) |
| `backend/ai/context.py:8` | `get_ai_tier`, `get_user_subscription` |

---

## 7. Authority / Access Rules

- All billing API routes require `IsAuthenticated` (DRF project default). No view sets a role-based permission class (no admin-only, no staff-only gates at the view layer).
- `WebhookAPIView` explicitly overrides to `authentication_classes = []` and `permission_classes = [AllowAny]` (`views.py:369–370`). Authorization is via Stripe signature verification only.
- No distinction between user roles within billing. Any authenticated user can read their own subscription, usage, invoices, and trial status.

---

## 8. Relationship to Other Domains

### Payments (`backend/billing/`)

Stripe is owned entirely by the billing domain. The payments domain (`backend/payments/`, documented in `payments.md`) handles `Payment` and `ContractObligation` records but does not touch Stripe objects. The `has_feature(user, "lifecycle")` gate consumed in `backend/api/payments/views.py` is the only billing-to-payments link at the code level.

### Contracts (`backend/api/contracts/`)

`can_create_contract`, `consume_trial_contract`, and `increment_contracts_used` are called in `contract_viewset.py` before and after a contract is created. Contracts does not read billing models directly.

### Sessions (`backend/api/sessions/`)

`can_create_session` and `increment_sessions_used` are called in `sessions/views.py` before and after a live session is created.

### Sol (`backend/api/sol/`, `backend/sol/`)

`can_create_sol` and `can_join_sol` gate Sol group creation and membership. `auto_upgrade_to_sol_member` and `auto_downgrade_from_sol_member` modify `UserSubscription` when Sol membership changes. `auto_downgrade_from_sol_member` imports `backend.sol.models.SolMember` directly (`gates.py:377`).

### AI (`backend/api/ai/`, `backend/ai/`)

`get_ai_tier` and `get_user_subscription` are used in `backend/ai/context.py` and `backend/api/ai/views.py` to gate AI features by tier. `can_create_contract`, `increment_contracts_used`, and `consume_trial_contract` are also called from `backend/api/ai/views.py` at three separate call sites (lines 195, 235, 723) — the AI domain can create contracts directly and enforces the same billing gates as the contracts domain.

### Entities (`backend/api/entities/`, `backend/users/`)

`can_create_business_entity` and `max_businesses` gate business entity creation. `max_businesses` is also used in `backend/api/users/serializers.py` to embed the limit in the user profile response.

### Obligations / Prep

`has_feature(user, "lifecycle")` is checked before obligation-related actions in `backend/api/obligations/views.py` and `backend/api/payments/views.py`. `has_feature(user, "negotiation_prep")` is checked in `backend/api/prep/views.py`.

---

## 9. Current Gaps

1. **No plan seed or fixture.** `SubscriptionPlan` rows must exist in the database for any gate to function. No migration, fixture, or management command that creates initial plan rows was found in the codebase. How rows are populated in production is not established in code.

2. **`_MAX_BUSINESSES` contains both legacy and current slugs.** (`gates.py:259`) Legacy slugs (`trial`, `starter`, `professional`, `business`, `anchor`) and current slugs (`blackboard_basic`, `blackboard_pro`, `blackboard_business`, `blackboard_enterprise`) both appear. Whether the legacy slugs correspond to active `SubscriptionPlan` rows in production, or are dead, is not established in code. Any plan slug not in `_MAX_BUSINESSES` silently returns `0` from `max_businesses` and blocks business entity creation.

3. **`SubscriptionAPIView.post()` allows direct plan changes when `STRIPE_SECRET_KEY` is unset.** (`views.py:101`) The code comment says "dev/test only" but this is enforced only by the absence of the secret key — it is not a separate flag, environment check, or `DEBUG` gate. The intent for whether this path should ever be reachable in production is not established in code.

4. **`billing_period` is always written as `"monthly"` by Stripe sync.** `_sync_subscription_from_stripe` unconditionally sets `billing_period="monthly"` (`services.py:322`). The model defines `"yearly"` and `"per_contract"` as valid choices but no code path writes them via Stripe sync. Yearly pricing exists (`price_yearly` field on `SubscriptionPlan`; `STRIPE_PRICE_IDS` keys in settings only cover monthly price IDs — `settings.py:237`). Whether yearly billing is intentionally deferred or an oversight is not established in code.

5. **`start_trial` is not called from any production code path.** `start_trial` is defined in `gates.py:204` and called only from test code (`backend/api/tests/test_billing.py`). There is no user registration signal, view, or management command in the codebase that calls it. How new users actually receive a trial subscription in production is not established in code.

---

## 10. Open Questions

1. **Plan population**: What is the intended mechanism for creating `SubscriptionPlan` rows in a production environment? A management command, a data migration, or manual admin entry?

2. **Legacy slug retirement**: Are the legacy slugs in `_MAX_BUSINESSES` (`trial`, `starter`, `professional`, `business`, `anchor`) still present in any `SubscriptionPlan` table in any environment, or have they been replaced by the `blackboard_*` slugs? If the latter, the legacy slug logic in `_MAX_BUSINESSES` is unreachable.

3. **Trial trigger**: `start_trial` exists and is tested but is not wired to any user registration event. Was automatic trial assignment removed from a prior registration flow, or was it never wired and the trial flow is manually triggered only?

4. **Yearly billing**: The `price_yearly` field, the `"yearly"` `billing_period` choice, and the `"Per Contract"` period choice exist in the model, but Stripe price ID configuration only covers monthly plans, and `_sync_subscription_from_stripe` always writes `"monthly"`. Is yearly billing planned but not implemented?

5. **`per_contract` billing**: The `billing_period="per_contract"` choice exists in the model. `SubscriptionAPIView.post()` accepts it as a valid value. No Stripe price ID for a per-contract plan appears in `STRIPE_PRICE_IDS`. Whether this billing period is fully functional or a stub is not established in code.

6. **`sol_member` plan in `_LOWER_THAN_SOL_MEMBER`**: `_LOWER_THAN_SOL_MEMBER = {"trial"}` (`gates.py:330`). Users on `per_contract`, `starter`, or any other plan that is not in this set will not be upgraded to `sol_member` by `auto_upgrade_to_sol_member` — the function silently no-ops. Whether this is intentional (i.e., only `trial` users should auto-upgrade) is not established in a comment.

---

## 11. Update Rule

Update this file when code changes any of: billing models, Stripe integration, webhook handlers, gate functions, API routes, or cross-domain gate call sites.


---

## 12. Store Checkout Test-Mode Foundation

> Updated: 2026-08-28

`POST /api/billing/checkout/` now starts the Store payment flow from the same customer selection shape used by `POST /api/billing/quote/`. The backend re-runs `build_store_quote()` before creating Stripe Checkout, snapshots the authoritative selection/quote in `StoreCheckout`, and generates Stripe Checkout `price_data` from bonUP `Product` / `ProductPrice` state instead of trusting frontend totals or requiring Stripe Price IDs for Store products.

Store Checkout is test-mode only in this phase. The endpoint requires `STRIPE_SECRET_KEY` to start with `sk_test_`; hosted Checkout redirects back to `FRONTEND_URL/store/payment/success?session_id={CHECKOUT_SESSION_ID}`. `STRIPE_WEBHOOK_SECRET` is still required for webhook processing.

Checkout modes:

| bonUP quote contents | Stripe Checkout mode | Line item shape |
|---|---|---|
| Storage only | `payment` | one-time `price_data` only |
| Blackbòd only | `subscription` | recurring `price_data` with `month` or `year` interval |
| Blackbòd + Storage | `subscription` | recurring Blackbòd line plus one-time Storage line on initial checkout/invoice |

`GET /api/billing/checkout/<session_id>/status/` returns only the authenticated user's safe bonUP checkout status and item summary. It does not expose raw Stripe objects, Stripe customer IDs, provider economics, or secrets.

Webhook handling now routes `checkout.session.completed` and `checkout.session.async_payment_succeeded` Store events to idempotent fulfillment when `metadata.bonup_checkout_id` is present. It handles `checkout.session.async_payment_failed` and `checkout.session.expired` by marking the local attempt failed/expired without granting resources. Legacy subscription webhook handlers remain available for non-Store events.

Fulfillment retrieves the Stripe Checkout Session and requires `payment_status == "paid"` before granting resources. The MVP uses card-only Checkout sessions to avoid delayed payment method fulfillment risk. A transaction and row lock on `StoreCheckout` protect webhook retries and concurrent processing. Blackbòd fulfillment updates the canonical `UserSubscription` / `ToolEntitlement` bridge and stores Stripe customer/subscription IDs. Storage fulfillment creates one `StoragePurchase` from the checkout snapshot and calls `complete_storage_purchase()` so exactly one purchase-origin `StorageCapacityGrant` is created.
