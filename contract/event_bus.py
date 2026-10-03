"""Garcar Event Bus client for unprecedented-autonomous-revenue-os.

Emits and consumes on topics matching:
  garcar.unprecedented-autonomous-revenue-os.{event_type}

Compatible with garcar-enterprise-sync-core Redis bus.

Envelope versions
-----------------
v1   Frozen (PR #3). Do not mutate the v1 field set.
v1.1 Adds tenant_id, causation_id, policy_decision_id, evidence_refs.
     correlation_id already existed on v1 and is retained.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import uuid
from collections import deque
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable

logger = logging.getLogger("garcar.event_bus")

SYSTEM = "unprecedented-autonomous-revenue-os"
TOPIC_PREFIX = f"garcar.{SYSTEM}"
CHANNEL = "garcar:events"
LOG_KEY = "garcar:event_log"
SCHEMA_VERSION = "v1.1"
DEFAULT_TENANT_ID = os.getenv("GARCAR_TENANT_ID", "garcar-enterprise")

# Reconnect tuning (seconds). Exponential backoff with jitter, bounded by MAX.
BACKOFF_BASE = float(os.getenv("REDIS_BACKOFF_BASE", "0.5"))
BACKOFF_MAX = float(os.getenv("REDIS_BACKOFF_MAX", "30"))
HEALTH_INTERVAL = float(os.getenv("REDIS_HEALTH_INTERVAL", "15"))

_CRED_RE = re.compile(r"://[^@\s/]*@")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def backoff_delay(
    attempt: int,
    base: float = BACKOFF_BASE,
    cap: float = BACKOFF_MAX,
    rng: Callable[[], float] = random.random,
) -> float:
    """Exponential backoff with "equal jitter", bounded by ``cap``.

    ceiling = min(cap, base * 2**attempt); delay is uniform in [ceiling/2, ceiling].
    Always >= 0 and <= cap, and the lower bound grows with attempt until the cap.
    """
    ceiling = min(cap, base * (2 ** max(0, attempt)))
    return ceiling / 2 + rng() * (ceiling / 2)


def _safe_error(exc: BaseException) -> str:
    """Error text for logs/health with any URL credentials redacted."""
    msg = _CRED_RE.sub("://***@", str(exc))[:200]
    return f"{type(exc).__name__}: {msg}" if msg else type(exc).__name__


def _is_connection_error(exc: BaseException) -> bool:
    try:
        from redis import exceptions as rexc

        if isinstance(exc, (rexc.ConnectionError, rexc.TimeoutError)):
            return True
    except Exception:  # pragma: no cover - redis always installed in prod
        pass
    return isinstance(exc, (ConnectionError, TimeoutError, OSError, asyncio.TimeoutError))


def _default_client_factory(url: str):
    import redis.asyncio as redis

    return redis.from_url(
        url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=10,
        health_check_interval=int(HEALTH_INTERVAL),
    )


class EventBus:
    """Async Redis-backed event bus. Graceful when REDIS_URL is unset.

    ``connect()`` is a single attempt. ``run_forever(stop)`` is the supervisor:
    it reconnects with backoff at startup and after connection loss, and pings
    periodically while connected.
    """

    def __init__(self, redis_url: str | None = None, client_factory: Callable[[str], Any] | None = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL")
        self.client_factory = client_factory or _default_client_factory
        self.client = None
        self._connected = False
        self.backoff_base = BACKOFF_BASE
        self.backoff_max = BACKOFF_MAX
        self.health_interval = HEALTH_INTERVAL
        self.last_error: str | None = None
        self.last_connected_at: str | None = None
        self.reconnect_attempts = 0
        self.subscribed = False
        self.delays: deque[float] = deque(maxlen=50)
        self.connected_event: asyncio.Event | None = None
        self._lost: asyncio.Event | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    def init_runtime(self) -> None:
        """(Re)create asyncio primitives on the running loop and reset counters."""
        self.reconnect_attempts = 0
        self.last_error = None
        self.delays.clear()
        self.connected_event = asyncio.Event()
        self._lost = asyncio.Event()
        if self._connected:
            self.connected_event.set()

    def _ensure_runtime(self) -> None:
        if self.connected_event is None or self._lost is None:
            self.init_runtime()

    def state(self) -> dict[str, Any]:
        return {
            "configured": bool(self.redis_url),
            "connected": self._connected,
            "subscribed": self.subscribed,
            "last_error": self.last_error,
            "last_connected_at": self.last_connected_at,
            "reconnect_attempts": self.reconnect_attempts,
        }

    def _mark_connected(self) -> None:
        self._connected = True
        self.last_connected_at = _now()
        self.last_error = None
        if self.connected_event is not None:
            self.connected_event.set()
        if self._lost is not None:
            self._lost.clear()

    def _mark_disconnected(self, exc: BaseException | None = None) -> None:
        was = self._connected
        self._connected = False
        if exc is not None:
            self.last_error = _safe_error(exc)
        if self.connected_event is not None:
            self.connected_event.clear()
        if self._lost is not None:
            self._lost.set()
        if was:
            logger.warning("Event bus connection lost: %s", self.last_error)

    async def _drop_client(self) -> None:
        client, self.client = self.client, None
        if client is not None:
            try:
                await client.aclose()
            except Exception:
                pass

    async def connect(self) -> bool:
        """Single connection attempt. Returns True when Redis answered PING."""
        if not self.redis_url:
            logger.warning("REDIS_URL not set — event bus remains offline")
            self._connected = False
            return False
        await self._drop_client()
        try:
            self.client = self.client_factory(self.redis_url)
            await self.client.ping()
            self._mark_connected()
            logger.info("Event bus connected to Redis")
            return True
        except Exception as exc:
            self._mark_disconnected(exc)
            logger.error("Event bus connect failed: %s", self.last_error)
            await self._drop_client()
            return False

    async def _wait(self, stop: asyncio.Event, timeout: float, *others: asyncio.Event) -> None:
        """Sleep up to ``timeout`` but wake early if ``stop`` or any of ``others`` is set."""
        waiters = [asyncio.ensure_future(e.wait()) for e in (stop, *others)]
        try:
            await asyncio.wait(waiters, timeout=timeout, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for w in waiters:
                w.cancel()

    async def run_forever(self, stop: asyncio.Event) -> None:
        """Supervisor: keep the Redis connection alive until ``stop`` is set."""
        self._ensure_runtime()
        if not self.redis_url:
            logger.warning("REDIS_URL not set — supervisor idle (offline mode)")
            return
        attempt = 0
        while not stop.is_set():
            if not self._connected:
                if await self.connect():
                    attempt = 0
                    continue
                delay = backoff_delay(attempt, self.backoff_base, self.backoff_max)
                attempt += 1
                self.reconnect_attempts += 1
                self.delays.append(delay)
                logger.info("Redis reconnect attempt %d in %.2fs", attempt, delay)
                await self._wait(stop, delay)
                continue
            # Connected: wait for health interval, a loss signal, or stop.
            await self._wait(stop, self.health_interval, self._lost)
            if stop.is_set():
                break
            if self._lost.is_set() and not self._connected:
                continue
            try:
                await self.client.ping()
            except Exception as exc:
                self._mark_disconnected(exc)
        logger.info("Event bus supervisor stopped")

    async def close(self) -> None:
        self._connected = False
        self.subscribed = False
        if self.connected_event is not None:
            self.connected_event.clear()
        await self._drop_client()

    def _topic(self, event_type: str) -> str:
        return f"{TOPIC_PREFIX}.{event_type}"

    def _envelope(
        self,
        event_type: str,
        payload: dict[str, Any],
        *,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        tenant_id: str | None = None,
        policy_decision_id: str | None = None,
        evidence_refs: list[str] | None = None,
        classification: str = "internal",
    ) -> dict[str, Any]:
        eid = str(uuid.uuid4())
        return {
            # v1 frozen fields
            "event_id": eid,
            "event_type": f"{SYSTEM}.{event_type}.v1",
            "schema_version": SCHEMA_VERSION,
            "producer": SYSTEM,
            "correlation_id": correlation_id or eid,
            "idempotency_key": f"{SYSTEM}:{event_type}:{eid}",
            "classification": classification,
            "occurred_at": _now(),
            "payload": payload,
            "topic": self._topic(event_type),
            "source": SYSTEM,
            "timestamp": _now(),
            # v1.1 additions (GAR-529)
            "tenant_id": tenant_id or DEFAULT_TENANT_ID,
            "causation_id": causation_id,
            "policy_decision_id": policy_decision_id,
            "evidence_refs": list(evidence_refs or []),
        }

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any] | None = None,
        *,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        tenant_id: str | None = None,
        policy_decision_id: str | None = None,
        evidence_refs: list[str] | None = None,
        classification: str = "internal",
    ) -> dict[str, Any] | None:
        """Publish an event. Returns envelope or None if offline."""
        if not self._connected or not self.client:
            return None
        envelope = self._envelope(
            event_type,
            payload or {},
            correlation_id=correlation_id,
            causation_id=causation_id,
            tenant_id=tenant_id,
            policy_decision_id=policy_decision_id,
            evidence_refs=evidence_refs,
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
            if _is_connection_error(exc):
                self._mark_disconnected(exc)
            logger.error("Publish failed: %s", _safe_error(exc))
            return None

    async def subscribe(
        self,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
        *,
        system_only: bool = False,
        stop: asyncio.Event | None = None,
    ) -> None:
        """Subscribe to events. system_only=True listens only to this system's topics.

        Without ``stop`` this keeps the old behavior: return immediately when offline
        and return when the connection drops. With ``stop`` it waits for the bus to
        (re)connect and resubscribes after every drop until ``stop`` is set.
        """
        if stop is None:
            if not self._connected or not self.client:
                return
            await self._subscribe_once(callback, system_only)
            return
        self._ensure_runtime()
        if not self.redis_url:
            return
        while not stop.is_set():
            if not self._connected or not self.client:
                await self._wait(stop, self.health_interval, self.connected_event)
                continue
            dropped = await self._subscribe_once(callback, system_only, stop)
            if dropped and not stop.is_set():
                # Let the supervisor reconnect; small pause avoids a hot loop.
                await self._wait(stop, min(self.backoff_base, 1.0))

    async def _subscribe_once(
        self,
        callback: Callable[[dict[str, Any]], Awaitable[None]],
        system_only: bool,
        stop: asyncio.Event | None = None,
    ) -> bool:
        """Run one subscription session. Returns True if it ended because of an error."""
        pubsub = self.client.pubsub()
        try:
            if system_only:
                await pubsub.psubscribe(f"{TOPIC_PREFIX}.*")
            else:
                await pubsub.subscribe(CHANNEL)
            self.subscribed = True
            logger.info("Subscribed to %s", f"{TOPIC_PREFIX}.*" if system_only else CHANNEL)
            while stop is None or not stop.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    continue
                if message.get("type") not in ("message", "pmessage"):
                    continue
                try:
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode()
                    event = json.loads(data)
                    await callback(event)
                except Exception as exc:
                    logger.error("Subscribe callback error: %s", exc)
            return False
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if _is_connection_error(exc):
                self._mark_disconnected(exc)
            else:
                self.last_error = _safe_error(exc)
            logger.error("Subscription dropped: %s", _safe_error(exc))
            return True
        finally:
            self.subscribed = False
            try:
                await pubsub.aclose()
            except Exception:
                pass
