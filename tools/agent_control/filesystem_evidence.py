"""Supervisor-only pinned inspection and path-free controller expectations.

No descriptor is deserialized, no host mount is created and no worker is launched.
Installed mappings are trusted inputs; the request interface accepts UUIDs only.
"""
from dataclasses import dataclass
import configparser
import os
from pathlib import Path
import stat
from types import MappingProxyType

from .confinement import TaskRoot, PinnedMounts, ConfinementProfile, safe_relative
from .protocol import uuid_value, bounded_json
from .serialization import canonical_json, digest
from .supervisor_linux import secure_open
from .types import AuthorityError, ValidationError
from .schema import valid_format
from .paths import PathRule, overlaps


def identity(value):
    if type(value) is not tuple or len(value) != 4 or any(type(v) is not int or v < 0 for v in value):
        raise ValidationError('Exact device/inode/UID/GID required.')
    return value


def mount_id(fd):
    # Kernel descriptor metadata only, never file contents or a pathname reopen.
    for line in Path(f'/proc/self/fdinfo/{fd}').read_text().splitlines():
        if line.startswith('mnt_id:'):
            return int(line.split()[1])
    raise AuthorityError('Mount identity unavailable.')


@dataclass(frozen=True)
class StoragePolicy:
    mount_id: int
    mode: str = 'EPHEMERAL_TMPFS_WORKSPACE'
    bytes: int = 134217728
    inodes: int = 16384

    def __post_init__(self):
        if (type(self.mount_id) is not int or self.mount_id <= 0 or self.mode != 'EPHEMERAL_TMPFS_WORKSPACE' or
                type(self.bytes) is not int or self.bytes != 134217728 or
                type(self.inodes) is not int or self.inodes != 16384):
            raise ValidationError('Approved bounded storage policy required.')

    def data(self):
        return dict(mount_id=self.mount_id, mode=self.mode, bytes=self.bytes, inodes=self.inodes)


def verify_storage(fd, policy):
    """Real read-only probe; synthetic tests explicitly inject their own probe."""
    import ctypes
    from .supervisor_linux import _libc, _check
    buf = ctypes.create_string_buffer(256)
    _check(_libc().fstatfs(fd, ctypes.byref(buf)), 'fstatfs')
    magic = ctypes.c_long.from_buffer(buf).value
    fs = os.fstatvfs(fd)
    if (magic != 0x01021994 or mount_id(fd) != policy.mount_id or
            not 0 < fs.f_blocks * fs.f_frsize <= policy.bytes or not 0 < fs.f_files <= policy.inodes):
        raise AuthorityError('Workspace storage is not the approved bounded tmpfs.')
    return policy.data()


@dataclass(frozen=True)
class Export:
    logical_id: str
    relative: str
    object_identity: tuple
    kind: str
    writable: bool

    def __post_init__(self):
        uuid_value(self.logical_id); safe_relative(self.relative); identity(self.object_identity)
        if self.kind not in {'FILE', 'DIRECTORY'} or type(self.writable) is not bool:
            raise ValidationError('Invalid export policy.')

    def data(self):
        return dict(logical_id=self.logical_id, relative=self.relative, identity=list(self.object_identity),
                    kind=self.kind, writable=self.writable)


