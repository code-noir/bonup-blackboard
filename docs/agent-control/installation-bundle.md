# bonUP M3 installation review bundle

Block 4 generates and verifies a repository review artifact. It does not install,
provision, start services, enroll tasks or activate workers. Host integration remains
required. The existing founder Codex workflow is unchanged.

## Committed-source builder

The provisioning source is one explicit full Git commit, not the working tree.
`build(repository, source_commit=...)` validates the lowercase 40-character commit,
resolves its tree, and reads each reviewed source blob with bounded Git-object
operations. Dirty, deleted and untracked checkout files are not build inputs.
Branches, tags, `HEAD`, unsafe paths, symlinks, non-regular blobs and unresolved
local imports fail closed.

The current reviewed roots are the installed controller/supervisor/bootstrap,
Founder/Genesis transport, and product-review/artifact adapters. Their local
imports form the deterministic closure; standard-library imports are not copied,
and undeclared external imports are rejected. The resulting manifest records the
closure and hashes every generated or committed payload byte.

The controlled sequence is:

COMMITTED SOURCE
→ REVIEWED DEPENDENCY CLOSURE
→ GENERATED CANDIDATE
→ INDEPENDENT REVIEW
→ FOUNDER APPROVAL
→ INSTALLATION

The current-source builder change is a builder checkpoint only. It does not create
the next provisioning candidate, perform Genesis, or authorize installation.

Generation-1 installation approval is now governed by
[installation-approval.md](installation-approval.md). The historical candidate and
its inventory remain unchanged. Future installers must use the separate approved
installation inventory and linked receipt contract in `installation_approval.py`;
the legacy plan/receipt primitives described below are compatibility components,
not the complete approval gate.

## Source and dependency boundary

`tools/agent_control/installation_bundle.py` exposes `build`, `write_review`,
`validate_manifest`, `verify_payloads` and the installation/receipt/rollback contracts.
The historical candidate at `review/m3-generation-1/` is preserved unchanged.
Future generation must use a new review directory and an explicit committed
source object, run as an unprivileged user:

```python
from tools.agent_control.installation_bundle import write_review
write_review('/home/bonup/bonup-blackboard',
             '/home/bonup/bonup-blackboard/docs/agent-control/review/m3-generation-1-current-head',
             source_commit='FULL_40_CHARACTER_COMMIT')
```

Generation rejects existing output destinations. The recorded commit is the
exact caller-supplied committed source; no permanent historical payload directory
is read. Source mode is `COMMITTED_BASE_PLUS_REVIEWED_PAYLOAD_HASHES`. Any later
source change requires a fresh candidate and review.

The fixed production import inventory includes installed adapters and operational
enrollment. Imports must resolve to inventoried modules or Python's standard
library. No plugin discovery or test factory is selected by installed entrypoints.
Existing modules can contain synthetic test abstractions; production factories
continue to select Linux enforcement contracts exclusively.

Installed controller/supervisor wrappers use `/usr/bin/python3 -I`, fixed absolute
installed package paths, no arguments, no user-site/PYTHONPATH/CWD imports, and
verify root ownership, ancestor permissions and all installed code hashes before
importing agent-control. Source artifacts are read through retained descriptors;
symlink, hardlink and special-file sources are rejected. Installation must also
pin and reverify copied bytes: the review generator is not a privileged installer.

## Closed inventory and self-hashing

`payload/` mirrors future absolute destinations without writing to those paths.
Every installed artifact has an exact ID, source, destination, digest, type,
owner, group, mode, generation and required flag in `bundle-index.json`.

Manifest v4 hashes every payload artifact and every security-policy field.
Manifest v5 retains that closed inventory and additionally hashes the complete
Registry installation target and trusted projection scope, including the
Registry/history paths, target v3 migration intent, event-delivery file,
projection socket ownership/modes and Django service unit identity. The v5
Registry target accepts only absent/v1/v2 setup through reviewed migration and
v3 verification/no-op; future or invalid versions fail closed.
Manifest v6 retains the v4/v5 semantics and additionally binds the controller-owned
PROD-01 product scope. Its exact proposal artifact store is
`/var/lib/bonup-prod/proposals`, owned by `bonup-agentctl:bonup-agentctl` with mode
`0700`. The parent `/var/lib/bonup-prod` is `root:root` with mode `0711`, so the
controller can traverse to the proposal store but cannot create sibling entries.
The v6 controller unit grants `ReadWritePaths` for the existing controller state
paths and `/var/lib/bonup-prod/proposals` only; it does not grant the parent path.
A manifest cannot include its own final SHA-256 without a circular definition.
Its exact metadata therefore appears in `manifest_artifact`; the detached review
index includes its final SHA-256 together with the complete installed inventory.
The detached index is container metadata, not an installed runtime dependency.
The installer must verify both the manifest's policy/payload digest and the
index's final manifest-file digest. Permission changes require rehashing and
fresh review; no automatic approval function exists.

## Candidate policy

Identity map v2 has generation 1 candidates: controller `bonup-agentctl` 3000:3000,
`bonup-arch01` 3001:3001, `bonup-fe01` 3002:3002, `bonup-be01` 3003:3003 and
`bonup-qa01` 3004:3004. Each has its own primary group, locked password intent,
nologin, 0700 home, no SSH keys and no supplementary groups. Founder 1000:1000
is an explicit preflight assumption, never a worker membership.

Exact directory/socket inventories in the manifest are authoritative for review:
controller state/history are 0700 controller-owned; installed code and configuration
are root-controlled; worker roots are isolated 0700; runtime directories give only
founder/controller traversal needed for their respective endpoints. The founder
socket requires separate authenticated human enrollment. Proposal intake is
explicitly disabled. Workers receive no administrative sockets.

