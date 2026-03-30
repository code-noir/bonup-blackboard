# DOMAIN_MAP.md — Models, Relationships, and Domain Ownership

---

## Domain Ownership

| Model | Django App | Owned By |
|-------|-----------|----------|
| `Contract` | `backend/contracts/` | Contracts domain |
| `ContractVersion` | `backend/contracts/` | Contracts domain |
| `Obligation` | `backend/contracts/` | Contracts domain (template — largely unused) |
| `RequestChange` | `backend/contracts/` | Contracts domain |
| `ContractObligation` | `backend/contracts/` | Obligations domain |
| `ContractServiceObligation` | `backend/contracts/` | Obligations domain |
| `ObligationExecutionSession` | `backend/contracts/` | Obligations domain |
| `ObligationExecutionEvent` | `backend/contracts/` | Obligations domain |
| `ContractValueAdjustment` | `backend/contracts/` | Obligations domain |
| `ContractApprovalRequest` | `backend/contracts/` | Obligations domain |
| `ContractObligationPromotion` | `backend/contracts/` | Obligations domain |
| `Payment` | `backend/payments/` | Payments domain |
| `BonUserProfile` | `backend/users/` | Users domain |
| `ReservedBonId` | `backend/users/` | Users domain |

---

## Model Reference

### Contract

Primary record for any agreement between two parties.

```
Contract
├── id: UUID (PK)
├── initiator → User (FK, nullable)
├── counterparty_email: EmailField
├── structure_type: CharField [ONE_TIME, ONGOING, COLLABORATIVE, RESOLUTION]
├── max_versions: PositiveIntegerField (default 3)
├── state: CharField (default "active")
├── is_active: BooleanField
└── created_at: DateTimeField

Reverse relations:
├── versions → ContractVersion[]
├── obligations → Obligation[] (template, unused)
├── contract_obligations_links → ContractObligation[]
├── service_obligations → ContractServiceObligation[]
├── payments → Payment[]
├── change_requests → RequestChange[]
├── approval_requests → ContractApprovalRequest[]
├── value_adjustments → ContractValueAdjustment[]
└── obligation_promotions → ContractObligationPromotion[]
```

### ContractVersion

Immutable snapshot of a contract at a point in time. Cannot be modified after creation
(enforced in `save()`). Only `status` and `superseded` fields can be updated.

```
ContractVersion
├── id: UUID (PK)
├── contract → Contract (FK)
├── version_number: PositiveIntegerField
├── created_by → User (FK, nullable)
├── previous_version → ContractVersion (self-referential FK, nullable)
├── superseded: BooleanField
├── status: CharField [draft, sent, negotiating, signed, superseded, archived, rejected]
├── content_snapshot: TextField
└── created_at: DateTimeField

Unique together: (contract, version_number)
Ordered by: -version_number

Reverse relations:
├── obligations → ContractObligation[]
└── service_obligations → ContractServiceObligation[]
```

### Obligation (template)

Defines what obligations a contract should generate. Currently unused — no recurrence
expansion service exists. `recurrence_interval_days` and `recurrence_count` fields are present
but no service reads them.

```
Obligation
├── id: UUID (PK)
├── contract → Contract (FK)
├── obligation_type: CharField [payment, service]
├── from_party → User (FK)
├── to_party → User (FK)
├── description: TextField
├── amount: DecimalField (nullable)
├── currency: CharField
├── start_date: DateTimeField (nullable)
├── due_date: DateTimeField (nullable)
├── recurrence_interval_days: PositiveIntegerField (nullable)
├── recurrence_count: PositiveIntegerField (nullable)
├── state: CharField [pending, due, fulfilled, overdue, cancelled]
└── created_at: DateTimeField
```

### ContractObligation

Engine-generated payment obligation instance. One per installment, per contract activation.

