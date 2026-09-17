# bonUP 12-Agent Authority Requirements

> Status: Owner-review requirements specification
> Authority: **THIS DOCUMENT GRANTS NOTHING**
> Scope: least-authority requirements for the roster in `docs/agents/ROSTER.md`
> Updated: 2026-09-16

## 1. Purpose and interpretation

This document describes what each bonUP agent needs, may need later, and must
not have by default. It does not modify Agent Control policy, create an
`AgentRecord`, grant execution, assign a task, reserve a resource, create an OS
identity/workspace, authorize data access, approve publication, or activate an
agent.

Legend:

- **N — NEEDS:** required for the role, but still subject to a task, scope,
  controller, data, or publication grant where applicable.
- **L — MAY NEED LATER:** plausible only under a separate reviewed use case and
  explicit least-authority grant.
- **D — MUST NOT HAVE BY DEFAULT:** denied unless a later owner-approved policy
  explicitly establishes a narrower exception. Some powers, such as
  self-approval, remain prohibited rather than merely deferred.

`N` is a requirement, not present authority. Current authority for the original
four comes only from Agent Control policy and validated records.

## 2. Current Phase-I authority baseline

All four current `AgentRecord` identities are seeded `DISABLED`; policy
capabilities do not mean an active session or executable grant.

| Agent | Current authoritative contract | Current explicit limits |
|---|---|---|
| `ARCH-01` | `READ_SANITIZED`, `PROPOSE_SPEC`, `COORDINATE`, `RECORD_FINDING`, `RESOLVE_TECHNICAL`; write root limited to `docs/agent-control/proposals`; may revise task specifications through authorized lifecycle operations | No application write, local commit, merge, push, deployment, founder approval, activation, or unrestricted grant authority |
| `FE-01` | `READ_SANITIZED`, `WRITE_ASSIGNED`, `COMMIT_LOCAL`, `RECORD_FINDING`; role roots `frontend` and `docs`, further narrowed by approved task assignment and exact grant | No merge, push, specification change, deployment, or authority outside assigned scope |
| `BE-01` | `READ_SANITIZED`, `WRITE_ASSIGNED`, `COMMIT_LOCAL`, `RECORD_FINDING`; role roots `backend`, `tools`, `tests`, and `docs`, further narrowed by approved task assignment and exact grant | No merge, push, specification change, deployment, or authority outside assigned scope |
| `QA-01` | `READ_SANITIZED`, `TEST_SYNTHETIC`, `REVIEW_CANDIDATE`, `RECORD_FINDING`; no default write root; assigned independent QA owns QA review/pass transitions | No repair/application write, local commit, merge, push, specification approval/change, deployment, or self-approval |

The future requirements below do not expand this baseline.

## 3. Least-authority matrix

