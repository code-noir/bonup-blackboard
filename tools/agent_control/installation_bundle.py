"""Closed, deterministic review bundle and future installation contracts.

No installer side effects: this module never provisions or starts anything.
The manifest hashes its payload and policy; the detached bundle inventory hashes
that manifest's final bytes, avoiding a circular self-hash.
"""
import ast
from dataclasses import asdict
import hashlib
import os
from pathlib import Path
import stat
import sys

from .integration_policy import IntegrationPolicy, SUPERVISOR_CAPABILITIES
from .operational_enrollment import installation_spec
from .provisioning import MODULES, POLICIES, NAMES
from .schema import valid_format, timestamp
from .serialization import canonical_json, digest, parse_json
from .types import AuthorityError, ValidationError

PREFIX = '/usr/lib/bonup-agent-control'
ETC = '/etc/bonup-agent-control'
MANIFEST = ETC + '/approved-installation.json'
SOURCE_COMMIT = 'be8270ea2c067612843504d5835aee6cc772f940'
ADDITIONS = ('bootstrap_entry','composition','composition_protocol','controller_entry',
    'filesystem_evidence','installed_config','installed_transport','installed_runtime',
    'integration_policy','resource_supervision','service_runtime','supervisor_entry',
    'operational_enrollment','installation_bundle','exec_start')
PRODUCTION_MODULES = tuple(sorted(set(MODULES + ADDITIONS)))
HOST_TESTS = ('uid_gid_drop','empty_groups','capability_bounds','bwrap_apparmor',
    'pinned_mounts','confined_release_gate','cgroup_limits','descendant_kill','bounded_output',
    'tmpfs_limits','socket_activation','kernel_peer_enrollment','watchdog','controller_crash',
    'supervisor_crash','reboot_reconciliation','namespace_installation','exec_start_event')


def same(actual, expected, label):
    if canonical_json(actual) != canonical_json(expected):
        raise ValidationError('Unsafe or incomplete '+label+'.')


def keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise ValidationError('Unexpected bundle fields.')


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value):
    return (canonical_json(value)+'\n').encode()


def identities():
    return dict(version=2, provisioning_generation=1, accounts=[dict(
        username=name,uid=3000+i,gid=3000+i,primary_group=name,provisioning_generation=1,
        password='LOCKED',shell='/usr/sbin/nologin',home=('/var/lib/bonup-agent-control/home'
        if i==0 else '/srv/bonup-agent-work/'+name+'/home'),home_mode='0700',umask='0077',
        supplementary_groups=[],ssh_keys=[]) for i,name in enumerate(NAMES)])


def configurations():
    return {
        'controller':dict(version=2,service=installation_spec('controller'),founder_uid=1000,
                          founder=None,proposal=None,executions=[]),
        'supervisor':dict(version=2,service=installation_spec('supervisor'),roots=[],plans=[]),
    }


def directories():
    result=[]
    def add(path,owner,group,mode,purpose,lifecycle='persistent',rollback='REMOVE_IF_EMPTY_VERIFIED'):
        result.append(dict(path=path,owner=owner,group=group,mode=mode,purpose=purpose,
            readers=[owner] if mode=='0700' else [owner,group] if mode in ('0710','0750') else ['all'],
            writers=[owner],lifecycle=lifecycle,rollback=rollback))
    for suffix,purpose in (('', 'controller registry'),('/home','controller private home'),
            ('/runtime','durable runtime evidence'),('/history.git','audit history')):
        add('/var/lib/bonup-agent-control'+suffix,NAMES[0],NAMES[0],'0700',purpose,rollback='PRESERVE_FOR_INVESTIGATION')
    add('/run/bonup-agent-control',NAMES[0],'bonup','0710','controller endpoints','runtime')
    add('/run/bonup-agent-supervisor','root',NAMES[0],'0750','supervisor endpoint','runtime')
    add('/srv/bonup-agent-work','root','root','0711','worker parent')
    for name in NAMES[1:]:
        add('/srv/bonup-agent-work/'+name,name,name,'0700','private worker root',rollback='QUARANTINE_NONEMPTY')
        for suffix in ('home','tmp','workspace'):
            add('/srv/bonup-agent-work/'+name+'/'+suffix,name,name,'0700',suffix,'ephemeral','QUARANTINE_NONEMPTY')
    add(ETC,'root',NAMES[0],'0750','immutable configuration')
    for suffix in ('','/tools','/tools/agent_control','/docs','/docs/agent-control'):
        add(PREFIX+suffix,'root','root','0755','immutable installed code/policy')
    return result


