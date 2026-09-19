"""Immutable, non-authoritative validated PROD-01 proposal artifacts."""
from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat

from .prod_contract import validate_product_proposal
from .serialization import canonical_json, digest, parse_json
from .types import ValidationError

ARTIFACT_DIRECTORY = "/var/lib/bonup-prod/proposals"
ARTIFACT_VERSION = 1
ARTIFACT_MAX_BYTES = 131072
ARTIFACT_AGENT_ID = "PROD-01"
ARTIFACT_MODEL = "PROD-01-STRUCTURED-MODEL-V1"
ARTIFACT_KNOWLEDGE_STATE = "WORKING"
ARTIFACT_VALIDATION_RESULT = "PASS"
_GIT_OID = re.compile(r"[0-9a-f]{40}\Z", re.ASCII)
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z",
    re.ASCII,
)
_FILENAME = re.compile(r"proposal-[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\.json\Z", re.ASCII)
_DIRECTORY_MODE = 0o700
_FILE_MODE = 0o600


class ProposalArtifactError(ValidationError):
    """Bounded artifact persistence or verification failure."""

    def __init__(self, reason="ARTIFACT_INVALID"):
        super().__init__("Validated PROD-01 proposal artifact operation failed.")
        self.reason = reason


@dataclass(frozen=True)
class ProposalArtifact:
    value: dict
    path: str

    @property
    def artifact_id(self):
        return self.value["artifact_id"]

    @property
    def artifact_digest(self):
        return self.value["artifact_digest"]

    @property
    def proposal_bytes(self):
        return (canonical_json(self.value["proposal"]) + "\n").encode("utf-8")


def _directory_path(value):
    if not isinstance(value, (str, Path)) or not str(value):
        raise ProposalArtifactError()
    path = Path(value).absolute()
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents):
        raise ProposalArtifactError()
    return path


def _directory_fd(path, *, create):
    path = _directory_path(path)
    try:
        if create:
            path.mkdir(mode=_DIRECTORY_MODE, parents=True, exist_ok=True)
        directory_stat = os.lstat(path)
    except OSError:
        raise ProposalArtifactError() from None
    if (not stat.S_ISDIR(directory_stat.st_mode)
            or directory_stat.st_uid != os.getuid()
            or directory_stat.st_mode & 0o077):
        raise ProposalArtifactError()
    try:
        descriptor = os.open(
            path, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC | os.O_NOFOLLOW)
    except OSError:
        raise ProposalArtifactError() from None
    opened_stat = os.fstat(descriptor)
    if (not stat.S_ISDIR(opened_stat.st_mode)
            or opened_stat.st_uid != os.getuid()
            or opened_stat.st_mode & 0o077):
        os.close(descriptor)
        raise ProposalArtifactError()
    return descriptor


def _artifact_body(proposal, *, source_checkpoint, logical_model=ARTIFACT_MODEL):
    validated = validate_product_proposal(proposal)
    if (type(source_checkpoint) is not str or not _GIT_OID.fullmatch(source_checkpoint)
            or logical_model != ARTIFACT_MODEL):
        raise ProposalArtifactError()
    body = {
        "artifact_version": ARTIFACT_VERSION,
        "artifact_id": "PROD-01-" + validated["proposal_id"],
        "task_id": validated["task_id"],
        "agent_id": ARTIFACT_AGENT_ID,
        "proposal_id": validated["proposal_id"],
        "proposal": validated,
        "proposal_digest": digest(validated),
        "knowledge_state": ARTIFACT_KNOWLEDGE_STATE,
        "source_checkpoint": source_checkpoint,
        "logical_model": logical_model,
        "validation_result": ARTIFACT_VALIDATION_RESULT,
    }
    body["artifact_digest"] = digest(body)
    return body


def _filename(proposal_id):
    if type(proposal_id) is not str or not _UUID.fullmatch(proposal_id):
        raise ProposalArtifactError()
    return "proposal-" + proposal_id + ".json"


def _read_bounded(fd):
    chunks = []
    total = 0
    while True:
        chunk = os.read(fd, min(8192, ARTIFACT_MAX_BYTES + 1 - total))
        if not chunk:
            break
        total += len(chunk)
        if total > ARTIFACT_MAX_BYTES:
            raise ProposalArtifactError()
        chunks.append(chunk)
    return b"".join(chunks)


