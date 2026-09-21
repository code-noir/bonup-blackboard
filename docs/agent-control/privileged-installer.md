# bonUP privileged Agent Control installer

`tools/install_agent_control.py` is the repository installer entrypoint. It
consumes an approved detached installation manifest and its exact payload
inventory, validates the existing `TRUSTED_DJANGO_PROJECTION_BOUNDARY_V1`
configuration contract, and produces a bounded host plan.

The default invocation is a read-only dry run. `--apply` is an explicit root
operation and remains deliberately separate from service activation: it creates
or verifies the reviewed users, groups, directories, Registry, root-owned event
configuration, immutable Agent Control units, and the Django management-command
unit, then performs only `systemctl daemon-reload`. It never enables or starts
either service.

The Django unit runs the existing
`TrustedDjangoProjectionReceiver` through
`run_trusted_projection_receiver`. The receiver binds the configured AF_UNIX
socket as the explicit Django identity; Agent Control connects as UID/GID
3000/3000 and the transport continues to validate socket ownership, mode,
`SO_PEERCRED`, and process identity.

Re-running against exact state is a no-op. Existing conflicting accounts,
groups, paths, bytes, modes, owners, units, or Registry schema fail closed.
Registry initialization and v1/v2/v3 migration use the Registry APIs and end
at v3; authoritative Registry and Git history are never rollback targets.

No Founder state, credentials, review, ARCH state, execution authority,
publication authority, or activation is created by this installer.

## Installation schema v5 projection binding

Schema v4 remains valid for historical bundles. New event-delivery bundles use
schema v5 and include a closed `projection_scope`. Its digest binds the exact
root-owned event-delivery configuration and digest, the production Django
identity (`www-data`, UID/GID `33:33`, `/srv/bonup-web`,
`backend.core.settings`), the AF_UNIX socket and parent ownership/modes, and
`bonup-django-projection.service` including its unit path, service identity,
receiver command and generated unit digest.

The v5 installer still accepts explicit `RuntimeInstallOptions` for execution,
but every trust-bearing value is compared with `projection_scope` before any
installation files are generated. A conflicting option is rejected; it cannot
expand or replace the approved installation scope. Polling, batch, timeout and
message bounds are also included in the approved event configuration digest.
