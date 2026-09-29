"""Contract + event wiring tests for unprecedented-autonomous-revenue-os."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure offline mode for unit tests
os.environ.pop("REDIS_URL", None)

from contract.app import app, bus, SYSTEM, VERSION
from contract.event_bus import EventBus, TOPIC_PREFIX, SCHEMA_VERSION, DEFAULT_TENANT_ID


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_returns_system_and_flags(client):
    r = await client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    assert data["system"] == SYSTEM
    assert data["version"] == VERSION
    assert "event_bus_connected" in data
    assert "observability_connected" in data
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_meta_exposes_topic_schema_and_connection(client):
    r = await client.get("/meta")
    assert r.status_code == 200
    data = r.json()
    assert data["role"] == "revenue_os"
    assert data["event_bus_topic_schema"] == "garcar.{system}.{event_type}"
    assert data["system_topic_prefix"] == f"garcar.{SYSTEM}"
    assert "event_bus_connected" in data
    assert "observability_connected" in data


@pytest.mark.asyncio
async def test_metrics_includes_counters(client):
    await client.get("/health")
    r = await client.get("/metrics")
    assert r.status_code == 200
    data = r.json()
    assert data["requests_total"] >= 1
    assert data["health_checks"] >= 1
    assert "event_bus_connected" in data


@pytest.mark.asyncio
async def test_events_endpoint_returns_ring(client):
    r = await client.get("/events")
    assert r.status_code == 200
    data = r.json()
    assert "events" in data
    assert "total" in data
    assert isinstance(data["events"], list)


@pytest.mark.asyncio
async def test_emit_offline_records_in_memory(client):
    r = await client.post("/events/emit", json={"event_type": "test.ping", "payload": {"ok": True}})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] in ("emitted", "recorded_offline")
    assert "event" in data


def test_event_bus_topic_format():
    eb = EventBus(redis_url=None)
    assert eb._topic("cycle.completed") == f"{TOPIC_PREFIX}.cycle.completed"


def test_event_bus_envelope_shape():
    eb = EventBus(redis_url=None)
    env = eb._envelope("cycle.completed", {"mrr": 0})
    assert env["producer"] == SYSTEM
    assert env["schema_version"] == SCHEMA_VERSION
    assert env["event_type"].startswith(f"{SYSTEM}.cycle.completed")
    assert "event_id" in env
    assert "correlation_id" in env
    assert "idempotency_key" in env
    assert env["topic"] == f"{TOPIC_PREFIX}.cycle.completed"
    # v1.1 required keys always present
    assert env["tenant_id"] == DEFAULT_TENANT_ID
    assert "causation_id" in env
    assert "policy_decision_id" in env
    assert env["evidence_refs"] == []


def test_event_bus_envelope_v11_fields():
    eb = EventBus(redis_url=None)
    env = eb._envelope(
        "call.placed",
        {"to": "+1214"},
        correlation_id="corr-1",
        causation_id="cause-9",
        tenant_id="tenant-dfw",
        policy_decision_id="pol-42",
        evidence_refs=["evd_1", "evd_2"],
    )
    assert env["schema_version"] == "v1.1"
    assert env["correlation_id"] == "corr-1"
    assert env["causation_id"] == "cause-9"
    assert env["tenant_id"] == "tenant-dfw"
    assert env["policy_decision_id"] == "pol-42"
    assert env["evidence_refs"] == ["evd_1", "evd_2"]


@pytest.mark.asyncio
async def test_event_bus_offline_publish_returns_none():
    eb = EventBus(redis_url=None)
    assert eb.connected is False
    result = await eb.publish("test", {})
    assert result is None
