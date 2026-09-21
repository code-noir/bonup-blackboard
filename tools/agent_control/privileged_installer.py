"""Fail-closed, repeatable installer for the Agent Control runtime.

The installer is an artifact, not an activation authority.  It consumes an
approved immutable bundle and performs only exact, root-owned installation
operations.  The default command is a read-only dry run; the mutation path is
explicitly gated by ``--apply`` and never enables or starts a service.

The implementation keeps host effects behind ``HostOperations`` so the
installation contract can be tested without touching /etc, /run, systemd, or
authoritative Registry data.
"""
from dataclasses import dataclass
import argparse
import grp
import json
import os
from pathlib import Path
import pwd
import shlex
import sqlite3
import stat
import subprocess
import sys
from uuid import uuid4

from . import installation_bundle as bundle
from .domain_event_delivery import EventDeliveryConfig
from .registry import Registry
from .runtime_schema import check_version, migrate_v2, migrate_v3
from .serialization import canonical_json, digest
from .storage import RegistryBlocked
from .types import AuthorityError, ValidationError


VERSION = 1
CONTROLLER_USER = "bonup-agentctl"
CONTROLLER_UID = 3000
CONTROLLER_GID = 3000
BONUP_GROUP = "bonup"
BONUP_GID = 1000
REGISTRY_PATH = bundle.REGISTRY_PATH
HISTORY_PATH = bundle.HISTORY_PATH
EVENT_CONFIG_PATH = bundle.EVENT_CONFIG_PATH
PROJECTION_SOCKET = bundle.PROJECTION_SOCKET
PROJECTION_PARENT = bundle.PROJECTION_PARENT
PROJECTION_UNIT = bundle.PROJECTION_UNIT
CONTROLLER_UNIT = "bonup-agent-controller.service"
SYSTEMD_UNIT_DIR = "/etc/systemd/system"
DJANGO_COMMAND = "run_trusted_projection_receiver"


class InstallerBlocked(ValidationError):
    """The host or the reviewed input is not safe to mutate."""


def _mode(value):
    if type(value) is int:
        return value
    if type(value) is str and len(value) == 4 and all(c in "01234567" for c in value):
        return int(value, 8)
    raise InstallerBlocked("Invalid installation mode.")


def _absolute(path, label):
    if isinstance(path, Path):
        path = str(path)
    if type(path) is not str or not path.startswith("/") or "\0" in path:
        raise InstallerBlocked("Invalid " + label + ".")
    p = Path(path)
    if str(p) != os.path.normpath(path) or ".." in p.parts:
        raise InstallerBlocked("Non-canonical " + label + ".")
    return path


def _safe_name(value, label):
    if type(value) is not str or not value or value.startswith("-") or "/" in value:
        raise InstallerBlocked("Invalid " + label + ".")
    return value


@dataclass(frozen=True)
class RuntimeInstallOptions:
    """Explicit installation inputs; no environment-specific fallback exists."""

    django_uid: int
    django_gid: int
    django_user: str
    django_group: str
    django_root: str
    django_settings_module: str
    poll_interval_ms: int
    batch_size: int
    timeout_ms: int
    max_message_bytes: int
    socket_mode: int = 0o660
    socket_path: str = PROJECTION_SOCKET

    def __post_init__(self):
        if (type(self.django_uid) is not int or self.django_uid <= 0 or
                type(self.django_gid) is not int or self.django_gid <= 0):
            raise InstallerBlocked("Django UID/GID must be positive.")
        _safe_name(self.django_user, "Django user")
        _safe_name(self.django_group, "Django group")
        _absolute(self.django_root, "Django root")
        if (type(self.django_settings_module) is not str or
                not self.django_settings_module.replace(".", "").isalnum()):
            raise InstallerBlocked("Invalid Django settings module.")
        _absolute(self.socket_path, "projection socket")
        if self.socket_path != PROJECTION_SOCKET:
            raise InstallerBlocked("Projection socket is outside the reviewed path.")
        config = {
            "enabled": True,
            "poll_interval_ms": self.poll_interval_ms,
            "batch_size": self.batch_size,
            "transport_identity": "TRUSTED_DJANGO_PROJECTION_BOUNDARY_V1",
            "socket_path": self.socket_path,
            "socket_mode": self.socket_mode,
            "agent_control": {"uid": CONTROLLER_UID, "gid": CONTROLLER_GID},
            "django": {"uid": self.django_uid, "gid": self.django_gid},
            "timeout_ms": self.timeout_ms,
            "max_message_bytes": self.max_message_bytes,
        }
        EventDeliveryConfig.parse(config)

    def event_config(self):
        value = {
            "enabled": True,
            "poll_interval_ms": self.poll_interval_ms,
            "batch_size": self.batch_size,
            "transport_identity": "TRUSTED_DJANGO_PROJECTION_BOUNDARY_V1",
            "socket_path": self.socket_path,
            "socket_mode": self.socket_mode,
            "agent_control": {"uid": CONTROLLER_UID, "gid": CONTROLLER_GID},
            "django": {"uid": self.django_uid, "gid": self.django_gid},
            "timeout_ms": self.timeout_ms,
            "max_message_bytes": self.max_message_bytes,
        }
        EventDeliveryConfig.parse(value)
        return value


