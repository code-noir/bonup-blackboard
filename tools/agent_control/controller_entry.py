"""Fixed controller entrypoint for future /usr/lib/bonup-agent-control/controller.

The installed main selects fixed adapters; explicit objects are reserved for tests.
No missing registry is initialized and no privileged backend is imported here.
"""
import os
from pathlib import Path
import stat

from .registry import Registry
from .runtime_schema import check_version
from .service_runtime import ServiceConfig, ServiceLoop
from .types import AuthorityError

CONFIG = '/etc/bonup-agent-control/controller.json'


class ControllerDriver:
    """Bind the existing ControllerRuntime to the startup/maintenance contract.

    work and heartbeat are trusted nonblocking transport adapters. No worker or
    model can supply these Python objects. Installed asynchronous execution and
    filesystem evidence wiring remain separate composition blocks.
    """
    def __init__(self, controller, work, *, heartbeat, deadlines):
        from .composition import ControllerRuntime
        if type(controller) is not ControllerRuntime:
            raise AuthorityError('Existing controller composition required.')
        self.controller, self.work = controller, work
        self.heartbeat, self.deadlines = heartbeat, deadlines

    def reconcile(self):
        rows = self.controller.reconcile()
        return all(row['state'] == 'TERMINAL' and row['cleanup_confirmed'] for row in rows)

    def validate_config(self, config):
        return (self.controller.sequencer.generation == config.peer.generation and
                self.controller.sequencer.boot_id == config.boot_id)

    def establish_admission(self):
        row = self.controller.runtime.db.execute("SELECT 1 FROM launch_attempts WHERE state!='TERMINAL'").fetchone()
        return 'CLOSED' if row else 'OPEN'

    def control(self):
        self.controller.tick()

    def disconnect(self):
        self.controller.tick(controller_alive=False)


def open_existing_registry(path):
    if path != '/var/lib/bonup-agent-control/control.sqlite3':
        raise AuthorityError('Unapproved operational registry path.')
    parent = Path(path).parent
    if any(p.is_symlink() for p in (Path(path), *Path(path).parents)):
        raise AuthorityError('Symlinked registry rejected.')
    directory = parent.stat()
    info = os.stat(path, follow_symlinks=False)  # Missing state is an error, never initialization.
    if (directory.st_uid != 3000 or directory.st_gid != 3000 or stat.S_IMODE(directory.st_mode) != 0o700 or
            info.st_uid != 3000 or info.st_gid != 3000 or stat.S_IMODE(info.st_mode) != 0o600 or
            not stat.S_ISREG(info.st_mode) or info.st_nlink != 1):
        raise AuthorityError('Registry must be private controller-owned state.')
    return Registry(path)


def validate_registry(registry):
    if check_version(registry.db) not in (2, 3) or registry.verify()['status'] == 'BLOCKED':
        raise AuthorityError('Operational registry verification failed.')


def start(*, adapters, config_path=CONFIG):
    """Compose an existing ControllerRuntime through explicit testable adapters.

    compose_controller(registry, config) returns a ControllerRuntime-compatible
    service driver: reconcile(), establish_admission(), deadlines(), control(),
    heartbeat(), disconnect(), and a nonblocking work queue. It owns all SQLite
    mutation; the event pump only delivers authenticated supervisor evidence.
    """
    if config_path != CONFIG:
        raise AuthorityError('Fixed controller configuration path required.')
    registry = None
    loop = None
    transport = None
    driver = None
    try:
        config = ServiceConfig.parse(adapters.load_config(config_path), component='controller',
            identity=adapters.identity(), boot_id=adapters.boot_id(), manifest_digest=adapters.verify_manifest())
        if adapters.capabilities() != ():
            raise AuthorityError('Controller must have zero capabilities.')
        registry = adapters.open_registry(config.registry_path)
        validate_registry(registry)
        driver = adapters.compose_controller(registry, config)
        if driver.validate_config(config) is not True:
            raise AuthorityError('Controller composition generation mismatch.')
        if driver.reconcile() is not True:
            raise AuthorityError('Controller reconciliation incomplete.')
        transport = adapters.listener(config)
        if transport.ready() is not True:
            raise AuthorityError('Controller listener unavailable.')
        if driver.establish_admission() not in ('CLOSED', 'OPEN'):
            raise AuthorityError('Controller admission state unknown.')
        loop = ServiceLoop(config, transport, driver.work, now=adapters.now,
            deadlines=driver.deadlines, control=driver.control, heartbeat=driver.heartbeat,
            disconnect=driver.disconnect, notifier=adapters.notify)
        loop.activate()
        return ControllerService(loop, registry)
    except BaseException:
        if hasattr(adapters, 'abort_startup'):
            adapters.abort_startup()
        try:
            if loop is not None:
                loop.shutdown()
            else:
                try:
                    if driver is not None:
                        driver.disconnect()
                finally:
                    if transport is not None:
                        transport.close()
        finally:
            if registry is not None:
                registry.close()
        raise


class ControllerService:
    def __init__(self, loop, registry):
        self.loop, self.registry = loop, registry
        self.closed = False

    def close(self):
        if not self.closed:
            self.closed = True
            try:
                self.loop.shutdown()
            finally:
                self.registry.close()


def main(*, adapters=None):
    """Fixed installed composition; no environment-selected adapter factory."""
    if adapters is None:
        from .installed_runtime import build_installed_controller_adapters
        adapters = build_installed_controller_adapters()
        adapters.install_signals()
    service = start(adapters=adapters)
    try:
        service.loop.run(adapters.shutdown_requested, adapters.wait)
    finally:
        service.close()
