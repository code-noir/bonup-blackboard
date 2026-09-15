"""Immutable launch descriptions and pinned mount preparation.

Descriptor-relative inspection pins roots and rejects symlinks/hardlinks. The
installed OS backend consumes pinned descriptors, not generated source pathnames.
The legacy bwrap_argv method remains for synthetic fixture/review use only.
"""
from dataclasses import dataclass, asdict
import os
from pathlib import Path
import stat

from .paths import normalize_path
from .serialization import digest
from .types import ValidationError

RUNTIME_ROOTS = ('/usr',)
FORBIDDEN_COMPONENTS = frozenset({'.codex', '.ssh', '.git-credentials'})


def safe_relative(path, *, git=False):
    path = normalize_path(path)
    if any(p in FORBIDDEN_COMPONENTS or p.startswith('.env') or (p == '.git' and not git) for p in path.split('/')):
        raise ValidationError('Protected path.')
    return path


class TaskRoot:
    """Controller-owned descriptor; never deserialized from model data."""
    def __init__(self, path):
        path = str(path)
        if not os.path.isabs(path) or os.path.realpath(path) != path or path == '/':
            raise ValidationError('Task root must be canonical and explicit.')
        if path == '/home/bonup' or path.startswith('/home/bonup/'):
            raise ValidationError('Founder paths cannot be worker roots.')
        self.path = path
        self.fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        self.identity = self._identity(os.fstat(self.fd))

    @staticmethod
    def _identity(value):
        return value.st_dev, value.st_ino, value.st_uid, value.st_gid

    def verify(self):
        try:
            if os.path.realpath(self.path) != self.path:
                raise ValidationError('Task root path substituted.')
            current = os.stat(self.path, follow_symlinks=False)
            if not stat.S_ISDIR(current.st_mode) or self._identity(current) != self.identity:
                raise ValidationError('Task root substituted.')
            if self._identity(os.fstat(self.fd)) != self.identity:
                raise ValidationError('Task root changed.')
        except OSError:
            raise ValidationError('Task root unavailable.') from None

    def open_read(self, relative, *, git=False):
        relative = safe_relative(relative, git=git)
        self.verify()
        fd = os.dup(self.fd)
        try:
            parts = relative.split('/')
            for index, part in enumerate(parts):
                flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
                if index < len(parts) - 1:
                    flags |= os.O_DIRECTORY
                next_fd = os.open(part, flags, dir_fd=fd)
                os.close(fd)
                fd = next_fd
            info = os.fstat(fd)
            if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)):
                raise ValidationError('Special file rejected.')
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise ValidationError('Hardlinked file rejected.')
            return fd
        except OSError:
            os.close(fd)
            raise ValidationError('Unsafe or unavailable task path.') from None
        except BaseException:
            os.close(fd)
            raise

    def inspect(self, relative, *, create=False, git=False):
        relative = safe_relative(relative, git=git)
        if create:
            # Validate parent through descriptors; only ENOENT at the final leaf is acceptable.
            parent, _, leaf = relative.rpartition('/')
            fd = self.open_read(parent) if parent else os.dup(self.fd)
            try:
                self.verify()
                try:
                    info = os.stat(leaf, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    return
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValidationError('Unsafe write target.')
            finally:
                os.close(fd)
        fd = self.open_read(relative, git=git)
        os.close(fd)

    def export_entries(self, relative):
        """Bounded descriptor walk; never follow links or export special files."""
        count = 0

        def walk(path):
            nonlocal count
            count += 1
            if count > 4096 or len(path.split('/')) > 64:
                raise ValidationError('Export inventory limit.')
            fd = self.open_read(path)
            try:
                kind = 'DIRECTORY' if stat.S_ISDIR(os.fstat(fd).st_mode) else 'FILE'
                yield path, kind
                if kind == 'DIRECTORY':
                    for name in sorted(os.listdir(fd)):
                        yield from walk(path + '/' + name)
            finally:
                os.close(fd)

        yield from walk(safe_relative(relative))

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


@dataclass(frozen=True)
class ConfinementProfile:
    version: int = 1
    readonly_roots: tuple = RUNTIME_ROOTS
    readable_paths: tuple = ()
    writable_paths: tuple = ()
    network: str = 'isolated'
    git_metadata: str = 'hidden'
    timeout_seconds: int = 30
    output_bytes: int = 65536
    process_limit: int = 32
    memory_bytes: int = 268435456
    cpu_seconds: int = 30

    def __post_init__(self):
        if self.version != 1 or type(self.version) is not int or self.readonly_roots != RUNTIME_ROOTS:
            raise ValidationError('Unsupported runtime mounts.')
        if self.network != 'isolated' or self.git_metadata not in {'hidden', 'readonly', 'commit'}:
            raise ValidationError('Unsupported confinement policy.')
        for paths in (self.readable_paths, self.writable_paths):
            if type(paths) is not tuple or len(set(paths)) != len(paths):
                raise ValidationError('Immutable unique paths required.')
            for path in paths:
                safe_relative(path)
        for value, maximum in ((self.timeout_seconds, 3600), (self.output_bytes, 1048576),
                               (self.process_limit, 128), (self.memory_bytes, 2147483648), (self.cpu_seconds, 3600)):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValidationError('Invalid resource limit.')

    @property
    def profile_digest(self):
        data = asdict(self)
        for k in ('readonly_roots', 'readable_paths', 'writable_paths'):
            data[k] = list(data[k])
        return digest(data)

    def environment(self):
        # No dependency on os.environ, USER, LOGNAME or API/provider configuration.
        return (('PATH', '/usr/bin:/bin'), ('HOME', '/home/worker'), ('USER', 'worker'),
                ('LOGNAME', 'worker'), ('LANG', 'C.UTF-8'), ('LC_ALL', 'C.UTF-8'),
                ('TZ', 'UTC'), ('TMPDIR', '/tmp'), ('PWD', '/work'))

    def bwrap_argv(self, root, argv):
        if type(argv) is not tuple or not argv or any(type(v) is not str or '\0' in v for v in argv):
            raise ValidationError('Fixed argv tuple required.')
        if not argv[0].startswith('/usr/bin/'):
            raise ValidationError('Executable outside fixed runtime.')
        root.verify()
        result = ['/usr/bin/bwrap', '--unshare-user', '--unshare-pid', '--unshare-net',
                  '--unshare-ipc', '--unshare-uts', '--cap-drop', 'ALL', '--die-with-parent',
                  '--new-session', '--clearenv', '--ro-bind', '/usr', '/usr']
        for name in ('bin', 'sbin', 'lib', 'lib64'):
            result += ['--symlink', 'usr/' + name, '/' + name]
        result += ['--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp', '--dir', '/run',
                   '--dir', '/home', '--tmpfs', '/home/worker', '--dir', '/work']
        for paths, flag in ((self.readable_paths, '--ro-bind'), (self.writable_paths, '--bind')):
            for path in paths:
                for _ in root.export_entries(path):
                    pass
                result += [flag, root.path + '/' + path, '/work/' + path]
        if self.git_metadata != 'hidden':
            root.inspect('.git', git=True)
            result += ['--bind' if self.git_metadata == 'commit' else '--ro-bind', root.path + '/.git', '/work/.git']
        result += ['--chdir', '/work', '--remount-ro', '/']
        for k, v in self.environment():
            result += ['--setenv', k, v]
        return tuple(result + ['--', *argv])


class PinnedMounts:
    """Prepared FD-based source exports. Caller owns exclusive sanitized workspace lease.

    Pinning prevents pathname substitution, not concurrent content modification.
    Keep this object alive until bwrap consumes the inherited descriptors.
    """
    def __init__(self, root, profile, *, expected_identity):
        from .supervisor_linux import secure_open
        if type(root) is not TaskRoot or type(profile) is not ConfinementProfile:
            raise ValidationError('Trusted root/profile required.')
        root.verify()
        if root.identity != expected_identity:
            raise ValidationError('Workspace identity mismatch.')
        # Writable Git requires a separate sanitized Git helper; generic exports never provide it.
        if profile.git_metadata != 'hidden':
            raise ValidationError('Generic launch cannot export Git metadata.')
        self.root, self.profile, self.entries = root, profile, []
        self.identity = expected_identity
        try:
            for paths, writable in ((profile.readable_paths,False),(profile.writable_paths,True)):
                for path in paths:
                    count = 0
                    def inspect(fd, relative):
                        nonlocal count
                        count += 1
                        if count>4096 or len(relative.split('/'))>64:
                            raise ValidationError('Export inventory limit.')
                        safe_relative(relative)
                        if stat.S_ISDIR(os.fstat(fd).st_mode):
                            for name in os.listdir(fd):
                                child = secure_open(fd, name)
                                try:
                                    inspect(child, relative+'/'+name)
                                finally:
                                    os.close(child)
                    # Own the FD before inspection and retain it through mount setup.
                    # Descendants are opened relative to that object, never its old path.
                    fd = secure_open(root.fd, path)
                    self.entries.append((fd, path, writable))
                    inspect(fd, path)
            root.verify()
        except BaseException:
            self.close()
            raise

    @property
    def pass_fds(self):
        return tuple(fd for fd,_,_ in self.entries)

    def argv(self, fixed_payload):
        from .release_gate import FixedPayload
        if type(fixed_payload) is not FixedPayload:
            raise ValidationError('Fixed payload required.')
        self.root.verify()
        if self.root.identity != self.identity:
            raise ValidationError('Workspace substituted.')
        # Runtime is distribution /usr only. Worker source bind sources are exclusively FDs.
        result = ['/usr/bin/bwrap','--unshare-user','--unshare-pid','--unshare-net',
                  '--unshare-ipc','--unshare-uts','--cap-drop','ALL','--die-with-parent',
                  '--new-session','--clearenv','--ro-bind','/usr','/usr']
        for name in ('bin','sbin','lib','lib64'):
            result += ['--symlink','usr/'+name,'/'+name]
        result += ['--proc','/proc','--dev','/dev','--size','16777216','--tmpfs','/tmp',
                   '--dir','/run','--dir','/home','--size','16777216','--tmpfs','/home/worker','--dir','/work']
        for fd,path,writable in self.entries:
            os.fstat(fd)
            result += ['--bind-fd' if writable else '--ro-bind-fd',str(fd),'/work/'+path]
        result += ['--chdir','/work','--remount-ro','/']
        for key,value in self.profile.environment():
            result += ['--setenv',key,value]
        # fixed_payload MUST be the installed trusted gate, not untrusted model argv.
        return tuple(result+['--',*fixed_payload.argv])

    def close(self):
        for fd,_,_ in self.entries:
            os.close(fd)
        self.entries.clear()
