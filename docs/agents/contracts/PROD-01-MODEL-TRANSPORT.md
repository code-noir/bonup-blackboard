# PROD-01 Bounded Model Transport

> Status: non-active development contract
> Authority: **PROPOSAL_ONLY — NOT EXECUTION AUTHORITY**

The trusted PROD-01 model boundary validates a bounded product task, projects
only its identity, objective, reference metadata, behavioral limits, and required
proposal schema, and permits one structured model request. References are not
dereferenced. The request exposes no execution tools, filesystem, shell, Git,
deployment, web, or Agent Control operations.

The endpoint, logical model identifier, timeout, redirect behavior, and environment
trust are fixed by trusted code rather than task or model content. A credential is
obtained through a trusted provider and passed only to the injected transport. It is
not serialized into context, requests, proposals, task documents, or audit metadata.

The bounded model layer emits a deterministic internal request contract containing
the PROD-01 identity, logical model binding, bounded context, zero tools, closed
proposal schema and digest, and one-request/zero-retry policy. These internal fields
do not claim provider semantics or authority. Only the OpenAI HTTP adapter translates
that contract into provider-specific `model`, `input`, `text.format`, `tools`, and
`store` fields. Task, Founder, and model content cannot select or modify that mapping.

Each cycle permits exactly one request, zero retries, no fallback, no repair call,
and no autonomous loop. The bounded Responses envelope may contain reasoning before
the result, but must contain exactly one completed assistant `message` with exactly
one `output_text` part. That text is parsed as strict JSON and must pass
`validate_product_proposal()`, retain `WORKING` knowledge state, and use only
evidence references bound by the task. Refusals, incomplete responses, tool/function
output, unknown content, and ambiguous proposal text fail closed.

The request also instructs the model to copy the task identity exactly, use only
input-bound evidence references, emit canonical UUID proposal identities, keep an
initial predecessor null, avoid authority-status claims, and omit secrets. The
schema rejects `ATS-0000`, whitespace-only text, malformed reference identities, and
invalid reference data, while duplicate dependencies remain a runtime-only
invariant because `uniqueItems` is outside the reviewed provider subset. These
provider constraints are defense in depth: exact task/evidence binding, authority
language, secret patterns, duplicate dependencies, and all generic proposal rules
remain enforced after receipt by `validate_product_proposal()` and the cycle
boundary. The generic validator permits a valid predecessor for later
`REQUEST_CHANGES` revisions; the first-live boundary separately requires a null
predecessor and rejects `INITIAL_PREDECESSOR_INVALID` before accepting ATS-1201.

Narrative authority protection rejects bounded assertions that work or authority is
already complete or granted, including implemented, tested, approved, authorized,
deployed, assigned, published, complete, and passed status forms. Future
requirements and acceptance conditions using modal or hypothetical language remain
valid. Explicit authority-like fields remain rejected by the closed proposal field
set regardless of narrative wording.

Output failures retain only bounded code-owned classifications and, for provider
envelope failures, a structural fingerprint. Envelope reasons distinguish response
bytes/JSON/object/status/output shape, message status/role, content shape, refusal,
unexpected item types, missing or multiple assistant/output-text parts, and output
size. The fingerprint is capped to eight values per structural list and contains
only the allowlisted response status, bounded item type/status/role names, counts,
and a refusal boolean. It never retains output text, refusal text, reasoning,
annotations, IDs, arbitrary metadata, field values, or credentials. Unknown type
values are reported only when they match the bounded ASCII identifier rule;
otherwise they become `UNSAFE_TYPE`. The parser still requires one completed
assistant message with one output-text proposal before strict JSON and runtime
proposal validation. This improves future diagnostics but cannot retrospectively
identify a reason that an earlier execution discarded.

