# ]\backend/adapters/contract_adapter.py

from backend.contracts.models import Contract, ContractObligation
from backend.adapters.obligation_adapter import ObligationAdapter
from backend.engine.lifecycle_core.lifecycle_manager import LifecycleManager


class ContractAdapter:
    """
    Adapter that connects Django Contract models
    to the lifecycle engine.
    """

    @staticmethod
    def load_contract_obligations(contract_id):
        """
        Load obligations from database
        and convert them to engine objects.
        """

        obligations = ContractObligation.objects.filter(contract_id=contract_id)

        engine_obligations = []

        for ob in obligations:
            engine_ob = ObligationAdapter.model_to_payment(ob)
            engine_obligations.append(engine_ob)

        return engine_obligations

    @staticmethod
    def run_lifecycle(contract_id):
        """
        Run lifecycle evaluation for a contract.
        """

        engine_obligations = ContractAdapter.load_contract_obligations(contract_id)

        LifecycleManager.evaluate_contract_instances(engine_obligations)

        return engine_obligations

