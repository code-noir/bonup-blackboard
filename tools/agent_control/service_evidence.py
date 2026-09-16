"""Read-only, bounded systemd evidence for the two installed control services.

No unit operation or caller-selected command/path is exposed. Invocation occurs
only for the extended authenticated lifecycle-status query, never on import.
"""
import os
import selectors
import stat
import subprocess
import time
from uuid import UUID

from .protocol import bounded_json
from .types import AuthorityError

EXECUTABLE = '/usr/bin/journalctl'
UNITS = ('bonup-agent-controller.service', 'bonup-agent-supervisor.service')


def event_reason(unit, message):
    if unit not in UNITS or type(message) is not str:
        raise AuthorityError('Unknown service event identity.')
    # Accept only the exact event, optionally prefixed by that same unit.
    # Another unit's prefix and arbitrary suffixes remain unmatched.
    if message.startswith(unit+': '):message=message[len(unit)+2:]
    return ('WATCHDOG' if message=="Failed with result 'watchdog'." else
            'PROCESS_KILLED' if message=='Main process exited, code=killed, status=9/KILL' else None)


def recent_service_events():
    fd = os.open('/', os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC)
    try:
        for index, part in enumerate(('usr','bin','journalctl')):
            child = os.open(part,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|
                (os.O_DIRECTORY if index < 2 else 0),dir_fd=fd)
            os.close(fd);fd=child
            info=os.fstat(fd)
            if info.st_uid != 0 or info.st_gid != 0 or info.st_mode & 0o6022:
                raise AuthorityError('Untrusted systemd evidence executable.')
        if not stat.S_ISREG(info.st_mode):
            raise AuthorityError('Missing systemd evidence executable.')
        results=[]
        for unit in UNITS:
            unit_results=[]
            process=subprocess.Popen((EXECUTABLE,'--no-pager','--quiet','--output=json','--lines=16',
                '_PID=1','UNIT='+unit),executable=f'/proc/self/fd/{fd}',pass_fds=(fd,),close_fds=True,
                stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                cwd='/',env={'LANG':'C','LC_ALL':'C'},shell=False)
            try:
                deadline=time.monotonic()+2
                data=bytearray()
                with selectors.DefaultSelector() as selector:
                    os.set_blocking(process.stdout.fileno(),False)
                    selector.register(process.stdout,selectors.EVENT_READ)
                    while True:
                        remaining=deadline-time.monotonic()
                        if remaining<=0 or not selector.select(remaining):
                            raise AuthorityError('Service evidence timeout.')
                        chunk=os.read(process.stdout.fileno(),min(4096,65537-len(data)))
                        if not chunk:break
                        data.extend(chunk)
                        if len(data)>65536:raise AuthorityError('Service evidence exceeds bound.')
                if process.wait(timeout=max(0,deadline-time.monotonic())) != 0:
                    raise AuthorityError('Service evidence unavailable.')
                for line in bytes(data).splitlines():
                    row=bounded_json(line)
                    if row.get('_PID')!='1' or row.get('UNIT')!=unit:
                        raise AuthorityError('Wrong service evidence provenance.')
                    message=row.get('MESSAGE','')
                    reason=event_reason(unit,message)
                    if reason is None:continue
                    cursor=row.get('__CURSOR')
                    if type(cursor) is not str or not 1<=len(cursor)<=512:
                        raise AuthorityError('Unbounded service evidence cursor.')
                    unit_results.append(dict(unit=unit,reason=reason,cursor=cursor,
                        boot_id=str(UUID(row['_BOOT_ID']))))
                results.extend(unit_results[-2:])
            finally:
                if process.poll() is None:process.kill()
                process.wait();process.stdout.close()
        return results
    finally:
        os.close(fd)
