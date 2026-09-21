"""Privileged Agent Control runtime installer entrypoint.

The command defaults to a read-only dry run.  See
``tools.agent_control.privileged_installer`` for the fail-closed contract.
"""
import sys
from pathlib import Path

# Keep the standalone repository entrypoint usable from any working directory;
# the privileged artifact is still expected to be staged and hash-verified
# before a root caller uses it.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.agent_control.privileged_installer import main
from tools.agent_control.types import AuthorityError, ValidationError


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AuthorityError, ValidationError) as error:
        raise SystemExit(str(error))
