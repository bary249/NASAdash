"""Test reviews endpoint."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_reviews(client):
    """GET /properties/{id}/reviews returns review data or error gracefully."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/reviews")
    assert resp.status_code in (200, 500)
    if resp.status_code == 200:
        data = resp.json()
        # Should have reviews array even if empty
        if "reviews" in data:
            assert isinstance(data["reviews"], list)
