"""Development-only PROD-01 dry-run gate. This module has no live transmission path."""
import argparse
import getpass
import json
from pathlib import Path
import re
import subprocess

from .prod_contract import load_contract, validate_product_task
from .prod_model_transport import (
    ACCOUNT_MODEL_ACCESS, ALLOW_REDIRECTS, LOCAL_CONTRACT_VALIDATED,
    MAX_REQUESTS_PER_CYCLE, MAX_RETRIES, MAX_REQUEST_BYTES,
    PROVIDER_WIRE_COMPATIBILITY, TIMEOUT_SECONDS, TRUSTED_ENDPOINT, TRUSTED_MODEL,
    TRUST_ENVIRONMENT,
    build_product_model_request, project_product_context,
)
from .prod_openai_http import (
    CONNECT_TIMEOUT_SECONDS, HTTP_MAX_RETRIES, PROVIDER, PROVIDER_MODEL,
    READ_TIMEOUT_SECONDS,
)
from .serialization import canonical_json, digest, parse_json
from .types import ValidationError

EXPECTED_ENDPOINT = "https://api.openai.com/v1/responses"
EXPECTED_LOGICAL_MODEL = "PROD-01-STRUCTURED-MODEL-V1"
EXPECTED_PROVIDER = "OpenAI"
EXPECTED_PROVIDER_MODEL = "gpt-5.6-luna"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_CONSTRUCTION_TOKEN = object()
_SOURCE_CONSTRUCTION_TOKEN = object()
_COMMIT_PATTERN = re.compile(r"[0-9a-f]{40}\Z")

_FOUNDER_DIRECTION = {
    "kind": "SYNTHETIC_FOUNDER_DIRECTION",
    "statement": "Define the product requirements for displaying agent task history in the bonUP interface.",
    "version": 1,
}


class DevelopmentOneShotCredential:
    """Hidden-input, development-only credential retained until one consumption."""

    __slots__ = ("__secret", "__consumed")

    def __init__(self, secret, token):
        if token is not _CONSTRUCTION_TOKEN:
            raise ValidationError("Use the trusted development credential constructor.")
        if (type(secret) is not str or not secret or len(secret) > 4096
                or "\r" in secret or "\n" in secret):
            raise ValidationError("Invalid development credential input.")
        self.__secret = secret
        self.__consumed = False

    @classmethod
    def prompt_hidden(cls, prompt_fn=None):
        """Read from a hidden terminal prompt; never from argv, environment, or files."""
        reader = getpass.getpass if prompt_fn is None else prompt_fn
        secret = reader("OpenAI credential (hidden; development pre-live only): ")
        return cls(secret, _CONSTRUCTION_TOKEN)

    @classmethod
    def _for_tests(cls, secret):
        return cls(secret, _CONSTRUCTION_TOKEN)

    @property
    def present(self):
        return not self.__consumed and self.__secret is not None

    def credential(self):
        if not self.present:
            raise ValidationError("Development credential is unavailable or already consumed.")
        secret = self.__secret
        self.__secret = None
        self.__consumed = True
        return secret

    def discard(self):
        self.__secret = None
        self.__consumed = True

    def __repr__(self):
        return "<DevelopmentOneShotCredential DEVELOPMENT_PRE_LIVE_ONLY>"

    __str__ = __repr__

    def __getstate__(self):
        raise TypeError("Development credential serialization is prohibited.")

    def __reduce__(self):
        raise TypeError("Development credential serialization is prohibited.")


class OwnerReviewedSource:
    """Separate owner-reviewed source binding for a single pre-live review."""

    __slots__ = ("expected_commit",)

    def __init__(self, expected_commit, token):
        if token is not _SOURCE_CONSTRUCTION_TOKEN:
            raise ValidationError("Use the trusted owner-reviewed source constructor.")
        if type(expected_commit) is not str or not _COMMIT_PATTERN.fullmatch(expected_commit):
            raise ValidationError("Invalid owner-reviewed source identity.")
        self.expected_commit = expected_commit

    @classmethod
    def from_owner_authorization(cls, expected_commit):
        """Bind a commit supplied by the trusted launcher, never task/model content."""
        return cls(expected_commit, _SOURCE_CONSTRUCTION_TOKEN)

    def __repr__(self):
        return "<OwnerReviewedSource TRUSTED_LAUNCHER_INPUT>"


def synthetic_first_live_task():
    task = {
        "agent_id": "PROD-01",
        "task_id": "ATS-1201",
        "task_class": "PRODUCT_REQUIREMENT",
        "objective": _FOUNDER_DIRECTION["statement"],
        "input_references": [{
            "reference_type": "FOUNDER_DIRECTION",
            "reference_id": "FOUNDER-DIRECTION-PRELIVE-001",
            "digest": digest(_FOUNDER_DIRECTION),
            "knowledge_state": "DIRECT_FOUNDER",
        }],
    }
    return validate_product_task(task)


def _current_source_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=_REPO_ROOT, stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            check=True, timeout=5, env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"})
    except (OSError, subprocess.SubprocessError):
        raise ValidationError("Unable to verify trusted pre-live source identity.") from None
    return result.stdout.strip()


