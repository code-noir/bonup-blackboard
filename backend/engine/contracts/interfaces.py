from abc import ABC, abstractmethod


class ContractRepository(ABC):

    @abstractmethod
    def get(self, contract_id):
        pass

    @abstractmethod
    def save(self, contract):
        pass


class ContractVersionRepository(ABC):

    @abstractmethod
    def get_latest(self, contract):
        pass

    @abstractmethod
    def get_all(self, contract):
        pass

    @abstractmethod
    def get_signed_version(self, contract):
        pass

    @abstractmethod
    def count(self, contract):
        pass

    @abstractmethod
    def save(self, version):
        pass


class ContractObligationRepository(ABC):

    @abstractmethod
    def get_all(self):
        pass

    @abstractmethod
    def list_candidates(self, contract_id=None, limit=None):
        pass

    @abstractmethod
    def update_state(self, obligation, new_state, current_time):
        pass


class RequestChangeRepository(ABC):

    @abstractmethod
    def save(self, request):
        pass