def _validate_loaded(raw):
    if type(raw) is not bytes or not raw or len(raw) > ARTIFACT_MAX_BYTES or not raw.endswith(b"\n"):
        raise ProposalArtifactError()
    try:
        text = raw[:-1].decode("utf-8")
        value = parse_json(text)
        if canonical_json(value) != text or type(value) is not dict:
            raise ProposalArtifactError()
        expected = {
            "artifact_version", "artifact_id", "task_id", "agent_id", "proposal_id",
            "proposal", "proposal_digest", "knowledge_state", "source_checkpoint",
            "logical_model", "validation_result", "artifact_digest",
        }
        if set(value) != expected:
            raise ProposalArtifactError()
        if (value["artifact_version"] != ARTIFACT_VERSION
                or value["agent_id"] != ARTIFACT_AGENT_ID
                or value["artifact_id"] != "PROD-01-" + value["proposal_id"]
                or value["knowledge_state"] != ARTIFACT_KNOWLEDGE_STATE
                or value["logical_model"] != ARTIFACT_MODEL
                or value["validation_result"] != ARTIFACT_VALIDATION_RESULT
                or value["source_checkpoint"] is None
                or not _GIT_OID.fullmatch(value["source_checkpoint"])
                or value["proposal_digest"] != digest(value["proposal"])
                or value["artifact_digest"] != digest({k: v for k, v in value.items()
                                                         if k != "artifact_digest"})):
            raise ProposalArtifactError()
        proposal = validate_product_proposal(value["proposal"])
        if (proposal["proposal_id"] != value["proposal_id"]
                or proposal["task_id"] != value["task_id"]
                or proposal["agent_id"] != ARTIFACT_AGENT_ID
                or proposal["knowledge_state"] != ARTIFACT_KNOWLEDGE_STATE):
            raise ProposalArtifactError()
    except (UnicodeError, ValidationError, TypeError, ValueError):
        raise ProposalArtifactError() from None
    return value


class ProposalArtifactStore:
    """Owner-private append-only storage outside the working repository."""

    def __init__(self, directory=ARTIFACT_DIRECTORY):
        self.directory = _directory_path(directory)

    def persist(self, proposal, *, source_checkpoint, logical_model=ARTIFACT_MODEL):
        value = _artifact_body(proposal, source_checkpoint=source_checkpoint,
                               logical_model=logical_model)
        encoded = (canonical_json(value) + "\n").encode("utf-8")
        if len(encoded) > ARTIFACT_MAX_BYTES:
            raise ProposalArtifactError()
        filename = _filename(value["proposal_id"])
        directory_fd = _directory_fd(self.directory, create=True)
        temporary = "." + filename + ".tmp"
        temporary_fd = None
        try:
            temporary_fd = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW,
                _FILE_MODE, dir_fd=directory_fd)
            written = 0
            while written < len(encoded):
                count = os.write(temporary_fd, encoded[written:])
                if count <= 0:
                    raise ProposalArtifactError()
                written += count
            os.fsync(temporary_fd)
            os.close(temporary_fd)
            temporary_fd = None
            try:
                os.link(temporary, filename, src_dir_fd=directory_fd,
                        dst_dir_fd=directory_fd, follow_symlinks=False)
            except OSError:
                raise ProposalArtifactError() from None
            os.fsync(directory_fd)
            os.unlink(temporary, dir_fd=directory_fd)
            return ProposalArtifact(value, str(self.directory / filename))
        except ProposalArtifactError:
            raise
        except OSError:
            raise ProposalArtifactError() from None
        finally:
            if temporary_fd is not None:
                os.close(temporary_fd)
            try:
                os.unlink(temporary, dir_fd=directory_fd)
            except FileNotFoundError:
                pass
            except OSError:
                pass
            os.close(directory_fd)

    def load(self, proposal_id):
        filename = _filename(proposal_id)
        directory_fd = _directory_fd(self.directory, create=False)
        descriptor = None
        try:
            try:
                descriptor = os.open(
                    filename, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW,
                    dir_fd=directory_fd)
            except FileNotFoundError:
                raise ProposalArtifactError("ARTIFACT_MISSING") from None
            except OSError:
                raise ProposalArtifactError() from None
            file_stat = os.fstat(descriptor)
            if (not stat.S_ISREG(file_stat.st_mode)
                    or file_stat.st_uid != os.getuid()
                    or file_stat.st_mode & 0o077):
                raise ProposalArtifactError()
            value = _validate_loaded(_read_bounded(descriptor))
            return ProposalArtifact(value, str(self.directory / filename))
        finally:
            if descriptor is not None:
                os.close(descriptor)
            os.close(directory_fd)
