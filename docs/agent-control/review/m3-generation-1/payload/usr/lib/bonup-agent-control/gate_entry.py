"""Installed-only gate entry point. Not executable as a worker from a checkout."""
import os
from pathlib import Path
import socket
import stat
import struct
import sys
import hashlib
from datetime import datetime, timezone


def installation_object(root, relative):
    """Descriptor-relative inspection shared by host verifier and namespace gate."""
    parts = relative.split('/') if relative else []
    if any(not p or p in ('.', '..') for p in parts):
        raise RuntimeError('Invalid installation member.')
    fd = os.dup(root)
    try:
        for i, part in enumerate(parts):
            child = os.open(part, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW |
                os.O_NONBLOCK | (os.O_DIRECTORY if i < len(parts)-1 else 0), dir_fd=fd)
            os.close(fd)
            fd = child
        info = os.fstat(fd)
        directory = stat.S_ISDIR(info.st_mode)
        if not directory and (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > 1048576):
            raise RuntimeError('Invalid installation member type/size.')
        content = hashlib.sha256()
        if not directory:
            while True:
                block = os.read(fd, 65536)
                if not block: break
                content.update(block)
        return dict(device=info.st_dev, inode=info.st_ino, uid=info.st_uid,
            gid=info.st_gid, mode=stat.S_IMODE(info.st_mode), directory=directory,
            sha256=None if directory else content.hexdigest())
    finally:
        os.close(fd)


def verify_namespace_installation(root, proof, uid_map, gid_map, *, generation=1):
    """No overflow-UID exception: exact host evidence plus explicit UID mapping.

    proof comes ONLY from the sealed supervisor configuration, never the wire.
    The installation subtree is a read-only bind of the retained host descriptor.
    """
    if (type(proof) is not dict or set(proof) != {'version','generation','bundle_digest',
            'members','uid_map','gid_map','namespace_owner'} or proof['version'] != 1 or
            type(proof['generation']) is not int or proof['generation'] != generation or
            type(proof['bundle_digest']) is not str or len(proof['bundle_digest']) != 64 or
            any(c not in '0123456789abcdef' for c in proof['bundle_digest']) or
            uid_map != proof['uid_map'] or gid_map != proof['gid_map']):
        raise RuntimeError('Installation namespace binding mismatch.')
    members = proof['members']
    owners=proof['namespace_owner']
    if type(owners) is not list or len(owners)!=2 or any(type(v) is not int or v<0 for v in owners):
        raise RuntimeError('Invalid namespace ownership policy.')
    for mapping,owner in zip((uid_map,gid_map),owners):
        if (type(mapping) is not list or not mapping or
                any(type(row) is not list or len(row)!=3 or any(type(v) is not int or v<0 for v in row)
                    or row[2]==0 for row in mapping)):
            raise RuntimeError('Invalid namespace ID map.')
        root_mapping=[row[0] for row in mapping if row[1]==0]
        if (root_mapping and root_mapping!=[owner]) or (not root_mapping and owner==0):
            raise RuntimeError('Namespace root ownership contradicts ID map.')
    if type(members) is not dict or not 2 <= len(members) <= 128 or '' not in members or 'gate_entry.py' not in members:
        raise RuntimeError('Incomplete installation proof.')
    for name, expected in members.items():
        if (type(expected) is not dict or set(expected) != {'device','inode','uid','gid','mode','directory','sha256'} or
                expected['uid'] != 0 or expected['gid'] != 0 or expected['mode'] & 0o022):
            raise RuntimeError('No trusted host installation verification.')
        actual = installation_object(root, name)
        translated = dict(expected, uid=proof['namespace_owner'][0], gid=proof['namespace_owner'][1])
        if actual != translated:
            raise RuntimeError('Namespace installation differs from pinned host object.')


def read_sealed_config(fd):
    import fcntl
    import json
    required=fcntl.F_SEAL_WRITE|fcntl.F_SEAL_GROW|fcntl.F_SEAL_SHRINK|fcntl.F_SEAL_SEAL
    if fcntl.fcntl(fd,fcntl.F_GET_SEALS)&required!=required:
        raise RuntimeError('Unsealed gate configuration.')
    raw=os.read(fd,65537)
    if len(raw)>65536: raise RuntimeError('Gate configuration size limit.')
    def unique(items):
        result={}
        for key,value in items:
            if key in result: raise RuntimeError('Duplicate configuration field.')
            result[key]=value
        return result
    return json.loads(raw.decode('utf-8'),object_pairs_hook=unique)


def main():
    installed = Path('/usr/lib/bonup-agent-control')
    here = Path(__file__).resolve()
    if here != installed/'gate_entry.py' or len(sys.argv)!=3:
        raise RuntimeError('Verified installed gate required.')
    cfgfd, socketfd = map(int,sys.argv[1:])
    if cfgfd<3 or socketfd<3 or cfgfd==socketfd:
        raise RuntimeError('Invalid gate descriptors.')
    cfg=read_sealed_config(cfgfd)
    if type(cfg) is not dict or set(cfg)!={'expected','payload','worker','host_namespaces','installation','status_channel'}:
        raise RuntimeError('Invalid gate configuration.')
    root=os.open(installed,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW|os.O_CLOEXEC)
    try:
        if not os.fstatvfs(root).f_flag & os.ST_RDONLY:
            raise RuntimeError('Installation bind must be read-only.')
        mapping=lambda name: [list(map(int,line.split())) for line in Path('/proc/self/'+name).read_text().splitlines()]
        verify_namespace_installation(root,cfg['installation'],mapping('uid_map'),mapping('gid_map'))
    finally:
        os.close(root)
    sys.path.insert(0,str(installed))
    from tools.agent_control.identity import PeerIdentity
    from tools.agent_control.protocol import bounded_json
    from tools.agent_control.release_gate import ExpectedRelease, FixedPayload, ReleaseGate
    from tools.agent_control.serialization import canonical_json
    from tools.agent_control.supervisor_linux import close_except
    cfgfd, socketfd = map(int,sys.argv[1:])
    if cfgfd<3 or socketfd<3 or cfgfd==socketfd:
        raise RuntimeError('Invalid gate descriptors.')
    status=cfg['status_channel']
    if (type(status) is not dict or set(status)!={'fd','device','inode'} or
            any(type(v) is not int for v in status.values()) or status['fd']<3 or status['fd'] in (cfgfd,socketfd)):
        raise RuntimeError('Invalid execution-status descriptor.')
    info=os.fstat(status['fd'])
    if not stat.S_ISSOCK(info.st_mode) or (info.st_dev,info.st_ino)!=(status['device'],status['inode']):
        raise RuntimeError('Execution-status channel substituted.')
    status_channel=socket.socket(fileno=status['fd'])
    close_except((0,1,2,cfgfd,socketfd,status['fd']))
    os.close(cfgfd)
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
    from tools.agent_control.exec_start import execute_observed,authorize_observed
    authorize_observed(ReleaseGate(expected,payload),channel,status_channel,now=lambda:datetime.now(timezone.utc))
    from tools.agent_control.schema import timestamp
    import time
    def before_exec():
        if (datetime.now(timezone.utc)>=timestamp(expected.expires_at) or
                time.clock_gettime_ns(time.CLOCK_BOOTTIME)>=expected.elapsed_deadline_ns):
            raise RuntimeError('Authority expired before exec.')
    result=execute_observed(payload,expected,status_channel,before_exec=before_exec)
    os._exit(result if result>=0 else 128-result)


if __name__=='__main__':
    try:
        main()
    except BaseException:
        # No config/argv/credential-bearing exception text goes to worker logs.
        os._exit(125)
