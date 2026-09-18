"""Founder-run one-shot PROD-01 inference command with dual request binding."""
import argparse
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import inspect
import json
import sys

from . import prod_contract
from .prod_contract import load_contract
from .prod_model_transport import (
    ALLOW_REDIRECTS, MAX_REQUESTS_PER_CYCLE, MAX_RESPONSE_BYTES, MAX_RETRIES,
    INITIAL_PREDECESSOR_INVALID, PRODUCT_PROPOSAL_SCHEMA_DIGEST, TIMEOUT_SECONDS,
    SAFE_TRANSPORT_FAILURE_REASONS, TRUSTED_ENDPOINT, TRUSTED_MODEL,
    build_product_model_request, parse_product_model_response, run_product_model_cycle,
)
from .prod_openai_http import (
    CONNECT_TIMEOUT_SECONDS, PROVIDER, PROVIDER_MODEL, OpenAIResponsesHTTPAdapter,
    project_openai_responses_request,
)
from .prod_prelive import (
    DevelopmentOneShotCredential, OwnerReviewedSource, _current_source_commit,
    synthetic_first_live_task,
)
from .serialization import canonical_json, digest
from .types import ValidationError

EXPECTED_SCHEMA_DIGEST = "c13b322dff0b8da89699966165b4d6f3ab69f50efbb0cc540ab8a75133e661ce"
FROZEN_ATS_0701_WIRE_FIXTURE_DIGEST = "bdc532506e2d4ce59a4dd41af440a0a4ef3bba21a865df5d9060c58c638f759d"
EXPECTED_ATS_1201_INTERNAL_REQUEST_DIGEST = "955d0900a989f64ee5eff07385d59cb4f0fa694c92b1ee775e396f51fdff853b"
EXPECTED_ATS_1201_WIRE_REQUEST_DIGEST = "34225f802e9f0d7161a357e3b1cb5ab133baad99a53f31e59602a6c5a9089804"
PARSER_CONTRACT = "RESPONSES_COMPLETED_ASSISTANT_SINGLE_OUTPUT_TEXT_V1"
VALIDATOR_CONTRACT = "validate_product_proposal"


def stable_contract_identity():
    """Return task-independent security/provider invariants for PROD-01 inference."""
    return {
        "contract_version": 1,
        "agent_id": "PROD-01",
        "role": "Product",
        "logical_model": TRUSTED_MODEL,
        "provider": PROVIDER,
        "provider_model": PROVIDER_MODEL,
        "endpoint": TRUSTED_ENDPOINT,
        "proposal_schema_digest": PRODUCT_PROPOSAL_SCHEMA_DIGEST,
        "tools": [],
        "max_requests": MAX_REQUESTS_PER_CYCLE,
        "max_retries": MAX_RETRIES,
        "allow_redirects": ALLOW_REDIRECTS,
        "timeout": {
            "connect_seconds": CONNECT_TIMEOUT_SECONDS,
            "read_seconds": TIMEOUT_SECONDS,
        },
        "max_response_bytes": MAX_RESPONSE_BYTES,
        "parser_contract": PARSER_CONTRACT,
        "parser_implementation_digest": _implementation_digest(
            parse_product_model_response),
        "proposal_validator": VALIDATOR_CONTRACT,
        "proposal_validator_implementation_digest": _implementation_digest(
            prod_contract),
        "resulting_knowledge_state": "WORKING",
        "initial_proposal_predecessor_null": True,
        "founder_auto_approval": False,
        "arch_routing": False,
    }


def _implementation_digest(source_object):
    return hashlib.sha256(inspect.getsource(source_object).encode("utf-8")).hexdigest()


def stable_contract_digest(value=None):
    return digest(stable_contract_identity() if value is None else value)


# Frozen only after deterministic regeneration from the reviewed implementation.
EXPECTED_STABLE_CONTRACT_DIGEST = "42abc180020e1d9815a2382556d27475717b13ffc2b3df38942005a3b8511759"


@dataclass(frozen=True)
class FirstLiveBindings:
    task: dict
    internal_request: dict
    internal_request_digest: str
    wire_request_digest: str
    stable_contract_digest: str


@dataclass(frozen=True)
class FirstLiveResult:
    checkpoint: str
    cycle: object


class FirstLiveFailure(ValidationError):
    """Bounded first-live failure with a non-secret classification."""

    def __init__(self, classification):
        super().__init__(classification)
        self.classification = classification


def prepare_first_live_bindings():
    if PRODUCT_PROPOSAL_SCHEMA_DIGEST != EXPECTED_SCHEMA_DIGEST:
        raise FirstLiveFailure("CONTRACT_MISMATCH")
    contract_value = stable_contract_digest()
    if contract_value != EXPECTED_STABLE_CONTRACT_DIGEST:
        raise FirstLiveFailure("CONTRACT_MISMATCH")
    contract = load_contract()
    if (contract["status"] != "NON_ACTIVE"
            or contract["authority_mode"] != "PROPOSAL_ONLY"
            or any(value is not False for value in contract["permissions"].values())):
        raise FirstLiveFailure("CONTRACT_MISMATCH")

    task = synthetic_first_live_task()
    internal, _ = build_product_model_request(task)
    internal_digest = digest(internal)
    wire = project_openai_responses_request(internal)
    wire_digest = digest(wire)
    if (internal_digest != EXPECTED_ATS_1201_INTERNAL_REQUEST_DIGEST
            or wire_digest != EXPECTED_ATS_1201_WIRE_REQUEST_DIGEST
            or internal.get("tools") != [] or wire.get("tools") != []):
        raise FirstLiveFailure("REQUEST_INSTANCE_MISMATCH")
    return FirstLiveBindings(
        task=deepcopy(task), internal_request=deepcopy(internal),
        internal_request_digest=internal_digest, wire_request_digest=wire_digest,
        stable_contract_digest=contract_value)


