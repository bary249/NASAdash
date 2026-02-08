"""
Master Script: Download, Parse, and Save RealPage Reports
Automates the complete workflow for RealPage report integration.

NOTE: File ID discovery is complex - the UI uses SignalR/WebSocket.
Current workaround: Use subprocess with curl for reliable downloads.
"""
import httpx
import json
import asyncio
import base64
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
import time
import pandas as pd
from generic_report_parser import RealPageReportParser

# Load token
with open('realpage_token.json') as f:
    data = json.load(f)
    token = data['access_token']

if token.startswith("Bearer "):
    token = token[7:]

BASE_URL = "https://reportingapi.realpage.com/v1"

# Report configurations (from successful downloads)
REPORT_CONFIGS = {
    "Box Score": {
        "report_id": 4238,
        "report_key": "446266C0-D572-4D8A-A6DA-310C0AE61037",
        "property_id": "4779341",
        "property_name": "Aspire 7th and Grant",
        "payload": {
            "reportKey": "446266C0-D572-4D8A-A6DA-310C0AE61037",
            "sourceId": "OS",
            "scheduledType": 1,
            "scheduledDate": "",
            "scheduledTime": "",
            "scheduleDateTime": None,
            "reportFormat": "1683",
            "reportFormatName": "Excel",
            "emaiTo": "",
            "properties": ["4779341"],
            "propertyDetailList": [{
                "propertyId": "4779341",
                "propertyName": "Aspire 7th and Grant",
                "city": "Denver",
                "state": "CO",
                "zipcode": "80203-3789",
                "country": "US"
            }],
            "parameters": [
                {"name": "SubProperty", "label": "ALL", "value": "ALL"},
                {"name": "IncludeActivitiesDuring", "label": "Date Range", "value": "Date Range"},
                {"name": "Start_Date", "label": "02/01/2026", "value": "02/01/2026"},
                {"name": "End_Date", "label": "02/03/2026", "value": "02/03/2026"},
                {"name": "ShowUnitDesignations", "label": "No", "value": "Yes"},
                {"name": "Scheduling_Period", "value": "#PropertyDateMinus6Days#"}
            ],
            "users": [],
            "ReportFormatList": [
                {"text": "PDF", "value": "1682", "id": "option-1eecb348-5304-426e-b604-07fc9a89d91e"},
                {"text": "Excel", "value": "1683", "id": "option-c81e2260-6423-4529-a7fd-01e53eeeab4d"}
            ],
            "cloudServiceAccountId": None
        }
    },
    "Box Score - Edison at RiNo": {
        "report_id": 4238,
        "report_key": "446266C0-D572-4D8A-A6DA-310C0AE61037",
        "property_id": "4248319",
        "property_name": "Edison at RiNo",
        "payload": {
            "reportKey": "446266C0-D572-4D8A-A6DA-310C0AE61037",
            "sourceId": "OS",
            "scheduledType": 1,
            "scheduledDate": "",
            "scheduledTime": "",
            "scheduleDateTime": None,
            "reportFormat": "1683",
            "reportFormatName": "Excel",
            "emaiTo": "",
            "properties": ["4248319"],
            "propertyDetailList": [{
                "propertyId": "4248319",
                "propertyName": "Edison at RiNo",
                "city": "Denver",
                "state": "CO",
                "zipcode": "80216-5014",
                "country": "US"
            }],
            "parameters": [
                {"name": "SubProperty", "label": "ALL", "value": "ALL"},
                {"name": "IncludeActivitiesDuring", "label": "Date Range", "value": "Date Range"},
                {"name": "Start_Date", "label": "01/01/2026", "value": "01/01/2026"},
                {"name": "End_Date", "label": "02/04/2026", "value": "02/04/2026"},
                {"name": "ShowUnitDesignations", "label": "No", "value": "Yes"},
                {"name": "Scheduling_Period", "value": "#PropertyDateMinus6Days#"}
            ],
            "users": [],
            "ReportFormatList": [
                {"text": "PDF", "value": "1682", "id": "option-c21e666f-474d-44cc-825c-1c0e426978c6"},
                {"text": "Excel", "value": "1683", "id": "option-43c176cc-aff1-4be2-a390-25a9734bb746"}
            ],
            "cloudServiceAccountId": None
        }
    },
    "Box Score - Ridian": {
        "report_id": 4238,
        "report_key": "446266C0-D572-4D8A-A6DA-310C0AE61037",
        "property_id": "5446271",
        "property_name": "Ridian",
        "payload": {
            "reportKey": "446266C0-D572-4D8A-A6DA-310C0AE61037",
            "sourceId": "OS",
            "scheduledType": 1,
            "scheduledDate": "",
            "scheduledTime": "",
            "scheduleDateTime": None,
            "reportFormat": "1683",
            "reportFormatName": "Excel",
            "emaiTo": "",
            "properties": ["5446271"],
            "propertyDetailList": [{
                "propertyId": "5446271",
                "propertyName": "Ridian",
                "city": "Denver",
                "state": "CO",
                "zipcode": "80211-3243",
                "country": "US"
            }],
            "parameters": [
                {"name": "SubProperty", "label": "ALL", "value": "ALL"},
                {"name": "IncludeActivitiesDuring", "label": "Date Range", "value": "Date Range"},
                {"name": "Start_Date", "label": "01/01/2026", "value": "01/01/2026"},
                {"name": "End_Date", "label": "02/04/2026", "value": "02/04/2026"},
                {"name": "ShowUnitDesignations", "label": "No", "value": "Yes"},
                {"name": "Scheduling_Period", "value": "#PropertyDateMinus6Days#"}
            ],
            "users": [],
            "ReportFormatList": [
                {"text": "PDF", "value": "1682", "id": "option-6d43628e-0627-4a23-bc5e-2b34984e4f84"},
                {"text": "Excel", "value": "1683", "id": "option-5e8868c2-bee3-413e-8e07-2f7176e83a29"}
            ],
            "cloudServiceAccountId": None
        }
    },
    # Add more report configurations as we discover them
}

