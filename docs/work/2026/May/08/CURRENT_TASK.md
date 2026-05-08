# Current Task — 2026-05-08

## 2026-05-08, ~01:00 AM

Documented AI domain in docs/current-state/architecture/ai.md.

- 1 model (AIConversation, 7 fields, message JSON shape)
- 6 routes (chat, conversations list/detail, analyze-contract,
  counter-contract, import-contract)
- 4 Anthropic client instantiation sites in views.py
- 4 prompt locations (3 in prompts.py, 3 inline in views.py)
- 11 gaps surfaced; 5 open questions

Audit surfaced a Critical billing bypass: ImportContractView.post()
writes Contract, ContractVersion, and obligations inside
transaction.atomic(), commits, then checks can_create_contract.
If the gate fails, only the usage counter increment is skipped — the
contract stays in the database. Logged as C6 in tech-debt.md.

Both ai.md and the C6 entry committed and pushed in commit e64c218.
