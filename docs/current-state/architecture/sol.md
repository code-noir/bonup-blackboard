# Sol Domain Architecture

> Status: Generated from code
> Source of truth: current code first, docs second
> Generated: 2026-05-06

---

## 1. Overview

The Sol domain implements a rotating savings and contribution group system — a structure traditionally known as sou-sou, tontine, or susu. A `Sol` group is managed by one primary manager (optionally with a co-manager) and has a set of members, each assigned a unique hand number. The group runs on a fixed contribution frequency (weekly, biweekly, or monthly); each cycle one member receives a pooled payout funded by contributions from all other members. The domain covers the full lifecycle: group creation, member onboarding, per-member participation agreements (`SolContract`), payout scheduling, per-member contribution tracking (`SolContribution`), rearrangement of payout recipients, tips, manager notes, and PDF export of group and personal records. All group identifiers use the format `SOL-XXXXX` (`backend/sol/models.py:15`); all payout identifiers use `PAY-XXXXX` (`models.py:19`). **This domain is entirely self-contained. `SolContract` has no relationship to `contracts.Contract`, `ContractVersion`, or any other model in the `backend/contracts/` app. They share only a naming coincidence.** All workflow is HTTP REST. There is no WebSocket layer, no Celery task, no Django signal, and no background processing in this domain.

---

## 2. Models

All models are in `backend/sol/models.py`.

### 2.1 Sol

**File:** `backend/sol/models.py:26`

The top-level group record.

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` | Internal PK |
| `sol_id` | `CharField(max_length=20, unique=True, default=_sol_id, editable=False)` | Human-readable ID; format `SOL-XXXXXXXX` (`models.py:14`) |
| `name` | `CharField(max_length=200)` | |
| `description` | `TextField(blank=True)` | |
| `primary_manager` | `ForeignKey(User, on_delete=PROTECT, related_name="managed_sols")` | Required; deletion protected |
| `co_manager` | `ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name="co_managed_sols")` | Optional second manager |
| `status` | `CharField(max_length=20, choices=STATUS_CHOICES, default="active")` | See choices below |
| `frequency` | `CharField(max_length=20, choices=FREQUENCY_CHOICES)` | See choices below |
| `contribution_amount` | `DecimalField(max_digits=12, decimal_places=2)` | Per-member contribution per period |
| `currency` | `CharField(max_length=10, choices=CURRENCY_CHOICES, default="USD")` | From `backend.core.currencies` |
| `tip_expectation` | `DecimalField(max_digits=12, decimal_places=2, default=0)` | Expected tip to manager per payout |
| `is_private` | `BooleanField(default=True)` | Purpose not established in code beyond storage |
| `sol_type` | `CharField(max_length=20, choices=SOL_TYPE_CHOICES, default="single")` | See choices below |
| `start_date` | `DateField()` | |
| `expected_end_date` | `DateField(null=True, blank=True)` | |
| `created_at` | `DateTimeField(auto_now_add=True)` | |
| `updated_at` | `DateTimeField(auto_now=True)` | |

**Meta:** `ordering = ["-created_at"]` (`models.py:88`)

**Status choices** (`models.py:28–33`): `active`, `paused`, `completed`, `cancelled`

**Frequency choices** (`models.py:35–39`): `weekly`, `biweekly`, `monthly`

**Sol type choices** (`models.py:41–44`): `single` (Single Cycle), `recurring` (Recurring). A single-cycle Sol blocks new payout creation after all hands are scheduled (`backend/api/sol/views.py:455`).

**Helper method:** `active_member_count()` (`models.py:94`) — returns count of `SolMember` rows with `is_active=True`.

---

### 2.2 SolMember

**File:** `backend/sol/models.py:102`

One row per participant slot in a Sol group.

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` | |
| `sol` | `ForeignKey(Sol, on_delete=CASCADE, related_name="members")` | |
| `bonup_user` | `ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name="sol_memberships")` | Optional; links to a registered bonUP account |
| `name` | `CharField(max_length=200)` | Required for all members |
| `email` | `CharField(max_length=255)` | |
| `phone` | `CharField(max_length=50)` | |
| `employer` | `CharField(max_length=200, blank=True)` | |
| `emergency_contact_name` | `CharField(max_length=200, blank=True)` | |
| `emergency_contact_phone` | `CharField(max_length=50, blank=True)` | |
| `is_bonup_member` | `BooleanField(default=False)` | Set to `True` when `bonup_user` is linked at add time |
| `hand_number` | `PositiveIntegerField()` | Position in payout rotation |
| `has_received` | `BooleanField(default=False)` | Set to `True` when payout is marked paid (`views.py:512`) |
| `is_manager_participant` | `BooleanField(default=False)` | `True` when the member is also the manager of this Sol (`views.py:329`) |
| `joined_at` | `DateTimeField(auto_now_add=True)` | |
| `is_active` | `BooleanField(default=True)` | Deactivation is soft-delete (`views.py:383`) |
| `notes` | `TextField(blank=True)` | |

