# bonUP generation-1 installation approval

This correction preserves the historical candidate in `review/m3-generation-1`.
It adds repository-side approval tooling in `installation_approval.py`; it does
not change the 56 installed runtime/policy/configuration artifacts. It supplies
no privileged installer, service startup, host-test runner or activation command.

## Three distinct records

1. The committed candidate remains `approved=false`, `activation=false`, with
   exact bytes identified by SHA-256. Its `source_commit` names the historical
   base (`be8270e...`); the new outer approval binding also names the committed
   composition checkpoint `3e0749cf0d323952b2f6f3f7945e8fda1b258b51`.
2. `review/m3-generation-1-approval-proposal/proposed-approval-stage.json` is a
   deterministic **PROPOSED_APPROVAL_STAGE** envelope. Its nested installation
   manifest represents `approved=true`, `activation=false`, and
   `integration_services_approved=false`. That nested boolean is a proposed
   permission state, not evidence that the founder approved anything. The envelope
   contains the exact proposed manifest, detached installation inventory, and
   digests binding both to the candidate. No timestamp or approval ID is invented.
3. A later installation decision records INSTALL_ONLY, a fresh approval UUID,
   actual approval timestamp, founder UID and the complete proposal binding/digest.
   `approval_record` and every installation/receipt authority gate require an
   independently authenticated founder context. Serialized fields cannot mint
   that context. Generation never calls `approval_record`.

The later trusted installer must obtain the explicit founder decision through its
reviewed authentication boundary, pin/root-protect approved input bytes and retain
that evidence. Reading `approved=true`, a matching digest, a generated envelope or
an arbitrary JSON decision is insufficient. Existing `AuthenticatedContext` is a
trusted in-process input, not a cryptographic signature; caller JSON must never
construct it. This correction does not implement that future privileged boundary.

## Closed transformation and installed hashes

`propose` accepts only the exact pinned candidate bytes. It copies them in memory,
changes only `approved`, then recomputes `bundle_digest` with existing canonical
serialization. Every other field, including activation and service-start approval,
is unchanged. `validate_proposal` recomputes and compares the entire envelope;
rehashing a changed policy cannot make it acceptable.

The installed rule is now: **all 57 files match the approved installation
inventory**. The 56 non-manifest artifacts retain the candidate hashes. Only
`/etc/bonup-agent-control/approved-installation.json` has the separately reviewed
approved-representation hash. The candidate remains a historical repository input,
not the installed permission manifest. The approval envelope and decision are
installer review/evidence records, not extra runtime imports or a replacement
runtime bundle. New tooling must later be installed into root-controlled installer
staging and verified before privileged execution, never run from the checkout.

Future candidates are not accepted by these historical constants. Their approval
identity must be derived from the exact candidate bytes and bind the selected
source commit, manifest digest, bundle digest, artifact inventory, provisioning
generation and policy digests. A historical approval therefore cannot authorize a
new candidate.

Current event-delivery candidates use installation schema v5. In addition to the
existing v4 inventory, v5 binds `projection_scope`: the canonical event-delivery
file and digest, the Registry database path, Git history path, target schema v3,
and initialize/migrate/verify intent, the fixed production Django identity (`www-data`, `33:33`,
`/srv/bonup-web`, `backend.core.settings`), the projection socket and secure
parent ownership/modes, and the exact trusted Django unit identity/path/command
and generated unit digest. The privileged installer must match its explicit
runtime options to this scope; it cannot supply a different peer, path, mode,
service, or application identity after approval. v4 validation remains available
for historical bundles and does not acquire v5 semantics.

The PROD-01 production candidate uses installation schema v6. v6 retains the v4
and v5 semantics without reinterpretation and additionally binds the controller-owned
product runtime scope, including the fixed PROD-01 configuration, application
socket, credential contract, runtime closure, controller unit hash, and exact
artifact-store authority. The proposal store is
`/var/lib/bonup-prod/proposals` (`bonup-agentctl:bonup-agentctl`, `0700`). Its
parent is `root:root`, `0711`, and is not a controller `ReadWritePaths` entry.
The v6 candidate remains `approved=false`, `activation=false`, and
`integration_services_approved=false`; changing this scope invalidates the
candidate identity and requires a new review.

