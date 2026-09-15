# Supervisor provisioning review — NOT installation authorization

No artifact in this directory creates accounts, directories, sockets or services.
`review_manifest(repository)` produces hashes and unresolved allocation values in
memory. It reads only agent-control Python source and policy/schema JSON. No UID/GID
is allocated here. Worker homes sit under their private workspace roots, not below
the controller's inaccessible 0700 directory.

The service template is intentionally non-installable: entrypoint, capabilities and
writable roots must be reviewed and rendered. No socket/service is enabled by a
Python import. The trusted host event-loop/controller composition is an installed
integration gate, not a command exposing root Python evaluation.

Before installation, the founder reviews:

1. Exact unused UID/GID pairs and generation; existing matching names are NOT silently
   adopted. Controller and workers get private primary groups, locked passwords,
   nologin shells, no SSH keys and empty supplementary groups. Never inherit sudo,
   docker, ollama, founder or production groups.
2. Every installed file hash, root ownership and mode, including the complete Python
   package, schemas/policy data used by imports, the gate entry and service entrypoint.
   Schema lookup currently uses repository-relative docs: the installed layout must
   include the reviewed docs/agent-control policy/schema files at the corresponding
   root. Installation tests must verify imports against that immutable layout.
3. Immutable installed package under /usr/lib/bonup-agent-control and root-owned
   ancestor directories. Copy and hash from an unprivileged staged bundle first;
   only then invoke a reviewed installed helper. Never execute checkout code as root.
4. Controller state 0700, worker homes 0700, root-owned workspace ancestors, per-agent
   workspace ownership/modes, and a finite workspace storage allocation (filesystem
   quota or bounded dedicated filesystem). RLIMIT_FSIZE is not a total storage quota.
5. Private controller/supervisor IPC ownership and enrolled process identity. Model
   clients and workers get neither administrative endpoint. No founder credentials.
6. Capability bound: SETUID/SETGID/KILL. If the root supervisor itself opens worker-
   owned 0700 sources, DAC_READ_SEARCH is additionally needed for that traversal;
   it is not enabled by this template and must be explicitly reviewed. SYS_ADMIN
   is not a workaround for namespace failures. Worker permitted/effective/inheritable/
   ambient capabilities must be zero; no_new_privs must be set.
7. cgroup v2 delegation with a manager subgroup, aggregate/per-launch budgets,
   watchdog event loop, deny-on-restart reconciliation, bounded output, deadline
   servicing independent of controller requests, and installation crash tests.
8. No changes to AppArmor, sysctl, distribution bwrap, founder Codex or application
   services. No live model transport or activation is authorized by provisioning.

Rollback procedure (future founder operation only):

- Stop admission. Stop the supervisor and verify its dedicated cgroup subtree is
  empty; never signal application processes or rely on recycled numeric PIDs.
- Disable/remove only the manifest-installed unit after verifying path and hash.
  Reload systemd only as part of that separately authorized installation rollback.
- Remove only manifest-created socket/runtime entries after identity/type checks.
- Preserve the control database, migration backup, history and nonempty workspaces
  for review. No blind recursive deletion. Roll back v2 only by restoring the
  consistent backup while all writers/executions are stopped; do not drop live tables.
- Remove only newly created account/group names whose exact numeric identities
  still match the manifest, after verifying no processes and inventorying ownership.
  Quarantine nonempty homes/workspaces; do not recursively remove unknown data.
- Restore any replaced installed artifacts from the recorded backup with verified
  owner/mode/hash. Do not roll back packages, AppArmor or sysctls: this plan changes none.
- Verify founder/application accounts, customer data, databases, services and Git
  history were never included in the rollback inventory.