@dataclass(frozen=True)
class HostObject:
    kind: str
    uid: int
    gid: int
    mode: int


@dataclass(frozen=True)
class Account:
    username: str
    uid: int
    gid: int
    home: str
    shell: str


@dataclass(frozen=True)
class Group:
    name: str
    gid: int


@dataclass(frozen=True)
class FileInstall:
    path: str
    content: bytes
    uid: int
    gid: int
    mode: int
    kind: str = "file"


@dataclass(frozen=True)
class DirectoryInstall:
    path: str
    uid: int
    gid: int
    mode: int


@dataclass(frozen=True)
class InstallPlan:
    version: int
    bundle_digest: str
    manifest_digest: str
    config_digest: str
    accounts: tuple
    groups: tuple
    django_account: Account
    django_group: Group
    directories: tuple
    files: tuple
    units: tuple
    registry_path: str
    history_path: str
    projection_socket: str
    activation: str

    def report(self, observation):
        """Return bounded dry-run state; no payloads or exception text are exposed."""
        return {
            "version": self.version,
            "bundle_digest": self.bundle_digest,
            "manifest_digest": self.manifest_digest,
            "config_digest": self.config_digest,
            "accounts": observation.get("accounts", {}),
            "groups": observation.get("groups", {}),
            "paths": observation.get("paths", {}),
            "units": observation.get("units", {}),
            "registry": observation.get("registry", "UNKNOWN"),
            "socket": {"path": self.projection_socket, "expected": True},
            "activation": self.activation,
            "blocking_conflicts": tuple(observation.get("blocking_conflicts", ())),
        }


def _account_specs(options):
    rows = []
    for index, name in enumerate(bundle.NAMES):
        uid = 3000 + index
        home = ("/var/lib/bonup-agent-control/home" if index == 0 else
                "/srv/bonup-agent-work/" + name + "/home")
        rows.append(Account(name, uid, uid, home, "/usr/sbin/nologin"))
    return tuple(rows)


def _group_specs(options):
    return tuple([Group(BONUP_GROUP, BONUP_GID)] +
                 [Group(name, 3000 + index) for index, name in enumerate(bundle.NAMES)])


def _owner_id(name, options):
    if name == "root":
        return 0
    if name == BONUP_GROUP:
        return BONUP_GID
    if name in bundle.NAMES:
        return 3000 + bundle.NAMES.index(name)
    if name == options.django_user:
        return options.django_uid
    raise InstallerBlocked("Unknown installation owner.")


def _group_id(name, options):
    if name == "root":
        return 0
    if name == BONUP_GROUP:
        return BONUP_GID
    if name in bundle.NAMES:
        return 3000 + bundle.NAMES.index(name)
    if name == options.django_group:
        return options.django_gid
    raise InstallerBlocked("Unknown installation group.")


