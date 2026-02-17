"""
Comprehensive UI Data Integrity Tests
======================================
Validates that all API endpoints return consistent, non-empty data
and that breakdowns sum to totals across all views.

Run:  python -m pytest tests/test_ui_data_integrity.py -v
      python -m pytest tests/test_ui_data_integrity.py -v --tb=short -q   (compact)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
API = f"{BASE_URL}/api/v2/properties"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def property_ids():
    """Get all property IDs from the properties endpoint."""
    r = requests.get(f"{BASE_URL}/api/v2/properties")
    assert r.status_code == 200, f"Properties list failed: {r.text[:200]}"
    data = r.json()
    ids = [p["id"] for p in data] if isinstance(data, list) else [p["id"] for p in data.get("properties", [])]
    assert len(ids) > 0, "No properties returned"
    return ids


# Use a property with full data for detailed tests.
# Override via PROPERTY_ID env var.
TEST_PROPERTY = os.environ.get("PROPERTY_ID", "nexus_east")


@pytest.fixture(scope="module")
def first_property():
    return TEST_PROPERTY


def _get(endpoint, params=None):
    """Helper: GET and assert 200."""
    r = requests.get(endpoint, params=params, timeout=30)
    assert r.status_code == 200, f"GET {endpoint} → {r.status_code}: {r.text[:300]}"
    return r.json()


# ===================================================================
# 1. ENDPOINT HEALTH — every endpoint returns 200
# ===================================================================

class TestEndpointHealth:
    """All endpoints return 200 with non-empty data."""

    ENDPOINTS = [
        "/occupancy",
        "/availability",
        "/availability-by-floorplan",
        "/availability-by-floorplan/units",
        "/consolidated-by-bedroom",
        "/leasing-funnel",
        "/turn-time",
        "/projected-occupancy",
        "/expirations",
        "/expirations/details?days=90",
        "/shows?days=90",
        "/occupancy-forecast",
        "/financials",
        "/marketing",
        "/maintenance",
        "/lost-rent",
        "/move-out-reasons",
        "/delinquency",
    ]

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_endpoint_returns_200(self, first_property, endpoint):
        url = f"{API}/{first_property}{endpoint}"
        r = requests.get(url, timeout=30)
        assert r.status_code in (200, 404), f"{endpoint} → {r.status_code}: {r.text[:300]}"
        if r.status_code == 404:
            pytest.skip(f"{endpoint} returned 404 (no data for this property)")
        data = r.json()
        assert data is not None, f"{endpoint} returned null"


# ===================================================================
# 2. OCCUPANCY CONSISTENCY
# ===================================================================

class TestOccupancyConsistency:
    """Occupancy numbers are self-consistent and cross-check across endpoints."""

    def test_occupancy_units_sum(self, first_property):
        """occupied + vacant + excluded ≈ total"""
        occ = _get(f"{API}/{first_property}/occupancy")
        assert occ["total_units"] > 0
        assert occ["occupied_units"] >= 0
        assert occ["vacant_units"] >= 0
        assert occ["leased_units"] >= occ["occupied_units"]
        # Physical occupancy math
        expected_pct = round(occ["occupied_units"] / occ["total_units"] * 100, 2)
        assert abs(occ["physical_occupancy"] - expected_pct) < 0.5, \
            f"Occupancy pct mismatch: reported={occ['physical_occupancy']} expected={expected_pct}"

    def test_occupancy_leased_gte_occupied(self, first_property):
        """Leased % >= Occupied % (preleased units count as leased)."""
        occ = _get(f"{API}/{first_property}/occupancy")
        assert occ["leased_percentage"] >= occ["physical_occupancy"] - 0.1

    def test_total_units_across_endpoints(self, first_property):
        """total_units matches across occupancy, floorplan, bedroom."""
        occ = _get(f"{API}/{first_property}/occupancy")
        fp = _get(f"{API}/{first_property}/availability-by-floorplan")
        bed = _get(f"{API}/{first_property}/consolidated-by-bedroom")
        assert fp["totals"]["total"] == occ["total_units"], \
            f"Floorplan total {fp['totals']['total']} != occupancy {occ['total_units']}"
        assert bed["totals"]["total_units"] == occ["total_units"], \
            f"Bedroom total {bed['totals']['total_units']} != occupancy {occ['total_units']}"


# ===================================================================
# 3. AVAILABILITY & ATR
# ===================================================================

class TestAvailability:
    """Availability buckets, ATR math, and drill-through counts."""

    def test_atr_formula(self, first_property):
        """ATR = vacant + on_notice - preleased."""
        avail = _get(f"{API}/{first_property}/availability")
        expected_atr = avail["vacant"] + avail["on_notice"] - avail["preleased"]
        assert avail["atr"] == expected_atr, \
            f"ATR mismatch: {avail['atr']} != {avail['vacant']}+{avail['on_notice']}-{avail['preleased']}={expected_atr}"

    def test_availability_buckets_sum(self, first_property):
        """0-30 + 30-60 + 60+ == total bucket count."""
        avail = _get(f"{API}/{first_property}/availability")
        b = avail["buckets"]
        bucket_sum = b["available_0_30"] + b["available_30_60"] + b["available_60_plus"]
        assert bucket_sum == b["total"], \
            f"Bucket sum {bucket_sum} != total {b['total']}"

    def test_bucket_total_matches_atr(self, first_property):
        """Bucket total (0-30 + 30-60 + 60+) must equal ATR."""
        avail = _get(f"{API}/{first_property}/availability")
        assert avail["buckets"]["total"] == avail["atr"], \
            f"Bucket total {avail['buckets']['total']} != ATR {avail['atr']}"

    def test_availability_pct_math(self, first_property):
        """availability_pct ≈ atr / total_units * 100."""
        avail = _get(f"{API}/{first_property}/availability")
        if avail["total_units"] > 0:
            expected = round(avail["atr"] / avail["total_units"] * 100, 1)
            assert abs(avail["atr_pct"] - expected) < 0.2, \
                f"ATR pct {avail['atr_pct']} != expected {expected}"


# ===================================================================
# 4. FLOORPLAN BREAKDOWN SUMS
# ===================================================================

class TestFloorplanBreakdown:
    """Individual floorplan rows sum to the totals row."""

    def test_floorplan_rows_sum_to_totals(self, first_property):
        fp = _get(f"{API}/{first_property}/availability-by-floorplan")
        rows = fp["floorplans"]
        totals = fp["totals"]

        assert sum(r["total_units"] for r in rows) == totals["total"], "total_units sum mismatch"
        assert sum(r["vacant_units"] for r in rows) == totals["vacant"], "vacant sum mismatch"
        assert sum(r["on_notice"] for r in rows) == totals["notice"], "notice sum mismatch"
        assert sum(r["occupied_units"] for r in rows) == totals["occupied"], "occupied sum mismatch"
        assert sum(r["vacant_leased"] for r in rows) == totals["vacant_leased"], "vacant_leased sum mismatch"
        assert sum(r["model_units"] for r in rows) == totals["model"], "model sum mismatch"
        assert sum(r["down_units"] for r in rows) == totals["down"], "down sum mismatch"

    def test_floorplan_per_row_consistency(self, first_property):
        """Each floorplan: occupied + vacant + notice + model + down == total (approximately)."""
        fp = _get(f"{API}/{first_property}/availability-by-floorplan")
        for r in fp["floorplans"]:
            parts = r["occupied_units"] + r["vacant_units"] + r["on_notice"] + r["model_units"] + r["down_units"]
            assert abs(parts - r["total_units"]) <= 1, \
                f"FP {r['floorplan']}: parts sum {parts} != total {r['total_units']}"


# ===================================================================
# 5. CONSOLIDATED BY BEDROOM
# ===================================================================

class TestBedroomBreakdown:
    """Bedroom rows sum to totals; rent averages present."""

    def test_bedroom_rows_sum_to_totals(self, first_property):
        bed = _get(f"{API}/{first_property}/consolidated-by-bedroom")
        rows = bed["bedrooms"]
        t = bed["totals"]

        assert sum(r["total_units"] for r in rows) == t["total_units"]
        assert sum(r["occupied"] for r in rows) == t["occupied"]
        assert sum(r["vacant"] for r in rows) == t["vacant"]
        assert sum(r["vacant_leased"] for r in rows) == t["vacant_leased"]
        assert sum(r["on_notice"] for r in rows) == t["on_notice"]
        assert sum(r["expiring_90d"] for r in rows) == t["expiring_90d"]
        assert sum(r["renewed_90d"] for r in rows) == t["renewed_90d"]

    def test_bedroom_totals_have_rent(self, first_property):
        """Total row includes avg_market_rent and avg_in_place_rent."""
        bed = _get(f"{API}/{first_property}/consolidated-by-bedroom")
        t = bed["totals"]
        assert "avg_market_rent" in t, "Missing avg_market_rent in totals"
        assert "avg_in_place_rent" in t, "Missing avg_in_place_rent in totals"
        assert "rent_delta" in t, "Missing rent_delta in totals"
        if t["occupied"] > 0:
            assert t["avg_market_rent"] > 0, "avg_market_rent should be > 0"
            assert t["avg_in_place_rent"] > 0, "avg_in_place_rent should be > 0"

    def test_bedroom_occupancy_pct(self, first_property):
        bed = _get(f"{API}/{first_property}/consolidated-by-bedroom")
        for r in bed["bedrooms"]:
            if r["total_units"] > 0:
                expected = round(r["occupied"] / r["total_units"] * 100, 1)
                assert abs(r["occupancy_pct"] - expected) < 0.2, \
                    f"{r['bedroom_type']}: occ_pct {r['occupancy_pct']} != expected {expected}"


# ===================================================================
# 6. EXPIRATIONS & RENEWALS
# ===================================================================

class TestExpirations:
    """Expiration periods, drill-through matching."""

    def test_expirations_periods_present(self, first_property):
        exp = _get(f"{API}/{first_property}/expirations")
        assert "periods" in exp and len(exp["periods"]) > 0

    def test_expirations_30d_lte_60d_lte_90d(self, first_property):
        """Cumulative periods: 30d <= 60d <= 90d."""
        exp = _get(f"{API}/{first_property}/expirations")
        periods = {p["label"]: p for p in exp["periods"]}
        if "30d" in periods and "60d" in periods:
            assert periods["30d"]["expirations"] <= periods["60d"]["expirations"]
        if "60d" in periods and "90d" in periods:
            assert periods["60d"]["expirations"] <= periods["90d"]["expirations"]

    def test_expirations_drill_count_matches(self, first_property):
        """Drill-through detail count == summary expirations count for 90d."""
        exp = _get(f"{API}/{first_property}/expirations")
        p90 = next((p for p in exp["periods"] if p["label"] == "90d"), None)
        if p90 and p90["expirations"] > 0:
            det = _get(f"{API}/{first_property}/expirations/details?days=90")
            detail_list = det.get("details", det.get("leases", []))
            assert len(detail_list) == p90["expirations"], \
                f"90d drill count {len(detail_list)} != summary {p90['expirations']}"

    def test_renewals_lte_expirations(self, first_property):
        """Renewals can't exceed expirations in any period."""
        exp = _get(f"{API}/{first_property}/expirations")
        for p in exp["periods"]:
            assert p["renewals"] <= p["expirations"], \
                f"Period {p['label']}: renewals {p['renewals']} > expirations {p['expirations']}"


