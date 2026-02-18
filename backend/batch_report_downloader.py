#!/usr/bin/env python3
"""
RealPage Smart Batch Report Downloader

Workflow:
1. Create instances for all reports in report_definitions.json
2. Smart scan file IDs - identify content and match to instances
3. Parse reports and import to database
4. Delete temporary files after import

Usage:
    python batch_report_downloader.py --property "The Northern"
    python batch_report_downloader.py --property "Nexus East" --reports box_score rent_roll
    python batch_report_downloader.py --property "Parkside at Round Rock" --import-only
"""

import json
import time
import httpx
import argparse
import sqlite3
import pandas as pd
import io
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://reportingapi.realpage.com/v1"
SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "app/db/data/realpage_raw.db"

# Load token
def load_token():
    with open(SCRIPT_DIR / "realpage_token.json") as f:
        token_data = json.load(f)
        token = token_data["access_token"]
        if token.startswith("Bearer "):
            token = token[7:]
        return token

TOKEN = load_token()

# Load report definitions
with open(SCRIPT_DIR / "report_definitions.json") as f:
    DEFINITIONS = json.load(f)


def get_headers():
    return {
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": "application/json",
        "accept": "application/json, text/plain, */*",
        "origin": "https://www.realpage.com",
        "referer": "https://www.realpage.com/",
    }


def get_property_detail(property_name: str) -> dict:
    """Get property details from definitions or use provided info."""
    for key, prop in DEFINITIONS.get("properties", {}).items():
        if prop["propertyName"].lower() == property_name.lower():
            return prop
    raise ValueError(f"Property '{property_name}' not found in definitions")


def build_payload(report_def: dict, property_detail: dict, dates: dict) -> dict:
    """Build the API payload for a report."""
    parameters = []
    for param in report_def["parameters"]:
        value = param["value"]
        # Replace template variables
        if value == "{{start_date}}":
            value = dates.get("start_date", "01/01/2026")
        elif value == "{{end_date}}":
            value = dates.get("end_date", "02/04/2026")
        elif value == "{{as_of_date}}":
            value = dates.get("as_of_date", dates.get("end_date", "02/04/2026"))
        elif value == "{{start_month}}":
            value = dates.get("start_month", "02/2026")
        elif value == "{{end_month}}":
            value = dates.get("end_month", "07/2026")
        elif value == "{{fiscal_period}}":
            value = dates.get("fiscal_period", "022026")
        
        parameters.append({
            "name": param["name"],
            "label": value,
            "value": value
        })
    
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
        "cloudServiceAccountId": None
    }


def create_instance(report_name: str, report_def: dict, property_detail: dict, dates: dict) -> str:
    """Create a report instance and return the instance ID."""
    url = f"{BASE_URL}/reports/{report_def['report_id']}/report-instances"
    payload = build_payload(report_def, property_detail, dates)
    
    print(f"  Creating instance for {report_name}...")
    
    with httpx.Client(timeout=30, verify=False) as client:
        response = client.post(url, headers=get_headers(), json=payload)
        
        if response.status_code in (200, 201):
            data = response.json()
            instance_id = data.get("instanceId")
            print(f"    ✓ Instance: {instance_id}")
            return instance_id
        else:
            print(f"    ✗ Error {response.status_code}: {response.text[:200]}")
            return None


def try_download_file(file_id: int) -> Optional[bytes]:
    """Try to download a file with the given file ID."""
    url = f"{BASE_URL}/reports/4043/report-instances/0-0-0/files"
    payload = {
        "reportId": 4043,
        "parameters": f"reportKey=A6F61299-E960-4235-9DC2-44D2C2EF4F99&sourceId=OS&fileID={file_id}&View=2",
        "fileId": str(file_id),
        "propertyName": "scan"
    }
    
    try:
        with httpx.Client(timeout=30, verify=False) as client:
            response = client.post(url, headers=get_headers(), json=payload)
            if response.status_code == 200 and len(response.content) > 1000:
                return response.content
    except Exception:
        pass
    return None


