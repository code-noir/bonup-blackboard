from backend.engine.contracts.exceptions import (
    NegotiationLimitReached,
)

class ContractService:

    def __init__(self, contract_repo, version_repo):
        self.contract_repo = contract_repo
        self.version_repo = version_repo

    def create_initial_version(self, contract_id, content, user=None):

        contract = self.contract_repo.get(contract_id)

        existing = self.version_repo.count(contract)
        if existing > 0:
            raise Exception("Initial version already exists.")

        return self.version_repo.create(
            contract=contract,
            version_number=1,
            content_snapshot=content,
            created_by=user,
            status="draft"
        )

    def create_new_version(self, contract_id, content, user=None):

        contract = self.contract_repo.get(contract_id)

        current_count = self.version_repo.count(contract)

        if current_count >= contract.max_versions:
            raise NegotiationLimitReached("Negotiation limit reached.")

        latest = self.version_repo.get_latest(contract)

        next_number = 1 if not latest else latest.version_number + 1

        if latest:
            latest.status = "superseded"
            self.version_repo.save(latest)

        return self.version_repo.create(
            contract=contract,
            version_number=next_number,
            content_snapshot=content,
            created_by=user,
            status="draft"
        )



    def sync_contract_obligation(self, contract_obligation):
        """
        Sync a persisted ContractObligation with engine lifecycle logic.
        """

        from backend.engine.contracts.obligations.primitives import ObligationInstance
        from backend.engine.contracts.obligations.lifecycle import process_obligation_lifecycle

        instance = ObligationInstance(
            obligor_id=contract_obligation.obligor_id,
            obligee_id=contract_obligation.obligee_id,
            amount_due=contract_obligation.amount_due,
            due_date=contract_obligation.due_date,
        )

        instance.amount_paid = contract_obligation.amount_paid
        instance.state = contract_obligation.state

        new_state = process_obligation_lifecycle(instance)

        contract_obligation.state = new_state
        contract_obligation.is_defaulted = (new_state == "defaulted")

        contract_obligation.save(update_fields=["state", "is_defaulted"])

        return contract_obligation
