# Garcar Autonomous Wiring TODO for unprecedented-autonomous-revenue-os

Role: `revenue_os`

_Live fan-out: 2026-09-25 (event bus + consumers + outreach wave)_

## Required Garcar Base Contract
- [x] `/health` — **added** via `contract/` sidecar
- [x] `/meta` — **added** (role revenue_os, contract_version 1.1.0)
- [x] `/metrics` — **added** (JSON counters + connection flags)
- [x] `/events` — **added** (in-memory ring + emit endpoint)

Sidecar: `contract/app.py` + `contract/event_bus.py` + `contract/consumers.py` + `contract/requirements.txt` + `contract/Dockerfile` (EXPOSE 8080).

## Event Bus Wiring
- [x] Emit required events for this role (`garcar.unprecedented-autonomous-revenue-os.{event_type}`).
- [x] Redis client (compatible with garcar-enterprise-sync-core `garcar:events` channel).
- [x] Graceful offline mode when `REDIS_URL` unset.
- [x] Consume skeleton (`contract/consumers.py`) for arbitrage / control commands.
- [x] Contract + event tests (`tests/test_contract.py`).

## Current Full-Stack Components
- backend_api: FastAPI contract sidecar (`contract/app.py`)
- frontend_ui: None
- payment_hook: None
- event_bus_connected: **True when REDIS_URL set** (runtime flag)
- observability_connected: **True when REDIS_URL set** (same bus)

## Wiring Tasks
1. ~~Add or verify Garcar Base Contract endpoints.~~ **DONE**
2. ~~Add NATS/Redis Streams client and emit/consume required topics.~~ **DONE (Redis + consumers)**
3. Ensure metrics/events appear in Zeus/Atlas dashboards. — **ready** (publish path live; Atlas consumer is next hop)
4. ~~Add tests for contract + event wiring.~~ **DONE**

## Activation tracker
Linear: [GAR-526](https://linear.app/garrettc/issue/GAR-526/activation-unprecedented-enterprise-intelligence-full-stack)
PR: https://github.com/Garrettc123/unprecedented-autonomous-revenue-os/pull/3 (ready for review)

## Safety
- Cash lock revoked per Garcar operating stance — architecture and revenue run in parallel.