def sockets():
    return [dict(path=path,owner=owner,group=group,mode=mode,allowed_installation_identity=identity,
        operational_enrollment_required=True,protocol=protocol,replay='DENY_REQUIRE_FRESH_ENROLLMENT',
        lifecycle_owner=unit) for path,owner,group,mode,identity,protocol,unit in (
        ('/run/bonup-agent-control/founder.sock',NAMES[0],'bonup','0660',
         'FOUNDER_UID_1000_SEPARATE_HUMAN_ENROLLMENT','founder-control-v1','bonup-agent-founder.socket'),
        ('/run/bonup-agent-control/proposals.sock',NAMES[0],NAMES[0],'0600',
         'NONE_INTAKE_DISABLED','proposal-v1','bonup-agent-proposals.socket'),
        ('/run/bonup-agent-supervisor/control.sock','root',NAMES[0],'0660',
         'CONTROLLER_UID_GID_3000','operational-enrollment-v1+composition-v2','bonup-agent-supervisor.socket'))]


def services():
    return {name:dict(argv=[PREFIX+'/'+name],user=NAMES[0] if name=='controller' else 'root',
        group=NAMES[0] if name=='controller' else 'root',working_directory='/',umask='0077',
        capabilities=[] if name=='controller' else list(SUPERVISOR_CAPABILITIES),ambient_capabilities=[],
        environment=dict(PATH='/usr/bin:/bin',LANG='C.UTF-8',LC_ALL='C.UTF-8',HOME='/nonexistent'),
        environment_files=[],no_new_privileges=True,protect_system='strict',protect_home=True,
        private_tmp=True,private_devices='HOST_TEST_REQUIRED',restart='no',type='notify',
        watchdog_seconds=10,kill_mode='control-group',core_bytes=0,open_fds=256,
        writable_paths=['/var/lib/bonup-agent-control','/run/bonup-agent-control'] if name=='controller' else
            ['/srv/bonup-agent-work','/run/bonup-agent-supervisor'],
        inaccessible_paths=['/srv/bonup-agent-work'] if name=='controller' else
            ['/var/lib/bonup-agent-control','/run/bonup-agent-control'],
        delegate=[] if name=='controller' else ['cpu','memory','pids'],
        delegate_subgroup=None if name=='controller' else 'supervisor') for name in ('controller','supervisor')}


def units():
    result={}
    for name,p in services().items():
        lines=['[Unit]','Description=bonUP agent '+name,'After=local-fs.target',
            'ConditionPathExists='+MANIFEST,'[Service]','Type=notify','User='+p['user'],'Group='+p['group'],
            'ExecStart='+p['argv'][0],'WorkingDirectory=/','UMask=0077',
            'Environment=PATH=/usr/bin:/bin LANG=C.UTF-8 LC_ALL=C.UTF-8 HOME=/nonexistent',
            'CapabilityBoundingSet='+' '.join(p['capabilities']),'AmbientCapabilities=',
            'NoNewPrivileges=yes','ProtectSystem=strict','ProtectHome=yes','PrivateTmp=yes',
            '# PrivateDevices compatibility: HOST_TEST_REQUIRED',
            'ReadWritePaths='+' '.join(p['writable_paths']),'InaccessiblePaths='+' '.join(p['inaccessible_paths']),
            'KillMode=control-group','KillSignal=SIGKILL','SendSIGKILL=yes','TimeoutStopSec=5s',
            'WatchdogSec=10s','WatchdogSignal=SIGKILL','NotifyAccess=main','Restart=no','LimitCORE=0','LimitNOFILE=256']
        if name=='supervisor':lines+=['Delegate=cpu memory pids','DelegateSubgroup=supervisor','Sockets=bonup-agent-supervisor.socket']
        else:lines+=['Sockets=bonup-agent-founder.socket bonup-agent-proposals.socket']
        result['bonup-agent-'+name+'.service']='\n'.join(lines)+'\n'
    for row in sockets():
        fdname={'bonup-agent-founder.socket':'founder','bonup-agent-proposals.socket':'proposals',
                'bonup-agent-supervisor.socket':'supervisor'}[row['lifecycle_owner']]
        service='supervisor' if fdname=='supervisor' else 'controller'
        result[row['lifecycle_owner']]='\n'.join(['[Unit]','Description=bonUP '+fdname+' endpoint',
            '[Socket]','ListenStream='+row['path'],'SocketUser='+row['owner'],'SocketGroup='+row['group'],
            'SocketMode='+row['mode'],'DirectoryMode=0700','Accept=no','RemoveOnStop=yes','PassCredentials=yes',
            'FileDescriptorName='+fdname,'Service=bonup-agent-'+service+'.service'])+'\n'
    return result


