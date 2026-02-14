"""Test property listing and info endpoints."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_properties_list(client):
    """GET /properties returns a list of PropertyInfo."""
    resp = await client.get("/api/v2/properties")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)

    # Our test property should be in the list
    ids = [p["id"] for p in data]
    assert TEST_PROPERTY_ID in ids


@pytest.mark.asyncio
async def test_get_property_summary(client):
    """GET /properties/{id}/summary returns dashboard summary."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/summary")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "property_info" in data


@pytest.mark.asyncio
async def test_get_risk_scores(client):
    """GET /properties/{id}/risk-scores returns risk data."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/risk-scores")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
