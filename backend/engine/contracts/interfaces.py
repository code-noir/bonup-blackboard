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
    def count(self, contract):
        pass

    @abstractmethod
    def save(self, version):
        pass


class RequestChangeRepository(ABC):

    @abstractmethod
    def save(self, request):
        pass


