"""Bounded proposal-only protocol. Parsing never dispatches an operation."""
from dataclasses import dataclass
from enum import Enum
import socket
import struct
import time
from uuid import UUID

from .paths import normalize_path
from .serialization import canonical_json, parse_json
from .types import ValidationError

MAX_MESSAGE = 65536
MAX_DEPTH = 12


class Operation(str, Enum):
    READ_FILE = 'READ_FILE'
    LIST_DIRECTORY = 'LIST_DIRECTORY'
    SEARCH = 'SEARCH'
    WRITE_FILE = 'WRITE_FILE'
    APPLY_PATCH = 'APPLY_PATCH'
    RUN_TEST = 'RUN_TEST'
    RUN_COMMAND = 'RUN_COMMAND'
    GIT_STATUS = 'GIT_STATUS'
    GIT_DIFF = 'GIT_DIFF'
    GIT_COMMIT_LOCAL = 'GIT_COMMIT_LOCAL'


ARGUMENTS = {
    Operation.READ_FILE: ('path',), Operation.LIST_DIRECTORY: ('path',),
    Operation.SEARCH: ('path', 'query'), Operation.WRITE_FILE: ('path', 'content'),
    # Single-file patch only; production helper must reject embedded alternate paths.
    Operation.APPLY_PATCH: ('path', 'patch'), Operation.RUN_TEST: ('command_id',),
    Operation.RUN_COMMAND: ('command_id', 'argv'), Operation.GIT_STATUS: (),
    Operation.GIT_DIFF: (), Operation.GIT_COMMIT_LOCAL: ('message',),
}


def bounded_json(raw):
    if type(raw) is not bytes or len(raw) > MAX_MESSAGE:
        raise ValidationError('Invalid message size/type.')
    try:
        text = raw.decode('utf-8', errors='strict')
        # Bound nesting before recursive JSON parsing; brackets inside strings do not count.
        depth, quoted, escaped = 0, False, False
        for char in text:
            if quoted:
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
            elif char in '[{':
                depth += 1
                if depth > MAX_DEPTH:
                    raise ValidationError('Message nesting limit.')
            elif char in ']}':
                depth -= 1
        return parse_json(text)
    except UnicodeError:
        raise ValidationError('Invalid UTF-8.') from None


def uuid_value(value):
    try:
        if type(value) is not str or str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError):
        raise ValidationError('Invalid correlation identifier.') from None
    return value


@dataclass(frozen=True)
class ModelProposal:
    request_id: str
    execution_id: str
    operation: Operation
    arguments_json: str

    def __post_init__(self):
        uuid_value(self.request_id)
        uuid_value(self.execution_id)
        if type(self.operation) is not Operation:
            raise ValidationError('Unknown operation.')
        args = bounded_json(self.arguments_json.encode('utf-8'))
        if type(args) is not dict or set(args) != set(ARGUMENTS[self.operation]):
            raise ValidationError('Unexpected operation fields.')
        for key, value in args.items():
            if key == 'argv':
                if type(value) is not list or not 1 <= len(value) <= 64:
                    raise ValidationError('Argv array required.')
                if any(type(v) is not str or not v or '\0' in v or len(v) > 4096 for v in value):
                    raise ValidationError('Invalid argv.')
            elif type(value) is not str or '\0' in value or len(value) > 32768:
                raise ValidationError('Invalid operation argument.')
            if key == 'path':
                normalize_path(value)
        object.__setattr__(self, 'arguments_json', canonical_json(args))

    @classmethod
    def parse(cls, raw):
        data = bounded_json(raw)
        if type(data) is not dict or set(data) != {'version', 'request_id', 'execution_id', 'operation', 'arguments'}:
            raise ValidationError('Unexpected proposal fields.')
        if type(data['version']) is not int or data['version'] != 1:
            raise ValidationError('Unsupported proposal version.')
        try:
            op = Operation(data['operation'])
        except (ValueError, TypeError):
            raise ValidationError('Unknown operation.') from None
        return cls(data['request_id'], data['execution_id'], op, canonical_json(data['arguments']))

    @property
    def arguments(self):
        return parse_json(self.arguments_json)

    def to_dict(self):
        return dict(version=1, request_id=self.request_id, execution_id=self.execution_id,
                    operation=self.operation.value, arguments=self.arguments)


def encode_frame(proposal):
    if type(proposal) is not ModelProposal:
        raise ValidationError('Proposal required.')
    raw = canonical_json(proposal.to_dict()).encode('utf-8')
    if len(raw) > MAX_MESSAGE:
        raise ValidationError('Message too large.')
    return struct.pack('!I', len(raw)) + raw


def receive_frame(sock, *, timeout=5.0, clock=time.monotonic):
    if timeout <= 0 or timeout > 30:
        raise ValidationError('Invalid frame timeout.')
    deadline, old_timeout = clock() + timeout, sock.gettimeout()

    def exact(count):
        result = bytearray()
        while len(result) < count:
            remaining = deadline - clock()
            if remaining <= 0:
                raise ValidationError('Frame timeout.')
            sock.settimeout(remaining)
            block = sock.recv(count - len(result))
            if not block:
                raise ValidationError('Truncated frame.')
            result.extend(block)
        return bytes(result)

    try:
        size = struct.unpack('!I', exact(4))[0]
        if not 1 <= size <= MAX_MESSAGE:
            raise ValidationError('Invalid frame length.')
        return ModelProposal.parse(exact(size))
    except (socket.timeout, OSError):
        raise ValidationError('Frame transport failed.') from None
    finally:
        sock.settimeout(old_timeout)