| # | Authority dimension | ARCH | FE | BE | QA | PROD | RES | BI | CX | MKT | SEC | DOC | EDU |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | Knowledge access | N | N | N | N | N | N | N | N | N | N | N | N |
| B | Repository read | N¹ | N¹ | N¹ | N¹ | L¹ | N¹ | L¹ | L¹ | L¹ | N¹ | N¹ | L¹ |
| C | Repository write | N² | N² | N² | D | L² | D | D | D | D | D³ | L² | D |
| D | Local code execution | D | N⁴ | N⁴ | L⁴ | D | L⁴ | N⁵ | D | D | L⁴ | D | D |
| E | Local Git commit | D | N² | N² | D | D | D | D | D | D | D³ | L² | D |
| F | Merge/integration | D | D | D | D | D | D | D | D | D | D | D | D |
| G | Push | D | D | D | D | D | D | D | D | D | D | D | D |
| H | Test execution | L⁴ | N⁴ | N⁴ | N⁴ | D | L⁴ | L⁵ | D | D | L⁴ | D | D |
| I | Security evidence access | L¹ | L¹ | L¹ | N¹ | D | L¹ | D | D | D | N¹ | L¹ | D |
| J | Product/customer insight access | L⁶ | D | D | L⁶ | N⁶ | L⁶ | N⁶ | N⁶ | N⁶ | L⁶ | L⁶ | L⁶ |
| K | Production database access | D | D | D | D | D | D | D⁵ | D | D | D | D | D |
| L | Customer-identifiable data | D | D | D | D | D | D | L⁶ | L⁶ | D | L⁶ | D | D |
| M | External web/research | L⁷ | L⁷ | L⁷ | L⁷ | L⁷ | N⁷ | L⁷ | L⁷ | L⁷ | L⁷ | L⁷ | L⁷ |
| N | External publication | D | D | D | D | D | D | D | D | L⁸ | D | L⁸ | L⁸ |
| O | Agent-to-agent task proposal | N⁹ | L⁹ | L⁹ | L⁹ | N⁹ | N⁹ | N⁹ | N⁹ | N⁹ | N⁹ | N⁹ | N⁹ |
| P | Agent assignment/delegation | N¹⁰ | D | D | D | D | D | D | D | D | D | D | D |
| Q | Deployment | D | D | D | D | D | D | D | D | D | D | D | D |
| R | Host/system administration | D | D | D | D | D | D | D | D | D | D | D | D |
| S | Credential/secret access | D | D | D | D | D | D | D | D | D | D | D | D |
| T | bonUP knowledge publication | L⁸ | D | D | D | L⁸ | L⁸ | L⁸ | L⁸ | L⁸ | L⁸ | N⁸ | N⁸ |

Matrix qualifiers:

1. Read access is task-scoped, sanitized, and limited to needed repositories,
   candidates, documents, or evidence references. `N` never means unrestricted
   repository or evidence access.
2. Writes/commits are limited to an exact approved task and path scope. ARCH's
   current write root remains proposal documentation; FE/BE retain their current
   assigned engineering model. Future PROD/DOC writes would be documentation-only
   and require a separate policy. No cell authorizes the write now.
3. SEC independent review defaults to read/findings only. A separate remediation
   task could grant bounded write/commit authority, but SEC must then be treated
   as implementer and cannot independently approve that repair in the same review.
4. Execution/testing requires a bounded synthetic workspace, allowlisted command,
   time/resource limits, sanitized inputs, and controller authorization. No role
   receives unrestricted shell or host execution.
5. BI analytical execution uses approved, minimized datasets in a bounded
   analysis environment. A later read-only export/query service is not
   unrestricted production-database access; direct production DB remains denied
   by default.
6. Insight/data access must be minimized, purpose-bound, and approved. Aggregate
   or de-identified data is preferred. Customer-identifiable data requires a
   separate explicit grant and must never imply customer-secret access.
7. Web/research access is task-authorized, source-bounded, and must not transmit
   repository secrets, customer content, credentials, or unapproved internal data.
8. Drafting is distinct from publication. External publication and movement to a
   publication-eligible knowledge level require separate founder/publication
   approval. DOC/EDU knowledge publication means controlled internal knowledge
   preparation, not automatic public release or Speaker ingestion.
9. A proposal is nonbinding work/request metadata. It cannot create a task grant,
   launch an agent, reserve resources, or compel another agent.
10. ARCH may propose assignments and coordinate dependencies, and may use only
    the already-authorized task-assignment operations. ARCH cannot mint grants,
    approve on behalf of the founder, activate agents, or bypass QA/SEC.

## 4. Role-specific boundaries

### ARCH-01 coordination

ARCH needs sanitized technical knowledge, specification proposals, assignment
proposals, and dependency coordination. Coordination does not confer founder
approval, unrestricted agent grants, activation, deployment, merge, push, or a
right to bypass QA/SEC. Every executable assignment still requires the bonUP
task, approval, grant, fencing, and controller path applicable at that time.

### Product and analysis agents

- `PROD-01` needs approved product knowledge, task/product documentation,
  approved CX/BI outputs, and proposal drafting. Engineering writes, execution,
  commits, push, deployment, production DB, customer secrets, administration,
  and self-approval are denied by default.
