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

Each cycle permits exactly one request, zero retries, no fallback, no repair call,
and no autonomous loop. The bounded Responses envelope may contain reasoning before
the result, but must contain exactly one completed assistant `message` with exactly
one `output_text` part. That text is parsed as strict JSON and must pass
`validate_product_proposal()`, retain `WORKING` knowledge state, and use only
evidence references bound by the task. Refusals, incomplete responses, tool/function
output, unknown content, and ambiguous proposal text fail closed.

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

After that separate approval, the pre-authorized live procedure is exactly one
synthetic PROD-01 task, one POST to the fixed endpoint using `gpt-5.6-luna`, zero
execution tools, one structured `PRODUCT_REQUIREMENT_PROPOSAL`, strict validation,
a `WORKING` proposal, no automatic Founder approval, then stop. Live use and
PROD-01 activation remain separate approvals; the proposal is never routed
automatically to ARCH-01.
