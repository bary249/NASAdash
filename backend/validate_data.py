#!/usr/bin/env python3
"""
Post-refresh data validation — ensures all critical tables have fresh data.
Run after refresh_all.py and before push_to_deployed.py.
Exit code 0 = all checks pass, 1 = critical failures.
"""
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timedelta

SCRIPT_DIR = Path(__file__).parent
RAW_DB = SCRIPT_DIR / "app" / "db" / "data" / "realpage_raw.db"
UNIFIED_DB = SCRIPT_DIR / "app" / "db" / "data" / "unified.db"

CRITICAL_TABLES = {
    "realpage_raw.db": [
        ("realpage_box_score", 10),
        ("realpage_rent_roll", 100),
        ("realpage_activity", 100),
        ("realpage_delinquency", 10),
        ("realpage_projected_occupancy", 10),
        ("realpage_lease_expiration_renewal", 10),
        ("realpage_monthly_transaction_detail", 10),
        ("realpage_make_ready", 1),
        ("realpage_closed_make_ready", 1),
        ("realpage_advertising_source", 10),
        ("realpage_lost_rent_summary", 1),
        ("realpage_move_out_reasons", 1),
    ],
    "unified.db": [
        ("unified_properties", 5),
        ("unified_occupancy_metrics", 5),
        ("unified_pricing_metrics", 10),
        ("unified_units", 100),
        ("unified_residents", 100),
    ],
}

# PHH properties that must have marketing + move-out data
PHH_SITES = {
    "5472172": "Nexus East",
    "5536211": "Parkside",
}


def check_table(conn, table, min_rows):
    """Check table exists and has minimum rows."""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        return count, count >= min_rows
    except Exception:
        return 0, False


def check_phh_data(conn):
    """Verify PHH-specific data (advertising_source + move_out_reasons)."""
    issues = []
    cursor = conn.cursor()

    for site_id, name in PHH_SITES.items():
        # Check advertising_source has timeframe-tagged data
        try:
            cursor.execute(
                "SELECT COUNT(DISTINCT timeframe_tag) FROM realpage_advertising_source WHERE property_id = ?",
                (site_id,),
            )
            tf_count = cursor.fetchone()[0]
            if tf_count < 2:
                issues.append(f"{name}: only {tf_count} timeframe tags in advertising_source (expected ≥2)")
        except Exception as e:
            issues.append(f"{name}: advertising_source check failed: {e}")

        # Check move_out_reasons
        try:
            cursor.execute(
                "SELECT COUNT(DISTINCT resident_type) FROM realpage_move_out_reasons WHERE property_id = ?",
                (site_id,),
            )
            rt_count = cursor.fetchone()[0]
            if rt_count < 1:
                issues.append(f"{name}: no move_out_reasons data")
        except Exception as e:
            issues.append(f"{name}: move_out_reasons check failed: {e}")

    return issues


def main():
    print("=" * 60)
    print("  DATA VALIDATION")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 60)

    failures = []
    warnings = []

    # Check raw DB
    if not RAW_DB.exists():
        print("  ❌ realpage_raw.db not found!")
        sys.exit(1)

    print(f"\n── realpage_raw.db ({RAW_DB.stat().st_size / 1024 / 1024:.1f} MB) ──")
    conn = sqlite3.connect(str(RAW_DB))
    for table, min_rows in CRITICAL_TABLES["realpage_raw.db"]:
        count, ok = check_table(conn, table, min_rows)
        icon = "✅" if ok else "❌"
        print(f"  {icon} {table}: {count} rows (min {min_rows})")
        if not ok:
            failures.append(f"{table}: {count} rows < {min_rows}")

    # PHH-specific checks
    phh_issues = check_phh_data(conn)
    for issue in phh_issues:
        print(f"  ⚠️  {issue}")
        warnings.append(issue)
    conn.close()

    # Check unified DB
    if not UNIFIED_DB.exists():
        print("  ❌ unified.db not found!")
        sys.exit(1)

    print(f"\n── unified.db ({UNIFIED_DB.stat().st_size / 1024 / 1024:.1f} MB) ──")
    conn = sqlite3.connect(str(UNIFIED_DB))
    for table, min_rows in CRITICAL_TABLES["unified.db"]:
        count, ok = check_table(conn, table, min_rows)
        icon = "✅" if ok else "❌"
        print(f"  {icon} {table}: {count} rows (min {min_rows})")
        if not ok:
            failures.append(f"{table}: {count} rows < {min_rows}")
    conn.close()

    # Summary
    print(f"\n{'=' * 60}")
    if failures:
        print(f"  ❌ {len(failures)} CRITICAL FAILURES:")
        for f in failures:
            print(f"     • {f}")
    if warnings:
        print(f"  ⚠️  {len(warnings)} WARNINGS:")
        for w in warnings:
            print(f"     • {w}")
    if not failures and not warnings:
        print("  ✅ ALL CHECKS PASSED")
    elif not failures:
        print("  ✅ No critical failures (warnings only)")
    print("=" * 60)

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
