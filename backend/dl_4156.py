#!/usr/bin/env python3
"""One-shot script to download Report 4156 for Nexus East, Parkside, and Ridian.
Creates instances, polls, downloads, parses, and imports into realpage_raw.db.
"""
import httpx, time, json, sqlite3, os, sys
from pathlib import Path

TOKEN = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("RP_TOKEN", "")
if not TOKEN:
    print("Usage: python dl_4156.py <bearer_token>")
    sys.exit(1)

BASE = "https://reportingapi.realpage.com/v1"
HEADERS = {
    "authorization": f"Bearer {TOKEN}",
    "content-type": "application/json",
    "origin": "https://www.realpage.com",
    "referer": "https://www.realpage.com/",
    "cache-control": "no-cache",
    "pragma": "no-cache",
}

PROPERTIES = {
    "5472172": "Nexus East",
    "5536211": "Parkside at Round Rock",
    "5446271": "Ridian",
}

DL_DIR = Path("downloads/4156")
DL_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path("app/db/data/realpage_raw.db")

# ── Step 1: Create report instances ──────────────────────────────────────
def create_instance(prop_id, prop_name):
    payload = {
        "reportKey": "05E163C2-14E9-4A4E-B71F-328717ABF599",
        "sourceId": "OS",
        "scheduledType": 1,
        "scheduledDate": "",
        "scheduledTime": "",
        "scheduleDateTime": None,
        "reportFormat": "1979",
        "reportFormatName": "Excel",
        "emaiTo": "",
        "properties": [prop_id],
        "propertyDetailList": [{"propertyId": prop_id, "propertyName": prop_name, "country": "US"}],
        "parameters": [
            {"name": "IPVC_LEABEGINDATE", "label": "02/01/2026", "value": "02/01/2026"},
            {"name": "IPVC_LEAENDDATE", "label": "06/01/2026", "value": "06/01/2026"},
            {"name": "IPVC_SUBPROPERTIES", "label": "ALL", "value": "ALL"},
            {"name": "IPVC_AlreadyRenewed", "label": "Yes", "value": "Yes"},
            {"name": "IPVC_MTM", "label": "No", "value": "No"},
            {"name": "IPVC_SORTORDER", "label": "Unit Number", "value": "Unit Number"},
        ],
        "users": [],
        "cloudServiceAccountId": None,
    }
    with httpx.Client(timeout=30) as client:
        resp = client.post(f"{BASE}/reports/4156/report-instances", headers=HEADERS, json=payload)
    print(f"  Create {prop_name} ({prop_id}): HTTP {resp.status_code}")
    if resp.status_code == 200:
        data = resp.json()
        inst_id = data.get("reportInstanceId") or data.get("instanceId") or data.get("id")
        print(f"    Instance: {inst_id}")
        print(f"    Response keys: {list(data.keys())}")
        return data
    else:
        print(f"    Error: {resp.text[:300]}")
        return None

