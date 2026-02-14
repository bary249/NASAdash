"""Test lease expiration endpoints."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_expirations(client):
    """GET /properties/{id}/expirations returns expiration metrics."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/expirations")
    assert resp.status_code == 200
    data = resp.json()
    # Should have period-based expiration counts
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_get_expiration_details(client):
    """GET /properties/{id}/expirations/details returns lease records."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/expirations/details?days=90")
    assert resp.status_code == 200
    data = resp.json()

    assert "leases" in data
    assert isinstance(data["leases"], list)
    assert "count" in data


@pytest.mark.asyncio
async def test_expiration_details_filter_renewed(client):
    """Expiration details accepts filter=renewed."""
    resp = await client.get(
        f"/api/v2/properties/{TEST_PROPERTY_ID}/expirations/details?days=90&filter=renewed"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "leases" in data


@pytest.mark.asyncio
async def test_expiration_details_filter_expiring(client):
    """Expiration details accepts filter=expiring."""
    resp = await client.get(
        f"/api/v2/properties/{TEST_PROPERTY_ID}/expirations/details?days=30&filter=expiring"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "leases" in data