def wrapper(component):
    if component not in ('controller','supervisor'):raise ValidationError('Unknown wrapper.')
    paths=[a['destination'] for a in artifact_spec() if a['destination'].startswith(PREFIX+'/')]
    template='''#!/usr/bin/python3 -I
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
root = Path('/usr/lib/bonup-agent-control')
here = root / 'COMPONENT'
if Path(__file__) != here or len(sys.argv) != 1 or not sys.flags.isolated or not sys.flags.no_user_site:
    raise SystemExit('Immutable isolated installation required')
def read_verified(path):
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    try:
        parts = Path(path).parts[1:]
        for index, part in enumerate(parts):
            child = os.open(part, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK |
                (os.O_DIRECTORY if index < len(parts)-1 else 0), dir_fd=fd)
            os.close(fd)
            fd = child
            info = os.fstat(fd)
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise SystemExit('Mutable installed object')
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1048576:
            raise SystemExit('Unsafe installed object')
        with os.fdopen(os.dup(fd), 'rb') as stream:
            raw = stream.read(1048577)
        if len(raw) != info.st_size or any(getattr(os.fstat(fd), k) != getattr(info, k)
            for k in ('st_dev','st_ino','st_mode','st_nlink','st_uid','st_gid','st_size','st_mtime_ns','st_ctime_ns')):
            raise SystemExit('Installed object changed')
        return raw
    finally:
        os.close(fd)
def unique_pairs(pairs):
    result = {}
    for key,value in pairs:
        if key in result:
            raise SystemExit('Duplicate manifest key')
        result[key] = value
    return result
manifest = json.loads(read_verified('/etc/bonup-agent-control/approved-installation.json'), object_pairs_hook=unique_pairs)
expected_paths = PATH_INVENTORY
if type(manifest.get('files')) is not dict or set(manifest['files']) != set(expected_paths):
    raise SystemExit('Incomplete installed dependency inventory')
for path in expected_paths:
    if hashlib.sha256(read_verified(path)).hexdigest() != manifest['files'][path]:
        raise SystemExit('Installed artifact digest mismatch')
os.chdir('/')
sys.path.insert(0, str(root))
from tools.agent_control.COMPONENT_entry import main
main()
'''
    return template.replace('COMPONENT',component).replace('PATH_INVENTORY',repr(paths)).encode()