```
ContractObligation
├── id: UUID (PK)
├── contract → Contract (FK, related_name="contract_obligations_links")
├── version → ContractVersion (FK)
├── obligor → User (FK, related_name="owed_obligations")
├── obligee → User (FK, related_name="receivable_obligations")
├── installment_number: PositiveIntegerField
├── amount_due: DecimalField
├── amount_paid: DecimalField (default 0)
├── due_date: DateTimeField
├── state: CharField [active, due, grace, overdue, defaulted, resolved]
├── is_defaulted: BooleanField (mirrors state == "defaulted")
├── created_at: DateTimeField
└── updated_at: DateTimeField

Ordered by: due_date

Reverse relations:
├── payments → Payment[]
├── execution_sessions → ObligationExecutionSession[]
├── approval_requests → ContractApprovalRequest[]
└── value_adjustments → ContractValueAdjustment[]
```

### ContractServiceObligation

Engine-generated service obligation instance.

```
ContractServiceObligation
├── id: UUID (PK)
├── contract → Contract (FK, related_name="service_obligations")
├── version → ContractVersion (FK)
├── obligor → User (FK, related_name="service_owed")
├── obligee → User (FK, related_name="service_receivable")
├── description: TextField
├── due_date: DateTimeField
├── state: CharField [active, due, overdue, resolved]
├── completed_at: DateTimeField (nullable)
├── created_at: DateTimeField
└── updated_at: DateTimeField

Methods:
└── mark_completed() → sets state="resolved", completed_at=now(), saves

Reverse relations:
├── execution_sessions → ObligationExecutionSession[]
├── approval_requests → ContractApprovalRequest[]
├── value_adjustments → ContractValueAdjustment[]
├── child_promotions → ContractObligationPromotion[]
└── origin_promotions → ContractObligationPromotion[]
```

### ObligationExecutionSession

A bounded work period against an obligation. One obligation can have many sessions.
Exactly one of `payment_obligation` or `service_obligation` should be set (not enforced at DB level).

```
ObligationExecutionSession
├── id: UUID (PK)
├── payment_obligation → ContractObligation (FK, nullable)
├── service_obligation → ContractServiceObligation (FK, nullable)
├── started_at: DateTimeField
├── ended_at: DateTimeField (nullable)
├── status: CharField [active, closed]
└── created_at: DateTimeField

Reverse relations:
└── events → ObligationExecutionEvent[]
```

### ObligationExecutionEvent

A structured event captured during an execution session. Foundation of PBVD (Proof By Value Delivered).

```
ObligationExecutionEvent
├── id: UUID (PK)
├── session → ObligationExecutionSession (FK)
├── event_type: CharField
├── task: CharField (nullable)
├── observation: CharField (nullable)
├── summary: TextField
├── estimated_duration_minutes: PositiveIntegerField (nullable)
├── estimated_cost_amount: DecimalField (nullable)
├── estimated_cost_currency: CharField (nullable)
├── planned_execution_time: DateTimeField (nullable)
├── metadata: JSONField
└── created_at: DateTimeField

Ordered by: created_at

Reverse relations:
├── value_adjustments → ContractValueAdjustment[]
├── approval_requests → ContractApprovalRequest[]
└── promotions → ContractObligationPromotion[]
```

### ContractValueAdjustment

A financial adjustment (additional charge or lateness penalty) tied to execution.

```
ContractValueAdjustment
├── id: UUID (PK)
├── contract → Contract (FK)
├── payment_obligation → ContractObligation (FK, nullable)
├── service_obligation → ContractServiceObligation (FK, nullable)
├── execution_event → ObligationExecutionEvent (FK, nullable, SET_NULL)
├── adjustment_type: CharField [additional_charge, lateness_adjustment]
├── mode: CharField [fixed_amount, percentage]
├── amount: DecimalField
├── currency: CharField
├── summary: TextField
└── created_at: DateTimeField
```

### ContractApprovalRequest

An approval request for an execution item or adjustment.