class RealPageReportDownloader:
    """Handles downloading RealPage reports."""
    
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "accept": "application/json, text/plain, */*",
            "accept-language": "en-US,en;q=0.9",
            "cache-control": "no-cache",
            "expires": "Sat, 01 Jan 2000 00:00:00 GMT",
            "origin": "https://www.realpage.com",
            "pragma": "no-cache",
            "priority": "u=1, i",
            "referer": "https://www.realpage.com/",
            "sec-ch-ua": '"Chromium";v="143", "Not A(Brand";v="24"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"macOS"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36"
        }
        self.parser = RealPageReportParser()
    
    async def download_report(self, report_name: str, config: dict) -> dict:
        """
        Download a single report.
        
        Args:
            report_name: Name of the report
            config: Report configuration
            
        Returns:
            Dictionary with download results
        """
        result = {
            "report_name": report_name,
            "status": "pending",
            "file_path": None,
            "parsed_data": None,
            "error": None
        }
        
        try:
            async with httpx.AsyncClient(headers=self.headers, timeout=30.0) as client:
                # Step 1: Create report instance
                print(f"\n📋 Creating {report_name} report instance...")
                report_id = config["report_id"]
                payload = config["payload"]
                
                # Update dates to use exact UI dates
                end_date = "02/04/2026"  # Exact date from UI
                start_date = "01/01/2026"
                
                print(f"   Using date range: {start_date} to {end_date}")
                
                for param in payload.get("parameters", []):
                    if param["name"] == "Start_Date":
                        param["value"] = start_date
                        param["label"] = start_date
                    elif param["name"] == "End_Date":
                        param["value"] = end_date
                        param["label"] = end_date
                    elif param["name"] == "ShowUnitDesignations":
                        param["value"] = "No"  # UI sends "No", not "Yes"
                        param["label"] = "No"
                
                print(f"   Payload dates: {[p for p in payload.get('parameters', []) if 'Date' in p['name']]}")
                
                resp = await client.post(f"{BASE_URL}/reports/{report_id}/report-instances", json=payload)
                
                if resp.status_code != 200:
                    result["error"] = f"Failed to create instance: {resp.status_code} - {resp.text[:200]}"
                    result["status"] = "failed"
                    return result
                
                instance_data = resp.json()
                instance_id = instance_data.get('instanceId')
                print(f"   ✅ Instance created: {instance_id}")
                
                # Step 2: Wait for processing
                print("   ⏳ Waiting for report generation...")
                time.sleep(5)
                
                # Step 3: Download file using curl (more reliable)
                # Note: File ID discovery is complex in RealPage - UI uses SignalR
                # For now, we try with the instance file ID which sometimes works
                file_id = instance_id.split('-')[1] if instance_id and '-' in instance_id else "0"
                
                print(f"   📥 Downloading report file via curl...")
                
                download_url = f"{BASE_URL}/reports/{report_id}/report-instances/{instance_id}/files"
                download_payload = {
                    "reportId": report_id,
                    "parameters": f"reportKey={config['report_key']}&sourceId=OS&fileID={file_id}&View=2",
                    "fileId": file_id,
                    "propertyName": config["property_name"]
                }
                
                # Use curl subprocess for reliable downloads
                curl_cmd = [
                    'curl', '-s', download_url,
                    '-H', f'Authorization: Bearer {token}',
                    '-H', 'Content-Type: application/json',
                    '-H', 'accept: application/json, text/plain, */*',
                    '-H', 'origin: https://www.realpage.com',
                    '-H', 'referer: https://www.realpage.com/',
                    '--data-raw', json.dumps(download_payload)
                ]
                
                try:
                    curl_result = subprocess.run(curl_cmd, capture_output=True, timeout=30)
                    content = curl_result.stdout
                    
                    if not content or b'error' in content.lower()[:100]:
                        # Fallback to httpx
                        resp2 = await client.post(download_url, json=download_payload)
                        content = resp2.content
                except Exception as e:
                    print(f"   ⚠️ Curl failed, using httpx: {e}")
                    resp2 = await client.post(download_url, json=download_payload)
                    content = resp2.content
                
                if not content:
                    result["error"] = "No content in download response"
                    result["status"] = "failed"
                    return result
                
                # Step 4: Save the file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"{report_name.lower().replace(' ', '_')}_{timestamp}.xlsx"
                file_path = Path(filename)
                file_path.write_bytes(content)
                
                print(f"   ✅ Downloaded: {filename} ({len(content):,} bytes)")
                result["file_path"] = str(file_path)
                
                # Step 5: Parse the file
                print("   📊 Parsing report data...")
                parsed_data = self.parser.parse_report(str(file_path), "Box Score")  # Use "Box Score" as the type
                
                if "error" not in parsed_data:
                    # Save parsed data
                    json_path = file_path.with_suffix('.json')
                    with open(json_path, 'w') as f:
                        json.dump(parsed_data, f, indent=2, default=str)
                    
                    result["parsed_data"] = parsed_data
                    result["status"] = "completed"
                    print(f"   ✅ Parsed data saved: {json_path}")
                else:
                    result["error"] = f"Parsing failed: {parsed_data['error']}"
                    result["status"] = "partial"
                
                return result
                
        except Exception as e:
            result["error"] = f"Unexpected error: {str(e)}"
            result["status"] = "failed"
            return result
    
    async def download_all_reports(self, report_names: list = None) -> dict:
        """
        Download multiple reports.
        
        Args:
            report_names: List of report names to download (default: all configured)
            
        Returns:
            Dictionary with all download results
        """
        if report_names is None:
            report_names = ["Box Score - Ridian"]  # Test Ridian now
        
        print(f"\n{'='*60}")
        print(f"🚀 Starting RealPage Report Download")
        print(f"   Reports: {', '.join(report_names)}")
        print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        results = {
            "session_id": datetime.now().strftime("%Y%m%d_%H%M%S"),
            "timestamp": datetime.now().isoformat(),
            "reports": {},
            "summary": {
                "total": len(report_names),
                "completed": 0,
                "failed": 0,
                "partial": 0
            }
        }
        
        # Download each report
        for report_name in report_names:
            if report_name not in REPORT_CONFIGS:
                print(f"\n❌ Unknown report: {report_name}")
                continue
            
            config = REPORT_CONFIGS[report_name]
            result = await self.download_report(report_name, config)
            results["reports"][report_name] = result
            
            # Update summary
            results["summary"][result["status"]] += 1
        
        # Save session summary
        session_file = f"report_session_{results['session_id']}.json"
        with open(session_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"📊 Download Summary")
        print(f"   Total reports: {results['summary']['total']}")
        print(f"   Completed: ✅ {results['summary']['completed']}")
        print(f"   Partial: ⚠️ {results['summary']['partial']}")
        print(f"   Failed: ❌ {results['summary']['failed']}")
        print(f"   Session saved: {session_file}")
        print(f"{'='*60}")
        
        return results

async def main():
    """Main execution function."""
    downloader = RealPageReportDownloader()
    
    # Download all configured reports
    results = await downloader.download_all_reports()
    
    # Create master summary
    master_summary = {
        "last_update": datetime.now().isoformat(),
        "available_reports": list(REPORT_CONFIGS.keys()),
        "recent_sessions": []
    }
    
    # Load existing master summary if exists
    master_file = Path("realpage_reports_master.json")
    if master_file.exists():
        try:
            existing = json.loads(master_file.read_text())
            master_summary["recent_sessions"] = existing.get("recent_sessions", [])[:4]  # Keep last 5
        except:
            pass
    
    # Add current session
    master_summary["recent_sessions"].insert(0, {
        "session_id": results["session_id"],
        "timestamp": results["timestamp"],
        "summary": results["summary"]
    })
    
    # Save master summary
    with open(master_file, 'w') as f:
        json.dump(master_summary, f, indent=2, default=str)
    
    print(f"\n✅ Master summary updated: {master_file}")

if __name__ == "__main__":
    asyncio.run(main())