def policy_sections():
    return dict(identity_map=identities(),directories=directories(),sockets=sockets(),services=services(),
        capabilities=dict(supervisor=list(SUPERVISOR_CAPABILITIES),controller=[],worker=[],ambient=[]),
        resource_profile=asdict(IntegrationPolicy()),
        storage=dict(mode='EPHEMERAL_TMPFS_WORKSPACE',host_provisioned=True,ephemeral=True,durable=False,
            worker_resize=False,supervisor_dynamic_mount=False,workspace_bytes=134217728,workspace_inodes=16384,
            home_bytes=16777216,tmp_bytes=16777216,enforcement='HOST_TEST_REQUIRED',
            host_mount_options=['nodev','nosuid'],quota_changes=False),
        operational_enrollment=dict(version=1,initial_admission='ENROLLMENT_CLOSED',
            kernel_peer=True,service_cgroup_required=True,challenge_required=True,reconciliation_required=True,
            grant_authority=False,human_model_intake='DISABLED',execution_catalog='EMPTY'),
        controller_state=dict(path='/var/lib/bonup-agent-control/control.sqlite3',
            history='/var/lib/bonup-agent-control/history.git',owner=NAMES[0],group=NAMES[0],mode='0600',
            schema_version=2,initialization='EXPLICIT_CONTROLLER_IDENTITY_INSTALLED_REGISTRY_INITIALIZE_THEN_MIGRATE_V2',
            before_integration_service_start=True,automatic_startup_initialization=False,
            existing_state='DENY_REINITIALIZATION',initial_agents='DISABLED',initial_executions='EMPTY',
            initialize_operation_id='FRESH_INSTALLER_RECORDED_UUID',rollback='PRESERVE_FOR_INVESTIGATION'),
        os_dependencies=dict(platform='Ubuntu 24.04',python_minimum=[3,12],python='/usr/bin/python3',
            bwrap='/usr/bin/bwrap',bwrap_version='0.9.0',systemd_minimum=255,git='/usr/bin/git',
            cgroup_version=2,cgroup_kill=True,tmpfs=True),
        host_preflight=dict(source_commit=True,source_artifact_hashes=True,founder_uid_gid=[1000,1000],
            unused_uids=list(range(3000,3005)),unused_gids=list(range(3000,3005)),unused_accounts=list(NAMES),
            target_conflicts='DENY',previous_installation='DENY',apparmor=['bwrap (enforce)','unpriv_bwrap (enforce)'],
            sysctls={'kernel.unprivileged_userns_clone':1,'kernel.apparmor_restrict_unprivileged_userns':1},
            minimum_available_disk_bytes=1073741824,minimum_available_memory_bytes=1073741824,
            verify_os_dependencies=True,read_only=True),
        post_installation_evidence=[dict(path=ETC+'/'+n+'.json',owner='root',group=NAMES[0],mode='0440',
            role='EVIDENCE_NOT_AUTHORITY') for n in ('installation-receipt','host-tests')],
        host_preflight_commands=preflight_commands(),
        host_test_required=list(HOST_TESTS),
        activation_prerequisites=['VERIFIED_INSTALLATION_RECEIPT','ALL_REQUIRED_HOST_TESTS',
            'EXPLICIT_FOUNDER_APPROVAL','FRESH_OPERATIONAL_ENROLLMENT','RECONCILIATION'],
        installer_contract=['VERIFY_SOURCE_COMMIT','READ_ONLY_HOST_PREFLIGHT','CHECK_ACCOUNT_UID_GID_COLLISIONS',
            'CHECK_TARGET_PATHS','VERIFY_BUNDLE_DIGEST','VERIFY_ALL_ARTIFACT_HASHES','REQUIRE_FOUNDER_APPROVAL',
            'PRIVILEGED_REVERIFY_ALL_INPUTS','CREATE_EXACT_IDENTITIES_GROUPS','CREATE_EXACT_DIRECTORIES',
            'COPY_EXACT_ARTIFACTS','VERIFY_INSTALLED_HASH_OWNER_GROUP_MODE','CREATE_EXACT_RUNTIME_POLICY',
            'INSTALL_EXACT_UNITS','DAEMON_RELOAD','KEEP_ACTIVATION_CLOSED',
            'INITIALIZE_VERIFY_CONTROLLER_REGISTRY_AS_CONTROLLER_NOT_ROOT',
            'SEPARATE_APPROVAL_FOR_INTEGRATION_SERVICES','RUN_HOST_TESTS','SEPARATE_ACTIVATION_APPROVAL'])


def artifact_spec():
    result=[]
    def add(source,destination,kind='regular',mode='0444',group='root'):
        result.append(dict(artifact_id=destination,source=source,destination=destination,
            artifact_type=kind,owner='root',group=group,mode=mode,provisioning_generation=1,required=True))
    for n in PRODUCTION_MODULES:add('tools/agent_control/'+n+'.py',PREFIX+'/tools/agent_control/'+n+'.py')
    for n in POLICIES:add('docs/agent-control/'+n+'.json',PREFIX+'/docs/agent-control/'+n+'.json')
    for n in ('bootstrap_entry.py','gate_entry.py'):add('tools/agent_control/'+n,PREFIX+'/'+n)
    add('generated/tools-init.py',PREFIX+'/tools/__init__.py')
    for n in ('controller','supervisor'):add('generated/'+n,PREFIX+'/'+n,'executable','0555')
    for n in ('identity-map','controller','supervisor'):add('generated/'+n+'.json',ETC+'/'+n+'.json','configuration','0440',NAMES[0])
    for n in sorted(units()):add('generated/'+n,'/etc/systemd/system/'+n,'unit')
    add('generated/bonup-agent-control.conf','/etc/tmpfiles.d/bonup-agent-control.conf','configuration')
    return result


def manifest_spec():
    return dict(artifact_id=MANIFEST,source='generated/approved-installation.json',destination=MANIFEST,
        artifact_type='configuration',owner='root',group=NAMES[0],mode='0440',provisioning_generation=1,required=True)


def rollback_policy(artifacts):
    return dict(version=1,recursive=False,created_only=True,verify_receipt_identity=True,
        sequence=['CLOSE_ADMISSION','PROHIBIT_RELEASE','TERMINATE_IDENTIFIED_LAUNCHES','VERIFY_EMPTY_CGROUPS',
            'STOP_DISABLE_EXACT_INSTALLED_UNITS','PRESERVE_REGISTRY_HISTORY','QUARANTINE_NONEMPTY_WORKSPACES',
            'VERIFY_UID_GID_NO_PROCESSES','REMOVE_VERIFIED_CREATED_ARTIFACTS','REMOVE_VERIFIED_EMPTY_DIRECTORIES',
            'REMOVE_VERIFIED_CREATED_IDENTITIES'],
        files=[a['destination'] for a in artifacts]+[MANIFEST],
        directories=[d['path'] for d in directories()],accounts=list(NAMES),
        protected_retention=['/var/lib/bonup-agent-control','/var/lib/bonup-agent-control/history.git'])


