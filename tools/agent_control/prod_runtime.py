"""Trusted application boundary for one bounded PROD-01 model cycle.

This module accepts only a fixed application projection.  A production
composition supplies the transport; that transport owns the provider
credential.  Django and browser inputs never construct or select it.
"""
from dataclasses import dataclass
import re
from uuid import UUID

from .prod_artifact import ProposalArtifactStore
from .prod_model_transport import (
    INITIAL_PREDECESSOR_INVALID,
    PROPOSAL_ARTIFACT_PERSISTENCE_FAILED,
    SAFE_TRANSPORT_FAILURE_REASONS,
    TRUSTED_ENDPOINT,
    TRUSTED_MODEL,
    ProductModelFailure,
    build_product_model_request,
    resume_product_model_cycle,
    run_product_model_cycle,
)
from .prod_contract import validate_product_task
from .prod_execution import (
    ARTIFACT_COMMITTED,
    ProdExecutionBinding,
    ProdExecutionLedger,
    ProductExecutionFailure,
    RECONCILIATION_REQUIRED,
    RESPONSE_CAPTURED,
    RESPONSE_REJECTED,
    SEND_FENCE_COMMITTED,
)
from .serialization import digest
from .types import ValidationError


_COMMIT = re.compile(r"[0-9a-f]{40}\Z", re.ASCII)
_TASK_ID = re.compile(r"ATS-[0-9]{4,}\Z", re.ASCII)
_RUNTIME_FAILURE_REASONS = frozenset(SAFE_TRANSPORT_FAILURE_REASONS) | frozenset({
    "PROPOSAL_SCHEMA_MISMATCH",
    "PROPOSAL_ID_INVALID",
    "TASK_BINDING_INVALID",
    "EVIDENCE_BINDING_INVALID",
    "KNOWLEDGE_STATE_INVALID",
    "AUTHORITY_CLAIM_REJECTED",
    "CONTENT_POLICY_REJECTED",
    "PROPOSAL_BINDING_INVALID",
    "PROPOSAL_BINDING_CONFLICT",
    INITIAL_PREDECESSOR_INVALID,
    PROPOSAL_ARTIFACT_PERSISTENCE_FAILED,
    "PROVIDER_OUTCOME_UNKNOWN",
})


class ProductRuntimeUnavailable(ValidationError):
    """No installed trusted PROD runtime has been composed."""


class ProductRuntimeFailure(ValidationError):
    """Bounded application-safe runtime failure."""

    def __init__(self, reason):
        if reason not in _RUNTIME_FAILURE_REASONS:
            reason = "PROVIDER_ERROR"
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class ProductDirectionRuntimeRequest:
    """The complete, non-secret application projection accepted by the runtime."""

    application_task_id: str
    agent_control_task_id: str
    agent_id: str
    objective: str

    def to_product_task(self):
        if set(self.__dict__) != {
                "application_task_id", "agent_control_task_id", "agent_id", "objective"}:
            raise ValidationError("Malformed PROD-01 application runtime request.")
        try:
            application_id = UUID(self.application_task_id)
        except (AttributeError, TypeError, ValueError):
            raise ValidationError("Invalid product-direction application identity.") from None
        if str(application_id) != self.application_task_id:
            raise ValidationError("Non-canonical product-direction application identity.")
        if (self.agent_id != "PROD-01"
                or not _TASK_ID.fullmatch(self.agent_control_task_id)):
            raise ValidationError("PROD-01 runtime identity mismatch.")
        if type(self.objective) is not str or not self.objective.strip():
            raise ValidationError("Bounded PROD-01 objective required.")
        task = {
            "agent_id": "PROD-01",
            "task_id": self.agent_control_task_id,
            "task_class": "PRODUCT_REQUIREMENT",
            "objective": self.objective,
            "input_references": [],
        }
        return validate_product_task(task)


@dataclass(frozen=True)
class ProductDirectionRuntimeResult:
    agent_control_task_id: str
    proposal_artifact_id: str
    proposal_id: str
    proposal_digest: str


