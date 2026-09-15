"""Fixed installed privileged bootstrap. Never run from a writable checkout."""
import os
import sys
import stat
from pathlib import Path


def main():
    installed=Path('/usr/lib/bonup-agent-control')
    if Path(__file__).resolve()!=installed/'bootstrap_entry.py' or len(sys.argv)!=2 or os.geteuid()!=0:
        raise RuntimeError('Installed privileged bootstrap required.')
    for node in (Path(__file__),installed,*installed.parents):
        info=node.lstat()
        if stat.S_ISLNK(info.st_mode) or info.st_uid!=0 or info.st_mode&0o022:
            raise RuntimeError('Mutable bootstrap installation.')
    sys.path.insert(0,str(installed))
    import fcntl
    from tools.agent_control.protocol import bounded_json
    from tools.agent_control.supervisor_linux import close_except,drop_worker_identity,set_process_limits
    from tools.agent_control.identity import WorkerIdentity
    from tools.agent_control.authority import actor_role
    fd=int(sys.argv[1])
    seals=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL
    if fd<3 or fcntl.fcntl(fd,fcntl.F_GET_SEALS)&seals!=seals:
        raise RuntimeError('Sealed bootstrap configuration required.')
    cfg=bounded_json(os.read(fd,65537))
    if type(cfg) is not dict or set(cfg)!={'version','worker','argv','keep','start_fd','cpu_seconds'} or type(cfg['version']) is not int or cfg['version']!=1:
        raise RuntimeError('Invalid bootstrap configuration.')
    names={3001:('ARCH-01','bonup-arch01'),3002:('FE-01','bonup-fe01'),
           3003:('BE-01','bonup-be01'),3004:('QA-01','bonup-qa01')}
    if type(cfg['worker']) is not list or len(cfg['worker'])!=2 or any(type(v) is not int for v in cfg['worker']) or cfg['worker'][0] not in names or cfg['worker'][0]!=cfg['worker'][1]:
        raise RuntimeError('Unenrolled worker identity.')
    if (type(cfg['argv']) is not list or not cfg['argv'] or cfg['argv'][0]!='/usr/bin/bwrap' or
            any(type(v) is not str or not v or '\0' in v for v in cfg['argv']) or
            type(cfg['cpu_seconds']) is not int or cfg['cpu_seconds']!=30 or type(cfg['keep']) is not list or
            any(type(n) is not int or n<0 for n in cfg['keep']) or
            len(set(cfg['keep']))!=len(cfg['keep']) or not {0,1,2}<=set(cfg['keep']) or
            type(cfg['start_fd']) is not int or cfg['start_fd']<3 or cfg['start_fd']==fd or
            cfg['start_fd'] not in cfg['keep'] or fd not in cfg['keep']):
        raise RuntimeError('Invalid fixed bootstrap plan.')
    close_except(tuple(cfg['keep']))
    os.close(fd)
    start=cfg['start_fd']
    if os.read(start,1)!=b'P':
        raise RuntimeError('No cgroup placement acknowledgment.')
    os.close(start)
    uid,gid=cfg['worker'];agent,username=names[uid]
    keep=tuple(n for n in cfg['keep'] if n not in (fd,start))
    set_process_limits(nofile=256,file_bytes=16777216,cpu_seconds=30)
    drop_worker_identity(WorkerIdentity(agent,actor_role(agent),username,uid,gid),allowed_fds=keep)
    for n in keep:
        os.set_inheritable(n,True)
    os.chdir('/')
    os.execve('/usr/bin/bwrap',cfg['argv'],{})


if __name__=='__main__':
    try: main()
    except BaseException: os._exit(125)
