"""Durable, controller-private execution fencing for PROD-01."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from .serialization import canonical_json, digest, parse_json
from .storage import external_path, utc_now
from .types import ValidationError


DEFAULT_EXECUTION_PATH = "/var/lib/bonup-agent-control/prod01-executions.sqlite3"
MAX_CAPTURE_BYTES = 65536
PROD_AGENT_ID = "PROD-01"

READY_TO_SEND = "READY_TO_SEND"
SEND_FENCE_COMMITTED = "SEND_FENCE_COMMITTED"
RESPONSE_CAPTURED = "RESPONSE_CAPTURED"
RESPONSE_REJECTED = "RESPONSE_REJECTED"
ARTIFACT_COMMITTED = "ARTIFACT_COMMITTED"
RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
_STATES = frozenset({
    READY_TO_SEND, SEND_FENCE_COMMITTED, RESPONSE_CAPTURED,
    RESPONSE_REJECTED, ARTIFACT_COMMITTED, RECONCILIATION_REQUIRED,
})
_SHA256 = re.compile(r"[a-f0-9]{64}\Z", re.ASCII)
_COMMIT = re.compile(r"[0-9a-f]{40}\Z", re.ASCII)
_TASK_ID = re.compile(r"ATS-[0-9]{4,}\Z", re.ASCII)
_UUID = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z",
    re.ASCII,
)
_SAFE_METADATA_KEYS = frozenset({
    "http_status", "content_type", "content_encoding", "body_bytes", "body_empty",
    "content_length_present", "declared_content_length", "declared_content_length_valid",
    "declared_length_matches", "utf8_decode_success", "json_decode_success",
})


class ProductExecutionFailure(ValidationError):
    """A durable PROD-01 execution cannot safely advance."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__("Durable PROD-01 execution cannot advance safely.")


@dataclass(frozen=True)
class ProdExecutionBinding:
    agent_id: str
    agent_control_task_id: str
    application_task_id: str
    request_digest: str
    policy_digest: str
    source_checkpoint: str

    def __post_init__(self):
        if self.agent_id != PROD_AGENT_ID:
            raise ProductExecutionFailure("EXECUTION_BINDING_INVALID")
        if (not _TASK_ID.fullmatch(self.agent_control_task_id)
                or not _UUID.fullmatch(self.application_task_id)
                or not _SHA256.fullmatch(self.request_digest)
                or not _SHA256.fullmatch(self.policy_digest)
                or not _COMMIT.fullmatch(self.source_checkpoint)):
            raise ProductExecutionFailure("EXECUTION_BINDING_INVALID")

    def to_dict(self):
        return {
            "agent_id": self.agent_id,
            "agent_control_task_id": self.agent_control_task_id,
            "application_task_id": self.application_task_id,
            "request_digest": self.request_digest,
            "policy_digest": self.policy_digest,
            "source_checkpoint": self.source_checkpoint,
        }

    @property
    def execution_key(self):
        return digest(self.to_dict())


@dataclass(frozen=True)
class ProdExecutionRecord:
    execution_key: str
    binding: ProdExecutionBinding
    state: str
    response: bytes | None
    response_digest: str | None
    response_metadata: dict | None
    artifact_id: str | None
    artifact_digest: str | None
    failure_reason: str | None


def _response_digest(value):
    return hashlib.sha256(value).hexdigest()


def _safe_metadata(value):
    if value is None:
        return None
    if type(value) is not dict or not set(value) <= _SAFE_METADATA_KEYS:
        raise ProductExecutionFailure("RESPONSE_METADATA_INVALID")
    encoded = canonical_json(value)
    if len(encoded.encode("utf-8")) > 4096:
        raise ProductExecutionFailure("RESPONSE_METADATA_INVALID")
    return parse_json(encoded)