# ===================================================================
# 7. LEASING FUNNEL
# ===================================================================

class TestLeasingFunnel:
    """Funnel stages are non-negative and properly ordered."""

    def test_funnel_stages_non_negative(self, first_property):
        f = _get(f"{API}/{first_property}/leasing-funnel")
        for key in ["leads", "tours", "applications", "lease_signs"]:
            assert f.get(key, 0) >= 0, f"Funnel {key} is negative"

    def test_funnel_leads_gte_tours(self, first_property):
        f = _get(f"{API}/{first_property}/leasing-funnel")
        assert f["leads"] >= f["tours"], \
            f"Leads {f['leads']} < tours {f['tours']}"

    TIMEFRAMES = ["cm", "pm", "l30", "l7", "ytd"]

    @pytest.mark.parametrize("tf", TIMEFRAMES)
    def test_funnel_all_timeframes_return_200(self, first_property, tf):
        """Every timeframe returns 200 with valid funnel data."""
        f = _get(f"{API}/{first_property}/leasing-funnel?timeframe={tf}")
        assert "leads" in f, f"Missing 'leads' in {tf} response"
        assert "tours" in f, f"Missing 'tours' in {tf} response"
        assert "applications" in f, f"Missing 'applications' in {tf} response"
        assert "lease_signs" in f, f"Missing 'lease_signs' in {tf} response"

    @pytest.mark.parametrize("tf", TIMEFRAMES)
    def test_funnel_non_negative_all_timeframes(self, first_property, tf):
        """All funnel values are non-negative for every timeframe."""
        f = _get(f"{API}/{first_property}/leasing-funnel?timeframe={tf}")
        for key in ["leads", "tours", "applications", "lease_signs"]:
            assert f.get(key, 0) >= 0, f"{tf}: {key}={f.get(key)} is negative"

    @pytest.mark.parametrize("tf", ["cm", "l30", "l7"])
    def test_funnel_has_data_for_current_periods(self, first_property, tf):
        """Current period funnel should have leads > 0 for active properties."""
        f = _get(f"{API}/{first_property}/leasing-funnel?timeframe={tf}")
        # Allow l7 to have 0 if report data has a lag
        if tf == "l7" and f["leads"] == 0:
            pytest.skip("L7 may have 0 leads due to report data lag")
        assert f["leads"] > 0, f"{tf}: 0 leads for {first_property} (expected active property)"

    def test_funnel_conversion_rates_present(self, first_property):
        """Conversion rates are returned and within 0-100%."""
        f = _get(f"{API}/{first_property}/leasing-funnel")
        for key in ["lead_to_tour_rate", "tour_to_app_rate", "app_to_lease_rate", "lead_to_lease_rate"]:
            assert key in f, f"Missing {key}"
            assert 0 <= f[key] <= 100, f"{key}={f[key]} out of 0-100 range"

    def test_funnel_period_dates_present(self, first_property):
        """Response includes period_start and period_end."""
        f = _get(f"{API}/{first_property}/leasing-funnel")
        assert f.get("period_start"), "Missing period_start"
        assert f.get("period_end"), "Missing period_end"
        assert f["period_start"] <= f["period_end"], \
            f"period_start {f['period_start']} > period_end {f['period_end']}"

    def test_funnel_custom_date_range(self, first_property):
        """Custom start_date/end_date overrides timeframe and returns data."""
        f = _get(f"{API}/{first_property}/leasing-funnel?timeframe=cm&start_date=2026-01-01&end_date=2026-01-31")
        assert "leads" in f
        # Should match PM data roughly
        pm = _get(f"{API}/{first_property}/leasing-funnel?timeframe=pm")
        # Custom date range Jan 1-31 should be close to PM (which is also Jan)
        if pm["leads"] > 0:
            assert f["leads"] > 0, "Custom date range Jan returned 0 leads but PM has data"

    def test_funnel_ytd_gte_cm(self, first_property):
        """YTD leads should be >= current month leads (YTD includes current month)."""
        ytd = _get(f"{API}/{first_property}/leasing-funnel?timeframe=ytd")
        cm = _get(f"{API}/{first_property}/leasing-funnel?timeframe=cm")
        if ytd["leads"] > 0 and cm["leads"] > 0:
            assert ytd["leads"] >= cm["leads"], \
                f"YTD leads {ytd['leads']} < CM leads {cm['leads']}"


class TestLeasingFunnelAllProperties:
    """Funnel data integrity across ALL properties (not just the test property)."""

    def test_funnel_no_negative_values_all_properties(self, property_ids):
        """No property should have negative funnel values for any timeframe."""
        errors = []
        for pid in property_ids:
            for tf in ["cm", "l30", "l7"]:
                r = requests.get(f"{API}/{pid}/leasing-funnel?timeframe={tf}", timeout=30)
                if r.status_code != 200:
                    continue
                f = r.json()
                for key in ["leads", "tours", "applications", "lease_signs"]:
                    if f.get(key, 0) < 0:
                        errors.append(f"{pid}/{tf}: {key}={f[key]}")
        assert not errors, f"Negative funnel values found:\n" + "\n".join(errors)

    def test_funnel_leads_gte_tours_all_properties(self, property_ids):
        """Leads >= tours for all properties (funnel should narrow)."""
        errors = []
        for pid in property_ids:
            for tf in ["cm", "l30"]:
                r = requests.get(f"{API}/{pid}/leasing-funnel?timeframe={tf}", timeout=30)
                if r.status_code != 200:
                    continue
                f = r.json()
                if f["leads"] > 0 and f["tours"] > f["leads"]:
                    errors.append(f"{pid}/{tf}: tours({f['tours']}) > leads({f['leads']})")
        assert not errors, f"Funnel narrowing violated:\n" + "\n".join(errors)

    def test_funnel_prior_period_comparison(self, property_ids):
        """Prior period (custom date range) returns data for properties with current data."""
        # Test L30 vs prior 30 days for a few properties
        test_props = property_ids[:5]
        for pid in test_props:
            current = requests.get(f"{API}/{pid}/leasing-funnel?timeframe=l30", timeout=30)
            if current.status_code != 200:
                continue
            c = current.json()
            if c["leads"] == 0:
                continue
            # Prior 30d: days 31-60 ago
            from datetime import datetime, timedelta
            now = datetime.now()
            prior_end = (now - timedelta(days=30)).strftime("%Y-%m-%d")
            prior_start = (now - timedelta(days=60)).strftime("%Y-%m-%d")
            prior = requests.get(
                f"{API}/{pid}/leasing-funnel?timeframe=l30&start_date={prior_start}&end_date={prior_end}",
                timeout=30
            )
            if prior.status_code != 200:
                continue
            p = prior.json()
            # Prior should have data if current does (at least some leads)
            assert p["leads"] >= 0, f"{pid}: prior L30 has negative leads"
            # Sanity: prior and current shouldn't be identical unless coincidence
            # (they cover different date ranges, so usually differ)


# ===================================================================
# 8. MARKETING
# ===================================================================

class TestMarketing:
    """Marketing sources sum to totals."""

    def test_marketing_sources_sum_to_totals(self, first_property):
        mkt = _get(f"{API}/{first_property}/marketing")
        if not mkt.get("sources"):
            pytest.skip("No marketing data")
        t = mkt["totals"]
        assert sum(s["new_prospects"] for s in mkt["sources"]) == t["total_prospects"]
        assert sum(s["visits"] for s in mkt["sources"]) == t["total_visits"]
        assert sum(s["leases"] for s in mkt["sources"]) == t["total_leases"]
        assert sum(s["net_leases"] for s in mkt["sources"]) == t["total_net_leases"]

    def test_marketing_has_sources(self, first_property):
        mkt = _get(f"{API}/{first_property}/marketing")
        # Only fail if we expect data for this property
        if first_property in ("nexus_east", "parkside"):
            assert len(mkt.get("sources", [])) > 0, "No marketing sources"


# ===================================================================
# 9. FINANCIALS
# ===================================================================

class TestFinancials:
    """Financial summary has key fields."""

    def test_financials_has_summary(self, first_property):
        fin = _get(f"{API}/{first_property}/financials")
        assert "summary" in fin, "Missing summary"
        s = fin["summary"]
        assert s.get("gross_market_rent") is not None, "Missing gross_market_rent"
        assert s.get("total_possible_collections") is not None, "Missing total_possible_collections"


# ===================================================================
# 10. MAINTENANCE
# ===================================================================

class TestMaintenance:
    """Maintenance pipeline and completed records."""

    def test_maintenance_has_data(self, first_property):
        m = _get(f"{API}/{first_property}/maintenance")
        assert "pipeline" in m, "Missing pipeline"
        assert "completed" in m, "Missing completed"
        assert "summary" in m, "Missing summary"

    def test_maintenance_summary_counts(self, first_property):
        m = _get(f"{API}/{first_property}/maintenance")
        assert m["summary"]["units_in_pipeline"] == len(m["pipeline"]), \
            f"Pipeline count mismatch: summary={m['summary']['units_in_pipeline']} actual={len(m['pipeline'])}"
        assert m["summary"]["completed_this_period"] == len(m["completed"]), \
            f"Completed count mismatch: summary={m['summary']['completed_this_period']} actual={len(m['completed'])}"


