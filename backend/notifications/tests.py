from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from backend.activity.log import log_activity
from backend.api.tests.helpers import authed_client, make_contract, make_subscription, make_user
from backend.notifications.models import Notification


class NotificationNoiseTests(TestCase):
    def setUp(self):
        self.alice = make_user("noise_alice", "noise-alice@example.com")
        self.bob = make_user("noise_bob", "noise-bob@example.com")
        make_subscription(self.alice)
        make_subscription(self.bob)
        self.contract = make_contract(self.alice, counterparty_email=self.bob.email)

    def test_autosave_activity_does_not_create_visible_notification(self):
        log_activity(
            contract=self.contract,
            user=self.alice,
            activity_type="draft_autosaved",
            description="Contract draft autosaved.",
            metadata={"source": "editor_autosave"},
        )

        self.assertEqual(Notification.objects.filter(user=self.bob).count(), 0)

    def test_unread_count_excludes_hidden_and_autosave_noise(self):
        Notification.objects.create(
            user=self.alice,
            notification_type="agreement_exchange",
            title="Change request received",
            message="Contract: Test\nFrom: Bob\nAction: Review request",
        )
        Notification.objects.create(
            user=self.alice,
            notification_type="draft_autosaved",
            title="bonUP notification",
            message="Draft autosaved.",
            metadata={"source": "editor_autosave"},
        )
        Notification.objects.create(
            user=self.alice,
            notification_type="contract_updated",
            title="Background save completed",
            message="Snapshot synced.",
            metadata={"notification_hidden": True},
        )

        response = authed_client(self.alice).get("/api/notifications/unread-count/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 1)

    def test_unread_count_includes_agreement_timeline_notifications(self):
        Notification.objects.create(
            user=self.alice,
            notification_type="agreement_timeline",
            title="Payment marked paid",
            message="Contract: Test\nFrom: Alice\nTimeline item: Deposit\nAction: Payment marked paid",
            target_url=f"/lifecycle?contract={self.contract.id}",
            metadata={"source": "agreement_timeline"},
        )

        client = authed_client(self.alice)
        response = client.get("/api/notifications/unread-count/")
        unread_response = client.get("/api/notifications/unread/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["unread_count"], 1)
        self.assertEqual(unread_response.status_code, 200)
        self.assertEqual(unread_response.data["results"][0]["target_url"], f"/lifecycle?contract={self.contract.id}")

    def test_unread_list_is_limited_and_excludes_noise(self):
        for index in range(25):
            Notification.objects.create(
                user=self.alice,
                notification_type="agreement_exchange",
                title=f"Meaningful {index}",
                message="Contract: Test\nFrom: Bob\nAction: Review",
            )
        Notification.objects.create(
            user=self.alice,
            notification_type="draft_autosaved",
            title="Draft saved",
            message="Autosaved.",
            metadata={"source": "editor_autosave"},
        )

        response = authed_client(self.alice).get("/api/notifications/unread/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 20)
        self.assertNotIn("Draft saved", {item["title"] for item in response.data["results"]})

    def test_cleanup_command_dry_run_finds_noise(self):
        noisy = Notification.objects.create(
            user=self.alice,
            notification_type="draft_autosaved",
            title="bonUP notification",
            message="Draft autosaved.",
            metadata={"source": "editor_autosave"},
        )
        meaningful = Notification.objects.create(
            user=self.alice,
            notification_type="agreement_exchange",
            title="Contract signed",
            message="Contract: Test\nSigned by: Bob\nAction: Open Agreement Timeline",
        )
        out = StringIO()

        call_command("cleanup_autosave_notifications", stdout=out)

        self.assertIn("Would update 1", out.getvalue())
        noisy.refresh_from_db()
        meaningful.refresh_from_db()
        self.assertFalse(noisy.is_read)
        self.assertFalse(meaningful.is_read)

    def test_cleanup_command_apply_hides_noise_only(self):
        noisy = Notification.objects.create(
            user=self.alice,
            notification_type="draft_autosaved",
            title="bonUP notification",
            message="Draft autosaved.",
            metadata={"source": "editor_autosave"},
        )
        meaningful = Notification.objects.create(
            user=self.alice,
            notification_type="agreement_exchange",
            title="Change request received",
            message="Contract: Test\nFrom: Bob\nAction: Review request",
        )

        call_command("cleanup_autosave_notifications", "--apply", stdout=StringIO())

        noisy.refresh_from_db()
        meaningful.refresh_from_db()
        self.assertTrue(noisy.is_read)
        self.assertTrue(noisy.metadata["notification_hidden"])
        self.assertFalse(meaningful.is_read)
        self.assertNotIn("notification_hidden", meaningful.metadata)