### Historical v4/v5 identity record

The following identities are **HISTORICAL**, **SUPERSEDED**, and **DO NOT USE
FOR CURRENT V6 APPROVAL**. They are retained only as evidence for the earlier
generation-1 candidate and its proposed installation transformation:

Historical candidate manifest byte SHA-256:
`034036d04043c470e67a050e827f1312445017069e1f234e3f096fa5864adbb6`

Historical candidate bundle digest:
`cdaf9528de71fd64cf60c44d916cb0d3632adf5e7245b3cc5e11b4a782ea72e4`

Historical proposed installation manifest byte SHA-256:
`da3124871d15fa64861c24e3a91bde66a9968029446d24de3ff2d54deb8836fe`

### Current PROD-01 v6 candidate identity

The current v6 candidate was recomputed from the exact committed runtime source
at `903795d7324e6b82f4b785987edb78a8da985a7f`. This documentation-only
correction is intentionally outside the packaged runtime source: it does not
change the candidate source commit or candidate payload bytes. The correction
commit must not be substituted as the v6 candidate source commit.

- Source commit: `903795d7324e6b82f4b785987edb78a8da985a7f`
- Runtime modules: `65`
- Manifest artifacts: `83`
- Detached inventory artifacts: `84`
- Manifest byte SHA-256: `0a166b8d2143c4fb633c4e06a0ea97e938008a1853356f2dabdb0a1ed1468d85`
- Bundle digest: `2f47a3dd820b5c0725993aa03e5ba4333e76458ecdaf847aa0dfa03bc14b099f`
- Product scope digest: `ac106b7d150bf275c6dce4865c6a7ef7b0e80915817e1e72694ab98ab2fe8bc0`
- Controller unit digest: `0be340e6760387f66e1277b3860680467178094b443a62665472db38c3f87386`
- Validation: `COMPLETE_BUT_UNAPPROVED`
- Approval state: `approved=false`, `activation=false`,
  `integration_services_approved=false`

Envelope bindings use SHA-256 of the exact canonical JSON bytes including the
final newline, as do detached artifact inventories. Legacy runtime canonical
object digests omit that newline; retain their distinct names/semantics.

`installation_plan` verifies authenticated consent, exact approved payload bytes,
the committed composition checkpoint and the existing preflight contract before
returning the bounded legacy plan. It executes no commands. New provisioning
packages must use this outer approval gate, not the legacy plan alone.

## Linked receipt without rewriting installed runtime

The version-2 full receipt binds source checkpoint, candidate manifest/bundle,
approved manifest/inventory, generation and the separate decision digest. It
contains `runtime_receipt`, the unchanged version-1 runtime-compatible projection
with actual file hashes, owner/group/modes, device/inode, created accounts and
objects, timestamp and boot identity. No filesystem observations are fabricated.

The future installer must preserve the **full linked receipt** with its installation
evidence and write the runtime projection to the already reviewed runtime receipt
path. The full evidence retention location must be specified in the later
provisioning package; this does not silently add a 58th static installed artifact.
The projection alone does not satisfy the new installer/rollback linkage checks.
Rollback must validate the full linked receipt before applying the existing exact
object/hash/identity cleanup contract. Neither receipt grants activation authority.

## Activation is a separate future decision

Installation approval cannot enable service startup or agents. The installation
manifest remains activation=false. `require_activation` in this tooling always
denies an installation-only decision, even with all host tests present. A later,
separately reviewed activation decision must bind verified installation evidence
and all mandatory host tests, followed by fresh operational enrollment and
reconciliation. It must preserve the original installation decision and receipt.
No activation-approval issuer is included here.

## Validation and review boundary

Deterministic tests reject changed identities, UID/GID, capabilities, paths, modes,
service policy, storage/resources, rollback, host tests, enrollment, source/digest
bindings, a second changed artifact, original candidate bytes as the installed
manifest, missing consent, JSON authority claims and root-as-founder. Tests also
verify linked receipt identities and refusal to activate with installation consent.
All approval identities/timestamps in tests are synthetic fixtures only.

No committed candidate bytes, installed runtime modules, application files or host
state are changed by this correction. Host provisioning remains separately gated.
