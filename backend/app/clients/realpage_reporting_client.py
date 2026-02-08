"""
RealPage Reporting API Client - Pull reports automatically.

This client uses the REST Reporting API to download reports from RealPage.
Requires a Bearer token from an authenticated RealPage session.

Flow:
1. POST /reports/{reportId}/report-instances - Create report instance
2. Extract fileId from instanceId (middle part: xxx-FILEID-xxx)
3. POST /reports/{reportId}/report-instances/{instanceId}/files - Download file

READ-ONLY: This only downloads reports, doesn't modify any data.
"""

import httpx
import json
import base64
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from pathlib import Path


class RealPageReportingClient:
    """
    Client for RealPage Reporting API.
    
    Usage:
        client = RealPageReportingClient(token="your_bearer_token")
        content, filename = await client.download_report(
            report_id=4153,
            report_key="7929C3F8-0BD4-42D7-B537-BD5BE0DD667D",
            property_id="5375283",
            property_name="The Northern",
            start_date="01/01/2026",
            end_date="02/02/2026",
            format="excel"  # or "pdf" or "raw"
        )
    """
    
    BASE_URL = "https://reportingapi.realpage.com/v1"
    
    # Report format codes
    FORMATS = {
        "pdf": "2015",
        "excel": "2016",
        "raw": "2105",
        "html": "561",
    }
    
    def __init__(self, token: str):
        """
        Initialize with a Bearer token from RealPage web session.
        
        Args:
            token: Bearer token (without "Bearer " prefix)
        """
        self.token = token.replace("Bearer ", "") if token.startswith("Bearer ") else token
        self._validate_token()
    
    def _validate_token(self) -> Dict[str, Any]:
        """Decode and validate the JWT token."""
        try:
            parts = self.token.split(".")
            if len(parts) != 3:
                raise ValueError("Invalid JWT format")
            
            payload = parts[1]
            padding = 4 - len(payload) % 4
            if padding != 4:
                payload += "=" * padding
            
            decoded = base64.urlsafe_b64decode(payload)
            self.token_payload = json.loads(decoded)
            
            # Check expiration
            exp_time = datetime.fromtimestamp(self.token_payload.get("exp", 0))
            if exp_time < datetime.now():
                raise ValueError(f"Token expired at {exp_time}")
            
            return self.token_payload
        except Exception as e:
            raise ValueError(f"Token validation failed: {e}")
    
    @property
    def organization(self) -> str:
        """Get organization name from token."""
        return self.token_payload.get("orgName", "Unknown")
    
    @property
    def token_expires_at(self) -> datetime:
        """Get token expiration time."""
        return datetime.fromtimestamp(self.token_payload.get("exp", 0))
    
    @property
    def token_valid_minutes(self) -> float:
        """Get remaining token validity in minutes."""
        return (self.token_expires_at - datetime.now()).total_seconds() / 60
    
    def _get_headers(self) -> Dict[str, str]:
        """Build HTTP headers for API requests."""
        return {
            "accept": "application/json, text/plain, */*",
            "authorization": f"Bearer {self.token}",
            "cache-control": "no-cache",
            "content-type": "application/json",
            "origin": "https://www.realpage.com",
            "referer": "https://www.realpage.com/",
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        }
    
    async def create_report_instance(
        self,
        report_id: int,
        report_key: str,
        property_id: str,
        property_name: str,
        start_date: str,
        end_date: str,
        format: str = "excel",
        city: str = "",
        state: str = "",
        zipcode: str = "",
        country: str = "US",
    ) -> Tuple[str, str]:
        """
        Create a report instance (triggers report generation).
        
        Args:
            report_id: RealPage report ID (e.g., 4153)
            report_key: Report key GUID
            property_id: Property ID
            property_name: Property name
            start_date: Start date (MM/DD/YYYY format)
            end_date: End date (MM/DD/YYYY format)
            format: "pdf", "excel", or "raw"
            city, state, zipcode, country: Optional property details
        
        Returns:
            Tuple of (instance_id, file_id)
        """
        url = f"{self.BASE_URL}/reports/{report_id}/report-instances"
        
        format_code = self.FORMATS.get(format.lower(), "2016")
        format_name = {"2015": "PDF", "2016": "Excel", "2105": "Raw Data", "561": "HTML"}.get(format_code, "Excel")
        
        payload = {
            "reportKey": report_key,
            "sourceId": "OS",
            "scheduledType": 1,
            "scheduledDate": "",
            "scheduledTime": "",
            "scheduleDateTime": None,
            "reportFormat": format_code,
            "reportFormatName": format_name,
            "emaiTo": "",
            "properties": [property_id],
            "propertyDetailList": [{
                "propertyId": property_id,
                "propertyName": property_name,
                "city": city,
                "state": state,
                "zipcode": zipcode,
                "country": country,
            }],
            "parameters": [
                {"name": "Startdate", "label": start_date, "value": start_date},
                {"name": "Enddate", "label": end_date, "value": end_date},
            ],
            "users": [],
            "ReportFormatList": [
                {"text": "PDF", "value": "2015", "id": "option-pdf"},
                {"text": "Excel", "value": "2016", "id": "option-excel"},
                {"text": "Raw Data", "value": "2105", "id": "option-raw"},
            ],
            "cloudServiceAccountId": None,
        }
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, headers=self._get_headers(), json=payload)
            response.raise_for_status()
            
            data = response.json()
            instance_id = data.get("instanceId")
            
            if not instance_id:
                raise ValueError(f"No instanceId in response: {data}")
            
            # Extract file_id from instance_id (middle part: xxx-FILEID-xxx)
            parts = instance_id.split("-")
            if len(parts) != 3:
                raise ValueError(f"Unexpected instanceId format: {instance_id}")
            
            file_id = parts[1]  # Middle part is the fileId
            
            return instance_id, file_id
    
    async def download_report_file(
        self,
        report_id: int,
        report_key: str,
        instance_id: str,
        file_id: str,
        property_name: str,
    ) -> bytes:
        """
        Download the report file content.
        
        Args:
            report_id: RealPage report ID
            report_key: Report key GUID
            instance_id: Instance ID from create_report_instance
            file_id: File ID extracted from instance_id
            property_name: Property name
        
        Returns:
            Raw file content (bytes)
        """
        url = f"{self.BASE_URL}/reports/{report_id}/report-instances/{instance_id}/files"
        
        payload = {
            "reportId": report_id,
            "parameters": f"reportKey={report_key}&sourceId=OS&fileID={file_id}&View=2",
            "fileId": file_id,
            "propertyName": property_name,
        }
        
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers=self._get_headers(), json=payload)
            response.raise_for_status()
            
            return response.content
    
    async def download_report(
        self,
        report_id: int,
        report_key: str,
        property_id: str,
        property_name: str,
        start_date: str,
        end_date: str,
        format: str = "excel",
        output_path: Optional[str] = None,
        **property_details,
    ) -> Tuple[bytes, str]:
        """
        Full workflow: Create instance and download report.
        
        Args:
            report_id: RealPage report ID (e.g., 4153)
            report_key: Report key GUID
            property_id: Property ID
            property_name: Property name
            start_date: Start date (MM/DD/YYYY format)
            end_date: End date (MM/DD/YYYY format)
            format: "pdf", "excel", or "raw"
            output_path: Optional path to save the file
            **property_details: Additional property info (city, state, etc.)
        
        Returns:
            Tuple of (file_content, suggested_filename)
        """
        # Step 1: Create report instance
        instance_id, file_id = await self.create_report_instance(
            report_id=report_id,
            report_key=report_key,
            property_id=property_id,
            property_name=property_name,
            start_date=start_date,
            end_date=end_date,
            format=format,
            **property_details,
        )
        
        # Step 2: Download the file
        content = await self.download_report_file(
            report_id=report_id,
            report_key=report_key,
            instance_id=instance_id,
            file_id=file_id,
            property_name=property_name,
        )
        
        # Generate filename
        ext = {"pdf": ".pdf", "excel": ".xlsx", "raw": ".csv"}.get(format.lower(), ".xlsx")
        safe_name = property_name.replace(" ", "_").replace("/", "-")
        date_str = datetime.now().strftime("%Y%m%d")
        filename = f"report_{safe_name}_{date_str}{ext}"
        
        # Save if path provided
        if output_path:
            path = Path(output_path)
            if path.is_dir():
                path = path / filename
            path.write_bytes(content)
        
        return content, filename


