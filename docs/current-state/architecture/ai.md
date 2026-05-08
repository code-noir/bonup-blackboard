# AI Architecture

> Status: Current
> Source of truth: code first, this document second
> Updated: 2026-05-08

---

## 1. Overview

The AI domain provides backend endpoints for four distinct capabilities: tier-aware multi-turn chat with stored conversation history, single-turn contract analysis from a PDF input, single-turn counter-contract drafting from a PDF input, and single-turn contract import from a PDF that creates Contract and obligation records in the database. The Anthropic Python SDK (`anthropic` package) is the model provider for all four. The SDK integration is **scattered**: `anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)` is instantiated at four separate call sites inside `backend/api/ai/views.py` (lines 362, 526, 572, 620) rather than in a shared module. The `AIChatView` additionally parses structured JSON action blocks emitted by the model from the Anthropic response text using `_extract_action()` (`backend/api/ai/views.py:152`) and dispatches them to two executors: `_execute_instantiate_template()` (`backend/api/ai/views.py:190`) and `_execute_create_contract()` (`backend/api/ai/views.py:233`).

---

## 2. Models

### AIConversation

`backend/ai/models.py:9`

| Field | Type | Notes |
|---|---|---|
| id | UUIDField | PK, `uuid4`, not editable |
| user | FK → AUTH_USER_MODEL | CASCADE; `related_name="ai_conversations"` |
| contract | FK → contracts.Contract | SET_NULL, null=True, blank=True; `related_name="ai_conversations"` |
| conversation_type | CharField(30) | choices below; default `"general"` |
| messages | JSONField | default=list; see message shape below |
| created_at | DateTimeField | auto_now_add |
| updated_at | DateTimeField | auto_now |

`Meta.ordering = ["-updated_at"]` (`backend/ai/models.py:47`)

**conversation_type choices** (`backend/ai/models.py:11`):

| Value | Label |
|---|---|
| `general` | General |
| `contract_help` | Contract Help |
| `template_recommendation` | Template Recommendation |
| `contract_generation` | Contract Generation |
| `obligation_creation` | Obligation Creation |

**messages field shape** (`backend/ai/models.py:41`):

The `messages` field is a JSON array. Each element has the shape:

    {"role": "user"|"assistant", "content": "<string>"}

This array is passed directly to the Anthropic API `messages` parameter on each request.

---

## 3. Core Concepts

### 3.1 Two AI Workflows in One Domain

Two distinct workflows are implemented.

**Chat workflow** (`AIChatView`, `backend/api/ai/views.py:328`):
- Multi-turn. Conversation history is stored in `AIConversation.messages`.
- Each request loads or creates an `AIConversation` record.
- A tier-differentiated system prompt with injected user context is sent on every turn.
- Action blocks emitted by the model are optionally parsed and executed (full tier only).
- The `AIConversation` record is saved after each response.

**Document AI workflow** (`AnalyzeContractView`, `CounterContractView`, `ImportContractView`):
- Single-turn. A PDF is accepted as input (multipart file or `upload_id`).
- A new `AIConversation` record is created for each request with `conversation_type="contract_help"` and saved once after the Anthropic response.
- No user context injection. No tier-differentiated prompt selection.
- Each endpoint uses a fixed inline system prompt.
- `ImportContractView` additionally writes Contract and obligation records based on extracted JSON.

### 3.2 Tier-Differentiated Prompts

Three system prompts exist in `backend/ai/prompts.py`, one per AI tier:

| Constant | Tier | Defined at |
|---|---|---|
| `BASIC_PROMPT` | basic | `backend/ai/prompts.py:10` |
| `ADVANCED_PROMPT` | advanced | `backend/ai/prompts.py:37` |
| `FULL_PROMPT` | full | `backend/ai/prompts.py:68` |

A `TIER_PROMPTS` dict maps tier names to prompt constants (`backend/api/ai/views.py:24`):

    TIER_PROMPTS = {
        "basic": BASIC_PROMPT,
        "advanced": ADVANCED_PROMPT,
        "full": FULL_PROMPT,
    }

