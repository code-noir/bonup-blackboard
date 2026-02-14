# Contract Version Engine Spec

## Purpose
The ContractVersion model represents an immutable snapshot of a contract at a specific point in time.

A new version is created whenever:
- A contract is drafted
- A contract is countered
- A contract is renegotiated
- A contract is amended
- A contract is renewed

Previous versions are NEVER edited.

## Core Principles

1. Contract is identity (container).
2. ContractVersion is the legal state.
3. Each version is immutable.
4. Version numbers must increment sequentially.
5. Only one version can be marked as current.
6. When a new version is created, the previous current version becomes superseded.

---

## Attached Code
- backend/contracts/models.py (ContractVersion model)
- backend/contracts/services/version_service.py (future)




