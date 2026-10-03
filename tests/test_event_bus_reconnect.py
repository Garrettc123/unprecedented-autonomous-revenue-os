"""Reconnect / consumer-startup tests. No live Redis: fakeredis + mocks only."""
from __future__ import annotations

import asyncio
import json
import random
import warnings

import fakeredis
import pytest
from httpx import ASGITransport, AsyncClient
from redis.exceptions import ConnectionError as RedisConnectionError

from contract import app as app_module
from contract import consumers
from contract.event_bus import CHANNEL, EventBus, _safe_error, backoff_delay


async def _until(pred, timeout=3.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if pred():
            return True
        await asyncio.sleep(0.01)
    return pred()


def _fake_factory(server):
    return lambda url: fakeredis.FakeAsyncRedis(server=server, decode_responses=True)


def _fast(bus: EventBus) -> EventBus:
    bus.backoff_base = 0.001
    bus.backoff_max = 0.01
    bus.health_interval = 0.05
    return bus


def _fast_patched(bus: EventBus, monkeypatch) -> EventBus:
    """Like _fast, but pytest restores the shared bus's timing after the test."""
    monkeypatch.setattr(bus, "backoff_base", 0.001)
    monkeypatch.setattr(bus, "backoff_max", 0.01)
    monkeypatch.setattr(bus, "health_interval", 0.05)
    return bus


@pytest.fixture
def app_bus(monkeypatch):
    """Point the app's module-level bus at a fake Redis for one test."""
    bus = app_module.bus
    server = fakeredis.FakeServer()
    monkeypatch.setattr(bus, "redis_url", "redis://fake:6379/0")
    monkeypatch.setattr(bus, "client_factory", _fake_factory(server))
    _fast_patched(bus, monkeypatch)
    yield bus, server
    bus.redis_url = None
    bus.client = None
    bus._connected = False


# 1
def test_backoff_bounded_with_jitter():
    rng = random.Random(42)
    delays = [backoff_delay(a, 0.5, 30.0, rng.random) for a in range(40)]
    assert all(0 <= d <= 30.0 for d in delays)
    # equal jitter: delay is in [ceiling/2, ceiling]
    for a, d in enumerate(delays):
        ceiling = min(30.0, 0.5 * 2 ** a)
        assert ceiling / 2 <= d <= ceiling
    # capped once 0.5 * 2**a >= 30
    assert all(15.0 <= d <= 30.0 for d in delays[7:])
    assert backoff_delay(0, 0.5, 30.0, lambda: 0.0) == 0.25
    assert backoff_delay(0, 0.5, 30.0, lambda: 1.0) == 0.5
    # error text exposed on /health never carries URL credentials
    msg = _safe_error(RedisConnectionError("Error connecting to redis://default:not-a-real-pw@redis.railway.internal:6379"))
    assert "not-a-real-pw" not in msg and "://***@" in msg


# 2
async def test_startup_with_redis_down_then_up():
    server = fakeredis.FakeServer()
    calls = {"n": 0}

    def factory(url):
        calls["n"] += 1
        client = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
        if calls["n"] <= 3:
            async def bad_ping():
                raise RedisConnectionError("Error 111 connecting to redis://default:not-a-real-pw@redis.railway.internal:6379")
            client.ping = bad_ping
        return client

    bus = _fast(EventBus(redis_url="redis://fake:6379/0", client_factory=factory))
    bus.init_runtime()
    stop = asyncio.Event()
    task = asyncio.create_task(bus.run_forever(stop))
    assert await _until(lambda: bus.connected)
    assert calls["n"] == 4
    assert bus.reconnect_attempts == 3
    d = list(bus.delays)
    assert len(d) == 3 and all(0 < x <= bus.backoff_max for x in d)
    # lower bound of each delay grows: attempt k is >= base*2**k/2 (until the cap)
    assert d[1] >= 0.001 and d[2] >= 0.002
    # credentials never leak into state
    assert bus.last_error is None
    stop.set()
    await asyncio.wait_for(task, 2)


# 3
async def test_reconnect_after_connection_loss():
    server = fakeredis.FakeServer()
    bus = _fast(EventBus(redis_url="redis://fake:6379/0", client_factory=_fake_factory(server)))
    bus.init_runtime()
    stop = asyncio.Event()
    task = asyncio.create_task(bus.run_forever(stop))
    assert await _until(lambda: bus.connected)
    first_client = bus.client

    async def broken_publish(*a, **k):
        raise RedisConnectionError("Connection reset by peer")

    first_client.publish = broken_publish
    assert await bus.publish("x", {}) is None
    assert bus.connected is False or bus.client is not first_client
    assert bus.last_error is None or "ConnectionError" in bus.last_error
    assert await _until(lambda: bus.connected and bus.client is not first_client)
    env = await bus.publish("x", {"ok": True})
    assert env is not None and env["payload"] == {"ok": True}
    stop.set()
    await asyncio.wait_for(task, 2)


# 4
async def test_consumers_start_on_lifespan(app_bus, monkeypatch):
    bus, server = app_bus
    seen = []

    async def fake_control(event):
        seen.append(event)

    monkeypatch.setattr(consumers, "handle_control_command", fake_control)
    async with app_module.lifespan(app_module.app):
        assert await _until(lambda: bus.connected and bus.subscribed)
        producer = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
        await producer.publish(CHANNEL, json.dumps({"event_type": "x.control.v1", "payload": {"cmd": "pause"}}))
        assert await _until(lambda: len(seen) == 1)
        transport = ASGITransport(app=app_module.app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            data = (await c.get("/health")).json()
        assert data["status"] == "healthy"
        assert data["event_bus"]["consumers_running"] is True
        assert data["event_bus"]["subscribed"] is True
    assert seen[0]["payload"] == {"cmd": "pause"}


# 5
async def test_server_starts_when_redis_unreachable(monkeypatch):
    bus = app_module.bus

    def factory(url):
        client = fakeredis.FakeAsyncRedis(decode_responses=True)

        async def bad_ping():
            raise RedisConnectionError("Connection refused")

        client.ping = bad_ping
        return client

    monkeypatch.setattr(bus, "redis_url", "redis://unreachable:6379/0")
    monkeypatch.setattr(bus, "client_factory", factory)
    _fast_patched(bus, monkeypatch)
    try:
        async with asyncio.timeout(2):
            async with app_module.lifespan(app_module.app):
                transport = ASGITransport(app=app_module.app)
                async with AsyncClient(transport=transport, base_url="http://test") as c:
                    r = await c.get("/health")
                assert r.status_code == 200
                data = r.json()
                assert data["status"] == "degraded"
                assert data["event_bus_connected"] is False
                assert data["event_bus"]["configured"] is True
                assert await _until(lambda: bus.reconnect_attempts >= 2)
                assert "ConnectionError" in (bus.state()["last_error"] or "")
    finally:
        bus.redis_url = None


# 6
async def test_consumer_resubscribes_after_drop(monkeypatch):
    from redis.asyncio.client import PubSub

    server = fakeredis.FakeServer()
    bus = _fast(EventBus(redis_url="redis://fake:6379/0", client_factory=_fake_factory(server)))
    bus.init_runtime()
    stop = asyncio.Event()
    got = []

    async def cb(event):
        got.append(event)

    sup = asyncio.create_task(bus.run_forever(stop))
    sub = asyncio.create_task(bus.subscribe(cb, stop=stop))
    assert await _until(lambda: bus.subscribed)
    first_client = bus.client

    # The live subscription's next read fails once, like a dropped socket.
    orig_get_message = PubSub.get_message
    state = {"raised": False}

    async def flaky_get_message(self, *a, **k):
        if not state["raised"]:
            state["raised"] = True
            raise RedisConnectionError("Connection closed by server.")
        return await orig_get_message(self, *a, **k)

    monkeypatch.setattr(PubSub, "get_message", flaky_get_message)
    assert await _until(lambda: state["raised"])
    # Supervisor reconnects with a new client and the consumer resubscribes.
    assert await _until(lambda: bus.connected and bus.client is not first_client and bus.subscribed)
    producer = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    await producer.publish(CHANNEL, json.dumps({"event_type": "after.reconnect.v1"}))
    assert await _until(lambda: len(got) == 1)
    assert got[0]["event_type"] == "after.reconnect.v1"
    stop.set()
    await asyncio.wait_for(asyncio.gather(sup, sub), 3)


# 7
async def test_offline_mode_unchanged(monkeypatch):
    bus = app_module.bus
    monkeypatch.setattr(bus, "redis_url", None)
    async with app_module.lifespan(app_module.app):
        assert app_module.app.state.background_tasks == []
        transport = ASGITransport(app=app_module.app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            data = (await c.get("/health")).json()
        assert data["status"] == "healthy"
        assert data["event_bus_connected"] is False
        assert data["event_bus"]["configured"] is False
        assert data["event_bus"]["reconnect_attempts"] == 0
    eb = EventBus(redis_url=None)
    eb.init_runtime()
    await eb.run_forever(asyncio.Event())  # returns immediately, no retries
    assert eb.reconnect_attempts == 0
    await consumers.run_consumers(eb)  # returns immediately


# 8
async def test_clean_shutdown(app_bus):
    bus, _ = app_bus
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        async with app_module.lifespan(app_module.app):
            assert await _until(lambda: bus.connected and bus.subscribed)
            tasks = list(app_module.app.state.background_tasks)
            assert len(tasks) == 3
        assert all(t.done() for t in tasks)
    assert bus.connected is False
    assert bus.client is None
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    assert pending == []
