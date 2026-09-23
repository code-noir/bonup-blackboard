"""Controller-owned host-test session and evidence lifecycle.

The runner is the normal controller composition, with a fixed catalog enrollment
adapter. Results are pulled from the controller's authenticated lifecycle state;
there is deliberately no submit-result/PASS request.
"""
from dataclasses import asdict
from uuid import uuid4

from .authority_installation import InstalledReceipt
from .founder_crypto import PURPOSES
from .host_test_catalog import CATALOG, CATALOG_DIGEST, IDS, VERSION, select
from .operational_enrollment import AdmissionState
from .serialization import digest
from .types import AuthorityError


class HostTests:
    def __init__(self, founder, receipt, controller, runner, journal, runtime_context):
        if type(receipt) is not InstalledReceipt:
            raise AuthorityError('Verified installed receipt required.')
        self.founder, self.receipt, self.controller = founder, receipt, controller
        self.runner, self.journal, self.context = runner, journal, runtime_context
        self.session = self.verify = None
        self.enrolled, self.launches, self.results = {}, {}, {}
        self.initial_context = None
        self.accepted_contexts = []
        self.audit_context = {}
        self.correlations = {}
        self.authorized_requests = set()

    def _live(self):
        if self.session is None or self.verify is None:
            raise AuthorityError('Host-test session is closed.')
        try:
            self.verify()
            if self.context() != self.initial_context:
                raise AuthorityError('Runtime changed; fresh enrollment required.')
        except BaseException:
            self.abort('REVOKE')
            raise

    def _binding(self, session):
        return dict(session_digest=self.controller.admission.session,
                    host_session_digest=session,installation_digest=digest(self.receipt.binding.data()))

    def begin(self, session):
        admission = self.controller.admission
        if self.session is not None or admission.state != AdmissionState.READY_CLOSED:
            raise AuthorityError('Host testing requires closed reconciled admission.')
        if self.controller.runtime.db.execute("SELECT 1 FROM launch_attempts WHERE state!='TERMINAL'").fetchone():
            raise AuthorityError('Uncertain launches block host testing.')
        challenge, proof, verify = self.founder.delegate(session, PURPOSES[1], self.receipt.binding.data(),
            installation_receipt_digest=self.receipt.receipt_digest)
        context = self.context()
        if challenge['process']['boot_id'] != context['boot_id']:
            raise AuthorityError('Founder and runtime boot mismatch.')
        verify()
        self.session, self.verify, self.initial_context = session, verify, context
        self.accepted_contexts = [context]
        try:
            self.journal.record('HOST_TEST_SESSION_BEGUN', session,
                dict(receipt=self.receipt.receipt_digest, signature_decision=proof,
                     runtime=context, activation=False,correlation=dict(self.audit_context)))
            admission.begin_host_tests(self.runner.execution_ids(), self._live)
            binding=self._binding(session)
            response = self.controller.remote._call('OPEN_HOST_TEST_ADMISSION', str(uuid4()),
                binding, 'HOST_TEST_ADMISSION_EVIDENCE',version=4)
            if response != dict(binding,closed=False,cleanup_confirmed=False):
                raise AuthorityError('Supervisor host-test session mismatch.')
        except BaseException:
            self.abort('FAILURE')
            raise
        return {'mode': 'HOST_TEST_ONLY', 'activation': False}

    def enroll(self, request):
        self._live()
        case = select(request)
        if case.test_id in self.enrolled:
            raise AuthorityError('Test enrollment replay.')
        enrollment = self.runner.enroll(case, self.verify)
        self.journal.record('HOST_TEST_CASE_ENROLLED', self.audit_context.get('request_id',self.session + case.test_id),
            dict(test_id=case.test_id, catalog=CATALOG_DIGEST, receipt=self.receipt.receipt_digest,
                 execution_id=enrollment.execution_id,correlation=dict(self.audit_context)))
        self.enrolled[case.test_id] = enrollment
        return {'test_id': case.test_id, 'enrolled': True}

    def run(self, request):
        self._live()
        case = select(request)
        if case.test_id not in self.enrolled or case.test_id in self.launches:
            raise AuthorityError('Fresh catalog enrollment required.')
        context=dict(self.audit_context)
        context.setdefault('request_id',str(uuid4()))
        context.update(session_id=self.session,test_id=case.test_id,receipt=self.receipt.receipt_digest)
        self.correlations[case.test_id]=context
        # Reserve before any dispatch; ambiguous delivery cannot be retried.
        self.launches[case.test_id] = None
        def authorized(launch):
            context['launch_id']=launch
            self.authorized_requests.add(context['request_id'])
            self.journal.record('HOST_TEST_AUTHORIZED',context['request_id'],context)
        launch = self.runner.run(case, self.enrolled[case.test_id],request_id=context['request_id'],authorized=authorized)
        self.launches[case.test_id] = launch
        self.journal.record('HOST_TEST_CASE_STARTED',context['request_id'],context)
        return {'test_id': case.test_id, 'launch_id': launch}

    def collect(self, request):
        self._live()
        case = select(request)
        launch = self.launches.get(case.test_id)
        if launch is None or case.test_id in self.results:
            raise AuthorityError('Missing launch or evidence replay.')
        observation = self.runner.collect(case, launch)
        if observation is None:
            raise AuthorityError('Lifecycle evidence is not complete.')
        # Runner owns observations. The public operation accepts only test_id.
        result = dict(receipt=self.receipt.receipt_digest, binding=self.receipt.binding.data(),
            catalog_version=VERSION, catalog_digest=CATALOG_DIGEST, test_id=case.test_id,
            launch_id=launch, worker=list(case.worker), **self.context(),
            evidence_digest=digest(observation), result='PASS' if observation['passed'] else 'FAIL',
            correlation=dict(self.correlations[case.test_id]))
        self._live()
        self.journal.record('HOST_TEST_CASE_' + ('PASSED' if observation['passed'] else 'FAILED'),
                            self.correlations[case.test_id]['request_id'], result)
        self.results[case.test_id] = result
        return dict(result)

    def complete(self):
        self._live()
        from .schema import valid_format
        fields={'receipt','binding','catalog_version','catalog_digest','test_id','launch_id','worker',
                'boot_id','controller_generation','supervisor_generation','evidence_digest','result','correlation'}
        valid = set(self.results) == set(IDS) and all(
            type(row) is dict and set(row)==fields and type(row['catalog_version']) is int and
            row['test_id']==name and row['catalog_version']==VERSION and row['worker']==list(CATALOG[name].worker) and
            valid_format('uuid',row['launch_id']) and valid_format('sha256',row['evidence_digest']) and
            row['result'] == 'PASS' and row['receipt'] == self.receipt.receipt_digest and
            row['binding'] == self.receipt.binding.data() and row['catalog_digest'] == CATALOG_DIGEST and
            any(all(row[k] == v for k, v in context.items()) for context in self.accepted_contexts)
            for name,row in self.results.items())
        valid = valid and len({row['launch_id'] for row in self.results.values()})==len(IDS)
        if not valid:
            self.journal.record('HOST_TEST_COMPLETION_DENIED',self.audit_context.get('request_id',self.session),
                dict(receipt=self.receipt.receipt_digest,evidence_digest=digest(self.results)))
            raise AuthorityError('All exact non-stale mandatory test results are required.')
        evidence=dict(receipt=self.receipt.receipt_digest,correlation=dict(self.audit_context),
                      evidence_digest=digest(self.results),results=dict(self.results),activation=False)
        correlation=self.audit_context.get('request_id',self.session)
        self._close('COMPLETE')
        self.journal.record('HOST_TEST_COMPLETION_ACCEPTED',correlation,evidence)
        return dict(completed=True, activation=False, mode='CLOSED',evidence_digest=evidence['evidence_digest'])

    def prepare_interruption(self, request):
        self._live()
        case = select(request)
        if case.test_id not in ('reboot_reconciliation','controller_crash','supervisor_crash','watchdog'):
            raise AuthorityError('Only a declared interruption case may be armed.')
        if case.test_id not in self.launches or self.launches[case.test_id] is None:
            raise AuthorityError('Reboot canary must traverse the normal launch path first.')
        launch = self.launches[case.test_id]
        armed = self.runner.arm_interruption(case, launch)
        pending = dict(receipt=self.receipt.receipt_digest, binding=self.receipt.binding.data(),
            catalog_digest=CATALOG_DIGEST, test_id=case.test_id,
            launch_id=launch, prior_results=self.results, prior_contexts=self.accepted_contexts,
            correlation=dict(self.correlations.get(case.test_id,self.audit_context)),armed=armed, **self.context())
        self.journal.record('HOST_TEST_REBOOT_PENDING', self.receipt.receipt_digest + ':' + case.test_id, pending)
        # Close future admission/release, not the running canary. Normal service
        # loss and the immutable execution deadline still enforce termination.
        self._close('INTERRUPTION')
        return dict(pending=True, activation=False)

    def reconcile_interruption(self, request):
        # A new signed host-test session is necessary; reconnect alone is insufficient.
        self._live()
        case = select(request)
        if case.test_id not in ('reboot_reconciliation','controller_crash','supervisor_crash','watchdog'):
            raise AuthorityError('Unknown interruption case.')
        pending = self.journal.load(self.receipt.receipt_digest + ':' + case.test_id)
        row = pending['evidence']
        current = self.context()
        if (pending['event'] != 'HOST_TEST_REBOOT_PENDING' or
                row['receipt'] != self.receipt.receipt_digest or row['binding'] != self.receipt.binding.data() or
                row['catalog_digest'] != CATALOG_DIGEST or row['test_id'] != case.test_id or
                row['controller_generation'] == current['controller_generation'] or
                (case.test_id in ('reboot_reconciliation','supervisor_crash') and
                    row['supervisor_generation'] == current['supervisor_generation']) or
                (case.reboot and row['boot_id'] == current['boot_id']) or
                self.controller.runtime.db.execute("SELECT 1 FROM launch_attempts WHERE state!='TERMINAL' OR cleanup_confirmed!=1").fetchone()):
            raise AuthorityError('Fresh boot, enrollment and complete cleanup required.')
        from .serialization import parse_json
        launch_row=self.controller.runtime.launch(row['launch_id'])
        armed=row['armed']
        witness=self.runner.interruption_evidence(case,row)
        identity_fields=('launch_id','process','target','cgroup_name','cgroup_identity')
        if (set(witness)!=set(identity_fields)|{'phase','worker_alive','observed_boottime_ns'} or
                armed['phase']!='INTERRUPTION_ARMED' or witness['phase']!='TARGET_INTERRUPTED' or
                witness['worker_alive'] is not True or
                any(witness[k]!=armed[k] for k in identity_fields) or
                type(witness['observed_boottime_ns']) is not int or
                witness['observed_boottime_ns']<=armed['armed_boottime_ns'] or
                launch_row['state']!='TERMINAL' or not launch_row['cleanup_confirmed'] or
                launch_row['cgroup_name']!=armed['cgroup_name'] or
                parse_json(launch_row['process_identity'])!=armed['process']):
            raise AuthorityError('Exact live-at-interruption and cleanup evidence required.')
        if not case.reboot:
            launch = next((launch for launch in self.launches.values() if launch is not None and
                self.controller.runtime.launch(launch)['state']=='TERMINAL'),None)
            if launch is None:
                raise AuthorityError('Fresh completed post-restart canary required.')
            events = self.runner.status(launch)['service_events']
            old = {e['cursor'] for e in armed['prior_service_events']}
            unit = 'bonup-agent-supervisor.service' if case.test_id=='supervisor_crash' else 'bonup-agent-controller.service'
            reason = 'WATCHDOG' if case.test_id=='watchdog' else 'PROCESS_KILLED'
            if not any(e['cursor'] not in old and e['unit']==unit and e['reason']==reason and
                       e['boot_id']==row['boot_id'] for e in events):
                raise AuthorityError('Missing fresh systemd interruption evidence.')
        previous_context={k:row[k] for k in current}
        contexts=row['prior_contexts']
        if (type(contexts) is not list or not 1<=len(contexts)<=18 or previous_context not in contexts or
                any(type(context) is not dict or set(context)!=set(current) for context in contexts)):
            raise AuthorityError('Invalid runtime evidence chain.')
        for name, previous in row['prior_results'].items():
            if (name not in CATALOG or previous['test_id']!=name or previous['receipt']!=self.receipt.receipt_digest or
                    previous['binding']!=self.receipt.binding.data() or previous['catalog_digest']!=CATALOG_DIGEST or
                    not any(all(previous[k]==v for k,v in context.items()) for context in contexts)):
                raise AuthorityError('Invalid pre-interruption evidence chain.')
        result = dict(receipt=row['receipt'],binding=row['binding'],catalog_digest=CATALOG_DIGEST,
            test_id=case.test_id,launch_id=row['launch_id'], **current,catalog_version=VERSION,
            worker=list(case.worker),correlation=row['correlation'],evidence_digest=digest(dict(pending=pending,witness=witness,
                phases=['PREPARED','RELEASED','EXEC_START_CONFIRMED','CANARY_RUNNING','INTERRUPTION_ARMED',
                        'TARGET_INTERRUPTED','RECONCILIATION','CLEANUP_EVIDENCE','TEST_RESULT'])),result='PASS')
        self.journal.record('HOST_TEST_CASE_PASSED', self.receipt.receipt_digest + ':' + case.test_id, result)
        self.accepted_contexts.extend(context for context in contexts if context not in self.accepted_contexts)
        self.results.update(row['prior_results'])
        self.results[case.test_id] = result
        return result

    def prepare_reboot(self):
        return self.prepare_interruption({'test_id':'reboot_reconciliation'})

    def reconcile_reboot(self):
        return self.reconcile_interruption({'test_id':'reboot_reconciliation'})

    def end(self):
        self._live()
        return self._close('END')

    def abort(self, reason='FAILURE'):
        if self.session is not None:
            return self._close(reason)

    def _close(self, reason):
        session=self.session
        if session is None:raise AuthorityError('Host-test authority already consumed.')
        binding=self._binding(session)
        correlation=self.audit_context.get('request_id',session)
        evidence=dict(binding,reason=reason,receipt=self.receipt.receipt_digest,
                      correlation=dict(self.audit_context),activation=False)
        # The controller thread owns admission/SQLite. Reentrant operations now
        # fail before RPC, audit, or cleanup can block. No delegation is restored.
        self.controller.admission.end_host_tests()
        self.session=self.verify=None
        try:
            try:
                self.founder.revoke_all()
                self.journal.record('HOST_TEST_CLOSURE_REQUESTED',correlation,evidence)
            finally:
                response=self.controller.remote._call('CLOSE_HOST_TEST_ADMISSION',str(uuid4()),
                    dict(binding,reason=reason),'HOST_TEST_ADMISSION_EVIDENCE',version=4)
                expected=dict(binding,closed=True,cleanup_confirmed=reason!='INTERRUPTION')
                if response!=expected:
                    raise AuthorityError('Supervisor host-test closure uncertain.')
            if reason!='INTERRUPTION':
                rows=self.controller.runtime.db.execute("SELECT launch_id FROM launch_attempts WHERE state!='TERMINAL'").fetchall()
                for (launch,) in rows:
                    row=self.controller.stop(launch,'CANCELLED')
                    if row['state']!='TERMINAL' or not row['cleanup_confirmed']:
                        raise AuthorityError('Host-test cleanup remains uncertain.')
            self.journal.record('HOST_TEST_SUPERVISOR_CLOSED',correlation,evidence)
            self.journal.record('HOST_TEST_AUTHORITY_CONSUMED',correlation,evidence)
            self.journal.record('HOST_TEST_SESSION_ENDED',correlation,evidence)
        except BaseException:
            try:self.controller.remote.invalidate_channel()
            finally:
                self.controller.admission.end_host_tests()
                self.journal.record('HOST_TEST_CLOSURE_UNCERTAIN',correlation,evidence)
            raise
        return {'mode':'CLOSED','activation':False}
