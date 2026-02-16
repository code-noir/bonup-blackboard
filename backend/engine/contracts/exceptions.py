class ContractError(Exception):
    pass


class NegotiationLimitReached(ContractError):
    pass


class ImmutableVersionError(ContractError):
    pass


class InvalidStateTransition(ContractError):
    pass