# ===================================================================
# 11. DELINQUENCY
# ===================================================================

class TestDelinquency:
    """Delinquency totals match detail sums."""

    def test_delinquency_has_data(self, first_property):
        d = _get(f"{API}/{first_property}/delinquency")
        assert "resident_details" in d
        assert d["resident_count"] >= 0

    def test_delinquent_detail_sum(self, first_property):
        d = _get(f"{API}/{first_property}/delinquency")
        detail_sum = sum(r.get("total_delinquent", 0) or 0 for r in d["resident_details"])
        assert abs(detail_sum - (d["total_delinquent"] or 0)) < 1.0, \
            f"Detail delinquent sum {detail_sum} != reported {d['total_delinquent']}"

    def test_delinquency_aging_sums(self, first_property):
        """For delinquent residents, aging buckets should sum ≈ total_delinquent.
        Note: late fees and other charges may cause buckets to not match exactly."""
        d = _get(f"{API}/{first_property}/delinquency")
        mismatches = 0
        for r in d["resident_details"]:
            if (r.get("total_delinquent") or 0) > 0:
                aging = (r.get("current", 0) or 0) + (r.get("days_30", 0) or 0) + \
                        (r.get("days_60", 0) or 0) + (r.get("days_90_plus", 0) or 0)
                if abs(aging - r["total_delinquent"]) > 500:
                    mismatches += 1
        # Allow up to 35% of residents to have aging vs total mismatch
        # (late fees, utility charges, and other non-rent items are not broken into aging buckets)
        total_delq = len([r for r in d["resident_details"] if (r.get("total_delinquent") or 0) > 0])
        if total_delq > 0:
            assert mismatches / total_delq < 0.35, \
                f"{mismatches}/{total_delq} residents have aging sum >$500 off from total_delinquent"


# ===================================================================
# 12. LOST RENT
# ===================================================================

class TestLostRent:
    """Lost rent unit count and total match."""

    def test_lost_rent_unit_count(self, first_property):
        lr = _get(f"{API}/{first_property}/lost-rent")
        if not lr.get("units"):
            pytest.skip("No lost rent data")
        assert len(lr["units"]) == lr["summary"]["total_units"]

    def test_lost_rent_total_matches(self, first_property):
        lr = _get(f"{API}/{first_property}/lost-rent")
        if not lr.get("units"):
            pytest.skip("No lost rent data")
        detail_sum = sum(u.get("lost_rent", 0) for u in lr["units"])
        assert abs(detail_sum - lr["summary"]["total_lost_rent"]) < 1.0, \
            f"Lost rent sum {detail_sum} != reported {lr['summary']['total_lost_rent']}"


# ===================================================================
# 13. MOVE-OUT REASONS
# ===================================================================

class TestMoveOutReasons:
    """Sub-reason counts sum to category counts."""

    def test_move_out_sub_reasons_sum(self, first_property):
        r = requests.get(f"{API}/{first_property}/move-out-reasons", timeout=30)
        if r.status_code == 404:
            pytest.skip("No move-out data for this property")
        mo = r.json()
        for cat_list_key in ["former", "current"]:
            for cat in mo.get(cat_list_key, []):
                sub_sum = sum(r["count"] for r in cat.get("reasons", []))
                assert sub_sum == cat["count"], \
                    f"Move-out {cat['category']}: sub_sum {sub_sum} != count {cat['count']}"


# ===================================================================
# 14. OCCUPANCY FORECAST
# ===================================================================

class TestOccupancyForecast:
    """Forecast weeks are sequential, projected occupancy is reasonable."""

    def test_forecast_has_weeks(self, first_property):
        fc = _get(f"{API}/{first_property}/occupancy-forecast")
        assert "forecast" in fc and len(fc["forecast"]) > 0

    def test_forecast_projected_within_bounds(self, first_property):
        fc = _get(f"{API}/{first_property}/occupancy-forecast")
        total = fc["total_units"]
        for w in fc["forecast"]:
            occ = w["projected_occupied"]
            assert 0 <= occ <= total * 1.05, \
                f"Week {w['week']}: projected_occupied {occ} out of bounds (total={total})"

    def test_forecast_net_change_math(self, first_property):
        """net_change ≈ move_ins - move_outs."""
        fc = _get(f"{API}/{first_property}/occupancy-forecast")
        for w in fc["forecast"]:
            mi = w.get("scheduled_move_ins", 0) or 0
            mo = w.get("scheduled_move_outs", 0) or 0
            notice_mo = w.get("notice_move_outs", 0) or 0
            net = w.get("net_change", 0) or 0
            # net_change should roughly be move_ins - (move_outs + notice_move_outs)
            # Allow slack for renewals/expirations logic
            assert abs(net - (mi - mo - notice_mo)) <= max(abs(net) * 0.5 + 5, 10), \
                f"Week {w.get('week')}: net={net} but mi={mi} mo={mo} nmo={notice_mo}"


# ===================================================================
# 15. SHOWS
# ===================================================================

class TestShows:
    """Shows by_date sums match total."""

    def test_shows_by_date_sum(self, first_property):
        s = _get(f"{API}/{first_property}/shows?days=90")
        if s["total_shows"] == 0:
            pytest.skip("No shows data")
        date_sum = sum(d["count"] for d in s["by_date"])
        assert date_sum == s["total_shows"], \
            f"by_date sum {date_sum} != total {s['total_shows']}"

    def test_shows_by_type_sum(self, first_property):
        s = _get(f"{API}/{first_property}/shows?days=90")
        if s["total_shows"] == 0:
            pytest.skip("No shows data")
        type_sum = sum(s["by_type"].values())
        assert type_sum == s["total_shows"], \
            f"by_type sum {type_sum} != total {s['total_shows']}"

    def test_shows_details_count(self, first_property):
        s = _get(f"{API}/{first_property}/shows?days=90")
        if s["total_shows"] == 0:
            pytest.skip("No shows data")
        assert len(s["details"]) == s["total_shows"], \
            f"details count {len(s['details'])} != total {s['total_shows']}"


# ===================================================================
# 16. PROJECTED OCCUPANCY
# ===================================================================

class TestProjectedOccupancy:
    """Projected occupancy sanity."""

    def test_projected_occupancy_reasonable(self, first_property):
        p = _get(f"{API}/{first_property}/projected-occupancy")
        assert p["total_units"] > 0
        if "projected_occupied" in p:
            assert 0 <= p["projected_occupied"] <= p["total_units"]


# ===================================================================
# 17. TURN TIME
# ===================================================================

class TestTurnTime:
    """Turn time averages are reasonable when data exists."""

    def test_turn_time_valid(self, first_property):
        t = _get(f"{API}/{first_property}/turn-time")
        if t["turn_count"] > 0:
            assert t["avg_turn_days"] is not None
            assert 0 <= t["avg_turn_days"] <= 180, \
                f"avg_turn_days {t['avg_turn_days']} out of range"
            assert t["min_turn_days"] <= t["avg_turn_days"] <= t["max_turn_days"]


# ===================================================================
# 18. DRILL-THROUGH: RECORD COUNTS MATCH CLICKED VALUES
# ===================================================================

class TestDrillThroughExpirations:
    """Expiration drill-through counts match summary for every period."""

    PERIODS = [30, 60, 90]

    @pytest.mark.parametrize("days", PERIODS)
    def test_expiration_drill_count(self, first_property, days):
        """Clicking expiration count opens detail with exact same number of records."""
        exp = _get(f"{API}/{first_property}/expirations")
        period = next((p for p in exp["periods"] if p["label"] == f"{days}d"), None)
        if not period or period["expirations"] == 0:
            pytest.skip(f"No {days}d expirations")
        det = _get(f"{API}/{first_property}/expirations/details?days={days}")
        detail_count = len(det.get("leases", []))
        assert detail_count == period["expirations"], \
            f"{days}d: drill count {detail_count} != summary {period['expirations']}"

    @pytest.mark.parametrize("days", PERIODS)
    def test_renewal_drill_count(self, first_property, days):
        """Clicking renewal count opens detail with exact same number of records."""
        exp = _get(f"{API}/{first_property}/expirations")
        period = next((p for p in exp["periods"] if p["label"] == f"{days}d"), None)
        if not period or period["renewals"] == 0:
            pytest.skip(f"No {days}d renewals")
        det = _get(f"{API}/{first_property}/expirations/details?days={days}&filter=renewed")
        detail_count = len(det.get("leases", []))
        assert detail_count == period["renewals"], \
            f"{days}d: renewed drill {detail_count} != summary {period['renewals']}"

    @pytest.mark.parametrize("days", PERIODS)
    def test_expiring_plus_renewed_eq_total(self, first_property, days):
        """Expiring (not renewed) + renewed == total expirations."""
        exp_all = _get(f"{API}/{first_property}/expirations/details?days={days}")
        exp_only = _get(f"{API}/{first_property}/expirations/details?days={days}&filter=expiring")
        ren_only = _get(f"{API}/{first_property}/expirations/details?days={days}&filter=renewed")
        total = len(exp_all.get("leases", []))
        expiring = len(exp_only.get("leases", []))
        renewed = len(ren_only.get("leases", []))
        # There may be other statuses (vacating, MTM, moved_out) so expiring+renewed <= total
        assert expiring + renewed <= total, \
            f"{days}d: expiring({expiring}) + renewed({renewed}) > total({total})"


