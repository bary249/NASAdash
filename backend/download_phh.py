#!/usr/bin/env python3
"""
Minified RealPage Report Downloader — PHH Properties Only

Pulls all 7 report types for PHH-group properties only.
Uses the v2 flow: create → poll /my/report-instances → download → import → sync.

Usage:
    python download_phh.py
    python download_phh.py --only-reports box_score rent_roll projected_occupancy
"""

import json
import time
import io
import sys
import warnings
import httpx
import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

warnings.filterwarnings("ignore")

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "app/db/data/realpage_raw.db"
BASE_URL = "https://reportingapi.realpage.com/v1"
POLL_INTERVAL = 15
POLL_MAX_ATTEMPTS = 20
MAX_DATE_RETRIES = 3

# ── Config ──────────────────────────────────────────────────
with open(SCRIPT_DIR / "realpage_token.json") as f:
    TOKEN = json.load(f)["access_token"]
    if TOKEN.startswith("Bearer "):
        TOKEN = TOKEN[7:]

with open(SCRIPT_DIR / "report_definitions.json") as f:
    DEFINITIONS = json.load(f)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "accept": "application/json, text/plain, */*",
    "cache-control": "no-cache",
    "origin": "https://www.realpage.com",
    "referer": "https://www.realpage.com/",
}

CLIENT = httpx.Client(timeout=60, verify=False)

# PHH properties only
PHH_PROPERTIES = {
    "5472172": {"propertyId": "5472172", "propertyName": "Nexus East", "country": "US"},
    "5536211": {"propertyId": "5536211", "propertyName": "Parkside at Round Rock", "country": "US"},
}

# All active report types
REPORT_TYPES = {k: v for k, v in DEFINITIONS["reports"].items() if v.get("status") == "complete"}


# ── Core functions ──────────────────────────────────────────
def compute_dates(timeframe_tag: str = None, date_offset: int = 0) -> dict:
    """Compute date ranges for a given timeframe tag."""
    target = datetime.now() - timedelta(days=date_offset)
    today = target
    dates = {
        "as_of_date": today.strftime("%m/%d/%Y"),
        "start_month": today.strftime("%m/%Y"),
        "end_month": today.strftime("%m/%Y"),
        "fiscal_period": today.strftime("%m%Y"),
        "exp_start_date": today.strftime("%m/%d/%Y"),
        "exp_end_date": (today + timedelta(days=365)).strftime("%m/%d/%Y"),
    }
    if timeframe_tag == 'mtd':
        dates["start_date"] = f"{today.month:02d}/01/{today.year}"
        dates["end_date"] = today.strftime("%m/%d/%Y")
    elif timeframe_tag == 'l30':
        dates["start_date"] = (today - timedelta(days=30)).strftime("%m/%d/%Y")
        dates["end_date"] = today.strftime("%m/%d/%Y")
    elif timeframe_tag == 'l7':
        dates["start_date"] = (today - timedelta(days=7)).strftime("%m/%d/%Y")
        dates["end_date"] = today.strftime("%m/%d/%Y")
    else:  # ytd or default
        dates["start_date"] = f"01/01/{today.year}"
        dates["end_date"] = today.strftime("%m/%d/%Y")
    return dates


def build_payload(report_def, property_detail, date_offset=0, timeframe_tag=None, run_report_for=None):
    dates = compute_dates(timeframe_tag, date_offset)
    parameters = []
    for param in report_def["parameters"]:
        value = param["value"]
        if value == "{{run_report_for}}" and run_report_for:
            value = run_report_for
        else:
            for key, replacement in dates.items():
                if value == "{{" + key + "}}":
                    value = replacement
                    break
        parameters.append({"name": param["name"], "label": value, "value": value})

    return {
        "reportKey": report_def["report_key"],
        "sourceId": "OS",
        "scheduledType": 1, "scheduledDate": "", "scheduledTime": "",
        "scheduleDateTime": None,
        "reportFormat": report_def["formats"].get(report_def.get("download_format", "excel"), "3"),
        "reportFormatName": report_def.get("download_format", "Excel").upper() if report_def.get("download_format") else "Excel",
        "emaiTo": "",
        "properties": [property_detail["propertyId"]],
        "propertyDetailList": [property_detail],
        "parameters": parameters,
        "users": [], "cloudServiceAccountId": None,
    }


def create_instance(report_def, property_detail, date_offset=0, timeframe_tag=None, run_report_for=None):
    url = f"{BASE_URL}/reports/{report_def['report_id']}/report-instances"
    try:
        resp = CLIENT.post(url, headers=HEADERS, json=build_payload(report_def, property_detail, date_offset, timeframe_tag, run_report_for))
        if resp.status_code in (200, 201):
            return resp.json()
        else:
            return None
    except Exception:
        return None