@dataclass(frozen=True)
class RootMapping:
    logical_id: str
    host_root: str
    object_identity: tuple
    generation: int
    exports: tuple
    profile: ConfinementProfile
    storage: StoragePolicy
    repository_id: str | None = None
    repository_identity: tuple | None = None

    def __post_init__(self):
        uuid_value(self.logical_id); identity(self.object_identity)
        path = self.host_root
        if (type(path) is not str or not path.startswith(('/srv/bonup-agent-work/', '/tmp/', '/var/tmp/')) or
                os.path.normpath(path) != path or any(p in {'.codex','.ssh','.git'} for p in Path(path).parts)):
            raise ValidationError('Root outside approved worker storage.')
        if type(self.generation) is not int or self.generation <= 0:
            raise ValidationError('Provisioning generation required.')
        if (type(self.profile) is not ConfinementProfile or self.profile.git_metadata != 'hidden' or
                type(self.storage) is not StoragePolicy or type(self.exports) is not tuple or
                not 1 <= len(self.exports) <= 4 or any(type(e) is not Export for e in self.exports)):
            raise ValidationError('Closed ordinary mount policy required.')
        if (len({e.logical_id for e in self.exports}) != len(self.exports) or
                len({e.relative for e in self.exports}) != len(self.exports) or
                tuple(e.relative for e in self.exports if not e.writable) != self.profile.readable_paths or
                tuple(e.relative for e in self.exports if e.writable) != self.profile.writable_paths):
            raise ValidationError('Export scope differs from immutable confinement profile.')
        if self.repository_id is not None:
            uuid_value(self.repository_id); identity(self.repository_identity)
        elif self.repository_identity is not None:
            raise ValidationError('Repository identity requires a logical repository ID.')

    def expectation(self):
        return ExpectedFilesystem(canonical_json(dict(root_id=self.logical_id,
            identity=list(self.object_identity), generation=self.generation, kind='DIRECTORY',
            exports=[e.data() for e in self.exports], profile_digest=self.profile.profile_digest,
            storage=self.storage.data(), repository_id=self.repository_id,
            repository_identity=None if self.repository_identity is None else list(self.repository_identity))))


@dataclass(frozen=True)
class ExpectedFilesystem:
    """Controller-owned installed policy, not constructed from received evidence."""
    policy_json: str

    def __post_init__(self):
        data = bounded_json(self.policy_json.encode())
        if type(data) is not dict or set(data) != {'root_id','identity','generation','kind','exports',
                'profile_digest','storage','repository_id','repository_identity'}:
            raise ValidationError('Closed filesystem expectation required.')
        if canonical_json(data) != self.policy_json or len(self.policy_json.encode()) > 2048:
            raise ValidationError('Bounded canonical filesystem policy required.')
        uuid_value(data['root_id']); identity(tuple(data['identity']))
        if (type(data['generation']) is not int or data['generation']<=0 or data['kind']!='DIRECTORY' or
                not valid_format('sha256',data['profile_digest']) or type(data['exports']) is not list or
                not 1<=len(data['exports'])<=4):
            raise ValidationError('Invalid filesystem policy facts.')
        StoragePolicy(**data['storage'])
        seen=set()
        for row in data['exports']:
            if type(row) is not dict or set(row)!={'logical_id','relative','identity','kind','writable'}:
                raise ValidationError('Unexpected export facts.')
            Export(row['logical_id'],row['relative'],tuple(row['identity']),row['kind'],row['writable'])
            if row['logical_id'] in seen:
                raise ValidationError('Duplicate export ID.')
            seen.add(row['logical_id'])
        if data['repository_id'] is not None:
            uuid_value(data['repository_id']); identity(tuple(data['repository_identity']))
        elif data['repository_identity'] is not None:
            raise ValidationError('Unbound repository identity.')

    @property
    def policy(self): return bounded_json(self.policy_json.encode())
    @property
    def policy_digest(self): return digest(self.policy)

    def accept(self, evidence, launch_id, generation):
        uuid_value(launch_id); uuid_value(generation)
        expected = dict(version=1, launch_id=launch_id, supervisor_generation=generation,
                        policy=self.policy, policy_digest=self.policy_digest)
        expected['evidence_digest'] = digest(expected)
        if canonical_json(evidence) != canonical_json(expected):
            raise AuthorityError('Filesystem evidence differs from original installed authority.')
        return expected['evidence_digest']

    def root_view(self, approved_grant_path):
        return LogicalRootView(self, approved_grant_path)


