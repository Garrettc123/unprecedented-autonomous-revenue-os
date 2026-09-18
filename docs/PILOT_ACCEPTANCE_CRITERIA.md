# Pilot acceptance criteria

## Functional
- A test lead produces one organization-scoped customer and opportunity record.
- A proposal has evidence, expected value, risk class, policy decision, expiry, and idempotency key.
- A policy-blocked proposal cannot execute.
- A required approval can be approved, rejected, or expired from the mobile-first API/UI.
- Duplicate provider webhook delivery does not cause duplicate execution.
- An approved external action executes once and records a provider receipt.
- A kill switch blocks executions immediately.

## Security
- Authentication and role checks protect every organization-scoped route.
- Secrets are environment-only and excluded from version control.
- Raw webhook signatures are verified before parsing or queueing.
- Audit records include actor, timestamp, payload hash, and policy version.

## Pilot readiness
- One integration is live in sandbox/test mode.
- One design partner has approved written workflow boundaries.
- Baseline metrics are captured before automation is enabled.
