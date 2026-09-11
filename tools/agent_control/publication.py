"""Idempotent local Git publication. No remotes, checkout, reset or push."""
import json
import os
import subprocess

from .serialization import digest, parse_json
from .paths import PathRule
from .storage import RegistryBlocked, external_path

REF = 'refs/heads/control-history'
IDENTITY_PATH = 'registry-identity.json'


def readable(payload):
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()


class GitHistory:
    def __init__(self, path, registry_id):
        self.path = external_path(path)
        self.registry_id = registry_id

    def _git(self, *args, data=None, allow_failure=False):
        # Exclude inherited repository, credential/helper, template and config redirection.
        env = {'PATH': os.defpath, 'LC_ALL': 'C',
               'GIT_CONFIG_NOSYSTEM':'1', 'GIT_CONFIG_GLOBAL':os.devnull,
               'GIT_TERMINAL_PROMPT':'0', 'GIT_NO_REPLACE_OBJECTS':'1',
               'GIT_AUTHOR_NAME':'bonUP control publication', 'GIT_AUTHOR_EMAIL':'control@invalid',
               'GIT_COMMITTER_NAME':'bonUP control publication','GIT_COMMITTER_EMAIL':'control@invalid',
               'GIT_AUTHOR_DATE':'2000-01-01T00:00:00Z','GIT_COMMITTER_DATE':'2000-01-01T00:00:00Z'}
        command = ['git','-c','core.hooksPath=/dev/null','-c','commit.gpgSign=false',
                   '-c','core.fsync=committed','-c','core.fsyncMethod=fsync','-c','gc.auto=0','-c','maintenance.auto=false','--git-dir='+str(self.path),*args]
        try:
            result = subprocess.run(command, input=data, capture_output=True, env=env, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            raise RegistryBlocked('Control-history Git process unavailable; retry when available.') from None
        if result.returncode and not allow_failure:
            raise RegistryBlocked('Control-history Git operation failed.')
        return result

    def initialize(self):
        if self.path.exists():
            self.verify_identity()
            return
        self.path.mkdir(parents=True, mode=0o700)
        self._git('init','--bare','--template=',str(self.path))
        blob = self._git('hash-object','-w','--stdin',data=readable({'registry_id':self.registry_id,'format_version':1})).stdout.decode().strip()
        tree = self._git('mktree', data=f'100644 blob {blob}\t{IDENTITY_PATH}\n'.encode()).stdout.decode().strip()
        commit = self._git('commit-tree',tree,data=b'Initialize bonUP control history\n').stdout.decode().strip()
        self._git('update-ref',REF,commit,'0'*40)
        self._git('symbolic-ref','HEAD',REF)

    def head(self):
        return self._git('rev-parse','--verify',REF).stdout.decode().strip()

    def verify_identity(self):
        if self._git('rev-parse','--is-bare-repository').stdout.strip() != b'true':
            raise RegistryBlocked('History must be a dedicated bare repository.')
        if self._git('remote').stdout.strip():
            raise RegistryBlocked('Control history must have no remote.')
        refs = self._git('for-each-ref','--format=%(refname)').stdout.decode().splitlines()
        if refs != [REF]:
            raise RegistryBlocked('Unexpected control-history refs.')
        actual = parse_json(self._git('show',self.head()+':'+IDENTITY_PATH).stdout)
        if actual != {'registry_id':self.registry_id,'format_version':1}:
            raise RegistryBlocked('Control-history repository identity mismatch.')

    def _existing(self, path, expected):
        result = self._git('show',self.head()+':'+path,allow_failure=True)
        if result.returncode:
            return None
        if result.stdout != readable(expected):
            raise RegistryBlocked('Conflicting publication payload; operator recovery required.')
        commits = self._git('log','--format=%H',REF,'--',path).stdout.decode().splitlines()
        if len(commits) != 1:
            raise RegistryBlocked('Publication path history is ambiguous.')
        return commits[0]

    def publish(self, item):
        self.verify_identity()
        PathRule('FILE',item['path'])
        if item['path']==IDENTITY_PATH or item['path'].split('/')[0] not in {
            'agents','tasks','findings','conflicts','decisions','candidates','approvals',
            'evidence','executions','candidate_events','events'}:
            raise RegistryBlocked('Invalid publication record path.')
        payload = parse_json(item['payload'])
        if digest(payload) != item['payload_digest']:
            raise RegistryBlocked('Outbox digest mismatch.')
        existing = self._existing(item['path'],payload)
        if existing:
            return existing
        # Build a fresh tree in memory from the current tip. update-ref is CAS;
        # competing publishers retry against the new tip without rewriting it.
        for _ in range(8):
            parent = self.head()
            existing = self._existing(item['path'],payload)
            if existing:
                return existing
            entries = self._git('ls-tree','-rz',parent).stdout.split(b'\0')
            leaves = {}
            for entry in entries:
                if not entry:continue
                meta,path = entry.split(b'\t',1)
                mode,kind,oid = meta.decode().split()
                leaves[path.decode()] = (mode,kind,oid)
            blob = self._git('hash-object','-w','--stdin',data=readable(payload)).stdout.decode().strip()
            leaves[item['path']] = ('100644','blob',blob)
            tree = self._tree(leaves)
            message = f"Publish {item['publication_id']} {item['payload_digest']}\n".encode()
            commit = self._git('commit-tree',tree,'-p',parent,data=message).stdout.decode().strip()
            if not self._git('update-ref',REF,commit,parent,allow_failure=True).returncode:
                return commit
        raise RegistryBlocked('Concurrent publication retry limit reached; retry later.')

    def _tree(self, leaves):
        root = {}
        for path, entry in leaves.items():
            target = root
            parts = path.split('/')
            for part in parts[:-1]:
                target = target.setdefault(part,{})
            target[parts[-1]] = entry
        def build(node):
            rows=[]
            for name,value in sorted(node.items()):
                mode,kind,oid = ('040000','tree',build(value)) if isinstance(value,dict) else value
                rows.append(f'{mode} {kind} {oid}\t{name}\0'.encode())
            return self._git('mktree','-z',data=b''.join(rows)).stdout.decode().strip()
        return build(root)

    def verify_ack(self, item, acknowledgement):
        self.verify_identity()
        oid=acknowledgement['git_commit']
        if self._git('merge-base','--is-ancestor',oid,self.head(),allow_failure=True).returncode:
            raise RegistryBlocked('Acknowledged publication is not in history.')
        if self._git('show',oid+':'+item['path']).stdout != readable(parse_json(item['payload'])):
            raise RegistryBlocked('Acknowledged publication payload mismatch.')
        if self._existing(item['path'],parse_json(item['payload'])) != oid:
            raise RegistryBlocked('Acknowledged publication identity mismatch.')

    def verify_paths(self, expected):
        actual=set(self._git('ls-tree','-r','--name-only',REF).stdout.decode().splitlines())
        if actual - set(expected) - {IDENTITY_PATH}:
            raise RegistryBlocked('Unexpected records in control history.')
