"""
RealPage Report Parsers

Parses downloaded Excel reports and extracts structured data for database storage.
"""

import pandas as pd
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any


def detect_report_type(df: pd.DataFrame) -> Optional[str]:
    """Detect report type from content."""
    # Check first 10 rows for report identifiers
    for i in range(min(10, len(df))):
        row_text = ' '.join(str(x) for x in df.iloc[i].dropna().tolist()).upper()
        
        if 'BOXSCORE' in row_text or 'BOX SCORE' in row_text:
            return 'box_score'
        elif 'RENT ROLL' in row_text:
            return 'rent_roll'
        elif 'ACTIVITY REPORT' in row_text or 'ACTIVITY LOG' in row_text:
            return 'activity'
        elif 'MONTHLY ACTIVITY SUMMARY' in row_text:
            return 'monthly_summary'
        elif 'LEASE EXPIR' in row_text:
            return 'lease_expiration'
        elif 'DELINQUENT' in row_text or 'DELINQUENCY' in row_text:
            return 'delinquency'
    
    return None


def extract_property_info(df: pd.DataFrame) -> Dict[str, str]:
    """Extract property name and report date from header rows."""
    property_name = None
    report_date = None
    fiscal_period = None
    
    for i in range(min(15, len(df))):
        row = df.iloc[i].dropna().tolist()
        row_text = ' '.join(str(x) for x in row)
        
        # Look for property name (usually contains "LLC" or management company name)
        if 'LLC' in row_text or 'Management' in row_text:
            for item in row:
                if isinstance(item, str) and ('LLC' in item or 'Management' in item):
                    # Extract property name after the company name
                    parts = item.split(' - ')
                    if len(parts) > 1:
                        property_name = parts[-1].strip()
                    break
        
        # Look for date patterns
        date_match = re.search(r'(\d{2}/\d{2}/\d{4})', row_text)
        if date_match and not report_date:
            report_date = date_match.group(1)
        
        # Look for fiscal period
        fiscal_match = re.search(r'Fiscal Period (\d{6})', row_text)
        if fiscal_match:
            fiscal_period = fiscal_match.group(1)
        
        # Also check "As of" date
        as_of_match = re.search(r'As of (\d{2}/\d{2}/\d{4})', row_text)
        if as_of_match:
            report_date = as_of_match.group(1)
    
    return {
        'property_name': property_name,
        'report_date': report_date,
        'fiscal_period': fiscal_period
    }


