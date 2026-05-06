# Live Sessions Architecture

> Status: Generated from code
> Source of truth: current code first, docs second
> Generated: 2026-05-06

---

## 1. Overview

The live sessions domain provides real-time video sessions backed by LiveKit. Each session is represented by a `LiveSession` database record that stores the lifecycle state, the LiveKit `room_name`, and optional links to a contract and contract version. HTTP routes manage the full session lifecycle (create, update, join, cancel, end). A Django Channels `AsyncWebsocketConsumer` handles in-session real-time events (content sync, slide sync, presentation control, session-end notification). The LiveKit SDK integration is intentionally isolated to a single file — `backend/sessions/token.py` — so no other code imports from `livekit` directly. There is no LiveKit webhook handler.

---

## 2. Models

### 2.1 LiveSession

**File:** `backend/sessions/models.py:13`

**App label:** `live_sessions` (`backend/sessions/apps.py`) — used in FK string references by other apps.

| Field | Type | Notes |
|---|---|---|
| `id` | `UUIDField(primary_key=True, default=uuid4, editable=False)` | |
| `contract` | `ForeignKey(contracts.Contract, on_delete=SET_NULL, null=True, blank=True, related_name="live_sessions")` | Optional; see §11 |
| `version` | `ForeignKey(contracts.ContractVersion, on_delete=SET_NULL, null=True, blank=True, related_name="live_sessions")` | Optional; the version being negotiated |
| `created_by` | `ForeignKey(AUTH_USER_MODEL, on_delete=SET_NULL, null=True, related_name="created_live_sessions")` | Preserved as null if user is deleted |
| `title` | `CharField(max_length=200, blank=True, default="")` | |
| `room_name` | `CharField(max_length=200, unique=True)` | LiveKit room identifier; set at creation as `"bonup-{session_uuid}"` |
| `status` | `CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")` | See choices below |
| `presentation_controller` | `CharField(max_length=20, choices=CONTROLLER_CHOICES, default="initiator")` | Updated via WebSocket only; see §3 |
| `scheduled_at` | `DateTimeField(null=True, blank=True)` | |
| `started_at` | `DateTimeField(null=True, blank=True)` | Set when status transitions to `active` |
| `ended_at` | `DateTimeField(null=True, blank=True)` | Set when status transitions to `ended` |
| `created_at` | `DateTimeField(auto_now_add=True)` | |
| `updated_at` | `DateTimeField(auto_now=True)` | |

**Status choices** (`models.py:15–20`):

| Value | Label |
|---|---|
| `scheduled` | Scheduled |
| `active` | Active |
| `ended` | Ended |
| `cancelled` | Cancelled |

**Presentation controller choices** (`models.py:45–48`):

| Value | Label |
|---|---|
| `initiator` | Initiator |
| `counterparty` | Counterparty |

**Meta:** `ordering = ["-created_at"]`; DB index on `(contract, -created_at)` (`models.py:72–76`)

---

## 3. Core Concepts

### 3.1 LiveKit isolation

`backend/sessions/token.py:4` (file comment): *"Kept isolated so the rest of the codebase doesn't import livekit directly."* The `livekit.api` package is imported only in `token.py:7`. All other code that needs a token calls `generate_token()` from `token.py`. No other domain touches the LiveKit SDK.

### 3.2 LiveSession.room_name and the LiveKit room

`room_name` is set at session creation as `f"bonup-{session_uuid}"` (`views.py:105`). It is unique in the DB (`models.py:51`). When a user joins, the same `room_name` is passed to `generate_token` (`views.py:244`) and returned to the client alongside `LIVEKIT_HOST` (`views.py:252`). The client uses both to connect to LiveKit directly. The backend does not call any LiveKit Room creation API — it only generates join tokens.

### 3.3 WebSocket vs HTTP split

The HTTP routes manage lifecycle state (create, schedule, cancel, join, end). The WebSocket connection (`ws/sessions/<session_id>/` via `SessionConsumer`) handles real-time in-session events that need to be fanned out to all connected participants. Both paths enforce party membership independently.

