#!/usr/bin/env python3
"""Download RealPage reports for all properties.

Flow:
1. Create report instances for all property/report combos
2. Poll /v1/my/report-instances to get fileIds when reports are ready
3. Download files using fileIds
4. Import to realpage_raw.db and sync to unified.db
"""

import json
import time
import io
import httpx
import sqlite3
import sys
import warnings
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List

warnings.filterwarnings("ignore")

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "app/db/data/realpage_raw.db"
BASE_URL = "https://reportingapi.realpage.com/v1"
MAX_DATE_RETRIES = 3
POLL_INTERVAL = 15      # seconds between polls
POLL_MAX_ATTEMPTS = 20   # max polls (~5 minutes total)

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
    "cache-control": "no-cache",
    "expires": "Sat, 01 Jan 2000 00:00:00 GMT",
    "pragma": "no-cache",
    "origin": "https://www.realpage.com",
    "referer": "https://www.realpage.com/",
}

CLIENT = httpx.Client(timeout=60, verify=False)

# Report types (only status=complete)
REPORT_TYPES = {}
for rkey, rdef in DEFINITIONS["reports"].items():
    if rdef.get("status") == "complete":
        REPORT_TYPES[rkey] = rdef

# All properties
ALL_PROPERTIES = {}
for key, prop in DEFINITIONS["properties"].items():
    ALL_PROPERTIES[prop["propertyId"]] = {
        "key": key,
        "name": prop["propertyName"],
        "detail": prop,
    }


# ── Poll for file IDs ────────────────────────────────────────
def poll_my_instances(instance_ids: set, start_date: str) -> Dict[str, str]:
    """Poll /v1/my/report-instances to get fileIds for created instances.
    
    Returns dict: {instanceId -> reportFileId}
    """
    url = f"{BASE_URL}/my/report-instances"
    body = {
        "pageSize": 200,
        "pageNumber": 1,
        "searchText": "",
        "reportProductList": [],
        "reportAreaList": [],
        "startDate": start_date,
        "endDate": datetime.utcnow().strftime("%Y-%m-%dT23:59:59.999Z"),
        "favorite": False,
        "PropertiesList": [],
        "OrderBy": "CreatedDate",
        "OrderByDesc": True,
    }

    found = {}
    for attempt in range(POLL_MAX_ATTEMPTS):
        try:
            resp = CLIENT.post(url, headers=HEADERS, json=body)
            if resp.status_code != 200:
                print(f"  Poll error: {resp.status_code} {resp.text[:200]}")
                time.sleep(POLL_INTERVAL)
                continue

            data = resp.json()
            items = data.get("data", [])

            for item in items:
                src_id = item.get("sourceReportInstanceId", "")
                file_id = item.get("reportFileId", "")
                status = item.get("status", 0)
                if src_id in instance_ids and file_id and status == 3:
                    found[src_id] = file_id

            remaining = len(instance_ids) - len(found)
            sys.stdout.write(f"\r  Poll {attempt + 1}/{POLL_MAX_ATTEMPTS}: {len(found)}/{len(instance_ids)} ready, {remaining} pending...")
            sys.stdout.flush()

            if len(found) >= len(instance_ids):
                print(f"\r  All {len(found)} reports ready!                    ")
                return found

            # Check if we need more pages
            total_count = data.get("totalCount", 0)
            if total_count > 200:
                body["pageSize"] = min(total_count, 500)
                continue

        except Exception as e:
            print(f"\n  Poll exception: {e}")

        time.sleep(POLL_INTERVAL)

    print(f"\n  Poll complete: {len(found)}/{len(instance_ids)} found after {POLL_MAX_ATTEMPTS} attempts")
    return found


