"""Test watchpoint CRUD endpoints (WS8: Custom AI Metrics)."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_watchpoints_empty(client):
    """GET /properties/{id}/watchpoints returns empty list initially."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/watchpoints")
    assert resp.status_code == 200
    data = resp.json()
    assert data["property_id"] == TEST_PROPERTY_ID
    assert "watchpoints" in data
    assert "available_metrics" in data
    assert "current_metrics" in data
    assert isinstance(data["watchpoints"], list)


@pytest.mark.asyncio
async def test_create_and_get_watchpoint(client):
    """POST then GET watchpoint lifecycle."""
    # Create
    resp = await client.post(
        f"/api/v2/properties/{TEST_PROPERTY_ID}/watchpoints",
        json={"metric": "occupancy_pct", "operator": "lt", "threshold": 90.0}
    )
    assert resp.status_code == 200
    wp = resp.json()
    assert wp["metric"] == "occupancy_pct"
    assert wp["operator"] == "lt"
    assert wp["threshold"] == 90.0
    assert wp["enabled"] is True
    assert "id" in wp

    # Get should include it
    resp2 = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/watchpoints")
    assert resp2.status_code == 200
    wps = resp2.json()["watchpoints"]
    assert any(w["id"] == wp["id"] for w in wps)

    # Clean up
    await client.delete(f"/api/v2/properties/{TEST_PROPERTY_ID}/watchpoints/{wp['id']}")


@pytest.mark.asyncio
async def test_create_watchpoint_bad_metric(client):
    """POST with invalid metric returns 400."""
    resp = await client.post(
        f"/api/v2/properties/{TEST_PROPERTY_ID}/watchpoints",
        json={"metric": "nonexistent", "operator": "lt", "threshold": 50}
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_delete_watchpoint(client):
    """DELETE removes a watchpoint."""
    # Create
    resp = await client.post(
        f"/api/v2/properties/{TEST_PROPERTY_ID}/watchpoints",
        json={"metric": "vacant_units", "operator": "gt", "threshold": 5}
    )
    wp_id = resp.json()["id"]

    # Delete
    resp2 = await client.delete(f"/api/v2/properties/{TEST_PROPERTY_ID}/watchpoints/{wp_id}")
    assert resp2.status_code == 200
    assert resp2.json()["deleted"] is True

    # Should be gone
    resp3 = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/watchpoints")
    wps = resp3.json()["watchpoints"]
    assert not any(w["id"] == wp_id for w in wps)