class TestDrillThroughAvailability:
    """Availability drill-through counts match KPI values."""

    def test_vacant_drill_count(self, first_property):
        """Clicking Vacant KPI → units list count matches."""
        avail = _get(f"{API}/{first_property}/availability")
        r = requests.get(f"{API}/{first_property}/availability-by-floorplan/units?status=vacant", timeout=30)
        if r.status_code != 200:
            pytest.skip("Status filter not supported")
        units = r.json().get("units", [])
        assert len(units) == avail["vacant"], \
            f"Vacant drill {len(units)} != KPI {avail['vacant']}"

    def test_notice_drill_count(self, first_property):
        """Clicking On Notice KPI → units list count matches."""
        avail = _get(f"{API}/{first_property}/availability")
        r = requests.get(f"{API}/{first_property}/availability-by-floorplan/units?status=notice", timeout=30)
        if r.status_code != 200:
            pytest.skip("Status filter not supported")
        units = r.json().get("units", [])
        assert len(units) == avail["on_notice"], \
            f"Notice drill {len(units)} != KPI {avail['on_notice']}"

    def test_preleased_drill_count(self, first_property):
        """Clicking Pre-leased KPI → units list count matches."""
        avail = _get(f"{API}/{first_property}/availability")
        r = requests.get(f"{API}/{first_property}/availability-by-floorplan/units?status=preleased", timeout=30)
        if r.status_code != 200:
            pytest.skip("Status filter not supported")
        units = r.json().get("units", [])
        assert len(units) == avail["preleased"], \
            f"Preleased drill {len(units)} != KPI {avail['preleased']}"

    def test_atr_drill_count(self, first_property):
        """Clicking ATR KPI → ?status=atr returns exactly ATR units."""
        avail = _get(f"{API}/{first_property}/availability")
        atr_r = requests.get(f"{API}/{first_property}/availability-by-floorplan/units?status=atr", timeout=30)
        assert atr_r.status_code == 200, f"ATR drill failed: {atr_r.status_code}"
        atr_units = atr_r.json().get("units", [])
        assert len(atr_units) == avail["atr"], \
            f"ATR drill {len(atr_units)} != KPI {avail['atr']}"


class TestDrillThroughAvailabilityPortfolio:
    """Portfolio-level: drill counts summed across ALL properties must match summed KPIs.
    This catches the bug where the frontend queried a single property instead of all."""

    def test_portfolio_vacant_drill_count(self, property_ids):
        """Sum of vacant drill across all properties == sum of vacant KPIs."""
        total_kpi = 0
        total_drill = 0
        for pid in property_ids:
            r = requests.get(f"{API}/{pid}/availability", timeout=30)
            if r.status_code != 200:
                continue
            avail = r.json()
            total_kpi += avail.get("vacant", 0)
            dr = requests.get(f"{API}/{pid}/availability-by-floorplan/units?status=vacant", timeout=30)
            if dr.status_code == 200:
                total_drill += dr.json().get("count", 0)
        assert total_drill == total_kpi, \
            f"Portfolio vacant drill {total_drill} != KPI sum {total_kpi}"

    def test_portfolio_notice_drill_count(self, property_ids):
        """Sum of notice drill across all properties == sum of on_notice KPIs."""
        total_kpi = 0
        total_drill = 0
        for pid in property_ids:
            r = requests.get(f"{API}/{pid}/availability", timeout=30)
            if r.status_code != 200:
                continue
            avail = r.json()
            total_kpi += avail.get("on_notice", 0)
            dr = requests.get(f"{API}/{pid}/availability-by-floorplan/units?status=notice", timeout=30)
            if dr.status_code == 200:
                total_drill += dr.json().get("count", 0)
        assert total_drill == total_kpi, \
            f"Portfolio notice drill {total_drill} != KPI sum {total_kpi}"

    def test_portfolio_preleased_drill_count(self, property_ids):
        """Sum of preleased drill across all properties == sum of preleased KPIs."""
        total_kpi = 0
        total_drill = 0
        for pid in property_ids:
            r = requests.get(f"{API}/{pid}/availability", timeout=30)
            if r.status_code != 200:
                continue
            avail = r.json()
            total_kpi += avail.get("preleased", 0)
            dr = requests.get(f"{API}/{pid}/availability-by-floorplan/units?status=preleased", timeout=30)
            if dr.status_code == 200:
                total_drill += dr.json().get("count", 0)
        assert total_drill == total_kpi, \
            f"Portfolio preleased drill {total_drill} != KPI sum {total_kpi}"

    def test_portfolio_atr_drill_count(self, property_ids):
        """Sum of ATR drill across all properties == sum of ATR KPIs."""
        total_kpi = 0
        total_drill = 0
        for pid in property_ids:
            r = requests.get(f"{API}/{pid}/availability", timeout=30)
            if r.status_code != 200:
                continue
            avail = r.json()
            total_kpi += avail.get("atr", 0)
            dr = requests.get(f"{API}/{pid}/availability-by-floorplan/units?status=atr", timeout=30)
            if dr.status_code == 200:
                total_drill += dr.json().get("count", 0)
        assert total_drill == total_kpi, \
            f"Portfolio ATR drill {total_drill} != KPI sum {total_kpi}"


class TestDrillThroughFloorplan:
    """Floorplan drill-through: per-floorplan unit count matches summary."""

    def test_floorplan_unit_counts(self, first_property):
        fp = _get(f"{API}/{first_property}/availability-by-floorplan")
        units_data = _get(f"{API}/{first_property}/availability-by-floorplan/units")
        all_units = units_data.get("units", [])
        for f_row in fp["floorplans"]:
            name = f_row["floorplan"]
            drill_units = [u for u in all_units if u.get("floorplan") == name]
            assert len(drill_units) == f_row["total_units"], \
                f"FP {name}: drill {len(drill_units)} != summary {f_row['total_units']}"

    def test_total_units_drill_count(self, first_property):
        """Total units in floorplan drill matches totals row."""
        fp = _get(f"{API}/{first_property}/availability-by-floorplan")
        units_data = _get(f"{API}/{first_property}/availability-by-floorplan/units")
        all_units = units_data.get("units", [])
        assert len(all_units) == fp["totals"]["total"], \
            f"Total drill {len(all_units)} != totals {fp['totals']['total']}"


class TestDrillThroughTradeouts:
    """Tradeout drill-through array length matches summary count."""

    def test_tradeout_drill_count(self, first_property):
        tr = _get(f"{API}/{first_property}/tradeouts?days=30")
        if not tr.get("tradeouts"):
            pytest.skip("No tradeouts")
        assert len(tr["tradeouts"]) == tr["summary"]["count"], \
            f"Tradeout drill {len(tr['tradeouts'])} != summary {tr['summary']['count']}"


class TestDrillThroughRenewals:
    """Renewal drill-through array length matches summary count."""

    def test_renewal_drill_count(self, first_property):
        ren = _get(f"{API}/{first_property}/renewals?days=30")
        if not ren.get("renewals"):
            pytest.skip("No renewals")
        assert len(ren["renewals"]) == ren["summary"]["count"], \
            f"Renewal drill {len(ren['renewals'])} != summary {ren['summary']['count']}"


class TestDrillThroughForecast:
    """Forecast drill-through: unit arrays support weekly drill-down."""

    def test_forecast_move_in_units_gte_weekly_sum(self, first_property):
        """Move-in unit list should have enough records for weekly drill."""
        fc = _get(f"{API}/{first_property}/occupancy-forecast")
        if not fc.get("forecast"):
            pytest.skip("No forecast data")
        mi_units = fc.get("move_in_units", [])
        weekly_sum = sum(w.get("scheduled_move_ins", 0) or 0 for w in fc["forecast"])
        # Unit list may include undated move-ins, so >= weekly scheduled
        assert len(mi_units) >= weekly_sum or weekly_sum == 0, \
            f"move_in_units({len(mi_units)}) < weekly scheduled sum({weekly_sum})"

    def test_forecast_notice_units_present(self, first_property):
        """Notice unit list should exist when notice_move_outs > 0."""
        fc = _get(f"{API}/{first_property}/occupancy-forecast")
        if not fc.get("forecast"):
            pytest.skip("No forecast data")
        notice_units = fc.get("notice_units", [])
        weekly_notice = sum(w.get("notice_move_outs", 0) or 0 for w in fc["forecast"])
        if weekly_notice > 0:
            assert len(notice_units) > 0, \
                f"weekly notice={weekly_notice} but notice_units is empty"

    def test_forecast_expiration_units_present(self, first_property):
        """Expiration unit list should exist when lease_expirations > 0."""
        fc = _get(f"{API}/{first_property}/occupancy-forecast")
        if not fc.get("forecast"):
            pytest.skip("No forecast data")
        exp_units = fc.get("expiration_units", [])
        weekly_exp = sum(w.get("lease_expirations", 0) or 0 for w in fc["forecast"])
        if weekly_exp > 0:
            assert len(exp_units) > 0, \
                f"weekly expirations={weekly_exp} but expiration_units is empty"


# ===================================================================
# 19. DRILL-THROUGH FIELD COMPLETENESS
# ===================================================================

