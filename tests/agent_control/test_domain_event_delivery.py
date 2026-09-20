import base64
import tempfile
import unittest
from contextlib import ExitStack
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from prod_cycle_fixtures import DeterministicProductFake
from test_founder_root import BOOT, ROOT, sign

from fixtures import ARCH
from tools.agent_control.domain_event_delivery import DomainEventDeliveryWorker
from tools.agent_control.founder_review_auth import ProductProposalReviewBinding
from tools.agent_control.founder_session import FounderSessions
from tools.agent_control.identity import PeerIdentity, ProcessIdentity
from tools.agent_control.prod_artifact import ProposalArtifactStore
from tools.agent_control.prod_review_adapter import ProductionProductReviewAdapter
from tools.agent_control.registry import Registry
from tools.agent_control.runtime_schema import migrate_v2, migrate_v3
from tools.agent_control.serialization import canonical_json, digest
from tools.agent_control.storage import RegistryBlocked


class Boundary:
    trusted_application_boundary = True
    available = True

    def __init__(self, failures=()):
        self.failures = set(failures)
        self.calls = []

    def deliver(self, event, consumer_name):
        self.calls.append((event["event_id"], consumer_name))
        if consumer_name in self.failures:
            raise RuntimeError("synthetic consumer failure")


class DomainEventDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = ExitStack()
        self.addCleanup(self.paths.close)
        self.paths.enter_context(patch(
            "tools.agent_control.registry.external_path",
            lambda value: Path(value).absolute(),
        ))
        self.paths.enter_context(patch(
            "tools.agent_control.storage.external_path",
            lambda value: Path(value).absolute(),
        ))
        self.paths.enter_context(patch(
            "tools.agent_control.publication.external_path",
            lambda value: Path(value).absolute(),
        ))
        self.registry = Registry.initialize(
            self.root / "state.sqlite3", self.root / "history.git", operation_id=str(uuid4())
        )
        migrate_v2(self.registry)
        self.store = ProposalArtifactStore(self.root / "proposals")
        now = datetime(2026, 9, 20, tzinfo=timezone.utc)
        self.sessions = FounderSessions(
            ROOT,
            observe=lambda: (PeerIdentity(1000, 1000, 1234), ProcessIdentity(BOOT, 1234, 42)),
            audit=lambda *_: None,
            clock=lambda: now,
            boottime=lambda: 100.0,
        )
        self.adapter = ProductionProductReviewAdapter(self.store, self.sessions, self.registry)
        self.addCleanup(self.registry.close)
        self.addCleanup(self.temp.cleanup)
        self.event = self._committed_event()
        migrate_v3(self.registry)

    def _committed_event(self, number=701):
        task = self.registry.create_task(
            {"title": "Delivery task", "objective": "Deliver one event",
             "source_base_commit": "a" * 40},
            operation_id=str(uuid4()), context=ARCH,
        )
        product = DeterministicProductFake({
            "proposal_id": f"00000000-0000-4000-8000-000000000{number:03d}",
            "title": "Product direction result",
            "objective": "Deliver the committed product direction.",
        }).propose(dict(
            task_id=task["task_id"],
            objective="Deliver the committed product direction.",
            input_references=[{
                "reference_type": "FOUNDER_DIRECTION",
                "reference_id": "FOUNDER-DIRECTION-0701",
                "digest": "7" * 64,
                "knowledge_state": "DIRECT_FOUNDER",
            }],
        ))
        artifact = self.store.persist(product, source_checkpoint="a" * 40)
        binding = ProductProposalReviewBinding.from_artifact(
            artifact, decision="ACCEPT", reason="Founder delivery review."
        )
        challenge = self.sessions.issue_product_review(binding)
        session = self.sessions.submit({
            "challenge_id": digest(challenge),
            "signature": base64.b64encode(
                sign(canonical_json(challenge).encode())
            ).decode(),
        })
        self.adapter.review(binding, session=session, operation_id=str(uuid4()))
        return self.registry.load_product_review_event(
            self.registry.db.execute(
                "SELECT record_id FROM product_reviews"
            ).fetchone()[0]
        )

    def _worker(self, boundary):
        return DomainEventDeliveryWorker(
            self.registry, boundary, now=lambda: "9999-01-01T00:00:00Z"
        )

    def _make_retryable_now(self):
        self.registry.db.execute(
            "UPDATE domain_event_deliveries SET next_attempt_at='1970-01-01T00:00:00Z' "
            "WHERE status='RETRY'"
        )

    def test_committed_event_fans_out_independently_to_both_consumers(self):
        boundary = Boundary()
        result = self._worker(boundary).run_once()
        self.assertEqual(result["acknowledged"], 2)
        self.assertEqual(
            {consumer for _, consumer in boundary.calls},
            {"product-direction", "blackboard-product-direction"},
        )
        self.assertEqual(
            self.registry.db.execute(
                "SELECT count(*) FROM domain_event_deliveries WHERE status='ACKNOWLEDGED'"
            ).fetchone()[0], 2,
        )

    def test_duplicate_delivery_is_harmless_and_replay_is_projection_only(self):
        boundary = Boundary()
        self._worker(boundary).run_once()
        before = self.registry.db.execute("SELECT count(*) FROM product_reviews").fetchone()[0]
        result = self._worker(boundary).run_once(replay=True)
        self.assertEqual(result["acknowledged"], 2)
        self.assertEqual(len(boundary.calls), 4)
        self.assertEqual(
            self.registry.db.execute("SELECT count(*) FROM product_reviews").fetchone()[0], before
        )

    def test_product_success_blackboard_failure_retries_blackboard_only(self):
        boundary = Boundary({"blackboard-product-direction"})
        first = self._worker(boundary).run_once()
        self.assertEqual(first["acknowledged"], 1)
        self.assertEqual(first["retried"], 1)
        self.assertEqual(
            self.registry.db.execute(
                "SELECT status FROM domain_event_deliveries WHERE consumer_name='product-direction'"
            ).fetchone()[0], "ACKNOWLEDGED"
        )
        boundary.failures.clear()
        self._make_retryable_now()
        second = self._worker(boundary).run_once()
        self.assertEqual(second["acknowledged"], 1)
        self.assertEqual([consumer for _, consumer in boundary.calls[-1:]], ["blackboard-product-direction"])

    def test_blackboard_success_product_failure_retries_product_only(self):
        boundary = Boundary({"product-direction"})
        first = self._worker(boundary).run_once()
        self.assertEqual(first["acknowledged"], 1)
        boundary.failures.clear()
        self._make_retryable_now()
        self._worker(boundary).run_once()
        self.assertEqual([consumer for _, consumer in boundary.calls[-1:]], ["product-direction"])

    def test_worker_crash_leaves_pending_delivery_recoverable(self):
        class CrashingBoundary(Boundary):
            def deliver(self, event, consumer_name):
                super().deliver(event, consumer_name)
                raise SystemExit("synthetic crash")

        with self.assertRaises(SystemExit):
            self._worker(CrashingBoundary()).run_once()
        self.assertEqual(
            self.registry.db.execute(
                "SELECT count(*) FROM domain_event_deliveries WHERE status='PENDING'"
            ).fetchone()[0], 2,
        )
        result = self._worker(Boundary()).run_once()
        self.assertEqual(result["acknowledged"], 2)

    def test_acknowledgement_occurs_only_after_successful_consumer(self):
        boundary = Boundary({"product-direction"})
        self._worker(boundary).run_once()
        self.assertEqual(
            self.registry.db.execute(
                "SELECT status FROM domain_event_deliveries WHERE consumer_name='product-direction'"
            ).fetchone()[0], "RETRY"
        )

    def test_invalid_digest_blocks_without_delivery(self):
        boundary = Boundary()
        with patch.object(
            self.registry,
            "load_domain_event",
            side_effect=RegistryBlocked(
                "Domain event binding or digest mismatch."
            ),
        ):
            result = self._worker(boundary).run_once()
        self.assertEqual(result["blocked"], 2)
        self.assertEqual(boundary.calls, [])

    def test_unsupported_version_blocks_without_delivery(self):
        with patch.object(
            self.registry,
            "load_domain_event",
            side_effect=RegistryBlocked("Unsupported domain event version."),
        ):
            result = self._worker(Boundary()).run_once()
        self.assertEqual(result["blocked"], 2)

    def test_trusted_runtime_unavailable_preserves_pending_rows(self):
        result = self._worker(None).run_once()
        self.assertEqual(result["status"], "TRUSTED_RUNTIME_UNAVAILABLE")
        self.assertEqual(
            self.registry.db.execute(
                "SELECT count(*) FROM domain_event_deliveries WHERE status='PENDING'"
            ).fetchone()[0], 2,
        )

    def test_worker_never_invokes_review_or_founder_authority(self):
        with patch("tools.agent_control.founder_intake.FounderIntake", side_effect=AssertionError), \
                patch("tools.agent_control.founder_session.FounderSessions", side_effect=AssertionError), \
                patch.object(self.registry, "create_product_review", side_effect=AssertionError), \
                patch("tools.agent_control.prod_review_adapter.ProductionProductReviewAdapter.review",
                      side_effect=AssertionError):
            result = self._worker(Boundary()).run_once()
        self.assertEqual(result["acknowledged"], 2)
        self.assertEqual(self.registry.db.execute("SELECT count(*) FROM product_reviews").fetchone()[0], 1)

    def test_delivery_migration_backfills_existing_event_obligations(self):
        self.assertEqual(
            self.registry.db.execute(
                "SELECT count(*) FROM domain_event_deliveries WHERE event_id=?",
                (self.event["event_id"],),
            ).fetchone()[0], 2,
        )

    def test_v3_review_commit_creates_both_consumer_obligations(self):
        event = self._committed_event(702)
        self.assertEqual(
            self.registry.db.execute(
                "SELECT count(*) FROM domain_event_deliveries WHERE event_id=?",
                (event["event_id"],),
            ).fetchone()[0], 2,
        )


if __name__ == "__main__":
    unittest.main()
