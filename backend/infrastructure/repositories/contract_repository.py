# backend/infrastructure/repositories/contract_repository.py
from backend.contracts.models import Contract


class ContractRepository:

    def get(self, contract_id):
        return Contract.objects.get(id=contract_id)

    def save(self, contract):
        contract.save()
        return contract

    def create(self, initiator, counterparty_email, structure_type):
        return Contract.objects.create(
        initiator=initiator,
        counterparty_email=counterparty_email,
        structure_type=structure_type,
    )