def _interactive_terminal_available():
    return sys.stdin.isatty() and sys.stderr.isatty()


def _run_first_live(reviewed_source, tty_check, prompt_fn, transport_factory):
    if type(reviewed_source) is not OwnerReviewedSource:
        raise FirstLiveFailure("SOURCE_MISMATCH")
    current = _current_source_commit()
    if current != reviewed_source.expected_commit:
        raise FirstLiveFailure("SOURCE_MISMATCH")
    bindings = prepare_first_live_bindings()
    if tty_check() is not True:
        raise FirstLiveFailure("TTY_REQUIRED")

    provider = None
    try:
        provider = DevelopmentOneShotCredential.prompt_hidden(prompt_fn)
        transport = transport_factory(provider)
        try:
            cycle = run_product_model_cycle(
                bindings.task, transport, require_initial_predecessor_null=True)
        except ValidationError as error:
            metadata = getattr(error, "audit_metadata", {})
            reason = metadata.get("failure_reason")
            safe_reasons = {
                "PROVIDER_ENVELOPE_INVALID", "STRUCTURED_JSON_INVALID",
                "PROPOSAL_SCHEMA_MISMATCH", "PROPOSAL_ID_INVALID",
                "TASK_BINDING_INVALID", "EVIDENCE_BINDING_INVALID",
                "KNOWLEDGE_STATE_INVALID", "AUTHORITY_CLAIM_REJECTED",
                "CONTENT_POLICY_REJECTED", INITIAL_PREDECESSOR_INVALID,
            } | SAFE_TRANSPORT_FAILURE_REASONS
            classification = (reason if type(reason) is str and reason in safe_reasons
                              and metadata.get("result_classification") in {
                                  "OUTPUT_REJECTED", "TRANSPORT_FAILED"}
                              else "PROVIDER_ERROR")
            raise FirstLiveFailure(classification) from None
        return FirstLiveResult(current, cycle)
    finally:
        if provider is not None:
            provider.discard()


def run_first_live(reviewed_source):
    """Production construction has no caller-selectable task, model, endpoint, or tools."""
    return _run_first_live(
        reviewed_source, _interactive_terminal_available, None,
        OpenAIResponsesHTTPAdapter)


def _run_first_live_for_tests(reviewed_source, tty_check, prompt_fn, transport_factory):
    """Explicit local test seam; the Founder CLI never calls this function."""
    return _run_first_live(reviewed_source, tty_check, prompt_fn, transport_factory)


def format_success(result):
    if type(result) is not FirstLiveResult:
        raise ValidationError("Invalid first-live result.")
    proposal = result.cycle.proposal
    lines = [
        "CHECKPOINT:", result.checkpoint,
        "TASK_ID:", result.cycle.task["task_id"],
        "AGENT:", "PROD-01",
        "MODEL:", PROVIDER_MODEL,
        "INFERENCE_REQUEST_COUNT:", "1",
        "TOOLS:", "0",
        "PROPOSAL_ID:", proposal["proposal_id"],
        "PROPOSAL_DIGEST:", result.cycle.proposal_digest,
        "KNOWLEDGE_STATE:", proposal["knowledge_state"],
        "VALIDATION:", "PASS",
        "PRODUCT REQUIREMENT PROPOSAL:",
        "TITLE:", canonical_json(proposal["title"]),
        "PROBLEM / USER NEED:", canonical_json(proposal["problem_user_need"]),
        "OBJECTIVE:", canonical_json(proposal["objective"]),
        "PROPOSED REQUIREMENT:", canonical_json(proposal["proposed_requirement"]),
        "ACCEPTANCE INTENT:", canonical_json(proposal["acceptance_intent"]),
        "DEPENDENCIES:", canonical_json(proposal["dependencies"]),
        "ASSUMPTIONS:", canonical_json(proposal["assumptions"]),
        "RISKS / OPEN QUESTIONS:", canonical_json(proposal["risks_open_questions"]),
        "PRIORITY RECOMMENDATION:", canonical_json(proposal["priority_recommendation"]),
        "EVIDENCE REFERENCES:", canonical_json(proposal["evidence_references"]),
    ]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python3 -B -m tools.agent_control.prod_first_live",
        description="Founder-run one-shot ATS-1201 PROD-01 inference.")
    parser.add_argument(
        "--expected-source-commit", required=True,
        help="Owner-reviewed checkpoint identity (40 lowercase hexadecimal characters).")
    args = parser.parse_args(argv)
    try:
        reviewed = OwnerReviewedSource.from_owner_authorization(
            args.expected_source_commit)
        print(format_success(run_first_live(reviewed)))
        return 0
    except FirstLiveFailure as error:
        print(json.dumps({"status": "BLOCKED", "classification": error.classification},
                         sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 2
    except (ValidationError, OSError):
        print(json.dumps({"status": "BLOCKED", "classification": "CONTRACT_MISMATCH"},
                         sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
