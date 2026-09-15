"""Installed-only gate entry point. Not executable as a worker from a checkout."""
import os
from pathlib import Path
import socket
import stat
import struct
import sys
from datetime import datetime, timezone


def main():
    installed = Path('/usr/lib/bonup-agent-control')
    here = Path(__file__).resolve()
    if here != installed/'gate_entry.py' or len(sys.argv)!=3:
        raise RuntimeError('Verified installed gate required.')
    for path in (installed,*installed.parents):
        info=path.lstat()
        if info.st_uid!=0 or info.st_mode & 0o022 or stat.S_ISLNK(info.st_mode):
            raise RuntimeError('Installed gate path is mutable.')
    sys.path.insert(0,str(installed))
    from tools.agent_control.identity import PeerIdentity
    from tools.agent_control.protocol import bounded_json
    from tools.agent_control.release_gate import ExpectedRelease, FixedPayload, ReleaseGate
    from tools.agent_control.serialization import canonical_json
    from tools.agent_control.supervisor_linux import close_except
    cfgfd, socketfd = map(int,sys.argv[1:])
    if cfgfd<3 or socketfd<3 or cfgfd==socketfd:
        raise RuntimeError('Invalid gate descriptors.')
    close_except((0,1,2,cfgfd,socketfd))
    import fcntl
    required=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL
    if fcntl.fcntl(cfgfd,fcntl.F_GET_SEALS)&required!=required:
        raise RuntimeError('Unsealed gate configuration.')
    raw=os.read(cfgfd,65537)
    os.close(cfgfd)
    cfg=bounded_json(raw)
    if type(cfg) is not dict or set(cfg)!={'expected','payload','worker','host_namespaces'}:
        raise RuntimeError('Invalid gate configuration.')
    expected=dict(cfg['expected'])
    expected['peer']=PeerIdentity(**expected['peer'])
    expected['channel_identity']=tuple(expected['channel_identity'])
    expected=ExpectedRelease(**expected)
    p=cfg['payload']
    if type(p) is not dict or set(p)!={'argv','environment','cwd'}:
        raise RuntimeError('Invalid payload configuration.')
    payload=FixedPayload(tuple(p['argv']),tuple(tuple(x) for x in p['environment']),p['cwd'])
    if cfg['worker'] != [os.geteuid(),os.getegid()] or os.geteuid()==0 or os.getgroups():
        raise RuntimeError('Worker identity mismatch.')
    for name,inode in cfg['host_namespaces'].items():
        if name not in ('mnt','pid','net') or os.stat('/proc/self/ns/'+name).st_ino==inode:
            raise RuntimeError('Confinement namespace missing.')
    if set(cfg['host_namespaces'])!={'mnt','pid','net'}:
        raise RuntimeError('Missing namespace evidence.')
    status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    if status['NoNewPrivs'].strip()!='1' or any(int(status[k].strip(),16) for k in ('CapEff','CapPrm','CapInh','CapAmb')):
        raise RuntimeError('Worker privilege boundary missing.')
    if Path('/proc/self/attr/current').read_text().strip()!='unpriv_bwrap (enforce)':
        raise RuntimeError('Expected AppArmor profile absent.')
    channel=socket.socket(fileno=socketfd)
    ready=canonical_json({'version':1,'ready':expected.launch_id}).encode()
    channel.sendall(struct.pack('!I',len(ready))+ready)
    channel.shutdown(socket.SHUT_WR)
    ReleaseGate(expected,payload).execute(channel,now=lambda:datetime.now(timezone.utc))


if __name__=='__main__':
    try:
        main()
    except BaseException:
        # No config/argv/credential-bearing exception text goes to worker logs.
        os._exit(125)
