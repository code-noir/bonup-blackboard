"""Deterministic PROD-01 behavioral simulation; no execution or registry authority."""
from dataclasses import dataclass

from .prod_contract import contract_digest, load_contract, validate_product_proposal, validate_product_task
from .serialization import canonical_json, digest
from .types import ValidationError


@dataclass(frozen=True)
class SyntheticProductCycle:
    task: dict
    proposal: dict
    proposal_bytes: bytes
    proposal_digest: str
    task_document_bytes: bytes


def _fake_adapter(adapter):
    if (getattr(adapter, "adapter_kind", None) != "DETERMINISTIC_FAKE"
            or getattr(adapter, "test_only", None) is not True
            or getattr(adapter, "network_enabled", None) is not False
            or not callable(getattr(adapter, "propose", None))):
        raise ValidationError("PROD-01 synthetic cycle requires a deterministic test-only fake adapter.")


def _render_document(task, proposal, proposal_digest):
    metadata = {
        "agent_id": "PROD-01",
        "authority": "PROPOSAL_ONLY",
        "contract_digest": contract_digest(),
        "knowledge_state": "WORKING",
        "proposal_digest": proposal_digest,
        "proposal_id": proposal["proposal_id"],
        "status": "SYNTHETIC_PROPOSAL_VALIDATED",
        "synthetic": True,
        "task_id": task["task_id"],
    }
    evidence = "\n".join(
        f"- {item['reference_type']}: {item['reference_id']} (sha256:{item['digest']})"
        for item in proposal["evidence_references"]
    ) or "None recorded."
    acceptance = "\n".join(f"- {item}" for item in proposal["acceptance_intent"])
    return (
        "<!-- bonUP synthetic PROD-01 task metadata\n"
        + canonical_json(metadata)
        + "\n-->\n\n"
        + f"# {task['task_id']} — {proposal['title']}\n\n"
        + "**HUMAN-READABLE PROJECTION — NOT EXECUTION AUTHORITY**\n\n"
        + "**SYNTHETIC — NON-AUTHORITATIVE — NOT APPROVED**  \n"
        + "**Agent:** PROD-01  \n"
        + "**Role:** Product  \n"
        + "**Authority:** PROPOSAL_ONLY  \n"
        + "**Status:** SYNTHETIC_PROPOSAL_VALIDATED  \n"
        + "**Knowledge state:** WORKING\n\n"
        + f"## Objective\n\n{task['objective']}\n\n"
        + "## Work Performed\n\n"
        + f"- Processed bounded task class `{task['task_class']}` with a deterministic test-only fake model.\n"
        + "- Validated the candidate as a non-authoritative product proposal.\n\n"
        + "## Proposal Artifact\n\n"
        + f"- Type: `{proposal['proposal_type']}`\n"
        + f"- Proposal ID: `{proposal['proposal_id']}`\n"
        + f"- Digest: `sha256:{proposal_digest}`\n"
        + "- Storage: in-memory canonical JSON synthetic artifact\n\n"
        + f"### Problem / User Need\n\n{proposal['problem_user_need']}\n\n"
        + f"### Proposed Requirement\n\n{proposal['proposed_requirement']}\n\n"
        + f"### Acceptance Intent\n\n{acceptance}\n\n"
        + f"## Evidence References\n\n{evidence}\n\n"
        + "## Result\n\n"
        + "A bounded WORKING product proposal was validated. No approval, assignment, grant, implementation, or publication occurred.\n"
    ).encode("utf-8")


def run_synthetic_product_cycle(task_input, adapter):
    """Run an in-memory fake cycle; no files, commands, network, processes, or registry writes."""
    contract = load_contract()
    if contract["status"] != "NON_ACTIVE" or contract["authority_mode"] != "PROPOSAL_ONLY":
        raise ValidationError("PROD-01 synthetic cycle requires the non-active proposal-only contract.")
    _fake_adapter(adapter)
    task = validate_product_task(task_input)
    detached = validate_product_task(task)
    proposal = validate_product_proposal(adapter.propose(detached))
    if proposal["task_id"] != task["task_id"]:
        raise ValidationError("PROD-01 proposal belongs to another task.")
    available = {canonical_json(item) for item in task["input_references"]}
    if any(canonical_json(item) not in available for item in proposal["evidence_references"]):
        raise ValidationError("PROD-01 proposal introduced an unbound evidence reference.")
    proposal_bytes = (canonical_json(proposal) + "\n").encode("utf-8")
    proposal_digest = digest(proposal)
    document = _render_document(task, proposal, proposal_digest)
    return SyntheticProductCycle(task, proposal, proposal_bytes, proposal_digest, document)
