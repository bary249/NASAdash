#!/usr/bin/env python3
"""
Download ALL missing RealPage reports for all Kairoi properties.

Workflow:
1. Check which properties/reports are missing from realpage_raw.db
2. Create report instances for all missing combinations
3. Wait for reports to generate
4. Scan file IDs to find and download them
5. Parse and import to realpage_raw.db
6. Sync to unified.db
"""

import json
import time
import httpx
import sqlite3
import pandas as pd
import io
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "app/db/data/realpage_raw.db"
BASE_URL = "https://reportingapi.realpage.com/v1"

# Load token
with open(SCRIPT_DIR / "realpage_token.json") as f:
    TOKEN = json.load(f)["access_token"]
    if TOKEN.startswith("Bearer "):
        TOKEN = TOKEN[7:]

# Load report definitions
with open(SCRIPT_DIR / "report_definitions.json") as f:
    DEFINITIONS = json.load(f)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "accept": "application/json, text/plain, */*",
    "origin": "https://www.realpage.com",
    "referer": "https://www.realpage.com/",
}

# All 6 report types
REPORT_TYPES = {
    "box_score": DEFINITIONS["reports"]["box_score"],
    "rent_roll": DEFINITIONS["reports"]["rent_roll"],
    "delinquency": DEFINITIONS["reports"]["delinquency"],
    "activity_report": DEFINITIONS["reports"]["activity_report"],
    "monthly_activity_summary": DEFINITIONS["reports"]["monthly_activity_summary"],
    "lease_expiration": DEFINITIONS["reports"]["lease_expiration"],
}

# All properties with their RealPage IDs
ALL_PROPERTIES = {}
for key, prop in DEFINITIONS["properties"].items():
    ALL_PROPERTIES[prop["propertyId"]] = {
        "key": key,
        "name": prop["propertyName"],
        "detail": prop,
    }


