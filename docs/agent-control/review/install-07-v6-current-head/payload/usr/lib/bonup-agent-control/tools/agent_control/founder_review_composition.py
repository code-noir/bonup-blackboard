"""Concrete Agent Control composition for the external PROD-01 Founder review."""
from threading import RLock

from .founder_review_auth import ProductProposalReviewBinding
from .founder_review_runtime import (
    FounderReviewBoundary,
    product_review_operation_id,
)
from .prod_artifact import (
    ProposalArtifactError,
    ProposalArtifactStore,
    safe_proposal_projection,
    validate_safe_proposal_projection,
)
from .registry import Registry
from .schema import valid_format
from .types import AuthorityError, ValidationError


_RESULTING_STATE = {
    "ACCEPT": "APPROVED_INTERNAL",
    "REJECT": "WORKING",
    "REQUEST_CHANGES": "WORKING",
}


class FounderReviewCoordinator:
    """Join the application request, Founder transport, and Registry review.

    The coordinator retains only the canonical binding while a Founder request
    is pending.  Founder-facing proposal content is reloaded from the verified
    immutable artifact for every display request; it is never copied into the
    signed challenge.
    """

    trusted_agent_control_boundary = True

    def __init__(self, artifact_store, registry):
        if (type(artifact_store) is not ProposalArtifactStore
                or type(registry) is not Registry):
            raise ValidationError("Founder review Agent Control dependencies required.")
        self.artifact_store = artifact_store
        self.registry = registry
        self._pending = {}
        self._lock = RLock()

    def boundary(self):
        return FounderReviewBoundary(
            request_review=self.request_product_review,
            observe_review=self.observe_product_review,
        )

    @staticmethod
    def _binding(value):
        try:
            return value if type(value) is ProductProposalReviewBinding else ProductProposalReviewBinding.from_dict(value)
        except (AuthorityError, ValidationError):
            raise AuthorityError("Canonical Founder review binding required.") from None

    @staticmethod
    def _assert_projection(binding, projection):
        try:
            value = validate_safe_proposal_projection(projection)
        except ProposalArtifactError:
            raise AuthorityError("Verified Founder proposal projection required.") from None
        metadata = binding.to_dict()
        if any(value[field] != metadata[expected] for field, expected in (
                ("artifact_id", "artifact_id"),
                ("artifact_digest", "artifact_digest"),
                ("task_id", "task_id"),
                ("proposal_id", "proposal_id"),
                ("proposal_digest", "proposal_digest"))):
            raise AuthorityError("Founder proposal projection binding mismatch.")
        return value

    def request_product_review(self, binding, proposal_projection, *, operation_id):
        binding = self._binding(binding)
        projection = self._assert_projection(binding, proposal_projection)
        if operation_id != product_review_operation_id(binding):
            raise AuthorityError("Founder review operation binding mismatch.")
        task_id = binding.to_dict()["task_id"]
        with self._lock:
            previous = self._pending.get(task_id)
            if previous is not None:
                if previous != binding.canonical_json():
                    raise AuthorityError("Conflicting Founder review already pending.")
                return {"status": "ALREADY_REQUESTED"}
            self._pending[task_id] = binding.canonical_json()
        # Keep the verified value in this call path for binding validation, but
        # do not retain proposal text outside the immutable artifact store.
        if projection["knowledge_state"] != "WORKING":
            raise AuthorityError("Founder review requires WORKING proposal knowledge.")
        return {"status": "REQUESTED"}

    def allow_product_review(self, binding):
        binding = self._binding(binding)
        task_id = binding.to_dict()["task_id"]
        with self._lock:
            if self._pending.get(task_id) != binding.canonical_json():
                raise AuthorityError("Founder review was not requested by the application.")
        return True

    def proposal_for_product_review(self, binding):
        binding = self._binding(binding)
        self.allow_product_review(binding)
        metadata = binding.to_dict()
        try:
            projection = safe_proposal_projection(self.artifact_store.load(metadata["proposal_id"]))
        except ProposalArtifactError as error:
            raise AuthorityError(getattr(error, "reason", "ARTIFACT_INVALID")) from None
        return self._assert_projection(binding, projection)

    def founder_review_display(self, binding):
        """Return safe display data separate from the signed challenge payload."""
        binding = self._binding(binding)
        proposal = self.proposal_for_product_review(binding)
        metadata = binding.to_dict()
        return {
            "task_id": proposal["task_id"],
            "agent_id": proposal["agent_id"],
            "artifact_id": proposal["artifact_id"],
            "artifact_digest": proposal["artifact_digest"],
            "proposal_id": proposal["proposal_id"],
            "proposal_digest": proposal["proposal_digest"],
            "proposal_type": proposal["proposal_type"],
            "predecessor_proposal_id": proposal["predecessor_proposal_id"],
            "title": proposal["title"],
            "problem_user_need": proposal["problem_user_need"],
            "objective": proposal["objective"],
            "proposed_requirement": proposal["proposed_requirement"],
            "acceptance_intent": proposal["acceptance_intent"],
            "dependencies": proposal["dependencies"],
            "assumptions": proposal["assumptions"],
            "risks_open_questions": proposal["risks_open_questions"],
            "priority_recommendation": proposal["priority_recommendation"],
            "evidence_references": proposal["evidence_references"],
            "requested_decision": metadata["decision"],
            "reason": metadata["reason"],
            "resulting_knowledge_state": _RESULTING_STATE[metadata["decision"]],
            "authority_notice": (
                "ACCEPT means APPROVED_INTERNAL product direction only; "
                "it does not authorize ARCH work, implementation, execution, "
                "deployment, publication, or agent activation."
            ),
        }

    def complete_product_review(self, binding):
        binding = self._binding(binding)
        task_id = binding.to_dict()["task_id"]
        with self._lock:
            if self._pending.get(task_id) != binding.canonical_json():
                raise AuthorityError("Founder review completion binding mismatch.")
            del self._pending[task_id]

    def observe_product_review(self, task_id):
        if type(task_id) is not str or not valid_format("task-id", task_id):
            raise ValidationError("Agent Control task binding required.")
        row = self.registry.db.execute(
            "SELECT review_id FROM product_reviews WHERE task_id=? ORDER BY rowid DESC LIMIT 1",
            (task_id,),
        ).fetchone()
        if row is None:
            return None
        event = self.registry.load_product_review_event(row["review_id"])
        object.__setattr__(event, "_trusted", True)
        return event


__all__ = ["FounderReviewCoordinator"]
