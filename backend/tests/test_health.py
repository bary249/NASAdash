"""Test health and root endpoints."""
import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/v2/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Owner Dashboard V2 API"
    assert data["version"] == "2.0.0"