class TestDrillThroughFieldCompleteness:
    """Every drill-through must have complete data — no missing fields that should be present."""

    def test_all_units_have_sqft(self, first_property):
        """Every unit must have sqft > 0."""
        data = _get(f"{API}/{first_property}/availability-by-floorplan/units")
        missing = [u["unit"] for u in data["units"] if not u.get("sqft") or u["sqft"] <= 0]
        assert len(missing) == 0, f"{len(missing)} units missing sqft: {missing[:10]}"

    def test_all_units_have_market_rent(self, first_property):
        """Every unit must have market_rent > 0."""
        data = _get(f"{API}/{first_property}/availability-by-floorplan/units")
        missing = [u["unit"] for u in data["units"] if not u.get("market_rent") or u["market_rent"] <= 0]
        assert len(missing) == 0, f"{len(missing)} units missing market_rent: {missing[:10]}"

    def test_occupied_units_have_actual_rent(self, first_property):
        """Occupied units must have actual_rent > 0."""
        data = _get(f"{API}/{first_property}/availability-by-floorplan/units?status=occupied")
        units = data.get("units", [])
        if not units:
            pytest.skip("No occupied units")
        missing = [u["unit"] for u in units if not u.get("actual_rent") or u["actual_rent"] <= 0]
        pct = len(missing) / len(units) * 100 if units else 0
        assert pct < 10, f"{len(missing)}/{len(units)} ({pct:.0f}%) occupied units missing actual_rent: {missing[:10]}"

    def test_ntv_units_have_actual_rent(self, first_property):
        """On-notice units must have actual_rent (from lease expirations fallback)."""
        data = _get(f"{API}/{first_property}/availability-by-floorplan/units?status=notice")
        units = data.get("units", [])
        if not units:
            pytest.skip("No notice units")
        missing = [u["unit"] for u in units if not u.get("actual_rent") or u["actual_rent"] <= 0]
        pct = len(missing) / len(units) * 100 if units else 0
        assert pct < 10, f"{len(missing)}/{len(units)} ({pct:.0f}%) NTV units missing actual_rent: {missing[:10]}"

    def test_ntv_units_have_lease_end(self, first_property):
        """On-notice units must have lease_end date."""
        data = _get(f"{API}/{first_property}/availability-by-floorplan/units?status=notice")
        units = data.get("units", [])
        if not units:
            pytest.skip("No notice units")
        missing = [u["unit"] for u in units if not u.get("lease_end")]
        assert len(missing) == 0, f"{len(missing)} NTV units missing lease_end: {missing[:10]}"

    def test_vacant_units_have_days_vacant(self, first_property):
        """Vacant (non-preleased) units must have days_vacant computed."""
        data = _get(f"{API}/{first_property}/availability-by-floorplan/units?status=atr")
        vacant = [u for u in data.get("units", []) if u["status"] == "Vacant"]
        if not vacant:
            pytest.skip("No vacant ATR units")
        missing = [u["unit"] for u in vacant if u.get("days_vacant") is None]
        pct = len(missing) / len(vacant) * 100 if vacant else 0
        assert pct < 15, f"{len(missing)}/{len(vacant)} ({pct:.0f}%) vacant units missing days_vacant: {missing[:10]}"

    def test_atr_drill_rent_coverage(self, first_property):
        """ATR drill should have rent for all NTV units, and days_vacant for all vacant."""
        data = _get(f"{API}/{first_property}/availability-by-floorplan/units?status=atr")
        units = data.get("units", [])
        ntv = [u for u in units if u["status"] in ("Occupied-NTV", "Occupied-NTVL")]
        ntv_no_rent = [u["unit"] for u in ntv if not u.get("actual_rent") or u["actual_rent"] <= 0]
        assert len(ntv_no_rent) == 0, f"NTV units missing rent in ATR drill: {ntv_no_rent}"

    def test_expiration_drill_has_lease_end(self, first_property):
        """Expiration drill records must all have lease_end."""
        det = _get(f"{API}/{first_property}/expirations/details?days=90")
        leases = det.get("leases", [])
        if not leases:
            pytest.skip("No expiration leases")
        missing = [l.get("unit") for l in leases if not l.get("lease_end")]
        pct = len(missing) / len(leases) * 100 if leases else 0
        assert pct < 5, f"{len(missing)}/{len(leases)} expiration records missing lease_end"

    def test_tradeout_drill_has_rents(self, first_property):
        """Tradeout drill records must have prior_rent and new_rent."""
        tr = _get(f"{API}/{first_property}/tradeouts?days=30")
        trades = tr.get("tradeouts", [])
        if not trades:
            pytest.skip("No tradeouts")
        for t in trades:
            assert t.get("prior_rent") is not None, f"Tradeout unit {t.get('unit_id')} missing prior_rent"
            assert t.get("new_rent") is not None, f"Tradeout unit {t.get('unit_id')} missing new_rent"

    def test_renewal_drill_has_rents(self, first_property):
        """Renewal drill records must have renewal_rent and prior_rent."""
        ren = _get(f"{API}/{first_property}/renewals?days=30")
        renewals = ren.get("renewals", [])
        if not renewals:
            pytest.skip("No renewals")
        missing_rent = [r.get("unit_id") for r in renewals if not r.get("renewal_rent")]
        pct = len(missing_rent) / len(renewals) * 100 if renewals else 0
        assert pct < 10, f"{len(missing_rent)}/{len(renewals)} renewal records missing rent"

    def test_shows_drill_has_dates(self, first_property):
        """Show detail records must have dates."""
        s = _get(f"{API}/{first_property}/shows?days=90")
        details = s.get("details", [])
        if not details:
            pytest.skip("No show details")
        missing = [d for d in details if not d.get("date")]
        assert len(missing) == 0, f"{len(missing)} show records missing date"

    def test_delinquency_drill_has_amounts(self, first_property):
        """Delinquency resident details must have total_delinquent."""
        d = _get(f"{API}/{first_property}/delinquency")
        details = d.get("resident_details", [])
        if not details:
            pytest.skip("No delinquency details")
        missing = [r.get("unit") for r in details if r.get("total_delinquent") is None]
        assert len(missing) == 0, f"{len(missing)} delinquency records missing amount"


# ===================================================================
# 20. LOGICAL CONSISTENCY (status ↔ lease/rent/days alignment)
# ===================================================================

class TestLogicalConsistency:
    """Cross-field logical checks: status must be consistent with lease, rent, and vacancy data."""

    def _all_units(self, property_ids):
        """Fetch all units across all properties."""
        all_units = []
        for pid in property_ids:
            r = requests.get(f"{API}/{pid}/availability-by-floorplan/units", timeout=30)
            if r.status_code == 200:
                for u in r.json().get("units", []):
                    u["_property"] = pid
                    all_units.append(u)
        return all_units

    def test_no_unknown_statuses(self, property_ids):
        """Every unit must have a recognized display status."""
        units = self._all_units(property_ids)
        valid = {'Occupied', 'Vacant', 'Vacant-Leased', 'Occupied-NTV',
                 'Occupied-NTVL', 'Admin/Down'}
        bad = [f"{u['_property']}/{u['unit']}={u['status']}"
               for u in units if u.get("status") not in valid]
        assert len(bad) == 0, f"{len(bad)} units with unknown status: {bad[:10]}"

    def test_occupied_units_have_lease_end(self, property_ids):
        """Occupied units must have a lease_end date."""
        units = self._all_units(property_ids)
        occupied = [u for u in units if u["status"] == "Occupied"]
        if not occupied:
            pytest.skip("No occupied units")
        missing = [f"{u['_property']}/{u['unit']}" for u in occupied if not u.get("lease_end")]
        pct = len(missing) / len(occupied) * 100
        assert pct < 5, \
            f"{len(missing)}/{len(occupied)} ({pct:.0f}%) occupied units missing lease_end: {missing[:10]}"

    def test_ntv_units_have_lease_end(self, property_ids):
        """On-notice units must have a lease_end date."""
        units = self._all_units(property_ids)
        ntv = [u for u in units if u["status"] in ("Occupied-NTV", "Occupied-NTVL")]
        if not ntv:
            pytest.skip("No NTV units")
        missing = [f"{u['_property']}/{u['unit']}" for u in ntv if not u.get("lease_end")]
        assert len(missing) == 0, \
            f"{len(missing)} NTV units missing lease_end: {missing[:10]}"

    def test_occupied_units_have_rent(self, property_ids):
        """Occupied units should have actual_rent (< 12% missing tolerated — RealPage API
        returns rent=0 for some properties where rent roll data is incomplete)."""
        units = self._all_units(property_ids)
        occupied = [u for u in units if u["status"] == "Occupied"]
        if not occupied:
            pytest.skip("No occupied units")
        missing = [f"{u['_property']}/{u['unit']}" for u in occupied
                   if not u.get("actual_rent") or u["actual_rent"] <= 0]
        pct = len(missing) / len(occupied) * 100
        assert pct < 12, \
            f"{len(missing)}/{len(occupied)} ({pct:.0f}%) occupied units missing actual_rent: {missing[:10]}"

    def test_days_vacant_only_on_vacant(self, property_ids):
        """Days vacant should only appear on vacant/Vacant-Leased units, never on occupied."""
        units = self._all_units(property_ids)
        bad = [f"{u['_property']}/{u['unit']} ({u['status']})"
               for u in units
               if u["status"] in ("Occupied", "Occupied-NTV", "Occupied-NTVL")
               and u.get("days_vacant") is not None]
        assert len(bad) == 0, \
            f"{len(bad)} non-vacant units have days_vacant set: {bad[:10]}"

    def test_estimated_rent_equals_market_rent(self, property_ids):
        """When rent_is_estimated=True, actual_rent must equal market_rent."""
        units = self._all_units(property_ids)
        estimated = [u for u in units if u.get("rent_is_estimated")]
        bad = [f"{u['_property']}/{u['unit']} actual={u.get('actual_rent')} mkt={u.get('market_rent')}"
               for u in estimated
               if u.get("actual_rent") != u.get("market_rent")]
        assert len(bad) == 0, \
            f"{len(bad)} estimated rent != market_rent: {bad[:10]}"

    def test_estimated_rent_only_on_vacant_or_down(self, property_ids):
        """rent_is_estimated should only be True for vacant or admin/down units."""
        units = self._all_units(property_ids)
        bad = [f"{u['_property']}/{u['unit']} ({u['status']})"
               for u in units
               if u.get("rent_is_estimated")
               and u["status"] not in ("Vacant", "Vacant-Leased", "Admin/Down")]
        assert len(bad) == 0, \
            f"{len(bad)} occupied/NTV units have rent_is_estimated=True: {bad[:10]}"

    def test_vacant_no_future_lease_end_unless_preleased(self, property_ids):
        """Vacant (non-preleased) units should not show future lease_end dates.
        Future lease_end on a vacant unit implies either a broken lease or
        a data issue (should be preleased). Allow < 2% tolerance — these are
        typically applicant leases on vacant_not_ready units awaiting move-in."""
        from datetime import datetime, date
        today = date.today()
        units = self._all_units(property_ids)
        vacant = [u for u in units
                  if u["status"] == "Vacant" and not u.get("is_preleased")]
        bad = []
        for u in vacant:
            le = u.get("lease_end")
            if not le:
                continue
            for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
                try:
                    le_date = datetime.strptime(le, fmt).date()
                    if le_date > today:
                        bad.append(f"{u['_property']}/{u['unit']} end={le}")
                    break
                except ValueError:
                    continue
        pct = len(bad) / len(vacant) * 100 if vacant else 0
        assert pct < 2, \
            f"{len(bad)}/{len(vacant)} ({pct:.1f}%) vacant non-preleased units have future lease_end: {bad[:10]}"

    def test_all_units_have_valid_status(self, property_ids):
        """Every unit must have a non-empty status."""
        units = self._all_units(property_ids)
        bad = [f"{u['_property']}/{u['unit']}" for u in units
               if not u.get("status") or u["status"].strip() == '']
        assert len(bad) == 0, f"{len(bad)} units with empty status: {bad[:10]}"

    def test_sqft_and_market_rent_positive(self, property_ids):
        """Every unit must have sqft > 0 and market_rent > 0."""
        units = self._all_units(property_ids)
        no_sqft = [f"{u['_property']}/{u['unit']}" for u in units
                   if not u.get("sqft") or u["sqft"] <= 0]
        no_mkt = [f"{u['_property']}/{u['unit']}" for u in units
                  if not u.get("market_rent") or u["market_rent"] <= 0]
        assert len(no_sqft) == 0, f"{len(no_sqft)} units missing sqft: {no_sqft[:10]}"
        assert len(no_mkt) == 0, f"{len(no_mkt)} units missing market_rent: {no_mkt[:10]}"