Transport failures retain only an allowlisted code-owned classification. HTTP
401, 403, 404, 429, other 4xx, and 5xx responses map respectively to bounded
authentication, permission, not-found, rate-limit, request-rejected, and
server-error classes. Timeout, connection/TLS, and response-size failures are
separate bounded classes; unexpected JSON media types, unsupported response
encodings, and truncated responses are separate bounded classes; unknown adapter
failures remain `PROVIDER_ERROR`. Provider bodies, status text, request content,
credentials, and arbitrary headers are never included in diagnostics. The HTTP
adapter retains only bounded response metadata: HTTP status, JSON/missing/other
content-type classification, missing/identity/gzip/deflate/other encoding
classification, bounded collected-byte count, empty-body state, bounded
Content-Length state, and decode-stage booleans. `iter_content()` receives bytes
with `decode_unicode=False`; the requests/urllib3 path may transparently decode
the explicitly accepted gzip or deflate content encodings before the byte bound
and JSON parser see the chunks. The bound therefore applies to decompressed
parser input. A non-200 response still makes exactly one attempt and never
triggers a retry or repair request.

The adapter sends one ordinary JSON Responses request: its local `stream=True`
flag controls bounded response reading and is not an SSE request field. It sends
`Accept: application/json` and never requests `text/event-stream`; unexpected
content types are rejected before proposal parsing. Empty, invalid-UTF-8,
malformed, and content-length/truncation cases fail closed with bounded reasons.

The bounded model module remains transport-neutral, and its tests use an injected
in-memory transport and synthetic credential marker. The separate hardened HTTP
adapter described below is tested only against a loopback fake server. No live
provider request is made, and the existing deterministic synthetic cycle remains
unchanged.

The owner-approved provider binding is fixed as follows:

```text
PROD-01-STRUCTURED-MODEL-V1 -> OpenAI Responses API -> gpt-5.6-luna
POST https://api.openai.com/v1/responses
```

The hardened `requests` adapter uses a new session for each call, sets
`trust_env = False`, supplies fixed authorization/content headers, requires normal
TLS certificate verification, disables redirects, uses explicit 5-second connect
and 30-second read bounds, streams at most 65,536 response bytes, accepts only HTTP
200, and performs no retry, fallback, or repair request. Provider error bodies are
not read into diagnostics. Its production constructor has no endpoint or model
arguments. An underscored test-only factory accepts only an explicit numeric
loopback host and the exact `/v1/responses` path; local-server tests do not contact
external networks.

The committed `text.format` JSON Schema request shape remains
**PRE-LIVE-UNVERIFIED** because official documentation could not be retrieved in the
local review environment; no alternate shape was guessed. Before one live request,
the remaining prerequisites are an owner-approved production
credential source and composition mechanism that injects the OpenAI credential only
into `InjectedOpenAICredentialProvider`, plus a transport-only pre-live fixture check
against the current official Responses request/response envelope and confirmed
account access to the owner-selected `gpt-5.6-luna` model. Account access status is
`ACCOUNT_ACCESS_REQUIRES_AUTHENTICATED_CHECK`. The offline parser is
intentionally fail-closed; unverified provider-envelope behavior must not be assumed
to work or bypass validation. No environment-variable, file, keyring, or
service-secret source is selected by this contract.

Readiness is represented by three separate values and never implies `LIVE_READY`:

```text
LOCAL_CONTRACT_VALIDATED = true
PROVIDER_WIRE_COMPATIBILITY = LIVE_OR_OFFICIAL_CHECK_REQUIRED
ACCOUNT_MODEL_ACCESS = AUTHENTICATED_CHECK_REQUIRED
```

After that separate approval, the pre-authorized live procedure is exactly one
synthetic PROD-01 task, one POST to the fixed endpoint using `gpt-5.6-luna`, zero
execution tools, one structured `PRODUCT_REQUIREMENT_PROPOSAL`, strict validation,
a `WORKING` proposal, no automatic Founder approval, then stop. Live use and
PROD-01 activation remain separate approvals; the proposal is never routed
automatically to ARCH-01.