**Meta:** `ordering = ["hand_number"]`; `unique_together = [("sol", "hand_number")]` (`models.py:132–134`)

---

### 2.3 SolContract

**File:** `backend/sol/models.py:144`

A per-member participation agreement auto-generated at member-add time. **Not related to `contracts.Contract`.** The name is a coincidence within the same codebase. `SolContract` has no FK or inheritance relationship to any model in `backend/contracts/`.

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` | |
| `sol` | `ForeignKey(Sol, on_delete=CASCADE, related_name="contracts")` | |
| `member` | `OneToOneField(SolMember, on_delete=CASCADE, related_name="contract")` | One contract per member |
| `agreed_contribution_amount` | `DecimalField(max_digits=12, decimal_places=2)` | Copied from `Sol.contribution_amount` at create time |
| `agreed_hand_number` | `PositiveIntegerField()` | Copied from member's hand number at create time |
| `agreed_tip_amount` | `DecimalField(max_digits=12, decimal_places=2)` | Copied from `Sol.tip_expectation` at create time |
| `contract_text` | `TextField()` | Auto-generated plaintext agreement (`views.py:125`) |
| `signed_by_member` | `BooleanField(default=False)` | Member signature flag; not enforced as a precondition by any view |
| `signed_at` | `DateTimeField(null=True, blank=True)` | |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

---

### 2.4 SolPayout

**File:** `backend/sol/models.py:169`

One row per scheduled payout cycle slot. Identifies which member receives the pooled fund for that cycle position.

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` | |
| `payout_id` | `CharField(max_length=20, unique=True, default=_pay_id, editable=False)` | Format `PAY-XXXXXXXX` (`models.py:19`) |
| `sol` | `ForeignKey(Sol, on_delete=CASCADE, related_name="payouts")` | |
| `cycle_number` | `PositiveIntegerField()` | Starts at 1; increments for recurring Sols |
| `hand_number` | `PositiveIntegerField()` | Which hand this payout covers |
| `recipient` | `ForeignKey(SolMember, on_delete=PROTECT, related_name="payouts_received")` | Deletion protected |
| `expected_date` | `DateField()` | |
| `paid_date` | `DateField(null=True, blank=True)` | Set when status → `paid` |
| `expected_amount` | `DecimalField(max_digits=12, decimal_places=2)` | Computed as `contribution_amount × (active_members − 1)` (`views.py:467`) |
| `actual_amount` | `DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)` | Set when status → `paid` |
| `status` | `CharField(max_length=20, choices=STATUS_CHOICES, default="upcoming")` | See choices below |
| `was_rearranged` | `BooleanField(default=False)` | Set to `True` on recipient swap |
| `original_recipient` | `ForeignKey(SolMember, on_delete=SET_NULL, null=True, blank=True, related_name="payouts_original")` | Preserved on rearrangement |
| `rearranged_reason` | `TextField(blank=True)` | Manager-provided reason on rearrangement |
| `rearranged_by` | `ForeignKey(User, on_delete=SET_NULL, null=True, blank=True, related_name="sol_rearrangements")` | Audit field |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

**Meta:** `ordering = ["cycle_number", "hand_number"]` (`models.py:224`)

**Status choices** (`models.py:171–176`): `upcoming`, `paid`, `delayed`, `missed`

---

### 2.5 SolContribution

**File:** `backend/sol/models.py:235`

