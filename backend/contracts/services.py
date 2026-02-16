# backend/contracts/services.py
#
# SPEC: dev/specs/contract-creation-flow.md

from .models import Contract, ContractVersion
from django.contrib.auth import get_user_model

User = get_user_model()


class ContractService:
    """
    Service layer for contract creation and lifecycle logic.
    Keeps business logic out of views.
    """

    @staticmethod
    def create_contract(initiator, counterparty_email, content):
        """
        Creates a contract container and its initial version.
        """

        contract = Contract.objects.create(
            initiator=initiator,
            counterparty_email=counterparty_email,
        )

        ContractVersion.create_initial_version(
            contract=contract,
            content=content,
            user=initiator
        )

        return contract
