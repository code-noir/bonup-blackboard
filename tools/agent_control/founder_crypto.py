"""Ed25519 VERIFY ONLY via the approved OS OpenSSL executable.

No production private-key, signing, key-generation, algorithm selection or plugin
API exists here. Public inputs are pinned memfds; diagnostic output is discarded.
"""
import base64
from dataclasses import dataclass
import fcntl
import os
import re
import selectors
import stat
import subprocess
import time

from .serialization import digest, canonical_json
from .types import AuthorityError, ValidationError
from .founder_key_validation import validate_public_key

OPENSSL = '/usr/bin/openssl'
SPKI_PREFIX = bytes.fromhex('302a300506032b6570032100')
PURPOSES = ('FOUNDER_INSTALLATION_APPROVAL', 'FOUNDER_HOST_TEST_AUTHORIZATION')
DEPENDENCY = dict(path=OPENSSL, minimum_version='3.0', algorithm='Ed25519',
                  operations=['pkeyutl-verify'], package_installation=False,
                  compatibility='ROOT_CONTROLLED_BINARY_AND_KNOWN_ANSWER_VERIFICATION')


def sealed(raw):
    fd = os.memfd_create('bonup-public-verification', os.MFD_CLOEXEC | os.MFD_ALLOW_SEALING)
    try:
        if os.write(fd, raw) != len(raw): raise AuthorityError('Short verification input write.')
        os.lseek(fd, 0, os.SEEK_SET)
        fcntl.fcntl(fd, fcntl.F_ADD_SEALS,
                    fcntl.F_SEAL_WRITE | fcntl.F_SEAL_SHRINK | fcntl.F_SEAL_GROW | fcntl.F_SEAL_SEAL)
        return fd
    except BaseException:
        os.close(fd)
        raise


@dataclass(frozen=True)
class FounderRoot:
    key_id: str
    public_key: bytes
    generation: int
    purposes: tuple = PURPOSES
    algorithm: str = 'Ed25519'

    def __post_init__(self):
        if (type(self.key_id) is not str or not 1 <= len(self.key_id) <= 64 or
                not all(c in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in self.key_id) or
                type(self.public_key) is not bytes or len(self.public_key) != 32 or
                type(self.generation) is not int or self.generation < 1 or
                self.purposes != PURPOSES or self.algorithm != 'Ed25519'):
            raise ValidationError('Invalid immutable founder root.')
        validate_public_key(self.public_key)

    @property
    def identity(self):
        return digest(dict(key_id=self.key_id,public_key=self.public_key.hex(),
                           generation=self.generation,purposes=list(self.purposes),algorithm=self.algorithm))