# Known report configurations
KNOWN_REPORTS = {
    "activity_log": {
        "report_id": 4153,
        "report_key": "7929C3F8-0BD4-42D7-B537-BD5BE0DD667D",
        "description": "Activity Log Report",
        "formats": {"pdf": "2015", "excel": "2016", "raw": "2105", "html": "561"},
    },
    "form_type_report": {
        "report_id": None,  # Need to find
        "report_key": "84C36518-D324-4124-9016-54E68931B5F6",
        "description": "Form Type Report (FormType: ALL)",
        "formats": {"pdf": "1633", "excel": "1666"},
        "parameters": [{"name": "FormTypeid", "label": "ALL", "value": "ALL"}],
    },
    "issues_report": {
        "report_id": 4188,
        "report_key": "0F1AC604-DDD3-4547-8C26-46435FEFFDD5",
        "description": "Issues Report (with date range, sort by unit)",
        "formats": {"pdf": "2081", "excel": "2082"},
        "parameters": [
            {"name": "StartDate", "label": "02/01/2026", "value": "02/01/2026"},
            {"name": "EndDate", "label": "02/03/2026", "value": "02/03/2026"},
            {"name": "IncludeDisabledIssues", "label": "30", "value": "30"},
            {"name": "SortBy", "label": "Unit", "value": "unitNumber"},
            {"name": "IncludeParam", "label": "Yes", "value": "1"},
        ],
    },
}
