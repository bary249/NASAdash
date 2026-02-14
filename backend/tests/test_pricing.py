"""Test pricing, trade-out, and renewal endpoints."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_pricing(client):
    """GET /properties/{id}/pricing returns valid UnitPricingMetrics shape."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/pricing")
    assert resp.status_code == 200
    data = resp.json()

    assert data["property_id"] == TEST_PROPERTY_ID
    assert "floorplans" in data
    assert "total_in_place_rent" in data
    assert "total_asking_rent" in data
    assert "total_rent_growth" in data


@pytest.mark.asyncio
async def test_get_tradeouts(client):
    """GET /properties/{id}/tradeouts returns tradeouts + summary."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/tradeouts")
    assert resp.status_code == 200
    data = resp.json()

    assert "tradeouts" in data
    assert "summary" in data
    assert isinstance(data["tradeouts"], list)

    summary = data["summary"]
    assert "count" in summary
    assert "avg_prior_rent" in summary
    assert "avg_new_rent" in summary
    assert "avg_dollar_change" in summary
    assert "avg_pct_change" in summary


@pytest.mark.asyncio
async def test_get_tradeouts_with_days_filter(client):
    """Trade-outs endpoint accepts optional days filter."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/tradeouts?days=30")
    assert resp.status_code == 200
    data = resp.json()
    assert "tradeouts" in data


@pytest.mark.asyncio
async def test_get_renewals(client):
    """GET /properties/{id}/renewals returns renewals with prior rent comparison."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/renewals")
    assert resp.status_code == 200
    data = resp.json()

    assert "renewals" in data
    assert "summary" in data
    assert isinstance(data["renewals"], list)

    summary = data["summary"]
    assert "count" in summary
    assert "avg_renewal_rent" in summary
    assert "avg_prior_rent" in summary
    assert "avg_vs_prior" in summary
    assert "avg_vs_prior_pct" in summary

    # Each renewal should have prior_rent fields (not market_rent)
    for r in data["renewals"]:
        assert "renewal_rent" in r
        assert "prior_rent" in r
        assert "vs_prior" in r
        assert "vs_prior_pct" in r


@pytest.mark.asyncio
async def test_get_renewals_with_days_filter(client):
    """Renewals endpoint accepts optional days filter."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/renewals?days=90")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_renewals_with_month_filter(client):
    """Renewals endpoint accepts calendar month filter."""
    resp = await client.get(f"/api/v2/properties/{TEST_PROPERTY_ID}/renewals?month=2026-01")
    assert resp.status_code == 200
    data = resp.json()
    assert "renewals" in data
    assert "summary" in data
