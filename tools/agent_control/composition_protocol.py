"""Nonblocking, closed controller/supervisor wire vocabulary.

This protocol carries logical IDs and authority/evidence digests, never privileged
launch parameters. Authentication belongs to the enrolled Unix transport, not JSON.
"""
from dataclasses import dataclass
import struct

from .identity import PeerIdentity, ProcessIdentity
from .protocol import bounded_json, uuid_value
from .schema import timestamp, valid_format
from .serialization import canonical_json
from .types import AuthorityError, ValidationError

LIMIT = 4096
FIELDS = {
    'PREPARE_LAUNCH': {'plan_id', 'execution_id', 'authorization_digest',
                       'workspace_digest', 'plan_digest', 'expires_at', 'elapsed_deadline_ns'},
    'PREPARED_EVIDENCE': {'authorization_digest', 'workspace_digest', 'process'},
    'RELEASE_LAUNCH': {'authorization_digest', 'release_id'},
    'RUNNING_EVIDENCE': {'authorization_digest', 'release_id', 'process'},
    'STOP_LAUNCH': {'reason'},
    'CLEANUP_EVIDENCE': {'empty', 'exit_code'},
    'HEARTBEAT': {'ready'},
    'RECONCILE': set(),
    'OPEN_ADMISSION': {'session_digest'},
    'ADMISSION_EVIDENCE': {'session_digest'},
    'STATUS_LAUNCH': set(),
    'STATUS_EVIDENCE': {'exited', 'process', 'output'},
}
BASE = {'version', 'action', 'request_id', 'launch_id', 'generation', 'boot_id', 'data'}


def validate(message):
    if type(message) is not dict or set(message) != BASE:
        raise ValidationError('Unexpected composition message fields.')
    if type(message['version']) is not int or message['version'] not in (1, 2, 3):
        raise ValidationError('Unsupported composition protocol.')
    action, data = message['action'], message['data']
    if type(action) is not str or action not in FIELDS:
        raise ValidationError('Unknown composition action.')
    expected = FIELDS[action]
    if message['version'] == 3:
        if action not in ('STATUS_LAUNCH', 'STATUS_EVIDENCE'):
            raise ValidationError('Version 3 extends status evidence only.')
        if action == 'STATUS_EVIDENCE':
            expected = expected | {'lifecycle', 'service_events'}
    if message['version'] == 2:
        expected = expected | {'PREPARE_LAUNCH':{'root_id','filesystem_policy_digest'},
            'PREPARED_EVIDENCE':{'filesystem_evidence'},
            'RELEASE_LAUNCH':{'filesystem_evidence_digest'}}.get(action,set())
    if type(data) is not dict or set(data) != expected:
        raise ValidationError('Unexpected action fields.')
    for name in ('request_id', 'launch_id', 'generation', 'boot_id'):
        uuid_value(message[name])
    for name, value in data.items():
        if name == 'service_events':
            if type(value) is not list or len(value)>4:
                raise ValidationError('Bounded service events required.')
            for row in value:
                if (type(row) is not dict or set(row)!={'unit','reason','cursor','boot_id'} or
                        row['unit'] not in ('bonup-agent-controller.service','bonup-agent-supervisor.service') or
                        row['reason'] not in ('WATCHDOG','PROCESS_KILLED') or
                        type(row['cursor']) is not str or not 1<=len(row['cursor'])<=512):
                    raise ValidationError('Invalid service observation.')
                uuid_value(row['boot_id'])
        elif name == 'lifecycle':
            if (type(value) is not dict or set(value) != {'resources_verified','exec_confirmed','cleanup_confirmed'} or
                    any(type(v) is not bool for v in value.values())):
                raise ValidationError('Closed kernel lifecycle facts required.')
        elif name in {'plan_id', 'execution_id', 'release_id','root_id'}:
            uuid_value(value)
        elif name.endswith('_digest'):
            if not valid_format('sha256', value):
                raise ValidationError('Invalid evidence digest.')
        elif name == 'expires_at':
            timestamp(value)
        elif name == 'elapsed_deadline_ns':
            if type(value) is not int or not 0 < value < 2**63:
                raise ValidationError('Invalid absolute boot-time deadline.')
        elif name == 'process':
            if (type(value) is not dict or set(value) != {'boot_id', 'pid', 'start_ticks'} or
                    value['boot_id'] != message['boot_id'] or
                    type(value['pid']) is not int or value['pid'] <= 0 or
                    type(value['start_ticks']) is not int or value['start_ticks'] < 0):
                raise ValidationError('Invalid process evidence.')
        elif name == 'filesystem_evidence':
            from .filesystem_evidence import validate_evidence
            validate_evidence(value)
        elif name == 'output':
            if type(value) is not dict or set(value) != {'stdout','stderr'}:
                raise ValidationError('Closed output evidence required.')
            for item in value.values():
                if (type(item) is not dict or set(item) != {'retained','truncated'} or
                        type(item['retained']) is not int or not 0 <= item['retained'] <= 65536 or
                        type(item['truncated']) is not bool):
                    raise ValidationError('Bounded output evidence required.')
        elif name in {'empty', 'ready', 'exited'}:
            if type(value) is not bool:
                raise ValidationError('Boolean evidence required.')
        elif name == 'exit_code':
            if value is not None and (type(value) is not int or not -255 <= value <= 255):
                raise ValidationError('Invalid exit evidence.')
        elif name == 'reason':
            if value not in {'DENIED', 'SETUP_FAILED', 'EXITED', 'TIMEOUT',
                             'REVOKED', 'CANCELLED', 'INTERRUPTED'}:
                raise ValidationError('Invalid stop reason.')
    if len(canonical_json(message).encode()) > LIMIT:
        raise ValidationError('Composition frame too large.')
    return message