def run_preflight(credential_provider, reviewed_source):
    """Validate and preview one future request without constructing an HTTP adapter."""
    if type(credential_provider) is not DevelopmentOneShotCredential or not credential_provider.present:
        raise ValidationError("Trusted one-shot development credential is required.")
    if type(reviewed_source) is not OwnerReviewedSource:
        raise ValidationError("Trusted owner-reviewed source identity is required.")
    source_commit = _current_source_commit()
    if source_commit != reviewed_source.expected_commit:
        raise ValidationError("Pre-live source identity is not approved.")
    contract = load_contract()
    if (contract["agent_id"] != "PROD-01" or contract["role"] != "Product"
            or contract["status"] != "NON_ACTIVE"
            or contract["authority_mode"] != "PROPOSAL_ONLY"
            or any(value is not False for value in contract["permissions"].values())):
        raise ValidationError("PROD-01 pre-live authority boundary mismatch.")
    if (TRUSTED_ENDPOINT != EXPECTED_ENDPOINT or TRUSTED_MODEL != EXPECTED_LOGICAL_MODEL
            or PROVIDER != EXPECTED_PROVIDER or PROVIDER_MODEL != EXPECTED_PROVIDER_MODEL):
        raise ValidationError("PROD-01 pre-live provider binding mismatch.")
    if (MAX_REQUESTS_PER_CYCLE != 1 or MAX_RETRIES != 0 or HTTP_MAX_RETRIES != 0
            or ALLOW_REDIRECTS is not False or TRUST_ENVIRONMENT is not False
            or TIMEOUT_SECONDS != READ_TIMEOUT_SECONDS or CONNECT_TIMEOUT_SECONDS != 5):
        raise ValidationError("PROD-01 pre-live transport policy mismatch.")

    task = synthetic_first_live_task()
    context = project_product_context(task)
    request, request_bytes = build_product_model_request(task)
    behavior = set(context["behavior_contract"])
    required_behavior = {
        "PRODUCE_PRODUCT_REQUIREMENT_PROPOSAL_ONLY", "CANNOT_APPROVE", "CANNOT_ASSIGN",
        "CANNOT_GRANT_AUTHORITY", "CANNOT_EXECUTE", "CANNOT_DEPLOY", "CANNOT_PUBLISH",
        "CANNOT_ACTIVATE_AGENTS",
    }
    output = request.get("output_contract", {})
    schema = output.get("schema", {})
    knowledge = schema.get("properties", {}).get("knowledge_state", {})
    if (request.get("tools") != [] or output.get("type") != "PRODUCT_REQUIREMENT_PROPOSAL"
            or output.get("encoding") != "STRICT_JSON_SCHEMA"
            or output.get("strict") is not True
            or schema.get("additionalProperties") is not False
            or knowledge != {"type": "string", "const": "WORKING"}
            or behavior != required_behavior or len(request_bytes) > MAX_REQUEST_BYTES):
        raise ValidationError("PROD-01 pre-live request boundary mismatch.")

    preview = {
        "preflight_version": 1,
        "mode": "DRY_RUN_PREFLIGHT_ONLY",
        "gate_status": "READY_FOR_SEPARATE_LIVE_AUTHORIZATION",
        "live_check_status": "LIVE_CHECK_REQUIRED",
        "local_contract_validated": LOCAL_CONTRACT_VALIDATED,
        "provider_wire_compatibility": PROVIDER_WIRE_COMPATIBILITY,
        "account_model_access": ACCOUNT_MODEL_ACCESS,
        "source_commit": source_commit,
        "task_id": task["task_id"],
        "agent_id": task["agent_id"],
        "logical_model_id": TRUSTED_MODEL,
        "provider": PROVIDER,
        "provider_model_id": PROVIDER_MODEL,
        "endpoint_identity": TRUSTED_ENDPOINT,
        "request_digest": digest(request),
        "request_byte_count": len(request_bytes),
        "tool_count": len(request["tools"]),
        "max_request_count": MAX_REQUESTS_PER_CYCLE,
        "max_retries": MAX_RETRIES,
        "timeout_policy": {
            "connect_seconds": CONNECT_TIMEOUT_SECONDS,
            "read_seconds": READ_TIMEOUT_SECONDS,
        },
        "credential_present": "YES",
    }
    return parse_json(canonical_json(preview))


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m tools.agent_control.prod_prelive",
        description="Development-only PROD-01 dry-run preflight; transmission is unavailable.")
    parser.add_argument(
        "--expected-source-commit", required=True,
        help="Exact checkpoint commit from separate owner review (40 lowercase hex characters).")
    args = parser.parse_args(argv)
    provider = None
    try:
        reviewed_source = OwnerReviewedSource.from_owner_authorization(
            args.expected_source_commit)
        provider = DevelopmentOneShotCredential.prompt_hidden()
        print(json.dumps(run_preflight(provider, reviewed_source),
                         sort_keys=True, separators=(",", ":")))
        return 0
    except (ValidationError, OSError):
        print(json.dumps({"status": "BLOCKED", "error": "PROD-01 pre-live gate rejected."}),
              file=__import__("sys").stderr)
        return 2
    finally:
        if provider is not None:
            provider.discard()


if __name__ == "__main__":
    raise SystemExit(main())
