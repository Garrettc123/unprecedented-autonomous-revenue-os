"""Garcar Event Bus client for unprecedented-autonomous-revenue-os.

Emits and consumes on topics matching:
  garcar.unprecedented-autonomous-revenue-os.{event_type}

Compatible with garcar-enterprise-sync-core Redis bus.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

logger = logging.getLogger("garcar.event_bus")

SYSTEM = "unprecedented-autonomous-revenue-os"
TOPIC_PREFIX = f"garcar.{SYSTEM}"
CHANNEL = "garcar:events"
LOG_KEY = "garcar:event_log"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventBus:
    """Async Redis-backed event bus. Graceful when REDIS_URL is unset."""

    def __init__(self, redis_url: str | None = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.client = None
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect(self) -> bool:
        if not self.redis_url:
            logger.warning("REDIS_URL not set — event bus remains offline")
            self._connected = False
            return False
        try:
            import redis.asyncio as redis

            self.client = redis.from_url(self.redis_url, decode_responses=True)
            await self.client.ping()
            self._connected = True
            logger.info("Event bus connected to Redis")
            return True
        except Exception as exc:
            logger.error("Event bus connect failed: %s", exc)
            self._connected = False
            self.client = None
            return False

    async def close(self) -> None:
        if self.client:
            await self.client.aclose()
            self.client = None
            self._connected = False

    def _topic(self, event_type: str) -> str:
        return f"{TOPIC_PREFIX}.{event_type}"

    def _envelope(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
        classification: str = "internal",
    ) -> dict[str, Any]:
        eid = str(uuid.uuid4())
        return {
            "event_id": eid,
            "event_type": f"{SYSTEM}.{event_type}.v1",
            "schema_version": "v1",
            "producer": SYSTEM,
            "correlation_id": correlation_id or eid,
            "idempotency_key": f"{SYSTEM}:{event_type}:{eid}",
            "classification": classification,
            "occurred_at": _now(),
            "payload": payload,
            "topic": self._topic(event_type),
            "source": SYSTEM,
            "timestamp": _now(),
        }

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        correlation_id: str | None = None,
        classification: str = "internal",
    ) -> dict[str, Any] | None:
        """Publish an event. Returns envelope or None if offline."""
        if not self._connected or not self.client:
            return None
        envelope = self._envelope(
            event_type,
            payload or {},
            correlation_id=correlation_id,
            classification=classification,
        )
        try:
            data = json.dumps(envelope)
            # Fan-out on shared channel (sync-core compatible)
            await self.client.publish(CHANNEL, data)
            # Also publish on system-specific topic for selective consumers
            await self.client.publish(envelope["topic"], data)
            await self.client.lpush(LOG_KEY, data)
            await self.client.ltrim(LOG_KEY, 0, 9999)
            logger.debug("Published %s", envelope["event_type"])
            return envelope
        except Exception as exc:
            logger.error("Publish failed: %s", exc)
            return None

    async def subscribe(
        self,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
        *,
        system_only: bool = False,
    ) -> None:
        """Subscribe to events. system_only=True listens only to this system's topics."""
        if not self._connected or not self.client:
            return
        pubsub = self.client.pubsub()
        if system_only:
            # Pattern subscribe for this system
            await pubsub.psubscribe(f"{TOPIC_PREFIX}.*")
        else:
            await pubsub.subscribe(CHANNEL)
        async for message in pubsub.listen():
            if message["type"] in ("message", "pmessage"):
                try:
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode()
                    event = json.loads(data)
                    await callback(event)
                except Exception as exc:
                    logger.error("Subscribe callback error: %s", exc)
