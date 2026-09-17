# Policy and approval model

Policies are organization-scoped and versioned. Policy evaluation returns a decision, reasons, and the policy version used.

## Initial defaults
- Internal CRM updates and task creation: allowed after validation.
- Draft creation: allowed; sending is not.
- Customer email, SMS, calendar invitations, quotes, or proposals: approval required.
- Contracts, payment links, refunds, discounts, ad-spend changes, public posts, deletion, exports, and credential changes: owner approval required.
- Any action above a configured spend threshold: owner approval required.
- Any action whose target cannot be resolved uniquely: block and request review.

## Approval record
An approval stores the exact proposal payload hash, organization, approver identity, decision, timestamp, optional edited payload, policy version, expiry, and reason. Edited payloads create a new proposal revision and require a new policy evaluation.

## Emergency controls
Each organization has an execution state: `active`, `paused`, or `emergency_stop`. Only an owner can change it. `paused` blocks new executions; `emergency_stop` also revokes pending approvals.
