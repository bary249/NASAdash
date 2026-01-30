"""
Excel Importer Service for RealPage Reports.

Parses scheduled RealPage Excel reports and imports data into the database.
Supports multiple report types:
- Leasing Activity Summary
- Prospect Detail Report
- Traffic Summary
"""

import pandas as pd
import sqlite3
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from app.db.schema import UNIFIED_DB_PATH, get_connection


class ReportType(str, Enum):
    LEASING_ACTIVITY_SUMMARY = "leasing_activity_summary"
    LEASE_SUMMARY = "lease_summary"
    PROSPECT_DETAIL = "prospect_detail"
    TRAFFIC_SUMMARY = "traffic_summary"
    UNKNOWN = "unknown"


@dataclass
class ImportResult:
    """Result of an import operation."""
    success: bool
    report_type: ReportType
    property_name: str
    date_range: str
    records_imported: int
    message: str
    data: Optional[Dict[str, Any]] = None


class RealPageReportParser:
    """Parser for RealPage Excel reports."""
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.df_raw: Optional[pd.DataFrame] = None
        self.report_type: ReportType = ReportType.UNKNOWN
        self.metadata: Dict[str, str] = {}
        
    def detect_report_type(self) -> ReportType:
        """Detect the type of RealPage report based on content."""
        if self.df_raw is None:
            self._load_raw()
            
        # Convert first few rows to string for detection
        header_text = self.df_raw.iloc[:15].astype(str).values.flatten()
        header_str = ' '.join([str(x) for x in header_text if str(x) != 'nan'])
        
        if 'LEASING ACTIVITY SUMMARY' in header_str:
            self.report_type = ReportType.LEASING_ACTIVITY_SUMMARY
        elif 'Lease summary' in header_str or 'GuestCards' in header_str:
            self.report_type = ReportType.LEASE_SUMMARY
        elif 'PROSPECT DETAIL' in header_str or 'Guest Card' in header_str:
            self.report_type = ReportType.PROSPECT_DETAIL
        elif 'TRAFFIC SUMMARY' in header_str:
            self.report_type = ReportType.TRAFFIC_SUMMARY
        else:
            self.report_type = ReportType.UNKNOWN
            
        return self.report_type
    
    def _load_raw(self):
        """Load Excel file without headers."""
        suffix = self.file_path.suffix.lower()
        if suffix == '.xls':
            self.df_raw = pd.read_excel(self.file_path, header=None, engine='xlrd')
        else:
            self.df_raw = pd.read_excel(self.file_path, header=None, engine='openpyxl')
    
    def extract_metadata(self) -> Dict[str, str]:
        """Extract report metadata (property name, date range, etc.)."""
        if self.df_raw is None:
            self._load_raw()
            
        metadata = {}
        
        # Search first 10 rows for metadata
        for i in range(min(10, len(self.df_raw))):
            row = self.df_raw.iloc[i].astype(str).values
            row_text = ' '.join([x for x in row if x != 'nan'])
            
            # Property name pattern (e.g., "Kairoi Management, LLC - Ridian")
            if ' - ' in row_text and 'LLC' in row_text:
                parts = row_text.split(' - ')
                if len(parts) >= 2:
                    metadata['management_company'] = parts[0].strip()
                    metadata['property_name'] = parts[-1].strip()
            
            # Date range pattern (e.g., "01/01/2026 through 01/31/2026")
            date_match = re.search(r'(\d{2}/\d{2}/\d{4})\s+through\s+(\d{2}/\d{2}/\d{4})', row_text)
            if date_match:
                metadata['start_date'] = date_match.group(1)
                metadata['end_date'] = date_match.group(2)
                
            # Report generation timestamp
            timestamp_match = re.search(r'(\d{2}/\d{2}/\d{4}\s+\d{1,2}:\d{2}:\d{2}[AP]M)', row_text)
            if timestamp_match:
                metadata['generated_at'] = timestamp_match.group(1)
        
        self.metadata = metadata
        return metadata
    
    def parse(self) -> ImportResult:
        """Parse the report based on its type."""
        if self.df_raw is None:
            self._load_raw()
            
        self.detect_report_type()
        self.extract_metadata()
        
        if self.report_type == ReportType.LEASING_ACTIVITY_SUMMARY:
            return self._parse_leasing_activity_summary()
        elif self.report_type == ReportType.LEASE_SUMMARY:
            return self._parse_lease_summary()
        elif self.report_type == ReportType.PROSPECT_DETAIL:
            return self._parse_prospect_detail()
        else:
            return ImportResult(
                success=False,
                report_type=self.report_type,
                property_name=self.metadata.get('property_name', 'Unknown'),
                date_range=f"{self.metadata.get('start_date', '')} - {self.metadata.get('end_date', '')}",
                records_imported=0,
                message=f"Unsupported report type: {self.report_type}"
            )
    
    def _parse_leasing_activity_summary(self) -> ImportResult:
        """Parse Leasing Activity Summary report."""
        data = {
            'by_consultant': [],
            'by_day_of_week': [],
            'by_floorplan': [],
            'totals': {}
        }
        
        # Parse all rows looking for data patterns
        current_section = None
        
        for i in range(len(self.df_raw)):
            row = self.df_raw.iloc[i]
            row_vals = [str(v).strip() for v in row.values if str(v) != 'nan' and str(v).strip()]
            row_text = ' '.join(row_vals)
            
            # Skip empty rows
            if not row_text.strip():
                continue
            
            # Detect section headers
            if 'Summary By Leasing Consultant' in row_text:
                current_section = 'consultant'
                continue
            elif 'Summary By Day' in row_text:
                current_section = 'day'
                continue
            elif 'Summary By Floor Plan' in row_text:
                current_section = 'floorplan'
                continue
            
            # Skip header/label rows
            if 'New Prospects' in row_text or 'Leasing Consultant' in row_text:
                continue
            if 'Floor Plan Group' in row_text:
                continue
            if 'Activities' in row_text and len(row_vals) < 3:
                continue
                
            # Parse consultant rows - look for "Name, Name" pattern or known names
            if len(row_vals) >= 5:
                first_val = row_vals[0] if row_vals else ''
                
                # Check for consultant name patterns
                is_consultant = (
                    re.match(r'^[A-Za-z]+,\s*[A-Za-z]+$', first_val) or
                    first_val in ['HOUSE', 'Admin, Admin'] or
                    (', ' in first_val and first_val[0].isupper())
                )
                
                # Check for day names
                days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                is_day = first_val in days
                
                # Check for totals
                is_totals = first_val == 'Totals'
                
                if is_consultant and current_section != 'day':
                    consultant_data = self._extract_data_row(row_vals, 'consultant')
                    if consultant_data:
                        data['by_consultant'].append(consultant_data)
                        
                elif is_day:
                    day_data = self._extract_data_row(row_vals, 'day')
                    if day_data:
                        data['by_day_of_week'].append(day_data)
                        
                elif is_totals:
                    totals_data = self._extract_data_row(row_vals, 'totals')
                    if totals_data:
                        data['totals'] = totals_data
        
        records = len(data['by_consultant']) + len(data['by_day_of_week'])
        
        # Clean up property name
        prop_name = self.metadata.get('property_name', 'Unknown')
        if 'Page' in prop_name:
            prop_name = prop_name.split('Page')[0].strip()
        
        return ImportResult(
            success=True,
            report_type=self.report_type,
            property_name=prop_name,
            date_range=f"{self.metadata.get('start_date', '')} - {self.metadata.get('end_date', '')}",
            records_imported=records,
            message=f"Parsed {len(data['by_consultant'])} consultants, {len(data['by_day_of_week'])} days",
            data=data
        )
    
    def _extract_data_row(self, row_vals: List[str], row_type: str) -> Optional[Dict]:
        """Extract metrics from a data row."""
        if len(row_vals) < 3:
            return None
            
        # First value is the dimension name
        name = row_vals[0]
        
        # Rest are numeric values
        nums = []
        for val in row_vals[1:]:
            val = val.strip()
            # Handle percentages
            if '%' in val:
                try:
                    nums.append(float(val.replace('%', '').strip()))
                except:
                    nums.append(0.0)
            # Handle numbers
            elif val.replace('.', '').replace('-', '').isdigit():
                nums.append(float(val) if '.' in val else int(val))
        
        if len(nums) < 3:
            return None
        
        if row_type == 'consultant':
            # RealPage Leasing Activity Summary column order:
            # 0: New Prospects, 1: Activities, 2: Off-Site Conv, 3: Visits, 4: Return Visits
            # 5: Not In Ratio, 6: Net Visits, 7: Units Shown, 8: Quotes, 9: Leases
            # 10: Waitlist, 11: Total Leases, 12: Cancelled, 13: Net Leases, 14: Close%, 15: Move-ins
            return {
                'consultant_name': name,
                'new_prospects': int(nums[0]) if len(nums) > 0 else 0,
                'activities': int(nums[1]) if len(nums) > 1 else 0,
                'visits': int(nums[3]) if len(nums) > 3 else 0,  # Visits at index 3
                'return_visits': int(nums[4]) if len(nums) > 4 else 0,
                'net_visits': int(nums[6]) if len(nums) > 6 else 0,
                'quotes': int(nums[8]) if len(nums) > 8 else 0,  # Quotes at index 8
                'leases': int(nums[9]) if len(nums) > 9 else 0,  # Leases at index 9
                'move_ins': int(nums[-1]) if len(nums) > 0 else 0
            }
        elif row_type == 'day':
            return {
                'day_of_week': name,
                'activities': int(nums[0]) if len(nums) > 0 else 0,
                'visits': int(nums[1]) if len(nums) > 1 else 0,
                'return_visits': int(nums[2]) if len(nums) > 2 else 0,
                'net_visits': int(nums[3]) if len(nums) > 3 else 0,
                'quotes': int(nums[4]) if len(nums) > 4 else 0,
                'leases': int(nums[5]) if len(nums) > 5 else 0,
                'close_rate': float(nums[-2]) if len(nums) > 1 else 0.0,
                'move_ins': int(nums[-1]) if len(nums) > 0 else 0
            }
        elif row_type == 'totals':
            return {
                'total_activities': int(nums[0]) if len(nums) > 0 else 0,
                'total_visits': int(nums[1]) if len(nums) > 1 else 0,
                'total_quotes': int(nums[4]) if len(nums) > 4 else 0,
                'total_leases': int(nums[5]) if len(nums) > 5 else 0,
                'total_close_rate': float(nums[-2]) if len(nums) > 1 else 0.0,
                'total_move_ins': int(nums[-1]) if len(nums) > 0 else 0
            }
        
        return None
    
    def _extract_consultant_row(self, row: pd.Series, row_text: str) -> Optional[Dict]:
        """Extract metrics from a consultant row."""
        # Find numeric values in the row
        nums = []
        name = None
        
        for val in row.values:
            if pd.isna(val):
                continue
            val_str = str(val).strip()
            
            # Check for consultant name
            if re.match(r'^[A-Za-z]+,\s*[A-Za-z]+$', val_str) or val_str in ['Admin, Admin', 'HOUSE']:
                name = val_str
            # Check for numeric
            elif val_str.replace('.', '').replace('-', '').isdigit():
                nums.append(float(val_str) if '.' in val_str else int(val_str))
            # Check for percentage
            elif '%' in val_str:
                try:
                    nums.append(float(val_str.replace('%', '').strip()))
                except:
                    pass
        
        if not name or len(nums) < 5:
            return None
            
        return {
            'consultant_name': name,
            'new_prospects': nums[0] if len(nums) > 0 else 0,
            'activities': nums[1] if len(nums) > 1 else 0,
            'visits': nums[2] if len(nums) > 2 else 0,
            'quotes': nums[3] if len(nums) > 3 else 0,
            'leases': nums[4] if len(nums) > 4 else 0,
            'net_leases': nums[5] if len(nums) > 5 else 0,
            'close_rate': nums[6] if len(nums) > 6 else 0.0,
            'move_ins': nums[7] if len(nums) > 7 else 0
        }
    
    def _extract_day_row(self, row: pd.Series, day: str) -> Optional[Dict]:
        """Extract metrics from a day-of-week row."""
        nums = []
        
        for val in row.values:
            if pd.isna(val):
                continue
            val_str = str(val).strip()
            
            if val_str.replace('.', '').replace('-', '').isdigit():
                nums.append(float(val_str) if '.' in val_str else int(val_str))
            elif '%' in val_str:
                try:
                    nums.append(float(val_str.replace('%', '').strip()))
                except:
                    pass
        
        if len(nums) < 3:
            return None
            
        return {
            'day_of_week': day,
            'activities': nums[0] if len(nums) > 0 else 0,
            'visits': nums[1] if len(nums) > 1 else 0,
            'quotes': nums[2] if len(nums) > 2 else 0,
            'leases': nums[3] if len(nums) > 3 else 0,
            'close_rate': nums[4] if len(nums) > 4 else 0.0,
            'move_ins': nums[5] if len(nums) > 5 else 0
        }
    
    def _extract_activity_metrics(self, row: pd.Series) -> Optional[Dict]:
        """Extract totals metrics."""
        nums = []
        
        for val in row.values:
            if pd.isna(val):
                continue
            val_str = str(val).strip()
            
            if val_str.replace('.', '').replace('-', '').isdigit():
                nums.append(float(val_str) if '.' in val_str else int(val_str))
            elif '%' in val_str:
                try:
                    nums.append(float(val_str.replace('%', '').strip()))
                except:
                    pass
        
        if len(nums) < 5:
            return None
            
        return {
            'total_activities': nums[0] if len(nums) > 0 else 0,
            'total_visits': nums[1] if len(nums) > 1 else 0,
            'total_quotes': nums[2] if len(nums) > 2 else 0,
            'total_leases': nums[3] if len(nums) > 3 else 0,
            'total_close_rate': nums[4] if len(nums) > 4 else 0.0,
            'total_move_ins': nums[5] if len(nums) > 5 else 0
        }
    
    def _parse_lease_summary(self) -> ImportResult:
        """Parse Lease Summary report - contains applications count."""
        data = {
            'guest_cards': 0,
            'online_guest_cards': 0,
            'quotes': 0,
            'applications': 0,
            'screenings': 0,
            'leases_signed': 0,
            'property_name': ''
        }
        
        # Find the property name and data row
        for i in range(len(self.df_raw)):
            row = self.df_raw.iloc[i]
            row_vals = [str(v).strip() for v in row.values if str(v) != 'nan' and str(v).strip()]
            
            if not row_vals:
                continue
            
            # Look for property name (standalone row before headers)
            if len(row_vals) == 1 and row_vals[0] not in ['Lease summary', 'Total', 'SiteTotal :', 'PMC Total :']:
                if not any(x in row_vals[0] for x in ['Page', 'Date range', 'Report created', 'Kairoi']):
                    data['property_name'] = row_vals[0]
            
            # Look for the data row (starts with a number for GuestCards)
            if len(row_vals) >= 10 and row_vals[0].isdigit():
                # Parse: GuestCards, Online GuestCards, Quotes, Applications, Screenings, DocuSign, RP E-Sign, OFSA, Mixed, NotSigned, Leases
                try:
                    data['guest_cards'] = int(row_vals[0])
                    data['online_guest_cards'] = int(row_vals[1]) if len(row_vals) > 1 and row_vals[1].isdigit() else 0
                    data['quotes'] = int(row_vals[2]) if len(row_vals) > 2 and row_vals[2].isdigit() else 0
                    data['applications'] = int(row_vals[3]) if len(row_vals) > 3 and row_vals[3].isdigit() else 0
                    data['screenings'] = int(row_vals[4]) if len(row_vals) > 4 and row_vals[4].isdigit() else 0
                    data['leases_signed'] = int(row_vals[10]) if len(row_vals) > 10 and row_vals[10].isdigit() else 0
                except (ValueError, IndexError):
                    pass
                break
        
        # Extract date range from metadata
        date_range = ""
        for i in range(min(10, len(self.df_raw))):
            row = self.df_raw.iloc[i]
            row_text = ' '.join([str(v) for v in row.values if str(v) != 'nan'])
            date_match = re.search(r'Date range:\s*(\d{1,2}/\d{1,2}/\d{4})\s*-\s*(\d{1,2}/\d{1,2}/\d{4})', row_text)
            if date_match:
                date_range = f"{date_match.group(1)} - {date_match.group(2)}"
                break
        
        return ImportResult(
            success=True,
            report_type=self.report_type,
            property_name=data['property_name'] or self.metadata.get('property_name', 'Unknown'),
            date_range=date_range,
            records_imported=1,
            message=f"Parsed lease summary: {data['applications']} applications, {data['leases_signed']} leases",
            data=data
        )
    
    def _parse_prospect_detail(self) -> ImportResult:
        """Parse Prospect Detail report (individual prospect records)."""
        # This would parse individual prospect records if that report type is uploaded
        return ImportResult(
            success=False,
            report_type=self.report_type,
            property_name=self.metadata.get('property_name', 'Unknown'),
            date_range=f"{self.metadata.get('start_date', '')} - {self.metadata.get('end_date', '')}",
            records_imported=0,
            message="Prospect Detail parser not yet implemented"
        )