### 3.4 presentation_controller as in-session state

`presentation_controller` is stored on `LiveSession`. It is updated during a live WebSocket session via the `presentation_control` event handler in `SessionConsumer._update_presentation_controller` (`consumers.py:224–229`). It is not updated by any HTTP endpoint and is included in the HTTP serializer response via `_serialize()` — but `_serialize` in `views.py:23–37` does **not** include `presentation_controller` in its output. See §11.

### 3.5 Channel layer

`CHANNEL_LAYERS` is configured as `InMemoryChannelLayer` (`backend/core/settings.py:176–180`). The `_broadcast_to_group` helper (`views.py:45–53`) wraps `channel_layer.group_send` in a try/except that silently discards all errors. Broadcasts no-op if no channel layer is configured. See §11.

### 3.6 ASGI application

`backend/core/asgi.py` uses `ProtocolTypeRouter` to route HTTP traffic to Django and WebSocket traffic to `URLRouter(websocket_urlpatterns)` from `backend/api/sessions/routing.py`. The WebSocket URL pattern is `ws/sessions/(?P<session_id>[0-9a-f-]+)/` (`routing.py:7`).

---

## 4. Current Behavior (HTTP Routes)

All routes require `IsAuthenticated` (DRF project default) plus party membership. See §9 for access rules.

---

### Route 1 — `GET /api/sessions/`

| | |
|---|---|
| **View** | `SessionListCreateAPIView.get` (`views.py:68`) |
| **Permission** | `IsAuthenticated`; party filter applied at queryset level |
| **What it does** | Returns all `LiveSession` rows across the authenticated user's contracts. Supports `?contract_id=` and `?status=` filters. No pagination. |
| **State transitions** | None |
| **Side effects** | None |

---

### Route 2 — `POST /api/sessions/`

| | |
|---|---|
| **View** | `SessionListCreateAPIView.post` (`views.py:81`) |
| **Permission** | `IsAuthenticated`; billing gate `can_create_session`; `is_party` on the contract |
| **What it does** | Requires `contract_id`; accepts optional `version_id`, `title`, `scheduled_at`. Generates `room_name = f"bonup-{session_uuid}"`. Creates `LiveSession` with `status="scheduled"` inside `transaction.atomic`. Fires `log_activity(..., activity_type="session_held")`. Calls `increment_sessions_used` after commit. |
| **State transitions** | Creates `LiveSession` with `status="scheduled"` |
| **Side effects** | `ContractActivity` row written. `live_sessions_used_this_month` counter incremented. |

---

### Route 3 — `GET /api/sessions/<session_id>/`

| | |
|---|---|
| **View** | `SessionDetailAPIView.get` (`views.py:145`) |
| **Permission** | `IsAuthenticated`; `is_party` on the session's contract |
| **What it does** | Returns a single `LiveSession`. |
| **State transitions** | None |
| **Side effects** | None |

---

### Route 4 — `PATCH /api/sessions/<session_id>/`

| | |
|---|---|
| **View** | `SessionDetailAPIView.patch` (`views.py:151`) |
| **Permission** | `IsAuthenticated`; `is_party` |
| **What it does** | Updates `title` and/or `scheduled_at`. Returns `HTTP 409` if `status != "scheduled"` (`views.py:156–159`). Either party may update. |
| **State transitions** | None |
| **Side effects** | None |

---

### Route 5 — `POST /api/sessions/<session_id>/cancel/`

| | |
|---|---|
| **View** | `SessionCancelAPIView.post` (`views.py:183`) |
| **Permission** | `IsAuthenticated`; `is_party` |
| **What it does** | Returns `HTTP 409` if `status != "scheduled"`. Sets `status = "cancelled"` inside `transaction.atomic`. Fires `log_activity(..., activity_type="session_held")`. Either party may cancel. |
| **State transitions** | `scheduled` → `cancelled` |
| **Side effects** | `ContractActivity` row written. |

