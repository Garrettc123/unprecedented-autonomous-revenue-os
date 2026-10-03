"""Garcar Base Contract sidecar for unprecedented-autonomous-revenue-os (role: revenue_os)."""
import asyncio
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from contextlib import asynccontextmanager

from .consumers import run_consumers
from .event_bus import EventBus

logger = logging.getLogger("garcar.app")

SYSTEM = "unprecedented-autonomous-revenue-os"
ROLE = "revenue_os"
VERSION = "1.1.0"
CONTRACT_VERSION = "1.1.0"

_events: deque[dict[str, Any]] = deque(maxlen=1000)
_counters: dict[str, int] = {
    "requests_total": 0,
    "health_checks": 0,
    "meta_checks": 0,
    "metrics_checks": 0,
    "events_checks": 0,
    "events_emitted": 0,
}

bus = EventBus()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_event(event: dict[str, Any]) -> None:
    _events.appendleft(event)
    _counters["events_emitted"] += 1


async def _announce_started(stop: asyncio.Event) -> None:
    """Publish system.started once, the first time the bus connects."""
    while not stop.is_set():
        if bus.connected:
            env = await bus.publish(
                "system.started",
                {"version": VERSION, "role": ROLE},
                classification="internal",
            )
            if env:
                _record_event(env)
                return
        await bus._wait(stop, 1.0, bus.connected_event)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Nothing here awaits Redis: the server starts even when Redis is down.
    bus.init_runtime()
    stop = asyncio.Event()
    tasks: list[asyncio.Task] = []
    if bus.redis_url:
        tasks = [
            asyncio.create_task(bus.run_forever(stop), name="event-bus-supervisor"),
            asyncio.create_task(run_consumers(bus, stop), name="event-consumers"),
            asyncio.create_task(_announce_started(stop), name="announce-started"),
        ]
    app.state.background_tasks = tasks
    try:
        yield
    finally:
        stop.set()
        if bus.connected:
            try:
                await asyncio.wait_for(bus.publish("system.stopping", {"version": VERSION}), timeout=2)
            except Exception as exc:  # never block shutdown on Redis
                logger.warning("system.stopping not published: %s", type(exc).__name__)
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await bus.close()


def _consumers_running() -> bool:
    for t in getattr(app.state, "background_tasks", []) or []:
        if t.get_name() == "event-consumers" and not t.done():
            return True
    return False


def _bus_state() -> dict[str, Any]:
    state = bus.state()
    state["consumers_running"] = _consumers_running()
    return state


app = FastAPI(
    title=f"{SYSTEM} Garcar Base Contract",
    version=VERSION,
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, Any]:
    _counters["health_checks"] += 1
    _counters["requests_total"] += 1
    # Offline mode (no REDIS_URL) is a supported configuration -> healthy.
    # Configured but disconnected -> degraded (still HTTP 200 so the platform
    # does not restart-loop the API during a Redis outage).
    status = "healthy" if (bus.connected or not bus.redis_url) else "degraded"
    payload = {
        "status": status,
        "system": SYSTEM,
        "version": VERSION,
        "timestamp": _now(),
        "event_bus_connected": bus.connected,
        "observability_connected": bus.connected,
        "event_bus": _bus_state(),
    }
    env = await bus.publish("health.check", payload)
    if env:
        _record_event(env)
    return payload


@app.get("/meta")
async def meta() -> dict[str, Any]:
    _counters["meta_checks"] += 1
    _counters["requests_total"] += 1
    return {
        "system": SYSTEM,
        "role": ROLE,
        "contract_version": CONTRACT_VERSION,
        "version": VERSION,
        "endpoints": ["/health", "/meta", "/metrics", "/events"],
        "event_bus_topic_schema": "garcar.{system}.{event_type}",
        "event_bus_connected": bus.connected,
        "observability_connected": bus.connected,
        "event_bus_channel": "garcar:events",
        "system_topic_prefix": f"garcar.{SYSTEM}",
    }


@app.get("/metrics")
async def metrics() -> dict[str, Any]:
    _counters["metrics_checks"] += 1
    _counters["requests_total"] += 1
    out = dict(_counters)
    out["event_bus_connected"] = bus.connected
    out["observability_connected"] = bus.connected
    out["event_bus"] = _bus_state()
    return out


@app.get("/events")
async def events() -> dict[str, Any]:
    _counters["events_checks"] += 1
    _counters["requests_total"] += 1
    ev = list(_events)
    return {
        "events": ev,
        "total": len(ev),
        "event_bus_connected": bus.connected,
    }


@app.post("/events/emit")
async def emit_event(body: dict[str, Any]) -> dict[str, Any]:
    """Manual emit for testing / control-plane injection."""
    event_type = body.get("event_type", "custom")
    payload = body.get("payload", {})
    env = await bus.publish(event_type, payload)
    if env:
        _record_event(env)
        return {"status": "emitted", "event": env}
    # Fallback to in-memory only
    fallback = {
        "event_id": None,
        "event_type": f"{SYSTEM}.{event_type}.v1",
        "occurred_at": _now(),
        "payload": payload,
        "offline": True,
    }
    _record_event(fallback)
    return {"status": "recorded_offline", "event": fallback}