class OpenSSLVerifier:
    """Fixed command, clean environment, no shell and no caller-selected executable.

    OpenSSL must be at its distribution path under root-controlled ancestors.
    Execute the pinned binary descriptor to close the path replacement window.
    Host updates are allowed; each new invocation revalidates the current object.
    """
    @staticmethod
    def _version(executable):
        """Bounded fixed compatibility probe; never accepts command arguments."""
        process = subprocess.Popen((OPENSSL, 'version'), executable=f'/proc/self/fd/{executable}',
            pass_fds=(executable,), close_fds=True, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, shell=False, cwd='/',
            env={'LANG': 'C', 'LC_ALL': 'C', 'OPENSSL_CONF': '/dev/null'})
        try:
            deadline = time.monotonic() + 2
            output = bytearray()
            with selectors.DefaultSelector() as selector:
                os.set_blocking(process.stdout.fileno(), False)
                selector.register(process.stdout, selectors.EVENT_READ)
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0 or not selector.select(remaining):
                        raise AuthorityError('OpenSSL compatibility probe timed out.')
                    chunk = os.read(process.stdout.fileno(), 513 - len(output))
                    if not chunk:
                        break
                    output.extend(chunk)
                    if len(output) > 512:
                        raise AuthorityError('Unbounded OpenSSL version response.')
            if process.wait(timeout=max(0, deadline-time.monotonic())) != 0:
                raise AuthorityError('OpenSSL compatibility probe failed.')
            match = re.fullmatch(rb'OpenSSL (\d+)\.(\d+)\.(\d+)[^\r\n]*\n', bytes(output))
            if not match or int(match[1]) != 3:
                raise AuthorityError('Reviewed OpenSSL 3.x CLI required.')
            return bytes(output).decode('ascii').strip()
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            process.stdout.close()

    @staticmethod
    def _executable():
        fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            for i, name in enumerate(('usr','bin','openssl')):
                child=os.open(name, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW |
                              (os.O_DIRECTORY if i<2 else 0), dir_fd=fd)
                os.close(fd);fd=child
                info=os.fstat(fd)
                if info.st_uid != 0 or info.st_gid != 0 or info.st_mode & 0o6022:
                    raise AuthorityError('Untrusted OpenSSL executable identity.')
            if not stat.S_ISREG(info.st_mode) or not info.st_mode & 0o111:
                raise AuthorityError('OpenSSL executable unavailable.')
            return os.dup(fd)
        finally: os.close(fd)

    def verify(self, root, message, signature):
        if (type(root) is not FounderRoot or type(message) is not bytes or not 1 <= len(message) <= 16384 or
                type(signature) is not bytes or len(signature) != 64):
            raise ValidationError('Bounded Ed25519 verification inputs required.')
        validate_public_key(root.public_key)
        descriptors=[]
        try:
            executable=self._executable();descriptors.append(executable)
            self._version(executable)
            for raw in (SPKI_PREFIX+root.public_key,message,signature):descriptors.append(sealed(raw))
            pub,msg,sig=descriptors[1:]
            result=subprocess.run((OPENSSL,'pkeyutl','-verify','-pubin','-keyform','DER',
                '-inkey',f'/proc/self/fd/{pub}','-rawin','-in',f'/proc/self/fd/{msg}',
                '-sigfile',f'/proc/self/fd/{sig}'),executable=f'/proc/self/fd/{executable}',
                pass_fds=tuple(descriptors),close_fds=True,stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,shell=False,timeout=2,
                cwd='/',env={'LANG':'C','LC_ALL':'C','OPENSSL_CONF':'/dev/null'})
            if result.returncode != 0:raise AuthorityError('Founder signature rejected.')
        except (OSError,subprocess.TimeoutExpired) as error:
            raise AuthorityError('Founder verification unavailable.') from error
        finally:
            for fd in reversed(descriptors):os.close(fd)

    def preflight(self):
        """Public RFC 8032 vector: verify-only positive and negative capability checks."""
        root = FounderRoot('compatibility-vector', bytes.fromhex(
            '3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c'), 1)
        signature = bytes.fromhex(
            '92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da'
            '085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00')
        self.verify(root, b'\x72', signature)
        try:
            self.verify(root, b'\x73', signature)
        except AuthorityError:
            return
        raise AuthorityError('OpenSSL accepted an invalid known-answer signature.')


def parse_founder_root(cfg):
    """Strict installed PUBLIC artifact parser, including repeated point validity."""
    if type(cfg) is not dict or set(cfg)!={'key_id','algorithm','public_key','generation','purposes'}:
        raise ValidationError('Closed public trust configuration required.')
    from .founder_genesis import public_root, public_artifact
    root=public_root(cfg['public_key'])
    if canonical_json(cfg)!=canonical_json(public_artifact(root)):
        raise ValidationError('Installed founder public key identity mismatch.')
    return root


def load_founder_root():
    """Only installed, root-controlled PUBLIC trust configuration; no env input."""
    from .serialization import parse_json
    path='/etc/bonup-agent-control/founder-root.json'
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for i,part in enumerate(path.split('/')[1:]):
            child=os.open(part,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|
                          (os.O_DIRECTORY if i<2 else 0),dir_fd=fd)
            os.close(fd);fd=child
            info=os.fstat(fd)
            if info.st_uid!=0 or info.st_gid!=0 or info.st_mode&0o022:
                raise AuthorityError('Untrusted founder root configuration.')
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>4096:
            raise AuthorityError('Invalid public trust configuration.')
        raw=os.read(fd,4097)
        after=os.fstat(fd)
        if (len(raw)!=info.st_size or
                (info.st_size,info.st_mtime_ns,info.st_ctime_ns)!=(after.st_size,after.st_mtime_ns,after.st_ctime_ns)):
            raise AuthorityError('Public trust configuration changed.')
        cfg=parse_json(raw)
        return parse_founder_root(cfg)
    finally:os.close(fd)
