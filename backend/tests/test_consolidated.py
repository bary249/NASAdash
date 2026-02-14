"""Test consolidated-by-bedroom endpoint (WS5: Dashboard Consolidation)."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_consolidated_by_bedroom(client):
    """GET /properties/{id}/consolidated-by-bedroom returns bedroom-type aggregation."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/consolidated-by-bedroom")
    assert resp.status_code == 200
    data = resp.json()

    assert "bedrooms" in data
    assert "totals" in data
    assert isinstance(data["bedrooms"], list)

    # Test property has 1BR floorplans in box_score
    if len(data["bedrooms"]) > 0:
        bed = data["bedrooms"][0]
        assert "bedroom_type" in bed
        assert "total_units" in bed
        assert "occupied" in bed
        assert "vacant" in bed
        assert "occupancy_pct" in bed
        assert "avg_market_rent" in bed
        assert "avg_in_place_rent" in bed
        assert "floorplans" in bed

    # Totals should have occupancy_pct
    totals = data["totals"]
    if totals:
        assert "total_units" in totals
        assert "occupancy_pct" in totals