Service candidates and three socket units are generated, with explicit descriptor
names and ownership. Runtime directories use an exact tmpfiles contract. Controller
capabilities are empty. Supervisor capabilities are exactly SETUID, SETGID, KILL
and DAC_READ_SEARCH; ambient capabilities are empty. SYS_ADMIN and DAC_OVERRIDE
are forbidden. Services use immutable ExecStart, fixed environment, cwd `/`,
NoNewPrivileges, ProtectSystem, ProtectHome, PrivateTmp and control-group killing.
Supervisor cgroup delegation is cpu/memory/pids. PrivateDevices compatibility is
HOST_TEST_REQUIRED. No namespace restriction or syscall filter is added.

The immutable integration profile remains concurrency 1; 256 MiB memory, zero
swap, one CPU bandwidth, 30 s CPU/runtime ceiling, 32 PIDs, 256 FDs, 64 KiB retained
output per stream, 16 MiB file size and no core dumps. HOME/TMP are each 16 MiB;
workspace tmpfs is 128 MiB/16384 inodes, ephemeral and not durable task storage.
Host provisioning must establish and test the bounded storage. Neither worker
nor supervisor receives authority to resize/remount it dynamically.

## Installation versus operational authority

The v6 PROD-01 candidate validates as `COMPLETE_BUT_UNAPPROVED`:
`approved=false`, `activation=false`, `integration_services_approved=false`.
These flags are resolved permission states. The v6 product scope grants no
execution authority, ARCH routing, assignment, or activation authority. No future
PID, process-start identity, boot ID or runtime generation is in installation
policy. Actual kernel identity and fresh generations are established by
admission-closed enrollment and reconciliation.

Controller and supervisor configuration catalogs are explicitly empty; founder and
model intake are disabled, not placeholders for guessed future credentials or tasks.
The installed default requires manifest v4. Earlier v2/v3 forms remain only for
explicit injected offline fixtures, not the default installed KernelIO path.

Installation approval does not permit service startup. A separate root-controlled
`integration_services_approved` decision can later permit protocol-only host testing
with empty catalogs, preventing a circular requirement to pass service tests before
starting test services. It cannot admit a worker. Normal activation requires a
verified installation receipt, all required host-test evidence and explicit founder
approval. Admission still requires fresh operational enrollment, reconciliation and
execution authority. Evidence alone and founder approval alone cannot bypass tests.

## Installer, receipt and rollback contracts

`installation_plan` is a pure bounded plan, not a mutation executor. It requires
reviewed hashes, source binding, fresh trusted preflight evidence and authenticated
founder authority. It returns only exact account/directory/file/unit operations and
no shell strings, wildcard operations or automatic service start.

A future separately reviewed privileged installer must first copy/hash/verify its
immutable code into root-controlled staging; it must never run repository Python as
root. It must reverify source/manifest/content, reject account/target conflicts,
create only exact identities/directories, copy and verify all owners/modes/hashes,
install runtime/unit policy, reload systemd and leave admission/activation closed.
Starting integration-test services needs separate authorization.

Receipt generation requires explicit fresh observations of every installed object
and created account/group. It records device/inode, hashes, owner/group/mode,
created/preexisting status, boot ID and timestamp. These are observations, not
installation authority. Preexisting objects are forbidden by this first-install
contract. Receipts retain the original installation manifest digest. A normalized
installation binding permits separately approved permission flips without treating
new code or changed policy as the old installation. A changed manifest file will
fail exact rollback hash comparison and must be preserved for explicit review.

Rollback first closes admission, prohibits release, terminates identified launches,
verifies empty descendants, and stops/disables only installed units. Preserve
registry/history and quarantine nonempty workspaces. Account removal requires exact
UID/GID and no-process verification. `rollback_file` only decides whether one exact
receipt-created file with matching identity/hash can be unlinked after cleanup;
it never deletes anything. No recursive deletion, arbitrary commands or protected
paths are accepted. Remaining directory/account steps are bounded review contracts,
not claims of an implemented privileged removal executor.

## Preflight and host-test gate

`preflight_commands()` provides fixed future read-only argv arrays. They have not
been executed here. A trusted future collector must distinguish absent targets from
permission errors and other failures; errors are not successful absence checks.
Recheck source/hash binding, founder identity, UID/GID/name collisions, every target,
previous installation, bwrap 0.9.0, enforcing targeted AppArmor profiles, both userns
sysctls=1, cgroup v2/kill, Python >=3.12, systemd >=255, tmpfs, RAM and disk.

The manifest lists 16 mandatory host-test categories: UID/GID drop, empty groups,
capabilities, AppArmor/bwrap, pinned mounts, confined gate, cgroup limits, descendant
kill, bounded pipe draining, tmpfs limits, socket activation, real peer enrollment,
watchdog, controller crash, supervisor crash and reboot reconciliation. These remain
HOST_TEST_REQUIRED; synthetic tests do not prove host enforcement. Evidence is bound
to the exact installation and receipt and read only from root-controlled paths.

No host installation, migration, service operation or agent activation is performed
by bundle generation, its tests or this document.

The manifest also specifies the mutable controller registry prerequisite: explicit
initialization as UID 3000 using the installed `Registry.initialize`, then
`runtime_schema.migrate_v2` and integrity/history verification, before test-service
startup. Its fresh operation UUID is recorded by the future installer; it is not a
future process identity or a guessed authority. Existing state must not be
reinitialized. This step creates only disabled agents and no executions, with a
0600 controller-owned database. No initialization or migration is performed here;
normal service startup continues to reject missing operational state. The database
and audit contents are mutable operational data, not immutable bundle artifacts.