---

### Route 6 — `POST /api/sessions/<session_id>/join/`

| | |
|---|---|
| **View** | `SessionJoinAPIView.post` (`views.py:226`) |
| **Permission** | `IsAuthenticated`; `is_party` |
| **What it does** | Returns `HTTP 409` if `status` is `ended` or `cancelled`. If `status == "scheduled"`, transitions to `active` and sets `started_at = timezone.now()` inside `transaction.atomic`. Calls `generate_token(room_name, str(user.id), user.username)`. Returns `{session_id, room_name, livekit_host, token, status}`. |
| **State transitions** | `scheduled` → `active` (if first join) |
| **Side effects** | LiveKit JWT generated. No `ContractActivity` written on join. |

---

### Route 7 — `POST /api/sessions/<session_id>/end/`

| | |
|---|---|
| **View** | `SessionEndAPIView.post` (`views.py:267`) |
| **Permission** | `IsAuthenticated`; `is_party` |
| **What it does** | Returns `HTTP 409` if `status` is `ended` or `cancelled`. Sets `status = "ended"`, `ended_at = now()` inside `transaction.atomic`. Computes `duration_seconds` from `started_at` if set. Fires `log_activity(..., activity_type="session_held")` with duration in metadata. Broadcasts `{"type": "session.ended"}` to the `session_{session_id}` channel group. Either party may end. |
| **State transitions** | `active` → `ended` (or `scheduled` → `ended` — no guard prevents ending a scheduled session) |
| **Side effects** | `ContractActivity` row written. WebSocket `session_ended` broadcast sent to all connected participants. |

---

### Route 8 — `POST /api/sessions/<session_id>/broadcast/`

| | |
|---|---|
| **View** | `SessionBroadcastAPIView.post` (`views.py:326`) |
| **Permission** | `IsAuthenticated`; `is_party`; initiator-only (returns `HTTP 403` for counterparty, `views.py:337–341`) |
| **What it does** | Returns `HTTP 409` if `status != "active"`. Broadcasts `{"type": "session.editor_update", "content": ..., "sender_id": ...}` to the channel group. |
| **State transitions** | None |
| **Side effects** | WebSocket `editor_update` broadcast sent to all connected participants. |

---

### Route 9 — `GET /api/contracts/<contract_id>/sessions/`

| | |
|---|---|
| **View** | `ContractSessionListAPIView.get` (`views.py:365`) |
| **Permission** | `IsAuthenticated`; `is_party` on the contract |
| **What it does** | Returns all `LiveSession` rows for a specific contract. No filters. |
| **State transitions** | None |
| **Side effects** | None |
| **Registration** | `backend/api/contracts/urls.py:141–142` |

---

## 5. WebSocket Flow

**URL:** `ws/sessions/<session_id>/` (`routing.py:7`)  
**Consumer:** `SessionConsumer` (`backend/api/sessions/consumers.py:42`)  
**ASGI wiring:** `backend/core/asgi.py` routes all WebSocket traffic to `URLRouter(websocket_urlpatterns)`

### Authentication

JWT access token passed as `?token=` query parameter (`consumers.py:5`). Browsers cannot set `Authorization` headers on WebSocket connections; this is the documented reason for the query param approach.

On connect (`consumers.py:48`):
1. `_authenticate()` (`consumers.py:180`) extracts `?token=`, validates it via `rest_framework_simplejwt.tokens.AccessToken`, looks up the user by `token["user_id"]`. Returns `None` on any failure → close with code `4001`.
2. `_get_active_session()` (`consumers.py:201`) fetches `LiveSession` with `status="active"` and `select_related("contract")`. Returns `None` if not found or not active → close with code `4002`.
3. `_is_party()` (`consumers.py:212`) checks `contract.initiator_id == user.pk` or `contract.counterparty_email == user.email` → close with code `4003`.

On successful connect: consumer joins the `session_{session_id}` channel group (`consumers.py:71`).

