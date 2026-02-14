"""Test watchlist endpoint (WS6: Underperforming properties)."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_watchlist(client):
    """GET /portfolio/watchlist returns scored property list."""
    resp = await client.get("/api/portfolio/watchlist")
    assert resp.status_code == 200
    data = resp.json()

    assert "total_properties" in data
    assert "flagged_count" in data
    assert "thresholds" in data
    assert "watchlist" in data
    assert isinstance(data["watchlist"], list)

    # Thresholds should have defaults
    t = data["thresholds"]
    assert t["occupancy_pct"] == 90.0
    assert t["delinquent_total"] == 5000.0
    assert t["renewal_rate_90d"] == 50.0
    assert t["google_rating"] == 3.5


@pytest.mark.asyncio
async def test_watchlist_custom_thresholds(client):
    """Watchlist accepts custom threshold parameters."""
    resp = await client.get("/api/portfolio/watchlist?occ_threshold=95&delinq_threshold=1000")
    assert resp.status_code == 200
    data = resp.json()
    assert data["thresholds"]["occupancy_pct"] == 95.0
    assert data["thresholds"]["delinquent_total"] == 1000.0


@pytest.mark.asyncio
async def test_watchlist_property_flags(client):
    """Each property in watchlist should have flags array and metrics."""
    resp = await client.get("/api/portfolio/watchlist")
    assert resp.status_code == 200
    data = resp.json()

    for prop in data["watchlist"]:
        assert "id" in prop
        assert "name" in prop
        assert "flags" in prop
        assert "flag_count" in prop
        assert isinstance(prop["flags"], list)
        assert prop["flag_count"] == len(prop["flags"])

        # Each flag should have expected fields
        for flag in prop["flags"]:
            assert "metric" in flag
            assert "label" in flag
            assert "severity" in flag
            assert flag["severity"] in ("high", "medium")
