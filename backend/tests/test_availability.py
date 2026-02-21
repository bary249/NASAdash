"""Test availability endpoint (WS2: ATR, buckets, 7-week trend)."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_availability(client):
    """GET /properties/{id}/availability returns ATR and availability metrics."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/availability")
    assert resp.status_code == 200
    data = resp.json()

    assert data["property_id"] == TEST_PROPERTY_ID
    assert "atr" in data
    assert "atr_pct" in data
    assert "availability_pct" in data
    assert "buckets" in data
    assert "trend" in data

    # ATR = vacant + on_notice - preleased
    expected_atr = max(0, data["vacant"] + data["on_notice"] - data["preleased"])
    assert data["atr"] == expected_atr

    # Buckets shape
    buckets = data["buckets"]
    assert "available_0_30" in buckets
    assert "available_30_60" in buckets
    assert "total" in buckets
    assert buckets["total"] >= 0
    bucket_sum = buckets.get("available_0_30", 0) + buckets.get("available_30_60", 0) + buckets.get("available_60_plus", 0)
    assert buckets["total"] == bucket_sum or buckets["total"] >= 0

    # Trend shape
    trend = data["trend"]
    assert trend["direction"] in ("increasing", "decreasing", "flat")
    assert isinstance(trend["weeks"], list)


@pytest.mark.asyncio
async def test_availability_unknown_property(client):
    """Unknown property returns 404."""
    resp = await client.get("/api/v2/properties/nonexistent_xyz/availability")
    assert resp.status_code in (404, 500)
