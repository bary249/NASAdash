"""
Test fixtures for OwnerDashV2 backend tests.

Creates temporary SQLite databases with seed data and patches
all DB path references so tests never touch production data.
"""
import sqlite3
import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import patch

from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.schema import UNIFIED_SCHEMA, REALPAGE_SCHEMA


# ── Seed data ──────────────────────────────────────────────────────────

TEST_PROPERTY_ID = "test_prop"
TEST_SITE_ID = "9999999"
TEST_PMC_ID = "999"
SNAPSHOT_DATE = "2026-02-14"


def _seed_unified(db_path: Path):
    """Populate unified.db with minimal test data."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(UNIFIED_SCHEMA)

    # Add owner_group column (added at runtime by sync scripts, not in base schema)
    try:
        conn.execute("ALTER TABLE unified_properties ADD COLUMN owner_group TEXT DEFAULT 'other'")
    except Exception:
        pass  # already exists

    # Property
    conn.execute("""
        INSERT INTO unified_properties
            (unified_property_id, pms_source, pms_property_id, name, address, city, state, zip, total_units, owner_group)
        VALUES (?, 'realpage', ?, 'Test Property', '123 Main St', 'Austin', 'TX', '78701', 10, 'test_group')
    """, (TEST_PROPERTY_ID, TEST_SITE_ID))

    # Units — 8 occupied, 1 vacant, 1 down
    for i in range(1, 11):
        status = "occupied" if i <= 8 else ("vacant" if i == 9 else "down")
        conn.execute("""
            INSERT INTO unified_units
                (unified_property_id, pms_source, pms_unit_id, unit_number, floorplan, bedrooms, bathrooms,
                 square_feet, market_rent, status, days_vacant)
            VALUES (?, 'realpage', ?, ?, '1BR', 1, 1.0, 750, 1500.0, ?, ?)
        """, (TEST_PROPERTY_ID, str(100 + i), str(100 + i), status, 0 if status == "occupied" else 30))

    # Residents for occupied units
    for i in range(1, 9):
        conn.execute("""
            INSERT INTO unified_residents
                (unified_property_id, pms_source, pms_resident_id, pms_unit_id, unit_number,
                 first_name, last_name, status, lease_start, lease_end, current_rent)
            VALUES (?, 'realpage', ?, ?, ?, 'Test', 'Resident', 'current', '01/01/2025', '12/31/2025', 1450.0)
        """, (TEST_PROPERTY_ID, str(200 + i), str(100 + i), str(100 + i)))

    # Occupancy metrics
    conn.execute("""
        INSERT INTO unified_occupancy_metrics
            (unified_property_id, snapshot_date, total_units, occupied_units, vacant_units,
             leased_units, preleased_vacant, notice_units, model_units, down_units,
             vacant_ready, vacant_not_ready, physical_occupancy, leased_percentage,
             exposure_30_days, exposure_60_days)
        VALUES (?, ?, 10, 8, 1, 9, 1, 0, 0, 1, 1, 0, 80.0, 90.0, 1, 2)
    """, (TEST_PROPERTY_ID, SNAPSHOT_DATE))

    # Pricing metrics
    conn.execute("""
        INSERT INTO unified_pricing_metrics
            (unified_property_id, snapshot_date, floorplan, floorplan_name, unit_count,
             bedrooms, bathrooms, avg_square_feet, in_place_rent, in_place_per_sf,
             asking_rent, asking_per_sf, rent_growth)
        VALUES (?, ?, '1BR', 'One Bedroom', 10, 1, 1.0, 750, 1450.0, 1.93, 1500.0, 2.00, 3.4)
    """, (TEST_PROPERTY_ID, SNAPSHOT_DATE))

    # Risk scores
    conn.execute("""
        INSERT INTO unified_risk_scores
            (unified_property_id, snapshot_date, total_scored, notice_count, at_risk_total,
             avg_churn_score, median_churn_score, avg_delinquency_score, median_delinquency_score,
             churn_high_count, churn_medium_count, churn_low_count,
             delinq_high_count, delinq_medium_count, delinq_low_count)
        VALUES (?, ?, 8, 0, 8, 0.72, 0.75, 0.81, 0.85, 1, 3, 4, 0, 2, 6)
    """, (TEST_PROPERTY_ID, SNAPSHOT_DATE))

    # Leasing metrics
    conn.execute("""
        INSERT INTO unified_leasing_metrics
            (unified_property_id, snapshot_date, period,
             move_ins, move_outs, net_move_ins, lease_expirations, renewals, renewal_percentage,
             leads, tours, applications, lease_signs)
        VALUES (?, ?, 'current_month', 2, 1, 1, 3, 2, 66.7, 10, 5, 3, 2)
    """, (TEST_PROPERTY_ID, SNAPSHOT_DATE))

    # Unified delinquency table (created by sync_realpage_to_unified, not in UNIFIED_SCHEMA)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS unified_delinquency (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unified_property_id TEXT NOT NULL,
            report_date TEXT,
            unit_number TEXT,
            resident_name TEXT,
            status TEXT,
            current_balance REAL,
            balance_0_30 REAL,
            balance_31_60 REAL,
            balance_61_90 REAL,
            balance_over_90 REAL,
            prepaid REAL,
            total_delinquent REAL,
            net_balance REAL,
            is_eviction INTEGER DEFAULT 0,
            eviction_balance REAL DEFAULT 0,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        INSERT INTO unified_delinquency
            (unified_property_id, report_date, unit_number, resident_name, status,
             current_balance, balance_0_30, balance_31_60, balance_over_90,
             prepaid, total_delinquent, net_balance)
        VALUES (?, ?, '101', 'REDACTED', 'Current resident',
                100.0, 100.0, 50.0, 0.0, 0.0, 250.0, 250.0)
    """, (TEST_PROPERTY_ID, SNAPSHOT_DATE))
    conn.execute("""
        INSERT INTO unified_delinquency
            (unified_property_id, report_date, unit_number, resident_name, status,
             current_balance, balance_0_30, balance_31_60, balance_over_90,
             prepaid, total_delinquent, net_balance)
        VALUES (?, ?, '109', 'REDACTED', 'Former resident',
                0.0, 0.0, 200.0, 300.0, 0.0, 500.0, 500.0)
    """, (TEST_PROPERTY_ID, SNAPSHOT_DATE))

    conn.commit()
    conn.close()


