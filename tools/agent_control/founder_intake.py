"""Fixed installed controller operations for externally signed founder decisions."""
from dataclasses import dataclass
from uuid import uuid4

from .authority_installation import InstallationBinding, verify_receipt, approval_projection
from .founder_crypto import FounderRoot, PURPOSES
from .founder_session import FounderSessions
from .host_test_runtime import HostTests
from .operational_enrollment import AdmissionState
from .protocol import uuid_value
from .types import AuthorityError, ValidationError


@dataclass(frozen=True)
class FounderPolicy:
    enabled: bool
    binding: InstallationBinding
    root_digest: str
    receipt_digest: str | None
    activation: bool = False
    host_tests_enabled: bool = True

    def __post_init__(self):
        from .schema import valid_format
        if (type(self.enabled) is not bool or type(self.host_tests_enabled) is not bool or type(self.binding) is not InstallationBinding or
                self.binding.provisioning_generation < 2 or self.activation is not False or
                not valid_format('sha256', self.root_digest) or
                self.receipt_digest is not None and not valid_format('sha256', self.receipt_digest)):
            raise ValidationError('Closed Generation-2-or-later founder policy required.')


class FounderIntake:
    def __init__(self, policy, root, observe, journal, *, controller, runner, runtime_context,
                 receipt_reader, candidate_reader, clock=None, boottime=None):
        if type(policy) is not FounderPolicy or not policy.enabled:
            raise AuthorityError('Installed founder enrollment is disabled.')
        if type(root) is not FounderRoot or root.identity != policy.root_digest:
            raise AuthorityError('Installed founder root pin mismatch.')
        self.policy, self.journal, self.controller = policy, journal, controller
        options = {}
        if clock is not None: options['clock'] = clock
        if boottime is not None: options['boottime'] = boottime
        self.founder = FounderSessions(root, observe=observe, audit=journal, **options)
        self.runner, self.context = runner, runtime_context
        self.receipt_reader, self.candidate_reader = receipt_reader, candidate_reader
        self.tests = None
        self.seen = set()

    def _receipt(self):
        if self.policy.receipt_digest is None:
            raise AuthorityError('No installed receipt pin.')
        return verify_receipt(self.receipt_reader(), self.policy.binding, self.policy.receipt_digest)

    def request(self, request):
        if type(request) is not dict or set(request) != {'version', 'request_id', 'action', 'arguments'}:
            raise ValidationError('Closed founder operation required.')
        request_id = uuid_value(request['request_id'])
        if request['version'] != 1 or type(request['version']) is not int or request_id in self.seen or len(self.seen) >= 256:
            raise AuthorityError('Founder request version/replay/capacity.')
        self.seen.add(request_id)
        action, args = request['action'], request['arguments']
        if type(args) is not dict:
            raise ValidationError('Bounded operation arguments required.')
        from .host_test_catalog import CATALOG
        host=type(action) is str and any(part in action for part in ('HOST_TEST','INTERRUPTION','REBOOT'))
        context=dict(request_id=request_id,receipt=self.policy.receipt_digest,
            session_id=self.tests.session if self.tests else None,
            test_id=args.get('test_id') if type(args.get('test_id')) is str and args['test_id'] in CATALOG else None)
        from .schema import valid_format
        if context['session_id'] is None and valid_format('sha256',args.get('session')):
            context['session_id']=args['session']  # Correlation only, never authority.
        self.request_context=context
        if host:self.journal.record('HOST_TEST_REQUEST_RECEIVED',request_id,context)
        if self.tests is not None:self.tests.audit_context=context
        try:
            result = self._request(action, args)
            return dict(version=1, request_id=request_id, result=result)
        except BaseException:
            kind = 'HOST_TEST_AUTHORIZATION_DENIED' if host else 'FOUNDER_SIGNATURE_DENIED'
            if not (self.tests is not None and request_id in self.tests.authorized_requests):
                self.journal.record(kind, request_id, context)
            raise

    def _request(self, action, args):
        if action == 'REQUEST_FOUNDER_CHALLENGE' and set(args) == {'purpose'}:
            purpose = args['purpose']
            receipt = None
            if purpose == PURPOSES[1]:
                if not self.policy.host_tests_enabled:
                    raise AuthorityError('Installed host testing is disabled.')
                receipt = self._receipt()
                if self.controller.admission.state != AdmissionState.READY_CLOSED:
                    raise AuthorityError('Fresh operational reconciliation required.')
                self.controller.admission.verify()
            return self.founder.issue_binding(purpose, self.policy.binding.data(),
                installation_receipt_digest=None if receipt is None else receipt.receipt_digest)
        if action == 'SUBMIT_FOUNDER_SIGNATURE' and set(args) == {'challenge_id', 'signature'}:
            return {'session': self.founder.submit(args)}
        if action == 'APPROVE_INSTALLATION' and set(args) == {'session'}:
            candidate, approved = self.candidate_reader()
            projection = approval_projection(candidate, approved, self.policy.binding)
            challenge, proof, verify = self.founder.delegate(args['session'], PURPOSES[0], self.policy.binding.data())
            verify()
            decision = dict(version=1, purpose=PURPOSES[0], binding=self.policy.binding.data(),
                approval_id=str(uuid4()), projection_digest=projection, signature_decision_digest=proof,
                challenge_digest=args['session'], activation=False, integration_services_approved=False)
            self.journal.record('INSTALLATION_APPROVAL_ISSUED', args['session'], decision)
            verify()
            return decision
        if action == 'BEGIN_HOST_TEST_SESSION' and set(args) == {'session'}:
            receipt = self._receipt()
            if self.tests is not None:
                raise AuthorityError('Only one host-test session per connection.')
            tests = HostTests(self.founder, receipt, self.controller, self.runner, self.journal, self.context)
            tests.audit_context=dict(self.request_context)
            result = tests.begin(args['session'])
            self.tests = tests
            self.journal('HOST_TEST_AUTHORIZATION_ACCEPTED', args['session'])
            return result
        if self.tests is not None:
            self._receipt()  # Detect receipt replacement before every operation.
            operations = {'ENROLL_HOST_TEST_CASE': self.tests.enroll,
                'RUN_HOST_TEST_CASE': self.tests.run, 'RECORD_HOST_TEST_EVIDENCE': self.tests.collect,
                'PREPARE_INTERRUPTION_TEST': self.tests.prepare_interruption,
                'RECONCILE_INTERRUPTION_TEST': self.tests.reconcile_interruption}
            if action in operations:
                return operations[action](args)
            if args == {}:
                operations = {'END_HOST_TEST_SESSION': self.tests.end,
                    'COMPLETE_HOST_TESTS': self.tests.complete, 'PREPARE_REBOOT_TEST': self.tests.prepare_reboot,
                    'RECONCILE_REBOOT_TEST': self.tests.reconcile_reboot}
                if action in operations:
                    return operations[action]()
        raise AuthorityError('Operation unsupported in M3.')

    def tick(self):
        if self.tests is not None and self.tests.session is not None:
            try:
                self._receipt()
                self.tests._live()
            except BaseException:
                self.close()
                raise

    def close(self):
        try:
            if self.tests is not None and self.tests.session is not None:
                self.tests.end()
        finally:
            self.founder.revoke_all()
