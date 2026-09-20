"""Explicit additive control-registry migrations. No import-time I/O."""
import json
import sqlite3

from .storage import DDL, RegistryBlocked, utc_now

DDL_V2 = (
    '''CREATE TABLE product_reviews(
        record_id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL REFERENCES tasks(task_id),
        artifact_id TEXT NOT NULL UNIQUE,
        artifact_digest TEXT NOT NULL,
        proposal_id TEXT NOT NULL UNIQUE,
        proposal_digest TEXT NOT NULL,
        binding_digest TEXT NOT NULL UNIQUE,
        payload TEXT NOT NULL,
        payload_digest TEXT NOT NULL,
        context TEXT NOT NULL)''',
    '''CREATE TABLE domain_events(
        event_id TEXT PRIMARY KEY,
        event_type TEXT NOT NULL,
        review_id TEXT NOT NULL UNIQUE REFERENCES product_reviews(record_id),
        operation_id TEXT NOT NULL REFERENCES operations(operation_id) DEFERRABLE INITIALLY DEFERRED,
        occurred_at TEXT NOT NULL,
        payload TEXT NOT NULL,
        payload_digest TEXT NOT NULL)''',
    '''CREATE TABLE domain_event_outbox(
        event_id TEXT PRIMARY KEY REFERENCES domain_events(event_id),
        event_type TEXT NOT NULL,
        payload TEXT NOT NULL,
        payload_digest TEXT NOT NULL,
        created_at TEXT NOT NULL)''',
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
        held INTEGER NOT NULL CHECK(held IN (0,1)),
        revision INTEGER NOT NULL CHECK(revision>0),
        revoked INTEGER NOT NULL CHECK(revoked IN (0,1)),
        resource_json TEXT NOT NULL, resource_digest TEXT NOT NULL)''',
    'CREATE INDEX runtime_enrollment ON execution_runtime(enrollment_id)',
    'CREATE INDEX launches_state ON launch_attempts(state,execution_id)',
    '''CREATE UNIQUE INDEX one_live_launch ON launch_attempts(execution_id)
       WHERE state!='TERMINAL' ''',
    'CREATE INDEX leases_execution ON resource_leases(execution_id,held)',
    '''CREATE UNIQUE INDEX held_physical_resource ON resource_leases(
       json_extract(resource_json,'$.resource_type'), json_extract(resource_json,'$.resource_key'))
       WHERE held=1''',
    '''CREATE TRIGGER runtime_revision_guard BEFORE UPDATE ON execution_runtime
       WHEN NEW.execution_id!=OLD.execution_id OR NEW.authority_revision!=OLD.authority_revision+1
       BEGIN SELECT RAISE(ABORT,'Runtime authority revision must advance'); END''',
    '''CREATE TRIGGER lease_revision_guard BEFORE UPDATE ON resource_leases
       WHEN NEW.resource_key!=OLD.resource_key OR NEW.revision!=OLD.revision+1
       BEGIN SELECT RAISE(ABORT,'Lease revision must advance'); END''',
    '''CREATE TRIGGER lease_delete_guard BEFORE DELETE ON resource_leases
       BEGIN SELECT RAISE(ABORT,'Lease history cannot be deleted'); END''',
)
DDL_V2 += tuple(
    f'''CREATE TRIGGER immutable_{table}_{action.lower()} BEFORE {action} ON {table}
        BEGIN SELECT RAISE(ABORT,'Immutable runtime enrollment/profile'); END'''
    for table in ('identity_enrollments','execution_profiles') for action in ('UPDATE','DELETE')
)

DDL_V3 = (
    '''CREATE TABLE domain_event_deliveries(
        event_id TEXT NOT NULL REFERENCES domain_events(event_id),
        event_type TEXT NOT NULL,
        event_digest TEXT NOT NULL,
        consumer_name TEXT NOT NULL,
        status TEXT NOT NULL CHECK(status IN ('PENDING','RETRY','ACKNOWLEDGED','BLOCKED')),
        attempts INTEGER NOT NULL CHECK(attempts>=0),
        next_attempt_at TEXT NOT NULL,
        last_reason TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(event_id,consumer_name))''',
    'CREATE INDEX domain_event_delivery_pending ON domain_event_deliveries(status,next_attempt_at)',
)
DDL_V2 += tuple(
    f'''CREATE TRIGGER immutable_product_reviews_{action.lower()} BEFORE {action} ON product_reviews
        BEGIN SELECT RAISE(ABORT,'Product review records are immutable'); END'''
    for action in ('UPDATE', 'DELETE')
)
DDL_V2 += tuple(
    f'''CREATE TRIGGER immutable_domain_events_{action.lower()} BEFORE {action} ON domain_events
        BEGIN SELECT RAISE(ABORT,'Domain events are immutable'); END'''
    for action in ('UPDATE', 'DELETE')
)
DDL_V2 += tuple(
    f'''CREATE TRIGGER immutable_domain_event_outbox_{action.lower()} BEFORE {action} ON domain_event_outbox
        BEGIN SELECT RAISE(ABORT,'Domain event delivery obligations are immutable'); END'''
    for action in ('UPDATE', 'DELETE')
)


def _schema(db):
    # Include SQLite's autoindexes and sqlite_sequence with their exact definitions.
    # Optional ANALYZE statistics are recognized only by definitions generated by
    # this SQLite build, below; never exempt arbitrary names starting sqlite_.
    return {r[1]: tuple(r) for r in db.execute('SELECT type,name,tbl_name,sql FROM sqlite_master')}


def expected_schema(version=2, *, analyzed=False):
    db = sqlite3.connect(':memory:')
    try:
        for sql in (*DDL, *(DDL_V2 if version >= 2 else ()),
                    *(DDL_V3 if version >= 3 else ())):
            db.execute(sql)
        if analyzed:
            db.execute('ANALYZE')
        return _schema(db)
    finally:
        db.close()


def check_version(db):
    actual, source = _schema(db), expected_schema(1)
    if (actual.get('schema_versions') != source['schema_versions'] or
            db.execute('SELECT 1 FROM sqlite_temp_master LIMIT 1').fetchone()):
        raise RegistryBlocked('Untrusted version table or temporary schema.')
    versions = [r[0] for r in db.execute('SELECT version FROM schema_versions ORDER BY version')]
    if versions not in ([1], [1, 2], [1, 2, 3]):
        raise RegistryBlocked('Unsupported control schema version.')
    expected = expected_schema(versions[-1])
    optional = expected_schema(versions[-1], analyzed=True)
    optional = {k:v for k,v in optional.items() if k not in expected}
    if (any(actual.get(k) != v for k,v in expected.items()) or
            any(k not in expected and optional.get(k) != v for k,v in actual.items())):
        raise RegistryBlocked('Untrusted control schema inventory or definition.')
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


def migrate_v3(registry):
    """Add mutable per-consumer delivery state to an existing v2 registry."""
    from .records import PRODUCT_REVIEW_EVENT_CONSUMERS

    db = registry.db
    if db.in_transaction:
        raise RegistryBlocked('Migration requires an idle connection.')
    db.execute('BEGIN IMMEDIATE')
    try:
        if check_version(db) != 2:
            raise RegistryBlocked('Only v2 to v3 migration is supported.')
        if registry.verify(check_history=False)['status'] == 'BLOCKED':
            raise RegistryBlocked('Existing registry verification failed.')
        for sql in DDL_V3:
            db.execute(sql)
        now = utc_now()
        for row in db.execute('SELECT event_id,event_type,payload FROM domain_events'):
            event = json.loads(row['payload'])
            for consumer_name in PRODUCT_REVIEW_EVENT_CONSUMERS:
                db.execute(
                    '''INSERT INTO domain_event_deliveries(
                       event_id,event_type,event_digest,consumer_name,status,attempts,
                       next_attempt_at,last_reason,created_at,updated_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?)''',
                    (row['event_id'], row['event_type'], event['event_digest'], consumer_name,
                     'PENDING', 0, now, None, now, now),
                )
        db.execute('INSERT INTO schema_versions VALUES (3,?)', (now,))
        check_version(db)
        if (db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok'
                or db.execute('PRAGMA foreign_key_check').fetchall()):
            raise RegistryBlocked('Migration integrity failure.')
        db.commit()
    except BaseException:
        db.rollback()
        raise