def _directory_specs(options):
    rows = [DirectoryInstall(d["path"], _owner_id(d["owner"], options),
                             _group_id(d["group"], options), _mode(d["mode"]))
            for d in bundle.directories()]
    rows.append(DirectoryInstall(PROJECTION_PARENT, options.django_uid,
                                 options.django_gid, 0o700))
    return tuple(rows)


def _projection_unit(options):
    root = _absolute(options.django_root, "Django root")
    manage = root.rstrip("/") + "/manage.py"
    lines = [
        "[Unit]", "Description=bonUP trusted Django projection receiver",
        "After=local-fs.target", "ConditionPathExists=" + EVENT_CONFIG_PATH,
        "[Service]", "Type=simple", "User=" + options.django_user,
        "Group=" + options.django_group, "WorkingDirectory=" + root,
        "Environment=DJANGO_SETTINGS_MODULE=" + options.django_settings_module,
        "Environment=PYTHONPATH=" + root,
        "ExecStart=/usr/bin/python3 " + manage + " " + DJANGO_COMMAND,
        "UMask=0077", "NoNewPrivileges=yes", "ProtectSystem=strict",
        "ProtectHome=yes", "PrivateTmp=yes", "ReadOnlyPaths=" + root,
        "ReadWritePaths=" + PROJECTION_PARENT, "Restart=on-failure",
        "RestartSec=2s", "TimeoutStopSec=5s", "LimitNOFILE=128",
    ]
    return "\n".join(lines) + "\n"


def _verify_approved_projection_scope(manifest, options):
    """Keep all v5 trust-bearing installer inputs equal to approval."""
    scope = bundle.validate_projection_scope(manifest["projection_scope"])
    registry = scope["registry"]
    if (registry["path"] != REGISTRY_PATH or
            registry["history_path"] != HISTORY_PATH or
            registry["target_schema_version"] != bundle.REGISTRY_TARGET_VERSION or
            registry["accepted_existing_versions"] != [1, 2, 3] or
            registry["initialization"] != "INITIALIZE_ABSENT_THEN_MIGRATE_V1_TO_V2_TO_V3" or
            registry["verify_history"] is not True or
            registry["preserve_existing_records"] is not True or
            registry["reinitialize_existing"] is not False):
        raise InstallerBlocked("Registry installation scope conflicts with approval.")
    service = scope["service"]
    if (options.django_uid, options.django_gid, options.django_user,
            options.django_group, options.django_root,
            options.django_settings_module) != (
                service["uid"], service["gid"], service["user"],
                service["group"], service["root"], service["settings_module"]):
        raise InstallerBlocked("Django service identity conflicts with approval.")
    if options.socket_path != scope["socket"]["path"] or options.socket_mode != int(scope["socket"]["mode"], 8):
        raise InstallerBlocked("Projection socket conflicts with approval.")
    if options.event_config() != bundle.projection_event_config(scope):
        raise InstallerBlocked("Event-delivery configuration conflicts with approval.")
    if (service["path"] != SYSTEMD_UNIT_DIR + "/" + PROJECTION_UNIT or
            service["name"] != PROJECTION_UNIT or
            (service["file_owner"], service["file_owner_uid"],
             service["file_group"], service["file_group_gid"], service["file_mode"]) !=
            ("root", 0, "root", 0, "0444") or
            bundle.sha(_projection_unit(options).encode()) != service["unit_sha256"]):
        raise InstallerBlocked("Projection service conflicts with approval.")
    return scope


def _files(manifest, payloads, options):
    bundle.verify_payloads(manifest, payloads)
    rows = []
    for artifact in bundle.detached_inventory(manifest)["artifacts"]:
        path = artifact["destination"]
        content = (canonical_json(manifest) + "\n").encode() if path == bundle.MANIFEST else payloads[path]
        rows.append(FileInstall(path, content, _owner_id(artifact["owner"], options),
                                _group_id(artifact["group"], options), _mode(artifact["mode"]),
                                artifact.get("artifact_type", "file")))
    event = (canonical_json(options.event_config()) + "\n").encode()
    rows.append(FileInstall(EVENT_CONFIG_PATH, event, 0, CONTROLLER_GID, 0o440, "configuration"))
    rows.append(FileInstall(SYSTEMD_UNIT_DIR + "/" + PROJECTION_UNIT,
                            _projection_unit(options).encode(), 0, 0, 0o444, "unit"))
    return tuple(rows)


