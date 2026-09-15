# Operational enrollment — M3 Block 3.75

This is repository code and synthetic validation. No service, identity, socket,
installation manifest or execution is provisioned or activated by this block.

## Installation identity and per-start identity

`operational_enrollment.InstallationIdentity` is a closed immutable service
policy: component, UID/GID, provisioning generation, service/cgroup name, endpoint,
capability policy and verified bundle/component-configuration digests. It rejects
PID, process-start, boot and runtime-generation fields. Component configuration
hashes are attached from the verified manifest, avoiding a circular self-hash.

The new v3 runtime attestation uses v2 component configurations. Production
`KernelIO` startup rejects the previous v2 attestation with precomputed process
identities. Its parser remains available to the earlier explicitly injected
offline fixtures; it is not an installed activation path. The legacy v1
installation validator remains unchanged. Block 4 still owns the complete
installation inventory, approval and host-test activation gate.

Resolved controller component configuration has `version`, `service`, explicit
`founder_uid`, `founder=null`, `proposal=null`, and `executions=[]`. Supervisor
configuration has `version`, `service`, `roots=[]`, and `plans=[]`. Null client
contexts and empty execution catalogs mean **intake disabled**, not unresolved
process identities. No guessed boot/PID/anchor belongs in either configuration.
`installation_spec()` supplies the exact static service policies. These dormant
configurations can be bundled without inventing operational authority.

Founder/model sessions and task launch catalogs are separate operational
permissions. Service enrollment does not enroll them, generate grants, initialize
SQLite or activate workers. Their later operational registration must preserve
existing founder authentication, original grant binding and pinned-root checks;
this block does not replace them with UID-only admission. Installed startup can
establish the service channel and reconcile with no human/model intake enabled.

## Per-start handshake

On the same AF_UNIX channel subsequently used for supervisor RPC:

1. Controller sends `ENROLL_BEGIN` with the two installation digests, its fresh
   nonce and runtime generation.
2. Supervisor returns `ENROLL_CHALLENGE`, binding that message to its own fresh
   nonce and per-start generation.
3. Controller returns `ENROLL_PROOF` containing the session digest.
4. Supervisor verifies that digest and returns `ENROLL_ACCEPTED`.

The session digest covers both sides' transcript and independently observed
UID/GID/PID/start/boot/service identities. The transport obtains SO_PEERCRED,
reads process identity and checks the expected systemd cgroup; the peer's JSON
never supplies those observations. The runtime checks both its own and peer
identity again throughout enrollment and before admission/release. Claiming a
known installation digest is not authentication by itself.

Nonces are freshness tokens, not secret bearer grants. JSON is bounded to 4096
bytes, strict and duplicate-key rejecting. A single BOOTTIME deadline bounds the
handshake to one second; no frame renews it. Wrong phase, replay, wrong transcript,
EOF, malformed/partial input, timeout or changed identity closes the channel.
There is no TCP, alternate authentication or retry of a release.

The process identities are learned only after processes exist. The supervisor
adopts its verified systemd listener. The controller validates its existing
private registry and zero capabilities before enrollment. No supervisor SQLite
writer is introduced.

## Admission and readiness

```
STARTING -> ENROLLMENT_CLOSED -> RECONCILING -> READY_CLOSED
                                                   |
                                            ADMISSION_OPEN
Any state ------------------------------------> STOPPING
```

STOPPING cannot reopen. READY_CLOSED follows verified cleanup/reconciliation;
it is not launch authority. Controller registration and preparation require open
admission; release checks the gate again under its close/release lock. Supervisor
PREPARE checks its own gate, and the final backend release also requires that
gate to remain open. Existing grant/lease/fence/profile/expiry checks still run.

Supervisor reconciliation returns bounded cleanup evidence. Only after durable
controller reconciliation succeeds does the controller send `OPEN_ADMISSION`,
bound to this session. Supervisor returns `ADMISSION_EVIDENCE`; controller opens
its local gate only after checking that response. No lost acknowledgement is
retransmitted. Supervisor startup/local reconciliation alone cannot open admission.

Supervisor `READY=1` and heartbeat liveness mean it can service the bounded
protocol with deadline servicing active. They do not advertise execution admission.
`establish_admission()` reports the separate gate state. Controller readiness
follows its enrollment, registry reconciliation, protocol setup and admission
step. No model or founder session becomes authorized by either notification.

## Restart, disconnect and persistence

Each service start generates fresh randomness. The installed loop fails closed on
channel loss and stops; a controlled service restart performs fresh enrollment
and reconciliation. It does not hot-reconnect an old session. A surviving peer
must also stop its lost session before participating in a new one. No reconnect
alone restores admission; no uncertain release is repeated.

BOOT changes and PID/start changes invalidate old enrollment even if the numeric
UID or PID is reused. A stopped session can never return to READY_CLOSED or OPEN.
The existing runtime launch rows retain supervisor generation, boot and process
metadata for cleanup/reconciliation. Session nonces and reusable OS descriptors
are not persisted. Old launches are interrupted/cleaned before new admission;
SQLite and OS startup are not treated as one atomic operation.

Channel closure closes admission immediately in the owning transport. Existing
controller-loss/deadline servicing terminates prepared/running work and retains
reservations until cleanup evidence is established. Release and close have a
local lock-defined ordering; whole-process termination still has scheduling
latency. Exact OS service-cgroup observations, socket activation, watchdog,
privilege bounds, restart ordering and real descendant cleanup remain
HOST_TEST_REQUIRED.

## Tests

`test_operational_enrollment.py` covers static identity separation, immutable UID
and capability policy, challenged first start, malformed/replayed/expired
handshakes, forged process/role claims, process/boot changes, controller/supervisor
restart semantics, disconnect, admission-before-grant/release ordering, and both
installed factories using temporary Unix channels/disposable SQLite with synthetic
kernel observations and process effects. No live model or host service is used.

## Block 4 installed configuration

The default installed adapter now requires the closed v4 review-bundle manifest
and verified installation receipt. Legacy v2/v3 configuration remains available
only to explicitly injected offline fixtures. See [installation-bundle.md](installation-bundle.md)
for separate installation, integration-service and activation permissions.
Operational identity remains per-start; no PID/start/boot/generation is prepopulated.