def agent_control_task_id_for(application_task_id):
    """Derive one stable valid Agent Control task ID from the app UUID."""
    try:
        value = UUID(str(application_task_id))
    except (AttributeError, TypeError, ValueError):
        raise ValidationError("Invalid product-direction application identity.") from None
    if str(value) != str(application_task_id):
        raise ValidationError("Non-canonical product-direction application identity.")
    return "ATS-" + str(value.int)


def _policy_digest(request):
    return digest({
        "endpoint": TRUSTED_ENDPOINT,
        "model": TRUSTED_MODEL,
        "tools": request["tools"],
        "request_policy": request["request_policy"],
        "schema_digest": request["output_contract"]["schema_digest"],
    })


class TrustedProd01Runtime:
    """One-cycle PROD-01 runtime composed outside the Django request boundary."""

    def __init__(self, transport, *, source_checkpoint, artifact_store,
                 execution_ledger):
        if (not callable(getattr(transport, "send", None))
                or getattr(transport, "credential_owned", False) is not True):
            raise ValidationError("Credential-owning trusted PROD transport required.")
        if type(source_checkpoint) is not str or not _COMMIT.fullmatch(source_checkpoint):
            raise ValidationError("Trusted PROD source checkpoint required.")
        if not isinstance(artifact_store, ProposalArtifactStore):
            raise ValidationError("Trusted PROD proposal artifact store required.")
        if not isinstance(execution_ledger, ProdExecutionLedger):
            raise ValidationError("Durable PROD execution ledger required.")
        self.__transport = transport
        self.__source_checkpoint = source_checkpoint
        self.__artifact_store = artifact_store
        self.__execution_ledger = execution_ledger

    def _binding(self, request, task):
        model_request, _ = build_product_model_request(task)
        return ProdExecutionBinding(
            agent_id=task["agent_id"],
            agent_control_task_id=task["task_id"],
            application_task_id=request.application_task_id,
            request_digest=digest(model_request),
            policy_digest=_policy_digest(model_request),
            source_checkpoint=self.__source_checkpoint,
        )

    def _result_from_artifact(self, task, artifact):
        if (artifact.value["task_id"] != task["task_id"]
                or artifact.value["agent_id"] != "PROD-01"
                or artifact.value["source_checkpoint"] != self.__source_checkpoint):
            raise ProductRuntimeFailure("PROPOSAL_BINDING_INVALID")
        return ProductDirectionRuntimeResult(
            agent_control_task_id=task["task_id"],
            proposal_artifact_id=artifact.artifact_id,
            proposal_id=artifact.value["proposal_id"],
            proposal_digest=artifact.value["proposal_digest"],
        )

    def _recover_artifact(self, binding, task):
        try:
            artifact = self.__artifact_store.find_by_task_id(task["task_id"])
        except Exception as error:
            raise ProductRuntimeFailure(getattr(error, "reason", "PROVIDER_ERROR")) from None
        if artifact is None:
            return None
        try:
            self.__execution_ledger.mark_artifact(
                binding, artifact.artifact_id, artifact.artifact_digest)
        except ProductExecutionFailure:
            raise ProductRuntimeFailure("PROPOSAL_BINDING_INVALID") from None
        return self._result_from_artifact(task, artifact)

    def _resume_local(self, binding, task, record):
        if record.state == ARTIFACT_COMMITTED:
            try:
                artifact = self.__artifact_store.load(record.artifact_id[8:])
            except Exception:
                raise ProductRuntimeFailure("PROPOSAL_BINDING_INVALID") from None
            if artifact.artifact_digest != record.artifact_digest:
                raise ProductRuntimeFailure("PROPOSAL_BINDING_INVALID")
            return self._result_from_artifact(task, artifact)
        if record.state in {RECONCILIATION_REQUIRED, SEND_FENCE_COMMITTED}:
            raise ProductRuntimeFailure("PROVIDER_OUTCOME_UNKNOWN")
        if record.state == RESPONSE_REJECTED:
            raise ProductRuntimeFailure(record.failure_reason or "PROVIDER_ERROR")
        if record.state != RESPONSE_CAPTURED:
            return None
        try:
            cycle = resume_product_model_cycle(
                task,
                record.response,
                response_metadata=record.response_metadata,
                require_initial_predecessor_null=True,
                proposal_artifact_store=self.__artifact_store,
                source_checkpoint=self.__source_checkpoint,
            )
        except ProductModelFailure as error:
            if error.audit_metadata.get("result_classification") == "OUTPUT_REJECTED":
                self.__execution_ledger.mark_response_rejected(
                    binding, error.audit_metadata.get("failure_reason", "OUTPUT_REJECTED"))
            raise ProductRuntimeFailure(
                error.audit_metadata.get("failure_reason", "PROVIDER_ERROR")) from None
        return self._finalize_artifact(binding, task, cycle)

    def _finalize_artifact(self, binding, task, cycle):
        artifact = cycle.proposal_artifact
        if artifact is None:
            raise ProductRuntimeFailure(PROPOSAL_ARTIFACT_PERSISTENCE_FAILED)
        try:
            self.__execution_ledger.mark_artifact(
                binding, artifact.artifact_id, artifact.artifact_digest)
        except ProductExecutionFailure:
            raise ProductRuntimeFailure("PROPOSAL_BINDING_INVALID") from None
        return self._result_from_artifact(task, artifact)

    def submit(self, request):
        if type(request) is not ProductDirectionRuntimeRequest:
            raise ValidationError("Trusted PROD application request required.")
        task = request.to_product_task()
        binding = self._binding(request, task)
        try:
            record = self.__execution_ledger.prepare(binding)
            recovered = self._recover_artifact(binding, task)
            if recovered is not None:
                return recovered
            resumed = self._resume_local(binding, task, record)
            if resumed is not None:
                return resumed
            claimed, record = self.__execution_ledger.claim_send_fence(binding)
            if not claimed:
                resumed = self._resume_local(binding, task, record)
                if resumed is not None:
                    return resumed
                raise ProductRuntimeFailure("PROVIDER_OUTCOME_UNKNOWN")

            def capture(response, metadata):
                self.__execution_ledger.capture_response(binding, response, metadata)

            cycle = run_product_model_cycle(
                task,
                self.__transport,
                require_initial_predecessor_null=True,
                proposal_artifact_store=self.__artifact_store,
                source_checkpoint=self.__source_checkpoint,
                response_capture=capture,
            )
            return self._finalize_artifact(binding, task, cycle)
        except ProductExecutionFailure as error:
            record = self.__execution_ledger.get(binding)
            if record is not None and record.state == SEND_FENCE_COMMITTED:
                self.__execution_ledger.mark_reconciliation_required(binding)
                raise ProductRuntimeFailure("PROVIDER_OUTCOME_UNKNOWN") from None
            if error.reason in {"RESPONSE_CAPTURE_INVALID", "RESPONSE_METADATA_INVALID"}:
                raise ProductRuntimeFailure("PROVIDER_OUTCOME_UNKNOWN") from None
            raise ProductRuntimeFailure(error.reason) from None
        except ProductModelFailure as error:
            record = self.__execution_ledger.get(binding)
            if record is not None and record.state == SEND_FENCE_COMMITTED:
                self.__execution_ledger.mark_reconciliation_required(binding)
                raise ProductRuntimeFailure("PROVIDER_OUTCOME_UNKNOWN") from None
            reason = error.audit_metadata.get("failure_reason")
            raise ProductRuntimeFailure(reason) from None
        except ProductRuntimeFailure:
            raise
        except ValidationError:
            raise ProductRuntimeFailure("PROVIDER_ERROR") from None


def runtime_unavailable():
    """Fail closed until a trusted installed composition supplies the runtime."""
    raise ProductRuntimeUnavailable("Trusted PROD-01 runtime is unavailable.")


def submit_product_direction_task(request):
    """Application seam; installed composition replaces this with a trusted client."""
    runtime_unavailable()