def build_plan(manifest, payloads, options):
    """Validate the reviewed bundle and return a non-mutating host plan."""
    if type(options) is not RuntimeInstallOptions:
        raise InstallerBlocked("Explicit installer options required.")
    bundle.validate_manifest(manifest)
    if manifest.get("approved") is not True or manifest.get("activation") is not False:
        raise AuthorityError("Installation-only approved manifest required.")
    if manifest.get("integration_services_approved") is not False:
        raise AuthorityError("Integration service activation is separate.")
    registry_path, history_path = REGISTRY_PATH, HISTORY_PATH
    if manifest["version"] == bundle.INSTALLATION_SCHEMA_VERSION:
        scope = _verify_approved_projection_scope(manifest, options)
        registry_path, history_path = scope["registry"]["path"], scope["registry"]["history_path"]
    if options.django_user in bundle.NAMES or options.django_group in bundle.NAMES:
        raise InstallerBlocked("Django identity uses a reserved Agent Control name.")
    files = _files(manifest, payloads, options)
    units = tuple(sorted({f.path for f in files if f.kind == "unit"} |
                         {SYSTEMD_UNIT_DIR + "/" + name for name in bundle.units()}))
    for path in (registry_path, history_path, EVENT_CONFIG_PATH, PROJECTION_SOCKET):
        _absolute(path, "installation path")
    if (options.django_uid, options.django_gid) in {
            (a.uid, a.gid) for a in _account_specs(options)}:
        raise InstallerBlocked("Django identity collides with Agent Control identity.")
    if options.django_gid in {g.gid for g in _group_specs(options) if g.name != BONUP_GROUP}:
        raise InstallerBlocked("Django group collides with Agent Control group.")
    return InstallPlan(
        VERSION, manifest["bundle_digest"], digest(manifest),
        digest(options.event_config()), _account_specs(options), _group_specs(options),
        Account(options.django_user, options.django_uid, options.django_gid,
                options.django_root, "/usr/sbin/nologin"),
        Group(options.django_group, options.django_gid),
        _directory_specs(options), files, units, registry_path, history_path,
        options.socket_path, "INSTALL_ONLY_NO_SERVICE_ACTIVATION",
    )


def _exact_object(actual, expected):
    return (actual is not None and actual.kind == expected.kind and
            actual.uid == expected.uid and actual.gid == expected.gid and
            actual.mode == expected.mode)