def check_existing_data():
    """Check what data already exists in realpage_raw.db."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    table_map = {
        "box_score": "realpage_box_score",
        "rent_roll": "realpage_rent_roll",
        "delinquency": "realpage_delinquency",
        "activity_report": "realpage_activity",
        "monthly_activity_summary": "realpage_monthly_summary",
        "lease_expiration": "realpage_lease_expirations",
    }

    props_by_type = {}
    for rtype, tbl in table_map.items():
        try:
            c.execute(f"SELECT DISTINCT property_id FROM {tbl}")
            props_by_type[rtype] = {r[0] for r in c.fetchall()}
        except Exception:
            props_by_type[rtype] = set()

    conn.close()

    existing = {}
    for pid in ALL_PROPERTIES:
        existing[pid] = {rtype: pid in pset for rtype, pset in props_by_type.items()}

    return existing


def build_payload(report_def: dict, property_detail: dict) -> dict:
    """Build the API payload for a report."""
    now = datetime.now()
    dates = {
        "start_date": f"01/01/{now.year}",
        "end_date": now.strftime("%m/%d/%Y"),
        "as_of_date": now.strftime("%m/%d/%Y"),
        "start_month": now.strftime("%m/%Y"),
        "end_month": now.strftime("%m/%Y"),
        "fiscal_period": now.strftime("%m%Y"),
    }

    parameters = []
    for param in report_def["parameters"]:
        value = param["value"]
        if value == "{{start_date}}":
            value = dates["start_date"]
        elif value == "{{end_date}}":
            value = dates["end_date"]
        elif value == "{{as_of_date}}":
            value = dates["as_of_date"]
        elif value == "{{start_month}}":
            value = dates["start_month"]
        elif value == "{{end_month}}":
            value = dates["end_month"]
        elif value == "{{fiscal_period}}":
            value = dates["fiscal_period"]

        parameters.append({"name": param["name"], "label": value, "value": value})

    return {
        "reportKey": report_def["report_key"],
        "sourceId": "OS",
        "scheduledType": 1,
        "scheduledDate": "",
        "scheduledTime": "",
        "scheduleDateTime": None,
        "reportFormat": report_def["formats"].get("excel", "3"),
        "reportFormatName": "Excel",
        "emaiTo": "",
        "properties": [property_detail["propertyId"]],
        "propertyDetailList": [property_detail],
        "parameters": parameters,
        "users": [],
        "cloudServiceAccountId": None,
    }


def create_instance(report_type: str, report_def: dict, property_detail: dict) -> Optional[str]:
    """Create a report instance. Returns instance ID."""
    url = f"{BASE_URL}/reports/{report_def['report_id']}/report-instances"
    payload = build_payload(report_def, property_detail)

    try:
        with httpx.Client(timeout=30, verify=False) as client:
            resp = client.post(url, headers=HEADERS, json=payload)
            if resp.status_code in (200, 201):
                data = resp.json()
                return data.get("instanceId")
            else:
                print(f"      ✗ Error {resp.status_code}: {resp.text[:100]}")
                return None
    except Exception as e:
        print(f"      ✗ Exception: {e}")
        return None


def try_download_file(file_id: int) -> Optional[bytes]:
    """Try to download a file by ID."""
    url = f"{BASE_URL}/reports/4043/report-instances/0-0-0/files"
    payload = {
        "reportId": 4043,
        "parameters": f"reportKey=A6F61299-E960-4235-9DC2-44D2C2EF4F99&sourceId=OS&fileID={file_id}&View=2",
        "fileId": str(file_id),
        "propertyName": "scan",
    }
    try:
        with httpx.Client(timeout=30, verify=False) as client:
            resp = client.post(url, headers=HEADERS, json=payload)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return resp.content
    except Exception:
        pass
    return None


def identify_report(content: bytes) -> Dict:
    """Identify report type and property from content."""
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None)
        rows = []
        for _, row in df.iterrows():
            clean = [str(x) for x in row.dropna().tolist() if str(x) != "nan"]
            if clean:
                rows.append(clean)
            if len(rows) >= 8:
                break

        if not rows:
            return {"type": "unknown", "property": None}

        text = " ".join([" ".join(r) for r in rows[:5]]).upper()

        rtype = "unknown"
        if "BOXSCORE" in text or "BOX SCORE" in text:
            rtype = "box_score"
        elif "RENT ROLL" in text or "RENTROLL" in text:
            rtype = "rent_roll"
        elif "DELINQUENT" in text or "PREPAID" in text:
            rtype = "delinquency"
        elif "MONTHLY ACTIVITY SUMMARY" in text:
            rtype = "monthly_summary"
        elif "LEASE EXPIRATION" in text:
            rtype = "lease_expiration"
        elif "ACTIVITY REPORT" in text:
            rtype = "activity_report"

        # Extract property name
        prop = None
        for row in rows:
            row_text = " ".join(row)
            if "KAIROI" in row_text.upper() or "MANAGEMENT" in row_text.upper():
                parts = row_text.split("-")
                if len(parts) > 1:
                    prop = parts[-1].strip()
                    break

        return {"type": rtype, "property": prop}

    except Exception:
        return {"type": "unknown", "property": None}


def normalize(name: str) -> str:
    if not name:
        return ""
    return name.lower().replace(" ", "").replace("-", "").replace("_", "").replace("the", "")


def scan_and_match(needed: list, start_id: int, max_scan: int = 600) -> list:
    """Parallel scan file IDs and match to needed reports."""
    print(f"\n{'='*60}")
    print(f"  SCANNING FILE IDS from {start_id}")
    print(f"{'='*60}")

    remaining = {i: item for i, item in enumerate(needed)}
    batch_size = 10
    consecutive_empty = 0
    found_count = 0

    for batch_start in range(0, max_scan, batch_size):
        if not remaining:
            print("  All reports found!")
            break

        batch_ids = [start_id + batch_start + j for j in range(batch_size)]
        sys.stdout.write(f"  {batch_ids[0]}-{batch_ids[-1]}...")
        sys.stdout.flush()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(try_download_file, fid): fid for fid in batch_ids}
            results = {}
            for f in as_completed(futures):
                fid, content = f.result() if isinstance(f.result(), tuple) else (futures[f], f.result())
                if content:
                    results[fid] = content

        if not results:
            consecutive_empty += 1
            print(" empty")
            if consecutive_empty > 30:
                print("  ⚠ 300+ empty IDs, stopping scan")
                break
            continue

        consecutive_empty = 0
        hits = 0

        for fid in sorted(results.keys()):
            content = results[fid]
            ident = identify_report(content)
            file_prop = normalize(ident.get("property") or "")
            file_type = ident.get("type", "")

            for idx, item in list(remaining.items()):
                target_prop = normalize(item["prop_name"])
                target_type = item["report_type"]

                if file_prop and target_prop and (target_prop in file_prop or file_prop in target_prop) and file_type == target_type:
                    item["file_id"] = fid
                    item["content"] = content
                    hits += 1
                    found_count += 1
                    del remaining[idx]
                    print(f" ✓ {fid}: {item['prop_name']} / {target_type}")
                    break
            else:
                # Didn't match - check if it matches ANY remaining
                if file_type != "unknown":
                    # Try looser matching
                    for idx, item in list(remaining.items()):
                        if item["report_type"] == file_type:
                            # Check property by ID in content
                            target_pid = item["prop_id"]
                            # Just log it
                            pass

        if hits == 0:
            types_found = set()
            for c in results.values():
                i = identify_report(c)
                types_found.add(f"{i.get('type','?')}/{i.get('property','?')}")
            print(f" {len(results)} files (other: {', '.join(list(types_found)[:3])})")

    print(f"\n  Found {found_count} / {len(needed)} reports")
    return needed


def import_downloaded(needed: list):
    """Import all downloaded reports."""
    from report_parsers import parse_report
    from import_reports import (
        import_box_score, import_delinquency, import_rent_roll,
        import_monthly_summary, import_lease_expiration, import_activity,
        init_report_tables,
    )

    conn = sqlite3.connect(DB_PATH)
    init_report_tables(conn)

    IMPORTERS = {
        "box_score": import_box_score,
        "delinquency": import_delinquency,
        "rent_roll": import_rent_roll,
        "monthly_summary": import_monthly_summary,
        "lease_expiration": import_lease_expiration,
        "activity_report": import_activity,
        "activity": import_activity,
    }

    total_imported = 0
    results = {}

    for item in needed:
        if not item.get("content"):
            continue

        prop = item["prop_name"]
        rtype = item["report_type"]
        fid = item["file_id"]

        temp_path = SCRIPT_DIR / f"temp_{fid}.xlsx"
        temp_path.write_bytes(item["content"])

        try:
            result = parse_report(str(temp_path))
            records = result.get("records", [])
            parsed_type = result.get("report_type", rtype)

            if records:
                for r in records:
                    r["property_id"] = item["prop_id"]

                importer = IMPORTERS.get(parsed_type)
                count = 0
                if importer:
                    count = importer(conn, records, str(temp_path), str(fid))
                else:
                    print(f"  ⚠ No importer for type: {parsed_type}")

                if count > 0:
                    print(f"  ✓ {prop} / {parsed_type}: {count} records")
                    total_imported += count
                    results.setdefault(prop, {})[parsed_type] = count
                else:
                    print(f"  ⚠ {prop} / {parsed_type}: parsed {len(records)} but 0 imported")
            else:
                print(f"  - {prop} / {rtype}: no records parsed (detected as {parsed_type})")
        except Exception as e:
            print(f"  ✗ {prop} / {rtype}: {e}")
        finally:
            temp_path.unlink(missing_ok=True)

    conn.close()
    return total_imported, results


def main():
    print("=" * 60)
    print("  COMPLETE DATA DOWNLOAD FOR ALL KAIROI PROPERTIES")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 60)

    # Step 1: Check what's missing
    print("\n📋 Checking existing data...")
    existing = check_existing_data()

    needed = []
    for pid, prop_info in ALL_PROPERTIES.items():
        prop_existing = existing.get(pid, {})
        for rtype, rdef in REPORT_TYPES.items():
            if not prop_existing.get(rtype, False):
                needed.append({
                    "prop_id": pid,
                    "prop_name": prop_info["name"],
                    "prop_detail": prop_info["detail"],
                    "report_type": rtype,
                    "report_def": rdef,
                    "instance_id": None,
                    "file_id": None,
                    "content": None,
                })

    if not needed:
        print("✅ All properties have all report types!")
        return

    print(f"\n📊 Missing {len(needed)} reports across {len(set(n['prop_id'] for n in needed))} properties:")
    by_prop = {}
    for n in needed:
        by_prop.setdefault(n["prop_name"], []).append(n["report_type"])
    for prop, types in sorted(by_prop.items()):
        print(f"  {prop}: {', '.join(types)}")

    # Step 2: Create instances
    print(f"\n{'='*60}")
    print("  STEP 1: CREATING REPORT INSTANCES")
    print(f"{'='*60}")

    created = 0
    for item in needed:
        prop = item["prop_name"]
        rtype = item["report_type"]
        sys.stdout.write(f"  {prop} / {rtype}...")
        sys.stdout.flush()

        instance_id = create_instance(rtype, item["report_def"], item["prop_detail"])
        if instance_id:
            item["instance_id"] = instance_id
            created += 1
            print(f" ✓ {instance_id}")
        else:
            print(" ✗ failed")

    print(f"\n  Created {created} / {len(needed)} instances")

    if created == 0:
        print("❌ No instances created. Token may be expired.")
        return

    # Step 3: Wait for generation
    wait_secs = 45
    print(f"\n⏳ Waiting {wait_secs}s for reports to generate...")
    for i in range(wait_secs, 0, -5):
        sys.stdout.write(f"\r  {i}s remaining...")
        sys.stdout.flush()
        time.sleep(5)
    print("\r  Done waiting!          ")

    # Step 4: Find the starting file ID by probing
    # Reports get sequential file IDs - probe to find current range
    print("\n🔍 Finding current file ID range...")
    start_id = None
    # Try to find where new files start by probing common ranges
    for probe in range(8880000, 9200000, 10000):
        content = try_download_file(probe)
        if content:
            # Binary search backward to find the start
            start_id = probe - 500
            print(f"  Found files near {probe}, starting scan at {start_id}")
            break
    
    if not start_id:
        # If no files found in known range, use instance creation as anchor
        # The file IDs should be near the instance IDs
        print("  No files found in known range. Trying broader scan...")
        # Try a wider range
        for probe in range(9200000, 9500000, 20000):
            content = try_download_file(probe)
            if content:
                start_id = probe - 500
                print(f"  Found files near {probe}, starting scan at {start_id}")
                break
    
    if not start_id:
        print("  ⚠ Could not find file range. Using instance-based estimate.")
        # Parse the first instance ID as a numeric hint
        first_inst = next((n["instance_id"] for n in needed if n.get("instance_id")), None)
        if first_inst:
            # Instance IDs are often close to file IDs
            start_id = 8880700
        else:
            start_id = 8880700
        print(f"  Defaulting to scan from {start_id}")

    # Scan and match
    needed = scan_and_match(needed, start_id, max_scan=2000)

    # Step 5: Import
    downloaded = [n for n in needed if n.get("content")]
    if not downloaded:
        print("\n❌ No files downloaded. Reports may not have generated yet.")
        print("   Try running again in a minute.")
        return

    print(f"\n{'='*60}")
    print(f"  STEP 2: IMPORTING {len(downloaded)} REPORTS")
    print(f"{'='*60}")

    total, results = import_downloaded(needed)

    # Step 6: Sync
    print(f"\n{'='*60}")
    print("  STEP 3: SYNCING TO unified.db")
    print(f"{'='*60}")

    import subprocess
    subprocess.run(
        [sys.executable, "-m", "app.db.sync_realpage_to_unified"],
        cwd=str(SCRIPT_DIR),
    )

    # Summary
    print(f"\n{'='*60}")
    print("  FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"  Instances created: {created}")
    print(f"  Files downloaded:  {len(downloaded)}")
    print(f"  Records imported:  {total}")
    print(f"\n  Per property:")
    for prop, types in sorted(results.items()):
        details = ", ".join(f"{t}: {c}" for t, c in types.items())
        print(f"    {prop}: {details}")

    still_missing = [n for n in needed if not n.get("content")]
    if still_missing:
        print(f"\n  ⚠ Still missing {len(still_missing)} reports:")
        for n in still_missing:
            print(f"    {n['prop_name']} / {n['report_type']}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", nargs="+", help="Only download for these property site IDs")
    parser.add_argument("--only-reports", nargs="+", help="Only download these report types")
    args = parser.parse_args()

    if args.target:
        target_set = set(args.target)
        ALL_PROPERTIES = {k: v for k, v in ALL_PROPERTIES.items() if k in target_set}
        print(f"Filtered to {len(ALL_PROPERTIES)} properties")

    if args.only_reports:
        REPORT_TYPES = {k: v for k, v in REPORT_TYPES.items() if k in args.only_reports}
        print(f"Filtered to report types: {list(REPORT_TYPES.keys())}")

    main()
