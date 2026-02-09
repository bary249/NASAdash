#!/usr/bin/env python3
"""
Re-download and re-import ALL rent roll reports for all Kairoi properties.
Uses the fixed parser that handles unit numbers with special characters.
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
from typing import Optional
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

RENT_ROLL_DEF = DEFINITIONS["reports"]["rent_roll"]

# All properties
ALL_PROPERTIES = {}
for key, prop in DEFINITIONS["properties"].items():
    ALL_PROPERTIES[prop["propertyId"]] = {
        "key": key,
        "name": prop["propertyName"],
        "detail": prop,
    }


def build_payload(property_detail: dict) -> dict:
    now = datetime.now()
    as_of = now.strftime("%m/%d/%Y")

    parameters = []
    for param in RENT_ROLL_DEF["parameters"]:
        value = param["value"]
        if value == "{{as_of_date}}":
            value = as_of
        parameters.append({"name": param["name"], "label": value, "value": value})

    return {
        "reportKey": RENT_ROLL_DEF["report_key"],
        "sourceId": "OS",
        "scheduledType": 1,
        "scheduledDate": "",
        "scheduledTime": "",
        "scheduleDateTime": None,
        "reportFormat": RENT_ROLL_DEF["formats"].get("excel", "3"),
        "reportFormatName": "Excel",
        "emaiTo": "",
        "properties": [property_detail["propertyId"]],
        "propertyDetailList": [property_detail],
        "parameters": parameters,
        "users": [],
        "cloudServiceAccountId": None,
    }


def create_instance(property_detail: dict) -> Optional[str]:
    url = f"{BASE_URL}/reports/{RENT_ROLL_DEF['report_id']}/report-instances"
    payload = build_payload(property_detail)
    try:
        with httpx.Client(timeout=30, verify=False) as client:
            resp = client.post(url, headers=HEADERS, json=payload)
            if resp.status_code in (200, 201):
                return resp.json().get("instanceId")
            else:
                print(f"    ✗ Error {resp.status_code}: {resp.text[:100]}")
                return None
    except Exception as e:
        print(f"    ✗ {e}")
        return None


def try_download_file(file_id: int):
    """Try to download a file by ID. Returns (file_id, content) or (file_id, None)."""
    url = f"{BASE_URL}/reports/{RENT_ROLL_DEF['report_id']}/report-instances/0-0-0/files"
    payload = {
        "reportId": RENT_ROLL_DEF["report_id"],
        "parameters": f"reportKey={RENT_ROLL_DEF['report_key']}&sourceId=OS&fileID={file_id}&View=2",
        "fileId": str(file_id),
        "propertyName": "scan",
    }
    try:
        with httpx.Client(timeout=20, verify=False) as client:
            resp = client.post(url, headers=HEADERS, json=payload)
            if resp.status_code == 200 and len(resp.content) > 1000:
                return (file_id, resp.content)
    except Exception:
        pass
    return (file_id, None)


def identify_report(content: bytes) -> dict:
    """Identify property name from Excel content."""
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None)
        rows = []
        for _, row in df.iterrows():
            clean = [str(x) for x in row.dropna().tolist() if str(x) != "nan"]
            if clean:
                rows.append(clean)
            if len(rows) >= 8:
                break

        prop = None
        for row in rows:
            row_text = " ".join(row)
            if "Kairoi" in row_text or "Management" in row_text:
                parts = row_text.split("-")
                if len(parts) > 1:
                    prop = parts[-1].strip()
                    break

        rtype = "unknown"
        text = " ".join([" ".join(r) for r in rows[:5]]).upper()
        if "RENT ROLL" in text or "RENTROLL" in text:
            rtype = "rent_roll"

        return {"type": rtype, "property": prop}
    except Exception:
        return {"type": "unknown", "property": None}


def normalize(name: str) -> str:
    if not name:
        return ""
    return name.lower().replace(" ", "").replace("-", "").replace("_", "").replace("the", "")


def main():
    START_FILE_ID = int(sys.argv[1]) if len(sys.argv) > 1 else 8885055

    print("=" * 60)
    print("  RE-DOWNLOAD ALL RENT ROLLS (FIXED PARSER)")
    print(f"  {datetime.now().isoformat()}")
    print(f"  Properties: {len(ALL_PROPERTIES)}")
    print(f"  Scan start: {START_FILE_ID}")
    print("=" * 60)

    # Step 1: Create instances for all properties
    print(f"\n--- STEP 1: CREATING {len(ALL_PROPERTIES)} RENT ROLL INSTANCES ---")
    items = []
    created = 0
    for pid, info in sorted(ALL_PROPERTIES.items(), key=lambda x: x[1]["name"]):
        sys.stdout.write(f"  {info['name']:<35}")
        sys.stdout.flush()

        instance_id = create_instance(info["detail"])
        if instance_id:
            created += 1
            print(f" ✓ {instance_id}")
        else:
            print(" ✗ failed")

        items.append({
            "prop_id": pid,
            "prop_name": info["name"],
            "instance_id": instance_id,
            "file_id": None,
            "content": None,
        })
        time.sleep(0.2)

    print(f"\n  Created {created}/{len(ALL_PROPERTIES)} instances")

    if created == 0:
        print("❌ No instances created. Token may be expired.")
        return

    # Step 2: Wait for generation
    wait_secs = 45
    print(f"\n--- STEP 2: WAITING {wait_secs}s FOR GENERATION ---")
    for i in range(wait_secs, 0, -5):
        sys.stdout.write(f"\r  {i}s remaining...")
        sys.stdout.flush()
        time.sleep(5)
    print("\r  Done waiting!          ")

    # Step 3: Scan file IDs
    print(f"\n--- STEP 3: SCANNING FILE IDS FROM {START_FILE_ID} ---")
    remaining = {i: item for i, item in enumerate(items)}
    batch_size = 10
    consecutive_empty = 0
    found_count = 0
    max_scan = 2000

    for batch_start in range(0, max_scan, batch_size):
        if not remaining:
            print("  All reports found!")
            break

        batch_ids = [START_FILE_ID + batch_start + j for j in range(batch_size)]
        sys.stdout.write(f"  {batch_ids[0]}-{batch_ids[-1]}...")
        sys.stdout.flush()

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(try_download_file, fid): fid for fid in batch_ids}
            results = {}
            for f in as_completed(futures):
                fid, content = f.result()
                if content:
                    results[fid] = content

        if not results:
            consecutive_empty += 1
            print(" empty")
            if consecutive_empty > 40:
                print("  ⚠ 400+ empty IDs, stopping scan")
                break
            continue

        consecutive_empty = 0

        for fid in sorted(results.keys()):
            content = results[fid]
            ident = identify_report(content)
            file_prop = normalize(ident.get("property") or "")
            file_type = ident.get("type", "")

            matched = False
            for idx, item in list(remaining.items()):
                target_prop = normalize(item["prop_name"])
                if file_prop and target_prop and (target_prop in file_prop or file_prop in target_prop):
                    item["file_id"] = fid
                    item["content"] = content
                    found_count += 1
                    del remaining[idx]
                    print(f" ✓ {fid}: {item['prop_name']}")
                    matched = True
                    break

            if not matched:
                prop_name = ident.get("property", "?")
                print(f" ? {fid}: {prop_name} / {file_type} (no match)")

    print(f"\n  Found {found_count}/{len(items)} rent rolls")

    # Step 4: Clear old rent_roll data and re-import
    downloaded = [n for n in items if n.get("content")]
    if not downloaded:
        print("\n❌ No files downloaded.")
        return

    print(f"\n--- STEP 4: IMPORTING {len(downloaded)} RENT ROLLS ---")

    from report_parsers import parse_report
    from import_reports import import_rent_roll, init_report_tables

    conn = sqlite3.connect(DB_PATH)
    init_report_tables(conn)

    # Clear old rent_roll data for properties we're re-importing
    for item in downloaded:
        conn.execute("DELETE FROM realpage_rent_roll WHERE property_id = ?", (item["prop_id"],))
    conn.commit()
    print(f"  Cleared old rent_roll data for {len(downloaded)} properties")

    total_imported = 0
    results_summary = {}

    for item in downloaded:
        temp_path = SCRIPT_DIR / f"temp_rr_{item['file_id']}.xlsx"
        temp_path.write_bytes(item["content"])

        try:
            result = parse_report(str(temp_path))
            records = result.get("records", [])
            parsed_type = result.get("report_type", "rent_roll")

            if records:
                for r in records:
                    r["property_id"] = item["prop_id"]

                count = import_rent_roll(conn, records, str(temp_path), str(item["file_id"]))
                if count > 0:
                    print(f"  ✓ {item['prop_name']:<35} {count} records (file {item['file_id']})")
                    total_imported += count
                    results_summary[item["prop_name"]] = count
                else:
                    print(f"  ⚠ {item['prop_name']:<35} parsed {len(records)} but 0 imported")
            else:
                print(f"  - {item['prop_name']:<35} no records parsed (detected as {parsed_type})")
        except Exception as e:
            print(f"  ✗ {item['prop_name']:<35} {e}")
        finally:
            temp_path.unlink(missing_ok=True)

    conn.close()

    # Summary
    print(f"\n{'='*60}")
    print("  FINAL SUMMARY")
    print(f"{'='*60}")
    print(f"  Instances created: {created}")
    print(f"  Files downloaded:  {len(downloaded)}")
    print(f"  Records imported:  {total_imported}")

    still_missing = [n for n in items if not n.get("content")]
    if still_missing:
        print(f"\n  ⚠ Missing {len(still_missing)} properties:")
        for n in still_missing:
            print(f"    {n['prop_name']} ({n['prop_id']})")

    print(f"\n  Per property:")
    for prop, count in sorted(results_summary.items()):
        print(f"    {prop:<35} {count} records")


if __name__ == "__main__":
    main()
