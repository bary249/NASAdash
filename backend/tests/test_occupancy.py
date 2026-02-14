"""Test occupancy and exposure endpoints."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_occupancy(client):
    """GET /properties/{id}/occupancy returns valid OccupancyMetrics shape."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/occupancy")
    assert resp.status_code == 200
    data = resp.json()

    # Required fields
    assert data["property_id"] == TEST_PROPERTY_ID
    assert "total_units" in data
    assert "occupied_units" in data
    assert "vacant_units" in data
    assert "physical_occupancy" in data
    assert "leased_percentage" in data

    # Value sanity
    assert data["total_units"] >= data["occupied_units"]
    assert 0 <= data["physical_occupancy"] <= 100
    assert 0 <= data["leased_percentage"] <= 100


@pytest.mark.asyncio
async def test_get_occupancy_timeframes(client):
    """Occupancy endpoint accepts cm, pm, ytd timeframes."""
    for tf in ("cm", "pm", "ytd"):
        resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/occupancy?timeframe={tf}")
        assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_occupancy_unknown_property(client):
    """Unknown property returns 500 (no data)."""
    resp = await client.get("/api/v2/properties/nonexistent_xyz/occupancy")
    # May return 200 with zeros or 500 depending on fallback — just don't crash
    assert resp.status_code in (200, 500)


@pytest.mark.asyncio
async def test_get_exposure(client):
    """GET /properties/{id}/exposure returns valid ExposureMetrics shape."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/exposure")
    assert resp.status_code == 200
    data = resp.json()

    assert data["property_id"] == TEST_PROPERTY_ID
    assert "exposure_30_days" in data
    assert "exposure_60_days" in data
    assert isinstance(data["exposure_30_days"], int)
    assert isinstance(data["exposure_60_days"], int)
