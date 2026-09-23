"""Evaluation of trusted lifecycle observations; no public result submission."""

def verify_canary(case, row, output, lifecycle):
    if not row['cleanup_confirmed'] or row['state'] != 'TERMINAL' or row['exit_code'] != 0:
        return False
    if not all(lifecycle[k] is True for k in ('resources_verified','exec_confirmed','cleanup_confirmed')):
        return False
    if case.test_id == 'bounded_output':
        return all(output[name] == {'retained': 65536, 'truncated': True} for name in ('stdout', 'stderr'))
    if case.test_id == 'watchdog':
        # Additional supervisor/service evidence is mandatory. Never infer these
        # properties merely from an exit status or delivery of a message.
        return False
    return all(not output[name]['truncated'] for name in ('stdout', 'stderr'))
