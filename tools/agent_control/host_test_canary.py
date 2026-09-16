"""Fixed synthetic payload, executed only by a separately authorized host test.

Standalone stdlib-only script suitable for python3 -I -S. Failure never emits a
PASS assertion. The controller checks trusted exec/cleanup evidence as well.
"""
import json
import os
import resource
import socket
import sys


def main(argv):
    if len(argv) != 1:
        raise SystemExit(64)
    case = argv[0]
    if case == 'uid_gid_drop':
        assert os.getuid() == os.geteuid() == 3002 and os.getgid() == os.getegid() == 3002
    elif case == 'empty_groups':
        assert os.getgroups() == []
    elif case == 'capability_bounds':
        import re
        with open('/proc/self/status', encoding='ascii') as stream:
            status = {}
            for line in stream:
                key,value=line.split(':',1)
                assert key not in status
                status[key]=value
        assert all(re.fullmatch(r'[0-9a-fA-F]{1,16}',status[k].strip()) for k in
                   ('CapInh','CapPrm','CapEff','CapBnd','CapAmb'))
        assert all(int(status[k].strip(), 16) == 0 for k in ('CapInh', 'CapPrm', 'CapEff', 'CapBnd', 'CapAmb'))
        assert status['NoNewPrivs'].strip() == '1'
    elif case == 'bwrap_apparmor':
        assert socket.if_nameindex() == [(1, 'lo')]
        with open('/proc/self/attr/current', encoding='ascii') as stream:
            assert 'unconfined' not in stream.read(4096)
    elif case == 'pinned_mounts':
        with open('/work/frontend/example.ts', 'rb') as stream:
            assert stream.read(128) == b'bonup synthetic host-test canary\n'
        try:
            fd = os.open('/work/frontend/example.ts', os.O_WRONLY)
        except PermissionError:
            pass
        except OSError as error:
            import errno
            assert error.errno == errno.EROFS
        else:
            os.close(fd)
            raise AssertionError('Canary export is writable')
    elif case == 'cgroup_limits':
        assert resource.getrlimit(resource.RLIMIT_NOFILE) == (256, 256)
        assert resource.getrlimit(resource.RLIMIT_FSIZE) == (16777216, 16777216)
        assert resource.getrlimit(resource.RLIMIT_CORE) == (0, 0)
        # Cgroup limits must additionally be observed by the supervisor; an
        # unmounted host cgroup filesystem inside confinement is expected.
    elif case == 'bounded_output':
        for fd in (1, 2):
            remaining = 65537
            while remaining:
                remaining -= os.write(fd, b'x' * min(4096, remaining))
    elif case == 'tmpfs_limits':
        for path, maximum in (('/work', 134217728), ('/home/worker', 16777216), ('/tmp', 16777216)):
            info = os.statvfs(path)
            assert 0 < info.f_blocks * info.f_frsize <= maximum
            if path == '/work':
                assert 0 < info.f_files <= 16384
    elif case == 'descendant_termination':
        import signal
        read_fd, write_fd = os.pipe()
        if os.fork() == 0:
            os.close(read_fd)
            os.setsid()
            os.write(write_fd, b'R')
            os.close(write_fd)
            while True:
                signal.pause()
        os.close(write_fd)
        assert os.read(read_fd, 1) == b'R'
        os.close(read_fd)
    elif case in ('controller_crash', 'supervisor_crash', 'reboot_reconciliation', 'watchdog'):
        import signal
        # Remain alive until the bounded normal supervisor deadline or the
        # externally authorized interruption. A normal exit cannot prove a crash.
        while True:
            signal.pause()
    elif case not in ('confined_release_gate', 'namespace_installation_identity', 'execution_start_proof',
                      'socket_activation', 'kernel_peer_authentication_operational_enrollment', 'watchdog',
                      'controller_crash', 'supervisor_crash', 'reboot_reconciliation'):
        raise SystemExit(64)
    # The remaining cases require controller/supervisor lifecycle observations.
    # Reaching this payload is only their canary, not proof of the whole test.


if __name__ == '__main__':
    main(sys.argv[1:])
