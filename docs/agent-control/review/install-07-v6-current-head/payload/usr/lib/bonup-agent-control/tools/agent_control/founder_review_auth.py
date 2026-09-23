"""Bounded Founder authentication binding for one PROD proposal decision."""
from dataclasses import dataclass
import re

from .founder_crypto import PROD_PROPOSAL_REVIEW
from .schema import valid_format
from .serialization import canonical_json, digest, parse_json
from .types import AuthorityError, ValidationError

REVIEW_BINDING_VERSION = 1
REVIEW_DECISIONS = ("ACCEPT", "REJECT", "REQUEST_CHANGES")
_FIELDS = frozenset({
    "binding_version", "purpose", "artifact_id", "artifact_digest", "task_id",
    "proposal_id", "proposal_digest", "decision", "reason",
})
_ARTIFACT_FIELDS = frozenset({
    "artifact_version", "artifact_id", "task_id", "agent_id", "proposal_id",
    "proposal", "proposal_digest", "knowledge_state", "source_checkpoint",
    "logical_model", "validation_result", "artifact_digest",
})
_SECRET = re.compile(
    r"(?i)\b(?:password|api[_ -]?key|private[_ -]?key|client[_ -]?secret)\s*[:=]\s*\S+"
)


def _reject(message):
    raise ValidationError(message)


def _reason(value):
    if type(value) is not str or not value.strip() or len(value) > 2048:
        _reject("Product review reason must be bounded.")
    value = value.strip()
    if _SECRET.search(value):
        _reject("Product review reason cannot contain secrets.")
    return value


def _artifact_metadata(artifact):
    """Read only a loader-verified artifact's identity, never proposal authority."""
    value = getattr(artifact, "value", None)
    if type(value) is not dict or set(value) != _ARTIFACT_FIELDS:
        raise AuthorityError("Verified PROD-01 proposal artifact required.")
    proposal = value["proposal"]
    if (type(proposal) is not dict
            or type(value["artifact_id"]) is not str
            or type(value["proposal_id"]) is not str
            or not valid_format("uuid", value["proposal_id"])
            or value["artifact_id"] != "PROD-01-" + value["proposal_id"]
            or value["agent_id"] != "PROD-01"
            or value["knowledge_state"] != "WORKING"
            or value["validation_result"] != "PASS"
            or not valid_format("task-id", value["task_id"])
            or not valid_format("sha256", value["proposal_digest"])
            or not valid_format("sha256", value["artifact_digest"])
            or value["proposal_digest"] != digest(proposal)
            or value["artifact_digest"] != digest(
                {key: item for key, item in value.items() if key != "artifact_digest"})
            or proposal.get("agent_id") != "PROD-01"
            or proposal.get("task_id") != value["task_id"]
            or proposal.get("proposal_id") != value["proposal_id"]
            or proposal.get("knowledge_state") != "WORKING"):
        raise AuthorityError("PROD-01 proposal artifact identity is invalid.")
    return dict(
        artifact_id=value["artifact_id"],
        artifact_digest=value["artifact_digest"],
        task_id=value["task_id"],
        proposal_id=value["proposal_id"],
        proposal_digest=value["proposal_digest"],
    )


@dataclass(frozen=True)
class ProductProposalReviewBinding:
    """Canonical signed subject for exactly one future Founder review decision."""

    _payload: str

    @classmethod
    def from_artifact(cls, artifact, *, decision, reason):
        metadata = _artifact_metadata(artifact)
        return cls.from_dict(dict(
            binding_version=REVIEW_BINDING_VERSION,
            purpose=PROD_PROPOSAL_REVIEW,
            **metadata,
            decision=decision,
            reason=reason,
        ))

    @classmethod
    def from_dict(cls, value):
        if type(value) is not dict or set(value) != _FIELDS:
            _reject("Closed PROD proposal review binding required.")
        detached = parse_json(canonical_json(value))
        if (detached["binding_version"] != REVIEW_BINDING_VERSION
                or detached["purpose"] != PROD_PROPOSAL_REVIEW
                or detached["decision"] not in REVIEW_DECISIONS
                or not valid_format("task-id", detached["task_id"])
                or not valid_format("uuid", detached["proposal_id"])
                or not valid_format("sha256", detached["artifact_digest"])
                or not valid_format("sha256", detached["proposal_digest"])
                or type(detached["artifact_id"]) is not str
                or detached["artifact_id"] != "PROD-01-" + detached["proposal_id"]):
            _reject("Invalid PROD proposal review binding identity.")
        normalized_reason = _reason(detached["reason"])
        if detached["reason"] != normalized_reason:
            _reject("Product review reason must be canonicalized before signing.")
        return cls(canonical_json(detached))

    def to_dict(self):
        return parse_json(self._payload)

    def canonical_json(self):
        return self._payload

    @property
    def binding_digest(self):
        return digest(self.to_dict())


def normalize_review_binding(value):
    if type(value) is ProductProposalReviewBinding:
        return value.to_dict()
    return ProductProposalReviewBinding.from_dict(value).to_dict()
