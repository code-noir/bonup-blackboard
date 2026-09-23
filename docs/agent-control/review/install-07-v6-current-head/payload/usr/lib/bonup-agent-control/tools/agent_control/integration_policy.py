"""Immutable Phase-I integration limits, separate from production FE/BE sizing.

These values describe required enforcement. They do not create tmpfs mounts,
enable quotas, provision identities or claim installed-host verification.
"""
from dataclasses import asdict, dataclass

from .serialization import digest
from .types import ValidationError

SUPERVISOR_CAPABILITIES = ('CAP_SETUID', 'CAP_SETGID', 'CAP_KILL', 'CAP_DAC_READ_SEARCH')


@dataclass(frozen=True)
class IntegrationPolicy:
    version: int = 1
    global_launches: int = 1
    memory_bytes: int = 256 * 1024 * 1024
    swap_bytes: int = 0
    cpu_quota_us: int = 100000
    cpu_period_us: int = 100000
    cpu_seconds: int = 30
    processes: int = 32
    open_fds: int = 256
    stdout_bytes: int = 65536
    stderr_bytes: int = 65536
    file_bytes: int = 16 * 1024 * 1024
    duration_seconds: int = 30
    core_bytes: int = 0
    tmp_bytes: int = 16 * 1024 * 1024
    home_bytes: int = 16 * 1024 * 1024
    workspace_bytes: int = 128 * 1024 * 1024
    workspace_inodes: int = 16384
    storage_mode: str = 'EPHEMERAL_TMPFS_WORKSPACE'
    durable_workspace: bool = False
    supervisor_mounts_workspace: bool = False

    def __post_init__(self):
        # Version 1 is one approved integration policy, not caller-controlled tuning.
        for name, field in self.__dataclass_fields__.items():
            value = getattr(self, name)
            if type(value) is not type(field.default) or value != field.default:
                raise ValidationError('Integration policy requires a new approved version to change.')

    @property
    def policy_digest(self):
        return digest(asdict(self))

    @classmethod
    def parse(cls, data):
        if type(data) is not dict or set(data) != set(cls.__dataclass_fields__):
            raise ValidationError('Closed complete resource profile required.')
        return cls(**data)

    def validate_record(self, record):
        if (type(record.timeout_seconds) not in (int,float) or
                not 0 < record.timeout_seconds <= self.duration_seconds or
                type(record.output_bytes) is not int or
                not 0 < record.output_bytes <= min(self.stdout_bytes, self.stderr_bytes)):
            raise ValidationError('Launch exceeds integration limits.')


def validate_capabilities(component, capabilities):
    expected = list(SUPERVISOR_CAPABILITIES) if component == 'supervisor' else []
    if component not in {'controller', 'supervisor', 'worker'} or capabilities != expected:
        raise ValidationError('Unapproved component capabilities.')
