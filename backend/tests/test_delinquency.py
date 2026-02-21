"""Test delinquency endpoints."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_delinquency(client):
    """GET /properties/{id}/delinquency returns delinquency data."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/delinquency")
    assert resp.status_code == 200
    data = resp.json()

    assert isinstance(data, dict)
    assert "total_delinquent" in data
    assert "delinquency_aging" in data
    assert "collections" in data
    assert "resident_details" in data
    assert data["total_delinquent"] > 0


@pytest.mark.asyncio
async def test_delinquency_ar_separation(client):
    """Delinquency response separates current vs former resident totals."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/delinquency")
    assert resp.status_code == 200
    data = resp.json()

    # New AR separation fields
    assert "current_resident_total" in data
    assert "former_resident_total" in data
    assert "current_resident_count" in data
    assert "former_resident_count" in data

    # Totals should be non-negative numbers
    assert isinstance(data["current_resident_total"], (int, float))
    assert isinstance(data["former_resident_total"], (int, float))
    assert data["current_resident_total"] >= 0
    assert data["former_resident_total"] >= 0

    # Resident counts should add up
    assert data["current_resident_count"] + data["former_resident_count"] == data["resident_count"]

    # resident_details should have is_former flag
    for r in data["resident_details"]:
        assert "is_former" in r


@pytest.mark.asyncio
async def test_delinquency_former_in_collections(client):
    """Former resident balances should appear in collections section."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/delinquency")
    assert resp.status_code == 200
    data = resp.json()

    if data["former_resident_count"] > 0:
        assert data["collections"]["total"] > 0
