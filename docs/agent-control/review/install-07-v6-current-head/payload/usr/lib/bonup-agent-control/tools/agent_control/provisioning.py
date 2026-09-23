"""Read-only manifest generation/validation. No installer or host mutation commands."""
from pathlib import Path
import hashlib

from .serialization import canonical_json, digest
import re
from .types import ValidationError

NAMES=('bonup-agentctl','bonup-arch01','bonup-fe01','bonup-be01','bonup-qa01')
PREFIX='/usr/lib/bonup-agent-control'
ENTRYPOINT=PREFIX+'/supervisor'
MANIFEST='/etc/bonup-agent-control/approved-installation.json'
CAPABILITIES=['CAP_SETUID','CAP_SETGID','CAP_KILL']
# Explicit roots for the current installed-runtime dependency closure. The
# builder resolves their local imports from the selected Git tree; this is not
# itself an installed-file inventory.
RUNTIME_ENTRYPOINTS=('controller_entry','supervisor_entry','bootstrap_entry','gate_entry',
                     'installed_runtime','founder_genesis','founder_intake','founder_transport',
                     'prod_review_adapter','prod_artifact')

# Legacy v2/v3 attestation compatibility only. Current v4 candidates derive
# their inventory from the reviewed closure in installation_bundle.py.
LEGACY_MODULES=('__init__','__main__','authority','confinement','execution','gate_entry','identity',
                'lifecycle','model_client','paths','protocol','provisioning','publication','records',
                'registry','release_gate','runtime','runtime_schema','schema','serialization',
                'storage','supervisor','supervisor_linux','types')
MODULES=LEGACY_MODULES
POLICIES=('document-authority','policy','schemas')


def artifact_policy():
    """Exact bundle sources and immutable installed destinations, not shell commands."""
    entries=[('tools/agent_control/'+n+'.py',PREFIX+'/tools/agent_control/'+n+'.py','regular','0444') for n in MODULES]
    entries += [('docs/agent-control/'+n+'.json',PREFIX+'/docs/agent-control/'+n+'.json','regular','0444') for n in POLICIES]
    entries += [('tools/agent_control/gate_entry.py',PREFIX+'/gate_entry.py','regular','0444'),
                ('generated/supervisor',ENTRYPOINT,'executable','0555'),
                ('generated/bonup-agent-supervisor.service','/etc/systemd/system/bonup-agent-supervisor.service','unit','0444')]
    return [dict(source=s,destination=d,artifact_type=t,mode=m,owner='root',group='root') for s,d,t,m in entries]


def directory_policy():
    entries=[('/var/lib/bonup-agent-control','bonup-agentctl','bonup-agentctl','0700'),
             ('/srv/bonup-agent-work','root','root','0711'),
             ('/run/bonup-agent-supervisor','root','bonup-agentctl','0750')]
    entries += [('/srv/bonup-agent-work/'+n,n,n,'0700') for n in NAMES[1:]]
    entries += [(('/var/lib/bonup-agent-control/home' if n==NAMES[0] else '/srv/bonup-agent-work/'+n+'/home'),n,n,'0700') for n in NAMES]
    entries += [(p,'root','root','0755') for p in
                (PREFIX,PREFIX+'/tools',PREFIX+'/tools/agent_control',PREFIX+'/docs',PREFIX+'/docs/agent-control')]
    entries += [('/etc/bonup-agent-control','root','root','0700')]
    return [dict(path=p,owner=o,group=g,mode=m) for p,o,g,m in entries]


