# backend/bonup/tests.py
#
# Focused tests for the Soul model.
# Covers: creation, one-to-one constraint, cascade behaviour, reverse accessor.
# No API layer, no routes, no authority relations (those belong to later sprints).

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from .models import Soul

User = get_user_model()


def make_user(username, email):
    return User.objects.create_user(username=username, email=email, password="testpass123")


# ------------------------------------------------------------------
# Soul creation
# ------------------------------------------------------------------

class SoulCreationTest(TestCase):
    """Soul can be created for an existing User."""

    def test_soul_created_with_valid_user(self):
        user = make_user("alice", "alice@example.com")
        soul = Soul.objects.create(user=user)
        self.assertIsNotNone(soul.pk)
        self.assertEqual(soul.user_id, user.pk)

    def test_soul_has_uuid_pk(self):
        user = make_user("bob", "bob@example.com")
        soul = Soul.objects.create(user=user)
        # UUID primary keys are represented as strings or UUID objects — just confirm non-null
        self.assertIsNotNone(soul.id)

    def test_soul_str(self):
        user = make_user("carol", "carol@example.com")
        soul = Soul.objects.create(user=user)
        self.assertIn(str(user.pk), str(soul))


# ------------------------------------------------------------------
# One-to-one constraint
# ------------------------------------------------------------------

class SoulOneToOneConstraintTest(TestCase):
    """A second Soul for the same User must be rejected at the DB level."""

    def test_duplicate_soul_raises_integrity_error(self):
        user = make_user("dave", "dave@example.com")
        Soul.objects.create(user=user)
        with self.assertRaises(IntegrityError):
            Soul.objects.create(user=user)


# ------------------------------------------------------------------
# Cascade behaviour
# ------------------------------------------------------------------

class SoulUserCascadeTest(TestCase):
    """Deleting the User must delete the associated Soul."""

    def test_soul_deleted_when_user_deleted(self):
        user = make_user("eve", "eve@example.com")
        soul = Soul.objects.create(user=user)
        soul_pk = soul.pk
        user.delete()
        self.assertFalse(Soul.objects.filter(pk=soul_pk).exists())


# ------------------------------------------------------------------
# Reverse accessor
# ------------------------------------------------------------------

class SoulReverseAccessorTest(TestCase):
    """user.soul reverse accessor must resolve to the correct Soul."""

    def test_reverse_accessor_resolves(self):
        user = make_user("frank", "frank@example.com")
        soul = Soul.objects.create(user=user)
        self.assertEqual(user.soul.pk, soul.pk)

    def test_user_without_soul_raises_on_reverse_access(self):
        user = make_user("grace", "grace@example.com")
        with self.assertRaises(Soul.DoesNotExist):
            _ = user.soul


# ------------------------------------------------------------------
# Soul requires a User
# ------------------------------------------------------------------

class SoulRequiresUserTest(TestCase):
    """Soul.user is non-nullable; creation without a user must fail."""

    def test_soul_without_user_raises(self):
        with self.assertRaises((IntegrityError, ValueError)):
            Soul.objects.create(user=None)
