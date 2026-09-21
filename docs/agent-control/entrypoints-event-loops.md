# M3 Block 1: entrypoints and authenticated event loops

This block adds repository entry functions and an injected-adapter control pump.
It does not complete the overall composition or authorize installation. The earlier
`composition-work-in-progress.md` remains the preserved snapshot of the previous
attempt; its entrypoint/event-loop items are addressed by this narrower block.

## Fixed entry functions

The future controller launcher calls `controller_entry.main(adapters=...)`; the
future supervisor launcher calls `supervisor_entry.main(adapters=...)`. These are
fixed Python entry functions, not installed executables or a deployable bundle.
Adapter objects come from trusted installation code, never configuration strings,
model messages or dynamic imports. [Controller](../../tools/agent_control/controller_entry.py#L138),
[supervisor](../../tools/agent_control/supervisor_entry.py#L82).

Controller startup requires the fixed controller config path, approved manifest
identity, UID/GID 3000 and zero capabilities. It opens existing state, verifies v2
schema/integrity/history, reconciles, establishes its listener and admission state,
and only then signals READY. The real registry opener checks the fixed controller
path and private controller ownership; test adapters substitute disposable
registries. Missing state is never initialized.
[Source](../../tools/agent_control/controller_entry.py#L51).

Supervisor startup validates its separate root configuration and composition
generation, reconciles its existing SupervisorEndpoint, establishes controller-only
IPC and admission state, and services deadlines before READY. Its config rejects
any registry path; its entrypoint has no registry opener or controller DB argument.
[Source](../../tools/agent_control/supervisor_entry.py#L44).

## Trusted adapter contract

`load_config` must use the bounded, descriptor-relative `installed_json` reader in
an installed adapter. `verify_manifest` must independently verify the approved
root-controlled installation identity and return its digest. Tests intentionally
replace both with synthetic values. Neither a claimed digest nor a JSON `approved`
field is permission to skip that independent adapter verification.
[Reader and schema](../../tools/agent_control/service_runtime.py#L25).

The transport's peer and process observations must come from SO_PEERCRED and
independent kernel process-start/boot inspection. The small handshake carries only
endpoint/generation/enrollment selectors; they confer no authority. Reusing an
enrollment is rejected, and reconnect requires a new trusted enrollment. The loop
rechecks process identity each iteration. Controller accepts only its enrolled root
supervisor; supervisor accepts only its enrolled UID/GID 3000 controller. No founder
authority is derived from this transport identity.
[Source](../../tools/agent_control/service_runtime.py#L111).

All transport and work-queue methods must be nonblocking. `submit` queues work;
`take_result` returns immediately while that work is pending. Do not attach the
blocking Linux preparation routine directly to this pump. A future installed work
executor must preserve the same contract. Tests use deterministic fake queues.

The event adapter distinguishes the end of one framed record from disconnect of
the enrolled connection. It reports bounded data/end/disconnect events; a future
Unix adapter must preserve these semantics. This does not change the separate
release gate's mandatory one-frame-plus-EOF semantics.

## Bounds and failure behavior

The pump allows one enrolled connection, one pending normal job, at most four input
events per iteration, 4096-byte messages, a one-second partial-frame timeout and a
4096-request generation replay budget. Maintenance runs before request polling:
deadlines, cancellation/revocation control, then outbound heartbeat. Inbound
heartbeat is handled even while normal work is pending. Missing peer activity for
two seconds, malformed frames, stale identity or replay cause shutdown.
[Source](../../tools/agent_control/service_runtime.py#L137).

READY follows validated startup and the first deadline/control service pass.
WATCHDOG is emitted only after readiness, at quarter-second service intervals.
Shutdown is idempotent: STOPPING, cancel queued work, notify the component of peer
loss, close transport, and (controller only) close its registry. Driver callbacks
bridge the existing ControllerRuntime and database-free SupervisorEndpoint;
normal evidence cannot create authority or change fixed launch parameters.

The installed controller also owns the bounded domain-event delivery lane. It is
started after the controller loop reaches READY and stopped before the controller
registry closes. Each cycle opens a separate controller-owned Registry connection,
loads only committed verified events, and delivers independently to the Product
Direction and Blackboard projection consumers through the trusted application
boundary. Missing or unprovisioned application transport leaves obligations
pending with `TRUSTED_RUNTIME_UNAVAILABLE`; it never creates an event or changes
review authority. See [installed-runtime-adapters.md](installed-runtime-adapters.md)
for the root-controlled scheduling contract and bounded diagnostics.

## Remaining work

Block 2 still needs supervisor-only pinned filesystem inspection and authenticated
evidence handoff. Privileged UID switching, real bwrap/cgroups, installed resource
enforcement, tmpfs setup, real Unix transport/work executors, final bundle/systemd
units and approved provisioning manifest are not installed or enabled by Block 1.
No live model client, worker execution or Milestone 4 scheduling is activated.
