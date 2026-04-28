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
