#!/usr/bin/env python3
"""
Direct download and import of known report files from RealPage.
File IDs were discovered via scanning after instance creation on 2026-02-08.

Pattern: For each property, 3 consecutive file IDs:
  - Activity Report (HTML format)
  - Monthly Activity Summary (XLS format)
  - Lease Expiration (XLS format)
"""

import json
import sqlite3
import httpx
import pandas as pd
import io
import sys
import re
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "app/db/data/realpage_raw.db"
BASE_URL = "https://reportingapi.realpage.com/v1"

with open(SCRIPT_DIR / "realpage_token.json") as f:
    TOKEN = json.load(f)["access_token"]
    if TOKEN.startswith("Bearer "):
        TOKEN = TOKEN[7:]

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
    "accept": "application/json, text/plain, */*",
    "origin": "https://www.realpage.com",
    "referer": "https://www.realpage.com/",
}

# Known file IDs discovered via scanning (activity, monthly_summary, lease_expiration)
# Order matches property creation order
PROPERTIES = [
    {"name": "Kalaco", "pid": "5339721", "activity": 8880903, "monthly": 8880904, "lease_exp": 8880905},
    {"name": "7 East", "pid": "5481703", "activity": 8880906, "monthly": 8880907, "lease_exp": 8880908},
    {"name": "Block 44", "pid": "5473254", "activity": 8880909, "monthly": 8880910, "lease_exp": 8880911},
    {"name": "Eden Keller Ranch", "pid": "5536209", "activity": 8880912, "monthly": 8880913, "lease_exp": 8880914},
    {"name": "Harvest", "pid": "5507303", "activity": 8880915, "monthly": 8880916, "lease_exp": 8880917},
    {"name": "Luna", "pid": "5590740", "activity": 8880918, "monthly": 8880919, "lease_exp": 8880920},
    {"name": "Nexus East", "pid": "5472172", "activity": 8880921, "monthly": 8880922, "lease_exp": 8880923},
    {"name": "Parkside at Round Rock", "pid": "5536211", "activity": 8880924, "monthly": 8880925, "lease_exp": 8880926},
    {"name": "The Alcott", "pid": "4996967", "activity": 8880927, "monthly": 8880928, "lease_exp": 8880929},
    {"name": "Aspire 7th and Grant", "pid": "4779341", "activity": 8880930, "monthly": 8880931, "lease_exp": 8880932},
    {"name": "Edison at RiNo", "pid": "4248319", "activity": 8880933, "monthly": 8880934, "lease_exp": 8880935},
    {"name": "Ridian", "pid": "5446271", "activity": 8880936, "monthly": 8880937, "lease_exp": 8880938},
    {"name": "The Northern", "pid": "5375283", "activity": 8880939, "monthly": 8880940, "lease_exp": 8880941},
    {"name": "The Avant", "pid": "5480255", "activity": 8880942, "monthly": 8880943, "lease_exp": 8880944},
    {"name": "The Hunter", "pid": "5558217", "activity": 8880945, "monthly": 8880946, "lease_exp": 8880947},
    {"name": "The Station at Riverfront Park", "pid": "4976258", "activity": 8880948, "monthly": 8880949, "lease_exp": 8880950},
    {"name": "Discovery at Kingwood", "pid": "5618425", "activity": 8880951, "monthly": 8880952, "lease_exp": 8880953},
    {"name": "Izzy", "pid": "5618432", "activity": 8880954, "monthly": 8880955, "lease_exp": 8880956},
]


def download_file(file_id: int) -> bytes:
    """Download a file by ID from RealPage."""
    url = f"{BASE_URL}/reports/4043/report-instances/0-0-0/files"
    payload = {
        "reportId": 4043,
        "parameters": f"reportKey=A6F61299-E960-4235-9DC2-44D2C2EF4F99&sourceId=OS&fileID={file_id}&View=2",
        "fileId": str(file_id),
        "propertyName": "scan",
    }
    with httpx.Client(timeout=30, verify=False) as client:
        r = client.post(url, headers=HEADERS, json=payload)
        if r.status_code == 200 and len(r.content) > 500:
            return r.content
    return None


