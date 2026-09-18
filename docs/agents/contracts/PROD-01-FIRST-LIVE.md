# PROD-01 Founder-Run First Inference

> Status: review required before use
> Authority: **ONE PROPOSAL-ONLY INFERENCE — NOT AGENT ACTIVATION**

After this command is reviewed, committed, and pushed, the Founder runs:

```text
python3 -B -m tools.agent_control.prod_first_live \
  --expected-source-commit <OWNER-REVIEWED-CHECKPOINT>
```

The command binds two distinct identities before requesting a credential:

- a stable security/provider contract covering PROD-01, model and endpoint
  bindings, zero tools, schema, limits, parser/validator, WORKING state, and no
  Founder auto-approval or ARCH routing;
- the exact deterministic ATS-1201 internal and provider-wire request instances.

The historical wire digest
`bdc532506e2d4ce59a4dd41af440a0a4ef3bba21a865df5d9060c58c638f759d`
belongs only to the older ATS-0701 fixture. It is not a universal contract digest.

Founder procedure:

1. Open an ordinary VPS terminal.
2. Run the exact reviewed command.
3. Allow source and dual contract/request bindings to verify before the prompt.
4. Enter the dedicated bonUP OpenAI key only at the hidden prompt.
5. The command may make exactly one inference request with zero tools and retries.
6. The response is strictly parsed and validated as a WORKING proposal with a null
   `predecessor_proposal_id`; a non-null initial predecessor is rejected.
7. Review the bounded proposal output; it is not Founder approval.
8. Allow the process to exit after the single cycle.
9. Report only safe output, never the API key, to ChatGPT or Codex.

The command creates no AgentRecord, grant, assignment, registry state, task document,
ARCH routing, deployment, or application change. Python reference disposal is not a
claim of physical memory zeroization.

Failed output is reported only through a bounded, code-owned classification. No raw
provider envelope, model text, hidden reasoning, credential, or rejected field value
is printed or persisted. A classification identifies the validation stage only; it
does not make rejected output recoverable or authorize a retry. The generic proposal
validator continues to support non-null predecessor linkage for later,
separately reviewed `REQUEST_CHANGES` revisions.
