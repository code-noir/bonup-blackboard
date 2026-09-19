"""Founder-controlled, private, single-response PROD-01 capture."""
import os
import re
import stat
import uuid

from .prod_model_transport import MAX_RESPONSE_BYTES
from .types import ValidationError

CAPTURE_DIRECTORY = "/var/tmp/bonup-prod-diagnostic"
CAPTURE_MODE = "PRIVATE_DIAGNOSTIC"
_CAPTURE_FILENAME = re.compile(r"response-[0-9a-f]{32}\.bin\Z", re.ASCII)
_DIRECTORY_MODE = 0o700
_FILE_MODE = 0o600


class PrivateResponseCaptureError(ValidationError):
    """Bounded capture failure without response or filesystem detail."""

    def __init__(self):
        super().__init__("Private provider response capture failed.")


def _directory_fd(*, create):
    try:
        directory_stat = os.lstat(CAPTURE_DIRECTORY)
    except FileNotFoundError:
        if not create:
            return None
        try:
            os.mkdir(CAPTURE_DIRECTORY, _DIRECTORY_MODE)
        except FileExistsError:
            pass
        except OSError:
            raise PrivateResponseCaptureError() from None
        try:
            directory_stat = os.lstat(CAPTURE_DIRECTORY)
        except OSError:
            raise PrivateResponseCaptureError() from None
    except OSError:
        raise PrivateResponseCaptureError() from None
    if (not stat.S_ISDIR(directory_stat.st_mode)
            or directory_stat.st_uid != os.getuid()
            or directory_stat.st_mode & 0o077):
        raise PrivateResponseCaptureError()
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW
    try:
        descriptor = os.open(CAPTURE_DIRECTORY, flags)
    except OSError:
        raise PrivateResponseCaptureError() from None
    opened_stat = os.fstat(descriptor)
    if (not stat.S_ISDIR(opened_stat.st_mode)
            or opened_stat.st_uid != os.getuid()
            or opened_stat.st_mode & 0o077):
        os.close(descriptor)
        raise PrivateResponseCaptureError()
    return descriptor


class PrivateResponseCapture:
    """Capture exactly one non-empty, already-bounded response body."""

    def __init__(self):
        self.__result = {
            "created": False,
            "path": None,
            "bytes": 0,
            "mode": CAPTURE_MODE,
        }
        self.__captured = False

    @property
    def result(self):
        return dict(self.__result)

    @property
    def used(self):
        return self.__captured

    def capture(self, body):
        if self.__captured:
            raise PrivateResponseCaptureError()
        self.__captured = True
        if type(body) is not bytes or len(body) > MAX_RESPONSE_BYTES:
            raise PrivateResponseCaptureError()
        if not body:
            return
        directory_fd = _directory_fd(create=True)
        filename = "response-" + uuid.uuid4().hex + ".bin"
        if not _CAPTURE_FILENAME.fullmatch(filename):
            os.close(directory_fd)
            raise PrivateResponseCaptureError()
        file_descriptor = None
        try:
            flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW
            file_descriptor = os.open(
                filename, flags, _FILE_MODE, dir_fd=directory_fd)
            file_stat = os.fstat(file_descriptor)
            if (not stat.S_ISREG(file_stat.st_mode)
                    or file_stat.st_uid != os.getuid()
                    or file_stat.st_mode & 0o077):
                raise PrivateResponseCaptureError()
            written = 0
            while written < len(body):
                count = os.write(file_descriptor, body[written:])
                if count <= 0:
                    raise PrivateResponseCaptureError()
                written += count
            os.fsync(file_descriptor)
            self.__result.update({
                "created": True,
                "path": os.path.join(CAPTURE_DIRECTORY, filename),
                "bytes": len(body),
            })
        except PrivateResponseCaptureError:
            raise
        except OSError:
            raise PrivateResponseCaptureError() from None
        finally:
            if file_descriptor is not None:
                os.close(file_descriptor)
            if not self.__result["created"]:
                try:
                    os.unlink(filename, dir_fd=directory_fd)
                except FileNotFoundError:
                    pass
                except OSError:
                    pass
            os.close(directory_fd)


def cleanup_private_response_captures():
    """Unlink only generated capture files and verify they are absent."""
    directory_fd = _directory_fd(create=False)
    if directory_fd is None:
        return 0
    removed = 0
    try:
        for filename in os.listdir(directory_fd):
            if not _CAPTURE_FILENAME.fullmatch(filename):
                continue
            try:
                os.unlink(filename, dir_fd=directory_fd)
            except FileNotFoundError:
                continue
            removed += 1
        remaining = [
            filename for filename in os.listdir(directory_fd)
            if _CAPTURE_FILENAME.fullmatch(filename)
        ]
        if remaining:
            raise PrivateResponseCaptureError()
        return removed
    finally:
        os.close(directory_fd)