def inspect_host(plan, host):
    """Inspect an injected host adapter without any mutation."""
    conflicts = []
    accounts = {}
    for expected in plan.accounts:
        actual = host.account(expected.username)
        if actual is None:
            occupied = host.account_uid(expected.uid)
            if occupied is not None:
                accounts[expected.username] = "BLOCKED"
                conflicts.append("uid:" + str(expected.uid))
            else:
                accounts[expected.username] = "CREATE"
        elif (actual.uid, actual.gid, actual.home, actual.shell) == (
                expected.uid, expected.gid, expected.home, expected.shell):
            accounts[expected.username] = "OK"
        else:
            accounts[expected.username] = "BLOCKED"
            conflicts.append("account:" + expected.username)
    groups = {}
    for expected in plan.groups:
        actual = host.group(expected.name)
        if actual is None:
            occupied = host.group_gid(expected.gid)
            if occupied is not None:
                groups[expected.name] = "BLOCKED"
                conflicts.append("gid:" + str(expected.gid))
            else:
                groups[expected.name] = "CREATE"
        elif actual.gid == expected.gid:
            groups[expected.name] = "OK"
        else:
            groups[expected.name] = "BLOCKED"
            conflicts.append("group:" + expected.name)
    django = host.account(plan.django_account.username)
    if django is None:
        accounts[plan.django_account.username] = "REQUIRED_EXISTING"
        conflicts.append("missing-django-account:" + plan.django_account.username)
    elif (django.uid, django.gid) == (plan.django_account.uid, plan.django_account.gid):
        accounts[plan.django_account.username] = "EXTERNAL_OK"
    else:
        accounts[plan.django_account.username] = "BLOCKED"
        conflicts.append("django-account:" + plan.django_account.username)
    django_group = host.group(plan.django_group.name)
    if django_group is None:
        groups[plan.django_group.name] = "REQUIRED_EXISTING"
        conflicts.append("missing-django-group:" + plan.django_group.name)
    elif django_group.gid == plan.django_group.gid:
        groups[plan.django_group.name] = "EXTERNAL_OK"
    else:
        groups[plan.django_group.name] = "BLOCKED"
        conflicts.append("django-group:" + plan.django_group.name)
    paths = {}
    for expected in (*plan.directories, *plan.files):
        actual = host.object(expected.path)
        expected_object = HostObject(
            "directory" if isinstance(expected, DirectoryInstall) else
            "unit" if expected.kind == "unit" else "file",
            expected.uid, expected.gid, expected.mode)
        if actual is None:
            paths[expected.path] = "CREATE"
        elif _exact_object(actual, expected_object) and (
                isinstance(expected, DirectoryInstall) or
                host.file_bytes(expected.path) == expected.content):
            paths[expected.path] = "OK"
        else:
            paths[expected.path] = "BLOCKED"
            conflicts.append("path:" + expected.path)
    units = {}
    for expected in plan.files:
        if expected.kind != "unit":
            continue
        actual = host.object(expected.path)
        if actual is None:
            units[expected.path] = "CREATE"
        elif (actual.uid, actual.gid, actual.mode) == (expected.uid, expected.gid, expected.mode) and \
                host.file_bytes(expected.path) == expected.content:
            units[expected.path] = "OK"
        else:
            units[expected.path] = "BLOCKED"
            conflicts.append("unit:" + expected.path)
    registry = host.registry_state(plan.registry_path, plan.history_path)
    if registry not in ("ABSENT", "V1", "V2", "V3"):
        conflicts.append("registry:" + str(registry))
    return {"accounts": accounts, "groups": groups, "paths": paths, "units": units,
            "registry": registry, "blocking_conflicts": tuple(conflicts)}


def prepare_registry(state_path=REGISTRY_PATH, history_path=HISTORY_PATH, *, operation_id=None):
    """Initialize or upgrade through Registry APIs only, always ending at v3."""
    state_path, history_path = _absolute(state_path, "Registry path"), _absolute(history_path, "history path")
    if operation_id is None:
        operation_id = str(uuid4())
    registry = None
    try:
        if Path(state_path).exists():
            registry = Registry(state_path)
        else:
            registry = Registry.initialize(state_path, history_path, operation_id=operation_id)
        if registry.meta("history_path") != history_path:
            raise InstallerBlocked("Registry history binding conflicts with the install plan.")
        version = check_version(registry.db)
        if version == 1:
            migrate_v2(registry)
            version = 2
        if version == 2:
            migrate_v3(registry)
            version = 3
        if version != 3 or registry.verify(check_history=False)["status"] == "BLOCKED":
            raise InstallerBlocked("Registry did not verify as v3.")
        return version
    except (RegistryBlocked, sqlite3.DatabaseError) as error:
        raise InstallerBlocked("Registry validation failed closed.") from error
    finally:
        if registry is not None:
            registry.close()


class HostOperations:
    """Interface used by the installer; production implementation is explicit."""

    def account(self, username): raise NotImplementedError
    def account_uid(self, uid): raise NotImplementedError
    def group(self, name): raise NotImplementedError
    def group_gid(self, gid): raise NotImplementedError
    def object(self, path): raise NotImplementedError
    def file_bytes(self, path): raise NotImplementedError
    def registry_state(self, state_path, history_path): raise NotImplementedError
    def create_group(self, group): raise NotImplementedError
    def create_account(self, account): raise NotImplementedError
    def create_directory(self, directory): raise NotImplementedError
    def create_file(self, file): raise NotImplementedError
    def daemon_reload(self): raise NotImplementedError


