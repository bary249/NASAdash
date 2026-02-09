#!/usr/bin/env python3
"""
Download reports from known file IDs extracted from browser curls,
parse them, import to realpage_raw.db, sync to unified.db, and report status.
"""
import json
import httpx
import sqlite3
import io
import sys
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "app/db/data/realpage_raw.db"

# Load token
with open(SCRIPT_DIR / "realpage_token.json") as f:
    TOKEN = json.load(f)["access_token"]

BASE_URL = "https://reportingapi.realpage.com/v1"

# Report ID -> report type mapping (from report_definitions.json)
REPORT_ID_MAP = {
    3906: "box_score",
    4238: "box_score",
    3837: "delinquency",
    4043: "rent_roll",
    3877: "monthly_summary",
    3838: "lease_expiration",
    4260: "activity_report",
}

# Report key mapping
REPORT_KEYS = {
    3906: "84C36518-D324-4124-9016-54E68931B5F6",
    4238: "446266C0-D572-4D8A-A6DA-310C0AE61037",
    3837: "B29B7C76-04B8-4D6C-AABC-62127F0CAE63",
    4043: "A6F61299-E960-4235-9DC2-44D2C2EF4F99",
    3877: "E41626AB-EC0F-4F6C-A6EA-D7A93909AA9B",
    3838: "89545A3A-C28A-49CC-8791-396AE71AB422",
    4260: "89A3C427-BE71-4A05-9D2B-BDF3923BF756",
}

# Property name -> RealPage property ID
PROPERTY_IDS = {
    "Aspire 7th and Grant": "4779341",
    "Kalaco": "5339721",
    "7East": "5481703",
    "7 East": "5481703",
    "Block 44": "5473254",
    "Edison at RiNo": "4248319",
    "Ridian": "5446271",
    "Nexus East": "5472172",
    "Parkside at Round Rock": "5536211",
    "The Northern": "5375283",
    "The Avant": "5480255",
    "The Hunter": "5558217",
}

# All files to download - parsed from the curls
# (report_id, instance_id, file_id, property_name)
FILES = [
    (3906, "3385128-3564910-3385149", "8880696", "Aspire 7th and Grant"),
    (3837, "3385130-3564912-3385151", "8880698", "Kalaco"),
    (4238, "3385129-3564911-3385150", "8880697", "Kalaco"),
    (3877, "3385132-3564914-3385153", "8880700", "Kalaco"),
    (4043, "3385131-3564913-3385152", "8880699", "Kalaco"),
    (3838, "3385133-3564915-3385154", "8880701", "Kalaco"),
    (4260, "3385134-3564916-3385155", "8880702", "Kalaco"),
    (3837, "3385136-3564918-3385157", "8880704", "Kalaco"),
    (4238, "3385135-3564917-3385156", "8880703", "Kalaco"),
    (4043, "3385137-3564919-3385158", "8880705", "Kalaco"),
    (3877, "3385138-3564920-3385159", "8880706", "Kalaco"),
    (3838, "3385139-3564921-3385160", "8880707", "Kalaco"),
    (4260, "3385140-3564922-3385161", "8880708", "Kalaco"),
    (4238, "3385141-3564923-3385162", "8880709", "7East"),
    (3837, "3385142-3564924-3385163", "8880710", "7East"),
    (4043, "3385143-3564925-3385164", "8880711", "7East"),
    (3877, "3385144-3564926-3385165", "8880712", "7East"),
    (3838, "3385145-3564927-3385166", "8880713", "7East"),
    (4260, "3385146-3564928-3385167", "8880714", "7East"),
    (3837, "3385148-3564930-3385169", "8880716", "Block 44"),
    (4238, "3385147-3564929-3385168", "8880715", "Block 44"),
    (4043, "3385149-3564931-3385170", "8880717", "Block 44"),
    (4260, "3385152-3564934-3385173", "8880720", "Block 44"),
    (3877, "3385150-3564932-3385171", "8880718", "Block 44"),
    (3838, "3385151-3564933-3385172", "8880719", "Block 44"),
]


def download_file(report_id, instance_id, file_id, property_name):
    """Download a single report file."""
    url = f"{BASE_URL}/reports/{report_id}/report-instances/{instance_id}/files"
    report_key = REPORT_KEYS[report_id]
    payload = {
        "reportId": report_id,
        "parameters": f"reportKey={report_key}&sourceId=OS&fileID={file_id}&View=2",
        "fileId": file_id,
        "propertyName": property_name,
    }
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "accept": "application/json, text/plain, */*",
        "origin": "https://www.realpage.com",
        "referer": "https://www.realpage.com/",
    }

    try:
        with httpx.Client(timeout=60, verify=False) as client:
            resp = client.post(url, headers=headers, json=payload)
            if resp.status_code == 200 and len(resp.content) > 500:
                return resp.content
            else:
                print(f"    ✗ HTTP {resp.status_code}, size {len(resp.content)}")
                return None
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return None


