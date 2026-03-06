✅ What this indicates we already have
	•	A central place defining state labels:
	•	ACTIVE, OVERDUE, DEFAULTED, RESOLVED, BREACHED, FULFILLED

❌ What this does NOT prove exists
	•	A state machine (allowed transitions table)
	•	A transition function (enforce rules + move state)
	•	Any automation/scheduler job that moves ACTIVE→OVERDUE→DEFAULTED
	•	Any connection between:
	•	contract version status (draft/sent/negotiating/signed/...)
	•	obligation state (active/overdue/defaulted/...)

Spec note (copy/paste)

Evidence: lifecycle_core/state/constants.py defines canonical lifecycle state strings (active/overdue/defaulted/resolved/breached/fulfilled). This establishes naming consistency but does not implement a transition graph, enforcement logic, or automated progression.