def parse_monthly_summary_xls(content: bytes, property_id: str, property_name: str):
    """Parse Monthly Activity Summary from XLS content."""
    df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None, engine="xlrd")
    
    records = []
    report_date = datetime.now().strftime("%Y-%m-%d")
    
    # Find the report date from header rows
    for _, row in df.head(5).iterrows():
        row_text = " ".join(str(x) for x in row.dropna().tolist())
        if "As of" in row_text:
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})', row_text)
            if date_match:
                report_date = datetime.strptime(date_match.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
    
    # Find the data rows - look for floorplan data
    # The header row contains: Floor plan, Market Rent, Base Rent, Total SQFT, Total Units,
    # Occupied no NTV, Vacant Not Leased, Vacant Leased, etc.
    data_started = False
    header_row_idx = None
    
    for idx, row in df.iterrows():
        vals = [str(x).strip() for x in row.tolist() if str(x).strip() != 'nan']
        row_text = " ".join(vals).upper()
        
        if "FLOOR PLAN" in row_text or "FLOORPLAN" in row_text:
            header_row_idx = idx
            data_started = True
            continue
        
        if data_started and vals:
            # Skip summary/total rows
            if any(x.upper() in ("TOTAL", "GRAND TOTAL", "SUMMARY") for x in vals):
                continue
            
            # Try to extract floorplan data
            # First non-empty value is usually the floorplan name
            floorplan = vals[0] if vals else ""
            if not floorplan or floorplan.upper() in ("NAN", "TOTAL", ""):
                continue
            
            # Try to extract numeric values from the row
            nums = []
            for v in row.tolist():
                try:
                    n = float(v) if str(v).strip() != 'nan' else None
                    nums.append(n)
                except (ValueError, TypeError):
                    nums.append(None)
            
            # Filter to get only numeric columns
            num_vals = [n for n in nums if n is not None]
            
            if len(num_vals) >= 4:
                record = {
                    "property_id": property_id,
                    "property_name": property_name,
                    "report_date": report_date,
                    "floorplan": floorplan,
                    "beginning_occupancy": int(num_vals[2]) if len(num_vals) > 2 else 0,
                    "move_ins": 0,
                    "move_outs": 0,
                    "ending_occupancy": int(num_vals[2]) if len(num_vals) > 2 else 0,
                    "renewals": 0,
                    "notices": 0,
                }
                records.append(record)
    
    return records


def parse_lease_expiration_xls(content: bytes, property_id: str, property_name: str):
    """Parse Lease Expiration from XLS content."""
    df = pd.read_excel(io.BytesIO(content), sheet_name=0, header=None, engine="xlrd")
    
    records = []
    report_date = datetime.now().strftime("%Y-%m-%d")
    
    # Find report date
    for _, row in df.head(5).iterrows():
        row_text = " ".join(str(x) for x in row.dropna().tolist())
        date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', row_text)
        if date_match and "LEASE EXPIRATION" in row_text.upper():
            report_date = datetime.strptime(date_match.group(1), "%m/%d/%Y").strftime("%Y-%m-%d")
    
    # Look for unit-level data rows
    data_started = False
    for idx, row in df.iterrows():
        vals = [str(x).strip() for x in row.tolist() if str(x).strip() != 'nan']
        row_text = " ".join(vals)
        
        if "Unit" in row_text and ("Floorplan" in row_text or "SQFT" in row_text):
            data_started = True
            continue
        
        if not data_started:
            continue
        
        if not vals:
            continue
            
        # Skip totals
        if any(x.upper() in ("TOTAL", "GRAND TOTAL", "SUBTOTAL") for x in vals):
            continue
        
        # Try to find unit number pattern (typically starts with a number)
        unit_number = None
        floorplan = None
        lease_end = None
        current_rent = 0
        market_rent = 0
        
        for i, v in enumerate(row.tolist()):
            sv = str(v).strip()
            if sv == 'nan':
                continue
            # Unit number is often in first column
            if i < 3 and unit_number is None and sv and not sv.upper().startswith(("TOTAL", "SUBTOTAL")):
                unit_number = sv
        
        if unit_number:
            # Extract numeric values
            nums = []
            for v in row.tolist():
                try:
                    n = float(v) if str(v).strip() != 'nan' else None
                    nums.append(n)
                except:
                    nums.append(None)
            
            num_vals = [n for n in nums if n is not None]
            
            record = {
                "property_id": property_id,
                "property_name": property_name,
                "report_date": report_date,
                "unit_number": str(unit_number),
                "floorplan": floorplan,
                "resident_name": None,
                "lease_end": None,
                "current_rent": num_vals[-2] if len(num_vals) >= 2 else 0,
                "market_rent": num_vals[-3] if len(num_vals) >= 3 else 0,
                "lease_term": None,
                "months_until_expiration": None,
                "renewal_status": None,
            }
            records.append(record)
    
    return records


def parse_activity_html(content: bytes, property_id: str, property_name: str):
    """Parse Activity Report from HTML content."""
    html = content.decode("utf-8", errors="replace")
    tables = pd.read_html(io.StringIO(html))
    
    records = []
    report_date = datetime.now().strftime("%Y-%m-%d")
    
    if len(tables) < 3:
        return records
    
    # Main data table is usually the largest
    main_table = max(tables, key=lambda t: len(t))
    
    # Extract activity types and counts
    activity_counts = {}
    for _, row in main_table.iterrows():
        vals = [str(x).strip() for x in row.tolist() if str(x).strip() != 'nan']
        if not vals:
            continue
        
        # Look for activity type entries
        activity_type = vals[0] if vals else None
        if activity_type and activity_type not in ("Activity:", "Follow-up Activity:", "nan"):
            # Count activities by type
            activity_counts[activity_type] = activity_counts.get(activity_type, 0) + 1
    
    # Create summary records per activity type
    for atype, count in activity_counts.items():
        records.append({
            "property_id": property_id,
            "property_name": property_name,
            "report_date": report_date,
            "activity_date": report_date,
            "unit_number": None,
            "floorplan": None,
            "activity_type": atype,
            "resident_name": None,
            "prior_rent": 0,
            "new_rent": 0,
            "rent_change": 0,
            "lease_term": None,
            "move_in_date": None,
            "move_out_date": None,
        })
    
    return records


def import_to_db(conn, records, report_type, file_id):
    """Import records to appropriate table."""
    from import_reports import (
        import_monthly_summary, import_lease_expiration, import_activity,
    )
    
    if report_type == "monthly_summary":
        return import_monthly_summary(conn, records, f"file_{file_id}", str(file_id))
    elif report_type == "lease_expiration":
        return import_lease_expiration(conn, records, f"file_{file_id}", str(file_id))
    elif report_type == "activity_report":
        return import_activity(conn, records, f"file_{file_id}", str(file_id))
    return 0


def main():
    print("=" * 60)
    print("  IMPORT KNOWN REPORTS - 54 FILES")
    print(f"  {datetime.now().isoformat()}")
    print("=" * 60)

    # Also try using the existing parsers first for monthly_summary and lease_expiration
    from report_parsers import parse_report
    from import_reports import (
        import_monthly_summary, import_lease_expiration, import_activity,
        init_report_tables,
    )

    conn = sqlite3.connect(DB_PATH)
    init_report_tables(conn)

    # Ensure new tables exist
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS realpage_lease_expirations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL,
            property_name TEXT,
            report_date TEXT NOT NULL,
            unit_number TEXT,
            floorplan TEXT,
            resident_name TEXT,
            lease_end TEXT,
            current_rent REAL,
            market_rent REAL,
            lease_term INTEGER,
            months_until_expiration INTEGER,
            renewal_status TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_id TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS realpage_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL,
            property_name TEXT,
            report_date TEXT NOT NULL,
            activity_date TEXT,
            unit_number TEXT,
            floorplan TEXT,
            activity_type TEXT,
            resident_name TEXT,
            prior_rent REAL,
            new_rent REAL,
            rent_change REAL,
            lease_term INTEGER,
            move_in_date TEXT,
            move_out_date TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_id TEXT
        )
    """)
    conn.commit()

    stats = {"monthly_summary": 0, "lease_expiration": 0, "activity_report": 0}
    errors = []

    for prop in PROPERTIES:
        name = prop["name"]
        pid = prop["pid"]
        print(f"\n--- {name} ({pid}) ---")

        # 1. Monthly Summary (XLS)
        fid = prop["monthly"]
        sys.stdout.write(f"  Monthly Summary (file {fid})...")
        sys.stdout.flush()
        try:
            content = download_file(fid)
            if content:
                # Save temp file and use existing parser
                temp = SCRIPT_DIR / f"temp_ms_{fid}.xls"
                temp.write_bytes(content)
                try:
                    result = parse_report(str(temp))
                    records = result.get("records", [])
                    for r in records:
                        r["property_id"] = pid
                    if records:
                        count = import_monthly_summary(conn, records, str(temp), str(fid))
                        stats["monthly_summary"] += count
                        print(f" ✓ {count} records (via parser)")
                    else:
                        # Fallback to custom parser
                        records = parse_monthly_summary_xls(content, pid, name)
                        if records:
                            count = import_monthly_summary(conn, records, str(temp), str(fid))
                            stats["monthly_summary"] += count
                            print(f" ✓ {count} records (custom)")
                        else:
                            print(f" ⚠ 0 records parsed")
                except Exception as e:
                    # Fallback
                    records = parse_monthly_summary_xls(content, pid, name)
                    if records:
                        count = import_monthly_summary(conn, records, str(temp), str(fid))
                        stats["monthly_summary"] += count
                        print(f" ✓ {count} records (fallback)")
                    else:
                        print(f" ✗ {e}")
                        errors.append(f"{name}/monthly: {e}")
                finally:
                    temp.unlink(missing_ok=True)
            else:
                print(" ✗ download failed")
        except Exception as e:
            print(f" ✗ {e}")
            errors.append(f"{name}/monthly: {e}")

        # 2. Lease Expiration (XLS)
        fid = prop["lease_exp"]
        sys.stdout.write(f"  Lease Expiration (file {fid})...")
        sys.stdout.flush()
        try:
            content = download_file(fid)
            if content:
                temp = SCRIPT_DIR / f"temp_le_{fid}.xls"
                temp.write_bytes(content)
                try:
                    result = parse_report(str(temp))
                    records = result.get("records", [])
                    for r in records:
                        r["property_id"] = pid
                    if records:
                        count = import_lease_expiration(conn, records, str(temp), str(fid))
                        stats["lease_expiration"] += count
                        print(f" ✓ {count} records (via parser)")
                    else:
                        records = parse_lease_expiration_xls(content, pid, name)
                        if records:
                            count = import_lease_expiration(conn, records, str(temp), str(fid))
                            stats["lease_expiration"] += count
                            print(f" ✓ {count} records (custom)")
                        else:
                            print(f" ⚠ 0 records parsed")
                except Exception as e:
                    records = parse_lease_expiration_xls(content, pid, name)
                    if records:
                        count = import_lease_expiration(conn, records, str(temp), str(fid))
                        stats["lease_expiration"] += count
                        print(f" ✓ {count} records (fallback)")
                    else:
                        print(f" ✗ {e}")
                        errors.append(f"{name}/lease_exp: {e}")
                finally:
                    temp.unlink(missing_ok=True)
            else:
                print(" ✗ download failed")
        except Exception as e:
            print(f" ✗ {e}")
            errors.append(f"{name}/lease_exp: {e}")

        # 3. Activity Report (HTML)
        fid = prop["activity"]
        sys.stdout.write(f"  Activity Report (file {fid})...")
        sys.stdout.flush()
        try:
            content = download_file(fid)
            if content:
                records = parse_activity_html(content, pid, name)
                if records:
                    count = import_activity(conn, records, f"file_{fid}", str(fid))
                    stats["activity_report"] += count
                    print(f" ✓ {count} records")
                else:
                    print(f" ⚠ 0 records parsed")
            else:
                print(" ✗ download failed")
        except Exception as e:
            print(f" ✗ {e}")
            errors.append(f"{name}/activity: {e}")

    conn.close()

    # Sync to unified
    print(f"\n{'='*60}")
    print("  SYNCING TO unified.db")
    print(f"{'='*60}")
    import subprocess
    subprocess.run([sys.executable, "-m", "app.db.sync_realpage_to_unified"], cwd=str(SCRIPT_DIR))

    # Summary
    print(f"\n{'='*60}")
    print("  FINAL SUMMARY")
    print(f"{'='*60}")
    for rtype, count in stats.items():
        print(f"  {rtype:30} {count:>5} records")
    print(f"  {'TOTAL':30} {sum(stats.values()):>5} records")

    if errors:
        print(f"\n  Errors ({len(errors)}):")
        for e in errors:
            print(f"    ✗ {e}")


if __name__ == "__main__":
    main()
