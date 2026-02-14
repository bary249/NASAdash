"""Test portfolio endpoints."""
import pytest
from tests.conftest import TEST_PROPERTY_ID


@pytest.mark.asyncio
async def test_get_portfolio_summary(client):
    """GET /portfolio/summary returns aggregated metrics."""
    resp = await client.get(f"/api/portfolio/summary?property_ids={TEST_PROPERTY_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    assert "property_ids" in data


@pytest.mark.asyncio
async def test_get_portfolio_risk_scores(client):
    """GET /portfolio/risk-scores returns risk data."""
    resp = await client.get(f"/api/portfolio/risk-scores?property_ids={TEST_PROPERTY_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


@pytest.mark.asyncio
async def test_get_portfolio_properties(client):
    """GET /portfolio/properties returns property list."""
    resp = await client.get("/api/portfolio/properties")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
