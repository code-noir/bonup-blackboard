"""Immutable PROD-01 product-knowledge review records; never execution approval."""
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import re

from .prod_contract import validate_product_proposal
from .prod_cycle import SyntheticProductCycle
from .schema import valid_format
from .serialization import canonical_json, digest, parse_json
from .types import ValidationError

CONTRACT_PATH = Path(__file__).resolve().parents[2] / "docs" / "agents" / "contracts" / "PROD-01-FOUNDER-REVIEW.json"
DECISIONS = ("ACCEPT", "REJECT", "REQUEST_CHANGES")
REVIEW_FIELDS = {
    "review_version", "decision_id", "task_id", "proposal_id", "proposal_digest",
    "proposal_predecessor_id", "previous_review_id", "reviewer", "decision", "reason",
    "resulting_knowledge_state", "review_digest",
}
_SECRET = re.compile(r"(?i)\b(?:password|api[_ -]?key|private[_ -]?key|client[_ -]?secret)\s*[:=]\s*\S+")


def _reject(message):
    raise ValidationError(message)


@dataclass(frozen=True)
class SyntheticFounderReviewContext:
    """Explicitly non-production attribution; not an AuthenticatedContext."""
    actor_id: str = "FOUNDER"
    role: str = "FOUNDER"
    context_kind: str = "SYNTHETIC_TEST_ONLY"

    def __post_init__(self):
        if (self.actor_id, self.role, self.context_kind) != (
                "FOUNDER", "FOUNDER", "SYNTHETIC_TEST_ONLY"):
            _reject("Synthetic Founder review context mismatch.")

    def actor(self):
        return {"actor_id": self.actor_id, "context_kind": self.context_kind, "role": self.role}


@dataclass(frozen=True)
class ProductReviewRecord:
    _payload: str

    def to_dict(self):
        return parse_json(self._payload)

    def canonical_json(self):
        return self._payload

    def __getitem__(self, key):
        return self.to_dict()[key]


@lru_cache(maxsize=1)
def load_review_contract():
    value = parse_json(CONTRACT_PATH.read_text(encoding="utf-8"))
    expected = {"authority_effect", "contract_version", "decisions", "founder_context",
                "knowledge_transitions", "proposal_type", "publication_eligible", "review_fields",
                "reviewer", "status", "version"}
    if type(value) is not dict or set(value) != expected:
        _reject("Malformed PROD-01 review contract.")
    if (value["version"] != 1 or value["contract_version"] != 1
            or value["authority_effect"] != "PRODUCT_KNOWLEDGE_ONLY"
            or value["status"] != "NON_EXECUTABLE" or value["publication_eligible"] is not False
            or tuple(value["decisions"]) != DECISIONS or set(value["review_fields"]) != REVIEW_FIELDS
            or value["reviewer"] != SyntheticFounderReviewContext().actor()):
        _reject("PROD-01 review contract boundary mismatch.")
    return parse_json(canonical_json(value))


def _reason(value):
    if type(value) is not str or not value.strip() or len(value) > 2048:
        _reject("PROD-01 review requires a bounded reason.")
    value = value.strip()
    if _SECRET.search(value):
        _reject("PROD-01 review reason cannot contain secrets or credentials.")
    return value


def _validate_record(data):
    contract = load_review_contract()
    if type(data) is not dict or set(data) != REVIEW_FIELDS:
        _reject("Malformed PROD-01 review fields.")
    if (data["review_version"] != 1 or data["decision"] not in DECISIONS
            or not valid_format("uuid", data["decision_id"])
            or not valid_format("task-id", data["task_id"])
            or not valid_format("uuid", data["proposal_id"])
            or not valid_format("sha256", data["proposal_digest"])
            or data["reviewer"] != SyntheticFounderReviewContext().actor()):
        _reject("Invalid PROD-01 review identity or attribution.")
    for field in ("proposal_predecessor_id", "previous_review_id"):
        if data[field] is not None and not valid_format("uuid", data[field]):
            _reject("Invalid PROD-01 review predecessor identity.")
    if data["resulting_knowledge_state"] != contract["knowledge_transitions"][data["decision"]]:
        _reject("Invalid PROD-01 review knowledge transition.")
    if data["resulting_knowledge_state"] == "PUBLICATION_ELIGIBLE":
        _reject("PROD-01 review cannot produce publication-eligible knowledge.")
    _reason(data["reason"])
    body = {key: value for key, value in data.items() if key != "review_digest"}
    if digest(body) != data["review_digest"]:
        _reject("PROD-01 review digest mismatch.")