def generated_payloads():
    result={PREFIX+'/'+n:wrapper(n) for n in ('controller','supervisor')}
    result[PREFIX+'/tools/__init__.py']=b'"""Immutable bonUP installed package namespace."""\n'
    result[ETC+'/identity-map.json']=json_bytes(identities())
    for n,c in configurations().items():result[ETC+'/'+n+'.json']=json_bytes(c)
    for n,u in units().items():result['/etc/systemd/system/'+n]=u.encode()
    result['/etc/tmpfiles.d/bonup-agent-control.conf']=(''.join(
        'd '+d['path']+' '+d['mode']+' '+d['owner']+' '+d['group']+' -\n'
        for d in directories() if d['lifecycle']=='runtime')).encode()
    return result


def seal(manifest):
    manifest['bundle_digest']=digest({k:v for k,v in manifest.items() if k!='bundle_digest'})
    return manifest


def candidate(artifacts, source_commit):
    if not valid_format('git-oid',source_commit):raise ValidationError('Exact source commit required.')
    result=dict(version=4,source_mode='COMMITTED_BASE_PLUS_REVIEWED_PAYLOAD_HASHES',approved=False,activation=False,integration_services_approved=False,
        provisioning_generation=1,source_commit=source_commit,**policy_sections(),artifacts=artifacts,
        manifest_artifact=manifest_spec(),identity_map_digest=digest(identities()),
        configuration_digests={k:digest(v) for k,v in configurations().items()},
        files={a['destination']:a['sha256'] for a in artifacts if a['destination'].startswith(PREFIX+'/')},
        resource_digest=IntegrationPolicy().policy_digest,rollback=rollback_policy(artifacts))
    return seal(result)


def validate_manifest(manifest):
    if type(manifest) is not dict:raise ValidationError('Manifest object required.')
    keys(manifest,candidate([],SOURCE_COMMIT))
    if (type(manifest['version']) is not int or manifest['version']!=4 or
            type(manifest['provisioning_generation']) is not int or manifest['provisioning_generation']!=1 or
            any(type(manifest[k]) is not bool for k in ('approved','activation','integration_services_approved')) or
            not valid_format('git-oid',manifest['source_commit'])):
        raise ValidationError('Unsupported or incomplete manifest.')
    for name,expected in policy_sections().items():same(manifest[name],expected,name)
    specs=artifact_spec();artifacts=manifest['artifacts']
    if type(artifacts) is not list or len(artifacts)!=len(specs):raise ValidationError('Incomplete artifact closure.')
    for actual,expected in zip(artifacts,specs):
        keys(actual,(*expected,'sha256'))
        same({k:v for k,v in actual.items() if k!='sha256'},expected,'artifact')
        if not valid_format('sha256',actual['sha256']) or actual['sha256']=='0'*64:
            raise ValidationError('Unresolved artifact hash.')
    expected=candidate(artifacts,manifest['source_commit'])
    for k in ('approved','activation','integration_services_approved'):expected[k]=manifest[k]
    seal(expected)
    same(manifest,expected,'manifest binding')
    generated=generated_payloads()
    for a in artifacts:
        if a['destination'] in generated and a['sha256']!=sha(generated[a['destination']]):
            raise ValidationError('Generated privileged artifact differs from fixed policy.')
    if not manifest['approved']:
        if manifest['activation'] or manifest['integration_services_approved']:
            raise AuthorityError('Unapproved permissions prohibited.')
        return 'COMPLETE_BUT_UNAPPROVED'
    return 'COMPLETE_APPROVED_REQUIRES_EXTERNAL_EVIDENCE'


def verify_payloads(manifest,payloads):
    validate_manifest(manifest)
    if type(payloads) is not dict or set(payloads)!={a['destination'] for a in manifest['artifacts']}:
        raise ValidationError('Payload inventory mismatch.')
    for a in manifest['artifacts']:
        if type(payloads[a['destination']]) is not bytes or sha(payloads[a['destination']])!=a['sha256']:
            raise ValidationError('Artifact content hash mismatch.')
    dependency_closure(payloads)


