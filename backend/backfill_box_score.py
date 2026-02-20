#!/usr/bin/env python3
"""
One-time historical backfill: download box_score snapshots for PHH properties
for the last 6 months (end-of-month snapshots).

This gives the AI historical occupancy data to answer trend questions.

Usage:
    python backfill_box_score.py
"""

import json
import time
import sys
import warnings
import httpx
import sqlite3
from datetime import datetime
from pathlib import Path
from calendar import monthrange

warnings.filterwarnings("ignore")

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "app/db/data/realpage_raw.db"
BASE_URL = "https://reportingapi.realpage.com/v1"
POLL_INTERVAL = 12
POLL_MAX_ATTEMPTS = 20

# ── Config ──────────────────────────────────────────────────
with open(SCRIPT_DIR / "realpage_token.json") as f:
    TOKEN = json.load(f)["access_token"]
    if TOKEN.startswith("Bearer "):
        TOKEN = TOKEN[7:]

with open(SCRIPT_DIR / "report_definitions.json") as f:
    BOX_SCORE_DEF = json.load(f)["reports"]["box_score"]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "accept": "application/json, text/plain, */*",
    "cache-control": "no-cache",
    "origin": "https://www.realpage.com",
    "referer": "https://www.realpage.com/",
}

CLIENT = httpx.Client(timeout=60, verify=False)

PHH_PROPERTIES = {
    "5472172": {"propertyId": "5472172", "propertyName": "Nexus East", "country": "US"},
    "5536211": {"propertyId": "5536211", "propertyName": "Parkside at Round Rock", "country": "US"},
}

# Generate end-of-month dates for last 6 months
def get_monthly_snapshots(months_back=6):
    """Return list of (year, month, end_date_str) for last N months."""
    now = datetime.now()
    snapshots = []
    for i in range(1, months_back + 1):
        m = now.month - i
        y = now.year
        while m <= 0:
            m += 12
            y -= 1
        last_day = monthrange(y, m)[1]
        date_str = f"{m:02d}/{last_day:02d}/{y}"
        snapshots.append((y, m, date_str))
    return list(reversed(snapshots))  # chronological order


def create_instance(end_date_str, property_detail):
    """Create a box_score report instance for a specific end date."""
    # For box_score, Start_Date = first of month, End_Date = end of month
    parts = end_date_str.split("/")
    start_date_str = f"{parts[0]}/01/{parts[2]}"
    
    parameters = []
    for param in BOX_SCORE_DEF["parameters"]:
        value = param["value"]
        if value == "{{start_date}}":
            value = start_date_str
        elif value == "{{end_date}}":
            value = end_date_str
        parameters.append({"name": param["name"], "label": value, "value": value})

    payload = {
        "reportKey": BOX_SCORE_DEF["report_key"],
        "sourceId": "OS",
        "scheduledType": 1, "scheduledDate": "", "scheduledTime": "",
        "scheduleDateTime": None,
        "reportFormat": BOX_SCORE_DEF["formats"].get(BOX_SCORE_DEF.get("download_format", "excel"), "3"),
        "reportFormatName": "Excel",
        "emaiTo": "",
        "properties": [property_detail["propertyId"]],
        "propertyDetailList": [property_detail],
        "parameters": parameters,
        "users": [], "cloudServiceAccountId": None,
    }

    url = f"{BASE_URL}/reports/{BOX_SCORE_DEF['report_id']}/report-instances"
    try:
        resp = CLIENT.post(url, headers=HEADERS, json=payload)
        if resp.status_code in (200, 201):
            return resp.json()
    except Exception as e:
        print(f"  Create error: {e}")
    return None


def poll_my_instances(instance_ids, start_date):
    url = f"{BASE_URL}/my/report-instances"
    body = {
        "pageSize": 200, "pageNumber": 1, "searchText": "",
        "reportProductList": [], "reportAreaList": [],
        "startDate": start_date,
        "endDate": datetime.utcnow().strftime("%Y-%m-%dT23:59:59.999Z"),
        "favorite": False, "PropertiesList": [],
        "OrderBy": "CreatedDate", "OrderByDesc": True,
    }
    found = {}
    for attempt in range(POLL_MAX_ATTEMPTS):
        try:
            resp = CLIENT.post(url, headers=HEADERS, json=body)
            if resp.status_code == 200:
                for item in resp.json().get("data", []):
                    src_id = item.get("sourceReportInstanceId", "")
                    file_id = item.get("reportFileId", "")
                    if src_id in instance_ids and file_id and item.get("status") == 3:
                        found[src_id] = file_id
            remaining = len(instance_ids) - len(found)
            sys.stdout.write(f"\r  Poll {attempt+1}/{POLL_MAX_ATTEMPTS}: {len(found)}/{len(instance_ids)} ready...")
            sys.stdout.flush()
            if len(found) >= len(instance_ids):
                print(f"\r  All {len(found)} reports ready!                    ")
                return found
        except Exception as e:
            print(f"\n  Poll error: {e}")
        time.sleep(POLL_INTERVAL)
    print(f"\n  Poll done: {len(found)}/{len(instance_ids)}")
    return found


