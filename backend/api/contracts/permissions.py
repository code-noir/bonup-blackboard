# backend/api/contracts/permissions.py

from rest_framework import status
from rest_framework.response import Response


def is_party(user, contract) -> bool:
    """
    Return True if the user is either the initiator or the counterparty
    of the given contract.

    Initiator is stored as a FK (user pk comparison).
    Counterparty is stored as an email; since email is unique across users,
    matching on user.email is safe and requires no schema change.
    """
    return (
        contract.initiator_id == user.pk
        or contract.counterparty_email == user.email
    )


def get_contract_for_object(obj):
    """
    Resolve the Contract instance from any object that traces back to one.

    Supported chains:
      Contract                          → returned directly
      ContractObligation                → obj.contract
      ContractServiceObligation         → obj.contract
      ObligationExecutionSession        → session.payment_obligation.contract
                                          or session.service_obligation.contract
      ObligationExecutionEvent          → event.session → (above)
      ContractApprovalRequest           → obj.contract
      ContractValueAdjustment           → obj.contract
      ContractObligationPromotion       → obj.contract
      Payment                           → obj.contract

    Raises ValueError if the chain cannot be resolved.
    """
    from backend.contracts.models import (
        Contract,
        ContractObligation,
        ContractServiceObligation,
        ObligationExecutionSession,
        ObligationExecutionEvent,
        ContractApprovalRequest,
        ContractValueAdjustment,
        ContractObligationPromotion,
    )
    from backend.payments.models import Payment

    if isinstance(obj, Contract):
        return obj

    if isinstance(obj, (ContractObligation, ContractServiceObligation)):
        return obj.contract

    if isinstance(obj, ObligationExecutionSession):
        if obj.payment_obligation_id:
            return obj.payment_obligation.contract
        if obj.service_obligation_id:
            return obj.service_obligation.contract
        raise ValueError(f"ExecutionSession {obj.pk} has no linked obligation.")

    if isinstance(obj, ObligationExecutionEvent):
        return get_contract_for_object(obj.session)

    if isinstance(obj, (ContractApprovalRequest, ContractValueAdjustment, ContractObligationPromotion)):
        return obj.contract

    if isinstance(obj, Payment):
        return obj.contract

    raise ValueError(f"Cannot resolve contract from object of type {type(obj).__name__}.")


def contract_party_response():
    """Standard 403 returned when a user is not a party to a contract."""
    return Response(
        {"error": "You are not a party to this contract."},
        status=status.HTTP_403_FORBIDDEN,
    )
