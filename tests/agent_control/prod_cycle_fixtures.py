"""Deterministic fake PROD-01 model. Test/development use only."""
from copy import deepcopy


class DeterministicProductFake:
    adapter_kind = "DETERMINISTIC_FAKE"
    test_only = True
    network_enabled = False

    def __init__(self, changes=None):
        self.changes = changes or {}

    def propose(self, task):
        founder = next(item for item in task["input_references"]
                       if item["reference_type"] == "FOUNDER_DIRECTION")
        proposal = {
            "agent_id": "PROD-01",
            "task_id": task["task_id"],
            "proposal_id": "00000000-0000-4000-8000-000000000701",
            "predecessor_proposal_id": None,
            "proposal_type": "PRODUCT_REQUIREMENT_PROPOSAL",
            "title": "Agent task history display",
            "problem_user_need": "A bonUP user needs a clear history of agent task outcomes.",
            "objective": task["objective"],
            "proposed_requirement": "The interface should present bounded agent task summaries with identity, status, artifacts, validation, result, and evidence references.",
            "acceptance_intent": [
                "A user can distinguish each agent and task identity.",
                "A user can understand status, result, and referenced evidence.",
                "The display states that human task documents do not create execution authority."
            ],
            "dependencies": [],
            "assumptions": ["Only sanitized task-document projections are display inputs."],
            "risks_open_questions": ["Visibility rules for different users require separate product approval."],
            "priority_recommendation": "P2",
            "evidence_references": [deepcopy(founder)],
            "knowledge_state": "WORKING",
        }
        proposal.update(deepcopy(self.changes))
        return proposal