class SystemHost(HostOperations):
    """Root-side adapter. It never replaces an existing conflicting object."""

    @staticmethod
    def _secure_parent(path):
        parent = Path(path).parent
        for node in (parent, *parent.parents):
            info = os.lstat(node)
            if stat.S_ISLNK(info.st_mode) or info.st_mode & 0o022:
                raise InstallerBlocked("Mutable or symlinked installation ancestor.")

    def _stat(self, path):
        try:
            info = os.lstat(path)
        except FileNotFoundError:
            return None
        kind = ("directory" if stat.S_ISDIR(info.st_mode) else
                "unit" if path.endswith(".service") else "file")
        return HostObject(kind, info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode))

    def account(self, username):
        try:
            row = pwd.getpwnam(username)
        except KeyError:
            return None
        return Account(username, row.pw_uid, row.pw_gid, row.pw_dir, row.pw_shell)

    def account_uid(self, uid):
        try:
            row = pwd.getpwuid(uid)
        except KeyError:
            return None
        return Account(row.pw_name, row.pw_uid, row.pw_gid, row.pw_dir, row.pw_shell)

    def group(self, name):
        try:
            row = grp.getgrnam(name)
        except KeyError:
            return None
        return Group(name, row.gr_gid)

    def group_gid(self, gid):
        try:
            row = grp.getgrgid(gid)
        except KeyError:
            return None
        return Group(row.gr_name, row.gr_gid)

    def object(self, path): return self._stat(path)

    def file_bytes(self, path):
        try:
            return Path(path).read_bytes()
        except OSError:
            return None

    def registry_state(self, state_path, history_path):
        if not Path(state_path).exists():
            return "ABSENT"
        try:
            db = sqlite3.connect("file:" + state_path + "?mode=ro", uri=True)
            try:
                value = check_version(db)
            finally:
                db.close()
            return "V" + str(value)
        except Exception:
            return "INVALID"

    def _run(self, argv):
        if os.geteuid() != 0:
            raise InstallerBlocked("Privileged installation requires root.")
        subprocess.run(argv, check=True, stdin=subprocess.DEVNULL,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       env={"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LANG": "C.UTF-8"})

    def create_group(self, group):
        self._run(["/usr/sbin/groupadd", "--system", "--gid", str(group.gid), group.name])

    def create_account(self, account):
        self._run(["/usr/sbin/useradd", "--system", "--uid", str(account.uid),
                   "--gid", str(account.gid), "--home-dir", account.home,
                   "--shell", account.shell, "--no-create-home", account.username])
        self._run(["/usr/bin/passwd", "--lock", account.username])

    def create_directory(self, directory):
        path = Path(directory.path)
        self._secure_parent(path)
        path.mkdir(mode=directory.mode, parents=False, exist_ok=False)
        os.chown(path, directory.uid, directory.gid)
        os.chmod(path, directory.mode)

    def create_file(self, file):
        self._secure_parent(file.path)
        fd = os.open(file.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC, file.mode)
        try:
            with os.fdopen(fd, "wb") as stream:
                stream.write(file.content)
                stream.flush()
                os.fsync(stream.fileno())
            os.chown(file.path, file.uid, file.gid)
            os.chmod(file.path, file.mode)
        except BaseException:
            try: os.unlink(file.path)
            except OSError: pass
            raise

    def daemon_reload(self): self._run(["/usr/bin/systemctl", "daemon-reload"])


