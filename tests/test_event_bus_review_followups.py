"""Regression tests for the revenue-os PR #6 review follow-ups (CodeRabbit).

No live Redis: fakeredis + stubs only.
"""
from __future__ import annotations

import asyncio

import fakeredis

from contract.event_bus import EventBus, _close_quietly


async def _until(pred, timeout=3.0):
    loop = asyncio.get_running_loop()
    end = loop.time() + timeout
    while loop.time() < end:
        if pred():
            return True
        await asyncio.sleep(0.01)
    return pred()


def _bus(server) -> EventBus:
    bus = EventBus(
        redis_url="redis://fake:6379/0",
        client_factory=lambda url: fakeredis.FakeAsyncRedis(server=server, decode_responses=True),
    )
    bus.backoff_base = 0.001
    bus.backoff_max = 0.01
    bus.health_interval = 0.05
    return bus


async def test_close_quietly_handles_close_only_and_aclose_objects():
    calls = []

    class CloseOnly:  # redis-py 5.0.0 shape: no aclose()
        async def close(self):
            calls.append("close")

    class Both:
        async def aclose(self):
            calls.append("aclose")

        async def close(self):  # pragma: no cover - must not be used
            calls.append("close-deprecated")

    class Broken:
        async def aclose(self):
            raise RuntimeError("boom")

    await _close_quietly(CloseOnly())
    await _close_quietly(Both())
    await _close_quietly(Broken())  # must not raise
    await _close_quietly(object())  # nothing to call, must not raise
    assert calls == ["close", "aclose"]


async def test_drop_client_actually_closes_old_client():
    closed = []

    class FakeClient:
        async def close(self):
            closed.append(True)

    bus = EventBus(redis_url="redis://fake:6379/0")
    bus.client = FakeClient()
    await bus._drop_client()
    assert bus.client is None and closed == [True]


async def test_subscription_session_ends_when_client_replaced():
    server = fakeredis.FakeServer()
    bus = _bus(server)
    assert await bus.connect()

    async def cb(event):
        pass

    stop = asyncio.Event()
    task = asyncio.create_task(bus._subscribe_once(cb, False, stop))
    assert await _until(lambda: bus.subscribed)
    # supervisor swaps in a new client (fast reconnect)
    bus.client = fakeredis.FakeAsyncRedis(server=server, decode_responses=True)
    async with asyncio.timeout(3):
        dropped = await task
    assert dropped is True  # caller must resubscribe on the new client
    assert bus.subscribed is False
    stop.set()
    await bus.close()


async def test_subscription_session_returns_false_on_stop():
    server = fakeredis.FakeServer()
    bus = _bus(server)
    assert await bus.connect()

    async def cb(event):
        pass

    stop = asyncio.Event()
    task = asyncio.create_task(bus._subscribe_once(cb, False, stop))
    assert await _until(lambda: bus.subscribed)
    stop.set()
    async with asyncio.timeout(3):
        assert await task is False
    await bus.close()


def test_serve_accepts_uppercase_log_level(monkeypatch):
    import uvicorn

    from contract import serve

    captured = {}

    class FakeServer:
        def __init__(self, config):
            captured["config"] = config

        def run(self, sockets=None):
            captured["sockets"] = sockets
            for s in sockets or []:
                s.close()

    monkeypatch.setenv("LOG_LEVEL", "INFO")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "0")
    monkeypatch.setattr(uvicorn, "Server", FakeServer)
    serve.main()
    cfg = captured["config"]
    assert cfg.log_level == "info"
    cfg.configure_logging()  # raised KeyError: 'INFO' before the fix
