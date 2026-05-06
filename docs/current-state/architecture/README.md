# Architecture Documentation

> Status: Index
> Source of truth: current code first, docs second
> Updated: 2026-05-06

---

## 1. About This Folder

This folder contains per-domain architecture documents for the bonUP backend. Each file is generated from the actual codebase using a read-then-write workflow with strict citation rules — every substantive claim cites a file path and line number. These documents are intended for developers and AI agents who need to orient themselves to a domain without reading all the source files directly. They are not design specs and do not describe intended future behavior; they describe what the code actually does at the time they were generated. When code changes in a domain, the corresponding file should be regenerated using the same audit-and-write method. Do not edit these files manually to add claims that are not supported by code.

---

## 2. Folder Map

| File | Description | Status |
|---|---|---|
| `identity.md` | Django User, bonID identity system, signup, email verification, and authentication flows | Current |
| `entity_layer.md` | Soul, Entity, SoulEntity, and BusinessEntity — the layer that turns a user into an operating actor inside bonUP | Current |
| `authority.md` | Contract participation authority, business ownership authority, and Contract Pro delegated authority | Current |
| `contract_lifecycle.md` | Contract creation, versioning, negotiation, signing, and role switching — lifecycle ends at signing | Current |
| `contract_pro.md` | Delegated authority system allowing a business owner to grant another user controlled access to act on contracts | Current |
| `obligations_lifecycle.md` | Post-contract obligation tracking, execution sessions, approval flows, value adjustments, and resolution for both payment and service obligations | Current |
| `payments.md` | Payment model, 13 API routes, obligation `amount_paid` write path, and engine-layer payment abstractions | Current |
| `sessions.md` | LiveKit-backed real-time video sessions, HTTP lifecycle management, and Django Channels WebSocket consumer for in-session events | Current |
| `sol.md` | Rotating savings group system (sou-sou/tontine/susu) — fully self-contained domain with its own contract, payout, and contribution models | Current |
| `billing.md` | Subscription plans, Stripe checkout and webhook flows, feature gate functions, and Sol-group billing auto-upgrade/downgrade lifecycle | Current |
| `audit_activity.md` | Contract-scoped audit trail via `ContractActivity` and `log_activity()` — 25 call sites across 4 domains, 2 read-only API endpoints | Current |
| `documents_uploads.md` | Two-layer file storage: raw `Upload` records backed by Digital Ocean Spaces (S3), and `ContractDocument` semantic attachment layer | Current |

All listed files are current and grounded in code.

---

## 3. Recommended Reading Order

For a developer or AI agent new to this codebase:

**1. Foundational concepts — read first**
- `identity.md` — how users are created and authenticated
- `entity_layer.md` — how users become operating actors

**2. Contract core**
- `authority.md` — who is allowed to act and under what conditions
- `contract_lifecycle.md` — how agreements are created, negotiated, and signed

**3. Delegated authority**
- `contract_pro.md` — scoped delegation of contract authority to another user

**4. Post-signing lifecycle**
- `obligations_lifecycle.md` — work and payment tracking after a contract is signed
- `payments.md` — payment records, status transitions, and obligation write path

**5. Feature domains**
- `sessions.md` — real-time video sessions backed by LiveKit
- `sol.md` — rotating savings group domain
- `billing.md` — subscription plans, Stripe integration, and feature gates
- `audit_activity.md` — contract-scoped event log
- `documents_uploads.md` — file uploads and contract document attachments

---

## 4. Maintenance Rules

- Each file is generated from code using a read-inventory-then-write workflow with strict citation rules.
- When code changes in a domain, the corresponding file should be regenerated. Reading the existing file and making ad hoc edits is not the correct method.
- Do not edit these files to add claims that are not supported by a specific file:line citation in the code.
- The correct regeneration method: (1) read all relevant source files for the domain, (2) produce an inventory report, (3) overwrite the architecture file from the inventory.
- If a file's status is ever reset to Draft during a partial regeneration, complete the pass before merging.