def download_file(file_id: str, instance_id: str, report_def: dict, property_name: str) -> Optional[bytes]:
    """Download a report file using its fileId."""
    url = f"{BASE_URL}/reports/{report_def['report_id']}/report-instances/{instance_id}/files"
    payload = {
        "reportId": report_def["report_id"],
        "parameters": f"reportKey={report_def['report_key']}&sourceId=OS&fileID={file_id}&View=2",
        "fileId": str(file_id),
        "propertyName": property_name,
    }
    try:
        resp = CLIENT.post(url, headers=HEADERS, json=payload)
        if resp.status_code == 200 and len(resp.content) > 500:
            return resp.content
        else:
            return None
    except Exception as e:
        print(f"    Download error for file {file_id}: {e}")
        return None


# ── DB table mapping ────────────────────────────────────────
TABLE_MAP = {
    "box_score": "realpage_box_score",
    "rent_roll": "realpage_rent_roll",
    "delinquency_prepaid": "realpage_delinquency",
    "activity_report": "realpage_activity",
    "monthly_activity_summary": "realpage_monthly_summary",
    "lease_expiration": "realpage_lease_expirations",
    "projected_occupancy": "realpage_projected_occupancy",
    "lease_expiration_renewal": "realpage_lease_expiration_renewal",
    "monthly_transaction_summary": "realpage_monthly_transaction_detail",
    "make_ready_summary": "realpage_make_ready",
    "closed_make_ready": "realpage_closed_make_ready",
    "advertising_source": "realpage_advertising_source",
    "lost_rent_summary": "realpage_lost_rent_summary",
    "move_out_reasons": "realpage_move_out_reasons",
}


def cleanup_report_files():
    """Remove downloaded .xls/.xlsx report files to keep codebase clean."""
    dl_dir = SCRIPT_DIR / "downloaded_reports"
    if not dl_dir.exists():
        return 0
    removed = 0
    for f in dl_dir.iterdir():
        if f.suffix in (".xls", ".xlsx"):
            f.unlink()
            removed += 1
    return removed


# ── Instance creation ────────────────────────────────────────
def build_payload(report_def, property_detail, date_offset=0, timeframe_tag=None, run_report_for=None):
    """Build the API payload. date_offset=0 means today, 1=yesterday, etc.
    timeframe_tag: 'ytd','mtd','l30','l7' — adjusts start_date for date-range reports."""
    from datetime import timedelta
    from dateutil.relativedelta import relativedelta
    target = datetime.now() - timedelta(days=date_offset)
    exp_end = target + relativedelta(months=4)

    # Compute start_date based on timeframe
    if timeframe_tag == 'mtd':
        start_date = f"{target.month:02d}/01/{target.year}"
    elif timeframe_tag == 'l30':
        start_date = (target - timedelta(days=30)).strftime("%m/%d/%Y")
    elif timeframe_tag == 'l7':
        start_date = (target - timedelta(days=7)).strftime("%m/%d/%Y")
    else:  # ytd or default
        start_date = f"01/01/{target.year}"

    dates = {
        "start_date": start_date,
        "end_date": target.strftime("%m/%d/%Y"),
        "as_of_date": target.strftime("%m/%d/%Y"),
        "start_month": target.strftime("%m/%Y"),
        "end_month": target.strftime("%m/%Y"),
        "fiscal_period": target.strftime("%m%Y"),
        # Forward-looking dates for lease expiration reports
        "exp_start_date": target.replace(day=1).strftime("%m/%d/%Y"),
        "exp_end_date": exp_end.replace(day=1).strftime("%m/%d/%Y"),
        "exp_end_month": exp_end.strftime("%m/%Y"),
    }

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


