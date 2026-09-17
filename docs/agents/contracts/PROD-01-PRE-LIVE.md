# PROD-01 Development Pre-Live Gate

> Status: development dry-run only
> Authority: **NO LIVE TRANSMISSION — NOT EXECUTION AUTHORITY**

`tools.agent_control.prod_prelive` prepares the fixed synthetic first-live task
and validates the complete bounded request policy, but it has no live option and
never constructs or calls the HTTP adapter. It reports `LIVE_CHECK_REQUIRED` for
provider availability and account access.

The development launcher obtains a credential through Python's hidden terminal
input. The credential is not accepted through argv, environment variables,
`.env`, files, task content, or model content. The one-shot provider cannot be
serialized, hides the value from `repr` and exceptions, permits one future
consumption, and is explicitly discarded when the dry-run command exits. It is
not an installed-service or production credential mechanism.

Python cannot promise physical memory zeroization: discarding the reference
shortens its lifetime but does not prove that every interpreter/runtime copy was
overwritten. Production credential provisioning remains a separate owner design.

The gate compares the current repository `HEAD` with an exact 40-character
commit identity supplied separately by the trusted launcher from owner review.
The expected identity is not embedded in the validator (which would create a
circular self-hash), and it cannot come from PROD-01 task or model content. The
development binding object is not cryptographic Founder authentication; a
separate owner-authorized live task must supply and approve it.

The gate also verifies valid `NON_ACTIVE` and
`PROPOSAL_ONLY` contract; all-false system permissions; fixed OpenAI endpoint,
provider, logical model, and `gpt-5.6-luna` binding; zero tools; strict structured
output; `WORKING` knowledge state; 65,536-byte request bound; one request; zero
retries; disabled redirects and environment trust; fixed timeouts; and explicit
no-approval/no-assignment/no-execution behavior.

The exact task is `ATS-1201`, class `PRODUCT_REQUIREMENT`, with objective:

> Define the product requirements for displaying agent task history in the
> bonUP interface.

It contains one deterministic synthetic Founder-direction reference and no
customer data or dereferenced repository content.

Safe dry-run output is limited to gate/live-check status, source/task/agent
identity, fixed endpoint and model identities, request digest and byte count,
zero tool count, request/retry limits, timeouts, and `credential_present` as
`YES`/`NO`. It never prints the credential, authorization header, prompt, raw
request, response, or reasoning.

The dry-run command requires the separately reviewed checkpoint identity:

```text
python -m tools.agent_control.prod_prelive --expected-source-commit <40-hex-commit>
```

The next step requires a separate owner-authorized task: validate the current
official provider envelope and
model/account access, decide the approved credential interaction, and authorize
exactly one transmission. This document does not authorize that request,
Founder approval, ARCH routing, agent activation, provisioning, or Milestone 4.