def _seed_realpage(db_path: Path):
    """Populate realpage_raw.db with minimal test data."""
    conn = sqlite3.connect(str(db_path))
    conn.executescript(REALPAGE_SCHEMA)

    # Units
    for i in range(1, 11):
        vacant = "False" if i <= 8 else "True"
        available = "False" if i <= 8 else "True"
        conn.execute("""
            INSERT INTO realpage_units
                (pmc_id, site_id, unit_id, unit_number, floorplan_id, floorplan_name,
                 bedrooms, bathrooms, rentable_sqft, market_rent, vacant, available, unit_status)
            VALUES (?, ?, ?, ?, '1BR', 'One Bedroom', 1, 1.0, 750, 1500.0, ?, ?, 'Active')
        """, (TEST_PMC_ID, TEST_SITE_ID, str(100 + i), str(100 + i), vacant, available))

    # Residents
    for i in range(1, 9):
        conn.execute("""
            INSERT INTO realpage_residents
                (pmc_id, site_id, resident_id, unit_id, unit_number,
                 first_name, last_name, lease_status, begin_date, end_date, rent, balance)
            VALUES (?, ?, ?, ?, ?, 'Test', 'Resident', 'Current', '01/01/2025', '12/31/2025', 1450.0, 0)
        """, (TEST_PMC_ID, TEST_SITE_ID, str(200 + i), str(100 + i), str(100 + i)))

    # Leases — mix of types for renewal/tradeout testing
    for i in range(1, 9):
        lease_type = "Renewal" if i <= 4 else "First(Lease)"
        status_text = "Current" if i <= 6 else "Current - Future"
        conn.execute("""
            INSERT INTO realpage_leases
                (pmc_id, site_id, lease_id, resident_id, unit_id, unit_number,
                 lease_start_date, lease_end_date, rent_amount, status_text, type_text, move_in_date)
            VALUES (?, ?, ?, ?, ?, ?, '01/01/2026', '12/31/2026', ?, ?, ?, '01/01/2026')
        """, (TEST_PMC_ID, TEST_SITE_ID, str(300 + i), str(200 + i),
              str(100 + i), str(100 + i), 1450.0 + i * 10, status_text, lease_type))

    # Prior leases for trade-out testing (Former status on same units 5-8)
    for i in range(5, 9):
        conn.execute("""
            INSERT INTO realpage_leases
                (pmc_id, site_id, lease_id, resident_id, unit_id, unit_number,
                 lease_start_date, lease_end_date, rent_amount, status_text, type_text, move_in_date)
            VALUES (?, ?, ?, ?, ?, ?, '01/01/2025', '12/31/2025', ?, 'Former', 'First(Lease)', '01/01/2025')
        """, (TEST_PMC_ID, TEST_SITE_ID, str(400 + i), str(900 + i),
              str(100 + i), str(100 + i), 1400.0 + i * 5))

    # Box score
    conn.execute("""
        INSERT INTO realpage_box_score
            (property_id, property_name, report_date, floorplan, total_units, vacant_units,
             vacant_not_leased, vacant_leased, occupied_units, occupied_no_notice,
             occupied_on_notice, model_units, down_units, avg_sqft, avg_market_rent,
             avg_actual_rent, occupancy_pct, leased_pct)
        VALUES (?, 'Test Property', ?, '1BR', 10, 1, 1, 0, 8, 8, 0, 0, 1, 750, 1500.0,
                1450.0, 80.0, 90.0)
    """, (TEST_SITE_ID, SNAPSHOT_DATE))

    # Rent roll
    for i in range(1, 11):
        status = "Occupied" if i <= 8 else ("Vacant" if i == 9 else "Admin/Down")
        conn.execute("""
            INSERT INTO realpage_rent_roll
                (property_id, report_date, unit_number, floorplan, status, sqft,
                 market_rent, actual_rent, lease_start, lease_end)
            VALUES (?, ?, ?, '1BR', ?, 750, 1500.0, ?, '01/01/2025', '12/31/2025')
        """, (TEST_SITE_ID, SNAPSHOT_DATE, str(100 + i), status, 1450.0 if i <= 8 else 0))

    # Delinquency
    conn.execute("""
        INSERT INTO realpage_delinquency
            (property_id, property_name, report_date, unit_number, status,
             total_delinquent, prepaid, net_balance,
             current_balance, balance_0_30, balance_31_60, balance_over_90)
        VALUES (?, 'Test Property', ?, '101', 'Current resident',
                250.0, 0.0, 250.0, 100.0, 100.0, 50.0, 0.0)
    """, (TEST_SITE_ID, SNAPSHOT_DATE))
    conn.execute("""
        INSERT INTO realpage_delinquency
            (property_id, property_name, report_date, unit_number, status,
             total_delinquent, prepaid, net_balance,
             current_balance, balance_0_30, balance_31_60, balance_over_90)
        VALUES (?, 'Test Property', ?, '109', 'Former resident',
                500.0, 0.0, 500.0, 0.0, 0.0, 200.0, 300.0)
    """, (TEST_SITE_ID, SNAPSHOT_DATE))

    conn.commit()
    conn.close()


# ── Fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def test_db_dir():
    """Create a temporary directory with seeded test databases."""
    with tempfile.TemporaryDirectory(prefix="ownerdash_test_") as tmpdir:
        tmpdir_path = Path(tmpdir)

        unified_path = tmpdir_path / "unified.db"
        realpage_path = tmpdir_path / "realpage_raw.db"
        yardi_path = tmpdir_path / "yardi_raw.db"

        _seed_unified(unified_path)
        _seed_realpage(realpage_path)

        # Create empty yardi DB
        conn = sqlite3.connect(str(yardi_path))
        from app.db.schema import YARDI_SCHEMA
        conn.executescript(YARDI_SCHEMA)
        conn.commit()
        conn.close()

        # Also create cache dirs that services expect
        (tmpdir_path / "google_places_cache.json").write_text("{}")
        (tmpdir_path / "google_reviews_cache.json").write_text("{}")

        yield tmpdir_path


@pytest.fixture(scope="session")
def _patch_db_paths(test_db_dir):
    """
    Intercept sqlite3.connect to redirect ANY reference to production DBs
    to our test databases. This covers both schema.py constants AND inline
    Path(__file__) / ... / "unified.db" references throughout the codebase.
    """
    import app.db.schema as schema_mod

    unified = str(test_db_dir / "unified.db")
    realpage = str(test_db_dir / "realpage_raw.db")
    yardi = str(test_db_dir / "yardi_raw.db")

    # Patch schema module constants
    patches = [
        patch.object(schema_mod, "DB_DIR", test_db_dir),
        patch.object(schema_mod, "UNIFIED_DB_PATH", test_db_dir / "unified.db"),
        patch.object(schema_mod, "REALPAGE_DB_PATH", test_db_dir / "realpage_raw.db"),
        patch.object(schema_mod, "YARDI_DB_PATH", test_db_dir / "yardi_raw.db"),
    ]
    for p in patches:
        p.start()

    # Intercept sqlite3.connect to redirect production DB paths
    _original_connect = sqlite3.connect

    def _redirected_connect(database, *args, **kwargs):
        db_str = str(database)
        if "unified.db" in db_str:
            database = unified
        elif "realpage_raw.db" in db_str:
            database = realpage
        elif "yardi_raw.db" in db_str:
            database = yardi
        return _original_connect(database, *args, **kwargs)

    sqlite3_patch = patch("sqlite3.connect", side_effect=_redirected_connect)
    sqlite3_patch.start()

    yield test_db_dir

    sqlite3_patch.stop()
    for p in patches:
        p.stop()


