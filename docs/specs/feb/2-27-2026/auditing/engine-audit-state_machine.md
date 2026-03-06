
ENGINE_AUDIT_STATE_MACHINE_FULL.md

FILE: backend/engine/contracts/state_machine.py

PURPOSE:
Defines allowed lifecycle transitions for contract versions and enforces legal state changes.

------------------------------------------------------------
SECTION 1 — ALLOWED TRANSITIONS MATRIX (CONFIRMED IMPLEMENTED)
------------------------------------------------------------

ALLOWED_TRANSITIONS = {

    "draft": ["sent", "archived"],

    "sent": ["negotiating", "signed", "rejected", "archived"],

    "negotiating": ["signed", "rejected", "archived"],

    "signed": ["superseded", "archived"],

    "rejected": ["archived"],

    "superseded": ["archived"],

    "archived": []
}

CONCLUSION:
A formal transition graph exists.
Each state explicitly defines forward transitions.
Terminal state: archived.

------------------------------------------------------------
SECTION 2 — TRANSITION ENFORCEMENT (CONFIRMED IMPLEMENTED)
------------------------------------------------------------

validate_transition(current_status, new_status):

- Looks up allowed transitions for current_status.
- Checks whether new_status is in allowed list.
- Raises ValueError if illegal.
- Prevents unauthorized state jumps.

This enforces:

- No draft → signed direct jump.
- No signed → draft rollback.
- No archived → any transition.
- No bypassing negotiation phase.

CONCLUSION:
Illegal transitions are programmatically blocked.

------------------------------------------------------------
SECTION 3 — LIFECYCLE COVERAGE ANALYSIS
------------------------------------------------------------

Defined states:

- draft
- sent
- negotiating
- signed
- rejected
- superseded
- archived

These match ContractVersion.STATUS_CHOICES in models.py.

State graph is coherent:

draft → sent → negotiating → signed → superseded → archived
                      ↘ rejected → archived

Terminal states:
- archived (fully terminal)
- superseded (semi-terminal, only moves to archived)
- rejected (moves only to archived)

CONCLUSION:
Lifecycle graph is complete and logically consistent.

------------------------------------------------------------
SECTION 4 — WHAT IS MISSING / NOT PRESENT
------------------------------------------------------------

1. No Side Effects
   - validate_transition only validates.
   - Does not mutate state.
   - Does not trigger activation.
   - Does not emit events.

2. No Contract-Level Integration
   - State machine is version-level only.
   - Does not control contract.is_active.
   - Does not bind to obligation lifecycle.

3. No Transition Orchestration Layer
   - No audit logging.
   - No hooks.
   - No automatic cascading effects.

4. No Idempotency Guard
   - Re-applying same status not handled explicitly.
   - Relies on caller discipline.

------------------------------------------------------------
SECTION 5 — CURRENT ENGINE STATUS BASED ON THIS FILE
------------------------------------------------------------

CONFIRMED BUILT:
- Formal version lifecycle state graph.
- Explicit allowed transitions.
- Illegal transition blocking.
- Terminal state enforcement.
- STATUS_CHOICES alignment with models.

CONFIRMED NOT COMPLETE:
- No orchestration layer.
- No side-effect engine.
- No activation binding.
- No contract-level lifecycle coordination.
- No event emission.

------------------------------------------------------------
FINAL ASSESSMENT
------------------------------------------------------------

The version lifecycle state machine is fully defined and structurally sound. Transition enforcement exists and illegal state changes are blocked.

However, the state machine is isolated validation logic only. It does not orchestrate lifecycle events, activation, automation, or contract-level state management. Those layers remain partially implemented or disconnected.