class LogicalRootView:
    """Authorization metadata only: no FD, os.open, stat, or worker-root traversal.

    Initial authorization is conditional on matching PREPARED evidence. Generic Git
    operations remain denied; this does not replace the separately authorized helper.
    """
    def __init__(self, expected, path):
        self.expected, self.path = expected, path
        self.identity = tuple(expected.policy['identity'])
        self.filesystem_policy_digest = expected.policy_digest
    def verify(self):
        if self.filesystem_policy_digest != self.expected.policy_digest or self.identity != tuple(self.expected.policy['identity']):
            raise AuthorityError('Logical workspace policy changed.')
    def export_entries(self, path):
        self.verify()
        for entry in self.expected.policy['exports']:
            if entry['relative'] == path:
                yield path, entry['kind']
                return
        raise ValidationError('Unapproved logical export.')
    def check_export_denials(self, path, denied):
        # No inventory read: even a not-yet-created forbidden descendant must
        # prevent exporting its ancestor directory.
        for entry, kind in self.export_entries(path):
            if any(overlaps(PathRule(kind, entry), rule) for rule in denied):
                raise ValidationError('Logical export intersects protected scope.')
    def inspect(self, path, *, create=False):
        safe_relative(path); self.verify()
        for entry in self.expected.policy['exports']:
            if (path == entry['relative'] or (entry['kind']=='DIRECTORY' and path.startswith(entry['relative']+'/'))):
                if not create or entry['writable']:
                    return
        raise ValidationError('Path outside installed export policy.')
    def open_read(self, *args, **kwargs):
        raise AuthorityError('Controller cannot open worker filesystem objects.')


def validate_evidence(data):
    if type(data) is not dict or set(data)!={'version','launch_id','supervisor_generation','policy','policy_digest','evidence_digest'}:
        raise ValidationError('Unexpected filesystem evidence fields.')
    if type(data['version']) is not int or data['version']!=1:
        raise ValidationError('Unsupported filesystem evidence version.')
    expected=ExpectedFilesystem(canonical_json(data['policy']))
    expected.accept(data,data['launch_id'],data['supervisor_generation'])
    if len(canonical_json(data).encode())>3072:
        raise ValidationError('Filesystem evidence limit.')
    return data


def verify_repository(root, mapping):
    if mapping.repository_id is None:
        return
    fd = secure_open(root.fd, '.git', directory=True, git=True)
    try:
        if TaskRoot._identity(os.fstat(fd)) != mapping.repository_identity:
            raise AuthorityError('Repository metadata substituted.')
        for relative in ('commondir','gitdir','worktrees','objects/info/alternates','objects/info/http-alternates'):
            try:
                child = secure_open(fd, relative, git=True)
            except FileNotFoundError:
                continue
            os.close(child)
            raise AuthorityError('External Git metadata reference rejected.')
        config = secure_open(fd, 'config', git=True)
        try:
            raw = os.read(config, 4097)
            if len(raw)>4096:
                raise AuthorityError('Git config limit.')
            parser = configparser.ConfigParser(interpolation=None, strict=True)
            parser.read_string(raw.decode('utf-8'))
            if (parser.defaults() or set(parser.sections()) != {'core'} or
                    not set(parser['core']) <= {'repositoryformatversion','filemode','bare','logallrefupdates'} or
                    parser['core'].get('repositoryformatversion') != '0' or parser['core'].get('bare') != 'false'):
                raise AuthorityError('Git configuration is not sanitized ordinary task metadata.')
        finally:
            os.close(config)
    finally:
        os.close(fd)


