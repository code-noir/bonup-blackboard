# backend/bonup/tests.py
#
# Focused tests for the Soul, Entity, SoulEntity, and BusinessEntity.entity
# pointer models.
# Covers: creation, one-to-one constraints, cascade behaviour, reverse accessors.
# No API layer, no routes, no authority relations (those belong to later sprints).

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

from backend.users.models import BusinessEntity

from .models import Entity, Soul, SoulEntity

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


# ===========================================================================
# Entity tests
# ===========================================================================

def make_entity(entity_type=Entity.ENTITY_TYPE_SOUL):
    return Entity.objects.create(entity_type=entity_type)


class EntityCreationTest(TestCase):
    """Entity can be created for each valid entity_type."""

    def test_soul_entity_type_created(self):
        entity = make_entity(Entity.ENTITY_TYPE_SOUL)
        self.assertIsNotNone(entity.pk)
        self.assertEqual(entity.entity_type, Entity.ENTITY_TYPE_SOUL)

    def test_business_entity_type_created(self):
        entity = make_entity(Entity.ENTITY_TYPE_BUSINESS)
        self.assertIsNotNone(entity.pk)
        self.assertEqual(entity.entity_type, Entity.ENTITY_TYPE_BUSINESS)

    def test_entity_has_uuid_pk(self):
        entity = make_entity()
        self.assertIsNotNone(entity.id)

    def test_entity_str(self):
        entity = make_entity(Entity.ENTITY_TYPE_SOUL)
        self.assertIn("soul_entity", str(entity))
        self.assertIn(str(entity.id), str(entity))


# ===========================================================================
# SoulEntity tests
# ===========================================================================

def make_soul_with_user(username, email):
    user = make_user(username, email)
    return Soul.objects.create(user=user)


class SoulEntityCreationTest(TestCase):
    """SoulEntity can be created linking a Soul to a soul_entity Entity."""

    def test_soul_entity_created(self):
        soul = make_soul_with_user("h1", "h1@example.com")
        entity = make_entity(Entity.ENTITY_TYPE_SOUL)
        se = SoulEntity.objects.create(soul=soul, entity=entity)
        self.assertIsNotNone(se.pk)
        self.assertEqual(se.soul_id, soul.pk)
        self.assertEqual(se.entity_id, entity.pk)

    def test_soul_entity_has_uuid_pk(self):
        soul = make_soul_with_user("h2", "h2@example.com")
        entity = make_entity()
        se = SoulEntity.objects.create(soul=soul, entity=entity)
        self.assertIsNotNone(se.id)

    def test_soul_entity_str(self):
        soul = make_soul_with_user("h3", "h3@example.com")
        entity = make_entity()
        se = SoulEntity.objects.create(soul=soul, entity=entity)
        self.assertIn(str(soul.pk), str(se))
        self.assertIn(str(entity.pk), str(se))


class SoulEntityOneToOneConstraintsTest(TestCase):
    """Both OneToOneField constraints must be enforced at DB level."""

    def test_duplicate_soul_raises_integrity_error(self):
        """A second SoulEntity for the same Soul must be rejected."""
        soul = make_soul_with_user("h4", "h4@example.com")
        entity1 = make_entity()
        entity2 = make_entity()
        SoulEntity.objects.create(soul=soul, entity=entity1)
        with self.assertRaises(IntegrityError):
            SoulEntity.objects.create(soul=soul, entity=entity2)

    def test_duplicate_entity_raises_integrity_error(self):
        """A second SoulEntity for the same Entity must be rejected."""
        soul1 = make_soul_with_user("h5", "h5@example.com")
        soul2 = make_soul_with_user("h6", "h6@example.com")
        entity = make_entity()
        SoulEntity.objects.create(soul=soul1, entity=entity)
        with self.assertRaises(IntegrityError):
            SoulEntity.objects.create(soul=soul2, entity=entity)