def dependency_closure(payloads):
    """Closed import graph: explicit local modules or declared Python stdlib only."""
    available=set(PRODUCTION_MODULES)
    for n in PRODUCTION_MODULES:
        path=PREFIX+'/tools/agent_control/'+n+'.py'
        if path not in payloads:raise ValidationError('Unresolved production module.')
        tree=ast.parse(payloads[path],filename=path)
        for node in ast.walk(tree):
            if isinstance(node,ast.ImportFrom):
                if node.level:
                    if node.level!=1 or not node.module or node.module.split('.')[0] not in available:
                        raise ValidationError('Unresolved relative import.')
                elif node.module and node.module.startswith('tools.agent_control.'):
                    if node.module.split('.')[2] not in available:raise ValidationError('Unresolved installed import.')
                elif node.module and node.module.split('.')[0] not in sys.stdlib_module_names:
                    raise ValidationError('Undeclared runtime dependency.')
            elif isinstance(node,ast.Import):
                for alias in node.names:
                    if alias.name.split('.')[0] not in sys.stdlib_module_names:
                        raise ValidationError('Undeclared runtime import.')
            elif isinstance(node,ast.Call) and isinstance(node.func,ast.Name) and node.func.id=='__import__':
                raise ValidationError('Dynamic runtime dependency.')