class PinnedFilesystem:
    def __init__(self, mapping, launch_id, generation, *, storage_probe=verify_storage):
        self.mapping, self.launch_id, self.generation = mapping, launch_id, generation
        self.root = self.mounts = None
        self.closed = False
        uuid_value(launch_id); uuid_value(generation)
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            parts = Path(mapping.host_root).parts[1:]
            for index, part in enumerate(parts):
                child = secure_open(fd, part, directory=True, allow_mount=index==len(parts)-1)
                os.close(fd); fd = child
            # Transfer the very same FD; adopt closes it on failure.
            adopted, fd = fd, None
            self.root = TaskRoot.adopt(mapping.host_root, adopted, mapping.object_identity)
            if mount_id(self.root.fd) != mapping.storage.mount_id:
                raise AuthorityError('Root mount substituted.')
            if storage_probe(self.root.fd, mapping.storage) != mapping.storage.data():
                raise AuthorityError('Storage evidence mismatch.')
            verify_repository(self.root, mapping)
            self.mounts = PinnedMounts(self.root, mapping.profile, expected_identity=mapping.object_identity)
            by_path = {e.relative:e for e in mapping.exports}
            for pinned, path, writable in self.mounts.entries:
                info = os.fstat(pinned)
                expected = by_path[path]
                kind = 'DIRECTORY' if stat.S_ISDIR(info.st_mode) else 'FILE'
                if (TaskRoot._identity(info) != expected.object_identity or kind != expected.kind or
                        mount_id(pinned) != mapping.storage.mount_id):
                    raise AuthorityError('Export identity/type/mount differs from approval.')
            self.expectation = mapping.expectation()
            self._evidence = dict(version=1, launch_id=launch_id, supervisor_generation=generation,
                                 policy=self.expectation.policy, policy_digest=self.expectation.policy_digest)
            self._evidence['evidence_digest'] = digest(self._evidence)
        except BaseException:
            self.close()
            raise
        finally:
            if fd is not None: os.close(fd)

    def verify(self, launch_id):
        if self.closed or launch_id != self.launch_id:
            raise AuthorityError('Closed or cross-launch filesystem handle.')
        self.root.verify()
        if mount_id(self.root.fd) != self.mapping.storage.mount_id:
            raise AuthorityError('Pinned mount identity changed.')
        verify_repository(self.root,self.mapping)
        for fd,path,_ in self.mounts.entries:
            expected = next(e for e in self.mapping.exports if e.relative==path)
            if TaskRoot._identity(os.fstat(fd)) != expected.object_identity:
                raise AuthorityError('Pinned export descriptor substituted.')
    def evidence(self):
        self.verify(self.launch_id)
        return bounded_json(canonical_json(self._evidence).encode())
    def argv(self, launch_id, payload):
        self.verify(launch_id)
        return self.mounts.argv(payload)
    @property
    def pass_fds(self):
        self.verify(self.launch_id)
        return self.mounts.pass_fds
    def close(self):
        if self.closed: return
        self.closed = True
        try:
            if self.mounts is not None: self.mounts.close()
        finally:
            if self.root is not None: self.root.close()


class FilesystemInspector:
    """Supervisor-local handle owner. Cancellation/disconnect/reconcile close all FDs."""
    def __init__(self, mappings, *, storage_probe=verify_storage):
        if any(type(m) is not RootMapping for m in mappings) or len({m.logical_id for m in mappings}) != len(mappings):
            raise ValidationError('Unique immutable installed root mappings required.')
        self.mappings = MappingProxyType({m.logical_id:m for m in mappings})
        self.storage_probe, self.handles, self.used = storage_probe, {}, set()
    def prepare(self, root_id, policy_digest, launch_id, generation):
        uuid_value(root_id); uuid_value(launch_id)
        mapping = self.mappings.get(root_id)
        if mapping is None or mapping.expectation().policy_digest != policy_digest:
            raise AuthorityError('Unknown/stale logical filesystem policy.')
        if launch_id in self.used or self.handles or len(self.used)>=4096:
            raise AuthorityError('Filesystem handle replay or concurrent inspection.')
        self.used.add(launch_id)
        handle = PinnedFilesystem(mapping, launch_id, generation, storage_probe=self.storage_probe)
        self.handles[launch_id] = handle
        return handle
    def close(self, launch_id):
        handle = self.handles.pop(launch_id, None)
        if handle is not None: handle.close()
    def disconnect(self):
        for key in tuple(self.handles): self.close(key)
