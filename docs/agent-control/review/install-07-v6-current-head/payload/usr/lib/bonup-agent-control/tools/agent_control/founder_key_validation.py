"""Fixed system libsodium public-point predicate; no signing/crypto dispatch API."""
import ctypes
import os
import re
import stat
import threading

from .types import AuthorityError, ValidationError

SONAME = 'libsodium.so.23'
DIRECTORY = '/usr/lib/x86_64-linux-gnu'
DEPENDENCY = dict(soname=SONAME, directory=DIRECTORY, package='libsodium23',
    symbols=['sodium_init','crypto_core_ed25519_is_valid_point'], input_bytes=32,
    operation='ED25519_PUBLIC_POINT_VALIDATION_ONLY', copied=False, caller_configurable=False,
    compatibility='ABI_23_INIT_AND_POSITIVE_NEGATIVE_FEATURE_TESTS', fallback=False)
VALID_VECTOR = bytes.fromhex('3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c')
ORDER_TWO = bytes.fromhex('ec'+'ff'*30+'7f')
_lock = threading.Lock()
_native = None
_failed = False
# Keep the pinned descriptor and dlopen handle alive together for process life.
# Reusing a /proc/self/fd name while dlopen caches that name is unsafe.
_retained = []


def _trusted(info, *, directory=False):
    if (info.st_uid != 0 or info.st_gid != 0 or info.st_mode & 0o6022 or
            not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode))):
        raise AuthorityError('Untrusted libsodium system object.')


def _load_fixed():
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        _trusted(os.fstat(fd),directory=True)
        for part in ('usr','lib','x86_64-linux-gnu'):
            child=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=fd)
            os.close(fd);fd=child
            _trusted(os.fstat(fd),directory=True)
        link=os.stat(SONAME,dir_fd=fd,follow_symlinks=False)
        target=SONAME
        if stat.S_ISLNK(link.st_mode):
            if link.st_uid!=0 or link.st_gid!=0:
                raise AuthorityError('Untrusted libsodium SONAME link.')
            target=os.readlink(SONAME,dir_fd=fd)
            if not re.fullmatch(r'libsodium\.so\.23\.[0-9]+\.[0-9]+',target):
                raise AuthorityError('Unexpected libsodium ABI target.')
        library_fd=os.open(target,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK,dir_fd=fd)
        try:
            info=os.fstat(library_fd)
            _trusted(info)
            if info.st_nlink!=1 or not 0<info.st_size<=16777216:
                raise AuthorityError('Invalid libsodium system library.')
        except BaseException:
            os.close(library_fd)
            raise
        # No filename from a request/environment and no dynamic library search.
        # Retain even a failed load's FD; initialization failure is permanent.
        _retained.append(library_fd)
        library=ctypes.CDLL('/proc/self/fd/'+str(library_fd),mode=os.RTLD_LOCAL|os.RTLD_NOW)
        _retained.append(library)
        after=os.fstat(library_fd)
        if any(getattr(after,name)!=getattr(info,name) for name in
                ('st_dev','st_ino','st_mode','st_uid','st_gid','st_nlink','st_size','st_mtime_ns','st_ctime_ns')):
            raise AuthorityError('libsodium changed during loading.')
        return library
    finally:
        os.close(fd)


class _Predicate:
    def __init__(self):
        library=_load_fixed()
        initialize=library.sodium_init
        initialize.argtypes=[]
        initialize.restype=ctypes.c_int
        self.point=library.crypto_core_ed25519_is_valid_point
        self.point.argtypes=[ctypes.POINTER(ctypes.c_ubyte)]
        self.point.restype=ctypes.c_int
        if initialize() not in (0,1):
            raise AuthorityError('libsodium initialization failed.')
        if self.check(VALID_VECTOR)!=1 or self.check(ORDER_TWO)!=0:
            raise AuthorityError('libsodium public-point feature test failed.')

    def check(self,raw):
        result=self.point((ctypes.c_ubyte*32).from_buffer_copy(raw))
        if type(result) is not int or result not in (0,1):
            raise AuthorityError('Unexpected libsodium predicate result.')
        return result


def validate_public_key(raw):
    """Canonical Ed25519, on curve, main subgroup, not small order; accept 1 only."""
    global _native, _failed
    if type(raw) is not bytes or len(raw)!=32:
        raise ValidationError('Exactly 32 Ed25519 public-key bytes required.')
    if any(name.startswith(('LD_','SODIUM_','LIBSODIUM_')) for name in os.environ):
        raise AuthorityError('Native dependency environment override prohibited.')
    with _lock:
        if _failed:
            raise AuthorityError('libsodium unavailable; restart after dependency repair.')
        try:
            if _native is None:
                _native=_Predicate()
            valid=_native.check(raw)
        except (OSError,AttributeError,TypeError,ValueError,AuthorityError) as error:
            _failed=True
            raise AuthorityError('Founder public-key validation unavailable.') from error
    if valid!=1:
        raise AuthorityError('Invalid founder root public key.')


def preflight():
    """Read-only compatibility check; no package or trust-state mutation."""
    validate_public_key(VALID_VECTOR)
    try:
        validate_public_key(ORDER_TWO)
    except AuthorityError:
        # A dependency failure is not a successful negative-vector result.
        if _failed:
            raise
        return
    raise AuthorityError('libsodium accepted the invalid public-point fixture.')