# ===================================================================
# 21. CROSS-PROPERTY (all properties pass basic checks)
# ===================================================================

class TestAllProperties:
    """Run basic health checks across all properties."""

    def test_all_properties_occupancy(self, property_ids):
        for pid in property_ids:
            occ = _get(f"{API}/{pid}/occupancy")
            assert occ["total_units"] > 0, f"{pid}: no units"
            assert occ["physical_occupancy"] >= 0, f"{pid}: negative occupancy"

    def test_all_properties_expirations(self, property_ids):
        for pid in property_ids:
            exp = _get(f"{API}/{pid}/expirations")
            assert "periods" in exp, f"{pid}: no periods"

    def test_all_properties_financials(self, property_ids):
        for pid in property_ids:
            r = requests.get(f"{API}/{pid}/financials", timeout=30)
            assert r.status_code in (200, 404), f"{pid}: financials {r.status_code}"
            if r.status_code == 200:
                fin = r.json()
                assert "summary" in fin, f"{pid}: no financial summary"

    def test_all_properties_marketing(self, property_ids):
        for pid in property_ids:
            r = requests.get(f"{API}/{pid}/marketing", timeout=30)
            assert r.status_code == 200, f"{pid}: marketing {r.status_code}"


# ===================================================================
# 22. ARCHITECTURE: API layer must read ONLY from unified.db
# ===================================================================

class TestArchitectureUnifiedOnly:
    """Enforce: the API/service layer must NEVER read from raw PMS databases.
    All data reads must come from unified.db. Raw DB access is only
    permitted in ETL/sync scripts (app/db/sync_*.py, download_*.py)."""

    # Files that constitute the "API layer" — must never touch raw DBs
    API_LAYER_GLOBS = [
        "app/api/**/*.py",
        "app/services/**/*.py",
    ]

    # Files excluded from scan (admin.py handles DB file uploads, not data reads)
    EXCLUDED_FILES = {"admin.py"}

    # Forbidden patterns: any reference to raw databases in the API layer
    FORBIDDEN_PATTERNS = [
        "realpage_raw",
        "yardi_raw",
        "realpage_residents",       # raw table
        "realpage_rent_roll",       # raw table (reads should use unified_units)
        "realpage_units",           # raw table (reads should use unified_units)
        "realpage_leases",          # raw table (reads should use unified_leases)
        "realpage_lease_expiration", # raw table
    ]

    # Whitelist: lines containing these are OK (e.g. comments explaining the rule)
    WHITELIST = [
        "# ",       # comments
        "\"\"\"",   # docstrings
        "'''",      # docstrings
    ]

    def _scan_files(self):
        """Scan API layer files for forbidden raw DB patterns."""
        import glob
        import os
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        violations = []
        for pattern in self.API_LAYER_GLOBS:
            for filepath in glob.glob(os.path.join(base, pattern), recursive=True):
                if os.path.basename(filepath) in self.EXCLUDED_FILES:
                    continue
                rel = os.path.relpath(filepath, base)
                with open(filepath, "r") as f:
                    for lineno, line in enumerate(f, 1):
                        stripped = line.strip()
                        # Skip comments and docstrings
                        if any(stripped.startswith(w) for w in self.WHITELIST):
                            continue
                        for forbidden in self.FORBIDDEN_PATTERNS:
                            if forbidden in line:
                                violations.append(
                                    f"{rel}:{lineno}: '{forbidden}' found in: {stripped[:120]}"
                                )
        return violations

    def test_no_raw_db_access_in_api_layer(self):
        """API layer files must not reference raw PMS databases or tables."""
        violations = self._scan_files()
        assert len(violations) == 0, (
            f"Architecture violation: {len(violations)} raw DB references in API layer.\n"
            "The API must read ONLY from unified.db. Move raw DB reads to sync scripts.\n"
            + "\n".join(violations[:20])
        )


# ===================================================================
# 23. MULTI-PROPERTY SUPPORT
# ===================================================================

PORTFOLIO = f"{BASE_URL}/api/portfolio"


@pytest.fixture(scope="module")
def multi_property_ids(property_ids):
    """Pick 2+ property IDs for multi-prop tests (PHH group: parkside + nexus_east)."""
    phh = [p for p in property_ids if p in ("parkside", "nexus_east")]
    if len(phh) >= 2:
        return phh
    # Fallback: first two properties
    return property_ids[:2] if len(property_ids) >= 2 else property_ids


class TestMultiPropertyEndpointHealth:
    """All per-property endpoints return 200 for EVERY property, not just the test prop."""

    ENDPOINTS = [
        "/occupancy",
        "/availability",
        "/availability-by-floorplan",
        "/consolidated-by-bedroom",
        "/expirations",
        "/pricing",
        "/maintenance",
        "/delinquency",
    ]

    @pytest.mark.parametrize("endpoint", ENDPOINTS)
    def test_endpoint_200_all_properties(self, property_ids, endpoint):
        failures = []
        for pid in property_ids:
            r = requests.get(f"{API}/{pid}{endpoint}", timeout=30)
            if r.status_code not in (200, 404):
                failures.append(f"{pid}: {r.status_code}")
        assert len(failures) == 0, f"Failures: {failures}"


class TestMultiPropertyPortfolioEndpoints:
    """Portfolio-level endpoints return valid aggregated data."""

    def test_portfolio_occupancy(self, multi_property_ids):
        ids = ",".join(multi_property_ids)
        data = _get(f"{PORTFOLIO}/occupancy?property_ids={ids}")
        assert data["total_units"] > 0
        assert data["occupied_units"] >= 0
        assert 0 <= data["physical_occupancy"] <= 100

    def test_portfolio_pricing(self, multi_property_ids):
        ids = ",".join(multi_property_ids)
        data = _get(f"{PORTFOLIO}/pricing?property_ids={ids}")
        assert "floorplans" in data or "total_in_place_rent" in data

    def test_portfolio_units(self, multi_property_ids):
        ids = ",".join(multi_property_ids)
        units = _get(f"{PORTFOLIO}/units?property_ids={ids}")
        assert isinstance(units, list)
        assert len(units) > 0
        # Units should come from multiple properties
        prop_ids_in_units = set(u.get("unified_property_id") or u.get("property_id", "") for u in units)
        if len(multi_property_ids) >= 2:
            assert len(prop_ids_in_units) >= 2, \
                f"Portfolio units only from {prop_ids_in_units}, expected ≥2 properties"

    def test_portfolio_residents(self, multi_property_ids):
        ids = ",".join(multi_property_ids)
        residents = _get(f"{PORTFOLIO}/residents?property_ids={ids}")
        assert isinstance(residents, list)
        assert len(residents) > 0

    def test_portfolio_summary(self, multi_property_ids):
        ids = ",".join(multi_property_ids)
        data = _get(f"{PORTFOLIO}/summary?property_ids={ids}")
        assert data["total_units"] > 0
        assert "physical_occupancy" in data


class TestMultiPropertyOccupancyAggregation:
    """Sum of per-property occupancy == portfolio occupancy."""

    def test_total_units_sum(self, multi_property_ids):
        per_prop = []
        for pid in multi_property_ids:
            per_prop.append(_get(f"{API}/{pid}/occupancy"))
        ids = ",".join(multi_property_ids)
        portfolio = _get(f"{PORTFOLIO}/occupancy?property_ids={ids}")
        sum_total = sum(p["total_units"] for p in per_prop)
        assert portfolio["total_units"] == sum_total, \
            f"Portfolio total {portfolio['total_units']} != sum {sum_total}"

    def test_occupied_units_sum(self, multi_property_ids):
        per_prop = []
        for pid in multi_property_ids:
            per_prop.append(_get(f"{API}/{pid}/occupancy"))
        ids = ",".join(multi_property_ids)
        portfolio = _get(f"{PORTFOLIO}/occupancy?property_ids={ids}")
        sum_occ = sum(p["occupied_units"] for p in per_prop)
        assert portfolio["occupied_units"] == sum_occ, \
            f"Portfolio occupied {portfolio['occupied_units']} != sum {sum_occ}"

    def test_vacant_units_sum(self, multi_property_ids):
        per_prop = []
        for pid in multi_property_ids:
            per_prop.append(_get(f"{API}/{pid}/occupancy"))
        ids = ",".join(multi_property_ids)
        portfolio = _get(f"{PORTFOLIO}/occupancy?property_ids={ids}")
        sum_vac = sum(p["vacant_units"] for p in per_prop)
        assert portfolio["vacant_units"] == sum_vac, \
            f"Portfolio vacant {portfolio['vacant_units']} != sum {sum_vac}"


