import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools.agent_control.gate_entry import installation_object,verify_namespace_installation


class GateInstallationTests(unittest.TestCase):
    def setUp(self):
        member=dict(device=10,inode=20,uid=0,gid=0,mode=0o644,directory=False,sha256='a'*64)
        self.proof=dict(version=1,generation=1,bundle_digest='b'*64,
            members={'':dict(member,inode=19,mode=0o755,directory=True,sha256=None),'gate_entry.py':member},
            uid_map=[[3001,3001,1]],gid_map=[[3001,3001,1]],namespace_owner=[65534,65534])
        self.actual={k:dict(v,uid=65534,gid=65534) for k,v in self.proof['members'].items()}

    def verify(self):
        with patch('tools.agent_control.gate_entry.installation_object',side_effect=lambda fd,name:self.actual[name]):
            verify_namespace_installation(8,self.proof,[[3001,3001,1]],[[3001,3001,1]])

    def test_host_verified_overflow_representation(self): self.verify()

    def test_arbitrary_overflow_host_owner_rejected(self):
        self.proof['members']['gate_entry.py']['uid']=65534
        with self.assertRaises(RuntimeError):self.verify()

    def test_wrong_digest(self):
        self.actual['gate_entry.py']['sha256']='c'*64
        with self.assertRaises(RuntimeError):self.verify()

    def test_wrong_generation(self):
        self.proof['generation']=2
        with self.assertRaises(RuntimeError):self.verify()

    def test_wrong_translation(self):
        self.actual['gate_entry.py']['uid']=0
        with self.assertRaises(RuntimeError):self.verify()

    def test_substituted_artifact(self):
        self.actual['gate_entry.py']['inode']+=1
        with self.assertRaises(RuntimeError):self.verify()

    def test_substituted_root(self):
        self.actual['']['inode']+=1
        with self.assertRaises(RuntimeError):self.verify()

    def test_literal_zero_requires_explicit_mapping(self):
        self.proof['uid_map']=self.proof['gid_map']=[[0,0,4294967295]]
        self.proof['namespace_owner']=[0,0]
        self.actual=copy.deepcopy(self.proof['members'])
        with patch('tools.agent_control.gate_entry.installation_object',side_effect=lambda fd,name:self.actual[name]):
            verify_namespace_installation(8,self.proof,[[0,0,4294967295]],[[0,0,4294967295]])

    def test_worker_writable_rejected(self):
        self.proof['members']['gate_entry.py']['mode']=0o666
        self.actual['gate_entry.py']['mode']=0o666
        with self.assertRaises(RuntimeError):self.verify()

    def test_retained_root_fd_survives_path_replacement(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'installed';root.mkdir()
            (root/'gate_entry.py').write_text('original')
            fd=os.open(root,os.O_RDONLY|os.O_DIRECTORY)
            try:
                inspected=installation_object(fd,'gate_entry.py')
                root.rename(Path(directory)/'old')
                root.mkdir();(root/'gate_entry.py').write_text('replacement')
                self.assertEqual(installation_object(fd,'gate_entry.py'),inspected)
                (Path(directory)/'old'/'gate_entry.py').unlink()
                (Path(directory)/'old'/'gate_entry.py').symlink_to(root/'gate_entry.py')
                with self.assertRaises(OSError):installation_object(fd,'gate_entry.py')
            finally:os.close(fd)
