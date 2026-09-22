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
    ProductModelFailure,
    run_product_model_cycle,
)
from .prod_contract import validate_product_task
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


class TrustedProd01Runtime:
    """One-cycle PROD-01 runtime composed outside the Django request boundary."""

    def __init__(self, transport, *, source_checkpoint, artifact_store):
        if (not callable(getattr(transport, "send", None))
                or getattr(transport, "credential_owned", False) is not True):
            raise ValidationError("Credential-owning trusted PROD transport required.")
        if type(source_checkpoint) is not str or not _COMMIT.fullmatch(source_checkpoint):
            raise ValidationError("Trusted PROD source checkpoint required.")
        if type(artifact_store) is not ProposalArtifactStore:
            raise ValidationError("Trusted PROD proposal artifact store required.")
        self.__transport = transport
        self.__source_checkpoint = source_checkpoint
        self.__artifact_store = artifact_store

    def submit(self, request):
        if type(request) is not ProductDirectionRuntimeRequest:
            raise ValidationError("Trusted PROD application request required.")
        task = request.to_product_task()
        try:
            cycle = run_product_model_cycle(
                task,
                self.__transport,
                require_initial_predecessor_null=True,
                proposal_artifact_store=self.__artifact_store,
                source_checkpoint=self.__source_checkpoint,
            )
        except ProductModelFailure as error:
            reason = error.audit_metadata.get("failure_reason")
            raise ProductRuntimeFailure(reason) from None
        except ValidationError:
            raise ProductRuntimeFailure("PROVIDER_ERROR") from None
        artifact = cycle.proposal_artifact
        if artifact is None:
            raise ProductRuntimeFailure(PROPOSAL_ARTIFACT_PERSISTENCE_FAILED)
        return ProductDirectionRuntimeResult(
            agent_control_task_id=task["task_id"],
            proposal_artifact_id=artifact.artifact_id,
            proposal_id=cycle.proposal["proposal_id"],
            proposal_digest=cycle.proposal_digest,
        )


def runtime_unavailable():
    """Fail closed until a trusted installed composition supplies the runtime."""
    raise ProductRuntimeUnavailable("Trusted PROD-01 runtime is unavailable.")


def submit_product_direction_task(request):
    """Application seam; installed composition replaces this with a trusted client."""
    runtime_unavailable()