class SoulEntityCascadeTest(TestCase):
    """SoulEntity must be deleted when either Soul or Entity is deleted."""

    def test_deleted_when_soul_deleted(self):
        user = make_user("h7", "h7@example.com")
        soul = Soul.objects.create(user=user)
        entity = make_entity()
        se = SoulEntity.objects.create(soul=soul, entity=entity)
        se_pk = se.pk
        soul.delete()
        self.assertFalse(SoulEntity.objects.filter(pk=se_pk).exists())

    def test_deleted_when_entity_deleted(self):
        soul = make_soul_with_user("h8", "h8@example.com")
        entity = make_entity()
        se = SoulEntity.objects.create(soul=soul, entity=entity)
        se_pk = se.pk
        entity.delete()
        self.assertFalse(SoulEntity.objects.filter(pk=se_pk).exists())


class SoulEntityReverseAccessorTest(TestCase):
    """Reverse accessors on both Soul and Entity must resolve correctly."""

    def test_soul_reverse_accessor(self):
        soul = make_soul_with_user("h9", "h9@example.com")
        entity = make_entity()
        se = SoulEntity.objects.create(soul=soul, entity=entity)
        self.assertEqual(soul.soul_entity.pk, se.pk)

    def test_entity_reverse_accessor(self):
        soul = make_soul_with_user("h10", "h10@example.com")
        entity = make_entity()
        se = SoulEntity.objects.create(soul=soul, entity=entity)
        self.assertEqual(entity.soul_entity.pk, se.pk)

    def test_soul_without_soul_entity_raises(self):
        soul = make_soul_with_user("h11", "h11@example.com")
        with self.assertRaises(SoulEntity.DoesNotExist):
            _ = soul.soul_entity

    def test_entity_without_soul_entity_raises(self):
        entity = make_entity()
        with self.assertRaises(SoulEntity.DoesNotExist):
            _ = entity.soul_entity


# ===========================================================================
# BusinessEntity.entity pointer tests (AG2b)
# ===========================================================================

def make_business_entity(owner, name="Test Biz"):
    return BusinessEntity.objects.create(
        owner=owner,
        name=name,
        business_type="LLC",
    )


def make_biz_entity_row():
    """Create a standalone Entity row of type business_entity."""
    return Entity.objects.create(entity_type=Entity.ENTITY_TYPE_BUSINESS)


class BusinessEntityPointerNullableTest(TestCase):
    """BusinessEntity.entity is nullable at the schema level (backfill compat)
    but is auto-populated on every new save() call."""

    def test_business_entity_created_with_entity_pointer_auto_set(self):
        user = make_user("biz1", "biz1@example.com")
        biz = make_business_entity(user)
        biz.refresh_from_db()
        # save() hook must have created and linked an Entity row.
        self.assertIsNotNone(biz.entity_id)

    def test_business_entity_functions_normally_with_pointer(self):
        user = make_user("biz2", "biz2@example.com")
        biz = make_business_entity(user)
        self.assertEqual(biz.owner, user)
        self.assertEqual(biz.business_type, "LLC")


class BusinessEntityPointerAssignTest(TestCase):
    """An Entity (business_entity type) can be assigned to a BusinessEntity."""

    def test_entity_pointer_can_be_set(self):
        user = make_user("biz3", "biz3@example.com")
        biz = make_business_entity(user)
        entity = make_biz_entity_row()
        biz.entity = entity
        biz.save(update_fields=["entity"])
        biz.refresh_from_db()
        self.assertEqual(biz.entity_id, entity.pk)

    def test_entity_type_is_business_entity(self):
        entity = make_biz_entity_row()
        self.assertEqual(entity.entity_type, Entity.ENTITY_TYPE_BUSINESS)


class BusinessEntityPointerOneToOneConstraintTest(TestCase):
    """Two BusinessEntities cannot share the same Entity pointer."""

    def test_duplicate_entity_pointer_raises_integrity_error(self):
        user = make_user("biz4", "biz4@example.com")
        biz1 = make_business_entity(user, name="Biz A")
        biz2 = make_business_entity(user, name="Biz B")
        entity = make_biz_entity_row()
        biz1.entity = entity
        biz1.save(update_fields=["entity"])
        biz2.entity = entity
        with self.assertRaises(IntegrityError):
            biz2.save(update_fields=["entity"])


