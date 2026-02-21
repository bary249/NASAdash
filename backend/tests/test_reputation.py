"""Test reputation endpoint (WS4: Multi-source reviews + Review Power)."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_reputation(client):
    """GET /properties/{id}/reputation returns multi-source reputation summary."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/reputation")
    assert resp.status_code == 200
    data = resp.json()

    assert data["property_id"] == TEST_PROPERTY_ID
    assert "overall_rating" in data
    assert "sources" in data
    assert "review_power" in data
    assert isinstance(data["sources"], list)

    # Each source should have valid structure
    for s in data["sources"]:
        assert "source" in s
        assert isinstance(s["source"], str)

    # Review power should have expected fields
    rp = data["review_power"]
    assert "response_rate" in rp
    assert "avg_response_hours" in rp
    assert "needs_attention" in rp
    assert "total_reviews" in rp
    assert isinstance(rp["total_reviews"], int)
    assert rp["total_reviews"] >= 0