One row per member per payout cycle. Represents one member's obligation to contribute to a given payout. The payout recipient does not get a contribution row.

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` | |
| `sol` | `ForeignKey(Sol, on_delete=CASCADE, related_name="contributions")` | |
| `payout` | `ForeignKey(SolPayout, on_delete=CASCADE, related_name="contributions")` | |
| `member` | `ForeignKey(SolMember, on_delete=CASCADE, related_name="contributions")` | |
| `amount` | `DecimalField(max_digits=12, decimal_places=2)` | |
| `status` | `CharField(max_length=20, choices=STATUS_CHOICES, default="pending")` | See choices below |
| `due_date` | `DateField()` | |
| `paid_date` | `DateField(null=True, blank=True)` | Set by manager when updating status to `paid` |
| `notes` | `TextField(blank=True)` | |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

**Meta:** `ordering = ["due_date"]`; `unique_together = [("payout", "member")]` (`models.py:260–261`)

**Status choices** (`models.py:237–242`): `pending`, `paid`, `late`, `missed`

---

### 2.6 SolTip

**File:** `backend/sol/models.py:271`

An optional gratuity payment from a member to the primary manager. Record-keeping only — bonUP does not process payments (`pdf_views.py:159–164`).

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` | |
| `sol` | `ForeignKey(Sol, on_delete=CASCADE, related_name="tips")` | |
| `from_member` | `ForeignKey(SolMember, on_delete=CASCADE, related_name="tips_given")` | |
| `to_manager` | `ForeignKey(User, on_delete=SET_NULL, null=True, related_name="sol_tips_received")` | Always set to `sol.primary_manager` at create time (`views.py:701`) |
| `amount` | `DecimalField(max_digits=12, decimal_places=2)` | |
| `currency` | `CharField(max_length=10, choices=CURRENCY_CHOICES, default="USD")` | |
| `note` | `TextField(blank=True)` | |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

---

### 2.7 SolNote

**File:** `backend/sol/models.py:298`

