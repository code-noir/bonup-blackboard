"""Explicit additive control-registry v2 migration. No import-time I/O."""
import sqlite3

from .storage import RegistryBlocked, utc_now

DDL_V2 = (
    '''CREATE TABLE identity_enrollments(
        enrollment_id TEXT PRIMARY KEY, agent_id TEXT NOT NULL REFERENCES agents(agent_id),
        username TEXT NOT NULL UNIQUE, uid INTEGER NOT NULL UNIQUE CHECK(uid>0),
        gid INTEGER NOT NULL UNIQUE CHECK(gid>0), generation INTEGER NOT NULL CHECK(generation>0),
        manifest_digest TEXT NOT NULL, payload TEXT NOT NULL, payload_digest TEXT NOT NULL,
        UNIQUE(agent_id,generation))''',
    '''CREATE TABLE execution_profiles(
        profile_digest TEXT PRIMARY KEY, payload TEXT NOT NULL)''',
    '''CREATE TABLE execution_runtime(
        execution_id TEXT PRIMARY KEY REFERENCES executions(record_id),
        enrollment_id TEXT NOT NULL REFERENCES identity_enrollments(enrollment_id),
        profile_digest TEXT NOT NULL REFERENCES execution_profiles(profile_digest),
        authority_revision INTEGER NOT NULL CHECK(authority_revision>=0),
        revoked INTEGER NOT NULL CHECK(revoked IN (0,1)),
        fencing_epoch INTEGER NOT NULL CHECK(fencing_epoch>0))''',
    '''CREATE TABLE launch_attempts(
        launch_id TEXT PRIMARY KEY, execution_id TEXT NOT NULL REFERENCES execution_runtime(execution_id),
        request_id TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN
        ('REGISTERED','PREPARING','PREPARED','RELEASE_PENDING','RUNNING','STOPPING','TERMINAL')),
        revision INTEGER NOT NULL CHECK(revision>=0), authorization_digest TEXT NOT NULL,
        authority_revision INTEGER NOT NULL, supervisor_generation TEXT NOT NULL, boot_id TEXT NOT NULL,
        cgroup_name TEXT NOT NULL UNIQUE, process_identity TEXT, deadline TEXT NOT NULL,
        binding TEXT NOT NULL, reason TEXT, exit_code INTEGER,
        cleanup_confirmed INTEGER NOT NULL DEFAULT 0 CHECK(cleanup_confirmed IN (0,1)),
        UNIQUE(execution_id,request_id))''',
    '''CREATE TABLE resource_leases(
        resource_key TEXT PRIMARY KEY, execution_id TEXT NOT NULL REFERENCES execution_runtime(execution_id),
        fencing_epoch INTEGER NOT NULL CHECK(fencing_epoch>0), expires_at TEXT NOT NULL,
        held INTEGER NOT NULL CHECK(held IN (0,1)))''',
    'CREATE INDEX runtime_enrollment ON execution_runtime(enrollment_id)',
    'CREATE INDEX launches_state ON launch_attempts(state,execution_id)',
    '''CREATE UNIQUE INDEX one_live_launch ON launch_attempts(execution_id)
       WHERE state!='TERMINAL' ''',
    'CREATE INDEX leases_execution ON resource_leases(execution_id,held)',
    '''CREATE TRIGGER runtime_revision_guard BEFORE UPDATE ON execution_runtime
       WHEN NEW.execution_id!=OLD.execution_id OR NEW.authority_revision!=OLD.authority_revision+1
       BEGIN SELECT RAISE(ABORT,'Runtime authority revision must advance'); END''',
)
DDL_V2 += tuple(
    f'''CREATE TRIGGER immutable_{table}_{action.lower()} BEFORE {action} ON {table}
        BEGIN SELECT RAISE(ABORT,'Immutable runtime enrollment/profile'); END'''
    for table in ('identity_enrollments','execution_profiles') for action in ('UPDATE','DELETE')
)


def _schema(db):
    return {r[0]: r[1] for r in db.execute("SELECT name,sql FROM sqlite_master WHERE sql IS NOT NULL")}


def expected_schema():
    db = sqlite3.connect(':memory:')
    try:
        for sql in DDL_V2:
            db.execute(sql)
        return _schema(db)
    finally:
        db.close()


def check_version(db):
    versions = [r[0] for r in db.execute('SELECT version FROM schema_versions ORDER BY version')]
    expected, actual = expected_schema(), _schema(db)
    if versions == [1]:
        if set(expected) & set(actual):
            raise RegistryBlocked('Partial runtime migration.')
    elif versions == [1, 2]:
        if any(actual.get(k) != v for k, v in expected.items()):
            raise RegistryBlocked('Runtime schema mismatch.')
    else:
        raise RegistryBlocked('Unsupported control schema version.')
    return versions[-1]


def migrate_v2(registry):
    """Caller explicitly selects a stopped control registry. Existing rows are untouched."""
    db = registry.db
    if db.in_transaction:
        raise RegistryBlocked('Migration requires an idle connection.')
    db.execute('BEGIN IMMEDIATE')
    try:
        if check_version(db) != 1:
            raise RegistryBlocked('Only v1 to v2 migration is supported.')
        if registry.verify(check_history=False)['status'] == 'BLOCKED':
            raise RegistryBlocked('Existing registry verification failed.')
        for sql in DDL_V2:
            db.execute(sql)
        db.execute('INSERT INTO schema_versions VALUES (2,?)', (utc_now(),))
        check_version(db)
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok' or db.execute('PRAGMA foreign_key_check').fetchall():
            raise RegistryBlocked('Migration integrity failure.')
        db.commit()
    except BaseException:
        db.rollback()
        raise