def source_bytes(root,relative):
    # Pin and read the same descriptor. No source symlink or special-file fallback.
    root_path=Path(root).absolute()
    if any(p.is_symlink() for p in (root_path,*root_path.parents)):
        raise ValidationError('Symlinked source root.')
    fd=os.open(root_path,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        parts=Path(relative).parts
        if not parts or Path(relative).is_absolute() or '..' in parts:raise ValidationError('Canonical source required.')
        for i,part in enumerate(parts):
            child=os.open(part,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK|
                (os.O_DIRECTORY if i<len(parts)-1 else 0),dir_fd=fd)
            os.close(fd);fd=child
        info=os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>1048576:
            raise ValidationError('Unsafe source artifact.')
        raw=b''
        while len(raw)<=1048576:
            chunk=os.read(fd,65536)
            if not chunk:break
            raw+=chunk
        if len(raw)!=info.st_size or any(getattr(os.fstat(fd),k)!=getattr(info,k) for k in
            ('st_dev','st_ino','st_mode','st_nlink','st_uid','st_gid','st_size','st_mtime_ns','st_ctime_ns')):
            raise ValidationError('Source changed while hashing.')
        return raw
    finally:os.close(fd)


def build(repository, *, source_commit):
    # Generation 1 is historical. Rehydrate its reviewed bytes, never incorporate
    # successor source files under its provisioning generation or old identities.
    repository = Path(repository) / 'docs/agent-control/review/m3-generation-1/payload'
    payloads=generated_payloads();artifacts=[]
    for spec in artifact_spec():
        path=spec['destination']
        if path not in payloads:payloads[path]=source_bytes(repository,path.lstrip('/'))
        artifacts.append(dict(spec,sha256=sha(payloads[path])))
    manifest=candidate(artifacts,source_commit)
    verify_payloads(manifest,payloads)
    return manifest,payloads


def detached_inventory(manifest):
    validate_manifest(manifest)
    return dict(version=1,bundle_digest=manifest['bundle_digest'],artifacts=manifest['artifacts']+
        [dict(manifest_spec(),sha256=sha(json_bytes(manifest)))])


def write_review(repository, output, *, source_commit):
    """Only a new review/build directory or temporary directory; no host installer."""
    root=Path(repository).resolve();dest=Path(output).absolute()
    if any(p.is_symlink() for p in (dest,*dest.parents)):
        raise ValidationError('Symlinked review destination.')
    allowed=root/'docs/agent-control/review'
    if not (dest.is_relative_to(allowed) or dest.is_relative_to(Path('/tmp'))):
        raise AuthorityError('Review output outside allowed build roots.')
    if dest.exists():raise ValidationError('Review destination must be new; no overwrite.')
    import subprocess
    observed=subprocess.run(['/usr/bin/git','-C',str(root),'rev-parse','HEAD'],check=True,
        capture_output=True,text=True,env={'PATH':'/usr/bin:/bin','GIT_CONFIG_NOSYSTEM':'1','GIT_CONFIG_GLOBAL':'/dev/null'}).stdout.strip()
    if observed!=source_commit:raise AuthorityError('Source commit mismatch.')
    manifest,payloads=build(root,source_commit=source_commit)
    dest.mkdir(parents=True)
    for a in manifest['artifacts']:
        path=dest/'payload'/a['destination'].lstrip('/')
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(payloads[a['destination']])
    path=dest/'payload'/MANIFEST.lstrip('/');path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(json_bytes(manifest))
    (dest/'bundle-index.json').write_bytes(json_bytes(detached_inventory(manifest)))
    return manifest


def installation_binding(manifest):
    """Immutable installed policy, excluding separately authorized permission flips."""
    normalized=dict(manifest,approved=True,activation=False,integration_services_approved=False)
    return seal(normalized)['bundle_digest']


def uid_gid(name):
    if name=='root':return 0
    if name=='bonup':return 1000
    if name in NAMES:return 3000+NAMES.index(name)
    raise ValidationError('Unknown installation principal.')


def receipt_objects(manifest):
    # Capture original installation bytes, before later service/activation approvals.
    original=seal(dict(manifest,approved=True,activation=False,integration_services_approved=False))
    rows=[]
    for a in detached_inventory(original)['artifacts']:
        rows.append(dict(path=a['destination'],kind='file',sha256=a['sha256'],uid=uid_gid(a['owner']),
            gid=uid_gid(a['group']),mode=a['mode']))
    for d in directories():
        rows.append(dict(path=d['path'],kind='directory',sha256=None,uid=uid_gid(d['owner']),
            gid=uid_gid(d['group']),mode=d['mode']))
    return rows


def make_receipt(manifest, observations, *, accounts, boot_id, installed_at):
    """Trusted installer supplies fresh kernel observations; no host reads here."""
    from .protocol import uuid_value
    validate_manifest(manifest)
    if not manifest['approved'] or manifest['activation']:
        raise AuthorityError('Approved non-active installation required.')
    uuid_value(boot_id);timestamp(installed_at)
    expected=receipt_objects(manifest)
    if type(observations) is not list or len(observations)!=len(expected):
        raise ValidationError('Complete installation observations required.')
    for actual,policy in zip(observations,expected):
        keys(actual,(*policy,'device','inode','created'))
        same({k:actual[k] for k in policy},policy,'installed observation')
        if (any(type(actual[k]) is not int or actual[k]<1 for k in ('device','inode')) or
                type(actual['created']) is not bool):raise ValidationError('Kernel object identity required.')
    expected_accounts=[dict(a,created=True,group_created=True) for a in identities()['accounts']]
    same(accounts,expected_accounts,'observed created identities/groups')
    return dict(version=1,provisioning_generation=1,source_commit=manifest['source_commit'],
        installation_binding=installation_binding(manifest),bundle_digest=installation_binding(manifest),
        approved_manifest_digest=digest(seal(dict(manifest,approved=True,activation=False,integration_services_approved=False))),
        objects=observations,accounts=accounts,
        units=sorted(units()),host_boot_id=boot_id,installed_at=installed_at)


def validate_receipt(manifest, receipt):
    if type(receipt) is not dict:raise ValidationError('Installation receipt required.')
    keys(receipt,('version','provisioning_generation','source_commit','installation_binding','bundle_digest',
        'approved_manifest_digest','objects','accounts','units','host_boot_id','installed_at'))
    normalized=seal(dict(manifest,approved=True,activation=False,integration_services_approved=False))
    expected=make_receipt(normalized,receipt['objects'],accounts=receipt['accounts'],boot_id=receipt['host_boot_id'],installed_at=receipt['installed_at'])
    same(receipt,expected,'receipt')
    # Installation preflight forbids reuse of accounts or owned installation paths.
    if not all(o['created'] is True for o in receipt['objects']):
        raise AuthorityError('Conflicting/preexisting installation object.')


def verify_host_tests(manifest, receipt, evidence):
    validate_receipt(manifest,receipt)
    keys(evidence,('version','installation_binding','receipt_digest','results'))
    if (type(evidence['version']) is not int or evidence['version']!=1 or
            evidence['installation_binding']!=installation_binding(manifest) or
            evidence['receipt_digest']!=digest(receipt)):
        raise AuthorityError('Stale host-test evidence.')
    same(evidence['results'],{name:'PASS' for name in HOST_TESTS},'host-test results')


def founder(context):
    from .authority import require_context
    from .types import Role
    require_context(context,roles={Role.FOUNDER},actor_id='FOUNDER')
    if context.authenticated_unix_uid!=1000:raise AuthorityError('Enrolled founder required; root is not founder.')


def require_activation(manifest,receipt,evidence,*,context):
    validate_manifest(manifest);founder(context)
    if manifest['approved'] is not True or manifest['activation'] is not True:
        raise AuthorityError('Separate explicit activation approval required.')
    verify_host_tests(manifest,receipt,evidence)
    return installation_binding(manifest)


def runtime_permission(manifest,receipt,evidence=None):
    """Only after descriptor-verified root-controlled installed inputs are read.

    Root-controlled manifest permissions are the persisted approval decision.
    Receipt and test outcomes are evidence, never permission by themselves.
    """
    validate_manifest(manifest)
    if manifest['approved'] is not True:raise AuthorityError('Unapproved installation.')
    validate_receipt(manifest,receipt)
    if manifest['activation']:
        verify_host_tests(manifest,receipt,evidence)
        return 'ACTIVATION_APPROVED_STILL_REQUIRES_OPERATIONAL_ENROLLMENT'
    if manifest['integration_services_approved']:
        return 'INTEGRATION_SERVICES_ONLY_INTAKE_DISABLED'
    raise AuthorityError('No service-start approval.')


def validate_preflight(manifest, report):
    keys(report,('version','source_commit','bundle_digest','checks','uid_collisions','gid_collisions',
        'account_collisions','target_conflicts'))
    if (type(report['version']) is not int or report['version']!=1 or
            report['source_commit']!=manifest['source_commit'] or report['bundle_digest']!=manifest['bundle_digest']):
        raise AuthorityError('Preflight does not bind reviewed source/bundle.')
    same(report['checks'],{k:True for k in manifest['host_preflight']},'host preflight')
    for key in ('uid_collisions','gid_collisions','account_collisions','target_conflicts'):
        if report[key]!=[]:raise AuthorityError('Host installation collision.')


def installation_plan(manifest,payloads,preflight,*,context):
    """Return a bounded contract only; intentionally no mutation executor exists."""
    verify_payloads(manifest,payloads)
    validate_preflight(manifest,preflight)
    founder(context)
    if not manifest['approved'] or manifest['activation'] or manifest['integration_services_approved']:
        raise AuthorityError('Explicit installation-only approval required.')
    return dict(version=1,manifest_digest=digest(manifest),bundle_digest=manifest['bundle_digest'],
        sequence=manifest['installer_contract'],accounts=identities()['accounts'],directories=directories(),
        artifacts=detached_inventory(manifest)['artifacts'],units=sorted(units()),
        copy_map=[dict(relative_source='payload/'+a['destination'].lstrip('/'),destination=a['destination'])
            for a in detached_inventory(manifest)['artifacts']],
        execute_checkout=False,automatic_service_start=False,automatic_approval=False)


def rollback_file(manifest,receipt,path,observation,*,cleanup_confirmed):
    """Decide on one exact file, never perform deletion or accept a command string."""
    validate_manifest(manifest);validate_receipt(manifest,receipt)
    if cleanup_confirmed is not True:raise AuthorityError('Known empty launch cleanup required.')
    matches=[o for o in receipt['objects'] if o['path']==path and o['kind']=='file']
    if len(matches)!=1:raise AuthorityError('Not a manifest-created file.')
    expected=matches[0]
    same(observation,expected,'rollback object identity/hash')
    if not expected['created']:raise AuthorityError('Preexisting object cannot be removed.')
    return dict(action='UNLINK_VERIFIED_FILE',path=path,recursive=False,device=expected['device'],inode=expected['inode'])


def preflight_commands():
    """Review-only fixed argv. The collector must interpret absence, not auto-approve."""
    result=[['/usr/bin/git','-C','/home/bonup/bonup-blackboard','rev-parse','HEAD'],
        ['/usr/bin/getent','passwd','bonup'],['/usr/bin/bwrap','--version'],
        ['/usr/bin/cat','/sys/kernel/security/apparmor/profiles'],
        ['/usr/sbin/sysctl','kernel.unprivileged_userns_clone','kernel.apparmor_restrict_unprivileged_userns'],
        ['/usr/bin/findmnt','--noheadings','--output','FSTYPE','/sys/fs/cgroup'],
        ['/usr/bin/stat','--format=%F','/sys/fs/cgroup/system.slice/cgroup.kill'],
        ['/usr/bin/systemctl','--version'],['/usr/bin/python3','--version'],
        ['/usr/bin/free','--bytes'],['/usr/bin/df','--block-size=1','/var/lib','/srv'],
        ['/usr/bin/cat','/proc/filesystems']]
    for i,name in enumerate(NAMES):
        result.extend([['/usr/bin/getent','passwd',name],['/usr/bin/getent','passwd',str(3000+i)],
            ['/usr/bin/getent','group',name],['/usr/bin/getent','group',str(3000+i)]])
    # Fixed targets only. Existing targets fail preflight; errors require review.
    targets=[d['path'] for d in directories()]+[a['destination'] for a in artifact_spec()]+[MANIFEST]
    result.append(['/usr/bin/stat','--format=%n %F %u %g %a','--',*targets])
    return result
