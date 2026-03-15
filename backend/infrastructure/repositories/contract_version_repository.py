# backend/infrastructure/repositories/contract_version_repository.py

from backend.contracts.models import ContractVersion


class ContractVersionRepository:

    def create(self, **kwargs):
        return ContractVersion.objects.create(**kwargs)

    def save(self, version):
        version.save()
        return version

    def count(self, contract):
        return ContractVersion.objects.filter(contract=contract).count()

    def get_latest(self, contract):
        return (
            ContractVersion.objects
            .filter(contract=contract)
            .order_by("-version_number")
            .first()
        )
