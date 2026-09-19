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
    PROPOSAL_ARTIFACT_PERSISTENCE_FAILED,
    SAFE_TRANSPORT_FAILURE_REASONS, TRUSTED_ENDPOINT, TRUSTED_MODEL,
    build_product_model_request, parse_product_model_response, run_product_model_cycle,
)
from .prod_openai_http import (
    CONNECT_TIMEOUT_SECONDS, PROVIDER, PROVIDER_MODEL, OpenAIResponsesHTTPAdapter,
    project_openai_responses_request,
)
from .prod_response_capture import (
    CAPTURE_MODE, PrivateResponseCapture, cleanup_private_response_captures,
)
from .prod_artifact import (
    ARTIFACT_DIRECTORY, ARTIFACT_MAX_BYTES, ARTIFACT_VERSION, ProposalArtifactStore,
)
from .prod_prelive import (
    DevelopmentOneShotCredential, OwnerReviewedSource, _current_source_commit,
    synthetic_first_live_task,
)
from .serialization import canonical_json, digest, parse_json
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
        "response_transport_implementation_digest": _implementation_digest(
            OpenAIResponsesHTTPAdapter),
        "proposal_validator": VALIDATOR_CONTRACT,
        "proposal_validator_implementation_digest": _implementation_digest(
            prod_contract),
        "proposal_artifact": {
            "version": ARTIFACT_VERSION,
            "directory": ARTIFACT_DIRECTORY,
            "max_bytes": ARTIFACT_MAX_BYTES,
            "implementation_digest": _implementation_digest(ProposalArtifactStore),
        },
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
EXPECTED_STABLE_CONTRACT_DIGEST = "beb8f2df0db16fe83a2906187c23867d0371b16fc7f80b971504ecef2cee1e4d"


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
    capture_result: dict = None


class FirstLiveFailure(ValidationError):
    """Bounded first-live failure with a non-secret classification."""

    def __init__(self, classification, provider_structure=None, capture_result=None):
        super().__init__(classification)
        self.classification = classification
        self.provider_structure = (None if provider_structure is None
                                   else parse_json(canonical_json(provider_structure)))
        self.capture_result = (None if capture_result is None
                               else parse_json(canonical_json(capture_result)))


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


def _run_first_live(reviewed_source, tty_check, prompt_fn, transport_factory,
                    *, private_response_capture=False, proposal_artifact_store=None):
    if type(reviewed_source) is not OwnerReviewedSource:
        raise FirstLiveFailure("SOURCE_MISMATCH")
    current = _current_source_commit()
    if current != reviewed_source.expected_commit:
        raise FirstLiveFailure("SOURCE_MISMATCH")
    bindings = prepare_first_live_bindings()
    if tty_check() is not True:
        raise FirstLiveFailure("TTY_REQUIRED")
    if type(private_response_capture) is not bool:
        raise FirstLiveFailure("CAPTURE_MODE_INVALID")

    provider = None
    capture = PrivateResponseCapture() if private_response_capture else None
    try:
        provider = DevelopmentOneShotCredential.prompt_hidden(prompt_fn)
        transport = transport_factory(
            provider, private_response_capture=capture)
        try:
            cycle = run_product_model_cycle(
                bindings.task, transport, require_initial_predecessor_null=True,
                proposal_artifact_store=proposal_artifact_store,
                source_checkpoint=current)
        except ValidationError as error:
            metadata = getattr(error, "audit_metadata", {})
            reason = metadata.get("failure_reason")
            safe_reasons = {
                "PROVIDER_ENVELOPE_INVALID", "STRUCTURED_JSON_INVALID",
                "PROPOSAL_SCHEMA_MISMATCH", "PROPOSAL_ID_INVALID",
                "TASK_BINDING_INVALID", "EVIDENCE_BINDING_INVALID",
                "KNOWLEDGE_STATE_INVALID", "AUTHORITY_CLAIM_REJECTED",
                "CONTENT_POLICY_REJECTED", INITIAL_PREDECESSOR_INVALID,
                PROPOSAL_ARTIFACT_PERSISTENCE_FAILED,
            } | SAFE_TRANSPORT_FAILURE_REASONS
            classification = (reason if type(reason) is str and reason in safe_reasons
                              and metadata.get("result_classification") in {
                                  "OUTPUT_REJECTED", "TRANSPORT_FAILED"}
                              else "PROVIDER_ERROR")
            structure = metadata.get("provider_structure")
            raise FirstLiveFailure(
                classification, structure,
                getattr(transport, "private_response_capture_result", None)) from None
        return FirstLiveResult(
            current, cycle,
            getattr(transport, "private_response_capture_result", None))
    finally:
        if provider is not None:
            provider.discard()