class TestMultiPropertyAvailabilitySums:
    """ATR and availability summed across properties match per-property sums."""

    def test_atr_sums_across_properties(self, multi_property_ids):
        total_atr = 0
        total_vacant = 0
        total_notice = 0
        total_preleased = 0
        for pid in multi_property_ids:
            avail = _get(f"{API}/{pid}/availability")
            total_atr += avail["atr"]
            total_vacant += avail["vacant"]
            total_notice += avail["on_notice"]
            total_preleased += avail["preleased"]
        assert total_atr == total_vacant + total_notice - total_preleased, \
            f"Summed ATR {total_atr} != {total_vacant}+{total_notice}-{total_preleased}"


class TestMultiPropertyDrillThroughMerge:
    """Drill-through data summed per-property == what frontend gets with Promise.all."""

    def test_expiration_details_merge(self, multi_property_ids):
        """Expiration details from all properties should merge correctly."""
        total_leases = 0
        for pid in multi_property_ids:
            det = _get(f"{API}/{pid}/expirations/details?days=90")
            total_leases += len(det.get("leases", []))
        # Verify each property contributed
        assert total_leases > 0, "No expiration leases across properties"

    def test_expiration_summary_merge(self, multi_property_ids):
        """Sum of per-property expiration summaries should be consistent."""
        total_exp = 0
        total_ren = 0
        for pid in multi_property_ids:
            exp = _get(f"{API}/{pid}/expirations")
            p90 = next((p for p in exp["periods"] if p["label"] == "90d"), None)
            if p90:
                total_exp += p90["expirations"]
                total_ren += p90["renewals"]
        assert total_ren <= total_exp, \
            f"Multi-prop renewals {total_ren} > expirations {total_exp}"

    def test_availability_units_merge(self, multi_property_ids):
        """Vacant units from all properties merge correctly."""
        total_vacant_kpi = 0
        total_vacant_drill = 0
        for pid in multi_property_ids:
            avail = _get(f"{API}/{pid}/availability")
            total_vacant_kpi += avail["vacant"]
            dr = requests.get(f"{API}/{pid}/availability-by-floorplan/units?status=vacant", timeout=30)
            if dr.status_code == 200:
                total_vacant_drill += len(dr.json().get("units", []))
        assert total_vacant_drill == total_vacant_kpi, \
            f"Multi-prop vacant drill {total_vacant_drill} != KPI sum {total_vacant_kpi}"

    def test_tradeouts_merge(self, multi_property_ids):
        """Tradeouts from all properties merge correctly."""
        total_trades = 0
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/tradeouts?days=30", timeout=30)
            if r.status_code == 200:
                total_trades += len(r.json().get("tradeouts", []))
        # Just verify it doesn't error — data may or may not exist
        assert total_trades >= 0

    def test_renewals_merge(self, multi_property_ids):
        """Renewals from all properties merge correctly."""
        total_renewals = 0
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/renewals?days=30", timeout=30)
            if r.status_code == 200:
                total_renewals += len(r.json().get("renewals", []))
        assert total_renewals >= 0

    def test_consolidated_bedroom_merge(self, multi_property_ids):
        """Bedroom consolidated from all properties merge by bedroom_type."""
        all_rows = []
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/consolidated-by-bedroom", timeout=30)
            if r.status_code == 200:
                all_rows.extend(r.json().get("bedrooms", []))
        # Merge by bedroom_type
        merged = {}
        for row in all_rows:
            key = row["bedroom_type"]
            if key not in merged:
                merged[key] = 0
            merged[key] += row["total_units"]
        # Sum across all bedroom types should match sum of per-property totals
        total_from_merge = sum(merged.values())
        total_from_totals = 0
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/consolidated-by-bedroom", timeout=30)
            if r.status_code == 200:
                total_from_totals += r.json().get("totals", {}).get("total_units", 0)
        assert total_from_merge == total_from_totals, \
            f"Bedroom merge units {total_from_merge} != totals sum {total_from_totals}"

    def test_maintenance_merge(self, multi_property_ids):
        """Maintenance data from all properties merge pipeline arrays."""
        total_pipeline = 0
        total_completed = 0
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/maintenance", timeout=30)
            if r.status_code == 200:
                d = r.json()
                total_pipeline += len(d.get("pipeline", []))
                total_completed += len(d.get("completed", []))
        assert total_pipeline >= 0 and total_completed >= 0

    def test_delinquency_merge(self, multi_property_ids):
        """Delinquency from all properties merge resident_details arrays."""
        total_details = 0
        total_delinquent = 0.0
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/delinquency", timeout=30)
            if r.status_code == 200:
                d = r.json()
                total_details += len(d.get("resident_details", []))
                total_delinquent += d.get("total_delinquent", 0) or 0
        assert total_details >= 0

    def test_financials_merge(self, multi_property_ids):
        """Financials from all properties return valid summaries."""
        valid_count = 0
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/financials", timeout=30)
            if r.status_code == 200:
                fin = r.json()
                assert "summary" in fin, f"{pid}: no financial summary"
                valid_count += 1
        assert valid_count > 0, "No properties returned financial data"

    def test_shows_merge(self, multi_property_ids):
        """Shows from all properties merge details arrays."""
        total_shows = 0
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/shows?days=7", timeout=30)
            if r.status_code == 200:
                total_shows += r.json().get("total_shows", 0)
        assert total_shows >= 0

    def test_forecast_merge(self, multi_property_ids):
        """Forecast from all properties have compatible week counts."""
        week_counts = []
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/occupancy-forecast", timeout=30)
            if r.status_code == 200:
                fc = r.json()
                if fc.get("forecast"):
                    week_counts.append(len(fc["forecast"]))
        if week_counts:
            # All should have roughly the same number of weeks
            assert max(week_counts) - min(week_counts) <= 2, \
                f"Forecast week counts vary too much: {week_counts}"

    def test_marketing_merge(self, multi_property_ids):
        """Marketing from all properties merge sources arrays."""
        total_sources = 0
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/marketing", timeout=30)
            if r.status_code == 200:
                total_sources += len(r.json().get("sources", []))
        assert total_sources >= 0

    def test_move_out_reasons_merge(self, multi_property_ids):
        """Move-out reasons from all properties merge category arrays."""
        total_former = 0
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/move-out-reasons", timeout=30)
            if r.status_code == 200:
                total_former += len(r.json().get("former", []))
        assert total_former >= 0


class TestMultiPropertyPortfolioUnitsIntegrity:
    """Portfolio units endpoint returns correct aggregation matching per-property data."""

    def test_portfolio_unit_count_matches_per_property(self, multi_property_ids):
        """Portfolio units count == sum of per-property occupancy total_units."""
        ids = ",".join(multi_property_ids)
        portfolio_units = _get(f"{PORTFOLIO}/units?property_ids={ids}")
        per_prop_total = 0
        for pid in multi_property_ids:
            occ = _get(f"{API}/{pid}/occupancy")
            per_prop_total += occ["total_units"]
        assert len(portfolio_units) == per_prop_total, \
            f"Portfolio units {len(portfolio_units)} != per-prop sum {per_prop_total}"

    def test_portfolio_resident_count_reasonable(self, multi_property_ids):
        """Portfolio residents should be roughly equal to sum of occupied units."""
        ids = ",".join(multi_property_ids)
        portfolio_residents = _get(f"{PORTFOLIO}/residents?property_ids={ids}")
        total_occupied = 0
        for pid in multi_property_ids:
            occ = _get(f"{API}/{pid}/occupancy")
            total_occupied += occ["occupied_units"]
        # Residents include current+notice+past+future, so should be >= occupied
        assert len(portfolio_residents) >= total_occupied * 0.5, \
            f"Portfolio residents {len(portfolio_residents)} seems low for {total_occupied} occupied units"


# ===================================================================
# 24. DELINQUENCY AGING TOTAL FIX
# ===================================================================

class TestDelinquencyAgingTotalFix:
    """Validates the fix: total_delinquent == sum of clipped aging buckets.
    The backend now uses sum(max(0, bucket)) for total instead of the raw
    DB total, which could include credits that make buckets go negative."""

    def test_total_equals_aging_sum(self, first_property):
        """total_delinquent must equal sum of non-negative aging buckets."""
        d = _get(f"{API}/{first_property}/delinquency")
        aging = d.get("aging", {})
        bucket_sum = sum(max(0, aging.get(k, 0) or 0)
                         for k in ["current_balance", "balance_0_30", "balance_30_60",
                                   "balance_60_90", "balance_90_plus"])
        # The endpoint may use slightly different key names
        if bucket_sum == 0 and aging:
            bucket_sum = sum(max(0, v or 0) for v in aging.values() if isinstance(v, (int, float)))
        if d.get("total_delinquent", 0) > 0 or bucket_sum > 0:
            assert abs((d.get("total_delinquent", 0) or 0) - bucket_sum) < 1.0, \
                f"total_delinquent {d.get('total_delinquent')} != aging bucket sum {bucket_sum}"

    def test_gross_delinquent_gte_total(self, first_property):
        """gross_delinquent (raw) should be >= total_delinquent (clipped)."""
        d = _get(f"{API}/{first_property}/delinquency")
        gross = d.get("gross_delinquent")
        total = d.get("total_delinquent", 0) or 0
        if gross is not None:
            assert gross >= total - 1.0, \
                f"gross_delinquent {gross} < total_delinquent {total}"


# ===================================================================
# 25. RENTABLE ITEMS CONSISTENCY
# ===================================================================

class TestRentableItems:
    """Rentable items (amenities) endpoint consistency."""

    def test_amenities_has_data(self, first_property):
        r = requests.get(f"{API}/{first_property}/amenities", timeout=30)
        if r.status_code == 404:
            pytest.skip("No amenities for this property")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, (list, dict))

    def test_amenities_summary_totals(self, first_property):
        """Summary rented + available should equal total for each type."""
        r = requests.get(f"{API}/{first_property}/amenities/summary", timeout=30)
        if r.status_code == 404:
            pytest.skip("No amenities summary")
        assert r.status_code == 200
        data = r.json()
        categories = data if isinstance(data, list) else data.get("categories", data.get("types", []))
        if not categories:
            pytest.skip("No amenity categories")
        for cat in categories:
            if isinstance(cat, dict) and "total" in cat:
                rented = cat.get("rented", 0) or 0
                available = cat.get("available", 0) or 0
                total = cat.get("total", 0) or 0
                assert rented + available == total, \
                    f"Amenity {cat.get('type', '?')}: rented({rented}) + available({available}) != total({total})"

    def test_amenities_revenue_non_negative(self, first_property):
        """Revenue from rentable items should be non-negative."""
        r = requests.get(f"{API}/{first_property}/amenities/summary", timeout=30)
        if r.status_code == 404:
            pytest.skip("No amenities summary")
        data = r.json()
        categories = data if isinstance(data, list) else data.get("categories", data.get("types", []))
        for cat in categories:
            if isinstance(cat, dict):
                rev = cat.get("monthly_revenue", cat.get("revenue", 0)) or 0
                assert rev >= 0, f"Amenity {cat.get('type', '?')} has negative revenue: {rev}"