Prompt selection occurs in `AIChatView.post()` at `backend/api/ai/views.py:356`:

    system_prompt = TIER_PROMPTS[ai_tier].replace("{{user_context}}", user_context)

This line both selects the prompt for the user's tier and substitutes the `{{user_context}}` placeholder.

### 3.3 build_user_context() Injection

All three prompts in `backend/ai/prompts.py` contain the literal placeholder string `{{user_context}}` (BASIC_PROMPT line 28, ADVANCED_PROMPT line 59, FULL_PROMPT line 191). This placeholder is replaced at runtime in `AIChatView.post()` (line 356) with the string returned by `build_user_context(request.user)`.

`build_user_context()` is defined in `backend/ai/context.py:15`. It reads from the following models in order:

| Model | Source | Lines in context.py |
|---|---|---|
| `BonUserProfile` | `backend/users/models` | 20 (query), 22 (bon_id) |
| `AUTH_USER_MODEL` (User) | Django | 25–26 (name, username, email) |
| `UserSubscription` via `get_user_subscription()` | `backend/billing/gates` | 31–37 |
| `Contract` | `backend/contracts/models` | 40–53 (last 10 for user as initiator or counterparty_email) |
| `ContractObligation` | `backend/contracts/models` | 59–65 (due in next 7 days) |
| `ContractServiceObligation` | `backend/contracts/models` | 66–72 (due in next 7 days) |
| `ContractTemplate` | `backend/contract_templates/models` | 92–102 (active, filtered by plan.excluded_categories, up to 50) |
| `Sol` | `backend/sol/models` | 108–111 (managed sols where user is primary_manager or co_manager, status=active) |
| `SolMember` | `backend/sol/models` | 143–145 (memberships where bonup_user=user and is_active=True) |
| `SolContribution` | `backend/sol/models` | 168 (contribution for open payout period) |

The function returns a newline-joined string (`backend/ai/context.py:175`).

### 3.4 Action Block Execution in Chat

When `ai_tier == "full"`, `AIChatView.post()` calls `_extract_action(assistant_text)` on the Anthropic response text (`backend/api/ai/views.py:376–379`).

**`_extract_action(text)`** (`backend/api/ai/views.py:152`):
- Primary: regex search for a ` ```json ... ``` ` fenced block; parses with `json.loads()` (line 158–162).
- Fallback: regex search for a bare `{...}` block containing the string `"action"` at the end of the text; parses with `json.loads()` (line 165–170).
- Returns a dict or `None`.

If an action dict is returned, `_execute_action(action_data, request.user)` dispatches on `action_data["action"]` (`backend/api/ai/views.py:180`):

| action value | executor called | defined at |
|---|---|---|
| `"instantiate_template"` | `_execute_instantiate_template(data, user)` | `backend/api/ai/views.py:190` |
| `"create_contract"` | `_execute_create_contract(data, user)` | `backend/api/ai/views.py:233` |
| any other | returns `{"status": "unknown_action"}` | line 187 |

**`_execute_instantiate_template(data, user)`** (`backend/api/ai/views.py:190`):
1. Calls `can_create_contract(user)` (line 197); returns blocked if not allowed.
2. Calls `TemplateInstantiationService().instantiate(...)` (line 209–217) from `backend/contract_templates/services/template_instantiation_service`.
3. On success: calls `increment_contracts_used(user)` (line 221) and `consume_trial_contract(user)` (line 222).
4. Returns a summary dict including `contract_id`, obligation counts.

**`_execute_create_contract(data, user)`** (`backend/api/ai/views.py:233`):
1. Calls `can_create_contract(user)` (line 237); returns blocked if not allowed.
2. In `transaction.atomic()` (line 253): creates `Contract` (line 254), `ContractVersion` (line 260).
3. Looks up counterparty by email in User table (line 272–275).
4. If counterparty is not found (not a registered User), skips all obligation creation (line 284).
5. If counterparty is found: creates `ContractObligation` records for `obligation_type="payment"` (line 289) and `ContractServiceObligation` records for all other types (line 300).
6. Calls `increment_contracts_used(user)` (line 310) and `consume_trial_contract(user)` (line 311).
7. Returns a summary dict including `contract_id`, `version_id`, `counterparty_found`, obligation counts.