# ── Step 2: Poll for file IDs via /v1/my/report-instances ────────────────
def poll_for_files(max_wait=120):
    """Poll the report-instances list until all 3 properties have status=3 (completed)."""
    from datetime import datetime, timedelta
    today = datetime.utcnow()
    body = {
        "pageSize": 200,
        "pageNumber": 1,
        "searchText": "",
        "reportProductList": [],
        "reportAreaList": [],
        "startDate": (today - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S.000Z"),
        "endDate": (today + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.999Z"),
        "favorite": False,
        "PropertiesList": [],
        "OrderBy": "CreatedDate",
        "OrderByDesc": True,
    }
    
    found = {}
    for attempt in range(max_wait // 5):
        with httpx.Client(timeout=30) as client:
            resp = client.post(f"{BASE}/my/report-instances", headers=HEADERS, json=body)
        if resp.status_code != 200:
            print(f"  Poll error: HTTP {resp.status_code} - {resp.text[:200]}")
            time.sleep(5)
            continue
        
        data = resp.json()
        items = data if isinstance(data, list) else data.get("items", data.get("data", []))
        
        for item in items:
            rname = item.get("reportName", "")
            pname = item.get("propertyName", "")
            status = item.get("status", 0)
            file_id = item.get("reportFileId")
            inst_id = item.get("sourceReportInstanceId") or item.get("reportInstanceId")
            report_id = item.get("reportId")
            
            # Only report 4156
            if report_id != 4156 and "Lease Expiration" not in rname:
                continue
            
            # Match our properties
            for pid, expected_name in PROPERTIES.items():
                if expected_name.lower() in (pname or "").lower() or pid in str(inst_id):
                    if status == 3 and file_id:
                        if pid not in found:
                            found[pid] = {"file_id": str(file_id), "instance_id": str(inst_id), "property_name": pname}
                            print(f"  ✓ {pname} ready: file_id={file_id}, instance={inst_id}")
        
        if len(found) >= len(PROPERTIES):
            print(f"  All {len(found)} files ready!")
            return found
        
        pending = [n for pid, n in PROPERTIES.items() if pid not in found]
        print(f"  Waiting... {len(found)}/{len(PROPERTIES)} ready (pending: {', '.join(pending)})")
        time.sleep(5)
    
    return found

# ── Step 3: Download file ────────────────────────────────────────────────
def download_file(prop_id, info):
    file_id = info["file_id"]
    instance_id = info["instance_id"]
    prop_name = info["property_name"]
    
    dl_body = {
        "reportId": 4156,
        "parameters": f"reportKey=05E163C2-14E9-4A4E-B71F-328717ABF599&sourceId=OS&fileID={file_id}&View=2",
        "fileId": file_id,
        "propertyName": prop_name,
    }
    with httpx.Client(timeout=60) as client:
        resp = client.post(
            f"{BASE}/reports/4156/report-instances/{instance_id}/files",
            headers=HEADERS, json=dl_body
        )
    
    out_path = DL_DIR / f"4156_{prop_id}_{prop_name.replace(' ', '_')}.xls"
    if resp.status_code == 200 and len(resp.content) > 500:
        out_path.write_bytes(resp.content)
        print(f"  Downloaded {prop_name}: {len(resp.content)} bytes → {out_path}")
        return out_path
    else:
        print(f"  Download failed {prop_name}: HTTP {resp.status_code}, {len(resp.content)} bytes")
        print(f"    Content preview: {resp.content[:200]}")
        return None

# ── Step 4: Parse and import ─────────────────────────────────────────────
def parse_and_import(file_path, prop_id, prop_name):
    sys.path.insert(0, str(Path(__file__).parent))
    from report_parsers import parse_report
    from import_reports import import_lease_expiration_renewal
    
    file_id_str = f"4156_{prop_id}_manual"
    result = parse_report(str(file_path), property_id=prop_id, file_id=file_id_str, report_type_hint="lease_expiration_renewal")
    records = result.get("records", [])
    
    detail = [r for r in records if r.get("_type") == "detail"]
    summary = [r for r in records if r.get("_type") == "summary"]
    print(f"  Parsed {prop_name}: {len(detail)} detail + {len(summary)} summary records")
    
    if not records:
        print(f"  ⚠ No records parsed! report_type={result.get('report_type')}, error={result.get('error')}")
        return 0
    
    conn = sqlite3.connect(str(DB_PATH))
    imported = import_lease_expiration_renewal(conn, records, str(file_path), file_id_str)
    conn.close()
    print(f"  Imported {imported} records for {prop_name}")
    return imported

# ── Main ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("Report 4156 - Lease Expiration Renewal Detail")
    print("=" * 60)
    
    # Step 1: Create instances
    print("\n── Creating report instances ──")
    for pid, pname in PROPERTIES.items():
        create_instance(pid, pname)
    
    # Step 2: Poll for files
    print("\n── Polling for completed files ──")
    files = poll_for_files(max_wait=120)
    
    if not files:
        print("\n⚠ No files found. Exiting.")
        sys.exit(1)
    
    # Step 3: Download
    print("\n── Downloading files ──")
    downloaded = {}
    for pid, info in files.items():
        path = download_file(pid, info)
        if path:
            downloaded[pid] = path
    
    # Step 4: Parse and import
    print("\n── Parsing and importing ──")
    total = 0
    for pid, path in downloaded.items():
        total += parse_and_import(path, pid, PROPERTIES[pid])
    
    print(f"\n{'=' * 60}")
    print(f"Done! {len(downloaded)} files downloaded, {total} total records imported.")
    
    # Quick verification
    conn = sqlite3.connect(str(DB_PATH))
    c = conn.cursor()
    for pid, pname in PROPERTIES.items():
        c.execute("SELECT COUNT(*) FROM realpage_lease_expiration_renewal WHERE property_id = ?", (pid,))
        cnt = c.fetchone()[0]
        c.execute("SELECT decision, COUNT(*) FROM realpage_lease_expiration_renewal WHERE property_id = ? GROUP BY decision", (pid,))
        breakdown = dict(c.fetchall())
        print(f"  {pname} ({pid}): {cnt} records — {breakdown}")
    conn.close()
