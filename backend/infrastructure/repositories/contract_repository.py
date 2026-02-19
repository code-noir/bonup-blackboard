
from backend.contracts.models import Contract


class ContractRepository:

    def get(self, contract_id):
        return Contract.objects.get(id=contract_id)

    def save(self, contract):
        contract.save()
        return contract

    def create(self, **kwargs):
        return Contract.objects.create(**kwargs)