def download_file(file_id, instance_id, property_name):
    url = f"{BASE_URL}/reports/{BOX_SCORE_DEF['report_id']}/report-instances/{instance_id}/files"
    payload = {
        "reportId": BOX_SCORE_DEF["report_id"],
        "parameters": f"reportKey={BOX_SCORE_DEF['report_key']}&sourceId=OS&fileID={file_id}&View=2",
        "fileId": str(file_id), "propertyName": property_name,
    }
    try:
        resp = CLIENT.post(url, headers=HEADERS, json=payload)
        if resp.status_code == 200 and len(resp.content) > 500:
            return resp.content
    except Exception:
        pass
    return None


def main():
    snapshots = get_monthly_snapshots(6)
    total_jobs = len(PHH_PROPERTIES) * len(snapshots)
    
    print("=" * 60)
    print("  BOX SCORE HISTORICAL BACKFILL")
    print(f"  {datetime.now().isoformat()}")
    print(f"  {len(PHH_PROPERTIES)} properties × {len(snapshots)} months = {total_jobs} reports")
    print(f"  Properties: {', '.join(p['propertyName'] for p in PHH_PROPERTIES.values())}")
    print(f"  Months: {', '.join(f'{y}-{m:02d}' for y, m, _ in snapshots)}")
    print("=" * 60)

    # Step 1: Create all instances
    print(f"\n── STEP 1: CREATING {total_jobs} INSTANCES ──")
    start_time = datetime.utcnow().strftime("%Y-%m-%dT00:00:00.000Z")
    needed = []
    
    for pid, pdetail in PHH_PROPERTIES.items():
        for year, month, end_date in snapshots:
            resp = create_instance(end_date, pdetail)
            if resp:
                needed.append({
                    "prop_id": pid, "prop_name": pdetail["propertyName"],
                    "instance_id": resp.get("instanceId"),
                    "file_id": None, "content": None,
                    "end_date": end_date, "year": year, "month": month,
                })
                print(f"  {pdetail['propertyName']} / {year}-{month:02d} ({end_date}) ✓")
            else:
                print(f"  {pdetail['propertyName']} / {year}-{month:02d} ({end_date}) ✗ FAILED")
            time.sleep(0.5)
    
    created = len([n for n in needed if n.get("instance_id")])
    print(f"  Created {created}/{total_jobs}")
    
    if created == 0:
        print("❌ Token expired or reports rejected. Get a fresh token.")
        CLIENT.close()
        return

    # Step 2: Poll for file IDs
    instance_lookup = {n["instance_id"]: n for n in needed if n.get("instance_id")}
    print(f"\n── STEP 2: POLLING FOR {len(instance_lookup)} FILE IDs ──")
    file_map = poll_my_instances(set(instance_lookup.keys()), start_time)
    for inst_id, file_id in file_map.items():
        if inst_id in instance_lookup:
            instance_lookup[inst_id]["file_id"] = file_id

    # Step 3: Download files
    with_file = [n for n in needed if n.get("file_id")]
    print(f"\n── STEP 3: DOWNLOADING {len(with_file)} FILES ──")
    for idx, item in enumerate(with_file):
        sys.stdout.write(f"\r  {idx+1}/{len(with_file)}: {item['prop_name']} / {item['year']}-{item['month']:02d}...")
        sys.stdout.flush()
        content = download_file(item["file_id"], item["instance_id"], item["prop_name"])
        if content:
            item["content"] = content
        time.sleep(0.3)
    downloaded = sum(1 for n in needed if n.get("content"))
    print(f"\n  Downloaded {downloaded}/{len(with_file)}")

    # Step 4: Parse and import
    with_content = [n for n in needed if n.get("content")]
    if with_content:
        print(f"\n── STEP 4: IMPORTING {len(with_content)} BOX SCORES ──")
        from report_parsers import parse_report
        from import_reports import import_box_score, init_report_tables
        
        conn = sqlite3.connect(DB_PATH)
        init_report_tables(conn)
        total_records = 0
        
        for item in with_content:
            temp = SCRIPT_DIR / f"temp_backfill_{item['prop_id']}_{item['year']}_{item['month']:02d}.xlsx"
            temp.write_bytes(item["content"])
            try:
                result = parse_report(str(temp), report_type_hint="box_score")
                records = result.get("records", [])
                if records:
                    for r in records:
                        r["property_id"] = item["prop_id"]
                        r["property_name"] = item["prop_name"]
                    count = import_box_score(conn, records, str(temp), f"backfill_{item['prop_id']}_{item['year']}{item['month']:02d}")
                    if count > 0:
                        print(f"  ✓ {item['prop_name']} / {item['year']}-{item['month']:02d}: {count} records")
                        total_records += count
            except Exception as e:
                print(f"  ✗ {item['prop_name']} / {item['year']}-{item['month']:02d}: {e}")
            finally:
                temp.unlink(missing_ok=True)
        
        conn.close()
        print(f"\n  Total records imported: {total_records}")

        # Step 5: Sync to unified.db
        print(f"\n── STEP 5: SYNCING TO unified.db ──")
        import subprocess
        subprocess.run([sys.executable, "-m", "app.db.sync_realpage_to_unified"], cwd=str(SCRIPT_DIR))
    else:
        print("\n❌ No files downloaded.")

    # Summary
    missing = [n for n in needed if not n.get("content")]
    if missing:
        print(f"\n  ⚠ Missing {len(missing)}/{total_jobs}:")
        for n in missing:
            print(f"    {n['prop_name']} / {n['year']}-{n['month']:02d}")
    else:
        print(f"\n✅ All {total_jobs} historical box scores downloaded!")

    CLIENT.close()


if __name__ == "__main__":
    main()
