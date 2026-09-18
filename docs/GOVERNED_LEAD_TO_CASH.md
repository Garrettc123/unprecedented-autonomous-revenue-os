# Governed workflow

`business event -> identity match -> opportunity -> action proposal -> policy evaluation -> approval if needed -> execution -> provider receipt -> outcome`

Every external call must be idempotent. The idempotency key is generated from organization, action type, target, and proposal revision. External content is untrusted and may inform a proposal but cannot change policy, tool permissions, approval requirements, or system instructions.

## Approval classes

| Class | Examples | Rule |
| --- | --- | --- |
| Observe | summarize CRM, calculate metrics | automatic |
| Recommend | score lead, draft follow-up | automatic; no external state change |
| Internal execute | update CRM, create internal task | automatic only if policy allows |
| External execute | email, text, calendar invite, quote | approval required in beta |
| Financial or irreversible | payment request, discount, refund, contract, deletion | approval required; owner only |

## Invariants
- An execution cannot start unless its proposal is policy-approved and any required approval is valid.
- A rejected, expired, revoked, or already-executed proposal cannot execute.
- Provider receipts and failures become immutable events.
- A kill switch blocks all execution while preserving observe and audit functions.
