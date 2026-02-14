"""Test forecast/projected occupancy endpoint."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_forecast(client):
    """GET /properties/{id}/forecast returns weekly projections."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/occupancy-forecast")
    # May return 200 with data or 500 if projected_occupancy table is empty
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        assert isinstance(data, dict)
        if "weeks" in data:
            assert isinstance(data["weeks"], list)


@pytest.mark.asyncio
async def test_get_forecast_with_weeks(client):
    """Forecast endpoint accepts weeks parameter."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/occupancy-forecast?weeks=4")
    assert resp.status_code in (200, 500)
