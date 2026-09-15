# Resource and process supervision — composition Block 3

This is a repository contract with deterministic synthetic enforcement. **All
privileged OS effects remain HOST_TEST_REQUIRED.** No account, service, socket,
cgroup or tmpfs is installed by these modules or their tests.

`IntegrationPolicy` is the closed immutable version-1 integration policy. Its
canonical digest includes every field and participates in the installed payload
selection digest. Changes require a newly approved policy version; neither model
proposals nor controller/supervisor messages accept resource overrides.
The same resource digest participates in the controller's original authorization
snapshot, so final authority continuity includes it.

| Control | Integration bound | Future enforcement |
|---|---:|---|
| Concurrent launch | 1 | Durable admission plus backend/timer admission |
| Memory / swap | 256 MiB / 0 | cgroup v2 memory.max / memory.swap.max |
| CPU bandwidth | 100000/100000 microseconds | cgroup v2 cpu.max |
| Aggregate CPU budget | 30 seconds | Independent cgroup CPU accounting monitor |
| Per-process CPU | 30 seconds | RLIMIT_CPU soft/hard bound; not an aggregate substitute |
| Processes | 32 | cgroup v2 pids.max |
| Open descriptors | 256 | RLIMIT_NOFILE |
| Individual file | 16 MiB | RLIMIT_FSIZE |
| Core dumps | 0 | RLIMIT_CORE |
| stdout / stderr retained | 65536 bytes each | Bounded nonblocking collectors |
| Duration | at most 30 seconds | Independent BOOTTIME deadline |
| HOME / TMP | 16 MiB each | Existing bwrap sized private tmpfs plan |
| Workspace | 128 MiB, 16384 inodes | Host-provisioned bounded ephemeral tmpfs |

`authority_deadline` composes grant, every required lease, operation and profile
ceilings. It preserves subsecond lifetime, denies nonpositive/nonfinite lifetime,
and can shorten an original deadline but cannot extend it. Existing exact
grant/lease revision snapshots still reject replacement authority. Controller
preparation now uses this composition. `DeadlineScheduler` records one-use timer
registrations and latches observed expiry even if wall time rolls back. Failed
termination delivery is observable and retryable; it is never cleanup evidence.

The installed adapter must drive timers on a separate timerfd/BOOTTIME servicing
lane, independent of proposal handling, output draining, heartbeat and watchdog.
Termination callbacks enqueue bounded whole-cgroup kill requests; they must not
wait for SQLite, output or process exit. The synthetic scheduler can be advanced
without executing any pending request. This is not proof of an installed timer
driver. CPU accounting and termination have finite service latency; no zero-latency
termination guarantee is made. Suspend/resume and CLOCK_BOOTTIME must be tested.

`build_plan` accepts trusted enrolled records and supervisor-local pinned handles,
not IPC parameters. Candidate workers are ARCH 3001, FE 3002, BE 3003 and QA 3004,
each with matching private GID. The fixed sequence clears groups, sets GID/UID,
drops all worker capabilities, enables no_new_privs, clears environment/FDs and
enters distribution bwrap. The payload is sealed separately; bwrap starts the
installed custom release gate. No block-fd shortcut is used. Gate configuration
and channel descriptors are supervisor-local and must survive to the gate only;
pin/config/release descriptor closure before payload is an installed-host test.

Existing Block-2 handle validation supplies exact retained FD mounts, sanitized
Git boundaries and verified storage identity. The supervisor does not acquire
CAP_SYS_ADMIN or dynamically provision workspace tmpfs. Its installed adapter
must verify actual tmpfs type, byte/inode bounds and ownership before admission.
Workspace storage is ephemeral, not durable task storage. Read-only root bundles
and the Python gate installation/import path also require installed validation.

The deterministic `ResourceBackend` models timer stops, aggregate CPU consumption,
process identity observations, output and cleanup. It does **not** spawn workers,
apply RLIMITs, switch identities, invoke bwrap or write cgroup controls. A future
Linux backend must provide the same contract and kernel evidence before it can
replace this synthetic backend. Unique cgroup identity includes supervisor
generation and launch UUID. Descendants remain launch-owned after fork, detach,
setsid or parent exit; only verified whole-cgroup emptiness permits TERMINAL.
The earlier `LinuxProcessBackend` is not selected by this composition: it lacks
the Block-2 `prepare_pinned` interface. A filesystem-bound plan fails closed with
that backend; there is no fallback to its older path-based preparation flow.

Normal exits now use strict authenticated STATUS_LAUNCH/STATUS_EVIDENCE messages.
Process/boot evidence must match PREPARED. Output evidence contains only bounded
retained counts and truncation flags, not raw output or credentials. Both pipes
must be nonblocking and fairly drained in chunks of at most 16 KiB, discarding
overflow. Raw buffers are discarded after cleanup; bounded summary metadata
remains available. Future sanitized tool-result delivery must consume retained
prefixes before that disposal and must not log raw output as audit history.

Revocation, lease revocation, cancellation and disconnection reuse the durable
STOPPING path. Exit codes survive supervisor-side cleanup before the controller
polls. Stale exit evidence causes interruption, not successful completion.
Reservations stay held until cleanup evidence is known. Controller/supervisor
crash, changed generation, lost acknowledgement and uncertain descendants retain
the existing no-replay reconciliation rules. Heartbeat/watchdog are additional
failure detectors, never substitutes for deadlines; notifier failure propagates
and controlled shutdown emits STOPPING.

Block 4 remains installation/bundle/manifest and adapter integration work. It must
not install these synthetic backends as production enforcement. Host tests must
prove UID/group/capability drop, gate EOF and release, FD survival/closure, actual
bwrap/AppArmor transition, pidfd/start/boot verification, cgroup placement and
kill/emptiness, CPU/memory/PID limits, concurrent pipe flooding with revocation,
timer independence under blocked handlers, storage bounds, and crash/reboot
reconciliation. The full M3 composition is not production-ready at this checkpoint.