def _production_transport(provider, *, private_response_capture=None):
    return OpenAIResponsesHTTPAdapter(
        provider, private_response_capture=private_response_capture)


def run_first_live(reviewed_source):
    """Production construction has no caller-selectable task, model, endpoint, or tools."""
    return _run_first_live(
        reviewed_source, _interactive_terminal_available, None,
        _production_transport, proposal_artifact_store=ProposalArtifactStore())


def _run_private_response_capture(reviewed_source):
    """Founder CLI-only construction for one private response capture."""
    return _run_first_live(
        reviewed_source, _interactive_terminal_available, None,
        _production_transport, private_response_capture=True,
        proposal_artifact_store=ProposalArtifactStore())


def _run_first_live_for_tests(reviewed_source, tty_check, prompt_fn, transport_factory,
                              *, private_response_capture=False,
                              proposal_artifact_store=None):
    """Explicit local test seam; the Founder CLI never calls this function."""
    def test_transport(provider, *, private_response_capture=None):
        if private_response_capture is None:
            return transport_factory(provider)
        return transport_factory(
            provider, private_response_capture=private_response_capture)

    return _run_first_live(
        reviewed_source, tty_check, prompt_fn, test_transport,
        private_response_capture=private_response_capture,
        proposal_artifact_store=proposal_artifact_store)


def _capture_lines(capture_result):
    if capture_result is None:
        return []
    created = capture_result.get("created") is True
    path = capture_result.get("path") if created else "NONE"
    return [
        "CAPTURE_CREATED: " + ("YES" if created else "NO"),
        "CAPTURE_PATH: " + (path if type(path) is str else "NONE"),
        "CAPTURE_BYTES: " + str(capture_result.get("bytes", 0)),
        "CAPTURE_MODE: " + CAPTURE_MODE,
    ]


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
    if result.cycle.proposal_artifact is not None:
        artifact = result.cycle.proposal_artifact
        lines.extend([
            "PROPOSAL ARTIFACT ID:", artifact.artifact_id,
            "PROPOSAL ARTIFACT DIGEST:", artifact.artifact_digest,
            "PROPOSAL ARTIFACT PATH:", artifact.path,
        ])
    lines.extend(_capture_lines(result.capture_result))
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python3 -B -m tools.agent_control.prod_first_live",
        description="Founder-run one-shot ATS-1201 PROD-01 inference.")
    parser.add_argument(
        "--expected-source-commit",
        help="Owner-reviewed checkpoint identity (40 lowercase hexadecimal characters).")
    parser.add_argument(
        "--private-response-capture", action="store_true",
        help="Founder-only private capture of this one response body.")
    parser.add_argument(
        "--cleanup-private-response-capture", action="store_true",
        help="Founder-only cleanup of generated private response captures.")
    args = parser.parse_args(argv)
    if args.private_response_capture and args.cleanup_private_response_capture:
        parser.error("Capture and cleanup modes cannot be combined.")
    if not args.cleanup_private_response_capture and args.expected_source_commit is None:
        parser.error("--expected-source-commit is required for Founder first-live mode.")
    try:
        if args.cleanup_private_response_capture:
            removed = cleanup_private_response_captures()
            print("CLEANUP_REMOVED: " + str(removed))
            print("CLEANUP_REMAINING: NO")
            return 0
        reviewed = OwnerReviewedSource.from_owner_authorization(
            args.expected_source_commit)
        result = (_run_private_response_capture(reviewed)
                  if args.private_response_capture else run_first_live(reviewed))
        print(format_success(result))
        return 0
    except FirstLiveFailure as error:
        for line in _capture_lines(error.capture_result):
            print(line, file=sys.stderr)
        blocked = {"status": "BLOCKED", "classification": error.classification}
        if error.provider_structure is not None:
            blocked["provider_structure"] = error.provider_structure
        print(json.dumps(blocked, sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 2
    except (ValidationError, OSError):
        print(json.dumps({"status": "BLOCKED", "classification": "CONTRACT_MISMATCH"},
                         sort_keys=True, separators=(",", ":")), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
