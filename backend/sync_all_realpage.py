#!/usr/bin/env python3
"""
Complete RealPage Data Pipeline
================================
1. Download reports from RealPage API for all properties
2. Sync data from realpage_raw.db to unified.db
3. Data automatically available to UI via FastAPI

Usage:
    python sync_all_realpage.py
    python sync_all_realpage.py --properties "Kalaco" "Block 44"  # Specific properties
    python sync_all_realpage.py --skip-download  # Only sync existing data
"""

import subprocess
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
DEFINITIONS_FILE = SCRIPT_DIR / "report_definitions.json"

# Load all properties from definitions
with open(DEFINITIONS_FILE) as f:
    DEFINITIONS = json.load(f)
    ALL_PROPERTIES = [prop["propertyName"] for prop in DEFINITIONS.get("properties", {}).values()]


def print_header(title: str):
    """Print a formatted header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def download_reports_for_property(property_name: str) -> dict:
    """Download reports for a single property with live output."""
    print(f"\n📥 Downloading reports for: {property_name}")
    sys.stdout.flush()

    try:
        proc = subprocess.Popen(
            ["python3", "-u", "batch_report_downloader.py", "--property", property_name],
            cwd=SCRIPT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        output_lines = []
        for line in proc.stdout:
            line = line.rstrip()
            output_lines.append(line)
            print(f"    {line}", flush=True)

        proc.wait(timeout=300)
        output = "\n".join(output_lines)
        success = "FINAL SUMMARY" in output

        # Extract record counts
        records = 0
        for line in output_lines:
            if "Total imported:" in line:
                try:
                    records = int(line.split("Total imported:")[-1].split("records")[0].strip())
                except:
                    pass

        status = "✅" if success else "⚠️"
        print(f"  {status} {property_name}: {records} records imported", flush=True)

        return {
            "property": property_name,
            "success": success,
            "records": records,
            "output": output
        }

    except subprocess.TimeoutExpired:
        proc.kill()
        print(f"  ❌ Timeout downloading reports for {property_name}")
        return {"property": property_name, "success": False, "records": 0, "error": "timeout"}
    except Exception as e:
        print(f"  ❌ Error downloading reports for {property_name}: {e}")
        return {"property": property_name, "success": False, "records": 0, "error": str(e)}


def download_all_reports(properties: list = None) -> list:
    """Download reports for all (or specified) properties."""
    print_header("STEP 1: DOWNLOADING REPORTS FROM REALPAGE API")

    properties = properties or ALL_PROPERTIES
    print(f"\n📋 Processing {len(properties)} properties...")

    results = []
    for i, property_name in enumerate(properties, 1):
        print(f"\n[{i}/{len(properties)}] {property_name}")
        result = download_reports_for_property(property_name)
        results.append(result)

    # Summary
    successful = sum(1 for r in results if r.get("success"))
    total_records = sum(r.get("records", 0) for r in results)

    print(f"\n📊 Download Summary:")
    print(f"  Properties processed: {len(results)}")
    print(f"  Successful: {successful}")
    print(f"  Total records: {total_records}")

    return results


def sync_to_unified() -> dict:
    """Sync data from realpage_raw.db to unified.db."""
    print_header("STEP 2: SYNCING TO UNIFIED DATABASE")

    try:
        proc = subprocess.Popen(
            ["python3", "-u", "-m", "app.db.sync_realpage_to_unified"],
            cwd=SCRIPT_DIR,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True
        )

        output_lines = []
        for line in proc.stdout:
            line = line.rstrip()
            output_lines.append(line)
            print(f"  {line}", flush=True)

        proc.wait(timeout=120)
        output = "\n".join(output_lines)

        # Parse sync results
        success = "SYNC COMPLETE" in output

        # Extract counts
        counts = {}
        for line in output.split("\n"):
            if "Properties:" in line:
                try:
                    counts["properties"] = int(line.split("Properties:")[-1].strip())
                except:
                    pass
            elif "Units:" in line:
                try:
                    counts["units"] = int(line.split("Units:")[-1].strip())
                except:
                    pass
            elif "Delinquency:" in line:
                try:
                    counts["delinquency"] = int(line.split("Delinquency:")[-1].strip())
                except:
                    pass

        return {
            "success": success,
            "counts": counts,
            "output": output
        }

    except Exception as e:
        print(f"❌ Error syncing to unified: {e}")
        return {"success": False, "error": str(e)}


def verify_ui_data() -> dict:
    """Verify data is available to UI by checking unified.db."""
    print_header("STEP 3: VERIFYING DATA AVAILABILITY")

    import sqlite3

    db_path = SCRIPT_DIR / "app/db/data/unified.db"

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Check properties
        cursor.execute("SELECT COUNT(*) FROM unified_properties WHERE pms_source = 'realpage'")
        property_count = cursor.fetchone()[0]

        # Check units
        cursor.execute("SELECT COUNT(*) FROM unified_units")
        unit_count = cursor.fetchone()[0]

        # Check last update
        cursor.execute("SELECT MAX(synced_at) FROM unified_properties")
        last_sync = cursor.fetchone()[0]

        conn.close()

        print(f"✅ Unified Database Status:")
        print(f"  Properties: {property_count}")
        print(f"  Units: {unit_count}")
        print(f"  Last synced: {last_sync}")
        print(f"\n🌐 Data is now available to the UI via FastAPI!")

        return {
            "success": True,
            "properties": property_count,
            "units": unit_count,
            "last_sync": last_sync
        }

    except Exception as e:
        print(f"❌ Error verifying data: {e}")
        return {"success": False, "error": str(e)}


def main():
    """Main pipeline execution."""
    parser = argparse.ArgumentParser(
        description="Complete RealPage data pipeline: Download → Sync → UI"
    )
    parser.add_argument(
        "--properties",
        nargs="+",
        help="Specific properties to process (default: all)"
    )
    parser.add_argument(
        "--skip-download",
        action="store_true",
        help="Skip download step, only sync existing data"
    )

    args = parser.parse_args()

    start_time = datetime.now()
    print("\n" + "=" * 70)
    print("  🚀 REALPAGE COMPLETE DATA PIPELINE")
    print("=" * 70)
    print(f"  Started: {start_time.isoformat()}")

    # Step 1: Download reports
    download_results = []
    if not args.skip_download:
        download_results = download_all_reports(args.properties)
    else:
        print_header("STEP 1: DOWNLOADING REPORTS (SKIPPED)")

    # Step 2: Sync to unified
    sync_result = sync_to_unified()

    # Step 3: Verify UI availability
    verify_result = verify_ui_data()

    # Final summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print_header("PIPELINE COMPLETE")
    print(f"  Duration: {duration:.1f} seconds")

    if not args.skip_download:
        successful = sum(1 for r in download_results if r.get("success"))
        print(f"  Downloads: {successful}/{len(download_results)} successful")

    if sync_result.get("success"):
        print(f"  Sync: ✅ Success")
        counts = sync_result.get("counts", {})
        if counts:
            print(f"    - Properties: {counts.get('properties', 0)}")
            print(f"    - Units: {counts.get('units', 0)}")
            print(f"    - Delinquency: {counts.get('delinquency', 0)}")
    else:
        print(f"  Sync: ❌ Failed")

    if verify_result.get("success"):
        print(f"  UI Data: ✅ Available")
    else:
        print(f"  UI Data: ❌ Not available")

    print(f"\n✨ Complete! Data is live in your dashboard.")
    print("=" * 70)

    # Exit code based on success
    if sync_result.get("success") and verify_result.get("success"):
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
