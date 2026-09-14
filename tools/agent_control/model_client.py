"""Proposal-only model adapters. No SDK, HTTP transport, key loading or execution."""
from typing import Protocol

from .protocol import ARGUMENTS, ModelProposal, Operation, bounded_json
from .serialization import canonical_json
from .types import ValidationError


class ModelClient(Protocol):
    def propose(self, context, allowed_operations): ...


class FakeModelClient:
    """Deterministic synthetic response source; does not inspect context or credentials."""
    def __init__(self, response):
        if type(response) is not bytes:
            raise ValidationError('Synthetic response must be bytes.')
        self.response = response

    def propose(self, context, allowed_operations):
        proposal = ModelProposal.parse(self.response)
        if proposal.operation not in allowed_operations:
            raise ValidationError('Operation not offered.')
        return proposal


def function_tool(operation):
    op = Operation(operation)
    fields = {}
    for key in ARGUMENTS[op]:
        fields[key] = ({'type': 'array', 'items': {'type': 'string'}} if key == 'argv'
                       else {'type': 'string'})
    return {'type': 'function', 'name': op.value, 'strict': True,
            'description': 'Propose an operation for independent controller authorization.',
            'parameters': {'type': 'object', 'properties': fields,
                           'required': list(fields), 'additionalProperties': False}}


class OpenAIProposalClient:
    """Offline Responses API contract only. Transport activation is separately gated.

    Request IDs/execution IDs come from the trusted caller, not model arguments.
    No credential parameter is accepted or transferred to any worker structure.
    """
    def propose(self, context, allowed_operations):
        raise ValidationError('Live OpenAI transport is not implemented or enabled.')

    def build_request(self, model, context, allowed_operations):
        if type(model) is not str or not model or type(context) is not str or len(context) > 32768:
            raise ValidationError('Invalid model context.')
        ops = tuple(Operation(op) for op in allowed_operations)
        if not ops or len(set(ops)) != len(ops):
            raise ValidationError('Explicit unique operations required.')
        return {'model': model, 'input': context, 'tools': [function_tool(op) for op in ops],
                'tool_choice': 'required', 'parallel_tool_calls': False, 'store': False}

    def parse_response(self, raw, *, request_id, execution_id, allowed_operations):
        data = bounded_json(raw)
        if type(data) is not dict or data.get('status') != 'completed' or data.get('error') is not None:
            raise ValidationError('Incomplete or failed model response.')
        output = data.get('output')
        if type(output) is not list or any(type(item) is not dict for item in output):
            raise ValidationError('Invalid model output.')
        if any(item.get('type') not in {'function_call', 'reasoning'} for item in output):
            raise ValidationError('Unexpected output item type.')
        calls = [item for item in output if item.get('type') == 'function_call']
        if len(calls) != 1:
            raise ValidationError('Exactly one proposal required.')
        call = calls[0]
        if type(call.get('call_id')) is not str or not 1 <= len(call['call_id']) <= 256:
            raise ValidationError('Invalid function call identifier.')
        if call.get('name') not in {Operation(op).value for op in allowed_operations}:
            raise ValidationError('Unadvertised function call.')
        if type(call.get('arguments')) is not str:
            raise ValidationError('Function arguments must be JSON text.')
        args = bounded_json(call['arguments'].encode('utf-8'))
        proposal = ModelProposal.parse(canonical_json(dict(version=1, request_id=request_id,
            execution_id=execution_id, operation=call['name'], arguments=args)).encode('utf-8'))
        return call['call_id'], proposal

    def function_output(self, call_id, *, accepted):
        if type(call_id) is not str or not 1 <= len(call_id) <= 256 or type(accepted) is not bool:
            raise ValidationError('Invalid function result.')
        # Deliberately status-only: arbitrary worker stdout is not safe model context.
        return {'type': 'function_call_output', 'call_id': call_id,
                'output': canonical_json({'accepted': accepted})}