```
ContractApprovalRequest
├── id: UUID (PK)
├── contract → Contract (FK)
├── payment_obligation → ContractObligation (FK, nullable)
├── service_obligation → ContractServiceObligation (FK, nullable)
├── execution_event → ObligationExecutionEvent (FK, nullable, SET_NULL)
├── requested_by → User (FK, nullable, SET_NULL)
├── requested_from → User (FK, nullable, SET_NULL)
├── approval_type: CharField (default "execution_item")
├── status: CharField [pending, approved, rejected]
├── summary: TextField
├── metadata: JSONField
├── requested_at: DateTimeField
└── decided_at: DateTimeField (nullable)
```

### ContractObligationPromotion

Tracks promotion of an execution event into a new side obligation.

```
ContractObligationPromotion
├── id: UUID (PK)
├── contract → Contract (FK)
├── source_execution_event → ObligationExecutionEvent (FK)
├── parent_service_obligation → ContractServiceObligation (FK, nullable)
├── promoted_service_obligation → ContractServiceObligation (FK, nullable)
├── promotion_type: CharField [event_to_service_obligation]
├── summary: TextField
└── created_at: DateTimeField
```

### RequestChange

A structured negotiation intent message. Does not automatically create a new version.

```
RequestChange
├── id: UUID (PK)
├── contract → Contract (FK)
├── version → ContractVersion (FK)
├── requested_by → User (FK)
├── message: TextField
├── status: CharField [pending, reviewed, resolved, rejected]
├── created_at: DateTimeField
└── reviewed_at: DateTimeField (nullable)
```

### Payment

Tracks a single payment transaction, linked to a contract and optionally to a specific obligation.

```
Payment
├── id: UUID (PK)
├── contract → contracts.Contract (FK, nullable)
├── payment_obligation → contracts.ContractObligation (FK, nullable)
├── payer → User (FK, related_name="sent_payments")
├── payee → User (FK, related_name="received_payments")
├── amount: DecimalField
├── currency: CharField
├── status: CharField [draft, pending, confirmed, failed, cancelled, refunded, reversed]
├── payment_method: CharField [cash, card, bank_transfer, manual]
├── reference: CharField (nullable)
├── metadata: JSONField
├── created_at: DateTimeField
├── updated_at: DateTimeField
├── confirmed_at: DateTimeField (nullable)
├── failed_at: DateTimeField (nullable)
├── cancelled_at: DateTimeField (nullable)
├── refunded_at: DateTimeField (nullable)
└── reversed_at: DateTimeField (nullable)

Ordered by: -created_at
```

### BonUserProfile

The bonUP identity attached to a Django user. Holds the 13-digit bonID.

```
BonUserProfile
├── id: (default Django PK)
├── user → User (OneToOne, related_name="bon_profile")
├── bon_id: CharField(13) (unique, auto-generated, never editable)
└── created_at: DateTimeField
```

### ReservedBonId

Stores binary-only bonIDs (composed only of 0s and 1s) that can never be assigned to users.

```
ReservedBonId
├── id: (default Django PK)
├── bon_id: CharField(13) (unique)
├── reason: CharField (default "binary_reserved")
└── created_at: DateTimeField
```

---

## Relationship Diagram (simplified)

```
User ──────────────────────────────────────────────────────────────
  │                │                │                │              │
initiator    requested_by     obligor/obligee    payer/payee   created_by
  │
Contract ─────────────────────────────────────────────────────────
  │                │                │                │
  ├─ ContractVersion[]   ├─ ContractObligation[]  ├─ Payment[]
  │                      │      │
  ├─ RequestChange[]     │ ObligationExecutionSession[]
  │                      │      │
  └─ ContractServiceObligation[] └─ ObligationExecutionEvent[]
       │                                    │
       └─ ContractObligationPromotion[]     └─ ContractValueAdjustment[]
                                            └─ ContractApprovalRequest[]
```
