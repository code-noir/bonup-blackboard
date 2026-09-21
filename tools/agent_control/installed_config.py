"""Closed runtime activation attestation; Block 4 renders these installed inputs.

This module does not generate approvals, write configuration, or read credentials.
Runtime generation/peer enrollment is root-approved state, not request metadata.
"""
from dataclasses import fields
import os
from pathlib import Path
import stat

from .identity import WorkerIdentity
from .integration_policy import IntegrationPolicy
from .protocol import bounded_json,uuid_value
from .schema import valid_format
from .serialization import digest, canonical_json
from .service_runtime import keys
from .types import AuthorityError,ValidationError,Role

PREFIX='/usr/lib/bonup-agent-control'
MANIFEST='/etc/bonup-agent-control/approved-installation.json'
IDENTITIES='/etc/bonup-agent-control/identity-map.json'


def read_installed(path):
    allowed={MANIFEST,IDENTITIES,'/etc/bonup-agent-control/controller.json',
        '/etc/bonup-agent-control/event-delivery.json',
        '/etc/bonup-agent-control/founder-root-binding.json',
        '/etc/bonup-agent-control/founder-genesis-evidence.json',
        '/etc/bonup-agent-control/runtime-authority.json',
        '/etc/bonup-agent-control/host-test-roots.json',
        '/etc/bonup-agent-control/supervisor.json',
        '/etc/bonup-agent-control/founder-policy.json',
        '/etc/bonup-agent-control/authority-receipt.json',
        '/etc/bonup-agent-control/installation-candidate.json',
        '/etc/bonup-agent-control/installation-approved.json',
        '/etc/bonup-agent-control/installation-receipt.json','/etc/bonup-agent-control/host-tests.json'}
    if path not in allowed:raise AuthorityError('Unknown installed configuration.')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        parts=Path(path).parts[1:]
        for i,part in enumerate(parts):
            child=os.open(part,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK|
                (os.O_DIRECTORY if i<len(parts)-1 else 0),dir_fd=fd)
            os.close(fd);fd=child
            info=os.fstat(fd)
            if info.st_uid!=0 or info.st_mode&0o022:
                raise AuthorityError('Mutable installed configuration.')
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>65536:
            raise AuthorityError('Invalid configuration object.')
        raw=os.read(fd,65537)
        if len(raw)>65536:raise ValidationError('Configuration size limit.')
        return bounded_json(raw)
    finally:os.close(fd)


def validate_activation(manifest, identities, configuration, *, component, receipt=None, host_tests=None):
    if type(manifest) is dict and manifest.get('version') in (4, 5):
        from .installation_bundle import (validate_manifest, runtime_permission, configurations,
                                          identities as expected_identities, same)
        validate_manifest(manifest)
        if component not in ('controller','supervisor'):
            raise AuthorityError('Unknown installed component.')
        same(identities,expected_identities(),'installed identity map')
        same(configuration,configurations()[component],'static installed configuration')
        runtime_permission(manifest,receipt,host_tests)
        return digest(manifest)
    keys(manifest,('version','approved','activation','provisioning_generation','source_commit',
        'bundle_digest','identity_map_digest','configuration_digests','files','resource_digest'))
    if (type(manifest['version']) is not int or manifest['version'] not in (2, 3) or
            manifest['approved'] is not True or manifest['activation'] is not True or
            type(manifest['provisioning_generation']) is not int or manifest['provisioning_generation']!=1 or
            not valid_format('git-oid',manifest['source_commit']) or manifest['resource_digest']!=IntegrationPolicy().policy_digest):
        raise AuthorityError('Explicit approved runtime activation required.')
    if manifest['bundle_digest']!=digest({k:v for k,v in manifest.items() if k!='bundle_digest'}):
        raise AuthorityError('Runtime attestation digest mismatch.')
    keys(manifest['configuration_digests'],('controller','supervisor'))
    if (component not in ('controller','supervisor') or
            any(not valid_format('sha256',v) for v in manifest['configuration_digests'].values()) or
            manifest['identity_map_digest']!=digest(identities) or
            manifest['configuration_digests'][component]!=digest(configuration)):
        raise AuthorityError('Installed configuration digest mismatch.')
    keys(identities,('version','provisioning_generation','accounts'))
    expected=[dict(username=n,uid=3000+i,gid=3000+i,groups=[],shell='/usr/sbin/nologin',password='LOCKED',ssh=False)
        for i,n in enumerate(('bonup-agentctl','bonup-arch01','bonup-fe01','bonup-be01','bonup-qa01'))]
    if canonical_json(identities)!=canonical_json({'version':1,'provisioning_generation':1,'accounts':expected}):
        raise AuthorityError('Unexpected installed identities.')
    files=manifest['files']
    if type(files) is not dict or not files or len(files)>64:
        raise ValidationError('Closed installed artifact map required.')
    for path,value in files.items():
        if (type(path) is not str or not path.startswith(PREFIX+'/') or
                str(Path(path))!=path or '..' in Path(path).parts or not valid_format('sha256',value)):
            raise ValidationError('Invalid installed artifact claim.')
    from .provisioning import MODULES, POLICIES
    additions=('bootstrap_entry','composition','composition_protocol','controller_entry',
        'filesystem_evidence','installed_config','installed_transport','installed_runtime',
        'integration_policy','resource_supervision','service_runtime','supervisor_entry')
    required={PREFIX+'/tools/agent_control/'+n+'.py' for n in (*MODULES,*additions)}
    if manifest['version'] == 3:
        required.add(PREFIX+'/tools/agent_control/operational_enrollment.py')
        from .operational_enrollment import installation_pair
        installation_pair(configuration, manifest, component)
    required.update(PREFIX+'/docs/agent-control/'+n+'.json' for n in POLICIES)
    required.update(PREFIX+'/'+n for n in ('bootstrap_entry.py','gate_entry.py','controller','supervisor'))
    if set(files)!=required:
        raise AuthorityError('Incomplete or unexpected installed dependency inventory.')
    return digest(manifest)


def parse_record(data):
    from .execution import LaunchRecord
    from .protocol import Operation
    keys(data,[f.name for f in fields(LaunchRecord)])
    row=dict(data);worker=row['worker']
    keys(worker,('agent_id','role','username','uid','gid'))
    row['worker']=WorkerIdentity(**dict(worker,role=Role(worker['role'])))
    row['operation']=Operation(row['operation'])
    if any(type(row[k]) is not list for k in ('argv','environment','inherited_fds')):
        raise ValidationError('Closed launch arrays required.')
    row['inherited_fds']=tuple(row['inherited_fds'])
    row['argv']=tuple(row['argv']);row['environment']=tuple(tuple(p) for p in row['environment'])
    record=LaunchRecord(**row)
    IntegrationPolicy().validate_record(record)
    return record
