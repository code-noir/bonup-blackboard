# backend/bonup/models.py

import uuid

from django.conf import settings
from django.db import models


class Soul(models.Model):
    """
    The natural human actor at the bonUP layer.

    A Soul represents the real individual — the person behind one or more
    system accounts, entities, or roles. It is always a natural person.
    There is at most one Soul per natural person.

    RELATIONSHIP TO USER
    --------------------
    Soul holds a one-to-one FK to the Django auth User (system account /
    bonID account). The FK direction is Soul → User, keeping the auth model
    clean. A Soul cannot exist without an associated User in phase one.

    RELATIONSHIP TO BONUSERPROFILE
    ------------------------------
    Soul does not replace BonUserProfile. BonUserProfile holds bonID state
    and email verification. Soul holds human-actor identity at the bonUP
    layer. They coexist as separate concerns and both point to User.

    SCOPE
    -----
    Soul is a bonUP-layer concept. It sits above individual products
    (Blackboard, SOL, future verticals). Products do not own Soul.

    Future FKs that need to reference the natural human actor should point
    to Soul, not to User and not to BonUserProfile.

    PHASE ONE BOUNDARIES
    --------------------
    No backward FKs from Contract, ContractPro, or BusinessEntity point
    here yet. AuthorityHolder and Entity are not yet implemented.
    See docs/current-state/BONUP_AUTHORITY_FOUNDATION_SPEC.md for the
    full build sequence.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="soul",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Soul"
        verbose_name_plural = "Souls"

    def __str__(self):
        return f"Soul({self.user_id})"


class Entity(models.Model):
    """
    The operating/legal actor at the bonUP layer.

    Entity is a standalone concrete model. It is NOT a Django MTI base class
    and does NOT use ContentType/GenericForeignKey. Subtype records (SoulEntity,
    and later BusinessEntity via a nullable pointer) each hold a OneToOneField
    that points *to* an Entity row. The entity_type discriminator field records
    which subtype is active.

    SUBTYPES
    --------
    soul_entity  — a natural person acting as their own operating actor.
                   Represented by a SoulEntity row pointing here.
    business_entity — a formal business structure (LLC, Corp, Trust, etc.).
                   Represented later by a nullable BusinessEntity.entity pointer
                   (AG2b), not by MTI inheritance.

    PHASE ONE BOUNDARIES
    --------------------
    BusinessEntity does not yet have a pointer to Entity. That is AG2b.
    No existing FKs (Contract.entity, ContractProAccessGrant.business) point
    here yet. AuthorityHolder is not yet implemented.
    See docs/current-state/BONUP_AUTHORITY_FOUNDATION_SPEC.md AG2a/AG2b.
    """

    ENTITY_TYPE_SOUL = "soul_entity"
    ENTITY_TYPE_BUSINESS = "business_entity"
    ENTITY_TYPE_CHOICES = [
        (ENTITY_TYPE_SOUL, "Soul Entity"),
        (ENTITY_TYPE_BUSINESS, "Business Entity"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    entity_type = models.CharField(
        max_length=20,
        choices=ENTITY_TYPE_CHOICES,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Entity"
        verbose_name_plural = "Entities"

    def __str__(self):
        return f"Entity({self.entity_type}, {self.id})"


class SoulEntity(models.Model):
    """
    The personal operating surface for a Soul.

    SoulEntity represents a natural person (Soul) acting as an operating
    actor in their own right — contracting, owning obligations, etc. in a
    personal capacity.

    A Soul is not the same as a SoulEntity. Soul is the natural person.
    SoulEntity is that person's personal operating surface record.

    RELATIONSHIPS
    -------------
    entity  — OneToOneField → Entity (entity_type must be 'soul_entity')
    soul    — OneToOneField → Soul

    In practice, creating a SoulEntity also requires the corresponding
    Entity row to exist with entity_type='soul_entity'. There is one
    SoulEntity per Soul. Enforcement is at the DB level via the OneToOneField
    constraints on both FKs.

    PHASE ONE BOUNDARIES
    --------------------
    No AuthorityHolder is created automatically here. On the personal
    surface, the Soul acts with implicit self-authority over their
    SoulEntity. No AuthorityHolder record is needed in phase one.
    See docs/current-state/BONUP_AUTHORITY_FOUNDATION_SPEC.md Section 4.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    entity = models.OneToOneField(
        Entity,
        on_delete=models.CASCADE,
        related_name="soul_entity",
    )

    soul = models.OneToOneField(
        Soul,
        on_delete=models.CASCADE,
        related_name="soul_entity",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Soul Entity"
        verbose_name_plural = "Soul Entities"

    def __str__(self):
        return f"SoulEntity(soul={self.soul_id}, entity={self.entity_id})"
