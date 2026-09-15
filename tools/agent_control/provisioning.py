"""Read-only manifest generation/validation. No installer or host mutation commands."""
from pathlib import Path
import hashlib

from .serialization import digest
from .types import ValidationError

NAMES=('bonup-agentctl','bonup-arch01','bonup-fe01','bonup-be01','bonup-qa01')


def review_manifest(repository):
    """Hash agent-control Python/policy files; never inspect secrets or application data."""
    root=Path(repository)
    files=[]
    for path in sorted((root/'tools/agent_control').glob('*.py')):
        if path.is_symlink():
            raise ValidationError('Symlinked artifact rejected.')
        destination='/usr/lib/bonup-agent-control/tools/agent_control/'+path.name
        files.append(dict(source=str(path.relative_to(root)),destination=destination,
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest(),owner='root',group='root',mode='0644'))
        if path.name=='gate_entry.py':
            files.append(dict(source=str(path.relative_to(root)),destination='/usr/lib/bonup-agent-control/gate_entry.py',
                              sha256=hashlib.sha256(path.read_bytes()).hexdigest(),owner='root',group='root',mode='0644'))
    for path in sorted((root/'docs/agent-control').glob('*.json')):
        if path.is_symlink():
            raise ValidationError('Symlinked policy rejected.')
        files.append(dict(source=str(path.relative_to(root)),destination='/usr/lib/bonup-agent-control/docs/agent-control/'+path.name,
                          sha256=hashlib.sha256(path.read_bytes()).hexdigest(),owner='root',group='root',mode='0644'))
    if not files:
        raise ValidationError('Agent-control artifacts missing.')
    return dict(version=1,approved=False,provisioning_generation=None,founder_uid=1000,
        accounts=[dict(username=n,uid=None,gid=None,primary_group=n,supplementary_groups=[],
            shell='/usr/sbin/nologin',password='LOCKED',home=('/var/lib/bonup-agent-control/home' if n=='bonup-agentctl'
                else '/srv/bonup-agent-work/'+n+'/home'),
            home_mode='0700',umask='0077',ssh_keys=[]) for n in NAMES],
        files=files,capabilities=['CAP_SETUID','CAP_SETGID','CAP_KILL'],
        capability_review='CAP_DAC_READ_SEARCH requires explicit review if supervisor opens worker-owned 0700 roots.',
        directories=[dict(path='/var/lib/bonup-agent-control',owner='bonup-agentctl',group='bonup-agentctl',mode='0700'),
                     dict(path='/srv/bonup-agent-work',owner='root',group='root',mode='0711'),
                     dict(path='/run/bonup-agent-supervisor',owner='root',group='bonup-agentctl',mode='0750')]+
                    [dict(path='/srv/bonup-agent-work/'+n,owner=n,group=n,mode='0700') for n in NAMES[1:]],
        socket=dict(path='/run/bonup-agent-supervisor/control.sock',owner='root',group='bonup-agentctl',mode='0660'),
        service_entrypoint=None,workspace_storage_limit=None,service_template='bonup-agent-supervisor.service.in',
        cgroups=dict(delegate=['cpu','memory','pids'],manager_subgroup='supervisor',launch_prefix='launch-',swap_max=0),
        activation=False)


def validate_approved_manifest(manifest):
    """Reject incomplete templates. Does not imply installation/activation permission."""
    if type(manifest) is not dict or manifest.get('approved') is not True or manifest.get('activation') is not False:
        raise ValidationError('Founder-approved non-activation manifest required.')
    if type(manifest.get('provisioning_generation')) is not int or manifest['provisioning_generation']<1:
        raise ValidationError('Provisioning generation required.')
    accounts=manifest.get('accounts',[])
    if len(accounts)!=len(NAMES) or {a['username'] for a in accounts}!=set(NAMES):
        raise ValidationError('Exact account inventory required.')
    for key in ('uid','gid'):
        values=[a[key] for a in accounts]
        if any(type(v) is not int or v<=0 or v==manifest['founder_uid'] for v in values) or len(set(values))!=len(values):
            raise ValidationError('Explicit distinct UID/GID allocation required.')
    for a in accounts:
        if a['supplementary_groups'] or a['ssh_keys'] or a['shell']!='/usr/sbin/nologin' or a['password']!='LOCKED':
            raise ValidationError('Unsafe account policy.')
    if manifest.get('service_entrypoint') is None or manifest.get('workspace_storage_limit') is None:
        raise ValidationError('Installed event-loop entrypoint and workspace storage policy require review.')
    return digest(manifest)
