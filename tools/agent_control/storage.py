"""SQLite storage primitives, explicitly initialized outside application repositories."""
from datetime import datetime, timezone
import os
from pathlib import Path
import sqlite3

from .types import ValidationError

DB_VERSION = 1


class RegistryBlocked(ValidationError):
    """Consistency failure; no automatic repair is authorized."""


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec='microseconds').replace('+00:00', 'Z')


def external_path(value):
    path = Path(value).expanduser().absolute()
    if path.is_symlink() or any(p.is_symlink() for p in path.parents):
        raise RegistryBlocked('Control paths cannot traverse symbolic links.')
    path = path.resolve(strict=False)
    for parent in (path, *path.parents):
        if (parent / '.git').exists():
            raise RegistryBlocked('Runtime storage must be outside working Git repositories.')
    return path


def connect(path):
    db = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, timeout=10, isolation_level=None)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys=ON')
    db.execute('PRAGMA busy_timeout=10000')
    db.execute('PRAGMA synchronous=FULL')
    return db


DDL = [
    'CREATE TABLE schema_versions(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)',
    'CREATE TABLE metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL)',
    'CREATE TABLE sequences(name TEXT PRIMARY KEY, value INTEGER NOT NULL CHECK(value>=0))',
    '''CREATE TABLE tasks(task_id TEXT PRIMARY KEY, task_uuid TEXT UNIQUE NOT NULL,
       payload TEXT NOT NULL, payload_digest TEXT NOT NULL)''',
    '''CREATE TABLE task_specs(task_id TEXT NOT NULL REFERENCES tasks(task_id), version INTEGER NOT NULL,
       spec_digest TEXT NOT NULL, frozen INTEGER NOT NULL CHECK(frozen IN (0,1)), payload TEXT NOT NULL,
       PRIMARY KEY(task_id,version))''',
    '''CREATE TABLE agents(agent_id TEXT PRIMARY KEY, payload TEXT NOT NULL, payload_digest TEXT NOT NULL)''',
    '''CREATE TABLE executions(record_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
       agent_id TEXT NOT NULL REFERENCES agents(agent_id), payload TEXT NOT NULL,
       payload_digest TEXT NOT NULL, context TEXT NOT NULL)''',
    '''CREATE TABLE records(record_id TEXT PRIMARY KEY, task_id TEXT REFERENCES tasks(task_id),
       kind TEXT NOT NULL, status TEXT NOT NULL, revision INTEGER NOT NULL,
       payload TEXT NOT NULL, payload_digest TEXT NOT NULL, context TEXT NOT NULL)''',
    '''CREATE TABLE candidates(record_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
       spec_version INTEGER NOT NULL, invalidated INTEGER NOT NULL DEFAULT 0 CHECK(invalidated IN (0,1)),
       payload TEXT NOT NULL, payload_digest TEXT NOT NULL, context TEXT NOT NULL,
       FOREIGN KEY(task_id,spec_version) REFERENCES task_specs(task_id,version))''',
    '''CREATE TABLE approvals(record_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
       candidate_id TEXT REFERENCES candidates(record_id), spec_version INTEGER NOT NULL,
       payload TEXT NOT NULL, payload_digest TEXT NOT NULL, context TEXT NOT NULL,
       FOREIGN KEY(task_id,spec_version) REFERENCES task_specs(task_id,version))''',
    '''CREATE TABLE evidence(record_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
       candidate_id TEXT REFERENCES candidates(record_id), execution_id TEXT NOT NULL REFERENCES executions(record_id),
       payload TEXT NOT NULL, payload_digest TEXT NOT NULL, context TEXT NOT NULL)''',
    '''CREATE TABLE candidate_events(record_id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES tasks(task_id),
       candidate_id TEXT NOT NULL REFERENCES candidates(record_id),
       payload TEXT NOT NULL, payload_digest TEXT NOT NULL, context TEXT NOT NULL)''',
    '''CREATE TABLE operations(operation_id TEXT PRIMARY KEY, payload_digest TEXT NOT NULL,
       result TEXT NOT NULL, created_at TEXT NOT NULL)''',
    '''CREATE TABLE audit_events(sequence INTEGER PRIMARY KEY, event_id TEXT UNIQUE NOT NULL,
       operation_id TEXT UNIQUE NOT NULL REFERENCES operations(operation_id) DEFERRABLE INITIALLY DEFERRED,
       payload TEXT NOT NULL, event_digest TEXT NOT NULL)''',
    '''CREATE TABLE outbox(outbox_id INTEGER PRIMARY KEY AUTOINCREMENT, publication_id TEXT UNIQUE NOT NULL,
       operation_id TEXT NOT NULL REFERENCES operations(operation_id) DEFERRABLE INITIALLY DEFERRED,
       record_type TEXT NOT NULL, record_id TEXT NOT NULL, path TEXT UNIQUE NOT NULL,
       payload TEXT NOT NULL, payload_digest TEXT NOT NULL, created_at TEXT NOT NULL,
       source_payload TEXT NOT NULL, source_digest TEXT NOT NULL)''',
    '''CREATE TABLE maintenance_operations(operation_id TEXT PRIMARY KEY, payload_digest TEXT NOT NULL, result TEXT NOT NULL)''',
    '''CREATE TABLE publications(publication_id TEXT PRIMARY KEY, outbox_id INTEGER UNIQUE NOT NULL REFERENCES outbox(outbox_id),
       record_type TEXT NOT NULL, record_id TEXT NOT NULL, payload_digest TEXT NOT NULL,
       git_commit TEXT NOT NULL, published_at TEXT NOT NULL, status TEXT NOT NULL CHECK(status='ACKNOWLEDGED'))''',
]
for table in ('audit_events', 'outbox', 'operations', 'publications', 'approvals', 'evidence', 'executions', 'candidate_events'):
    for action in ('UPDATE', 'DELETE'):
        DDL.append(f'''CREATE TRIGGER immutable_{table}_{action.lower()} BEFORE {action} ON {table}
                   BEGIN SELECT RAISE(ABORT,'Append-only control history'); END''')


def create_database(path):
    path = external_path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(fd)
    return path