Manager-authored private notes on a Sol group. Not an audit log.

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid.uuid4, editable=False)` | |
| `sol` | `ForeignKey(Sol, on_delete=CASCADE, related_name="notes")` | |
| `author` | `ForeignKey(User, on_delete=SET_NULL, null=True, related_name="sol_notes")` | Preserved as null if user deleted |
| `text` | `TextField()` | |
| `created_at` | `DateTimeField(auto_now_add=True)` | |

**Meta:** `ordering = ["-created_at"]` (`models.py:313`)

---

## 3. Core Concepts

### 3.1 What a Sol is

A Sol is a named rotating savings group. The manager sets a `contribution_amount` and `frequency`. In each payout cycle, every member except the designated recipient contributes one `contribution_amount`. The recipient collects the pooled total. Hands rotate until all members have received. For `sol_type = "recurring"`, the group starts a new cycle after all hands are complete. For `sol_type = "single"`, creation of a new payout is blocked once all hands are scheduled (`backend/api/sol/views.py:454–455`).

### 3.2 Manager vs co-manager vs member

**Primary manager** (`Sol.primary_manager`) — required FK, deletion protected. Has full management authority.

**Co-manager** (`Sol.co_manager`) — optional FK. The helper `_is_manager(user, sol)` at `views.py:25–26` grants the same management authority as the primary manager. Authority check: `sol.primary_manager_id == user.pk or sol.co_manager_id == user.pk`. This is evaluated inline in every manager view via `_manager_sol_or_404` (`views.py:29–33`).

**Member** — a `SolMember` row. A member may or may not have a linked bonUP account (`bonup_user`). A manager can also be a participant by adding themselves as a member; this sets `is_manager_participant = True` (`views.py:329`).

### 3.3 bonUP user vs non-bonUP participant

`SolMember.bonup_user` is optional. Non-bonUP participants are tracked by name, email, and phone only. When a member's email matches a registered bonUP user, `bonup_user` is set at add time (`views.py:319`), `is_bonup_member` is set to `True` (`views.py:324`), and billing gates are checked and applied (`views.py:321–325`). Member self-service routes (memberships/, detail, PDF) are only accessible to members with a `bonup_user` link, because they authenticate via JWT and the view filters by `bonup_user=request.user` (`views.py:40`, `views.py:723`).

### 3.4 The rotating payout pattern

Each payout corresponds to one hand. When a manager creates a payout, the system auto-selects the next unscheduled hand in the current cycle (`views.py:461–466`) and auto-creates `SolContribution` rows for all active members except the recipient (`views.py:480–490`). The recipient's `has_received` flag is set to `True` when the payout is marked `paid` (`views.py:512–513`).

### 3.5 SolContract vs contracts.Contract — naming clarification

`SolContract` (`backend/sol/models.py:144`) is a per-member participation agreement record within the Sol domain. It is auto-generated text, optionally signed by the member, and stored as a text field. It has no FK or code relationship to `contracts.Contract` (`backend/contracts/models.py`) or `ContractVersion`. The two models exist independently in different Django apps and serve different purposes. Their names sharing the word "Contract" is a naming coincidence. Do not conflate them.

### 3.6 SolContribution as per-member-per-cycle obligation

Each `SolContribution` row represents one member's obligation to pay one contribution amount for one payout cycle. `unique_together = [("payout", "member")]` prevents duplicate rows. Status transitions (`pending` → `paid`/`late`/`missed`) are manual — the manager updates them via API. There is no automated transition logic.

### 3.7 No services layer

There is no `backend/sol/services.py`, `backend/sol/engine.py`, or equivalent. All business logic — contract text generation, contribution backfilling, payout cycle tracking, rearrangement, billing gate calls — lives inline in `backend/api/sol/views.py`. This is the current architecture; it is not a documented design choice — it is the observed state.

---

## 4. Current Behavior

All views are `APIView` subclasses. Default permission is `IsAuthenticated` (DRF project default, `backend/core/settings.py:256`). No view overrides the permission class.

### 4.1 Manager Views

---

#### `SolListCreateView`

**File:** `backend/api/sol/views.py:214`

| | |
|---|---|
| **Routes** | `GET /api/sol/`, `POST /api/sol/` |
| **Permission** | `IsAuthenticated` |
| **Manager check** | GET: filters by `primary_manager=user OR co_manager=user` (`views.py:218`). POST: calls `_manager_sol_or_404` is not used here; `can_create_sol` gate is checked directly (`views.py:224`). |

**GET** — Returns all Sol groups where the requesting user is primary or co-manager. No pagination. Response: `{results: [serialized Sol, ...]}`.

**POST** — Creates a new Sol. Required fields: `name`, `frequency`, `contribution_amount`, `start_date`. Billing gate `can_create_sol(request.user)` is checked before creation (`views.py:224`). Returns 403 if gate fails. `primary_manager` is always set to `request.user`.

**State transitions:** None on GET. POST creates a `Sol` row.

---

#### `SolDetailView`

**File:** `backend/api/sol/views.py:259`

| | |
|---|---|
| **Routes** | `GET /api/sol/<sol_id>/`, `PATCH /api/sol/<sol_id>/` |
| **Permission** | `IsAuthenticated` + `_is_manager` check |

**GET** — Returns full Sol detail including inline serialized active members and all payouts (`include_members=True, include_payouts=True`) (`views.py:266`).

**PATCH** — Updates any of: `name`, `description`, `status`, `is_private`, `expected_end_date`, `tip_expectation`, `co_manager`. `co_manager` can be set by passing a user PK or cleared by passing `null` (`views.py:277–283`).

**State transitions:** PATCH can change `Sol.status` to any valid choice.

---

#### `SolMemberListCreateView`

**File:** `backend/api/sol/views.py:296`

| | |
|---|---|
| **Routes** | `POST /api/sol/<sol_id>/members/` |
| **Permission** | `IsAuthenticated` + `_is_manager` check |

**POST** — Adds a member to the Sol. Required: `name`, `email`, `phone`, `hand_number`. If the email matches a registered bonUP user, the join billing gate is checked and the auto-upgrade is applied. Full membership flow described in Section 5. Wrapped in `transaction.atomic()` (`views.py:331`).

**State transitions:** Creates `SolMember`, `SolContract`. Optionally creates `SolContribution` for the current open payout period.

**Side effects:** Billing gate `can_join_sol` and `auto_upgrade_to_sol_member` called if `bonup_user` resolved (`views.py:321–325`).

---

#### `SolMemberDeleteView`

**File:** `backend/api/sol/views.py:375`

| | |
|---|---|
| **Routes** | `DELETE /api/sol/<sol_id>/members/<member_id>/` |
| **Permission** | `IsAuthenticated` + `_is_manager` check |

**DELETE** — Soft-deactivates a member by setting `is_active = False` (`views.py:383–384`). Does not delete the `SolMember` row or associated contribution/payout rows. If the member has a `bonup_user`, calls `auto_downgrade_from_sol_member` (`views.py:385–386`).

**State transitions:** `SolMember.is_active` → `False`.

---

#### `SolMemberContractView`

**File:** `backend/api/sol/views.py:390`

| | |
|---|---|
| **Routes** | `GET /api/sol/<sol_id>/members/<member_id>/contract/` |
| **Permission** | `IsAuthenticated` + `_is_manager` check |

**GET** — Returns the `SolContract` for a specific member. Read-only. No endpoint exists for updating `signed_by_member` via the manager view.

---

#### `SolPayoutListCreateView`

**File:** `backend/api/sol/views.py:416`

| | |
|---|---|
| **Routes** | `GET /api/sol/<sol_id>/payouts/`, `POST /api/sol/<sol_id>/payouts/` |
| **Permission** | `IsAuthenticated` + `_is_manager` check |

**GET** — Returns all payouts for the Sol with prefetched contributions.

**POST** — Creates the next payout in sequence. Auto-determines `cycle_number` and `next_hand` from existing payout records (`views.py:448–465`). Auto-creates `SolContribution` for all active non-recipient members via `bulk_create` (`views.py:481–490`). Required field: `expected_date`. Wrapped in `transaction.atomic()` (`views.py:469`). Returns 400 if single-cycle Sol is complete (`views.py:455`).

**State transitions:** Creates `SolPayout` + N `SolContribution` rows.

---

#### `SolPayoutDetailView`

**File:** `backend/api/sol/views.py:495`

| | |
|---|---|
| **Routes** | `PATCH /api/sol/<sol_id>/payouts/<payout_id>/` |
| **Permission** | `IsAuthenticated` + `_is_manager` check |

**PATCH** — Updates payout fields. When `status` is set to `"paid"`: sets `paid_date` (defaults to today if not provided), sets `actual_amount` (defaults to `expected_amount` if not provided), and sets `recipient.has_received = True` (`views.py:509–513`). Also accepts `expected_date` update.

**State transitions:** `SolPayout.status` → any valid choice. `SolMember.has_received` → `True` when status set to `"paid"`.

---

#### `SolPayoutRearrangeView`

**File:** `backend/api/sol/views.py:520`

| | |
|---|---|
| **Routes** | `POST /api/sol/<sol_id>/payouts/<payout_id>/rearrange/` |
| **Permission** | `IsAuthenticated` + `_is_manager` check |

**POST** — Swaps the payout recipient. Only allowed when payout status is `"upcoming"` or `"delayed"` (`views.py:529`). Required: `new_recipient_id`. Within a single `transaction.atomic()` (`views.py:541`):
1. Sets `payout.original_recipient` to the current recipient.
2. Sets `payout.recipient` to the new recipient.
3. Updates `payout.hand_number`, `was_rearranged`, `rearranged_reason`, `rearranged_by`.
4. Deletes the new recipient's contribution row (they are now the recipient, not a contributor).
5. Creates a contribution row for the original recipient (they now contribute instead of receiving).

**State transitions:** `SolPayout.was_rearranged` → `True`. Contribution rows modified atomically.

---

#### `SolContributionUpdateView`

**File:** `backend/api/sol/views.py:566`

| | |
|---|---|
| **Routes** | `POST /api/sol/<sol_id>/payouts/<payout_id>/contributions/<contribution_id>/` |
| **Permission** | `IsAuthenticated` + `_is_manager` check |

**POST** — Updates a contribution's status and/or notes. When `status` → `"paid"`, sets `paid_date` (defaults to today) (`views.py:581–582`).

**State transitions:** `SolContribution.status` → any valid choice.

---

#### `SolDashboardView`

**File:** `backend/api/sol/views.py:593`

| | |
|---|---|
| **Routes** | `GET /api/sol/<sol_id>/dashboard/` |
| **Permission** | `IsAuthenticated` + `_is_manager` check |

**GET** — Returns aggregated group statistics: total members, members who have received, completion percentage, current upcoming payout with contribution breakdown (paid/pending/late/missed counts and fund totals), total payouts, paid payouts count. Read-only. No state transitions.

---

#### `SolNotesListCreateView`

**File:** `backend/api/sol/views.py:648`

| | |
|---|---|
| **Routes** | `GET /api/sol/<sol_id>/notes/`, `POST /api/sol/<sol_id>/notes/` |
| **Permission** | `IsAuthenticated` + `_is_manager` check |

**GET** — Returns all `SolNote` rows for the Sol.

**POST** — Creates a new `SolNote`. Required: `text`. `author` is set to `request.user`.

---

### 4.2 Member Self-Service Views

---

#### `SolMembershipListView`

**File:** `backend/api/sol/views.py:719`

| | |
|---|---|
| **Routes** | `GET /api/sol/memberships/` |
| **Permission** | `IsAuthenticated` |

**GET** — Returns all active `SolMember` rows where `bonup_user = request.user`. Non-bonUP participants cannot access this route. Response includes Sol name, sol_id, hand number, received status, frequency, contribution amount.

---

#### `SolMembershipDetailView`

**File:** `backend/api/sol/views.py:744`

| | |
|---|---|
| **Routes** | `GET /api/sol/memberships/<sol_id>/` |
| **Permission** | `IsAuthenticated` + active member check via `_member_of_sol` (`views.py:748`) |

**GET** — Returns detailed membership view: contribution history (last 20), next upcoming payout for this member, and full `SolContract` text if it exists.

---

### 4.3 Tips View

#### `SolTipCreateView`

**File:** `backend/api/sol/views.py:676`

| | |
|---|---|
| **Routes** | `POST /api/sol/<sol_id>/tips/` |
| **Permission** | `IsAuthenticated`; caller must be an active member or a manager who is also a participant |

**POST** — Creates a `SolTip`. The manager can only tip if they have an `is_manager_participant = True` member row in the group (`views.py:683–686`). `to_manager` is always set to `sol.primary_manager` regardless of the caller (`views.py:701`). Record-keeping only; no payment processing occurs.

---

### 4.4 PDF Export Views

Both views are in `backend/api/sol/pdf_views.py`. Both use `reportlab` to build PDFs in-memory and return `HttpResponse` with `Content-Type: application/pdf`.

---

#### `SolManagerExportView`

**File:** `backend/api/sol/pdf_views.py:178`

| | |
|---|---|
| **Routes** | `GET /api/sol/<sol_id>/export/pdf/` |
| **Permission** | `IsAuthenticated` + `_is_manager` check (`pdf_views.py:183`) |

**GET** — Generates and returns a full Sol group PDF. Sections: group summary, members table, payout schedule, contribution tracker grid, fund summary (expected/collected/outstanding/missed totals), tips table (if any), manager notes (if any). Filename: `sol-{sol_id}-record.pdf` (`pdf_views.py:356`).

---

#### `SolMemberExportView`

**File:** `backend/api/sol/pdf_views.py:364`

| | |
|---|---|
| **Routes** | `GET /api/sol/memberships/<sol_id>/export/pdf/` |
| **Permission** | `IsAuthenticated` + active member check via `_member_of_sol` (`pdf_views.py:368`) |

**GET** — Generates and returns a personal member PDF. Sections: membership summary, agreement text (if `SolContract` exists), contribution history, payout records for this member, next upcoming payout. Filename: `sol-{sol_id}-hand{hand_number}-record.pdf` (`pdf_views.py:501`).

---

## 5. Membership Flow

Step-by-step, with code citations:

1. **Manager creates Sol** — `POST /api/sol/` → `SolListCreateView.post` (`views.py:223`). Billing gate `can_create_sol(request.user)` is checked at `views.py:224`. If gate fails, returns 403. On success, a `Sol` row is created with `primary_manager = request.user`.

2. **Manager adds a member** — `POST /api/sol/<sol_id>/members/` → `SolMemberListCreateView.post` (`views.py:299`). Manager check via `_manager_sol_or_404` at `views.py:300`. Required fields validated: `name`, `email`, `phone`, `hand_number`. Hand number uniqueness enforced at `views.py:310`.

3. **bonUP user resolution** — The email is looked up against registered users at `views.py:319`. If found, `can_join_sol(bonup_user)` is called at `views.py:321`. If gate fails, returns 403 with error. If gate passes, `auto_upgrade_to_sol_member(bonup_user)` is called at `views.py:325`. If email not found, member is added without a `bonup_user` link.

4. **Atomic member creation** — Wrapped in `transaction.atomic()` at `views.py:331`. `SolMember` created at `views.py:332`.

5. **SolContract auto-generated** — `_generate_contract_text(sol, member, total_members)` called at `views.py:349`. Total member count is recalculated after insert (`views.py:348`). `SolContract` created at `views.py:350–357` with `agreed_contribution_amount`, `agreed_hand_number`, `agreed_tip_amount` copied from current Sol values. `signed_by_member` defaults to `False`.

6. **SolContribution backfill** — The first open (`status="upcoming"`) payout is fetched at `views.py:360`. If one exists and its recipient is not this new member, `SolContribution.objects.get_or_create(...)` is called at `views.py:362` to add the new member's contribution obligation for that open period.

7. **Member deactivation** — `DELETE /api/sol/<sol_id>/members/<member_id>/` → `SolMemberDeleteView.delete` (`views.py:378`). Sets `is_active = False` (`views.py:383–384`). Calls `auto_downgrade_from_sol_member(member.bonup_user)` at `views.py:386` if `bonup_user` is set. The `SolMember` row, its `SolContract`, and its `SolContribution` rows are NOT deleted.

---

## 6. Payout and Contribution Flow

Step-by-step, with code citations:

1. **Manager creates a payout** — `POST /api/sol/<sol_id>/payouts/` → `SolPayoutListCreateView.post` (`views.py:426`). Required: `expected_date`.

2. **Cycle and hand auto-determination** — The system reads all existing payout rows ordered by `cycle_number, hand_number` (`views.py:440`). It tracks which hands have been scheduled per cycle (`views.py:441–443`). It finds the first unscheduled hand in the current cycle (`views.py:461–465`). If all hands are scheduled and `sol_type = "single"`, creation is blocked (`views.py:454–455`). If `sol_type = "recurring"`, `cycle_number` increments (`views.py:456`).

3. **Payout creation** — `SolPayout` created at `views.py:470`. `expected_amount` is computed as `contribution_amount × (len(active_members) − 1)` at `views.py:467`.

4. **Contribution bulk-create** — All active members except the recipient are collected at `views.py:480`. `SolContribution.objects.bulk_create(...)` at `views.py:481` creates one row per contributing member with `status="pending"` and `due_date = expected_date`. Wrapped in `transaction.atomic()` at `views.py:469`.

5. **Manual status updates** — The manager calls `PATCH /api/sol/<sol_id>/payouts/<payout_id>/` to update payout status. Calls `POST /api/sol/<sol_id>/payouts/<payout_id>/contributions/<contribution_id>/` to update each member's contribution status. No automated transitions.

6. **Marking paid** — When payout status is set to `"paid"` (`views.py:509`): `paid_date` is set (`views.py:510`), `actual_amount` is set (`views.py:511`), and `recipient.has_received = True` is written (`views.py:512–513`).

7. **Rearrangement** — `POST /api/sol/<sol_id>/payouts/<payout_id>/rearrange/` → `SolPayoutRearrangeView.post` (`views.py:523`). Only allowed when payout is `"upcoming"` or `"delayed"` (`views.py:529`). Within `transaction.atomic()` (`views.py:541`): recipient is swapped, `was_rearranged = True`, `original_recipient` preserved, new recipient's contribution row deleted, original recipient's contribution row created.

---

## 7. Billing Gates

All four gate calls are in `backend/api/sol/views.py`. Gate implementations are in `backend/billing/gates.py` (documented in `billing.md`).

| Call site | Gate | Trigger | File:Line |
|---|---|---|---|
| `can_create_sol(request.user)` | Blocks Sol creation if user's plan excludes Sol | POST /api/sol/ | `views.py:224` |
| `can_join_sol(bonup_user)` | Blocks bonUP user linkage if their plan excludes Sol | member add, when email matches a registered user | `views.py:321` |
| `auto_upgrade_to_sol_member(bonup_user)` | Upgrades user's plan/subscription to a Sol-eligible tier | member add, after join gate passes | `views.py:325` |
| `auto_downgrade_from_sol_member(member.bonup_user)` | Downgrades user's plan/subscription when they are deactivated | member deactivation, when `bonup_user` is set | `views.py:386` |

`can_join_sol` and `auto_upgrade_to_sol_member` are only called if the added member's email resolves to a registered bonUP user (`views.py:316–326`). Non-bonUP participants bypass all billing gates.

---

## 8. Authority / Access Rules

- Default permission class is `IsAuthenticated` on all views (DRF project default, `backend/core/settings.py:256`). No Sol view overrides this.
- Manager authority is checked by `_is_manager(user, sol)` at `views.py:25–26`: `return sol.primary_manager_id == user.pk or sol.co_manager_id == user.pk`. This grants co-managers identical authority to the primary manager.
- `_manager_sol_or_404(user, sol_id)` at `views.py:29–33` is the entry point used by all manager views. It calls `_is_manager` and returns 403 if the check fails.
- **Manager authority enforcement is inline.** There is no centralized Django permission class for Sol manager access. Each manager view calls `_manager_sol_or_404` individually.
- Member self-service routes (`SolMembershipListView`, `SolMembershipDetailView`, `SolMemberExportView`) are scoped by `bonup_user = request.user` (`views.py:723`, `views.py:40`). Non-bonUP participants cannot use these routes.
- `SolTipCreateView` allows both active members and manager-participants to submit tips, with separate resolution paths (`views.py:683–691`).
- No Django admin registration for any Sol model was verified in the codebase.
- No staff-only or admin-only read path exists in the Sol domain.

---

## 9. Relationship to Other Domains

### Billing (`backend/billing/`)

Four billing gate functions from `backend/billing/gates.py` are imported and called in `views.py` (`views.py:15`). See Section 7. The Sol domain depends on billing for plan-gating; billing does not import from Sol.

### Admin Panel (`backend/api/admin_views.py`)

The admin panel references Sol models for read access in admin-facing views. This is out of scope for this document; behavior is in the admin domain.

### Search (`backend/api/search/`)

The search domain queries Sol data for unified search results. This is out of scope for this document; behavior is in the search domain.

### AI Context (`backend/ai/context.py`)

The AI context module reads Sol membership data to provide context for AI-assisted features. This is out of scope; behavior is in the AI domain.

### `contracts.Contract` — explicitly NOT related

`SolContract` (`backend/sol/models.py:144`) has no FK, no inheritance, and no code relationship to `contracts.Contract` (`backend/contracts/models.py`). They are independent models in separate Django apps. `log_activity` from `backend/activity/log.py` is never called in the Sol domain. `ContractActivity` has no FK to any Sol model. The Sol and contracts domains do not share state.

---

## 10. Current Gaps

1. **No audit trail.** No `log_activity` calls exist anywhere in the Sol domain. There is no equivalent of `ContractActivity` for Sol events. Manager actions (payout creation, rearrangement, member deactivation) are not logged to any audit table. `SolNote` is a narrative note, not an event log. `SolPayout.rearranged_by` / `rearranged_reason` is the only rearrangement audit record.

2. **No services layer.** All business logic is inline in `backend/api/sol/views.py`. Contract text generation, payout cycle tracking, contribution backfilling, rearrangement, and billing gate calls are all in view methods. There is no `backend/sol/services.py` or domain engine.

3. **No automated status transitions.** Payout status (`upcoming`/`paid`/`delayed`/`missed`) and contribution status (`pending`/`paid`/`late`/`missed`) are updated only by explicit manager API calls. There is no Celery task, scheduled job, or signal that advances status based on dates. Late or missed contributions are only marked as such if a manager manually changes them.

4. **No reminders, no escalations, no background processing.** No Celery tasks or signals exist in the Sol domain. There is no mechanism to notify members of upcoming due dates or missed contributions.

5. **Co-manager permission enforcement is inline, not centralized.** `_is_manager` is a module-level helper at `views.py:25–26`. There is no Django permission class or DRF permission object for Sol manager access. Adding a new Sol view requires manually calling `_manager_sol_or_404` to enforce the check.

6. **`SolContract.signed_by_member` is not enforced as a precondition.** No view checks whether a member has signed their `SolContract` before allowing payout creation or contribution updates. A Sol can operate fully with all contracts unsigned.

7. **The name `SolContract` is potentially confusing.** The same codebase contains `contracts.Contract` in `backend/contracts/models.py`. The names are similar enough to cause misreading. `SolContract` is a simple auto-generated text record; `contracts.Contract` is a full lifecycle negotiation model with versioning, signing, and role switching. They are unrelated.

8. **Member self-service is blocked for non-bonUP participants.** Members without a `bonup_user` link cannot view their membership, contribution history, or download their personal PDF. These participants are record-only from the system's perspective.

9. **`SolContribution` backfill at member-add time only covers the first open payout.** `views.py:360` fetches only the first `status="upcoming"` payout ordered by `cycle_number, hand_number`. If multiple open payouts exist, the new member only gets a contribution row for the earliest one.

---

## 11. Open Questions

1. **Is `is_private` enforced anywhere?** `Sol.is_private` (`models.py:79`) is stored and returned in API responses but no view uses it to filter Sol visibility or access. Its enforcement purpose is not established in code.

2. **Is there a member self-service path to sign `SolContract`?** `SolMembershipDetailView` returns the contract text and `signed_by_member` flag but there is no PATCH endpoint in the member self-service routes to update `signed_by_member`. The only contract-related manager endpoint (`SolMemberContractView`) is read-only. No signing endpoint was found.

3. **Does `SolTipCreateView` intend to support tips directed to co-managers?** `to_manager` is always set to `sol.primary_manager` at `views.py:701` regardless of who the caller is. If co-managers are expected to receive tips, this would not work as written.

4. **What happens to open `SolContribution` rows when a member is deactivated?** `SolMemberDeleteView` sets `is_active = False` on the member but does not modify or cancel any pending `SolContribution` rows. The deactivated member's pending contributions remain in the `pending` state with no cleanup.

---

## 12. Update Rule

Update this file when code changes `Sol`, `SolMember`, `SolContract`, `SolPayout`, `SolContribution`, `SolTip`, or `SolNote` models; when view logic in `backend/api/sol/views.py` or `backend/api/sol/pdf_views.py` changes; when billing gate call sites in Sol views change; or when new URL patterns are added to `backend/api/sol/urls.py`.