def create_product_review(proposal, context, *, decision, decision_id, reason,
                          previous_review_id=None):
    """Create an immutable exact-proposal review; perform no routing or mutation."""
    if type(context) is not SyntheticFounderReviewContext:
        _reject("Synthetic Founder review context required for this non-production contract.")
    before = canonical_json(proposal)
    validated = validate_product_proposal(proposal)
    if canonical_json(proposal) != before:
        _reject("Proposal changed during review validation.")
    if decision not in DECISIONS:
        _reject("Unknown PROD-01 review decision.")
    contract = load_review_contract()
    body = {
        "review_version": 1,
        "decision_id": decision_id,
        "task_id": validated["task_id"],
        "proposal_id": validated["proposal_id"],
        "proposal_digest": digest(validated),
        "proposal_predecessor_id": validated["predecessor_proposal_id"],
        "previous_review_id": previous_review_id,
        "reviewer": context.actor(),
        "decision": decision,
        "reason": _reason(reason),
        "resulting_knowledge_state": contract["knowledge_transitions"][decision],
    }
    body["review_digest"] = digest(body)
    _validate_record(body)
    return ProductReviewRecord(canonical_json(body))


def assert_review_binding(review, proposal):
    if type(review) is not ProductReviewRecord:
        _reject("Validated immutable PROD-01 review required.")
    data = review.to_dict()
    _validate_record(data)
    validated = validate_product_proposal(proposal)
    if (data["task_id"] != validated["task_id"]
            or data["proposal_id"] != validated["proposal_id"]
            or data["proposal_digest"] != digest(validated)):
        _reject("PROD-01 review does not bind this exact proposal.")
    return data["resulting_knowledge_state"]


def validate_requested_revision(review, prior_proposal, revised_proposal):
    data = review.to_dict() if type(review) is ProductReviewRecord else {}
    if data.get("decision") != "REQUEST_CHANGES":
        _reject("A REQUEST_CHANGES review is required for a proposal revision.")
    assert_review_binding(review, prior_proposal)
    prior = validate_product_proposal(prior_proposal)
    revised = validate_product_proposal(revised_proposal)
    if (revised["task_id"] != prior["task_id"]
            or revised["proposal_id"] == prior["proposal_id"]
            or revised["predecessor_proposal_id"] != prior["proposal_id"]
            or digest(revised) == digest(prior)):
        _reject("Requested changes require a new bound proposal revision.")
    return revised


@dataclass(frozen=True)
class SyntheticReviewedCycle:
    cycle: SyntheticProductCycle
    review: ProductReviewRecord
    review_bytes: bytes
    review_digest: str
    task_document_bytes: bytes


def review_synthetic_cycle(cycle, context, *, decision, decision_id, reason,
                           previous_review_id=None):
    if type(cycle) is not SyntheticProductCycle:
        _reject("Validated synthetic PROD-01 cycle required.")
    review = create_product_review(cycle.proposal, context, decision=decision,
                                   decision_id=decision_id, reason=reason,
                                   previous_review_id=previous_review_id)
    data = review.to_dict()
    document = cycle.task_document_bytes.rstrip() + (
        "\n\n## Synthetic Founder Review\n\n"
        f"- Decision: `{data['decision']}`\n"
        f"- Review ID: `{data['decision_id']}`\n"
        f"- Review digest: `sha256:{data['review_digest']}`\n"
        f"- Proposal digest: `sha256:{data['proposal_digest']}`\n"
        f"- Resulting knowledge state: `{data['resulting_knowledge_state']}`\n"
        "- Authority effect: product knowledge only; no ARCH routing or execution authority\n"
    ).encode("utf-8")
    return SyntheticReviewedCycle(cycle, review, (review.canonical_json() + "\n").encode("utf-8"),
                                  data["review_digest"], document)