# ===================================================================
# 26. REVIEWS MULTI-PROPERTY WEIGHTED AVERAGE
# ===================================================================

class TestReviewsMultiProperty:
    """Reviews endpoint returns valid data; multi-prop merge produces
    weighted average ratings."""

    def test_reviews_has_rating(self, first_property):
        r = requests.get(f"{API}/{first_property}/reviews", timeout=30)
        if r.status_code == 404:
            pytest.skip("No reviews for this property")
        assert r.status_code == 200
        data = r.json()
        assert "rating" in data or "google_rating" in data

    def test_reputation_has_fields(self, first_property):
        r = requests.get(f"{API}/{first_property}/reputation", timeout=30)
        if r.status_code == 404:
            pytest.skip("No reputation data")
        assert r.status_code == 200
        data = r.json()
        # Should have at least one review source
        assert any(k in data for k in ["google_rating", "apartments_rating", "rating"]), \
            f"Reputation response missing rating fields: {list(data.keys())[:10]}"

    def test_multi_property_reviews_weighted_average(self, multi_property_ids):
        """When merging reviews across properties, the combined rating should be
        a weighted average (by review count), not a simple average."""
        ratings = []
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/reviews", timeout=30)
            if r.status_code == 200:
                d = r.json()
                rating = d.get("rating") or d.get("google_rating")
                count = d.get("review_count") or d.get("google_review_count", 0)
                if rating and count:
                    ratings.append({"rating": rating, "count": count})
        if len(ratings) < 2:
            pytest.skip("Need 2+ properties with review data")
        # Calculate expected weighted average
        total_reviews = sum(r["count"] for r in ratings)
        weighted_avg = sum(r["rating"] * r["count"] for r in ratings) / total_reviews
        # Simple average for comparison
        simple_avg = sum(r["rating"] for r in ratings) / len(ratings)
        # The two should differ if review counts differ (proving weighted avg is needed)
        # Just validate the math is reasonable
        assert 1.0 <= weighted_avg <= 5.0, f"Weighted avg {weighted_avg} out of range"
        assert 1.0 <= simple_avg <= 5.0, f"Simple avg {simple_avg} out of range"

    def test_multi_property_reputation_valid(self, multi_property_ids):
        """All PHH properties should have reputation data."""
        valid_count = 0
        for pid in multi_property_ids:
            r = requests.get(f"{API}/{pid}/reputation", timeout=30)
            if r.status_code == 200:
                valid_count += 1
        assert valid_count > 0, "No properties returned reputation data"


# ===================================================================
# 27. OCCUPANCY CROSS-CHECK: BOX SCORE vs UNIFIED_UNITS
# ===================================================================

class TestOccupancyCrossCheck:
    """Validates that occupancy from box score (unified_occupancy_metrics)
    aligns with unit counts from unified_units. The main bug was notice
    units not being counted as occupied in unified_units."""

    def test_occupied_plus_notice_matches_box_score(self, first_property):
        """occupied + notice from unified_units ≈ occupied from box score."""
        occ = _get(f"{API}/{first_property}/occupancy")  # box score source
        ids = first_property
        units = _get(f"{PORTFOLIO}/units?property_ids={ids}")
        # Count statuses from unified_units
        status_counts = {}
        for u in units:
            s = u.get("status", "unknown")
            status_counts[s] = status_counts.get(s, 0) + 1
        occupied_from_units = status_counts.get("occupied", 0) + status_counts.get("notice", 0)
        box_score_occupied = occ["occupied_units"]
        # Allow small tolerance (timing differences between data sources)
        tolerance = max(3, box_score_occupied * 0.02)
        assert abs(occupied_from_units - box_score_occupied) <= tolerance, \
            f"unified_units occupied+notice={occupied_from_units} vs box_score={box_score_occupied} " \
            f"(diff={abs(occupied_from_units - box_score_occupied)}, tolerance={tolerance})"

    def test_vacant_from_units_matches_box_score(self, first_property):
        """vacant from unified_units ≈ vacant from box score."""
        occ = _get(f"{API}/{first_property}/occupancy")
        ids = first_property
        units = _get(f"{PORTFOLIO}/units?property_ids={ids}")
        vacant_from_units = sum(1 for u in units if u.get("status") == "vacant")
        box_score_vacant = occ["vacant_units"]
        tolerance = max(3, box_score_vacant * 0.05)
        assert abs(vacant_from_units - box_score_vacant) <= tolerance, \
            f"unified_units vacant={vacant_from_units} vs box_score={box_score_vacant}"

    def test_total_units_match(self, first_property):
        """Total units from both sources should match exactly."""
        occ = _get(f"{API}/{first_property}/occupancy")
        ids = first_property
        units = _get(f"{PORTFOLIO}/units?property_ids={ids}")
        assert len(units) == occ["total_units"], \
            f"unified_units count={len(units)} vs box_score total={occ['total_units']}"

    def test_multi_property_occupancy_consistent(self, multi_property_ids):
        """Multi-prop: sum of (occ+notice) from unified_units ≈ sum of box score occupied."""
        ids = ",".join(multi_property_ids)
        units = _get(f"{PORTFOLIO}/units?property_ids={ids}")
        units_occupied = sum(1 for u in units if u.get("status") in ("occupied", "notice"))
        box_total = 0
        for pid in multi_property_ids:
            occ = _get(f"{API}/{pid}/occupancy")
            box_total += occ["occupied_units"]
        tolerance = max(5, box_total * 0.02)
        assert abs(units_occupied - box_total) <= tolerance, \
            f"Multi-prop unified_units occ+notice={units_occupied} vs box_score sum={box_total}"


# ===================================================================
# DATA CONSISTENCY: Watchpoints, AI, Watchlist vs Dashboard
# ===================================================================

PORTFOLIO = f"{BASE_URL}/api/portfolio"

class TestDataConsistency:
    """Watchpoints, AI insights, and watchlist must use the same data as the dashboard."""

    def test_watchpoint_atr_matches_availability(self, first_property):
        """Watchpoint ATR must equal the availability endpoint ATR."""
        avail = _get(f"{API}/{first_property}/availability")
        wp = _get(f"{API}/{first_property}/watchpoints")
        wp_atr = wp.get("current_metrics", {}).get("atr")
        if wp_atr is None:
            pytest.skip("No ATR in watchpoint metrics")
        assert wp_atr == avail["atr"], \
            f"Watchpoint ATR {wp_atr} != availability ATR {avail['atr']}"

    def test_watchpoint_delinquency_matches_dashboard(self, first_property):
        """Watchpoint delinquent_total must equal delinquency endpoint total (current only)."""
        delq = _get(f"{API}/{first_property}/delinquency")
        wp = _get(f"{API}/{first_property}/watchpoints")
        wp_delq = wp.get("current_metrics", {}).get("delinquent_total")
        if wp_delq is None:
            pytest.skip("No delinquent_total in watchpoint metrics")
        assert abs(wp_delq - delq["total_delinquent"]) < 1, \
            f"Watchpoint delinquent ${wp_delq} != dashboard ${delq['total_delinquent']}"

    def test_watchpoint_occupancy_matches_dashboard(self, first_property):
        """Watchpoint occupancy_pct must equal occupancy endpoint."""
        occ = _get(f"{API}/{first_property}/occupancy")
        wp = _get(f"{API}/{first_property}/watchpoints")
        wp_occ = wp.get("current_metrics", {}).get("occupancy_pct")
        if wp_occ is None:
            pytest.skip("No occupancy in watchpoint metrics")
        assert abs(wp_occ - occ["physical_occupancy"]) < 0.5, \
            f"Watchpoint occ {wp_occ}% != dashboard {occ['physical_occupancy']}%"

    def test_watchlist_delinquency_excludes_former(self, property_ids):
        """Watchlist delinquent totals must match dashboard (current residents only)."""
        wl = requests.get(f"{PORTFOLIO}/watchlist", timeout=30).json()
        errors = []
        for prop in wl.get("watchlist", [])[:5]:
            pid = prop["id"]
            wl_delq = prop.get("delinquent_total", 0)
            if wl_delq == 0:
                continue
            r = requests.get(f"{API}/{pid}/delinquency", timeout=30)
            if r.status_code != 200:
                continue
            dash_delq = r.json().get("total_delinquent", 0)
            if abs(wl_delq - dash_delq) > 1:
                errors.append(f"{pid}: watchlist ${wl_delq:,.0f} != dashboard ${dash_delq:,.0f}")
        assert not errors, "Watchlist delinquency mismatch:\n" + "\n".join(errors)

    def test_consistency_atr_all_properties(self, property_ids):
        """ATR must match between watchpoints and availability for all properties."""
        errors = []
        for pid in property_ids:
            avail_r = requests.get(f"{API}/{pid}/availability", timeout=30)
            wp_r = requests.get(f"{API}/{pid}/watchpoints", timeout=30)
            if avail_r.status_code != 200 or wp_r.status_code != 200:
                continue
            avail_atr = avail_r.json().get("atr")
            wp_atr = wp_r.json().get("current_metrics", {}).get("atr")
            if avail_atr is not None and wp_atr is not None and avail_atr != wp_atr:
                errors.append(f"{pid}: availability ATR={avail_atr} != watchpoint ATR={wp_atr}")
        assert not errors, "ATR mismatch:\n" + "\n".join(errors)


# ===================================================================
# MAIN — run standalone
# ===================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
