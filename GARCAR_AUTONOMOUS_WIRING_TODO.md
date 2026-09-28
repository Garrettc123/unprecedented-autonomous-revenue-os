# Garcar Autonomous Wiring TODO for unprecedented-autonomous-revenue-os

Role: `revenue_os`

_Live fan-out: 2026-09-27 — payment_hook attached to public A wedge MLS-497_

## Required Garcar Base Contract
- [x] `/health`
- [x] `/meta`
- [x] `/metrics`
- [x] `/events`

## Event Bus Wiring
- [x] Emit / consume skeleton
- [x] Offline mode when REDIS_URL unset

## Current Full-Stack Components
- backend_api: FastAPI contract sidecar (`contract/app.py`)
- frontend_ui: storefront https://garrettc123.github.io/
- payment_hook: **LIVE** (`payment_hook/`) — CMC-gated attach to Stripe payment links
- event_bus_connected: True when REDIS_URL set
- observability_connected: True when REDIS_URL set

## Public A SKU this hour
- MLS-497 Mark the leads that sat — $497 — https://buy.stripe.com/8x2eVddjf0hQ86Tf0f43S2h
- Upsell LB-2500 callback clock — $2,500 — https://buy.stripe.com/14AdR95QN3u2af14lB43S2j

Retired as public default: $47 HVAC Contractor Lead Leak Audit.

## Production next step
```bash
python -m unittest discover -s tests -v
python -m agents.orchestrator --mode activate --stream local_services
# After a real Stripe checkout.session.completed webhook:
# Orchestrator.apply_payment({sku, amount_total, customer_email, checkout_session_id})
```
