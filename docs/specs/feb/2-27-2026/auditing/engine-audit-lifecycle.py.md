ENGINE_AUDIT_OBLIGATION_LIFECYCLE_FULL.md

FILE: backend/engine/contracts/obligations/lifecycle.py

PURPOSE:
Implements the master obligation lifecycle mutation engine. Responsible for evaluating, mutating, and escalating obligation state over time.

------------------------------------------------------------
SECTION 1 — ENTRY CONTRACT (CONFIRMED IMPLEMENTED)
------------------------------------------------------------

Function:
process_obligation_lifecycle(instance, current_time)

Rules enforced:

1. current_time MUST be provided.
   - Raises ValueError if None.
   - Prevents nondeterministic lifecycle evaluation.

2. Terminal State Protection:
   - If instance.state in ["resolved", "breached"]:
       return instance.state
   - No further mutation allowed.
   - Terminal states are protected from regression.

CONCLUSION:
Lifecycle requires explicit time input and protects terminal states.

------------------------------------------------------------
SECTION 2 — BASE STATE EVALUATION (CONFIRMED IMPLEMENTED)
------------------------------------------------------------

Step 1:
base_state = evaluate_obligation_state(instance)

evaluate_obligation_state():
- If fully paid → resolved
- If past deadline → overdue
- Otherwise → active

Additional regression guard:

If instance.state == "defaulted"
AND base_state == "overdue":
    base_state = "defaulted"

Prevents regression from defaulted → overdue.

Then:
instance.state = base_state

CONCLUSION:
Base state derives from factual evaluation.
Regression from higher severity state is prevented.

------------------------------------------------------------
SECTION 3 — ESCALATION LOGIC (CONFIRMED IMPLEMENTED)
------------------------------------------------------------

Step 2:
If instance.state == "defaulted":
    escalated_state = evaluate_default_escalation(
        instance,
        current_time=current_time
    )

evaluate_default_escalation():
- Applies only to defaulted obligations.
- If defaulted longer than max_default_days:
      return "breached"
- Otherwise:
      return "defaulted"

After escalation:
instance.state = escalated_state

CONCLUSION:
Defaulted obligations escalate to breached based on time threshold.
Escalation requires explicit current_time.
Escalation does not apply to non-defaulted states.

------------------------------------------------------------
SECTION 4 — LIFECYCLE STATE GRAPH (OBLIGATION LEVEL)
------------------------------------------------------------

States involved:

active
overdue
defaulted
resolved
breached

Flow:

active → overdue → defaulted → breached
active → resolved
overdue → resolved
defaulted → resolved
defaulted → breached

Terminal states:
resolved
breached

Regression prevented:
defaulted cannot revert to overdue
terminal states cannot change

CONCLUSION:
Obligation lifecycle graph is coherent and severity-monotonic.

------------------------------------------------------------
SECTION 5 — WHAT IS MISSING / NOT PRESENT
------------------------------------------------------------

1. No Persistence Layer Integration
   - process_obligation_lifecycle mutates in-memory instance.
   - Does not save state.
   - Caller must persist changes.

2. No Automation Runner
   - No loop executing lifecycle across all obligations.
   - No scheduler integration.
   - No periodic enforcement engine.

3. No Notification Hooks
   - No events emitted on state change.
   - No breach alerts.
   - No default alerts.

4. No Idempotency Marker
   - State mutation assumes clean invocation.
   - No transition logging.

5. No Contract-Level Propagation
   - Breached obligations do not update contract status.
   - No cascade from obligation → contract.

------------------------------------------------------------
SECTION 6 — CURRENT ENGINE STATUS BASED ON THIS FILE
------------------------------------------------------------

CONFIRMED BUILT:
- Deterministic lifecycle evaluation.
- Explicit time-based mutation.
- Regression prevention.
- Escalation logic.
- Terminal state protection.
- Severity monotonic progression.

CONFIRMED NOT COMPLETE:
- No lifecycle automation runner.
- No persistence coordination.
- No event emission.
- No contract-level cascading.
- No bulk lifecycle processor.

------------------------------------------------------------
FINAL ASSESSMENT
------------------------------------------------------------

The obligation lifecycle engine is structurally sound and properly designed. It enforces deterministic, monotonic state progression with escalation rules and terminal protection.

However, it operates as a pure mutation function without orchestration. Automation execution, persistence coordination, and contract-level cascading remain unimplemented.

The core lifecycle logic exists.
The orchestration layer does not.