def frame(message):
    raw = canonical_json(validate(message)).encode()
    return struct.pack('!I', len(raw)) + raw


class FrameReader:
    """Incremental framing: the caller's event loop never waits for a slow sender.

    One request per channel; EOF is mandatory before dispatch. A partial frame,
    second frame, timeout or disconnect consumes the reader without dispatching.
    """
    def __init__(self, *, now, timeout=1.0):
        if type(timeout) not in (int, float) or not 0 < timeout <= 1:
            raise ValidationError('Bounded IPC timeout required.')
        self.deadline = now + timeout
        self.buffer = bytearray()
        self.used = False

    def feed(self, chunk, *, now, eof=False):
        if self.used:
            raise AuthorityError('Consumed IPC channel.')
        try:
            if now >= self.deadline:
                raise AuthorityError('IPC deadline expired.')
            if type(chunk) is not bytes or len(self.buffer) + len(chunk) > LIMIT + 4:
                raise ValidationError('IPC size limit.')
            self.buffer.extend(chunk)
            size = None
            if len(self.buffer) >= 4:
                size = struct.unpack('!I', self.buffer[:4])[0]
                if not 1 <= size <= LIMIT or len(self.buffer) > size + 4:
                    raise ValidationError('Invalid or extra IPC frame.')
            if eof:
                self.used = True
                if size is None or len(self.buffer) != size + 4:
                    raise ValidationError('Incomplete IPC frame.')
                return validate(bounded_json(bytes(self.buffer[4:])))
            return None
        except BaseException:
            self.used = True
            raise


@dataclass(frozen=True)
class EnrolledChannel:
    peer: PeerIdentity
    process: ProcessIdentity
    generation: str

    def verify(self, sock, *, generation, process_reader=None):
        uuid_value(self.generation)
        if (type(self.peer) is not PeerIdentity or type(self.process) is not ProcessIdentity or
                self.peer.pid != self.process.pid or generation != self.generation or
                PeerIdentity.from_socket(sock) != self.peer):
            raise AuthorityError('Unenrolled transport peer.')
        self.process.verify(process_reader)
