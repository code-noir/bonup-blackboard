

# backend/contracts/models.py
#
# SPEC: dev/specs/contract-container.md
# SPEC: dev/specs/contract-version-engine.md

from django.db import models
from django.conf import settings
import uuid


# ============================================================
# CONTRACT CONTAINER
# ============================================================

class Contract(models.Model):
    """
    Contract container.
    Holds identity and relationship.
    Versions live separately.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    initiator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="initiated_contracts"
    )

    counterparty_email = models.EmailField()

    created_at = models.DateTimeField(auto_now_add=True)

    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Contract {self.id}"


# ============================================================
# CONTRACT VERSION ENGINE (IMMUTABLE)
# ============================================================

class ContractVersion(models.Model):
    """
    Immutable snapshot of a contract at a specific moment.

    Every negotiation, amendment, or counter creates a new version.
    Previous versions are NEVER edited.
    """

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("sent", "Sent"),
        ("negotiating", "Negotiating"),
        ("signed", "Signed"),
        ("superseded", "Superseded"),
        ("archived", "Archived"),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )

    contract = models.ForeignKey(
        Contract,
        on_delete=models.CASCADE,
        related_name="versions"
    )

    version_number = models.PositiveIntegerField()

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    previous_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="next_versions"
    )

    superseded = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="draft"
    )

    content_snapshot = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("contract", "version_number")
        ordering = ["-version_number"]

    def __str__(self):
        return f"{self.contract.id} - v{self.version_number} - {self.status}"

    def save(self, *args, **kwargs):
        """
        Enforces version sequencing and immutability.
        """

        # Creating new version
        if not self.pk:

            last_version = (
                ContractVersion.objects
                .filter(contract=self.contract)
                .order_by("-version_number")
                .first()
            )

            if last_version:
                self.version_number = last_version.version_number + 1
                self.previous_version = last_version

                last_version.status = "superseded"
                last_version.superseded = True
                last_version.save()

            else:
                self.version_number = 1

        else:
            raise Exception("Contract versions are immutable.")

        super().save(*args, **kwargs)

    # --------------------------------------------------------

    ALLOWED_TRANSITIONS = {
        "draft": ["sent", "archived"],
        "sent": ["negotiating", "signed", "archived"],
        "negotiating": ["superseded", "archived"],
        "signed": ["archived"],
        "superseded": [],
        "archived": [],
    }

    def transition_to(self, new_status):
        """
        Enforces valid contract state transitions.
        """

        if new_status not in dict(self.STATUS_CHOICES):
            raise ValueError(f"Invalid status: {new_status}")

        allowed = self.ALLOWED_TRANSITIONS.get(self.status, [])

        if new_status not in allowed:
            raise ValueError(
                f"Illegal transition from '{self.status}' to '{new_status}'"
            )

        self.status = new_status
        super().save()

    # --------------------------------------------------------

    @classmethod
    def create_initial_version(cls, contract, content, user=None):
        """
        Creates the first version of a contract.
        """

        if cls.objects.filter(contract=contract).exists():
            raise Exception("Initial version already exists.")

        return cls.objects.create(
            contract=contract,
            content_snapshot=content,
            created_by=user,
            status="draft"
        )

    @classmethod
    def create_new_version(cls, contract, content, user=None):
        """
        Creates a new negotiated/amended version.
        Automatically supersedes the previous version.
        """

        latest = (
            cls.objects
            .filter(contract=contract)
            .order_by("-version_number")
            .first()
        )

        if not latest:
            raise Exception("No previous version exists.")

        return cls.objects.create(
            contract=contract,
            content_snapshot=content,
            created_by=user,
            status="draft"
        )

