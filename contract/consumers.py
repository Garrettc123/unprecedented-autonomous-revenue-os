"""Control-plane event consumers for unprecedented-autonomous-revenue-os.

Subscribes to system-specific topics and shared garcar:events.
Handlers are intentionally thin — expand with real arbitrage / DAG logic.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from .event_bus import EventBus, SYSTEM

logger = logging.getLogger("garcar.consumers")


async def handle_arbitrage_signal(event: dict[str, Any]) -> None:
    """React to arbitrage / pricing signals from the wider Garcar DAG."""
    logger.info("arbitrage signal received: %s", event.get("event_type"))
    # Future: adjust offer routing, pause/resume streams, etc.


async def handle_control_command(event: dict[str, Any]) -> None:
    """React to control-plane commands (pause, resume, config push)."""
    logger.info("control command received: %s payload=%s", event.get("event_type"), event.get("payload"))
    # Future: honor pause/resume, hot-reload config


async def handle_any(event: dict[str, Any]) -> None:
    """Wildcard logger for observability."""
    et = event.get("event_type") or event.get("topic")
    logger.debug("event seen: %s", et)


async def _dispatch(event: dict[str, Any]) -> None:
    et = str(event.get("event_type", ""))
    if "arbitrage" in et:
        await handle_arbitrage_signal(event)
    elif "control" in et or "command" in et:
        await handle_control_command(event)
    await handle_any(event)


async def run_consumers(bus: EventBus, stop: asyncio.Event | None = None) -> None:
    """Long-running consumer loop. Run as a background task from the app lifespan.

    Waits for the bus to connect (instead of giving up when offline) and
    resubscribes after every reconnect, until ``stop`` is set or the task is
    cancelled. Returns immediately in offline mode (REDIS_URL unset).
    """
    if not bus.redis_url:
        logger.warning("REDIS_URL not set — consumers not started (offline mode)")
        return
    if stop is None:
        stop = asyncio.Event()
    logger.info("Starting consumers for %s", SYSTEM)
    await bus.subscribe(_dispatch, system_only=False, stop=stop)
    logger.info("Consumers stopped for %s", SYSTEM)