**Close codes:**

| Code | Reason |
|---|---|
| `4001` | Invalid or missing JWT token |
| `4002` | Session does not exist or is not active |
| `4003` | User is not a party to the contract |
| `4004` | Action requires initiator role |

### Inbound events (client → server)

(`consumers.py:82–129`)

| Event type | Who can send | What happens |
|---|---|---|
| `editor_update` | Initiator only (silently ignored for counterparty) | Broadcasts `session.editor_update` with `content` and `sender_id` to channel group |
| `slide_update` | Either party | Broadcasts `session.slide_update` with `slide_index`, `slide_url`, `sender_id` to channel group |
| `presentation_control` | Initiator only (non-initiator is disconnected with code `4004`) | Validates `controller` ∈ `{"initiator", "counterparty"}`; updates `LiveSession.presentation_controller` in DB; broadcasts `session.presentation_control` with `controller` to channel group |

Unknown event types are silently ignored (no explicit handler).

### Outbound events (server → client)

(`consumers.py:135–174`)

| Event type | Trigger | Payload |
|---|---|---|
| `editor_update` | Relayed from `session.editor_update` channel event | `{type, content, sender_id}` |
| `slide_update` | Relayed from `session.slide_update` channel event | `{type, slide_index, slide_url, sender_id}` |
| `presentation_control` | Relayed from `session.presentation_control` channel event | `{type, controller}` |
| `session_ended` | Sent when `session.ended` channel event arrives | `{type: "session_ended"}`; consumer closes after sending |

### Channel layer broadcast

`_broadcast_to_group(group_name, event)` (`views.py:45–53`) is used by HTTP views to push events into the channel group. It calls `async_to_sync(channel_layer.group_send)(...)`. Any exception is silently swallowed. It no-ops if `get_channel_layer()` returns `None`.

---

## 6. Token Generation

**File:** `backend/sessions/token.py:10`

**Signature:**
```python
def generate_token(room_name: str, user_identity: str, user_display_name: str) -> str
```

**How it's called** (`views.py:243–247`):
```python
token = generate_token(
    room_name=session.room_name,
    user_identity=str(request.user.id),
    user_display_name=request.user.username,
)
```

**Claims set on the LiveKit token** (`token.py:20–25`):
- `identity`: passed-in `user_identity` (= `str(user.id)`)
- `name`: passed-in `user_display_name` (= `user.username`)
- `VideoGrants`: `room_join=True`, `room=room_name`

**Credentials:** `settings.LIVEKIT_API_KEY` and `settings.LIVEKIT_API_SECRET`, read from env vars `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET` (`settings.py:186–187`).

**TTL:** No TTL is set explicitly in `generate_token`. The `AccessToken` constructor receives only `api_key` and `api_secret`; `.with_identity`, `.with_name`, `.with_grants` are chained; no `.with_ttl` or equivalent call appears. The effective TTL is whatever the LiveKit SDK default is — not established in this code.

**Response shape from `POST /api/sessions/<id>/join/`** (`views.py:249–255`):
```json
{
  "session_id": "<uuid>",
  "room_name": "<room_name>",
  "livekit_host": "<LIVEKIT_HOST>",
  "token": "<signed_jwt>",
  "status": "<status>"
}
```

**`LIVEKIT_HOST`** is hardcoded as `"https://live.bonup.cloud"` in `settings.py:185` (not an env var).

---

## 7. Lifecycle

### State machine

```
           create
             │
         scheduled ──cancel──► cancelled (terminal)
             │
           join
             │
           active ──end──────► ended (terminal)
```

Both `ended` and `cancelled` are terminal. `join` and `end` both reject with `HTTP 409` for terminal statuses (`views.py:231–235`, `views.py:272–276`).

**Note:** There is no guard preventing `POST /api/sessions/<id>/end/` on a `scheduled` session — the view only checks for `ended` or `cancelled`, not for `active` (`views.py:272–276`). A scheduled session can be transitioned to `ended` directly without ever being `active`.