def parse_box_score(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Box Score report.
    Returns list of floorplan-level metrics.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    
    # Extract property info
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']
    fiscal_period = info['fiscal_period']
    
    # Find header row (contains "Floor Plan" and "Units")
    header_row = None
    for i in range(min(20, len(df))):
        row = df.iloc[i].dropna().tolist()
        row_text = ' '.join(str(x) for x in row)
        if 'Floor Plan' in row_text and 'Units' in row_text:
            header_row = i
            break
    
    if header_row is None:
        return []
    
    # Get headers
    headers = df.iloc[header_row].tolist()
    
    # Map column indices
    col_map = {}
    for idx, h in enumerate(headers):
        if pd.isna(h):
            continue
        h_clean = str(h).replace('\n', ' ').strip().lower()
        if 'floor plan' in h_clean and 'group' not in h_clean:
            col_map['floorplan'] = idx
        elif 'group' in h_clean:
            col_map['floorplan_group'] = idx
        elif h_clean == 'units':
            col_map['units'] = idx
        elif 'total' in h_clean and 'vacant' in h_clean:
            col_map['vacant'] = idx
        elif 'not' in h_clean and 'leased' in h_clean:
            col_map['vacant_not_leased'] = idx
        elif h_clean == 'leased':
            col_map['vacant_leased'] = idx
        elif 'model' in h_clean:
            col_map['model'] = idx
        elif h_clean == 'down':
            col_map['down'] = idx
        elif 'total' in h_clean and 'occupied' in h_clean:
            col_map['occupied'] = idx
        elif 'no ntv' in h_clean:
            col_map['no_notice'] = idx
        elif 'ntv-nl' in h_clean:
            col_map['notice_not_leased'] = idx
        elif 'ntv-l' in h_clean:
            col_map['notice_leased'] = idx
        elif 'occupancy' in h_clean and 'percent' in h_clean:
            col_map['occupancy_pct'] = idx
        elif 'avg market' in h_clean:
            col_map['market_rent'] = idx
        elif 'avg leased' in h_clean or 'avg actual' in h_clean:
            col_map['actual_rent'] = idx
        elif 'avg' in h_clean and 'sqft' in h_clean:
            col_map['sqft'] = idx
    
    # Parse data rows
    records = []
    current_group = None
    
    for i in range(header_row + 1, len(df)):
        row = df.iloc[i].tolist()
        
        # Skip empty rows or subtotal rows
        if pd.isna(row[col_map.get('floorplan', 1)]):
            # Check if it's a group header
            first_val = row[0] if not pd.isna(row[0]) else None
            if first_val and isinstance(first_val, str) and 'x' in first_val.lower():
                current_group = first_val
            continue
        
        floorplan = row[col_map.get('floorplan', 1)]
        if not floorplan or not isinstance(floorplan, str):
            continue
        
        # Skip subtotal/total rows
        if 'total' in str(floorplan).lower() or 'subtotal' in str(floorplan).lower():
            continue
        
        def safe_int(val):
            try:
                return int(val) if pd.notna(val) else 0
            except:
                return 0
        
        def safe_float(val):
            try:
                return float(val) if pd.notna(val) else 0.0
            except:
                return 0.0
        
        record = {
            'property_id': property_id,
            'property_name': property_name,
            'report_date': report_date,
            'fiscal_period': fiscal_period,
            'floorplan_group': current_group,
            'floorplan': floorplan,
            'total_units': safe_int(row[col_map.get('units', 2)]),
            'vacant_units': safe_int(row[col_map.get('vacant', 3)]),
            'vacant_not_leased': safe_int(row[col_map.get('vacant_not_leased', 4)]),
            'vacant_leased': safe_int(row[col_map.get('vacant_leased', 5)]),
            'occupied_units': safe_int(row[col_map.get('occupied', 8)]),
            'occupied_no_notice': safe_int(row[col_map.get('no_notice', 9)]),
            'occupied_on_notice': safe_int(row[col_map.get('notice_not_leased', 10)]) + safe_int(row[col_map.get('notice_leased', 11)]),
            'model_units': safe_int(row[col_map.get('model', 6)]),
            'down_units': safe_int(row[col_map.get('down', 7)]),
            'avg_sqft': safe_int(row[col_map.get('sqft', 0)]),
            'avg_market_rent': safe_float(row[col_map.get('market_rent', 13)]),
            'avg_actual_rent': safe_float(row[col_map.get('actual_rent', 14)]),
            'occupancy_pct': safe_float(row[col_map.get('occupancy_pct', 12)]),
        }
        
        # Calculate leased % and exposure %
        if record['total_units'] > 0:
            leased = record['total_units'] - record['vacant_not_leased']
            record['leased_pct'] = round(leased / record['total_units'] * 100, 1)
            exposure = record['vacant_not_leased'] + record.get('occupied_on_notice', 0)
            record['exposure_pct'] = round(exposure / record['total_units'] * 100, 1)
        else:
            record['leased_pct'] = 0
            record['exposure_pct'] = 0
        
        records.append(record)
    
    return records


def parse_delinquency(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Delinquency report.
    Returns list of resident balance records.
    
    RealPage delinquency reports have a multi-row format:
    - Unit header row: contains unit number (col 1) and status (col 9)
    - Balance row: NEXT row with values in cols 39 (Net Balance), 43 (Current), 48 (30 days), etc.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']
    
    # Column indices for RealPage Delinquent and Prepaid Report
    COL_UNIT = 1
    COL_STATUS = 9
    COL_MOVE_DATE = 13
    COL_TOTAL_PREPAID = 24
    COL_TOTAL_DELINQUENT = 30
    COL_NET_BALANCE = 39
    COL_CURRENT = 43
    COL_30_DAYS = 48
    COL_60_DAYS = 52
    COL_90_PLUS = 55
    
    def safe_float(val):
        try:
            return float(val) if pd.notna(val) else 0.0
        except:
            return 0.0
    
    records = []
    i = 15  # Skip header rows
    
    while i < len(df) - 1:
        unit = df.iloc[i, COL_UNIT]
        status = df.iloc[i, COL_STATUS]
        
        # Check if this is a unit row
        if pd.notna(unit) and isinstance(unit, (str, int, float)):
            unit_str = str(unit).strip()
            
            # Skip header text and total rows
            if unit_str and 'unit' not in unit_str.lower() and 'total' not in unit_str.lower() and len(unit_str) < 15:
                # Look for balance row in next few rows
                for j in range(i + 1, min(i + 10, len(df))):
                    net_balance = df.iloc[j, COL_NET_BALANCE]
                    current = df.iloc[j, COL_CURRENT]
                    days_30 = df.iloc[j, COL_30_DAYS]
                    days_60 = df.iloc[j, COL_60_DAYS]
                    days_90 = df.iloc[j, COL_90_PLUS]
                    prepaid = df.iloc[j, COL_TOTAL_PREPAID]
                    delinquent = df.iloc[j, COL_TOTAL_DELINQUENT]
                    
                    # Found balance row if any balance column has data
                    if pd.notna(net_balance) or pd.notna(current) or pd.notna(days_30):
                        record = {
                            'property_id': property_id,
                            'property_name': property_name,
                            'report_date': report_date,
                            'unit_number': unit_str,
                            'resident_name': None,  # PII hidden in reports
                            'status': str(status).strip() if pd.notna(status) else '',
                            'current_balance': safe_float(current),
                            'balance_0_30': safe_float(days_30),
                            'balance_31_60': safe_float(days_60),
                            'balance_61_90': 0.0,  # Combined with 90+
                            'balance_over_90': safe_float(days_90),
                            'prepaid': safe_float(prepaid),
                            'total_delinquent': safe_float(delinquent),
                            'net_balance': safe_float(net_balance),
                        }
                        records.append(record)
                        break
        i += 1
    
    return records


def parse_rent_roll(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Rent Roll report.
    Returns list of unit-level rent records.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']
    
    # Find header row with Unit column
    header_row = None
    for i in range(min(15, len(df))):
        row_text = ' '.join(str(x) for x in df.iloc[i].dropna().tolist()).lower()
        if 'unit' in row_text and ('floorplan' in row_text or 'sqft' in row_text):
            header_row = i
            break
    
    if header_row is None:
        return []
    
    headers = df.iloc[header_row].tolist()
    
    # Map columns
    col_map = {}
    for idx, h in enumerate(headers):
        if pd.isna(h):
            continue
        h_clean = str(h).replace('\n', ' ').replace('\r', '').strip().lower()
        if h_clean == 'unit' or h_clean == 'unit':
            col_map['unit'] = idx
        elif 'floorplan' in h_clean:
            col_map['floorplan'] = idx
        elif 'sqft' in h_clean:
            col_map['sqft'] = idx
        elif 'status' in h_clean:
            col_map['status'] = idx
        elif h_clean == 'name' or h_clean == 'name':
            col_map['name'] = idx
        elif 'move-in' in h_clean or 'move in' in h_clean or 'move-out' in h_clean:
            col_map['move_in'] = idx
        elif 'lease' in h_clean and 'start' in h_clean:
            col_map['lease_start'] = idx
        elif 'lease' in h_clean and 'end' in h_clean:
            col_map['lease_end'] = idx
        elif 'lease' in h_clean and 'rent' in h_clean:
            col_map['lease_rent'] = idx
        elif 'market' in h_clean:
            col_map['market_rent'] = idx
        elif 'balance' in h_clean:
            col_map['balance'] = idx
        elif 'total' in h_clean and 'billing' in h_clean:
            col_map['total_billing'] = idx
    
    def safe_float(val):
        try:
            return float(val) if pd.notna(val) else 0.0
        except:
            return 0.0
    
    def safe_int(val):
        try:
            return int(val) if pd.notna(val) else 0
        except:
            return 0
    
    def safe_str(val):
        if pd.notna(val):
            s = str(val).replace('\r', '').strip()
            return s if s and s != '*' else None
        return None
    
    records = []
    
    for i in range(header_row + 1, len(df)):
        row = df.iloc[i].tolist()
        
        # Check if this is a unit row (has unit number in first column)
        unit_val = row[col_map.get('unit', 0)]
        if pd.notna(unit_val) and str(unit_val).strip() and not str(unit_val).strip().startswith('='):
            # Skip if it's a section header
            if 'total' in str(unit_val).lower() or 'subtotal' in str(unit_val).lower():
                continue
            
            # Get market rent: use mapped column, or find first large numeric after sqft
            market_rent = 0
            if 'market_rent' in col_map:
                market_rent = safe_float(row[col_map['market_rent']])
            else:
                # Look for first numeric value after status column that looks like rent (> 100)
                start_col = col_map.get('status', col_map.get('sqft', 13)) + 1
                for j in range(start_col, len(row)):
                    if pd.notna(row[j]) and isinstance(row[j], (int, float)) and float(row[j]) > 100:
                        market_rent = float(row[j])
                        break
            
            # Get actual/lease rent
            actual_rent = 0
            if 'lease_rent' in col_map:
                actual_rent = safe_float(row[col_map['lease_rent']])
            
            # Get resident name
            resident_name = None
            if 'name' in col_map:
                resident_name = safe_str(row[col_map['name']])
            
            # Get lease dates
            lease_start = None
            if 'lease_start' in col_map:
                lease_start = safe_str(row[col_map['lease_start']])
            
            lease_end = None
            if 'lease_end' in col_map:
                lease_end = safe_str(row[col_map['lease_end']])
            
            # Get move-in date
            move_in = None
            if 'move_in' in col_map:
                move_in = safe_str(row[col_map['move_in']])
            
            # Get balance
            balance = 0
            if 'balance' in col_map:
                balance = safe_float(row[col_map['balance']])
            
            status_val = safe_str(row[col_map.get('status', 17)])
            
            record = {
                'property_id': property_id,
                'property_name': property_name,
                'report_date': report_date,
                'unit_number': str(unit_val).strip(),
                'floorplan': safe_str(row[col_map.get('floorplan', 2)]),
                'sqft': safe_int(row[col_map.get('sqft', 13)]),
                'status': status_val,
                'resident_name': resident_name,
                'lease_start': lease_start,
                'lease_end': lease_end,
                'move_in_date': move_in,
                'actual_rent': actual_rent,
                'market_rent': market_rent,
                'balance': balance,
            }
            records.append(record)
    
    return records


def parse_monthly_summary(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Monthly Activity Summary report.
    Returns list of monthly metrics by floorplan.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']
    
    # Find header row
    header_row = None
    for i in range(min(20, len(df))):
        row_text = ' '.join(str(x) for x in df.iloc[i].dropna().tolist()).lower()
        if 'floor' in row_text and ('move' in row_text or 'begin' in row_text):
            header_row = i
            break
    
    if header_row is None:
        return []
    
    headers = df.iloc[header_row].tolist()
    
    col_map = {}
    for idx, h in enumerate(headers):
        if pd.isna(h):
            continue
        h_clean = str(h).replace('\n', ' ').strip().lower()
        if 'floor' in h_clean:
            col_map['floorplan'] = idx
        elif 'begin' in h_clean:
            col_map['beginning'] = idx
        elif 'move' in h_clean and 'in' in h_clean:
            col_map['move_ins'] = idx
        elif 'move' in h_clean and 'out' in h_clean:
            col_map['move_outs'] = idx
        elif 'end' in h_clean:
            col_map['ending'] = idx
        elif 'renewal' in h_clean:
            col_map['renewals'] = idx
        elif 'notice' in h_clean:
            col_map['notices'] = idx
    
    records = []
    for i in range(header_row + 1, len(df)):
        row = df.iloc[i].tolist()
        
        floorplan = row[col_map.get('floorplan', 0)]
        if pd.isna(floorplan) or 'total' in str(floorplan).lower():
            continue
        
        def safe_int(val):
            try:
                return int(val) if pd.notna(val) else 0
            except:
                return 0
        
        record = {
            'property_id': property_id,
            'property_name': property_name,
            'report_date': report_date,
            'floorplan': str(floorplan),
            'beginning_occupancy': safe_int(row[col_map.get('beginning', 1)]),
            'move_ins': safe_int(row[col_map.get('move_ins', 2)]),
            'move_outs': safe_int(row[col_map.get('move_outs', 3)]),
            'ending_occupancy': safe_int(row[col_map.get('ending', 4)]),
            'renewals': safe_int(row[col_map.get('renewals', 5)]),
            'notices': safe_int(row[col_map.get('notices', 6)]),
        }
        records.append(record)
    
    return records


def parse_lease_expiration(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Lease Expiration report.
    Returns list of upcoming lease expirations.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']
    
    # Find header row
    header_row = None
    for i in range(min(20, len(df))):
        row_text = ' '.join(str(x) for x in df.iloc[i].dropna().tolist()).lower()
        if 'unit' in row_text and ('expir' in row_text or 'lease' in row_text):
            header_row = i
            break
    
    if header_row is None:
        return []
    
    headers = df.iloc[header_row].tolist()
    
    col_map = {}
    for idx, h in enumerate(headers):
        if pd.isna(h):
            continue
        h_clean = str(h).replace('\n', ' ').strip().lower()
        if 'unit' in h_clean:
            col_map['unit'] = idx
        elif 'floorplan' in h_clean or 'floor plan' in h_clean:
            col_map['floorplan'] = idx
        elif 'resident' in h_clean or 'name' in h_clean:
            col_map['name'] = idx
        elif 'expir' in h_clean or 'lease end' in h_clean:
            col_map['lease_end'] = idx
        elif 'current' in h_clean and 'rent' in h_clean:
            col_map['current_rent'] = idx
        elif 'market' in h_clean:
            col_map['market_rent'] = idx
        elif 'term' in h_clean:
            col_map['lease_term'] = idx
        elif 'renewal' in h_clean or 'status' in h_clean:
            col_map['renewal_status'] = idx
    
    records = []
    for i in range(header_row + 1, len(df)):
        row = df.iloc[i].tolist()
        
        unit = row[col_map.get('unit', 0)]
        if pd.isna(unit) or 'total' in str(unit).lower():
            continue
        
        def safe_float(val):
            try:
                return float(val) if pd.notna(val) else 0.0
            except:
                return 0.0
        
        def safe_int(val):
            try:
                return int(val) if pd.notna(val) else 0
            except:
                return 0
        
        record = {
            'property_id': property_id,
            'property_name': property_name,
            'report_date': report_date,
            'unit_number': str(unit),
            'floorplan': str(row[col_map.get('floorplan', 1)]) if col_map.get('floorplan') and pd.notna(row[col_map.get('floorplan')]) else None,
            'resident_name': str(row[col_map.get('name', 2)]) if col_map.get('name') and pd.notna(row[col_map.get('name')]) else None,
            'lease_end': str(row[col_map.get('lease_end', 3)]) if col_map.get('lease_end') and pd.notna(row[col_map.get('lease_end')]) else None,
            'current_rent': safe_float(row[col_map.get('current_rent', 4)]),
            'market_rent': safe_float(row[col_map.get('market_rent', 5)]),
            'lease_term': safe_int(row[col_map.get('lease_term', 6)]),
            'renewal_status': str(row[col_map.get('renewal_status', 7)]) if col_map.get('renewal_status') and pd.notna(row[col_map.get('renewal_status')]) else None,
        }
        records.append(record)
    
    return records


def parse_activity(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Activity Report.
    Returns list of leasing activity events.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']
    
    # Find header row
    header_row = None
    for i in range(min(20, len(df))):
        row_text = ' '.join(str(x) for x in df.iloc[i].dropna().tolist()).lower()
        if 'date' in row_text and ('activity' in row_text or 'type' in row_text):
            header_row = i
            break
    
    if header_row is None:
        return []
    
    headers = df.iloc[header_row].tolist()
    
    col_map = {}
    for idx, h in enumerate(headers):
        if pd.isna(h):
            continue
        h_clean = str(h).replace('\n', ' ').strip().lower()
        if 'date' in h_clean and 'activity' not in h_clean:
            col_map['activity_date'] = idx
        elif 'unit' in h_clean:
            col_map['unit'] = idx
        elif 'floorplan' in h_clean:
            col_map['floorplan'] = idx
        elif 'type' in h_clean or 'activity' in h_clean:
            col_map['activity_type'] = idx
        elif 'resident' in h_clean or 'name' in h_clean:
            col_map['name'] = idx
        elif 'prior' in h_clean and 'rent' in h_clean:
            col_map['prior_rent'] = idx
        elif 'new' in h_clean and 'rent' in h_clean:
            col_map['new_rent'] = idx
        elif 'term' in h_clean:
            col_map['lease_term'] = idx
    
    records = []
    for i in range(header_row + 1, len(df)):
        row = df.iloc[i].tolist()
        
        activity_date = row[col_map.get('activity_date', 0)]
        if pd.isna(activity_date):
            continue
        
        def safe_float(val):
            try:
                return float(val) if pd.notna(val) else 0.0
            except:
                return 0.0
        
        def safe_int(val):
            try:
                return int(val) if pd.notna(val) else 0
            except:
                return 0
        
        record = {
            'property_id': property_id,
            'property_name': property_name,
            'report_date': report_date,
            'activity_date': str(activity_date) if pd.notna(activity_date) else None,
            'unit_number': str(row[col_map.get('unit', 1)]) if col_map.get('unit') and pd.notna(row[col_map.get('unit')]) else None,
            'floorplan': str(row[col_map.get('floorplan', 2)]) if col_map.get('floorplan') and pd.notna(row[col_map.get('floorplan')]) else None,
            'activity_type': str(row[col_map.get('activity_type', 3)]) if col_map.get('activity_type') and pd.notna(row[col_map.get('activity_type')]) else None,
            'resident_name': str(row[col_map.get('name', 4)]) if col_map.get('name') and pd.notna(row[col_map.get('name')]) else None,
            'prior_rent': safe_float(row[col_map.get('prior_rent', 5)]),
            'new_rent': safe_float(row[col_map.get('new_rent', 6)]),
            'lease_term': safe_int(row[col_map.get('lease_term', 7)]),
        }
        records.append(record)
    
    return records


def parse_report(file_path: str, property_id: str = None, file_id: str = None) -> Dict[str, Any]:
    """
    Parse a report file and return structured data.
    Auto-detects report type.
    """
    try:
        df = pd.read_excel(file_path, sheet_name=0, header=None)
    except Exception as e:
        return {'error': str(e), 'report_type': None, 'records': []}
    
    report_type = detect_report_type(df)
    
    if report_type == 'box_score':
        records = parse_box_score(file_path, property_id)
    elif report_type == 'delinquency':
        records = parse_delinquency(file_path, property_id)
    elif report_type == 'monthly_summary':
        records = parse_monthly_summary(file_path, property_id)
    elif report_type == 'rent_roll':
        records = parse_rent_roll(file_path, property_id)
    elif report_type == 'lease_expiration':
        records = parse_lease_expiration(file_path, property_id)
    elif report_type == 'activity':
        records = parse_activity(file_path, property_id)
    else:
        records = []
    
    # Add file_id to all records
    for r in records:
        r['file_id'] = file_id
    
    return {
        'report_type': report_type,
        'records': records,
        'file_path': str(file_path),
        'file_id': file_id
    }


if __name__ == '__main__':
    # Test parsing
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = 'reports/report_8849110.xlsx'
    
    result = parse_report(file_path, property_id='test')
    print(f"Report type: {result['report_type']}")
    print(f"Records: {len(result['records'])}")
    if result['records']:
        print(f"Sample: {result['records'][0]}")