- `RES-01` needs approved technical documentation, scoped sanitized reads,
  task-authorized research access, and findings/proposal output. It cannot approve
  architecture, write applications, commit/push, deploy, use production
  credentials, or receive unrestricted execution.
- `BI-01` needs approved/sanitized datasets, bounded analytical execution, and
  report output. Future bounded data grants must specify dataset, purpose,
  columns/identifiers, environment, retention, and outputs. They are not direct
  or unrestricted production DB authority.
- `CX-01` needs approved feedback and aggregate support/product insight plus
  proposal/document output. Unrestricted customer records, production DB,
  engineering writes, deployment, and unapproved publication remain denied.

### Knowledge and communication agents

- `MKT-01` needs approved product truth, DOC knowledge, approved CX/BI insights,
  and content drafting. Drafts cannot be externally published without approval;
  unsupported claims, customer secrets, engineering writes, deployment, and
  production administration remain denied.
- `DOC-01` needs approved task documents, findings, architecture/product/security
  knowledge, evidence references, and bounded documentation drafting. Documents
  cannot create authority, change evidence, write engineering code by default,
  expose credentials/customer secrets, deploy, or publish externally by default.
- `EDU-01` needs approved DOC/domain knowledge, educational drafting, and
  clarification proposals. Educational material cannot alter source truth,
  create execution authority, expose secrets, execute/write systems by default,
  deploy, or publish externally without approval.

## 5. QA-01 and SEC-01 independence

`QA-01` primarily evaluates functional/integration correctness and required test
evidence. `SEC-01` primarily evaluates security boundaries, threats, release
risk, and security evidence. They may inspect overlapping candidates and
evidence, but their conclusions remain separately attributable.

Neither agent may repair a finding and count that same work as independent
approval within the same review assignment. If either agent receives a separate,
explicitly authorized remediation task, it becomes the implementer for that
change. A different independent reviewer must validate the resulting candidate,
and prior review evidence must remain distinguishable from remediation evidence.
Neither QA nor SEC receives merge, push, deployment, self-approval, production
credentials, or arbitrary host-administration authority by default.

## 6. Agent proposals are not grants

An agent may propose work to another agent when its role permits collaboration.
That does not mean it may assign executable authority, create a grant, launch a
worker, reserve a resource, expand scope, or activate another agent. Future
delegation must pass through the bonUP authority/controller model with validated
identity, approved task/specification, exact scope, grant, fencing, resource,
and evidence requirements. Collaboration arrows in `ROSTER.md` grant nothing.

## 7. Knowledge authority levels

These levels describe documentation handling only; they are not implemented
publication policy:

1. **WORKING** — agent-produced or unapproved drafts, findings, analyses, and
   educational/marketing material. Other agents may use them only as attributed
   working inputs, never as approved bonUP truth.
2. **APPROVED INTERNAL** — validated and owner/policy-approved bonUP knowledge
   usable internally by authorized agents for the approved purpose. Approval does
   not make sensitive material public or broaden access.
3. **PUBLICATION-ELIGIBLE** — approved, sanitized knowledge that has passed the
   required factual, security, privacy, product, and publication review. It may
   later be supplied to public-facing entities such as the bonUP Speaker, but the
   classification alone does not publish it.

Promotion between levels requires an attributable approval process defined by a
future publication policy. Agents cannot self-promote their output merely by
labeling it approved or publication-eligible.

## 8. Consistency result

This requirements specification is consistent with `ROSTER.md` and the current
Phase-I policy:

- the existing four retain their current boundaries;
- the eight new identities remain recommendation-only and receive no Phase-I
  execution grants;
- founder-controlled approval, integration, push, and final release authority
  are not reassigned;
- no deployment, production DB, host administration, credentials, or external
  publication is granted by default; and
- proposed collaboration remains non-executable.

No contradiction requiring a current policy change was found.