def service_policy():
    return dict(argv=[ENTRYPOINT,'--manifest',MANIFEST],working_directory='/',user='root',group='root',
                capabilities=CAPABILITIES.copy(),environment={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':'/nonexistent'},
                environment_files=[],no_new_privileges=True,kill_mode='control-group',restart='no',watchdog_seconds=10)


def rollback_policy(manifest):
    """Receipt identities are captured at installation, not guessed before creation.

    Removal is conditional on receipt device/inode/type/owner/hash and generation;
    nonempty directories or preexisting objects must be retained for manual review.
    """
    objects=[dict(kind='file',path=f['destination'],sha256=f['sha256']) for f in manifest['files']]
    objects += [dict(kind='directory',path=d['path']) for d in manifest['directories']]
    objects += [dict(kind='socket',path=manifest['socket']['path']),dict(kind='manifest',path=MANIFEST)]
    objects += [dict(kind='account',username=a['username'],uid=a['uid'],gid=a['gid']) for a in manifest['accounts']]
    return dict(version=1,generation=manifest['provisioning_generation'],verify_installation_receipt=True,
                created_objects_only=True,require_empty_cgroup=True,nonempty_directories='PRESERVE',
                recursive=False,objects=objects)


def _same(actual, expected, label):
    if canonical_json(actual)!=canonical_json(expected):
        raise ValidationError('Unsafe or incomplete '+label+'.')


def _keys(value, keys, label):
    if type(value) is not dict or set(value)!=set(keys):
        raise ValidationError('Unexpected '+label+' fields.')


def validate_approved_manifest(manifest, *, founder_uid=1000, founder_gid=1000):
    """Closed installation policy, not an installer or permission to activate.

    Founder UID/GID are trusted host-review inputs, never accepted from the manifest
    alone. Hash claims still require unprivileged bundle verification and installed
    file verification; this structural validator never reads artifact contents.
    """
    _keys(manifest,('version','approved','activation','provisioning_generation','founder_uid','founder_gid',
        'accounts','files','capabilities','capability_review','directories','socket','service',
        'workspace_storage_limit','service_template','cgroups','rollback'),'manifest')
    if type(manifest['version']) is not int or manifest['version']!=1 or manifest['approved'] is not True or manifest['activation'] is not False:
        raise ValidationError('Approved version 1 non-activation manifest required.')
    generation=manifest['provisioning_generation']
    if type(generation) is not int or generation<1:
        raise ValidationError('Explicit provisioning generation required.')
    for key,value in (('founder_uid',founder_uid),('founder_gid',founder_gid)):
        if type(value) is not int or value<=0 or type(manifest[key]) is not int or manifest[key]!=value:
            raise ValidationError('Founder identity differs from trusted host review.')
    accounts=manifest['accounts']
    if type(accounts) is not list or len(accounts)!=len(NAMES):
        raise ValidationError('Complete account inventory required.')
    seen=set()
    for name,a in zip(NAMES,accounts):
        if type(a) is not dict:
            raise ValidationError('Invalid account.')
        uid,gid=a.get('uid'),a.get('gid')
        if (any(type(v) is not int or v<1001 or v>=2**31 or v in (founder_uid,founder_gid) for v in (uid,gid)) or
                uid!=gid or uid in seen):
            raise ValidationError('Distinct private UID/GID pairs required.')
        seen.add(uid)
        _same(a,dict(username=name,uid=uid,gid=gid,primary_group=name,supplementary_groups=[],
            shell='/usr/sbin/nologin',password='LOCKED',home=('/var/lib/bonup-agent-control/home' if name==NAMES[0]
                else '/srv/bonup-agent-work/'+name+'/home'),home_mode='0700',umask='0077',ssh_keys=[],
            provisioning_generation=generation),'account policy')
    files=manifest['files']
    expected=artifact_policy()
    if type(files) is not list or len(files)!=len(expected):
        raise ValidationError('Complete installed artifact inventory required.')
    # Compare by destination, rejecting duplicate destinations and arbitrary source paths.
    by_path={}
    for f in files:
        _keys(f,(*expected[0].keys(),'sha256'),'artifact')
        if type(f['sha256']) is not str or not re.fullmatch('[0-9a-f]{64}',f['sha256']) or f['sha256']=='0'*64:
            raise ValidationError('Resolved artifact SHA256 required.')
        if type(f['destination']) is not str or f['destination'] in by_path:
            raise ValidationError('Invalid or duplicate artifact destination.')
        by_path[f['destination']]=f
    for policy in expected:
        actual=by_path.get(policy['destination'])
        if actual is None:
            raise ValidationError('Missing required installed artifact.')
        _same({k:v for k,v in actual.items() if k!='sha256'},policy,'artifact policy')
    _same(manifest['capabilities'],CAPABILITIES,'capabilities')
    _same(manifest['capability_review'],
          'CAP_DAC_READ_SEARCH requires explicit review if supervisor opens worker-owned 0700 roots.','capability review')
    _same(manifest['directories'],directory_policy(),'directory policy')
    _same(manifest['socket'],dict(path='/run/bonup-agent-supervisor/control.sock',owner='root',group=NAMES[0],mode='0660'),'socket')
    _same(manifest['service'],service_policy(),'service')
    _same(manifest['service_template'],'bonup-agent-supervisor.service.in','service template')
    _same(manifest['cgroups'],dict(delegate=['cpu','memory','pids'],manager_subgroup='supervisor',launch_prefix='launch-',swap_max=0),'cgroups')
    storage=manifest['workspace_storage_limit']
    roots=['/var/lib/bonup-agent-control',*('/srv/bonup-agent-work/'+n for n in NAMES[1:])]
    if type(storage) is not list or len(storage)!=len(roots):
        raise ValidationError('Complete finite storage quotas required.')
    for row,path in zip(storage,roots):
        _keys(row,('path','bytes','inodes','enforcement'),'storage')
        if (row['path']!=path or row['enforcement']!='filesystem-quota' or
                type(row['bytes']) is not int or not 1048576<=row['bytes']<=2**40 or
                type(row['inodes']) is not int or not 1<=row['inodes']<=1000000):
            raise ValidationError('Unsafe or unresolved storage policy.')
    _same(manifest['rollback'],rollback_policy(manifest),'rollback')
    return digest(manifest)


def review_manifest(repository):
    """Hash agent-control Python/policy files; never inspect secrets or application data."""
    root=Path(repository)
    files=[]
    for path in sorted((root/'tools/agent_control').glob('*.py')):
        if path.is_symlink():
            raise ValidationError('Symlinked artifact rejected.')
        destination='/usr/lib/bonup-agent-control/tools/agent_control/'+path.name
        files.append(dict(source=str(path.relative_to(root)),destination=destination,
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest(),owner='root',group='root',mode='0444',artifact_type='regular'))
        if path.name=='gate_entry.py':
            files.append(dict(source=str(path.relative_to(root)),destination='/usr/lib/bonup-agent-control/gate_entry.py',
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest(),owner='root',group='root',mode='0444',artifact_type='regular'))
    for path in sorted((root/'docs/agent-control').glob('*.json')):
        if path.is_symlink():
            raise ValidationError('Symlinked policy rejected.')
        files.append(dict(source=str(path.relative_to(root)),destination='/usr/lib/bonup-agent-control/docs/agent-control/'+path.name,
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest(),owner='root',group='root',mode='0444',artifact_type='regular'))
    if not files:
        raise ValidationError('Agent-control artifacts missing.')
    return dict(version=1,approved=False,provisioning_generation=None,founder_uid=1000,founder_gid=1000,
        accounts=[dict(username=n,uid=None,gid=None,primary_group=n,supplementary_groups=[],
            shell='/usr/sbin/nologin',password='LOCKED',home=('/var/lib/bonup-agent-control/home' if n=='bonup-agentctl'
                else '/srv/bonup-agent-work/'+n+'/home'),
            home_mode='0700',umask='0077',ssh_keys=[],provisioning_generation=None) for n in NAMES],
        files=files,capabilities=['CAP_SETUID','CAP_SETGID','CAP_KILL'],
        capability_review='CAP_DAC_READ_SEARCH requires explicit review if supervisor opens worker-owned 0700 roots.',
        directories=directory_policy(),
        socket=dict(path='/run/bonup-agent-supervisor/control.sock',owner='root',group='bonup-agentctl',mode='0660'),
        service=None,workspace_storage_limit=None,rollback=None,service_template='bonup-agent-supervisor.service.in',
        cgroups=dict(delegate=['cpu','memory','pids'],manager_subgroup='supervisor',launch_prefix='launch-',swap_max=0),
        activation=False)