Both executors run as `user` (the authenticated `request.user`) passed at line 379.

### 3.5 Anthropic Client Instantiation Pattern

`anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)` is instantiated four times, all in `backend/api/ai/views.py`:

| Line | View / context |
|---|---|
| 362 | `AIChatView.post()` |
| 526 | `AnalyzeContractView.post()` |
| 572 | `CounterContractView.post()` |
| 620 | `ImportContractView.post()` |

There is no shared client singleton. Each HTTP request creates a new `Anthropic()` instance inline. For comparison, `backend/sessions/token.py` wraps the LiveKit SDK client instantiation in a single module-level function; the AI domain does not follow this pattern.

### 3.6 PDF Input Pipeline

**`_get_pdf_bytes(request)`** (`backend/api/ai/views.py:427`):

Accepts one of two input forms:
1. Multipart `file` field: reads bytes directly via `request.FILES.get("file").read()` (line 433–434).
2. `upload_id` field: fetches `Upload.objects.get(pk=upload_id, user=request.user)` (line 442); validates `upload.file_type == "pdf"` (line 445); opens via `default_storage.open(upload.storage_key)` (line 450). The `Upload` lookup is user-scoped — `user=request.user` is enforced in the query.

If neither form is present, returns a 400 error (line 456–459).

**`_extract_pdf_text(pdf_bytes)`** (`backend/api/ai/views.py:462`):

Uses `pdfplumber` (imported at line 465). Opens a `BytesIO` wrapper around the bytes, iterates pages, calls `page.extract_text()`, joins non-empty results with double newlines. Returns `"[No readable text found in PDF]"` if no text is extracted (line 473).

---

## 4. Current Behavior

| Route | View | Permission | What it does | State transitions | Side effects |
|---|---|---|---|---|---|
| `POST /api/ai/chat/` | `AIChatView` | IsAuthenticated | Checks ai_tier; builds user context; selects tier prompt; appends user message; calls Anthropic; appends response; if full tier, extracts and executes action block; saves conversation | None on `AIConversation` (creates or updates record) | Creates or updates `AIConversation`; optionally creates `Contract`, `ContractVersion`, `ContractObligation`, `ContractServiceObligation` via action executors |
| `GET /api/ai/conversations/` | `AIConversationListView` | IsAuthenticated | Returns paginated list of caller's conversations; page size 20; does not include messages array | None | None |
| `GET /api/ai/conversations/<uuid>/` | `AIConversationDetailView` | IsAuthenticated | Returns single conversation record scoped to caller; includes messages array | None | None |
| `DELETE /api/ai/conversations/<uuid>/` | — | — | **Not implemented.** `AIConversationDetailView` defines only a `get` method (`backend/api/ai/views.py:418`). No DELETE route is registered in `backend/api/ai/urls.py`. | — | — |
| `POST /api/ai/analyze-contract/` | `AnalyzeContractView` | IsAuthenticated | Checks subscription status; extracts PDF text; calls Anthropic with `ANALYZE_CONTRACT_PROMPT`; parses JSON block from response; saves conversation | None | Creates `AIConversation` with `conversation_type="contract_help"` |
| `POST /api/ai/counter-contract/` | `CounterContractView` | IsAuthenticated | Checks `has_feature("sol")`; extracts PDF text; calls Anthropic with `COUNTER_CONTRACT_PROMPT`; parses JSON block; saves conversation | None | Creates `AIConversation` with `conversation_type="contract_help"` |
| `POST /api/ai/import-contract/` | `ImportContractView` | IsAuthenticated | Checks ai_tier == "full"; extracts PDF text; calls Anthropic with `IMPORT_CONTRACT_PROMPT`; parses JSON block; creates Contract, ContractVersion, obligations atomically; calls billing gates after creation; saves conversation | Creates `Contract` in draft state, `ContractVersion` version_number=1 status=draft | Creates `AIConversation`, `Contract`, `ContractVersion`, `ContractObligation` (if counterparty found), `ContractServiceObligation` (if counterparty found) |