def identify_report(content: bytes) -> Dict:
    """Identify report type and property from content."""
    try:
        df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None)
        
        # Get first few non-empty rows
        rows = []
        for _, row in df.iterrows():
            clean_row = [str(x) for x in row.dropna().tolist() if str(x) != 'nan']
            if clean_row:
                rows.append(clean_row)
            if len(rows) >= 5:
                break
        
        if not rows:
            return {"type": "unknown", "property": None}
        
        content_text = ' '.join([' '.join(row) for row in rows[:3]]).upper()
        
        # Identify report type
        report_type = "unknown"
        if "BOXSCORE" in content_text or "BOX SCORE" in content_text:
            report_type = "box_score"
        elif "RENT ROLL" in content_text or "RENTROLL" in content_text:
            report_type = "rent_roll"
        elif "MONTHLY ACTIVITY SUMMARY" in content_text:
            report_type = "monthly_summary"
        elif "DELINQUENT" in content_text or "PREPAID" in content_text:
            report_type = "delinquency"
        elif "LEASE EXPIRATION" in content_text or "LEASE EXPIR" in content_text:
            report_type = "lease_expiration"
        elif "PROJECTED OCCUPANCY" in content_text:
            report_type = "projected_occupancy"
        elif "ACTIVITY REPORT" in content_text:
            report_type = "activity_report"
        
        # Extract property name
        property_name = None
        for row in rows:
            row_text = ' '.join(row)
            if "KAIROI MANAGEMENT" in row_text.upper():
                parts = row_text.split('-')
                if len(parts) > 1:
                    property_name = parts[1].strip()
                    break
        
        return {"type": report_type, "property": property_name}
        
    except Exception:
        if content.startswith(b'%PDF'):
            return {"type": "pdf", "property": None}
        return {"type": "unknown", "property": None}


# Last known file ID baseline - update this after successful runs
LAST_KNOWN_FILE_ID = 8896187


def normalize_property_name(name: str) -> str:
    """Normalize property name for matching (remove spaces, special chars)."""
    if not name:
        return ""
    return name.lower().replace(" ", "").replace("-", "").replace("_", "")


def _scan_single(file_id: int) -> tuple:
    """Scan a single file ID. Returns (file_id, content_or_None)."""
    content = try_download_file(file_id)
    return (file_id, content)


def smart_scan_and_match(instances: list, max_scan: int = 500) -> list:
    """Parallel scan file IDs and match to instances based on content."""
    start_file_id = LAST_KNOWN_FILE_ID + 1
    print(f"\n=== PARALLEL SCANNING ===")
    print(f"Scanning {max_scan} file IDs from {start_file_id} (10 parallel)...", flush=True)

    needed = {i: inst for i, inst in enumerate(instances) if inst.get("instance_id")}
    found_any = False
    batch_size = 10

    for batch_start in range(0, max_scan, batch_size):
        if not needed:
            break

        batch_ids = [start_file_id + batch_start + j for j in range(batch_size)]
        print(f"  Batch {batch_ids[0]}-{batch_ids[-1]}...", end="", flush=True)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(_scan_single, fid): fid for fid in batch_ids}
            results = {}
            for future in as_completed(futures):
                fid, content = future.result()
                if content:
                    results[fid] = content

        if not results:
            print(f" empty", flush=True)
            if not found_any and batch_start > 200:
                print(f"  ⚠ No files found in 200+ IDs, stopping")
                break
            continue

        found_any = True
        hits = 0
        for fid in sorted(results.keys()):
            content = results[fid]
            identification = identify_report(content)

            for idx, inst in list(needed.items()):
                target_prop = normalize_property_name(inst['property_name'])
                target_report = inst['report_key'].lower()
                file_prop = normalize_property_name(identification.get('property') or '')
                file_type = identification.get('type', '')

                # Normalize report key for matching (delinquency_prepaid → delinquency)
                match_type = target_report.replace('_prepaid', '') if '_prepaid' in target_report else target_report
                if file_prop and target_prop in file_prop and file_type == match_type:
                    inst['downloaded'] = True
                    inst['file_id'] = fid
                    inst['content'] = content
                    hits += 1
                    del needed[idx]
                    break

        if hits:
            print(f" ✓ {hits} matched", flush=True)
            for inst in instances:
                if inst.get('downloaded') and inst.get('file_id'):
                    if inst['file_id'] in results:
                        print(f"    ✓ {inst['file_id']}: {inst['report_name']}")
        else:
            found_types = [identify_report(c).get('type','?') for c in results.values()]
            print(f" {len(results)} files (not ours: {','.join(found_types)})", flush=True)

    matched = len([i for i in instances if i.get('downloaded')])
    print(f"\nMatched: {matched} / {len(instances)}")
    return instances


