# backend/api/tests/test_notifications.py
#
# Tests for the Notifications domain:
# - GET  /api/notifications/              — list, pagination, is_read filter
# - GET  /api/notifications/unread-count/ — unread count
# - POST /api/notifications/read-all/     — bulk mark read
# - POST /api/notifications/<id>/read/    — mark single read, ownership enforced
# - notify() helper — creates DB record, sends email
# - log_activity() integration — notifies the other party

from django.core import mail
from django.test import TestCase, override_settings

from backend.activity.log import log_activity
from backend.notifications.models import Notification
from backend.notifications.notify import notify

from .helpers import authed_client, make_contract, make_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_notification(user, contract=None, notification_type="contract_created", is_read=False):
    return Notification.objects.create(
        user=user,
        notification_type=notification_type,
        title="Test notification",
        message="Something happened.",
        is_read=is_read,
        related_contract=contract,
    )


# ---------------------------------------------------------------------------
# notify() helper
# ---------------------------------------------------------------------------

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class NotifyHelperTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_nh", "alice_nh@example.com")
        self.contract = make_contract(self.alice, counterparty_email="other_nh@example.com")
        mail.outbox = []

    def test_creates_notification_record(self):
        notify(
            user=self.alice,
            notification_type="contract_created",
            message="Contract created.",
            related_contract=self.contract,
        )
        self.assertEqual(Notification.objects.filter(user=self.alice).count(), 1)

    def test_notification_fields(self):
        n = notify(
            user=self.alice,
            notification_type="version_signed",
            message="Version was signed.",
            related_contract=self.contract,
            metadata={"version_id": "abc"},
        )
        self.assertEqual(n.notification_type, "version_signed")
        self.assertEqual(n.title, "Contract version signed")
        self.assertEqual(n.message, "Version was signed.")
        self.assertFalse(n.is_read)
        self.assertEqual(n.related_contract, self.contract)
        self.assertEqual(n.metadata["version_id"], "abc")

    def test_sends_email(self):
        notify(
            user=self.alice,
            notification_type="payment_confirmed",
            message="Payment confirmed.",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("alice_nh@example.com", mail.outbox[0].to)
        self.assertEqual(mail.outbox[0].subject, "Payment confirmed")

    def test_no_email_sent_when_user_has_no_email(self):
        self.alice.email = ""
        self.alice.save()
        notify(user=self.alice, notification_type="contract_created", message="x")
        self.assertEqual(len(mail.outbox), 0)

    def test_unknown_type_uses_fallback_title(self):
        n = notify(user=self.alice, notification_type="contract_created", message="x")
        self.assertIsNotNone(n.title)
        self.assertTrue(len(n.title) > 0)


# ---------------------------------------------------------------------------
# log_activity integration — notifies the other party
# ---------------------------------------------------------------------------

@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class LogActivityNotificationTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_la", "alice_la@example.com")
        self.bob = make_user("bob_la", "bob_la@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_la@example.com")
        mail.outbox = []

    def test_initiator_action_notifies_counterparty(self):
        log_activity(
            contract=self.contract,
            user=self.alice,
            activity_type="version_created",
            description="New version created.",
        )
        self.assertEqual(Notification.objects.filter(user=self.bob).count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.alice).count(), 0)

    def test_counterparty_action_notifies_initiator(self):
        log_activity(
            contract=self.contract,
            user=self.bob,
            activity_type="version_signed",
            description="Version signed.",
        )
        self.assertEqual(Notification.objects.filter(user=self.alice).count(), 1)
        self.assertEqual(Notification.objects.filter(user=self.bob).count(), 0)

    def test_email_sent_to_other_party(self):
        log_activity(
            contract=self.contract,
            user=self.alice,
            activity_type="payment_created",
            description="Payment created.",
        )
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("bob_la@example.com", mail.outbox[0].to)

    def test_no_notification_when_counterparty_unregistered(self):
        # contract counterparty_email has no User account
        unregistered_contract = make_contract(self.alice, counterparty_email="ghost@example.com")
        log_activity(
            contract=unregistered_contract,
            user=self.alice,
            activity_type="contract_created",
            description="Created.",
        )
        # No notification should be created (recipient doesn't exist)
        self.assertEqual(Notification.objects.count(), 0)

    def test_no_notification_when_actor_is_none(self):
        log_activity(
            contract=self.contract,
            user=None,
            activity_type="contract_created",
            description="Automated.",
        )
        self.assertEqual(Notification.objects.count(), 0)

    def test_notification_links_contract(self):
        log_activity(
            contract=self.contract,
            user=self.alice,
            activity_type="session_held",
            description="Session started.",
        )
        n = Notification.objects.get(user=self.bob)
        self.assertEqual(n.related_contract, self.contract)


# ---------------------------------------------------------------------------
# List endpoint
# ---------------------------------------------------------------------------

class NotificationListTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_nl", "alice_nl@example.com")
        self.bob = make_user("bob_nl", "bob_nl@example.com")
        self.contract = make_contract(self.alice, counterparty_email="bob_nl@example.com")
        _make_notification(self.alice, self.contract)
        _make_notification(self.alice, self.contract, is_read=True)

    def test_returns_own_notifications(self):
        r = authed_client(self.alice).get("/api/notifications/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 2)
        self.assertEqual(len(r.data["results"]), 2)

    def test_does_not_return_other_users_notifications(self):
        _make_notification(self.bob, self.contract)
        r = authed_client(self.alice).get("/api/notifications/")
        self.assertEqual(r.data["count"], 2)

    def test_is_read_filter_false(self):
        r = authed_client(self.alice).get("/api/notifications/?is_read=false")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)
        self.assertFalse(r.data["results"][0]["is_read"])

    def test_is_read_filter_true(self):
        r = authed_client(self.alice).get("/api/notifications/?is_read=true")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["count"], 1)
        self.assertTrue(r.data["results"][0]["is_read"])

    def test_pagination_envelope(self):
        r = authed_client(self.alice).get("/api/notifications/?page=1&page_size=1")
        self.assertEqual(r.status_code, 200)
        self.assertIn("count", r.data)
        self.assertIn("page", r.data)
        self.assertIn("page_size", r.data)
        self.assertIn("results", r.data)
        self.assertEqual(r.data["count"], 2)
        self.assertEqual(len(r.data["results"]), 1)

    def test_notification_fields_present(self):
        r = authed_client(self.alice).get("/api/notifications/")
        n = r.data["results"][0]
        for field in ("id", "notification_type", "title", "message", "is_read",
                      "related_contract_id", "metadata", "created_at"):
            self.assertIn(field, n)


# ---------------------------------------------------------------------------
# Unread count
# ---------------------------------------------------------------------------

class NotificationUnreadCountTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_uc", "alice_uc@example.com")
        self.bob = make_user("bob_uc", "bob_uc@example.com")
        _make_notification(self.alice, is_read=False)
        _make_notification(self.alice, is_read=False)
        _make_notification(self.alice, is_read=True)
        _make_notification(self.bob, is_read=False)

    def test_returns_own_unread_count(self):
        r = authed_client(self.alice).get("/api/notifications/unread-count/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["unread_count"], 2)

    def test_count_is_scoped_to_user(self):
        r = authed_client(self.bob).get("/api/notifications/unread-count/")
        self.assertEqual(r.data["unread_count"], 1)

    def test_zero_when_all_read(self):
        Notification.objects.filter(user=self.alice).update(is_read=True)
        r = authed_client(self.alice).get("/api/notifications/unread-count/")
        self.assertEqual(r.data["unread_count"], 0)


# ---------------------------------------------------------------------------
# Mark single as read
# ---------------------------------------------------------------------------

class NotificationMarkReadTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_mr", "alice_mr@example.com")
        self.bob = make_user("bob_mr", "bob_mr@example.com")
        self.notification = _make_notification(self.alice, is_read=False)

    def test_mark_own_notification_read(self):
        r = authed_client(self.alice).post(f"/api/notifications/{self.notification.id}/read/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_read"])
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_cannot_mark_other_users_notification(self):
        r = authed_client(self.bob).post(f"/api/notifications/{self.notification.id}/read/")
        self.assertEqual(r.status_code, 403)
        self.notification.refresh_from_db()
        self.assertFalse(self.notification.is_read)

    def test_nonexistent_returns_404(self):
        r = authed_client(self.alice).post(
            "/api/notifications/00000000-0000-0000-0000-000000000000/read/"
        )
        self.assertEqual(r.status_code, 404)

    def test_idempotent_mark_read(self):
        self.notification.is_read = True
        self.notification.save()
        r = authed_client(self.alice).post(f"/api/notifications/{self.notification.id}/read/")
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.data["is_read"])


# ---------------------------------------------------------------------------
# Read all
# ---------------------------------------------------------------------------

class NotificationReadAllTests(TestCase):

    def setUp(self):
        self.alice = make_user("alice_ra", "alice_ra@example.com")
        self.bob = make_user("bob_ra", "bob_ra@example.com")
        _make_notification(self.alice, is_read=False)
        _make_notification(self.alice, is_read=False)
        _make_notification(self.alice, is_read=True)
        _make_notification(self.bob, is_read=False)

    def test_marks_all_unread_as_read(self):
        r = authed_client(self.alice).post("/api/notifications/read-all/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data["marked_read"], 2)
        self.assertEqual(
            Notification.objects.filter(user=self.alice, is_read=False).count(), 0
        )

    def test_does_not_affect_other_users(self):
        authed_client(self.alice).post("/api/notifications/read-all/")
        self.assertEqual(
            Notification.objects.filter(user=self.bob, is_read=False).count(), 1
        )

    def test_returns_zero_when_nothing_unread(self):
        Notification.objects.filter(user=self.alice).update(is_read=True)
        r = authed_client(self.alice).post("/api/notifications/read-all/")
        self.assertEqual(r.data["marked_read"], 0)