def apply_plan(plan, host, *, operation_id=None):
    """Apply only a clean plan; preserve Registry data on every failure."""
    observation = inspect_host(plan, host)
    if observation["blocking_conflicts"]:
        raise InstallerBlocked("Installation conflicts detected.")
    created = []
    try:
        for expected in plan.groups:
            if observation["groups"][expected.name] == "CREATE":
                host.create_group(expected)
        for expected in plan.accounts:
            if observation["accounts"][expected.username] == "CREATE":
                host.create_account(expected)
        # Parent-first order is already guaranteed by the reviewed directory list.
        for expected in plan.directories:
            if observation["paths"][expected.path] == "CREATE":
                host.create_directory(expected); created.append(("directory", expected.path))
        registry_state = observation["registry"]
        if registry_state == "ABSENT":
            prepare_registry(plan.registry_path, plan.history_path, operation_id=operation_id)
        elif registry_state in ("V1", "V2", "V3"):
            prepare_registry(plan.registry_path, plan.history_path, operation_id=operation_id)
        else:
            raise InstallerBlocked("Registry state is not trusted.")
        for expected in plan.files:
            if observation["paths"][expected.path] == "CREATE":
                host.create_file(expected); created.append(("file", expected.path))
        if created:
            host.daemon_reload()
        return {"status": "INSTALLED", "created": tuple(created),
                "registry": "V3", "activation": plan.activation}
    except BaseException:
        # Deliberately no automatic deletion: authoritative Registry state and
        # any created objects remain available for receipt-based operator review.
        raise


def rollback_plan(plan, result):
    """Return a non-destructive rollback description.

    Authoritative Registry and Git history are intentionally absent from the
    removable set.  A later operator may remove only receipt-verified objects;
    this function never performs deletion.
    """
    if type(result) is not dict or result.get("status") != "INSTALLED":
        raise InstallerBlocked("Installed receipt required for rollback planning.")
    created = result.get("created")
    if type(created) is not tuple:
        raise InstallerBlocked("Bounded created-object receipt required.")
    allowed = {item.path for item in (*plan.directories, *plan.files)}
    removable = []
    for item in created:
        if (type(item) is not tuple or len(item) != 2 or item[0] not in {"file", "directory"}
                or item[1] not in allowed or item[1] in {plan.registry_path, plan.history_path}):
            raise InstallerBlocked("Rollback object is outside the exact install receipt.")
        removable.append(item[1])
    return {
        "version": VERSION, "recursive": False,
        "remove_created_only": True, "paths": tuple(removable),
        "preserve": (plan.registry_path, plan.history_path),
        "service_activation": "NONE",
    }


def _load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise InstallerBlocked("Installer input is unavailable or invalid.") from error


def main(argv=None):
    parser = argparse.ArgumentParser(prog="bonup-agent-control-install")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--payload-root", required=True)
    parser.add_argument("--django-uid", required=True, type=int)
    parser.add_argument("--django-gid", required=True, type=int)
    parser.add_argument("--django-user", required=True)
    parser.add_argument("--django-group", required=True)
    parser.add_argument("--django-root", required=True)
    parser.add_argument("--django-settings-module", required=True)
    parser.add_argument("--poll-interval-ms", required=True, type=int)
    parser.add_argument("--batch-size", required=True, type=int)
    parser.add_argument("--timeout-ms", required=True, type=int)
    parser.add_argument("--max-message-bytes", required=True, type=int)
    parser.add_argument("--operation-id")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    manifest = _load_json(args.manifest)
    root = Path(args.payload_root)
    payloads = {}
    for artifact in manifest.get("artifacts", []):
        path = root / artifact["destination"].lstrip("/")
        payloads[artifact["destination"]] = path.read_bytes()
    options = RuntimeInstallOptions(
        args.django_uid, args.django_gid, args.django_user, args.django_group,
        args.django_root, args.django_settings_module, args.poll_interval_ms,
        args.batch_size, args.timeout_ms, args.max_message_bytes)
    plan = build_plan(manifest, payloads, options)
    host = SystemHost()
    report = plan.report(inspect_host(plan, host))
    if not args.apply:
        print(canonical_json(report))
        return 0
    if os.geteuid() != 0:
        raise SystemExit("Privileged installation requires --apply as root.")
    result = apply_plan(plan, host, operation_id=args.operation_id)
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (InstallerBlocked, AuthorityError, ValidationError) as error:
        raise SystemExit(str(error))