class ProdExecutionLedger:
    """One durable state record per logical PROD-01 execution.

    This is deliberately separate from Registry authority records and the
    domain-event outbox.  It fences the external provider side effect; it does
    not create task, execution, grant, routing, or publication authority.
    """

    def __init__(self, path=DEFAULT_EXECUTION_PATH):
        if not isinstance(path, (str, Path)) or str(path) == ":memory:":
            if str(path) != ":memory:":
                raise ProductExecutionFailure("EXECUTION_STORAGE_INVALID")
            self.path = Path(path)
            self.db = sqlite3.connect(
                ":memory:", timeout=10, isolation_level=None, check_same_thread=False)
        else:
            self.path = external_path(path)
            self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if self.path.exists() and self.path.is_symlink():
                raise ProductExecutionFailure("EXECUTION_STORAGE_INVALID")
            if not self.path.exists():
                try:
                    descriptor = os.open(
                        self.path,
                        os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_CLOEXEC,
                        0o600,
                    )
                    os.close(descriptor)
                except FileExistsError:
                    pass
            file_stat = os.stat(self.path)
            if (not stat.S_ISREG(file_stat.st_mode)
                    or file_stat.st_uid != os.getuid()
                    or file_stat.st_mode & 0o077):
                raise ProductExecutionFailure("EXECUTION_STORAGE_INVALID")
            self.db = sqlite3.connect(
                str(self.path), timeout=10, isolation_level=None, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute(
            """CREATE TABLE IF NOT EXISTS prod01_executions(
                execution_key TEXT PRIMARY KEY,
                task_id TEXT NOT NULL UNIQUE,
                binding_json TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN (
                    'READY_TO_SEND','SEND_FENCE_COMMITTED','RESPONSE_CAPTURED',
                    'RESPONSE_REJECTED','ARTIFACT_COMMITTED','RECONCILIATION_REQUIRED')),
                response_bytes BLOB,
                response_digest TEXT,
                response_metadata TEXT,
                artifact_id TEXT,
                artifact_digest TEXT,
                failure_reason TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
        self.db.execute(
            "CREATE INDEX IF NOT EXISTS prod01_executions_state "
            "ON prod01_executions(state)")
        # A newly opened controller ledger represents a restart.  Any prior
        # send fence without a captured response is therefore reconciled
        # before a caller can inspect it.  Live duplicate submissions reuse
        # the already-open ledger and never rewrite an active fence.
        self.db.execute(
            """UPDATE prod01_executions
               SET state=?, failure_reason=?, updated_at=?
               WHERE state=?""",
            (RECONCILIATION_REQUIRED, "PROVIDER_OUTCOME_UNKNOWN", utc_now(),
             SEND_FENCE_COMMITTED),
        )

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    @staticmethod
    def _binding_json(binding):
        return canonical_json(binding.to_dict())

    def _row(self, row):
        if row is None:
            return None
        try:
            binding_value = parse_json(row["binding_json"])
            binding = ProdExecutionBinding(**binding_value)
            if (row["execution_key"] != binding.execution_key
                    or row["state"] not in _STATES):
                raise ProductExecutionFailure("EXECUTION_LEDGER_TAMPERED")
            response = row["response_bytes"]
            response_digest = row["response_digest"]
            if response is not None:
                if (type(response) is not bytes or type(response_digest) is not str
                        or response_digest != _response_digest(response)
                        or len(response) > MAX_CAPTURE_BYTES):
                    raise ProductExecutionFailure("RESPONSE_CAPTURE_TAMPERED")
            elif response_digest is not None:
                raise ProductExecutionFailure("RESPONSE_CAPTURE_TAMPERED")
            metadata = (None if row["response_metadata"] is None
                        else _safe_metadata(parse_json(row["response_metadata"])))
            return ProdExecutionRecord(
                row["execution_key"], binding, row["state"], response,
                response_digest, metadata, row["artifact_id"],
                row["artifact_digest"], row["failure_reason"])
        except ProductExecutionFailure:
            raise
        except (TypeError, ValueError, KeyError, json.JSONDecodeError):
            raise ProductExecutionFailure("EXECUTION_LEDGER_TAMPERED") from None

    def _find(self, binding):
        row = self.db.execute(
            "SELECT * FROM prod01_executions WHERE task_id=?",
            (binding.agent_control_task_id,)).fetchone()
        if row is None:
            return None
        record = self._row(row)
        if record.binding != binding:
            raise ProductExecutionFailure("EXECUTION_BINDING_CONFLICT")
        return record

    def prepare(self, binding):
        encoded = self._binding_json(binding)
        now = utc_now()
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current = self._find(binding)
            if current is None:
                self.db.execute(
                    """INSERT INTO prod01_executions(
                       execution_key,task_id,binding_json,state,created_at,updated_at)
                       VALUES (?,?,?,?,?,?)""",
                    (binding.execution_key, binding.agent_control_task_id, encoded,
                     READY_TO_SEND, now, now))
                current = ProdExecutionRecord(
                    binding.execution_key, binding, READY_TO_SEND, None, None,
                    None, None, None, None)
            self.db.commit()
            return current
        except BaseException:
            self.db.rollback()
            raise

    def get(self, binding):
        return self._find(binding)

    def claim_send_fence(self, binding):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current = self._find(binding)
            if current is None:
                raise ProductExecutionFailure("EXECUTION_NOT_PREPARED")
            if current.state != READY_TO_SEND:
                self.db.commit()
                return False, current
            now = utc_now()
            self.db.execute(
                "UPDATE prod01_executions SET state=?,updated_at=? WHERE execution_key=? AND state=?",
                (SEND_FENCE_COMMITTED, now, binding.execution_key, READY_TO_SEND))
            claimed = self.db.execute("SELECT changes()").fetchone()[0] == 1
            current = self._row(self.db.execute(
                "SELECT * FROM prod01_executions WHERE execution_key=?",
                (binding.execution_key,)).fetchone())
            self.db.commit()
            return claimed, current
        except BaseException:
            self.db.rollback()
            raise

    def capture_response(self, binding, response, response_metadata=None):
        if type(response) is not bytes or not response or len(response) > MAX_CAPTURE_BYTES:
            raise ProductExecutionFailure("RESPONSE_CAPTURE_INVALID")
        metadata = _safe_metadata(response_metadata)
        encoded_metadata = None if metadata is None else canonical_json(metadata)
        response_digest = _response_digest(response)
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current = self._find(binding)
            if current is None:
                raise ProductExecutionFailure("EXECUTION_NOT_PREPARED")
            if current.state in {RESPONSE_CAPTURED, ARTIFACT_COMMITTED}:
                if (current.response_digest != response_digest
                        or current.response != response):
                    raise ProductExecutionFailure("RESPONSE_CAPTURE_CONFLICT")
                self.db.commit()
                return current
            if current.state != SEND_FENCE_COMMITTED:
                raise ProductExecutionFailure("RESPONSE_CAPTURE_STATE_INVALID")
            now = utc_now()
            self.db.execute(
                """UPDATE prod01_executions SET state=?,response_bytes=?,response_digest=?,
                   response_metadata=?,updated_at=? WHERE execution_key=? AND state=?""",
                (RESPONSE_CAPTURED, response, response_digest, encoded_metadata, now,
                 binding.execution_key, SEND_FENCE_COMMITTED))
            current = self._row(self.db.execute(
                "SELECT * FROM prod01_executions WHERE execution_key=?",
                (binding.execution_key,)).fetchone())
            self.db.commit()
            return current
        except BaseException:
            self.db.rollback()
            raise

    def mark_response_rejected(self, binding, reason):
        if type(reason) is not str or not reason or len(reason) > 128:
            raise ProductExecutionFailure("EXECUTION_FAILURE_INVALID")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current = self._find(binding)
            if current is None or current.state != RESPONSE_CAPTURED:
                raise ProductExecutionFailure("EXECUTION_FAILURE_STATE_INVALID")
            self.db.execute(
                "UPDATE prod01_executions SET state=?,failure_reason=?,updated_at=? WHERE execution_key=?",
                (RESPONSE_REJECTED, reason, utc_now(), binding.execution_key))
            current = self._row(self.db.execute(
                "SELECT * FROM prod01_executions WHERE execution_key=?",
                (binding.execution_key,)).fetchone())
            self.db.commit()
            return current
        except BaseException:
            self.db.rollback()
            raise

    def mark_reconciliation_required(self, binding):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current = self._find(binding)
            if current is None:
                raise ProductExecutionFailure("EXECUTION_NOT_PREPARED")
            if current.state == SEND_FENCE_COMMITTED:
                self.db.execute(
                    "UPDATE prod01_executions SET state=?,failure_reason=?,updated_at=? WHERE execution_key=?",
                    (RECONCILIATION_REQUIRED, "PROVIDER_OUTCOME_UNKNOWN", utc_now(),
                     binding.execution_key))
                current = self._row(self.db.execute(
                    "SELECT * FROM prod01_executions WHERE execution_key=?",
                    (binding.execution_key,)).fetchone())
            self.db.commit()
            return current
        except BaseException:
            self.db.rollback()
            raise

    def mark_artifact(self, binding, artifact_id, artifact_digest):
        if (type(artifact_id) is not str or not artifact_id
                or type(artifact_digest) is not str or not _SHA256.fullmatch(artifact_digest)):
            raise ProductExecutionFailure("ARTIFACT_BINDING_INVALID")
        self.db.execute("BEGIN IMMEDIATE")
        try:
            current = self._find(binding)
            if current is None:
                raise ProductExecutionFailure("EXECUTION_NOT_PREPARED")
            if current.state == ARTIFACT_COMMITTED:
                if (current.artifact_id != artifact_id
                        or current.artifact_digest != artifact_digest):
                    raise ProductExecutionFailure("ARTIFACT_BINDING_CONFLICT")
                self.db.commit()
                return current
            if current.state not in {READY_TO_SEND, SEND_FENCE_COMMITTED, RESPONSE_CAPTURED}:
                raise ProductExecutionFailure("ARTIFACT_BINDING_STATE_INVALID")
            self.db.execute(
                """UPDATE prod01_executions SET state=?,artifact_id=?,artifact_digest=?,
                   updated_at=? WHERE execution_key=?""",
                (ARTIFACT_COMMITTED, artifact_id, artifact_digest, utc_now(),
                 binding.execution_key))
            current = self._row(self.db.execute(
                "SELECT * FROM prod01_executions WHERE execution_key=?",
                (binding.execution_key,)).fetchone())
            self.db.commit()
            return current
        except BaseException:
            self.db.rollback()
            raise


__all__ = [
    "ARTIFACT_COMMITTED", "DEFAULT_EXECUTION_PATH", "MAX_CAPTURE_BYTES",
    "ProdExecutionBinding", "ProdExecutionLedger", "ProdExecutionRecord",
    "ProductExecutionFailure", "READY_TO_SEND", "RECONCILIATION_REQUIRED",
    "RESPONSE_CAPTURED", "RESPONSE_REJECTED", "SEND_FENCE_COMMITTED",
]