class ExcelImportService:
    """Service for importing Excel reports into the database."""
    
    def __init__(self):
        self.db_path = UNIFIED_DB_PATH
        
    def import_file(self, file_path: str, property_id: Optional[str] = None) -> ImportResult:
        """Import an Excel file and store data in the database."""
        parser = RealPageReportParser(file_path)
        result = parser.parse()
        
        if not result.success:
            return result
            
        # Store in database
        if result.report_type == ReportType.LEASING_ACTIVITY_SUMMARY:
            self._store_leasing_activity(result, property_id)
        elif result.report_type == ReportType.LEASE_SUMMARY:
            self._store_lease_summary(result, property_id)
            
        return result
    
    def _store_leasing_activity(self, result: ImportResult, property_id: Optional[str] = None):
        """Store leasing activity data in the database."""
        if not result.data:
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Ensure table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS imported_leasing_activity (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    property_id TEXT,
                    property_name TEXT,
                    report_start_date TEXT,
                    report_end_date TEXT,
                    section_type TEXT,
                    dimension_name TEXT,
                    new_prospects INTEGER DEFAULT 0,
                    activities INTEGER DEFAULT 0,
                    visits INTEGER DEFAULT 0,
                    return_visits INTEGER DEFAULT 0,
                    quotes INTEGER DEFAULT 0,
                    leases INTEGER DEFAULT 0,
                    net_leases INTEGER DEFAULT 0,
                    close_rate REAL DEFAULT 0,
                    move_ins INTEGER DEFAULT 0,
                    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_imported_leasing_property 
                ON imported_leasing_activity(property_id, report_start_date)
            """)
            
            # Parse dates from result date_range
            date_parts = result.date_range.split(' - ')
            start_date = date_parts[0].strip() if len(date_parts) > 0 else ''
            end_date = date_parts[1].strip() if len(date_parts) > 1 else ''
            
            # Insert consultant data
            for consultant in result.data.get('by_consultant', []):
                cursor.execute("""
                    INSERT INTO imported_leasing_activity 
                    (property_id, property_name, report_start_date, report_end_date,
                     section_type, dimension_name, new_prospects, activities, visits,
                     quotes, leases, net_leases, close_rate, move_ins)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    property_id,
                    result.property_name,
                    start_date,
                    end_date,
                    'by_consultant',
                    consultant.get('consultant_name'),
                    consultant.get('new_prospects', 0),
                    consultant.get('activities', 0),
                    consultant.get('visits', 0),
                    consultant.get('quotes', 0),
                    consultant.get('leases', 0),
                    consultant.get('net_leases', 0),
                    consultant.get('close_rate', 0),
                    consultant.get('move_ins', 0)
                ))
            
            # Insert day data
            for day in result.data.get('by_day_of_week', []):
                cursor.execute("""
                    INSERT INTO imported_leasing_activity 
                    (property_id, property_name, report_start_date, report_end_date,
                     section_type, dimension_name, activities, visits,
                     quotes, leases, close_rate, move_ins)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    property_id,
                    result.property_name,
                    start_date,
                    end_date,
                    'by_day_of_week',
                    day.get('day_of_week'),
                    day.get('activities', 0),
                    day.get('visits', 0),
                    day.get('quotes', 0),
                    day.get('leases', 0),
                    day.get('close_rate', 0),
                    day.get('move_ins', 0)
                ))
            
            # Insert totals
            totals = result.data.get('totals', {})
            if totals:
                cursor.execute("""
                    INSERT INTO imported_leasing_activity 
                    (property_id, property_name, report_start_date, report_end_date,
                     section_type, dimension_name, activities, visits,
                     quotes, leases, close_rate, move_ins)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    property_id,
                    result.property_name,
                    start_date,
                    end_date,
                    'totals',
                    'TOTAL',
                    totals.get('total_activities', 0),
                    totals.get('total_visits', 0),
                    totals.get('total_quotes', 0),
                    totals.get('total_leases', 0),
                    totals.get('total_close_rate', 0),
                    totals.get('total_move_ins', 0)
                ))
            
            # Log the import
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS import_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_name TEXT,
                    report_type TEXT,
                    property_name TEXT,
                    records_imported INTEGER,
                    status TEXT,
                    message TEXT,
                    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                INSERT INTO import_log (file_name, report_type, property_name, records_imported, status, message)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(self.file_path) if hasattr(self, 'file_path') else 'unknown',
                result.report_type.value,
                result.property_name,
                result.records_imported,
                'success',
                result.message
            ))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def get_import_history(self, property_id: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """Get import history from log."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                SELECT * FROM import_log 
                ORDER BY imported_at DESC 
                LIMIT ?
            """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
        except:
            return []
        finally:
            conn.close()
    
    def get_leasing_activity(
        self, 
        property_id: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get imported leasing activity data."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            query = "SELECT * FROM imported_leasing_activity WHERE 1=1"
            params = []
            
            if property_id:
                query += " AND property_id = ?"
                params.append(property_id)
            if start_date:
                query += " AND report_start_date >= ?"
                params.append(start_date)
            if end_date:
                query += " AND report_end_date <= ?"
                params.append(end_date)
                
            query += " ORDER BY imported_at DESC"
            
            cursor.execute(query, params)
            rows = [dict(row) for row in cursor.fetchall()]
            
            # Group by section type
            result = {
                'by_consultant': [],
                'by_day_of_week': [],
                'totals': None
            }
            
            for row in rows:
                section = row.get('section_type')
                if section == 'by_consultant':
                    result['by_consultant'].append(row)
                elif section == 'by_day_of_week':
                    result['by_day_of_week'].append(row)
                elif section == 'totals':
                    result['totals'] = row
                    
            return result
            
        except Exception as e:
            return {'error': str(e)}
        finally:
            conn.close()
    
    def _store_lease_summary(self, result: ImportResult, property_id: Optional[str] = None):
        """Store lease summary data (applications) in the database."""
        if not result.data:
            return
            
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Ensure table exists
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS imported_lease_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    property_id TEXT,
                    property_name TEXT,
                    report_start_date TEXT,
                    report_end_date TEXT,
                    guest_cards INTEGER DEFAULT 0,
                    online_guest_cards INTEGER DEFAULT 0,
                    quotes INTEGER DEFAULT 0,
                    applications INTEGER DEFAULT 0,
                    screenings INTEGER DEFAULT 0,
                    leases_signed INTEGER DEFAULT 0,
                    imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_lease_summary_property 
                ON imported_lease_summary(property_id, report_start_date)
            """)
            
            # Parse dates from result date_range
            date_parts = result.date_range.split(' - ')
            start_date = date_parts[0].strip() if len(date_parts) > 0 else ''
            end_date = date_parts[1].strip() if len(date_parts) > 1 else ''
            
            # Insert data
            cursor.execute("""
                INSERT INTO imported_lease_summary 
                (property_id, property_name, report_start_date, report_end_date,
                 guest_cards, online_guest_cards, quotes, applications, screenings, leases_signed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                property_id,
                result.property_name,
                start_date,
                end_date,
                result.data.get('guest_cards', 0),
                result.data.get('online_guest_cards', 0),
                result.data.get('quotes', 0),
                result.data.get('applications', 0),
                result.data.get('screenings', 0),
                result.data.get('leases_signed', 0)
            ))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