### Transition triggers

| Transition | API call | File:line |
|---|---|---|
| → `scheduled` (create) | `POST /api/sessions/` | `views.py:108` |
| `scheduled` → `active` | `POST /api/sessions/<id>/join/` (first call only) | `views.py:238–241` |
| `scheduled` → `cancelled` | `POST /api/sessions/<id>/cancel/` | `views.py:195–196` |
| `active` → `ended` | `POST /api/sessions/<id>/end/` | `views.py:284–286` |

### `session_held` activity log

`log_activity` is called with `activity_type="session_held"` at three points (`backend/api/sessions/views.py`):

| Line | When | Description written |
|---|---|---|
| 117 | Session created | `"Live session scheduled[: title]."` |
| 198 | Session cancelled | `"Live session cancelled[: title]."` |
| 288 | Session ended | `"Live session ended[: title][ — Ns]."` |

Duration in seconds is included in the `ended` event metadata when `started_at` is set (`views.py:281, 302`).

---

## 8. Billing Gate

**Gate function:** `can_create_session` from `backend/billing/gates.py`  
**Import:** `backend/api/sessions/views.py:15`  
**Called at:** `views.py:82` — first check inside `SessionListCreateAPIView.post`. If `(False, message)`, returns `HTTP 403` immediately before any other validation.

**Usage counter:** `increment_sessions_used` from `backend/billing/gates.py`  
**Called at:** `views.py:132` — after the session and activity record are created and the transaction is committed.

No billing gate exists on any other session route (join, end, cancel, broadcast, list, detail).

---

## 9. Authority / Access Rules

- All HTTP routes require `IsAuthenticated` (DRF project default). No view sets a different permission class.
- All routes except `GET /api/sessions/` enforce `is_party(request.user, contract)` from `backend.api.contracts.permissions`. Non-parties receive a 403-equivalent from `contract_party_response()`.
- `GET /api/sessions/` applies the party filter at the queryset level via `_party_q_sessions(user)` (`views.py:40–42`): `contract__initiator=user OR contract__counterparty_email=user.email`.
- `POST /api/sessions/<id>/broadcast/` additionally requires the caller to be the contract initiator (`views.py:337`). Counterparties receive `HTTP 403`.
- WebSocket `SessionConsumer` authenticates via JWT in `?token=` query param (`consumers.py:188–198`). Party check is re-enforced at connection time (`consumers.py:67–69`). Initiator-only events (`editor_update`, `presentation_control`) are enforced inside the consumer (`consumers.py:92, 116`).
- No admin-only or staff-only routes exist in this domain.

---

## 10. Relationship to Other Domains

### Contracts (`backend/contracts/`)

`LiveSession.contract` is a nullable FK to `Contract` (`models.py:24`). `LiveSession.version` is a nullable FK to `ContractVersion` (`models.py:31`). The contract-scoped session list route is registered under the contracts URL namespace (`backend/api/contracts/urls.py:141–142`). All party checks in this domain query the associated contract.

### Negotiation Prep (`backend/negotiation_prep/`)

`PrepSession.live_session` is a nullable FK to `"live_sessions.LiveSession"` (`negotiation_prep/models.py:23`). `backend/api/prep/views.py:16` imports `LiveSession` and resolves an optional `live_session_id` when creating a `PrepSession` (`prep/views.py:99`). The prep domain consumes sessions; it does not modify them.

### Uploads (`backend/uploads/`)

`Upload.related_session` is a nullable FK to `"live_sessions.LiveSession"` (`uploads/models.py:43`). The uploads domain can associate a file with a session at upload time. The sessions domain does not reference `Upload`.

### Search (`backend/api/search/`)

`backend/api/search/views.py:18` imports `LiveSession` and queries it as part of full-text search results (`search/views.py:333, 550`). Read-only consumer.

### Audit Activity (`backend/activity/`)

