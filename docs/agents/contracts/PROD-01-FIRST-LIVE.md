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
7. After validation, the exact canonical proposal is persisted as an immutable,
   non-authoritative artifact under `/var/lib/bonup-prod/proposals/` using the
   proposal ID as its deterministic identity. Artifact creation failure is a
   failed cycle; it does not trigger another request or claim durable success.
8. Review the bounded proposal output; it is not Founder approval.
9. Allow the process to exit after the single cycle.
10. Report only safe output, never the API key, to ChatGPT or Codex.

The command creates no AgentRecord, grant, assignment, registry state, task document,
ARCH routing, deployment, or application change. Python reference disposal is not a
claim of physical memory zeroization.

Failed output is reported only through a bounded, code-owned classification. No raw
provider envelope, model text, hidden reasoning, credential, or rejected field value
is printed or persisted. A classification identifies the validation stage only; it
does not make rejected output recoverable or authorize a retry. The generic proposal
validator continues to support non-null predecessor linkage for later,
separately reviewed `REQUEST_CHANGES` revisions.

The artifact is a bounded canonical object containing the validated proposal and
its task, proposal, model, source-checkpoint, validation, knowledge-state, and
artifact-digest bindings. It contains no provider envelope, request, credential,
reasoning, or execution authority. The current Founder review implementation
remains synthetic-only; an authenticated production Founder review adapter is a
separate prerequisite.

The historical first successful ATS-1201 proposal was not durably captured by
the prior command. Its known identity and digest are historical evidence only;
no artifact or Founder decision may be fabricated for it.