def poll_my_instances(instance_ids: set, start_date: str) -> Dict[str, str]:
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
            sys.stdout.write(f"\r  Poll {attempt+1}/{POLL_MAX_ATTEMPTS}: {len(found)}/{len(instance_ids)} ready, {remaining} pending...")
            sys.stdout.flush()
            if len(found) >= len(instance_ids):
                print(f"\r  All {len(found)} reports ready!                    ")
                return found
        except Exception as e:
            print(f"\n  Poll error: {e}")
        time.sleep(POLL_INTERVAL)
    print(f"\n  Poll done: {len(found)}/{len(instance_ids)}")
    return found


def download_file(file_id, instance_id, report_def, property_name) -> Optional[bytes]:
    url = f"{BASE_URL}/reports/{report_def['report_id']}/report-instances/{instance_id}/files"
    payload = {
        "reportId": report_def["report_id"],
        "parameters": f"reportKey={report_def['report_key']}&sourceId=OS&fileID={file_id}&View=2",
        "fileId": str(file_id), "propertyName": property_name,
    }
    try:
        resp = CLIENT.post(url, headers=HEADERS, json=payload)
        if resp.status_code == 200 and len(resp.content) > 500:
            return resp.content
    except Exception:
        pass
    return None


def import_all(downloads):
    from report_parsers import parse_report
    from import_reports import (
        import_box_score, import_delinquency, import_rent_roll,
        import_monthly_summary, import_lease_expiration, import_activity,
        import_projected_occupancy, import_lease_expiration_renewal,
        import_monthly_transaction_summary,
        import_make_ready, import_closed_make_ready,
        import_advertising_source, import_lost_rent_summary,
        import_move_out_reasons, import_lease_details,
        import_income_statement,
        init_report_tables,
    )
    conn = sqlite3.connect(DB_PATH)
    init_report_tables(conn)

    IMPORTERS = {
        "box_score": import_box_score,
        "delinquency": import_delinquency, "delinquency_prepaid": import_delinquency,
        "rent_roll": import_rent_roll,
        "monthly_summary": import_monthly_summary,
        "lease_expiration": import_lease_expiration,
        "activity_report": import_activity, "activity": import_activity,
        "projected_occupancy": import_projected_occupancy,
        "lease_expiration_renewal": import_lease_expiration_renewal,
        "monthly_transaction_summary": import_monthly_transaction_summary,
        "make_ready_summary": import_make_ready,
        "closed_make_ready": import_closed_make_ready,
        "advertising_source": import_advertising_source,
        "lost_rent_summary": import_lost_rent_summary,
        "move_out_reasons": import_move_out_reasons,
        "lease_details": import_lease_details,
        "income_statement": import_income_statement,
    }
    total = 0
    for dl in downloads:
        if not dl.get("content"):
            continue
        ext = ".csv" if dl.get("report_def", {}).get("download_format") == "csv" else ".xlsx"
        temp = SCRIPT_DIR / f"temp_{dl['file_id']}{ext}"
        temp.write_bytes(dl["content"])
        try:
            result = parse_report(str(temp), report_type_hint=dl["report_type"])
            records = result.get("records", [])
            parsed_type = result.get("report_type") or dl["report_type"]
            if records:
                for r in records:
                    r["property_id"] = dl["prop_id"]
                    r["property_name"] = dl["prop_name"]
                importer = IMPORTERS.get(parsed_type)
                if importer:
                    # advertising_source takes timeframe_tag kwarg
                    if parsed_type == 'advertising_source' and dl.get('timeframe_tag'):
                        count = importer(conn, records, str(temp), str(dl["file_id"]), timeframe_tag=dl['timeframe_tag'])
                    else:
                        count = importer(conn, records, str(temp), str(dl["file_id"]))
                    tf_label = f" [{dl['timeframe_tag']}]" if dl.get('timeframe_tag') else ''
                    if count > 0:
                        print(f"  ✓ {dl['prop_name']} / {parsed_type}{tf_label}: {count} records")
                        total += count
        except Exception as e:
            print(f"  ✗ {dl['prop_name']} / {dl['report_type']}: {e}")
        finally:
            temp.unlink(missing_ok=True)
    conn.close()
    return total


