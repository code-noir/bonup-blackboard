"""Closed synthetic integration catalog; no caller-controlled launch fields."""
from dataclasses import asdict, dataclass
from types import MappingProxyType
from uuid import NAMESPACE_URL, uuid5

from .confinement import ConfinementProfile
from .integration_policy import IntegrationPolicy
from .serialization import digest
from .types import AuthorityError

VERSION = 1
IDS = ('uid_gid_drop', 'empty_groups', 'capability_bounds', 'bwrap_apparmor',
       'pinned_mounts', 'confined_release_gate', 'namespace_installation_identity',
       'execution_start_proof', 'cgroup_limits', 'descendant_termination',
       'bounded_output', 'tmpfs_limits', 'socket_activation',
       'kernel_peer_authentication_operational_enrollment', 'watchdog',
       'controller_crash', 'supervisor_crash', 'reboot_reconciliation')
PROFILE = ConfinementProfile(readable_paths=('frontend/example.ts',))
PAYLOAD = '/usr/lib/bonup-agent-control/host_test_canary.py'
ROOT_ID = str(uuid5(NAMESPACE_URL, 'bonup:host-tests:fe01:workspace:v1'))


@dataclass(frozen=True)
class TestCase:
    test_id: str
    version: int
    worker: tuple
    argv: tuple
    roots: tuple
    profile_digest: str
    resource_digest: str
    evidence_class: str
    lifecycle: str
    service_interruption: bool
    reboot: bool

    def data(self):
        value = asdict(self)
        for name in ('worker', 'argv', 'roots'):
            value[name] = list(value[name])
        return value


CATALOG = MappingProxyType({name: TestCase(name, VERSION,
    ('FE-01', 'bonup-fe01', 3002, 3002),
    ('/usr/bin/python3', '-I', '-S', PAYLOAD, name), (ROOT_ID,),
    PROFILE.profile_digest, IntegrationPolicy().policy_digest,
    'M3_LIFECYCLE_' + name.upper(),
    'REBOOT' if name == 'reboot_reconciliation' else
    'SERVICE_RESTART' if name in ('controller_crash', 'supervisor_crash', 'watchdog') else
    'TERMINATE_DESCENDANTS' if name == 'descendant_termination' else 'EXIT_AND_CLEANUP',
    name in ('controller_crash', 'supervisor_crash', 'reboot_reconciliation', 'watchdog'),
    name == 'reboot_reconciliation') for name in IDS})
CATALOG_DIGEST = digest([CATALOG[name].data() for name in IDS])


def select(request):
    if type(request) is not dict or set(request) != {'test_id'}:
        raise AuthorityError('Only a closed test ID may be selected.')
    name = request['test_id']
    if type(name) is not str or name not in CATALOG:
        raise AuthorityError('Unknown host-test case.')
    return CATALOG[name]