---

## 5. Tier and Billing Gate Enforcement

| Route | Gate function | Call site | Gate logic |
|---|---|---|---|
| `POST /api/ai/chat/` | `get_ai_tier(request.user)` | `backend/api/ai/views.py:331` | Blocks if `ai_tier == "none"`; selects prompt by tier (basic/advanced/full) |
| `GET /api/ai/conversations/` | None | — | No additional gate beyond IsAuthenticated |
| `GET /api/ai/conversations/<uuid>/` | None | — | No additional gate beyond IsAuthenticated |
| `POST /api/ai/analyze-contract/` | `get_user_subscription(request.user)` | `backend/api/ai/views.py:509` | Blocks if `sub is None or sub.status not in {"active", "trialing", "per_contract"}`; does not check `ai_tier` |
| `POST /api/ai/counter-contract/` | `has_feature(request.user, "sol")` | `backend/api/ai/views.py:556` | Blocks if Sol feature not enabled; does not check `ai_tier` |
| `POST /api/ai/import-contract/` | `get_ai_tier(request.user)` | `backend/api/ai/views.py:602` | Blocks if `ai_tier != "full"` |

`AnalyzeContractView` checks subscription status (`sub.status`) but not AI tier. `CounterContractView` uses `has_feature("sol")` — the Sol feature flag — not any AI tier check. These two routes apply different billing predicates than the chat and import routes, which use `get_ai_tier()`.

---

## 6. Prompts

### Prompts in backend/ai/prompts.py

Three tier-differentiated system prompts. All contain the `{{user_context}}` placeholder string.

**`BASIC_PROMPT`** (`backend/ai/prompts.py:10`):
- Capabilities declared in prompt: answer questions about platform, explain contracts, recommend templates.
- Instructs model to block contract creation and direct user to upgrade.
- Contains `{{user_context}}` at line 28.

**`ADVANCED_PROMPT`** (`backend/ai/prompts.py:37`):
- Capabilities declared in prompt: all basic capabilities plus contract improvements, negotiation assistance, drafting counterparty messages, obligation lifecycle guidance.
- Instructs model to block contract creation from scratch and direct user to full tier.
- Contains `{{user_context}}` at line 59.

**`FULL_PROMPT`** (`backend/ai/prompts.py:68`):
- Capabilities declared in prompt: all advanced capabilities plus contract creation from scratch and obligation creation via API.
- Defines the JSON action block specification (lines 99–131):
  - `instantiate_template` action: requires `template_id`, `guided_field_values`, `counterparty_email` fields.
  - `create_contract` action: requires `contract` object (`title`, `structure_type`, `counterparty_email`, `content`) and `obligations` array (`obligation_type`, `description`, `amount`, `due_date_offset_days`, `recurrence_interval_days`, `recurrence_count`).
  - Instructs model to place the JSON block at the **end** of the response after plain-language explanation (line 133).
- Contains `{{user_context}}` at line 191.

### Inline Prompts in backend/api/ai/views.py

Three inline system prompt constants defined at module level. None use `{{user_context}}` substitution. None are selected by tier.

**`ANALYZE_CONTRACT_PROMPT`** (`backend/api/ai/views.py:39`):
- Instructs model to return structured JSON inside a ` ```json ``` ` block at end of response.
- JSON shape: `summary`, `key_terms` (parties, dates, amounts, duration), `red_flags`, `questions`.
- Used exclusively by `AnalyzeContractView` (line 530).

**`COUNTER_CONTRACT_PROMPT`** (`backend/api/ai/views.py:64`):
- Instructs model to return structured JSON inside a ` ```json ``` ` block at end of response.
- JSON shape: `summary`, `concerning_clauses` (each with clause_reference, concern, counter_language), `negotiation_strategy` (push_on, concede), `revised_contract`.
- Used exclusively by `CounterContractView` (line 574).

