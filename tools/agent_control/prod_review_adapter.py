"""Production Founder adapter for persisted PROD-01 product reviews.

This module is deliberately separate from the synthetic review contract.  It
does not accept an AuthenticatedContext from a caller; FounderSessions mints
the opaque authentication proof after consuming its verified one-use session.
"""
from dataclasses import dataclass

from .founder_review_auth import ProductProposalReviewBinding
from .founder_session import FounderSessions
from .prod_artifact import ProposalArtifactStore
from .registry import Registry
from .types import AuthorityError, ValidationError


@dataclass(frozen=True)
class ProductionProductReviewAdapter:
    artifact_store: ProposalArtifactStore
    founder_sessions: FounderSessions
    registry: Registry

    def __post_init__(self):
        if (type(self.artifact_store) is not ProposalArtifactStore
                or type(self.founder_sessions) is not FounderSessions
                or type(self.registry) is not Registry):
            raise ValidationError("Production Founder review dependencies required.")

    def review(self, binding, *, session, operation_id):
        if type(binding) is not ProductProposalReviewBinding:
            raise AuthorityError("Signed product review binding required.")
        metadata=binding.to_dict()
        # The caller supplies only the signed subject.  The authoritative
        # proposal bytes come from the loader-verified immutable artifact.
        artifact=self.artifact_store.load(metadata["proposal_id"])
        expected=ProductProposalReviewBinding.from_artifact(
            artifact, decision=metadata["decision"], reason=metadata["reason"])
        if expected.canonical_json()!=binding.canonical_json():
            raise AuthorityError("Product review artifact binding mismatch.")
        authentication=self.founder_sessions.consume_product_review_authenticated(
            session, binding)
        return self.registry.create_product_review(
            artifact, binding, authentication, operation_id=operation_id)
