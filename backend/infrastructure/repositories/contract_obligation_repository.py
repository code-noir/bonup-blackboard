from backend.contracts.models import ContractObligation


class ContractObligationRepository:

    def create(self, **kwargs):
        return ContractObligation.objects.create(**kwargs)

    def bulk_create(self, obligations):
        return ContractObligation.objects.bulk_create(obligations)

    def filter_by_contract(self, contract):
        return ContractObligation.objects.filter(contract=contract)