**`IMPORT_CONTRACT_PROMPT`** (`backend/api/ai/views.py:95`):
- Instructs model to return **only** a ` ```json ``` ` block with no surrounding text.
- JSON shape: `title`, `counterparty_email`, `structure_type`, `start_date`, `end_date`, `summary`, `payment_obligations` array, `service_obligations` array.
- Used exclusively by `ImportContractView` (line 621).

---

## 7. Anthropic API Integration

**Settings** (`backend/core/settings.py`):

| Setting | Line | Value |
|---|---|---|
| `ANTHROPIC_API_KEY` | 203 | `os.environ.get("ANTHROPIC_API_KEY", "")` — defaults to empty string |
| `ANTHROPIC_MODEL` | 204 | `os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")` |

**Module-level constants in views.py** (`backend/api/ai/views.py`):

| Constant | Line | Value |
|---|---|---|
| `AI_MODEL` | 30 | `getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-4-6")` |
| `AI_MAX_TOKENS` | 31 | `2000` — used by `AIChatView` |
| `AI_MAX_TOKENS_ANALYSIS` | 32 | `4000` — used by `AnalyzeContractView`, `CounterContractView`, `ImportContractView` |

**Client instantiation sites** (all in `backend/api/ai/views.py`):

| Line | View |
|---|---|
| 362 | `AIChatView.post()` |
| 526 | `AnalyzeContractView.post()` |
| 572 | `CounterContractView.post()` |
| 620 | `ImportContractView.post()` |

All four use the pattern `anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)` and call `client.messages.create(model=AI_MODEL, max_tokens=..., system=..., messages=[...])`.

**Empty key behavior**: `ANTHROPIC_API_KEY` defaults to an empty string (`settings.py:203`). No code path in `backend/api/ai/views.py` checks whether the key is non-empty before instantiating the client or calling the API. The request will fail at the Anthropic SDK call if the key is absent.

---

## 8. Cross-Domain Interactions

### Reads via build_user_context()

All reads occur in `backend/ai/context.py`. Called from `AIChatView.post()` at `backend/api/ai/views.py:355`.

| Domain | Model | context.py lines |
|---|---|---|
| users | `BonUserProfile` | 20–23 |
| users | `AUTH_USER_MODEL` (User) | 25–28 |
| billing | `UserSubscription` via `get_user_subscription()` | 31–37 |
| contracts | `Contract` | 40–53 |
| contracts | `ContractObligation` | 59–65 |
| contracts | `ContractServiceObligation` | 66–72 |
| contract_templates | `ContractTemplate` | 92–102 |
| sol | `Sol` | 108–138 |
| sol | `SolMember` | 143–172 |
| sol | `SolContribution` | 168 |

### Writes via Action Executors and ImportContractView

**`_execute_instantiate_template()`** (`backend/api/ai/views.py:190`):

| Write | Line |
|---|---|
| `can_create_contract(user)` gate check | 197 |
| `TemplateInstantiationService().instantiate(...)` — writes Contract + obligations | 211 |
| `increment_contracts_used(user)` | 221 |
| `consume_trial_contract(user)` | 222 |

**`_execute_create_contract()`** (`backend/api/ai/views.py:233`):

| Write | Line |
|---|---|
| `can_create_contract(user)` gate check | 237 |
| `Contract.objects.create(...)` | 254 |
| `ContractVersion.objects.create(...)` | 260 |
| `ContractObligation.objects.create(...)` (payment obligations) | 289 |
| `ContractServiceObligation.objects.create(...)` (service obligations) | 300 |
| `increment_contracts_used(user)` | 310 |
| `consume_trial_contract(user)` | 311 |

**`ImportContractView.post()`** (`backend/api/ai/views.py:598`):

| Write | Line |
|---|---|
| `Contract.objects.create(...)` | 644 |
| `ContractVersion.objects.create(...)` | 652 |
| `ContractObligation.objects.create(...)` (payment obligations) | 681 |
| `ContractServiceObligation.objects.create(...)` (service obligations) | 704 |
| `can_create_contract(request.user)` gate check | 724 |
| `increment_contracts_used(request.user)` | 726 |
| `consume_trial_contract(request.user)` | 727 |

