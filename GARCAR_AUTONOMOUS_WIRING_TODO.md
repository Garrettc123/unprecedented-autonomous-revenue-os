# Garcar Autonomous Wiring TODO for unprecedented-autonomous-revenue-os

Role: `revenue_os`

_Live fan-out: 2026-09-25 (event bus + observability wired)_

## Required Garcar Base Contract
- [x] `/health` — **added** via `contract/` sidecar
- [x] `/meta` — **added** (role revenue_os, contract_version 1.1.0)
- [x] `/metrics` — **added** (JSON counters + connection flags)
- [x] `/events` — **added** (in-memory ring + emit endpoint)

Sidecar: `contract/app.py` + `contract/event_bus.py` + `contract/requirements.txt` + `contract/Dockerfile` (EXPOSE 8080).

## Event Bus Wiring
- [x] Emit required events for this role (`garcar.unprecedented-autonomous-revenue-os.{event_type}`).
- [x] Redis client (compatible with garcar-enterprise-sync-core `garcar:events` channel).
- [x] Graceful offline mode when `REDIS_URL` unset.
- [ ] Consume required arbitrage/control-plane events (subscribe ready; wire specific handlers next).
- [x] Contract + event tests (`tests/test_contract.py`).

## Current Full-Stack Components
- backend_api: FastAPI contract sidecar (`contract/app.py`)
- frontend_ui: None
- payment_hook: None
- event_bus_connected: **True when REDIS_URL set** (runtime flag)
- observability_connected: **True when REDIS_URL set** (same bus)

## Wiring Tasks
1. ~~Add or verify Garcar Base Contract endpoints.~~ **DONE**
2. ~~Add NATS/Redis Streams client and emit/consume required topics.~~ **DONE (Redis)**
3. Ensure metrics/events appear in Zeus/Atlas dashboards. — **ready** (publish path live; Atlas consumer is next hop)
4. ~~Add tests for contract + event wiring.~~ **DONE**

## Safety
- Draft PR only. Do not auto-merge.
- Cash lock revoked per Garcar operating stance — architecture and revenue run in parallel.
