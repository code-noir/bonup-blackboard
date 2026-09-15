# Pinned filesystem evidence — composition Block 2

The controller authorizes from installed logical policy and durable grants. It
does not open worker-owned roots. `LogicalRootView` supplies metadata-only scope
checks; its policy digest joins the original authorization snapshot. This initial
authorization is conditional on matching supervisor PREPARED evidence.
Metadata-only export checks conservatively reject overlap with protected,
task-forbidden and (for writable exports) task-readonly descendants, including
paths that do not exist yet. They do not substitute a current file inventory for
scope containment.

The supervisor owns an immutable `RootMapping` catalog. Each UUID binds a canonical
root, device/inode/owner, provisioning generation, exact exports, confinement
profile, optional repository identity and bounded storage policy. Requests contain
only logical IDs and digests. No host root or descriptor number crosses IPC.

`FilesystemInspector` resolves installed roots using descriptor-relative openat2.
Symlinks and magic links are forbidden. Only the final installed root component
may cross a mount; its mount ID must match approval. Descendants cannot cross
mounts. The exact root descriptor is adopted, and existing `PinnedMounts` retains
the exact inspected export descriptors. Export rename cannot substitute the
mounted object; root substitution fails validation. Hardlinked regular exports,
special files and protected Git metadata are rejected. Optional task-repository
inspection rejects external metadata, alternates and unsafe Git configuration.

Protocol version 2 binds the root policy to PREPARE, includes bounded path-free
filesystem facts in PREPARED, and binds their digest to RELEASE. The controller
compares every fact with its original installed expectation and durable
workspace/repository/worker/profile binding. Rehashing altered evidence does not
authorize it. The expected policy must remain unchanged through release. A
filesystem-bound installed plan rejects version 1; the old protocol remains only
for existing synthetic plans without a filesystem mapping.

The supervisor calls `prepare_pinned(launch, record, handle)`. This backend must
construct bwrap arguments from `handle.argv` and the same retained `pass_fds`,
complete confinement and descriptor closure, and return only once the trusted
gate is waiting. It must never reopen host paths. Missing backend support fails
closed, with no ordinary-prepare fallback. The inspector exclusively owns parent
descriptors; the backend borrows them and must not close or replace them in the
parent. Pins are closed after setup and on setup failure, cancellation,
disconnect or reconciliation failure. Closed/cross-launch handles are rejected.
The gate/payload must receive neither mount pins nor administrative descriptors.

The storage contract describes an ephemeral tmpfs workspace bounded to 128 MiB
and 16384 inodes, with exact mount identity and worker ownership. The default
read-only probe verifies filesystem type and upper bounds. Tests explicitly
inject synthetic storage observations; they do not provision or mount tmpfs.

Block 3 still owns the actual privileged backend: UID/GID switching, real bwrap
setup/gate acknowledgment, cgroups, complete resource enforcement and installed
tmpfs verification. This block runs synthetic backends only. It does not make
services deployable, provision accounts, enable ordinary Git commits, or complete
the full composition. Existing founder Codex authentication remains untouched.

Focused validation uses `test_filesystem_evidence.py`: actual temporary file
descriptors/openat2 checks, deterministic substitution and evidence attacks,
synthetic preparation/release, and a harmless fork verifying worker FD closure.
Nested mount rejection uses injected EXDEV; real mount transitions and actual
bwrap FD consumption remain installed-host integration tests.
