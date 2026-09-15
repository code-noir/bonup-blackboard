# bonUP M3 cross-block boundary corrections

These repository changes remain unprovisioned. The review bundle stays
`COMPLETE_BUT_UNAPPROVED`, with installation and activation disabled.

## Activated sockets

The installed controller/supervisor channel uses `SO_PASSCRED` and checks
`SCM_CREDENTIALS` on every received stream segment. A bounded credential-bearing
prelude observes the actual sender before operational enrollment constructs its
transcript. Listener-creator `SO_PEERCRED` is not service identity. The observed
PID must still match process-start/boot identity and the expected systemd service;
installation digests, fresh generations, challenges, reconciliation and admission
remain mandatory. Unknown ancillary messages are rejected; transferred FDs are
closed. Socket units explicitly enable credentials. Actual systemd activation
remains a host integration test.

## Installation identity inside the user namespace

The supervisor reopens the root-controlled installed subtree safely, verifies its
members against the approved artifact hashes, and retains that directory FD. It
binds that same FD read-only over the installed subtree after the distribution
`/usr` mount is established. Host owner/group, mode, type, device/inode, content
digest, bundle identity and provisioning generation enter sealed gate configuration.

The gate checks the sealed expected ID maps and translated ownership, exact
object identities and digests before importing installed modules. Unmapped UID
ownership is not independently trusted. Namespace UID 0 is acceptable only when
the sealed mapping actually maps host root there. Neither a writable installation
mount nor an artifact substitution is accepted. Actual bwrap UID/GID mapping and
the retained installation mount require the `namespace_installation` host test.

## Release versus execution start

Release delivery consumes the one-use release but does not authorize RUNNING
evidence. A separate inherited status channel belongs only to the trusted gate.
The gate traces its own fixed-payload child with `PTRACE_O_TRACEEXEC` and
`PTRACE_O_EXITKILL`. Only the kernel `PTRACE_EVENT_EXEC` stop confirms successful
exec. The payload has only its standard descriptors and cannot write this status
channel. The gate sends a launch/generation/authorization/nonce-bound confirmation,
closes the channel and detaches; it then waits for the child to preserve exit status.

Plain close-on-exec EOF was rejected because gate death would also produce EOF.
Here, EOF, failed exec, rejected release and lost acknowledgement produce no
confirmation and trigger cleanup without retry. Both the supervisor endpoint and
controller sequencer require typed, exact execution-start evidence. Deadline
servicing does not wait on the status-channel read lock. RUNNING denotes a
confirmed exec transition, not a guarantee the payload remains alive afterward.

This adds no host capabilities or AppArmor changes. Tracing the gate's own child
inside the installed confinement must pass the `exec_start_event` host test. If
the existing confinement denies it, launch fails closed; no weaker handshake or
unrestricted launch is selected automatically.

## Controller audit ownership

Production proposal intake emits bounded receipt and denial records even before
launch registration. Authorization, setup, setup failure, confirmed execution
start and terminal cleanup are correlated by request/execution/launch IDs. Only
reason codes and identifiers are logged, never proposal contents or arguments.

The controller uses the existing registry audit chain, operations and publication
outbox. Routing events identify `actor.component=CONTROLLER`; they do not invent
an architect/founder AuthenticatedContext. Failure to persist an event propagates,
prevents subsequent lifecycle work and stops a launch when necessary. Cleanup
transport failure cannot suppress the corresponding controller denial event.
The supervisor never receives a controller database reference.
