#!/usr/bin/env python3
"""
RealPage Single Report Downloader

Usage:
    python3 download_report.py --file-id 8848847 --report rent_roll --property "The Avant"
    
    Or paste the full download curl:
    python3 download_report.py --curl "curl 'https://...files' ... --data-raw '{...}'"
"""

import json
import re
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

# Load token
with open(Path(__file__).parent / "realpage_token.json") as f:
    token_data = json.load(f)
    TOKEN = token_data["access_token"]
    if TOKEN.startswith("Bearer "):
        TOKEN = TOKEN[7:]

# Load report definitions
with open(Path(__file__).parent / "report_definitions.json") as f:
    DEFINITIONS = json.load(f)


def download_with_file_id(file_id: str, report_key: str, report_id: int, 
                          instance_id: str, property_name: str, output_dir: Path) -> bool:
    """Download report using file ID."""
    
    url = f"https://reportingapi.realpage.com/v1/reports/{report_id}/report-instances/{instance_id}/files"
    
    payload = {
        "reportId": report_id,
        "parameters": f"reportKey={report_key}&sourceId=OS&fileID={file_id}&View=2",
        "fileId": str(file_id),
        "propertyName": property_name
    }
    
    # Use curl for reliability
    cmd = [
        "curl", "-s", url,
        "-H", f"authorization: Bearer {TOKEN}",
        "-H", "content-type: application/json",
        "-H", "origin: https://www.realpage.com",
        "--data-raw", json.dumps(payload),
        "-w", "\n%{http_code},%{size_download}"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=False)
    
    # Parse response
    output = result.stdout
    if not output:
        print(f"Error: No response")
        return False
    
    # Last line is status,size
    lines = output.split(b'\n')
    status_line = lines[-1].decode()
    content = b'\n'.join(lines[:-1])
    
    try:
        status, size = status_line.split(',')
        size = int(size)
    except:
        print(f"Error parsing response")
        return False
    
    if status == "200" and size > 1000:
        filename = f"{property_name.replace(' ', '_')}_{file_id}.xlsx"
        filepath = output_dir / filename
        filepath.write_bytes(content)
        print(f"✓ Downloaded: {filename} ({size:,} bytes)")
        return True
    else:
        print(f"✗ Failed: HTTP {status}, size {size}")
        return False


def parse_curl(curl_string: str) -> dict:
    """Extract parameters from a curl command."""
    
    # Extract URL
    url_match = re.search(r"curl\s+'([^']+)'", curl_string)
    if not url_match:
        return None
    url = url_match.group(1)
    
    # Extract report_id and instance_id from URL
    url_match = re.search(r"/reports/(\d+)/report-instances/([^/]+)/files", url)
    if not url_match:
        return None
    
    report_id = int(url_match.group(1))
    instance_id = url_match.group(2)
    
    # Extract data-raw payload
    data_match = re.search(r"--data-raw\s+'(\{[^']+\})'", curl_string)
    if not data_match:
        return None
    
    payload = json.loads(data_match.group(1))
    
    return {
        "report_id": report_id,
        "instance_id": instance_id,
        "file_id": payload.get("fileId"),
        "property_name": payload.get("propertyName"),
        "report_key": re.search(r"reportKey=([^&]+)", payload.get("parameters", "")).group(1) if "reportKey" in payload.get("parameters", "") else None
    }


def main():
    parser = argparse.ArgumentParser(description="Download RealPage report")
    parser.add_argument("--curl", help="Paste the full download curl command")
    parser.add_argument("--file-id", help="File ID to download")
    parser.add_argument("--report", help="Report type (box_score, rent_roll, etc.)")
    parser.add_argument("--property", help="Property name")
    parser.add_argument("--instance-id", help="Instance ID (from report creation)")
    parser.add_argument("--output", default="./reports", help="Output directory")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    output_dir.mkdir(exist_ok=True)
    
    if args.curl:
        # Parse curl command
        params = parse_curl(args.curl)
        if not params:
            print("Error: Could not parse curl command")
            return
        
        print(f"Parsed curl: file_id={params['file_id']}, property={params['property_name']}")
        
        download_with_file_id(
            params["file_id"],
            params["report_key"],
            params["report_id"],
            params["instance_id"],
            params["property_name"],
            output_dir
        )
    
    elif args.file_id and args.report:
        # Direct download with file ID
        report_def = DEFINITIONS["reports"].get(args.report)
        if not report_def:
            print(f"Error: Unknown report '{args.report}'")
            print("Available reports:", list(DEFINITIONS["reports"].keys()))
            return
        
        property_name = args.property or "Unknown"
        instance_id = args.instance_id or "0-0-0"
        
        download_with_file_id(
            args.file_id,
            report_def["report_key"],
            report_def["report_id"],
            instance_id,
            property_name,
            output_dir
        )
    
    else:
        print("Usage:")
        print("  python3 download_report.py --curl '<paste curl here>'")
        print("  python3 download_report.py --file-id 8848847 --report rent_roll --property 'The Avant'")


if __name__ == "__main__":
    main()
