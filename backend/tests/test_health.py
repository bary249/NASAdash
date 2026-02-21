"""Test health and root endpoints."""
import pytest


@pytest.mark.asyncio
async def test_health(client):
    resp = await client.get("/api/v2/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert isinstance(data["status"], str)
    assert "timestamp" in data


@pytest.mark.asyncio
async def test_root(client):
    resp = await client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert "name" in data
    assert "version" in data
    assert isinstance(data["name"], str)
    assert isinstance(data["version"], str)