### Frontend

Grep command run: `grep -r "/api/ai/" frontend/src/ --include="*.ts" --include="*.tsx" --include="*.js" --include="*.jsx"`

Result: **no matches**. No frontend files under `frontend/src/` reference `/api/ai/` routes.

---

## 9. Authority and Access Rules

**All routes**: DRF `DEFAULT_PERMISSION_CLASSES` is `["rest_framework.permissions.IsAuthenticated"]` (`backend/core/settings.py:255`). No view in `backend/api/ai/views.py` declares an explicit `permission_classes` attribute. All routes therefore inherit `IsAuthenticated`.

**Conversation scoping**:
- `AIConversationListView.get()` filters by `user=request.user` (`backend/api/ai/views.py:397`).
- `AIConversationDetailView.get()` uses `get_object_or_404(AIConversation, pk=conversation_id, user=request.user)` (`backend/api/ai/views.py:419`).
- `AIChatView.post()` — when loading an existing conversation — uses `get_object_or_404(AIConversation, pk=conversation_id, user=request.user)` (`backend/api/ai/views.py:347`).

**Upload scoping on PDF routes**:
`_get_pdf_bytes()` fetches `Upload.objects.get(pk=upload_id, user=request.user)` (`backend/api/ai/views.py:442`). The upload_id path is user-scoped; a user cannot reference another user's Upload record.

**Action executors**: Both `_execute_instantiate_template()` and `_execute_create_contract()` receive `user = request.user` (passed at `backend/api/ai/views.py:379`). Contracts and obligations are created with `initiator=user` and `obligor=user`.

---

## 10. Current Gaps

**G-AI-1 (High): CounterContractView uses wrong billing gate**
`CounterContractView.post()` gates on `has_feature(request.user, "sol")` (`backend/api/ai/views.py:556`). `has_feature("sol")` is the Sol feature flag, not an AI tier check. The error message says "Contract counter-drafting requires a Business or Anchor subscription." but the predicate enforced is Sol feature access. These two are not the same gate. Source: `backend/api/ai/views.py:556`.

**G-AI-2 (Medium): AnalyzeContractView checks subscription status, not AI tier**
`AnalyzeContractView.post()` checks `sub.status in {"active","trialing","per_contract"}` (`backend/api/ai/views.py:509`). It does not call `get_ai_tier()` or enforce any minimum tier. Any subscriber with an active status can call this endpoint regardless of tier. Source: `backend/api/ai/views.py:509–510`.

**G-AI-3 (High): ImportContractView checks billing gate after contract is already created**
`ImportContractView.post()` creates `Contract`, `ContractVersion`, and all obligations inside `transaction.atomic()` at lines 643–719. The `can_create_contract()` gate check occurs at line 724, after the atomic block has already committed. `increment_contracts_used` and `consume_trial_contract` are called only if `can_create_contract` returns allowed at that point (line 724–727), but the contract itself is already persisted regardless of gate outcome. Source: `backend/api/ai/views.py:643–727`.

**G-AI-4 (High): No rate limiting on any AI endpoint**
No DRF throttle class is configured in `backend/core/settings.py` (`REST_FRAMEWORK` block, lines 244–258). No `throttle_classes` attribute is present on any view in `backend/api/ai/views.py`. No middleware-level rate limiting was found. Each authenticated request triggers an Anthropic API call with no constraint on request frequency.

**G-AI-5 (High): No per-user cost or token usage tracking**
No model exists for recording tokens consumed or API call cost. No token usage data from `api_response` (e.g., `api_response.usage`) is stored. No monthly spend limit or circuit breaker is present.

**G-AI-6 (Medium): ANTHROPIC_API_KEY defaults to empty string with no startup validation**
`ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")` (`backend/core/settings.py:203`). No check for empty value exists before any of the four Anthropic client instantiation sites (views.py lines 362, 526, 572, 620). A missing key will produce an Anthropic SDK error at request time, not at startup.