`log_activity` is called from `views.py:117, 198, 288` with `activity_type="session_held"`. The activity domain is documented in `audit_activity.md`.

### Billing (`backend/billing/`)

`can_create_session` and `increment_sessions_used` from `billing/gates.py` are consumed here. The billing domain is documented in `billing.md`.

### Contract Pro (`backend/contract_pro/`)

`backend/contract_pro/models.py:131` defines `START_BOARDROOM_SESSION` and `START_EXTERNAL_SESSION` as string constants in the `ContractProPermission` enum. These are permission name strings only — `contract_pro` does not import `LiveSession` or any sessions code.

---

## 11. Current Gaps

1. **LiveKit token has no explicit TTL.** `generate_token` (`token.py:10`) calls `AccessToken(...).with_identity(...).with_name(...).with_grants(...).to_jwt()` with no `.with_ttl()` or equivalent call. The effective token lifetime is whatever the LiveKit SDK default is — not established in this code. A token issued to a user who later loses party status or whose session is cancelled may remain valid until it expires naturally.

2. **`CHANNEL_LAYERS` uses `InMemoryChannelLayer`.** (`settings.py:176–180`). `InMemoryChannelLayer` is in-process only and does not share state across multiple server processes or workers. In a multi-process deployment, WebSocket broadcasts from HTTP views (`_broadcast_to_group` in `views.py:45`) may not reach clients connected to a different worker. Production use requires a Redis-backed channel layer (`channels_redis`).

3. **`LiveSession.contract` is `SET_NULL` nullable but `POST /api/sessions/` requires `contract_id`.** The model allows a `LiveSession` without a contract (`models.py:26–30`), but the API enforces `contract_id` as required (`views.py:86–91`). A `LiveSession` with `contract=None` can exist in the DB if the contract is deleted after session creation. Party checks on such a session would fail unpredictably (e.g., `session.contract` would be `None` when `is_party` tries to access `contract.initiator_id`).

4. **No LiveKit webhook handler.** The LiveKit server can emit events for room creation, participant join/leave, recording, disconnection, and more. None of these are handled. Disconnects, room state changes, and recording events are not observed by the backend.

5. **`presentation_controller` is updated only via WebSocket; not reflected in the HTTP serializer.** `SessionConsumer._update_presentation_controller` writes to `LiveSession.presentation_controller` in the DB (`consumers.py:227`). The `_serialize` function in `views.py:23–37` does not include `presentation_controller` in its output. Whether this omission is intentional is not established in code.

6. **`scheduled` sessions can be transitioned directly to `ended`.** `SessionEndAPIView.post` (`views.py:267`) checks only for `status in ("ended", "cancelled")` before allowing the transition. A session that was never joined (never `active`) can be marked `ended`, which would leave `started_at = None` and produce a `duration_seconds = None` in the activity log.

---

## 12. Open Questions

1. **What is `LIVEKIT_HOST = "https://live.bonup.cloud"` hardcoded for?** (`settings.py:185`) It is not an env var. Is this a permanent production host? Other LiveKit settings (`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`) are env-driven but the host is not.

2. **Is there an intended Redis migration for `CHANNEL_LAYERS`?** The `InMemoryChannelLayer` setting is functional for single-process development but breaks multi-worker production. No Redis URL for channels was found in `settings.py`.

3. **Is the `presentation_controller` field meant to be read via HTTP?** It is stored in the DB and updated by the WebSocket consumer, but `_serialize` does not expose it to HTTP clients. If clients need the current controller on page load, they cannot retrieve it through the session detail endpoint.

4. **Can a party rejoin a session after it's been ended?** `SessionJoinAPIView` blocks join for `ended` and `cancelled` statuses (`views.py:231`), but there is no HTTP endpoint to re-open an ended session. Whether this is intentional is not established in code.

---

## 13. Update Rule

Update this file when code changes `LiveSession`, `generate_token`, any session HTTP view or URL, `SessionConsumer`, ASGI routing, LiveKit settings, or channel layer configuration.
