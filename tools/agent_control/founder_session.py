"""Process-bound external-signature enrollment; no private signer or activation."""
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime,timezone,timedelta
import base64
import secrets
import threading
import time
from uuid import uuid4

from .founder_crypto import FounderRoot,OpenSSLVerifier,PURPOSES,load_founder_root
from .identity import PeerIdentity,ProcessIdentity,founder_context
from .installation_approval import validate_proposal,approval_record
from .serialization import canonical_json,digest
from .types import AuthorityError,ValidationError


def wall():return datetime.now(timezone.utc)
def elapsed():return time.clock_gettime(time.CLOCK_BOOTTIME)


class FounderSessions:
    """Trusted owner supplies kernel observations and durable audit sink.

    Transport callers submit only a challenge ID and signature. Root configuration
    is selected at construction, never from a message. Objects do not survive
    service restart; persisted challenges cannot be resumed/replayed.
    """
    def __init__(self,root,*,observe,audit,clock=wall,boottime=elapsed):
        if type(root) is not FounderRoot:raise ValidationError('Trusted founder root required.')
        self.root=root;self.observe=observe;self.audit=audit;self.clock=clock;self.boottime=boottime
        self.generation=str(uuid4());self.pending={};self.sessions={};self.used=set();self.lock=threading.RLock()
        self.verifier=OpenSSLVerifier()

    @classmethod
    def installed(cls,*,observe,audit):return cls(load_founder_root(),observe=observe,audit=audit)

    def _peer(self):
        peer,process=self.observe()
        if (type(peer) is not PeerIdentity or type(process) is not ProcessIdentity or
                (peer.uid,peer.gid)!=(1000,1000) or peer.pid!=process.pid or process.start_ticks<=0):
            raise AuthorityError('Kernel founder process constraints failed.')
        return peer,process

    def issue(self,purpose,raw,proposal,*,installation_receipt_digest=None):
        return self.issue_binding(purpose, validate_proposal(raw,proposal),
                                  installation_receipt_digest=installation_receipt_digest)

    def issue_binding(self,purpose,binding,*,installation_receipt_digest=None):
        with self.lock:
            if purpose not in PURPOSES:raise AuthorityError('Purpose disabled.')
            from .authority_installation import InstallationBinding
            binding=InstallationBinding(**binding).data()
            if purpose==PURPOSES[1] and (type(installation_receipt_digest) is not str or
                    len(installation_receipt_digest)!=64 or any(c not in '0123456789abcdef' for c in installation_receipt_digest)):
                raise AuthorityError('Verified installation receipt binding required.')
            if purpose==PURPOSES[0] and installation_receipt_digest is not None:
                raise AuthorityError('Installation purpose cannot be substituted.')
            peer,process=self._peer();now=self.clock();deadline=self.boottime()+60;nonce=secrets.token_hex(32)
            if len(self.pending)+len(self.used)>=256:raise AuthorityError('Enrollment capacity exhausted.')
            challenge=dict(version=1,protocol='bonup-founder-root-v1',purpose=purpose,
                audience='GENERATION_'+str(binding['provisioning_generation'])+'_INSTALLER' if purpose==PURPOSES[0] else 'M3_HOST_TEST_CONTROLLER',
                nonce=nonce,peer=asdict(peer),process=asdict(process),enrollment_generation=self.generation,
                key_id=self.root.key_id,algorithm=self.root.algorithm,root_generation=self.root.generation,
                root_digest=self.root.identity,binding=binding,installation_receipt_digest=installation_receipt_digest,
                issued_at=now.isoformat(),expires_at=(now+timedelta(seconds=60)).isoformat())
            challenge_id=digest(challenge)
            self.audit('FOUNDER_CHALLENGE_ISSUED',challenge_id)
            self.pending[challenge_id]=(challenge,deadline)
            return deepcopy(challenge)

    def revoke_all(self):
        with self.lock:
            for session in tuple(self.sessions):
                self.audit('FOUNDER_SESSION_EXPIRED',session)
            self.sessions.clear()
            self.pending.clear()
            self.generation=str(uuid4())

    def _live(self,challenge,deadline):
        peer,process=self._peer()
        if (self.boottime()>=deadline or self.clock()>=datetime.fromisoformat(challenge['expires_at']) or
                challenge['peer']!=asdict(peer) or challenge['process']!=asdict(process) or
                challenge['enrollment_generation']!=self.generation or challenge['root_digest']!=self.root.identity):
            raise AuthorityError('Stale or transferred founder authority.')

    def submit(self,message):
        with self.lock:
            if type(message) is not dict or set(message)!={'challenge_id','signature'}:
                raise ValidationError('Closed signature submission required.')
            key=message['challenge_id']
            if type(key) is not str or key not in self.pending or key in self.used:
                raise AuthorityError('Unknown/replayed founder challenge.')
            challenge,deadline=self.pending.pop(key);self.used.add(key)
            try:
                self._live(challenge,deadline)
                if type(message['signature']) is not str or len(message['signature']) != 88:
                    raise AuthorityError('Bounded signature encoding required.')
                try:signature=base64.b64decode(message['signature'],validate=True)
                except (ValueError,TypeError) as error:raise AuthorityError('Invalid signature encoding.') from error
                self.verifier.verify(self.root,canonical_json(challenge).encode(),signature)
                self._live(challenge,deadline)
                self.audit('FOUNDER_SIGNATURE_ACCEPTED',key)
                self.audit('FOUNDER_SESSION_CREATED',key)
                self.sessions[key]=(challenge,deadline,digest({'challenge':key,'signature':signature.hex()}))
                return key
            except BaseException:
                self.audit('FOUNDER_SIGNATURE_DENIED',key)
                raise

    def consume(self,session,purpose,binding,*,installation_receipt_digest=None):
        with self.lock:
            if type(session) is not str or session not in self.sessions:raise AuthorityError('Founder session required.')
            challenge,deadline,decision=self.sessions.pop(session)
            try:
                self._live(challenge,deadline)
                if (purpose not in PURPOSES or challenge['purpose']!=purpose or challenge['binding']!=binding or
                        challenge['installation_receipt_digest']!=installation_receipt_digest):
                    raise AuthorityError('Founder purpose/installation mismatch.')
                return deepcopy(challenge),decision
            except BaseException:
                self.audit('FOUNDER_SESSION_EXPIRED',session)
                raise

    def delegate(self,session,purpose,binding,*,installation_receipt_digest=None):
        """Consume once and retain the original process/BOOTTIME ceiling."""
        with self.lock:
            if type(session) is not str or session not in self.sessions:
                raise AuthorityError('Founder session required.')
            deadline=self.sessions[session][1]
            challenge,decision=self.consume(session,purpose,binding,
                installation_receipt_digest=installation_receipt_digest)
            def verify():
                self._live(challenge,deadline)
            verify.expires_at = challenge['expires_at']
            verify.elapsed_deadline = deadline
            return challenge,decision,verify

    def approve_installation(self,session,raw,proposal):
        binding=validate_proposal(raw,proposal)
        try:
            with self.lock:
                if type(session) is not str or session not in self.sessions:
                    raise AuthorityError('Founder session required.')
                deadline=self.sessions[session][1]
                challenge,proof=self.consume(session,PURPOSES[0],binding)
                enrolled=ProcessIdentity(**challenge['process'])
                peer=PeerIdentity(**challenge['peer'])
                def reader(pid):
                    self._live(challenge,deadline)
                    observed=self._peer()[1]
                    if observed.pid!=pid:raise AuthorityError('Founder process changed.')
                    return observed
                context=founder_context(peer,founder_uid=1000,enrolled_process=enrolled,reader=reader)
                decision=approval_record(raw,proposal,context=context,approval_id=str(uuid4()),
                    approved_at=self.clock().isoformat().replace('+00:00','Z'))
                self._live(challenge,deadline)
                self.audit('INSTALLATION_APPROVAL_ISSUED',session)
                self._live(challenge,deadline)
                return dict(version=1,decision=decision,challenge_digest=digest(challenge),signature_decision_digest=proof)
        except BaseException:
            self.audit('INSTALLATION_APPROVAL_DENIED',session)
            raise