@pytest.fixture(scope="session")
def _patch_property_config(_patch_db_paths):
    """
    Ensure the test property is discoverable by property config lookups.
    Patches ALL_PROPERTIES and the get_pms_config helper.
    """
    from app.models.unified import PMSSource, PMSConfig
    from types import SimpleNamespace

    test_pms_config = PMSConfig(
        pms_type=PMSSource.REALPAGE,
        property_id=TEST_PROPERTY_ID,
        pms_property_id=TEST_SITE_ID,
        realpage_pmcid=TEST_PMC_ID,
        realpage_siteid=TEST_SITE_ID,
        realpage_licensekey="test_key",
    )

    test_property = SimpleNamespace(
        name="Test Property",
        unified_id=TEST_PROPERTY_ID,
        pms_config=test_pms_config,
        aln_id=None,
    )

    # Patch property_config module
    import app.property_config.properties as prop_mod
    original_all = prop_mod.ALL_PROPERTIES.copy() if hasattr(prop_mod, "ALL_PROPERTIES") else {}
    original_get_pms = prop_mod.get_pms_config

    prop_mod.ALL_PROPERTIES[TEST_PROPERTY_ID] = test_property

    original_get_pms_config = prop_mod.get_pms_config

    def patched_get_pms_config(property_id):
        if property_id == TEST_PROPERTY_ID:
            return test_pms_config
        return original_get_pms_config(property_id)

    prop_mod.get_pms_config = patched_get_pms_config

    yield

    # Cleanup
    prop_mod.ALL_PROPERTIES.pop(TEST_PROPERTY_ID, None)
    prop_mod.get_pms_config = original_get_pms


@pytest.fixture
async def client(_patch_property_config):
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