def create_instance(report_def, property_detail, date_offset=0, verbose=False, timeframe_tag=None, run_report_for=None):
    """Create a report instance. Returns response dict."""
    url = f"{BASE_URL}/reports/{report_def['report_id']}/report-instances"
    payload = build_payload(report_def, property_detail, date_offset=date_offset, timeframe_tag=timeframe_tag, run_report_for=run_report_for)

    try:
        resp = CLIENT.post(url, headers=HEADERS, json=payload)
        if resp.status_code in (200, 201):
            data = resp.json()
            if verbose:
                print(f"\n    CREATE RESPONSE ({resp.status_code}):")
                print(f"    {json.dumps(data, indent=2)[:600]}")
            return data
        else:
            print(f" ✗ {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        print(f" ✗ Exception: {e}")
        return None


# ── Import ───────────────────────────────────────────────────
def import_downloaded(downloads):
    """Import downloaded reports into realpage_raw.db."""
    from report_parsers import parse_report
    from import_reports import (
        import_box_score, import_delinquency, import_rent_roll,
        import_monthly_summary, import_lease_expiration, import_activity,
        import_projected_occupancy, import_lease_expiration_renewal,
        import_monthly_transaction_summary,
        import_make_ready, import_closed_make_ready,
        import_advertising_source, import_lost_rent_summary,
        import_move_out_reasons,
        init_report_tables,
    )

    conn = sqlite3.connect(DB_PATH)
    init_report_tables(conn)

    IMPORTERS = {
        "box_score": import_box_score,
        "delinquency": import_delinquency,
        "delinquency_prepaid": import_delinquency,
        "rent_roll": import_rent_roll,
        "monthly_summary": import_monthly_summary,
        "lease_expiration": import_lease_expiration,
        "activity_report": import_activity,
        "activity": import_activity,
        "projected_occupancy": import_projected_occupancy,
        "lease_expiration_renewal": import_lease_expiration_renewal,
        "monthly_transaction_summary": import_monthly_transaction_summary,
        "make_ready_summary": import_make_ready,
        "closed_make_ready": import_closed_make_ready,
        "advertising_source": import_advertising_source,
        "lost_rent_summary": import_lost_rent_summary,
        "move_out_reasons": import_move_out_reasons,
    }

    total = 0
    results = {}

    for dl in downloads:
        if not dl.get("content"):
            continue

        prop = dl["prop_name"]
        rtype = dl["report_type"]
        prop_id = dl["prop_id"]

        temp_path = SCRIPT_DIR / f"temp_{dl['file_id']}.xlsx"
        temp_path.write_bytes(dl["content"])

        try:
            result = parse_report(str(temp_path), report_type_hint=rtype)
            records = result.get("records", [])
            parsed_type = result.get("report_type") or rtype

            if records:
                for r in records:
                    r["property_id"] = prop_id
                    r["property_name"] = prop  # override with known name

                importer = IMPORTERS.get(parsed_type)
                count = 0
                if importer:
                    # advertising_source takes timeframe_tag kwarg
                    if parsed_type == 'advertising_source' and dl.get('timeframe_tag'):
                        count = importer(conn, records, str(temp_path), str(dl["file_id"]), timeframe_tag=dl['timeframe_tag'])
                    else:
                        count = importer(conn, records, str(temp_path), str(dl["file_id"]))

                tf_label = f" [{dl['timeframe_tag']}]" if dl.get('timeframe_tag') else ''
                if count > 0:
                    print(f"  ✓ {prop} / {parsed_type}{tf_label}: {count} records")
                    total += count
                    results.setdefault(prop, {})[f"{parsed_type}{tf_label}"] = count
                else:
                    print(f"  ⚠ {prop} / {parsed_type}{tf_label}: 0 imported from {len(records)} parsed")
            else:
                print(f"  - {prop} / {rtype}: no records parsed")
        except Exception as e:
            print(f"  ✗ {prop} / {rtype}: {e}")
        finally:
            temp_path.unlink(missing_ok=True)

    conn.close()
    return total, results


# ── Main ─────────────────────────────────────────────────────
def create_instances_with_fallback(needed):
    """Create instances for all items. If create fails, retry with date stepped back.
    
    Date fallback is ONLY for failed creates (API rejects the date).
    If create succeeds, the file exists — we just need to scan for it.
    """
    from datetime import timedelta
    for idx, item in enumerate(needed):
        for date_offset in range(MAX_DATE_RETRIES):
            target = (datetime.now() - timedelta(days=date_offset)).strftime("%m/%d/%Y")

            verbose = (date_offset == 0 and idx == 0)
            response = create_instance(item["report_def"], item["prop_detail"],
                                       date_offset=date_offset, verbose=verbose,
                                       timeframe_tag=item.get("timeframe_tag"),
                                       run_report_for=item.get("run_report_for"))
            tf_label = f" [{item['timeframe_tag']}]" if item.get('timeframe_tag') else ''
            if response:
                item["instance_id"] = response.get("instanceId")
                item["date_used"] = target
                if not verbose:
                    sys.stdout.write(f"  {item['prop_name']} / {item['report_type']}{tf_label}... ✓\n")
                break
            else:
                if date_offset < MAX_DATE_RETRIES - 1:
                    sys.stdout.write(f"  {item['prop_name']} / {item['report_type']}{tf_label}... ✗ (date {target}), retrying -1d\n")
                    time.sleep(2)  # pause before date retry
                else:
                    sys.stdout.write(f"  {item['prop_name']} / {item['report_type']}{tf_label}... ✗ all dates failed\n")
            sys.stdout.flush()

        # Rate limit: 0.5s per request, 3s pause every 20
        time.sleep(0.5)
        if (idx + 1) % 20 == 0:
            time.sleep(3)
            sys.stdout.write(f"  ... ({idx + 1}/{len(needed)} created)\n")
            sys.stdout.flush()

    created = sum(1 for n in needed if n.get("instance_id"))
    return created


def main():
    total_props = len(ALL_PROPERTIES)
    total_reports = len(REPORT_TYPES)
    # Count jobs including timeframe variants and run_report_for variants
    total_jobs = 0
    for rtype, rdef in REPORT_TYPES.items():
        tf_count = len(rdef.get('timeframe_variants', [])) or 1
        rrf_count = len(rdef.get('run_report_for_variants', [])) or 1
        total_jobs += total_props * tf_count * rrf_count

    print("=" * 60)
    print("  REALPAGE REPORT DOWNLOADER v2 (daily fresh)")
    print(f"  {datetime.now().isoformat()}")
    print(f"  Strategy: create → poll /my/report-instances → download")
    print(f"  {total_props} properties × {total_reports} report types = {total_jobs} jobs")
    print(f"  Reports: {', '.join(REPORT_TYPES.keys())}")
    tf_reports = [f"{k}×{len(v.get('timeframe_variants',[]))}tf" for k,v in REPORT_TYPES.items() if v.get('timeframe_variants')]
    if tf_reports:
        print(f"  Timeframe variants: {', '.join(tf_reports)}")
    print("=" * 60)

    # ── Build full list of ALL property/report combos ─────────
    needed = []
    for pid, prop_info in ALL_PROPERTIES.items():
        for rtype, rdef in REPORT_TYPES.items():
            tf_variants = rdef.get('timeframe_variants')
            rrf_variants = rdef.get('run_report_for_variants')
            if tf_variants:
                for tf in tf_variants:
                    needed.append({
                        "prop_id": pid,
                        "prop_name": prop_info["name"],
                        "prop_detail": prop_info["detail"],
                        "report_type": rtype,
                        "report_def": rdef,
                        "instance_id": None,
                        "file_id": None,
                        "content": None,
                        "timeframe_tag": tf,
                        "run_report_for": None,
                    })
            elif rrf_variants:
                for rrf in rrf_variants:
                    tag = 'former' if 'Former' in rrf else 'notice'
                    needed.append({
                        "prop_id": pid,
                        "prop_name": prop_info["name"],
                        "prop_detail": prop_info["detail"],
                        "report_type": rtype,
                        "report_def": rdef,
                        "instance_id": None,
                        "file_id": None,
                        "content": None,
                        "timeframe_tag": tag,
                        "run_report_for": rrf,
                    })
            else:
                needed.append({
                    "prop_id": pid,
                    "prop_name": prop_info["name"],
                    "prop_detail": prop_info["detail"],
                    "report_type": rtype,
                    "report_def": rdef,
                    "instance_id": None,
                    "file_id": None,
                    "content": None,
                    "timeframe_tag": None,
                    "run_report_for": None,
                })

    print(f"\n📊 Requesting {len(needed)} reports for {total_props} properties")

    # ── Step 1: Create all instances ──────────────────────────
    start_time = datetime.utcnow().strftime("%Y-%m-%dT00:00:00.000Z")

    print(f"\n{'='*60}")
    print(f"  STEP 1: CREATING REPORT INSTANCES")
    print(f"{'='*60}")

    created = create_instances_with_fallback(needed)
    print(f"\n  Created {created}/{len(needed)} instances")

    if created == 0:
        print("❌ Token may be expired. Get a fresh one from the UI.")
        CLIENT.close()
        return

    # ── Step 2: Poll for file IDs ────────────────────────────
    instance_lookup = {}  # instanceId -> needed item
    for item in needed:
        if item.get("instance_id"):
            instance_lookup[item["instance_id"]] = item

    print(f"\n{'='*60}")
    print(f"  STEP 2: POLLING FOR FILE IDs ({len(instance_lookup)} instances)")
    print(f"{'='*60}")

    file_map = poll_my_instances(set(instance_lookup.keys()), start_time)

    # Assign file IDs back to needed items
    for inst_id, file_id in file_map.items():
        if inst_id in instance_lookup:
            instance_lookup[inst_id]["file_id"] = file_id

    # ── Step 3: Download files ───────────────────────────────
    with_file_id = [n for n in needed if n.get("file_id")]
    print(f"\n{'='*60}")
    print(f"  STEP 3: DOWNLOADING {len(with_file_id)} FILES")
    print(f"{'='*60}")

    for idx, item in enumerate(with_file_id):
        sys.stdout.write(f"\r  Downloading {idx + 1}/{len(with_file_id)}: {item['prop_name']} / {item['report_type']}...")
        sys.stdout.flush()

        content = download_file(
            file_id=item["file_id"],
            instance_id=item["instance_id"],
            report_def=item["report_def"],
            property_name=item["prop_name"],
        )
        if content:
            item["content"] = content
        else:
            print(f"\n    ✗ Failed to download file {item['file_id']}")

        # Rate limit downloads
        time.sleep(0.3)

    downloaded = sum(1 for n in needed if n.get("content"))
    print(f"\n  Downloaded {downloaded}/{len(with_file_id)} files")

    # ── Step 3b: Retry box_score reports with date errors ────
    # Some properties reject End_Date > their property date.
    # Detect error content and retry with stepped-back dates.
    box_score_retries = []
    for item in needed:
        if item.get("content") and item["report_type"] == "box_score":
            if len(item["content"]) < 15000:
                try:
                    test_df = pd.read_excel(io.BytesIO(item["content"]), sheet_name=0, header=None)
                    full_text = ' '.join(str(x) for x in test_df.values.flatten() if pd.notna(x))
                    if 'Invalid end date' in full_text or 'Invalid start date' in full_text:
                        box_score_retries.append(item)
                        item["content"] = None  # clear bad content
                except Exception:
                    pass

    if box_score_retries:
        print(f"\n{'='*60}")
        print(f"  STEP 3b: RETRYING {len(box_score_retries)} BOX SCORE REPORTS (date fallback)")
        print(f"{'='*60}")

        for date_offset in range(2, MAX_DATE_RETRIES + 5):
            if not box_score_retries:
                break

            retry_start = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z")
            still_failing = []

            for item in box_score_retries:
                resp = create_instance(item["report_def"], item["prop_detail"],
                                       date_offset=date_offset)
                if resp:
                    item["instance_id"] = resp.get("instanceId")
                    sys.stdout.write(f"  {item['prop_name']} / box_score (offset -{date_offset}d)... ✓\n")
                else:
                    sys.stdout.write(f"  {item['prop_name']} / box_score (offset -{date_offset}d)... ✗\n")
                sys.stdout.flush()
                time.sleep(0.5)

            # Poll for the new instances
            retry_ids = {item["instance_id"] for item in box_score_retries if item.get("instance_id")}
            if retry_ids:
                retry_map = poll_my_instances(retry_ids, retry_start)
                for item in box_score_retries:
                    iid = item.get("instance_id")
                    if iid and iid in retry_map:
                        item["file_id"] = retry_map[iid]

            # Download and check for errors
            for item in box_score_retries:
                if not item.get("file_id"):
                    still_failing.append(item)
                    continue
                content = download_file(
                    file_id=item["file_id"],
                    instance_id=item["instance_id"],
                    report_def=item["report_def"],
                    property_name=item["prop_name"],
                )
                if content and len(content) > 15000:
                    item["content"] = content
                    print(f"  ✓ {item['prop_name']} box_score OK with offset -{date_offset}d")
                elif content:
                    # Check if still an error
                    try:
                        test_df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None)
                        full_text = ' '.join(str(x) for x in test_df.values.flatten() if pd.notna(x))
                        if 'Invalid' in full_text:
                            still_failing.append(item)
                            item["content"] = None
                        else:
                            item["content"] = content
                            print(f"  ✓ {item['prop_name']} box_score OK with offset -{date_offset}d")
                    except Exception:
                        still_failing.append(item)
                else:
                    still_failing.append(item)
                time.sleep(0.3)

            box_score_retries = still_failing
            if box_score_retries:
                print(f"  Still {len(box_score_retries)} failing, trying offset -{date_offset + 1}d...")

        if box_score_retries:
            print(f"  ⚠ {len(box_score_retries)} box_score reports still failing after all date retries")

    # ── Step 4: Import ───────────────────────────────────────
    with_content = [n for n in needed if n.get("content")]
    if with_content:
        print(f"\n{'='*60}")
        print(f"  STEP 4: IMPORTING {len(with_content)} REPORTS")
        print(f"{'='*60}")
        total, results = import_downloaded(with_content)

        print(f"\n{'='*60}")
        print("  STEP 5: SYNCING TO unified.db")
        print(f"{'='*60}")
        import subprocess
        subprocess.run([sys.executable, "-m", "app.db.sync_realpage_to_unified"], cwd=str(SCRIPT_DIR))

        print(f"\n  Total records imported: {total}")
        for prop, types in sorted(results.items()):
            details = ", ".join(f"{t}: {c}" for t, c in types.items())
            print(f"    {prop}: {details}")
    else:
        print("\n❌ No files downloaded.")

    # Final summary
    still_missing = [n for n in needed if not n.get("content")]
    if still_missing:
        print(f"\n  ⚠ Still missing {len(still_missing)}/{len(needed)} reports:")
        for n in still_missing[:20]:
            status = "no file_id" if not n.get("file_id") else "download failed"
            if not n.get("instance_id"):
                status = "create failed"
            print(f"    {n['prop_name']} / {n['report_type']} ({status})")
    else:
        print(f"\n✅ All {len(needed)} reports downloaded successfully!")

    # Clean up downloaded report files
    removed = cleanup_report_files()
    if removed:
        print(f"\n🧹 Cleaned up {removed} downloaded report files")

    CLIENT.close()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="RealPage Report Downloader v2")
    parser.add_argument("--target", nargs="+", help="Only these property IDs")
    parser.add_argument("--only-reports", nargs="+", help="Only these report types")
    args = parser.parse_args()

    if args.target:
        ALL_PROPERTIES = {k: v for k, v in ALL_PROPERTIES.items() if k in set(args.target)}
        print(f"Filtered to {len(ALL_PROPERTIES)} properties")

    if args.only_reports:
        REPORT_TYPES = {k: v for k, v in REPORT_TYPES.items() if k in args.only_reports}
        print(f"Filtered to: {list(REPORT_TYPES.keys())}")

    main()