class BusinessEntityPointerSetNullTest(TestCase):
    """Deleting an Entity sets BusinessEntity.entity to NULL (SET_NULL); row survives."""

    def test_business_entity_survives_entity_deletion(self):
        user = make_user("biz5", "biz5@example.com")
        biz = make_business_entity(user)
        entity = make_biz_entity_row()
        biz.entity = entity
        biz.save(update_fields=["entity"])
        biz_pk = biz.pk
        entity.delete()
        biz.refresh_from_db()
        self.assertTrue(BusinessEntity.objects.filter(pk=biz_pk).exists())
        self.assertIsNone(biz.entity_id)


class BusinessEntityPointerReverseAccessorTest(TestCase):
    """entity.business_entity reverse accessor resolves to the correct BusinessEntity."""

    def test_reverse_accessor_resolves(self):
        user = make_user("biz6", "biz6@example.com")
        biz = make_business_entity(user)
        entity = make_biz_entity_row()
        biz.entity = entity
        biz.save(update_fields=["entity"])
        self.assertEqual(entity.business_entity.pk, biz.pk)

    def test_entity_without_business_entity_raises(self):
        entity = make_biz_entity_row()
        with self.assertRaises(BusinessEntity.DoesNotExist):
            _ = entity.business_entity


class BusinessEntityDeleteDoesNotCascadeToEntityTest(TestCase):
    """Deleting a BusinessEntity does not delete the linked Entity row."""

    def test_entity_survives_business_entity_deletion(self):
        user = make_user("biz7", "biz7@example.com")
        biz = make_business_entity(user)
        entity_pk = biz.entity_id
        biz.delete()
        self.assertTrue(Entity.objects.filter(pk=entity_pk).exists())


# ===========================================================================
# BusinessEntity.entity auto-creation (save() hook) tests
# ===========================================================================

class BusinessEntityAutoEntityCreationTest(TestCase):
    """save() hook creates a matching Entity for every new BusinessEntity."""

    def test_new_business_entity_auto_creates_entity(self):
        user = make_user("biz8", "biz8@example.com")
        biz = make_business_entity(user)
        biz.refresh_from_db()
        self.assertIsNotNone(biz.entity_id)
        self.assertTrue(Entity.objects.filter(pk=biz.entity_id).exists())

    def test_auto_created_entity_has_correct_type(self):
        user = make_user("biz9", "biz9@example.com")
        biz = make_business_entity(user)
        entity = Entity.objects.get(pk=biz.entity_id)
        self.assertEqual(entity.entity_type, Entity.ENTITY_TYPE_BUSINESS)

    def test_repeated_save_does_not_create_duplicate_entity(self):
        user = make_user("biz10", "biz10@example.com")
        biz = make_business_entity(user)
        first_entity_id = biz.entity_id
        # Save again — must not create a second Entity row.
        biz.name = "Updated Name"
        biz.save()
        biz.refresh_from_db()
        self.assertEqual(biz.entity_id, first_entity_id)
        self.assertEqual(
            Entity.objects.filter(entity_type=Entity.ENTITY_TYPE_BUSINESS).count(),
            1,
        )

    def test_set_null_still_works_after_hook(self):
        """DB-level SET_NULL on Entity deletion is unaffected by the save() hook."""
        user = make_user("biz11", "biz11@example.com")
        biz = make_business_entity(user)
        biz_pk = biz.pk
        # Delete the Entity at DB level — triggers SET_NULL.
        Entity.objects.filter(pk=biz.entity_id).delete()
        biz.refresh_from_db()
        # BusinessEntity survives, pointer is NULL.
        self.assertTrue(BusinessEntity.objects.filter(pk=biz_pk).exists())
        self.assertIsNone(biz.entity_id)
