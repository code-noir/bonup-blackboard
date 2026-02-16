
# CONTRACT VERSION ENGINE — CORE ARCHITECTURE
# Blackboard Engine Core
# Date: 2026-02-15


# ============================================================
# PURPOSE
# ============================================================

This document defines the core logic of the Blackboard
Contract Version Engine.

The engine guarantees:

- Immutable contract versions
- Automatic version sequencing
- Automatic supersession
- Strict lifecycle state transitions
- Prevention of illegal contract flow


# ============================================================
# CORE PRINCIPLES
# ============================================================


## 1. IMMUTABILITY

Definition:
An immutable object cannot be changed after creation.

Engine Rule:
Once a ContractVersion is saved, it cannot be modified.

The only allowed update is controlled supersession via:
    update_fields=["status", "superseded"]

All other modifications raise:

    Exception("Contract versions are immutable.")

Reason:
Preserves legal integrity and prevents historical tampering.



## 2. SUPERSESSION

Definition:
To replace an older version with a newer authoritative version.

Engine Behavior:
When a new version is created:

1. The previous version is automatically updated:
       status = "superseded"
       superseded = True

2. The new version:
       version_number = previous.version_number + 1
       previous_version = last_version

Guarantee:
Only one active working version exists at a time.



## 3. VERSION SEQUENCING

Rules:

- Initial version:
      version_number = 1

- New versions:
      version_number = last_version.version_number + 1

Enforced inside the overridden save() method.



## 4. LIFECYCLE STATES

Current lifecycle states:

    draft
    sent
    negotiating
    signed
    superseded
    archived



# ============================================================
# ALLOWED STATE TRANSITIONS
# ============================================================

ALLOWED_TRANSITIONS = {
    "draft": ["sent", "archived"],
    "sent": ["negotiating", "signed", "archived"],
    "negotiating": ["superseded", "archived"],
    "signed": ["archived"],
    "superseded": [],
    "archived": [],
}


Rules:

- A version in "negotiating" cannot move directly to "signed".
- If negotiation succeeds:
      A new version must be created.
- Superseded versions cannot transition.
- Signed versions cannot be modified.



# ============================================================
# ENGINE FLOW — VERSION CREATION
# ============================================================


## INITIAL VERSION

create_initial_version(contract, content, user)

Logic:

- Only allowed if no versions exist for contract.
- Sets:
      version_number = 1
      status = "draft"



## CREATE NEW VERSION

create_new_version(contract, content, user)

Logic:

1. Fetch latest version
2. Create new version
3. Auto-supersede previous version
4. Increment version number



# ============================================================
# SAVE() METHOD LOGIC
# ============================================================

When save() is called:


IF updating existing version:

    if not self._state.adding:
        if "update_fields" in kwargs:
            allow controlled update
        else:
            raise Exception("Contract versions are immutable.")


IF creating new version:

    - Determine last_version
    - Increment version_number
    - Link previous_version
    - Mark last_version as superseded
    - Save new version



# ============================================================
# SHELL TEST RESULTS
# ============================================================

Confirmed:

✔ v1 created as draft  
✔ v1 transitioned to sent  
✔ v1 transitioned to negotiating  
✔ v2 created  
✔ v1 automatically marked superseded  
✔ Illegal transitions blocked  
✔ Immutable protection enforced  


Example Verified Output:

    V1 superseded: superseded True
    V2: v2 - draft



# ============================================================
# ARCHITECTURAL STATUS
# ============================================================

This represents the CORE ENGINE layer.

This is not UI.
This is not API.
This is not presentation logic.

This is the contract brain.

All UI and workflow layers must respect this engine.


# ============================================================
# ENGINE COMPLETION STATUS
# ============================================================

✔ Immutable version system  
✔ Automatic supersession  
✔ Version sequencing  
✔ State machine enforcement  
✔ Illegal transition protection  
✔ Shell-tested and verified  

Engine Core: STABLE