**G-AI-7 (Medium): Anthropic client instantiated four times instead of once**
`anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)` is called inline at lines 362, 526, 572, and 620. There is no shared client module. Source: `backend/api/ai/views.py:362, 526, 572, 620`.

**G-AI-8 (Medium): Inline prompts in views.py vs. prompts module**
`ANALYZE_CONTRACT_PROMPT`, `COUNTER_CONTRACT_PROMPT`, and `IMPORT_CONTRACT_PROMPT` are defined as module-level constants in `backend/api/ai/views.py` (lines 39, 64, 95) rather than in `backend/ai/prompts.py`. The tier-differentiated prompts are in `backend/ai/prompts.py` but the document-AI prompts are not.

**G-AI-9 (Medium): Action block execution writes contracts on user's behalf based on AI-emitted JSON**
When `ai_tier == "full"`, `AIChatView.post()` parses a JSON block from the Anthropic response and executes it to create database records (`backend/api/ai/views.py:376–379`). The JSON that drives `_execute_create_contract()` (contract title, counterparty_email, structure_type, content, obligations) originates from the model output, not from validated user input. The `_extract_action()` function applies no schema validation beyond `json.loads()` success and the presence of an `"action"` key (lines 152–173). Malformed or unexpected model output that passes JSON parsing will be passed to the executors.

**G-AI-10 (Low): DELETE /api/ai/conversations/<uuid>/ is not implemented**
`AIConversationDetailView` defines only a `get` method (`backend/api/ai/views.py:418`). There is no `delete` method and no separate DELETE route in `backend/api/ai/urls.py`. A DELETE request to this URL will receive a 405 Method Not Allowed response.

**G-AI-11 (Low): No frontend integration found**
Grep of `frontend/src/` found no files referencing `/api/ai/` routes. The AI domain has no connected frontend caller in the current codebase.

---

## 11. Open Questions

**Q-AI-1**: Is `has_feature(request.user, "sol")` in `CounterContractView` an intentional proxy for a tier tier (i.e., was the Sol feature flag chosen as a stand-in for Business/Anchor tiers), or is it a copy-paste error from another view? Cannot be resolved from `backend/api/ai/views.py` alone.

**Q-AI-2**: `_execute_create_contract()` skips all obligation creation if the counterparty email does not match a registered User (`backend/api/ai/views.py:284`). Is the intent to create obligations later (after counterparty signs up), or to always require a registered counterparty for this path? Not established in code.

**Q-AI-3**: `AIConversation.conversation_type` has five choices (general, contract_help, template_recommendation, contract_generation, obligation_creation). The analyze, counter-draft, and import views all set `conversation_type="contract_help"`. The other types (`template_recommendation`, `contract_generation`, `obligation_creation`) are never set by any view. Whether these are reserved for future use or are dead choices is not established in code.

**Q-AI-4**: `ImportContractView` calls `can_create_contract` after contract creation (line 724). Whether this represents an intentional post-create gate (e.g., audit only) or an implementation error is not established in code.

**Q-AI-5**: The `FULL_PROMPT` action block specification (`backend/ai/prompts.py:99–131`) includes `recurrence_interval_days` and `recurrence_count` fields in the obligations array. `_execute_create_contract()` does not read these fields — it uses only `obligation_type`, `description`, `amount`, and `due_date_offset_days` (`backend/api/ai/views.py:278–283`). Whether the recurrence fields are reserved for future handling is not established in code.

---

## 12. Update Rule

Regenerate this file when any of the following change:

- `backend/ai/models.py` — model fields or choices
- `backend/ai/prompts.py` — prompt text or {{user_context}} usage
- `backend/ai/context.py` — models queried or context assembly
- `backend/api/ai/views.py` — view logic, billing gates, action executors, helpers, or constants
- `backend/api/ai/urls.py` — route registration
- `backend/core/settings.py` — ANTHROPIC_API_KEY, ANTHROPIC_MODEL, or REST_FRAMEWORK defaults

Use the audit-and-write workflow: inventory first, then rewrite with citations. Do not manually patch individual claims.