def import_to_database(instances: list) -> int:
    """Import downloaded reports to database."""
    from report_parsers import parse_report
    from import_reports import import_box_score, import_delinquency, import_rent_roll, import_monthly_summary, import_lease_expiration, import_activity, import_projected_occupancy, import_lease_expiration_renewal, import_monthly_transaction_summary, import_income_statement, init_report_tables
    
    conn = sqlite3.connect(DB_PATH)
    init_report_tables(conn)
    
    imported_count = 0
    
    for inst in instances:
        if not inst.get('content'):
            continue
        
        try:
            # Save temp file for parsing
            temp_file = SCRIPT_DIR / f"temp_{inst['file_id']}.xlsx"
            temp_file.write_bytes(inst['content'])
            
            # Parse the report
            result = parse_report(str(temp_file))
            
            if result['records']:
                # Set property ID
                for r in result['records']:
                    r['property_id'] = inst['property_id']
                
                # Import based on type
                IMPORTERS = {
                    'box_score': import_box_score,
                    'delinquency': import_delinquency,
                    'delinquency_prepaid': import_delinquency,
                    'rent_roll': import_rent_roll,
                    'monthly_summary': import_monthly_summary,
                    'lease_expiration': import_lease_expiration,
                    'activity': import_activity,
                    'activity_report': import_activity,
                    'projected_occupancy': import_projected_occupancy,
                    'lease_expiration_renewal': import_lease_expiration_renewal,
                    'monthly_transaction_summary': import_monthly_transaction_summary,
                    'income_statement': import_income_statement,
                }
                importer = IMPORTERS.get(result['report_type'])
                if importer:
                    count = importer(conn, result['records'], str(temp_file), str(inst['file_id']))
                else:
                    count = 0
                
                if count > 0:
                    inst['imported'] = count
                    imported_count += count
                    print(f"  ✓ Imported {count} {result['report_type']} records")
            
            # Delete temp file
            temp_file.unlink()
            
        except Exception as e:
            print(f"  ✗ Error importing {inst['report_name']}: {e}")
    
    conn.close()
    return imported_count


def main():
    parser = argparse.ArgumentParser(description="Smart RealPage Report Downloader")
    parser.add_argument("--property", required=True, help="Property name")
    parser.add_argument("--start-date", default="02/01/2026", help="Start date (MM/DD/YYYY)")
    parser.add_argument("--end-date", default="02/04/2026", help="End date (MM/DD/YYYY)")
    parser.add_argument("--reports", nargs="+", help="Specific reports (box_score, rent_roll, delinquency)")
    parser.add_argument("--no-import", action="store_true", help="Skip database import")
    
    args = parser.parse_args()
    
    dates = {
        "start_date": args.start_date,
        "end_date": args.end_date,
        "as_of_date": args.end_date,
        "start_month": args.start_date[:2] + "/" + args.start_date[-4:],
        "end_month": "07/2026",
        "fiscal_period": args.start_date[:2] + args.start_date[-4:],
    }
    
    # Get property details
    try:
        property_detail = get_property_detail(args.property)
        print(f"Property: {property_detail['propertyName']} ({property_detail['propertyId']})")
    except ValueError as e:
        print(f"Error: {e}")
        print("Available properties:")
        for key, prop in DEFINITIONS.get("properties", {}).items():
            print(f"  - {prop['propertyName']}")
        return
    
    # Filter reports
    reports_to_run = DEFINITIONS["reports"]
    if args.reports:
        reports_to_run = {k: v for k, v in reports_to_run.items() if k in args.reports}
    
    print(f"\n=== STEP 1: CREATING INSTANCES ===")
    print(f"Creating {len(reports_to_run)} report instances...")
    
    instances = []
    for report_key, report_def in reports_to_run.items():
        if report_def.get("status") != "complete":
            continue
            
        instance_id = create_instance(
            report_def["name"],
            report_def,
            property_detail,
            dates
        )
        
        instances.append({
            "report_name": report_def["name"],
            "report_key": report_key,
            "report_id": report_def["report_id"],
            "instance_id": instance_id,
            "property_name": property_detail["propertyName"],
            "property_id": property_detail["propertyId"],
            "downloaded": False
        })
        
        time.sleep(0.3)
    
    # Wait for reports to generate
    print(f"\n=== STEP 2: WAITING FOR GENERATION ===")
    print("Waiting 30 seconds for report generation...")
    time.sleep(30)
    
    # Smart scan and match
    print(f"\n=== STEP 3: SMART SCAN & MATCH ===")
    instances = smart_scan_and_match(instances)
    
    # Import to database
    if not args.no_import:
        print(f"\n=== STEP 4: IMPORT TO DATABASE ===")
        imported = import_to_database(instances)
        print(f"Total imported: {imported} records")
    
    # Summary
    print("\n" + "=" * 50)
    print("FINAL SUMMARY")
    print("=" * 50)
    for inst in instances:
        status = "✓" if inst.get("downloaded") else "✗"
        import_info = f" ({inst.get('imported', 0)} records)" if inst.get('imported') else ""
        print(f"  {status} {inst['report_name']}: File ID {inst.get('file_id', 'N/A')}{import_info}")


if __name__ == "__main__":
    main()
