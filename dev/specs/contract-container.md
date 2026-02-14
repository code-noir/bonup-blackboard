# Contract Container Spec






## Purpose
Represents a legal relationship between two or more parties.

## Responsibilities
- Holds contract_id
- Holds initiator
- Holds counterparty
- Tracks overall status
- Never edited directly after creation

## Rules
- One container → many versions
- Container never deleted
- Container never mutated after creation


## Attached Code
- backend/contracts/models.py (Contract model)