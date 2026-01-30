"""
API endpoints for Excel report imports.
"""

import os
import tempfile
from typing import Optional
from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from pydantic import BaseModel
from typing import List, Dict, Any

from app.services.excel_importer import ExcelImportService, ReportType


router = APIRouter(prefix="/imports", tags=["imports"])


class ImportResponse(BaseModel):
    success: bool
    report_type: str
    property_name: str
    date_range: str
    records_imported: int
    message: str


class ImportHistoryItem(BaseModel):
    id: int
    file_name: Optional[str]
    report_type: str
    property_name: str
    records_imported: int
    status: str
    message: str
    imported_at: str


class LeasingActivityResponse(BaseModel):
    by_consultant: List[Dict[str, Any]]
    by_day_of_week: List[Dict[str, Any]]
    totals: Optional[Dict[str, Any]]


@router.post("/upload", response_model=ImportResponse)
async def upload_report(
    file: UploadFile = File(...),
    property_id: Optional[str] = Query(None, description="Property ID to associate with import")
):
    """
    Upload and import a RealPage Excel report.
    
    Supported report types:
    - Leasing Activity Summary (.xls/.xlsx)
    - Prospect Detail Report (.xls/.xlsx)
    - Traffic Summary (.xls/.xlsx)
    
    The report type is auto-detected from the file content.
    """
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    allowed_extensions = ['.xls', '.xlsx']
    file_ext = os.path.splitext(file.filename)[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Save to temp file
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Import the file
        service = ExcelImportService()
        result = service.import_file(tmp_path, property_id)
        
        return ImportResponse(
            success=result.success,
            report_type=result.report_type.value,
            property_name=result.property_name,
            date_range=result.date_range,
            records_imported=result.records_imported,
            message=result.message
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Import failed: {str(e)}")
    finally:
        # Cleanup temp file
        if 'tmp_path' in locals():
            try:
                os.unlink(tmp_path)
            except:
                pass


@router.get("/history", response_model=List[ImportHistoryItem])
async def get_import_history(
    property_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200)
):
    """Get history of imported files."""
    service = ExcelImportService()
    history = service.get_import_history(property_id, limit)
    
    return [
        ImportHistoryItem(
            id=item.get('id', 0),
            file_name=item.get('file_name'),
            report_type=item.get('report_type', 'unknown'),
            property_name=item.get('property_name', ''),
            records_imported=item.get('records_imported', 0),
            status=item.get('status', ''),
            message=item.get('message', ''),
            imported_at=item.get('imported_at', '')
        )
        for item in history
    ]


@router.get("/leasing-activity", response_model=LeasingActivityResponse)
async def get_leasing_activity(
    property_id: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None, description="Filter by report start date (MM/DD/YYYY)"),
    end_date: Optional[str] = Query(None, description="Filter by report end date (MM/DD/YYYY)")
):
    """
    Get imported leasing activity data.
    
    Returns data grouped by:
    - by_consultant: Metrics per leasing consultant
    - by_day_of_week: Metrics per day of week
    - totals: Summary totals
    """
    service = ExcelImportService()
    data = service.get_leasing_activity(property_id, start_date, end_date)
    
    if 'error' in data:
        raise HTTPException(status_code=500, detail=data['error'])
    
    return LeasingActivityResponse(
        by_consultant=data.get('by_consultant', []),
        by_day_of_week=data.get('by_day_of_week', []),
        totals=data.get('totals')
    )


@router.get("/supported-reports")
async def get_supported_reports():
    """Get list of supported report types."""
    return {
        "supported_reports": [
            {
                "type": ReportType.LEASING_ACTIVITY_SUMMARY.value,
                "name": "Leasing Activity Summary",
                "description": "RealPage OneSite Prospect Management report with leads, tours, applications, and lease metrics",
                "sections": ["by_consultant", "by_day_of_week", "totals"]
            },
            {
                "type": ReportType.PROSPECT_DETAIL.value,
                "name": "Prospect Detail Report",
                "description": "Individual prospect/guest card records (coming soon)",
                "sections": ["prospects"]
            },
            {
                "type": ReportType.TRAFFIC_SUMMARY.value,
                "name": "Traffic Summary",
                "description": "Traffic and marketing source summary (coming soon)",
                "sections": ["by_source", "totals"]
            }
        ],
        "supported_formats": [".xls", ".xlsx"],
        "max_file_size_mb": 10
    }