# ── Main ────────────────────────────────────────────────────
def main():
    import argparse
    parser = argparse.ArgumentParser(description="PHH-Only Report Downloader")
    parser.add_argument("--only-reports", nargs="+", help="Only these report types")
    args = parser.parse_args()

    report_types = REPORT_TYPES
    if args.only_reports:
        report_types = {k: v for k, v in report_types.items() if k in args.only_reports}

    # Count total jobs including timeframe variants and run_report_for variants
    total_jobs = 0
    for rtype, rdef in report_types.items():
        variant_count = len(rdef.get('timeframe_variants', [])) or len(rdef.get('run_report_for_variants', [])) or 1
        total_jobs += len(PHH_PROPERTIES) * variant_count
    print("=" * 60)
    print("  PHH REPORT DOWNLOADER")
    print(f"  {datetime.now().isoformat()}")
    print(f"  {len(PHH_PROPERTIES)} properties × {len(report_types)} reports = {total_jobs} jobs")
    print(f"  Properties: {', '.join(p['propertyName'] for p in PHH_PROPERTIES.values())}")
    print(f"  Reports: {', '.join(report_types.keys())}")
    tf_reports = [f"{k}×{len(v.get('timeframe_variants',[]))}" for k,v in report_types.items() if v.get('timeframe_variants')]
    if tf_reports:
        print(f"  Timeframe variants: {', '.join(tf_reports)}")
    print("=" * 60)

    # Step 1: Create instances
    print(f"\n── STEP 1: CREATING {total_jobs} INSTANCES ──")
    start_time = datetime.utcnow().strftime("%Y-%m-%dT00:00:00.000Z")
    needed = []

    for pid, pdetail in PHH_PROPERTIES.items():
        for rtype, rdef in report_types.items():
            # Check if this report has run_report_for variants (e.g. move_out_reasons)
            rrf_variants = rdef.get('run_report_for_variants')
            if rrf_variants:
                for rrf in rrf_variants:
                    for date_offset in range(MAX_DATE_RETRIES):
                        resp = create_instance(rdef, pdetail, date_offset=date_offset, run_report_for=rrf)
                        if resp:
                            tag = 'former' if 'Former' in rrf else 'notice'
                            needed.append({
                                "prop_id": pid, "prop_name": pdetail["propertyName"],
                                "prop_detail": pdetail, "report_type": rtype, "report_def": rdef,
                                "instance_id": resp.get("instanceId"),
                                "file_id": None, "content": None,
                                "timeframe_tag": tag,
                            })
                            sys.stdout.write(f"  {pdetail['propertyName']} / {rtype} [{tag}] ✓\n")
                            break
                        elif date_offset < MAX_DATE_RETRIES - 1:
                            time.sleep(1)
                        else:
                            sys.stdout.write(f"  {pdetail['propertyName']} / {rtype} [{rrf}] ✗ failed\n")
                    sys.stdout.flush()
                    time.sleep(0.5)
                continue
            # Check if this report has timeframe variants
            tf_variants = rdef.get('timeframe_variants')
            if tf_variants:
                for tf in tf_variants:
                    for date_offset in range(MAX_DATE_RETRIES):
                        resp = create_instance(rdef, pdetail, date_offset=date_offset, timeframe_tag=tf)
                        if resp:
                            needed.append({
                                "prop_id": pid, "prop_name": pdetail["propertyName"],
                                "prop_detail": pdetail, "report_type": rtype, "report_def": rdef,
                                "instance_id": resp.get("instanceId"),
                                "file_id": None, "content": None,
                                "timeframe_tag": tf,
                            })
                            sys.stdout.write(f"  {pdetail['propertyName']} / {rtype} [{tf}] ✓\n")
                            break
                        elif date_offset < MAX_DATE_RETRIES - 1:
                            time.sleep(1)
                        else:
                            sys.stdout.write(f"  {pdetail['propertyName']} / {rtype} [{tf}] ✗ failed\n")
                    sys.stdout.flush()
                    time.sleep(0.5)
            else:
                for date_offset in range(MAX_DATE_RETRIES):
                    resp = create_instance(rdef, pdetail, date_offset=date_offset)
                    if resp:
                        needed.append({
                            "prop_id": pid, "prop_name": pdetail["propertyName"],
                            "prop_detail": pdetail, "report_type": rtype, "report_def": rdef,
                            "instance_id": resp.get("instanceId"),
                            "file_id": None, "content": None,
                            "timeframe_tag": None,
                        })
                        sys.stdout.write(f"  {pdetail['propertyName']} / {rtype} ✓\n")
                        break
                    elif date_offset < MAX_DATE_RETRIES - 1:
                        sys.stdout.write(f"  {pdetail['propertyName']} / {rtype} ✗ retrying...\n")
                        time.sleep(1)
                    else:
                        sys.stdout.write(f"  {pdetail['propertyName']} / {rtype} ✗ failed\n")
                sys.stdout.flush()
                time.sleep(0.5)

    created = len([n for n in needed if n.get("instance_id")])
    print(f"  Created {created}/{total_jobs}")

    if created == 0:
        print("❌ Token expired. Get a fresh one.")
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
        sys.stdout.write(f"\r  {idx+1}/{len(with_file)}: {item['prop_name']} / {item['report_type']}...")
        sys.stdout.flush()
        content = download_file(item["file_id"], item["instance_id"], item["report_def"], item["prop_name"])
        if content:
            item["content"] = content
        time.sleep(0.3)
    downloaded = sum(1 for n in needed if n.get("content"))
    print(f"\n  Downloaded {downloaded}/{len(with_file)}")

    # Step 4: Import
    with_content = [n for n in needed if n.get("content")]
    if with_content:
        print(f"\n── STEP 4: IMPORTING {len(with_content)} REPORTS ──")
        total = import_all(with_content)
        print(f"\n  Total records: {total}")

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
            print(f"    {n['prop_name']} / {n['report_type']}")
    else:
        print(f"\n✅ All {total_jobs} PHH reports done!")

    CLIENT.close()


if __name__ == "__main__":
    main()