def main():
    print("=" * 60)
    print("  REALPAGE REPORT DOWNLOAD & IMPORT")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 60)

    # Deduplicate by (property, report_type) - keep latest file_id
    seen = {}
    for report_id, instance_id, file_id, prop in FILES:
        rtype = REPORT_ID_MAP.get(report_id, "unknown")
        key = (prop, rtype)
        seen[key] = (report_id, instance_id, file_id, prop)

    unique_files = list(seen.values())
    print(f"\n📋 {len(unique_files)} unique reports to download (deduplicated from {len(FILES)})")

    # Group by property for display
    by_prop = {}
    for report_id, instance_id, file_id, prop in unique_files:
        by_prop.setdefault(prop, []).append((report_id, instance_id, file_id))

    for prop, items in by_prop.items():
        types = [REPORT_ID_MAP.get(r, "?") for r, _, _ in items]
        print(f"  {prop}: {', '.join(types)}")

    # Download all files
    print(f"\n{'='*60}")
    print("  STEP 1: DOWNLOADING FILES")
    print(f"{'='*60}")

    downloaded = []
    failed = []

    for i, (report_id, instance_id, file_id, prop) in enumerate(unique_files, 1):
        rtype = REPORT_ID_MAP.get(report_id, "unknown")
        print(f"\n[{i}/{len(unique_files)}] {prop} - {rtype} (file {file_id})...", end="", flush=True)

        content = download_file(report_id, instance_id, file_id, prop)
        if content:
            size_kb = len(content) / 1024
            print(f" ✓ {size_kb:.1f} KB")
            downloaded.append({
                "report_id": report_id,
                "file_id": file_id,
                "property": prop,
                "report_type": rtype,
                "content": content,
            })
        else:
            print(f" ✗ FAILED")
            failed.append({"file_id": file_id, "property": prop, "report_type": rtype})

    print(f"\n✅ Downloaded: {len(downloaded)} / {len(unique_files)}")
    if failed:
        print(f"❌ Failed: {len(failed)}")
        for f in failed:
            print(f"   - {f['property']} / {f['report_type']} (file {f['file_id']})")

    # Import to database
    print(f"\n{'='*60}")
    print("  STEP 2: PARSING & IMPORTING TO realpage_raw.db")
    print(f"{'='*60}")

    from report_parsers import parse_report
    from import_reports import import_box_score, import_delinquency, import_rent_roll, init_report_tables

    conn = sqlite3.connect(DB_PATH)
    init_report_tables(conn)

    import_stats = {}  # property -> {report_type: count}

    for item in downloaded:
        prop = item["property"]
        rtype = item["report_type"]
        file_id = item["file_id"]

        # Save temp file
        temp_path = SCRIPT_DIR / f"temp_{file_id}.xlsx"
        temp_path.write_bytes(item["content"])

        try:
            result = parse_report(str(temp_path))
            records = result.get("records", [])
            parsed_type = result.get("report_type", rtype)

            if records:
                # Set property_id on all records
                prop_id = PROPERTY_IDS.get(prop, "")
                for r in records:
                    r['property_id'] = prop_id

                count = 0
                if parsed_type == "box_score":
                    count = import_box_score(conn, records, str(temp_path), file_id)
                elif parsed_type == "delinquency":
                    count = import_delinquency(conn, records, str(temp_path), file_id)
                elif parsed_type == "rent_roll":
                    count = import_rent_roll(conn, records, str(temp_path), file_id)
                else:
                    count = 0

                if count > 0:
                    import_stats.setdefault(prop, {})[parsed_type] = count
                    print(f"  ✓ {prop} / {parsed_type}: {count} records")
                else:
                    print(f"  - {prop} / {parsed_type}: parsed but no importable records (type: {parsed_type})")
            else:
                print(f"  - {prop} / {rtype}: no records parsed")
        except Exception as e:
            print(f"  ✗ {prop} / {rtype}: parse error - {e}")
        finally:
            temp_path.unlink(missing_ok=True)

    conn.close()

    # Sync to unified
    print(f"\n{'='*60}")
    print("  STEP 3: SYNCING TO unified.db")
    print(f"{'='*60}")

    import subprocess
    result = subprocess.run(
        ["python3", "-u", "-m", "app.db.sync_realpage_to_unified"],
        cwd=SCRIPT_DIR,
        capture_output=False,
        text=True,
        timeout=120,
    )

    # Final summary
    print(f"\n{'='*60}")
    print("  FINAL STATUS")
    print(f"{'='*60}")

    all_props = set()
    for item in downloaded:
        all_props.add(item["property"])

    for prop in sorted(all_props):
        stats = import_stats.get(prop, {})
        if stats:
            details = ", ".join(f"{t}: {c} rec" for t, c in stats.items())
            print(f"  ✅ {prop}: {details}")
        else:
            print(f"  ⚠️  {prop}: downloaded but no importable records")

    if failed:
        print(f"\n  ❌ Failed downloads:")
        for f in failed:
            print(f"     {f['property']} / {f['report_type']}")

    total_records = sum(c for stats in import_stats.values() for c in stats.values())
    print(f"\n📊 Total: {len(downloaded)} files downloaded, {total_records} records imported across {len(import_stats)} properties")


if __name__ == "__main__":
    main()
