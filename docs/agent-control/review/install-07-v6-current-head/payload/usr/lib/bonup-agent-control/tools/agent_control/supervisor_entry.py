"""Fixed supervisor entrypoint; deliberately has no controller registry dependency.

Future installation target: /usr/lib/bonup-agent-control/supervisor. Privileged
adapters are fixed repository code; installation and host tests remain separate.
"""
from .service_runtime import ServiceConfig, ServiceLoop
from .types import AuthorityError

CONFIG = '/etc/bonup-agent-control/supervisor.json'


class SupervisorDriver:
    """Bind the existing database-free SupervisorEndpoint, never a runtime registry."""
    def __init__(self, endpoint, work, *, heartbeat, control):
        from .composition import SupervisorEndpoint
        if type(endpoint) is not SupervisorEndpoint:
            raise AuthorityError('Database-free supervisor endpoint required.')
        self.endpoint, self.work = endpoint, work
        self.heartbeat, self.control = heartbeat, control

    def reconcile(self):
        self.endpoint.disconnect(close_admission=False)
        clean = self.endpoint.backend.reconcile_unknown() is True
        self.endpoint.ready = clean and all(e['state'] == 'TERMINAL' for e in self.endpoint.launches.values())
        self.endpoint.last_heartbeat = self.endpoint.elapsed()
        return self.endpoint.ready

    def validate_config(self, config):
        return self.endpoint.generation == config.generation and self.endpoint.boot_id == config.boot_id

    def establish_admission(self):
        from .operational_enrollment import AdmissionState
        gate = self.endpoint.admission
        return 'OPEN' if self.endpoint.ready and (gate is None or
            gate.state == AdmissionState.ADMISSION_OPEN) else 'CLOSED'

    def protocol_ready(self):
        # Heartbeat/READY describe protocol servicing, never execution authority.
        return self.endpoint.ready

    def deadlines(self):
        self.endpoint.tick()

    def disconnect(self):
        self.endpoint.disconnect()

    def peer_alive(self):
        self.endpoint.last_heartbeat = self.endpoint.elapsed()


def start(*, adapters, config_path=CONFIG):
    if config_path != CONFIG:
        raise AuthorityError('Fixed supervisor configuration path required.')
    loop = None
    transport = None
    driver = None
    try:
        config = ServiceConfig.parse(adapters.load_config(config_path), component='supervisor',
            identity=adapters.identity(), boot_id=adapters.boot_id(), manifest_digest=adapters.verify_manifest())
        driver = adapters.compose_supervisor(config)  # No DB argument or writer adapter.
        if driver.validate_config(config) is not True:
            raise AuthorityError('Supervisor composition generation mismatch.')
        if driver.reconcile() is not True:
            raise AuthorityError('Supervisor reconciliation incomplete.')
        transport = adapters.listener(config)
        if transport.ready() is not True:
            raise AuthorityError('Controller-only endpoint unavailable.')
        if driver.establish_admission() not in ('CLOSED', 'OPEN'):
            raise AuthorityError('Supervisor admission state unknown.')
        loop = ServiceLoop(config, transport, driver.work, now=adapters.now,
            deadlines=driver.deadlines, control=driver.control, heartbeat=driver.heartbeat,
            disconnect=driver.disconnect, notifier=adapters.notify,
            peer_alive=driver.peer_alive, ready_evidence=getattr(driver, 'protocol_ready', lambda: driver.establish_admission() == 'OPEN'))
        loop.activate()
        return loop
    except BaseException:
        if hasattr(adapters, 'abort_startup'):
            adapters.abort_startup()
        if loop is not None:
            loop.shutdown()
        else:
            try:
                if driver is not None:
                    driver.disconnect()
            finally:
                if transport is not None:
                    transport.close()
        raise


def main(*, adapters=None):
    """Select the fixed installed factory; never load an adapter named by JSON."""
    if adapters is None:
        from .installed_runtime import build_installed_supervisor_adapters
        adapters = build_installed_supervisor_adapters()
        adapters.install_signals()
    loop = start(adapters=adapters)
    loop.run(adapters.shutdown_requested, adapters.wait)
