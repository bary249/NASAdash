"""
RealPage Report Parsers

Parses downloaded Excel reports and extracts structured data for database storage.
"""

import pandas as pd
import re
import csv
import io
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
        elif 'LEASE EXPIR' in row_text and 'RENEWAL' in row_text:
            return 'lease_expiration_renewal'
        elif 'LEASE EXPIR' in row_text:
            return 'lease_expiration'
        elif 'DELINQUENT' in row_text or 'DELINQUENCY' in row_text:
            return 'delinquency'
        elif 'PROJECTED OCCUPANCY' in row_text:
            return 'projected_occupancy'
        elif 'MONTHLY TRANSACTION SUMMARY' in row_text:
            return 'monthly_transaction_summary'
        elif 'MAKE READY SUMMARY' in row_text and 'CLOSED' not in row_text:
            return 'make_ready_summary'
        elif 'CLOSED MAKE READY' in row_text:
            return 'closed_make_ready'
        elif 'PRIMARY ADVERTISING SOURCE' in row_text:
            return 'advertising_source'
        elif 'LOST RENT SUMMARY' in row_text:
            return 'lost_rent_summary'
        elif 'REASONS FOR MOVE OUT' in row_text:
            return 'move_out_reasons'
        elif 'LEASE DETAILS' in row_text:
            return 'lease_details'
    
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
        row_text = ' '.join(str(x) for x in row).lower()
        if 'floor plan' in row_text and 'unit' in row_text:
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
                if pd.isna(val):
                    return 0.0
                return float(str(val).replace(',', ''))
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
    Parse Delinquency / Delinquent and Prepaid report (reports 4260 and 4009).
    Returns list of resident balance records aggregated by unit.
    
    Handles two RealPage report formats:
    
    1. Detail format (~25 cols, report 4009): Per-resident per-transaction-code rows.
       Row 0 = header blob, Row 1 = column headers, Row 2+ = data.
       Columns: Resh ID[0], Lease ID[1], Bldg/Unit[2], Name[3], Phone[4], Email[5],
       Status[6], Move-In/Out[7], Code Description[8], Total Prepaid[9],
       Total Delinquent[10], D[11], O[12], Net Balance[13], Current[14],
       30 Days[15], 60 Days[16], 90+ Days[17], Prorate Credit[18],
       Deposits Held[19], Outstanding Deposit[20], #Late[21], #NSF[22],
       Comment Date[23], Leasing Agent[24].
       Multiple rows per unit (one per charge code) — must aggregate by unit.
    
    2. Summary format (74 cols, report 4260): Transaction-code level property summary.
       Provides property-level financial totals by transaction code, not per-unit detail.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']
    
    def safe_float(val):
        try:
            if pd.isna(val):
                return 0.0
            return float(str(val).replace(',', ''))
        except:
            return 0.0
    
    # Detect format: detail format has column headers in early rows
    is_detail = False
    header_row = None
    for check_row in range(min(5, len(df))):
        row_vals = [str(x).upper() for x in df.iloc[check_row].dropna().tolist()]
        row_text = ' '.join(row_vals)
        if 'BLDG/UNIT' in row_text or ('TOTAL PREPAID' in row_text and 'TOTAL DELINQUENT' in row_text):
            is_detail = True
            header_row = check_row
            break
    
    if is_detail:
        return _parse_delinquency_detail(df, header_row, property_id, property_name, report_date, safe_float)
    else:
        return _parse_delinquency_summary(df, property_id, property_name, report_date, safe_float)


def _parse_delinquency_detail(df, header_row, property_id, property_name, report_date, safe_float):
    """
    Parse detail format (report 4009, ~25 columns).
    Multiple rows per unit (one per transaction code) — aggregate by unit.
    """
    # Build column index map from header row
    col_map = {}
    for j in range(df.shape[1]):
        val = df.iloc[header_row, j]
        if pd.notna(val):
            col_map[str(val).strip().upper()] = j
    
    # Map known columns (with fallback indices for standard layout)
    COL_UNIT = col_map.get('BLDG/UNIT', 2)
    COL_STATUS = col_map.get('STATUS', 6)
    COL_PREPAID = col_map.get('TOTAL PREPAID', 9)
    COL_DELINQUENT = col_map.get('TOTAL DELINQUENT', 10)
    COL_NET_BALANCE = col_map.get('NET BALANCE', 13)
    COL_CURRENT = col_map.get('CURRENT', 14)
    COL_30_DAYS = col_map.get('30 DAYS', 15)
    COL_60_DAYS = col_map.get('60 DAYS', 16)
    COL_90_PLUS = col_map.get('90+ DAYS', 17)
    COL_DEPOSITS = col_map.get('DEPOSITS HELD', 19)
    COL_OUTSTANDING = col_map.get('OUTSTANDING DEPOSIT', 20)
    
    def get_val(row_idx, col_idx):
        if col_idx < df.shape[1]:
            return df.iloc[row_idx, col_idx]
        return None
    
    # Aggregate by unit number
    units = {}
    start_row = header_row + 1
    
    for i in range(start_row, len(df)):
        unit_val = get_val(i, COL_UNIT)
        if pd.isna(unit_val):
            continue
        
        unit_str = str(unit_val).strip()
        
        # Skip non-data rows
        if not unit_str or 'total' in unit_str.lower() or 'grand' in unit_str.lower():
            continue
        if unit_str.upper() in ('BLDG/UNIT', 'UNIT', ''):
            continue
        
        status_val = get_val(i, COL_STATUS)
        status = str(status_val).strip() if pd.notna(status_val) else ''
        
        if unit_str not in units:
            units[unit_str] = {
                'property_id': property_id,
                'property_name': property_name,
                'report_date': report_date,
                'unit_number': unit_str,
                'resident_name': None,
                'status': status,
                'current_balance': 0.0,
                'balance_0_30': 0.0,
                'balance_31_60': 0.0,
                'balance_61_90': 0.0,
                'balance_over_90': 0.0,
                'prepaid': 0.0,
                'total_delinquent': 0.0,
                'net_balance': 0.0,
            }
        
        rec = units[unit_str]
        if status and not rec['status']:
            rec['status'] = status
        
        # Sum financial columns across transaction codes for this unit
        rec['prepaid'] += safe_float(get_val(i, COL_PREPAID))
        rec['total_delinquent'] += safe_float(get_val(i, COL_DELINQUENT))
        rec['net_balance'] += safe_float(get_val(i, COL_NET_BALANCE))
        rec['current_balance'] += safe_float(get_val(i, COL_CURRENT))
        rec['balance_0_30'] += safe_float(get_val(i, COL_30_DAYS))
        rec['balance_31_60'] += safe_float(get_val(i, COL_60_DAYS))
        rec['balance_over_90'] += safe_float(get_val(i, COL_90_PLUS))
    
    return list(units.values())


def _parse_delinquency_summary(df, property_id, property_name, report_date, safe_float):
    """
    Parse summary format (report 4260, ~74 columns).
    Transaction-code level property summary — extract property-level totals.
    
    Column layout (from row ~19 headers):
    [3]=Description, [8]=D/P Account, [14]=Beginning Prepaid, [20]=Current Prepaid,
    [26]=Change In Prepaid, [31]=Beginning Delinquent, [37]=Current Delinquent,
    [42]=Change In Delinquent, [46]=Beginning Balance, [51]=Current Balance,
    [55]=Change In Balance
    """
    # Find the grand totals row (row ~54 or the row before "Summary by General Ledger")
    total_prepaid = 0.0
    total_delinquent = 0.0
    total_net_balance = 0.0
    
    for i in range(len(df)):
        # Look for the totals row (has values in cols 14, 20, 31, 37 but no description in col 3)
        desc = df.iloc[i, 3] if 3 < df.shape[1] else None
        acct = df.iloc[i, 8] if 8 < df.shape[1] else None
        
        if pd.isna(desc) and pd.isna(acct):
            cur_prepaid = safe_float(df.iloc[i, 20] if 20 < df.shape[1] else None)
            cur_delinquent = safe_float(df.iloc[i, 37] if 37 < df.shape[1] else None)
            cur_balance = safe_float(df.iloc[i, 51] if 51 < df.shape[1] else None)
            
            if cur_prepaid != 0 or cur_delinquent != 0 or cur_balance != 0:
                total_prepaid = cur_prepaid
                total_delinquent = cur_delinquent
                total_net_balance = cur_balance
    
    # Return a single property-level summary record
    if total_prepaid != 0 or total_delinquent != 0 or total_net_balance != 0:
        return [{
            'property_id': property_id,
            'property_name': property_name,
            'report_date': report_date,
            'unit_number': 'PROPERTY_TOTAL',
            'resident_name': None,
            'status': 'summary',
            'current_balance': total_delinquent,
            'balance_0_30': 0.0,
            'balance_31_60': 0.0,
            'balance_61_90': 0.0,
            'balance_over_90': 0.0,
            'prepaid': total_prepaid,
            'total_delinquent': total_delinquent,
            'net_balance': total_net_balance,
        }]
    
    return []


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
            if pd.isna(val):
                return 0.0
            return float(str(val).replace(',', ''))
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


def parse_projected_occupancy(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Projected Occupancy report (report 3842).
    
    Actual Excel layout (25 wide-spaced columns with merged cells):
      Col 0:  Week Ending
      Col 3:  # Occupied At Week Begin
      Col 9:  % Occupied At Week Begin
      Col 11: Scheduled Move-Ins
      Col 15: Scheduled Move-Outs
      Col 19: Projected # Occupied At Week End
      Col 24: Projected % Occupied At Week End
    
    Total Units found in header area: row with "Total Units:" has the count in the next column.
    Header row is the one containing "Week" + "Ending".
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']
    
    # Extract total units from header area (row with "Total Units:" → value in next col)
    total_units = 0
    for i in range(min(20, len(df))):
        for j in range(min(5, df.shape[1])):
            val = df.iloc[i, j]
            if pd.notna(val) and 'total units' in str(val).lower():
                # The number is in the next column
                if j + 1 < df.shape[1] and pd.notna(df.iloc[i, j + 1]):
                    try:
                        total_units = int(float(df.iloc[i, j + 1]))
                    except (ValueError, TypeError):
                        pass
                break
        if total_units > 0:
            break
    
    # Find header row containing "Week" + "Ending"
    header_row = None
    for i in range(min(20, len(df))):
        row_text = ' '.join(str(x) for x in df.iloc[i].dropna().tolist()).lower()
        if 'week' in row_text and 'end' in row_text:
            header_row = i
            break
    
    if header_row is None:
        return []
    
    # Map columns by scanning header row(s) for known labels
    # The report uses multi-row headers with merged cells, so scan rows header_row-2..header_row+2
    col_map = {}
    for scan_row in range(max(0, header_row - 2), min(len(df), header_row + 3)):
        for j in range(df.shape[1]):
            val = df.iloc[scan_row, j]
            if pd.isna(val):
                continue
            h = str(val).replace('\n', ' ').replace('\r', '').strip().lower()
            if 'week' in h and 'end' in h:
                col_map['week_ending'] = j
            elif 'move' in h and 'in' in h and 'out' not in h:
                col_map['move_ins'] = j
            elif 'move' in h and 'out' in h:
                col_map['move_outs'] = j
            elif 'projected' in h and '#' in h:
                col_map['occupied_end'] = j
            elif 'projected' in h and '%' in h:
                col_map['pct_end'] = j
            elif '# occupied' in h or h == '# occupied':
                col_map['occupied_begin'] = j
            elif '% occupied' in h and 'projected' not in h:
                col_map.setdefault('pct_begin', j)
    
    # Fallback: known fixed positions from actual RealPage Excel layout
    col_map.setdefault('week_ending', 0)
    col_map.setdefault('occupied_begin', 3)
    col_map.setdefault('pct_begin', 9)
    col_map.setdefault('move_ins', 11)
    col_map.setdefault('move_outs', 15)
    col_map.setdefault('occupied_end', 19)
    col_map.setdefault('pct_end', 24)
    
    def safe_int(val):
        try:
            return int(val) if pd.notna(val) else 0
        except:
            return 0
    
    def safe_float(val):
        try:
            if pd.isna(val):
                return 0.0
            return float(str(val).replace(',', '').replace('%', ''))
        except:
            return 0.0
    
    def safe_str(val):
        if pd.notna(val):
            s = str(val).strip()
            return s if s and s != 'nan' else None
        return None
    
    # Data rows start after the header block (skip blank rows after header)
    data_start = header_row + 1
    
    records = []
    for i in range(data_start, len(df)):
        row = df.iloc[i].tolist()
        
        week_ending = safe_str(row[col_map['week_ending']])
        if not week_ending:
            continue
        
        # Skip totals/subtotals
        if 'total' in str(week_ending).lower():
            continue
        
        # Validate it looks like a date (MM/DD/YYYY)
        if not re.match(r'\d{2}/\d{2}/\d{4}', str(week_ending)):
            continue
        
        record = {
            'property_id': property_id,
            'property_name': property_name,
            'report_date': report_date,
            'week_ending': week_ending,
            'occupied_begin': safe_int(row[col_map['occupied_begin']]),
            'pct_occupied_begin': safe_float(row[col_map['pct_begin']]),
            'scheduled_move_ins': safe_int(row[col_map['move_ins']]),
            'scheduled_move_outs': safe_int(row[col_map['move_outs']]),
            'occupied_end': safe_int(row[col_map['occupied_end']]),
            'pct_occupied_end': safe_float(row[col_map['pct_end']]),
            'total_units': total_units,
        }
        records.append(record)
    
    return records


def parse_lease_expiration_renewal(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Lease Expiration Renewal Detail report (Report 4156).
    .xls format (old Compound Document), needs engine='xlrd'.
    
    5 sheets: Table of Contents, Lease Expiration Detail, Renewal Detail,
    Summary by Floorplan, Future by Floorplan, Summary by Leasing Consultant.
    
    Returns combined records from Expiration Detail + Summary by Floorplan.
    """
    from datetime import datetime
    
    try:
        sheets = pd.read_excel(file_path, sheet_name=None, engine='xlrd', header=None)
    except Exception:
        # May be .xlsx format
        sheets = pd.read_excel(file_path, sheet_name=None, header=None)
    
    report_date = datetime.now().strftime('%Y-%m-%d')
    records = []
    
    def safe_float(val):
        if pd.isna(val):
            return 0.0
        try:
            s = str(val).replace(',', '').replace('(', '-').replace(')', '').strip()
            return float(s) if s else 0.0
        except:
            return 0.0
    
    def safe_int(val):
        try:
            return int(float(val)) if pd.notna(val) else 0
        except:
            return 0
    
    def safe_date(val):
        if pd.isna(val):
            return None
        s = str(val).strip()
        # Handle "2/15/2026 12:00:00 AM" format
        for fmt in ('%m/%d/%Y %I:%M:%S %p', '%m/%d/%Y', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d'):
            try:
                return datetime.strptime(s, fmt).strftime('%m/%d/%Y')
            except:
                continue
        return s.split(' ')[0] if ' ' in s else s
    
    # --- Parse Lease Expiration Detail sheet ---
    exp_sheet = None
    for name, df in sheets.items():
        if 'expiration' in name.lower() and 'detail' in name.lower():
            exp_sheet = df
            break
    
    if exp_sheet is not None:
        # Find header row (contains 'Bldg/Unit')
        header_row = None
        for i in range(min(10, len(exp_sheet))):
            row_vals = [str(v).strip() for v in exp_sheet.iloc[i].tolist() if pd.notna(v)]
            if any('bldg' in v.lower() or 'unit' in v.lower() for v in row_vals):
                header_row = i
                break
        
        if header_row is not None:
            for i in range(header_row + 1, len(exp_sheet)):
                row = exp_sheet.iloc[i].tolist()
                unit = row[0] if len(row) > 0 else None
                if pd.isna(unit) or str(unit).strip() == '' or 'total' in str(unit).lower():
                    continue
                
                record = {
                    '_type': 'detail',
                    'property_id': property_id,
                    'report_date': report_date,
                    'unit_number': str(unit).strip(),
                    'floorplan': str(row[1]).strip() if len(row) > 1 and pd.notna(row[1]) else None,
                    'actual_rent': safe_float(row[3]) if len(row) > 3 else 0.0,
                    'other_billings': safe_float(row[5]) if len(row) > 5 else 0.0,
                    'last_increase_date': safe_date(row[7]) if len(row) > 7 else None,
                    'last_increase_amount': safe_float(row[9]) if len(row) > 9 else 0.0,
                    'market_rent': safe_float(row[10]) if len(row) > 10 else 0.0,
                    'move_in_date': safe_date(row[12]) if len(row) > 12 else None,
                    'lease_end_date': safe_date(row[14]) if len(row) > 14 else None,
                    'decision': str(row[15]).strip() if len(row) > 15 and pd.notna(row[15]) else None,
                    'new_lease_start': safe_date(row[16]) if len(row) > 16 else None,
                    'new_lease_term': safe_int(row[17]) if len(row) > 17 else 0,
                    'new_rent': safe_float(row[18]) if len(row) > 18 else 0.0,
                    'new_other_billings': safe_float(row[19]) if len(row) > 19 else 0.0,
                }
                records.append(record)
    
    # --- Parse Summary by Floorplan sheet ---
    summary_sheet = None
    for name, df in sheets.items():
        if 'summary' in name.lower() and 'floorplan' in name.lower():
            summary_sheet = df
            break
    
    if summary_sheet is not None:
        header_row = None
        for i in range(min(10, len(summary_sheet))):
            row_vals = [str(v).strip().lower() for v in summary_sheet.iloc[i].tolist() if pd.notna(v)]
            if any('floor' in v for v in row_vals):
                header_row = i
                break
        
        if header_row is not None:
            for i in range(header_row + 1, len(summary_sheet)):
                row = summary_sheet.iloc[i].tolist()
                fp = row[0] if len(row) > 0 else None
                if pd.isna(fp) or str(fp).strip() == '' or 'total' in str(fp).lower():
                    continue
                
                record = {
                    '_type': 'summary',
                    'property_id': property_id,
                    'report_date': report_date,
                    'floorplan': str(fp).strip(),
                    'total_possible': safe_int(row[1]) if len(row) > 1 else 0,
                    'renewed': safe_int(row[2]) if len(row) > 2 else 0,
                    'vacating': safe_int(row[3]) if len(row) > 3 else 0,
                    'unknown': safe_int(row[4]) if len(row) > 4 else 0,
                    'month_to_month': safe_int(row[5]) if len(row) > 5 else 0,
                    'avg_term_renewed': safe_float(row[6]) if len(row) > 6 else 0.0,
                    'avg_new_rent': safe_float(row[7]) if len(row) > 7 else 0.0,
                    'avg_market_rent': safe_float(row[8]) if len(row) > 8 else 0.0,
                }
                records.append(record)
    
    return records


def parse_monthly_transaction_summary(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Monthly Transaction Summary report (report 4020).
    
    Extracts two record types:
    1. 'detail' — Individual transaction codes with YTD and current month amounts
       Columns: Group(0), Code(5), Description(9), YTD_Last_Month(19), This_Month(29), YTD_Through(35)
    2. 'summary' — P&L-like financial summary from the bottom of the report
       Lines: Gross Market Rent, Total Other Monthly Charges, Total Possible Monthly Collections,
       Less Collection Losses, Adjustments, Past Due/Prepaid changes, Total Monthly Collections
    
    Returns list of dicts, each with '_type' = 'detail' or 'summary'.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']
    fiscal_period = info['fiscal_period']
    
    # Also extract fiscal period from report content if not found in header
    if not fiscal_period:
        for i in range(min(10, len(df))):
            row_text = ' '.join(str(x) for x in df.iloc[i].dropna().tolist())
            fp_match = re.search(r'Fiscal Period:\s*(\d{6})', row_text)
            if fp_match:
                fiscal_period = fp_match.group(1)
                break
    
    def safe_float(val):
        try:
            if pd.isna(val):
                return 0.0
            return float(str(val).replace(',', ''))
        except:
            return 0.0
    
    records = []
    
    # ── Parse Detail Section ──
    # Detail rows have: Group in col 0, Code in col 5, Description in col 9,
    # YTD Last Month in col 19, This Month in col 29, YTD Through in col 35
    # They appear before the summary section (before "Category" header row)
    summary_start = None
    
    for i in range(7, len(df)):
        row = df.iloc[i]
        col0 = str(row[0]).strip() if pd.notna(row[0]) else ''
        
        # Detect start of summary section
        if col0 == 'Category':
            summary_start = i
            break
        
        # Also detect "Net" rows in the GL section — these are Net GL entries, skip for detail
        if col0 == 'Net':
            continue
        
        # Skip header rows and page breaks
        if col0 == 'Group' or col0 == '':
            # Check if it's a "Total:" row
            desc = str(row[9]).strip() if pd.notna(row[9]) else ''
            if desc == 'Total:':
                continue
            if not col0:
                continue
        
        code = str(row[5]).strip() if pd.notna(row[5]) else ''
        desc = str(row[9]).strip() if pd.notna(row[9]) else ''
        
        # Must have a valid transaction group and code
        if not col0 or not code or not desc:
            continue
        
        # Skip if group looks like a summary label
        if len(col0) > 6 or 'Total' in col0:
            continue
        
        ytd_last = safe_float(row[19])
        this_month = safe_float(row[29])
        ytd_through = safe_float(row[35])
        
        # Skip rows with all zeros
        if ytd_last == 0 and this_month == 0 and ytd_through == 0:
            continue
        
        records.append({
            '_type': 'detail',
            'property_id': property_id,
            'property_name': property_name,
            'report_date': report_date,
            'fiscal_period': fiscal_period,
            'transaction_group': col0,
            'transaction_code': code,
            'description': desc,
            'ytd_last_month': ytd_last,
            'this_month': this_month,
            'ytd_through_month': ytd_through,
        })
    
    # ── Parse P&L Summary Section ──
    # The summary section starts with "Category" header and contains:
    # - MONTHLY RENTAL POTENTIAL COMPUTATION
    # - OTHER MONTHLY CHARGES (line items)
    # - LESS MONTHLY COLLECTION LOSSES
    # - LESS ADJUSTMENTS
    # - PAST DUES/PREPAIDS
    # Key totals are in specific columns: col 14 (amounts), col 23 (subtotals), col 31 (totals)
    summary = {
        '_type': 'summary',
        'property_id': property_id,
        'property_name': property_name,
        'report_date': report_date,
        'fiscal_period': fiscal_period,
        'gross_market_rent': 0.0,
        'gain_to_lease': 0.0,
        'loss_to_lease': 0.0,
        'gross_potential': 0.0,
        'total_other_charges': 0.0,
        'total_possible_collections': 0.0,
        'total_collection_losses': 0.0,
        'total_adjustments': 0.0,
        'past_due_end_prior': 0.0,
        'prepaid_end_prior': 0.0,
        'past_due_end_current': 0.0,
        'prepaid_end_current': 0.0,
        'net_change_past_due_prepaid': 0.0,
        'total_losses_and_adjustments': 0.0,
        'current_monthly_collections': 0.0,
        'total_monthly_collections': 0.0,
    }
    
    if summary_start:
        # Map summary labels to fields
        label_map = {
            'Gross Market Rent': ('gross_market_rent', 14),
            'Gain To Old Lease': ('gain_to_lease', 14),
            'Loss To Old Lease': ('loss_to_lease', 14),
            'Gross Potential Monthly Per Leases': ('gross_potential', 23),
            'Total Other Monthly Charges': ('total_other_charges', 23),
            'Total Possible Monthly Collections': ('total_possible_collections', 31),
            'Less Total Monthly Collection Losses': ('total_collection_losses', 23),
            'Less Adjustments': ('total_adjustments', 23),
            'Past Due End of Prior Month': ('past_due_end_prior', 14),
            'Prepaid End of Prior Month': ('prepaid_end_prior', 14),
            'Past Due End of Current Month': ('past_due_end_current', 14),
            'Prepaid End of Current Month': ('prepaid_end_current', 14),
            'Net Change to Past Due/Prepaid Balances': ('net_change_past_due_prepaid', 23),
            'Total Monthly Collection Losses and Adjustments': ('total_losses_and_adjustments', 31),
            'Current Monthly Rental Collections': ('current_monthly_collections', 31),
            'Total Monthly Collections': ('total_monthly_collections', 31),
        }
        
        for i in range(summary_start, len(df)):
            row = df.iloc[i]
            label = str(row[0]).strip() if pd.notna(row[0]) else ''
            
            # Remove trailing colons and asterisks
            label_clean = label.rstrip(':').rstrip('*').strip()
            
            if label_clean in label_map:
                field, col_idx = label_map[label_clean]
                # Value might be on the same row or the next row
                val = safe_float(row[col_idx]) if col_idx < len(row) else 0.0
                if val == 0.0 and i + 1 < len(df):
                    next_row = df.iloc[i + 1]
                    val = safe_float(next_row[col_idx]) if col_idx < len(next_row) else 0.0
                summary[field] = val
    
    records.append(summary)
    
    return records


def parse_make_ready_summary(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Make Ready Summary report (report 4186).
    Units in make-ready pipeline, grouped by unit with WO sub-rows.
    Col mapping: c1=days_vacant, c2=date_vacated, c6=date_due, c9=unit, c10=sqft, c11=num_WOs.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']

    def safe_int(val):
        try:
            return int(float(val)) if pd.notna(val) else 0
        except:
            return 0

    def safe_str(val):
        if pd.notna(val):
            s = str(val).strip()
            return s if s and s != 'nan' else None
        return None

    # Find header row (contains "Days vacant" and "Unit")
    header_row = None
    for i in range(min(15, len(df))):
        row_text = ' '.join(str(x) for x in df.iloc[i].dropna().tolist()).lower()
        if 'days vacant' in row_text and 'unit' in row_text:
            header_row = i
            break

    if header_row is None:
        return []

    records = []
    for i in range(header_row + 1, len(df)):
        unit_val = df.iloc[i, 9] if 9 < df.shape[1] else None
        if pd.isna(unit_val):
            continue
        unit_str = str(unit_val).strip()
        if not unit_str or 'total' in unit_str.lower():
            continue

        records.append({
            'property_id': property_id,
            'property_name': property_name,
            'report_date': report_date,
            'unit': unit_str,
            'sqft': safe_int(df.iloc[i, 10]) if 10 < df.shape[1] else 0,
            'days_vacant': safe_int(df.iloc[i, 1]) if 1 < df.shape[1] else 0,
            'date_vacated': safe_str(df.iloc[i, 2]) if 2 < df.shape[1] else None,
            'date_due': safe_str(df.iloc[i, 6]) if 6 < df.shape[1] else None,
            'num_work_orders': safe_int(df.iloc[i, 11]) if 11 < df.shape[1] else 0,
            'status': 'open',
        })

    return records


def parse_closed_make_ready(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Closed Make Ready Summary report (report 4189).
    Completed make-ready WOs, grouped by unit.
    Col mapping: c2=unit, c5=num_WOs, c10=date_closed, c12=amount_charged.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']

    def safe_int(val):
        try:
            return int(float(val)) if pd.notna(val) else 0
        except:
            return 0

    def safe_float(val):
        try:
            if pd.isna(val):
                return 0.0
            return float(str(val).replace(',', ''))
        except:
            return 0.0

    def safe_str(val):
        if pd.notna(val):
            s = str(val).strip()
            return s if s and s != 'nan' else None
        return None

    # Find header rows (row with "Bldg" and "Unit")
    header_row = None
    for i in range(min(15, len(df))):
        row_text = ' '.join(str(x) for x in df.iloc[i].dropna().tolist()).lower()
        if 'bldg' in row_text and 'unit' in row_text:
            header_row = i
            break

    if header_row is None:
        return []

    records = []
    for i in range(header_row + 1, len(df)):
        unit_val = df.iloc[i, 2] if 2 < df.shape[1] else None
        if pd.isna(unit_val):
            continue
        unit_str = str(unit_val).strip()
        if not unit_str or 'total' in unit_str.lower() or 'grand' in unit_str.lower():
            continue

        # Get the first date_closed for this unit from its WO sub-rows
        date_closed = safe_str(df.iloc[i, 10]) if 10 < df.shape[1] else None
        if not date_closed:
            # Check next row for date
            for j in range(i + 1, min(i + 10, len(df))):
                dc = df.iloc[j, 10] if 10 < df.shape[1] else None
                if pd.notna(dc):
                    date_closed = safe_str(dc)
                    break

        records.append({
            'property_id': property_id,
            'property_name': property_name,
            'report_date': report_date,
            'unit': unit_str,
            'num_work_orders': safe_int(df.iloc[i, 5]) if 5 < df.shape[1] else 0,
            'date_closed': date_closed,
            'amount_charged': safe_float(df.iloc[i, 12]) if 12 < df.shape[1] else 0.0,
        })

    return records


def parse_advertising_source(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Primary Advertising Source Evaluation report (report 4158).
    37-column wide layout. Only parse first section (before "Totals:" row).
    Col mapping: c0=source, c2=new_prospects, c7=phone_calls, c13=visits(leasing),
    c15=return_visits, c19=leases, c25=cancelled_denied, c29=net_leases,
    c35=prospect_to_lease_pct, c36=visit_to_lease_pct.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']

    # Extract date range from header area
    date_range = ''
    for i in range(min(10, len(df))):
        val = df.iloc[i, 3] if 3 < df.shape[1] else None
        if pd.notna(val) and 'through' in str(val):
            date_range = str(val).strip()
            break

    COL = {
        'source': 0, 'new_prospects': 2, 'phone_calls': 7,
        'visits': 13, 'return_visits': 15,
        'leases': 19, 'cancelled_denied': 25, 'net_leases': 29,
        'prospect_to_lease_pct': 35, 'visit_to_lease_pct': 36,
    }

    def safe_int(val):
        try:
            return int(float(val)) if pd.notna(val) else 0
        except:
            return 0

    def safe_pct(val):
        try:
            if pd.isna(val):
                return 0.0
            return float(str(val).replace('%', '').replace(',', '').strip())
        except:
            return 0.0

    # Find first "Advertising Source" header row
    start_row = None
    for i in range(min(20, len(df))):
        val = df.iloc[i, 0]
        if pd.notna(val) and 'Advertising Source' in str(val):
            start_row = i + 1
            break

    if start_row is None:
        return []

    records = []
    for i in range(start_row, len(df)):
        src = df.iloc[i, 0]
        if pd.notna(src):
            src_str = str(src).strip()
            if src_str == 'Totals:' or src_str.startswith('Contact Types'):
                break
            if not src_str or src_str.startswith('*'):
                continue

            row = {}
            for field, col in COL.items():
                if field == 'source':
                    row[field] = src_str
                elif field in ('prospect_to_lease_pct', 'visit_to_lease_pct'):
                    row[field] = safe_pct(df.iloc[i, col]) if col < df.shape[1] else 0.0
                else:
                    row[field] = safe_int(df.iloc[i, col]) if col < df.shape[1] else 0

            # Only include rows with any activity
            if any(row.get(f, 0) > 0 for f in ['new_prospects', 'phone_calls', 'visits', 'leases', 'net_leases']):
                row['property_id'] = property_id
                row['property_name'] = property_name
                row['report_date'] = report_date
                row['date_range'] = date_range
                records.append(row)

    return records


def parse_lost_rent_summary(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Lost Rent Summary report (report 4279).
    Clean tabular format starting at row 7 (header at row 6).
    Col mapping: c0=location_id, c1=location_name, c2=unit, c3=resident_name,
    c4=move_in_date, c5=move_out_date, c6=days_occupied, c7=market_rent,
    c8=lease_rent, c9=rent_charged, c12=loss_to_rent, c14=gain_to_rent,
    c16=vacancy_current, c17=vacancy_adjustments, c18=market_rent_calculated,
    c19=lost_rent_not_charged.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    info = extract_property_info(df)
    property_name = info['property_name']
    report_date = info['report_date']

    # Extract fiscal period
    fiscal_period = None
    for i in range(min(6, len(df))):
        for c in range(min(10, df.shape[1])):
            val = df.iloc[i, c]
            if pd.notna(val) and 'Fiscal period' in str(val):
                fp_match = re.search(r'(\d{6})', str(val))
                if fp_match:
                    fiscal_period = fp_match.group(1)
                break

    # Find header row (contains "Market Rent" and "Bldg-Unit")
    header_row = None
    for i in range(min(10, len(df))):
        row_text = ' '.join(str(x) for x in df.iloc[i].dropna().tolist()).lower()
        if 'market rent' in row_text and ('bldg' in row_text or 'unit' in row_text):
            header_row = i
            break

    if header_row is None:
        return []

    def safe_float(val):
        try:
            if pd.isna(val):
                return 0.0
            return float(str(val).replace(',', ''))
        except:
            return 0.0

    def safe_str(val):
        if pd.notna(val):
            s = str(val).strip()
            return s if s and s != 'nan' else None
        return None

    records = []
    for i in range(header_row + 1, len(df)):
        unit_val = df.iloc[i, 2] if 2 < df.shape[1] else None
        if pd.isna(unit_val):
            continue
        unit_str = str(unit_val).strip()
        if not unit_str or 'total' in unit_str.lower() or 'grand' in unit_str.lower():
            continue

        records.append({
            'property_id': property_id,
            'property_name': property_name,
            'report_date': report_date,
            'fiscal_period': fiscal_period,
            'unit': unit_str,
            'move_in_date': safe_str(df.iloc[i, 4]) if 4 < df.shape[1] else None,
            'move_out_date': safe_str(df.iloc[i, 5]) if 5 < df.shape[1] else None,
            'market_rent': safe_float(df.iloc[i, 7]) if 7 < df.shape[1] else 0.0,
            'lease_rent': safe_float(df.iloc[i, 8]) if 8 < df.shape[1] else 0.0,
            'rent_charged': safe_float(df.iloc[i, 9]) if 9 < df.shape[1] else 0.0,
            'loss_to_rent': safe_float(df.iloc[i, 12]) if 12 < df.shape[1] else 0.0,
            'gain_to_rent': safe_float(df.iloc[i, 14]) if 14 < df.shape[1] else 0.0,
            'vacancy_current': safe_float(df.iloc[i, 16]) if 16 < df.shape[1] else 0.0,
            'vacancy_adjustments': safe_float(df.iloc[i, 17]) if 17 < df.shape[1] else 0.0,
            'market_rent_calculated': safe_float(df.iloc[i, 18]) if 18 < df.shape[1] else 0.0,
            'lost_rent_not_charged': safe_float(df.iloc[i, 19]) if 19 < df.shape[1] else 0.0,
        })

    return records


def parse_move_out_reasons(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """
    Parse Reasons for Move Out report (3879).
    Returns list of records with category, reason, count, percentage, and resident_type.
    """
    df = pd.read_excel(file_path, sheet_name=0, header=None)
    
    info = extract_property_info(df)
    property_name = info.get('property_name')
    report_date = info.get('report_date')
    
    # Detect resident_type from Parameters row
    resident_type = 'former'
    date_range = None
    for i in range(min(10, len(df))):
        row_text = ' '.join(str(x) for x in df.iloc[i].dropna().tolist())
        if 'Parameters:' in row_text:
            if 'Residents On Notice' in row_text:
                resident_type = 'notice'
            elif 'Former Residents' in row_text:
                resident_type = 'former'
        if 'Report run from' in row_text:
            m = re.search(r'from\s+(\d{2}/\d{2}/\d{4})\s+to\s+(\d{2}/\d{2}/\d{4})', row_text)
            if m:
                date_range = f"{m.group(1)} through {m.group(2)}"
    
    records = []
    current_category = None
    category_count = 0
    category_pct = 0.0
    
    for i in range(8, len(df)):
        row = df.iloc[i].tolist()
        col0 = str(row[0]).strip() if pd.notna(row[0]) and str(row[0]).strip() else ''
        col3 = str(row[3]).strip() if len(row) > 3 and pd.notna(row[3]) and str(row[3]).strip() else ''
        col4 = row[4] if len(row) > 4 and pd.notna(row[4]) else None
        col5 = row[5] if len(row) > 5 and pd.notna(row[5]) else None
        col7 = row[7] if len(row) > 7 and pd.notna(row[7]) else None
        col8 = row[8] if len(row) > 8 and pd.notna(row[8]) else None
        
        if col0 == 'Totals:':
            break
        
        # Category row: col[0] has name, col[5] has count, col[8] has pct
        if col0 and col5 is not None:
            current_category = col0
            category_count = int(float(col5))
            category_pct = float(col8) if col8 is not None else 0.0
        # Reason row: col[3] has name, col[4] has count, col[7] has pct
        elif col3 and col4 is not None and current_category:
            records.append({
                'property_id': property_id,
                'property_name': property_name,
                'report_date': report_date,
                'date_range': date_range,
                'resident_type': resident_type,
                'category': current_category,
                'category_count': category_count,
                'category_pct': category_pct,
                'reason': col3,
                'reason_count': int(float(col4)),
                'reason_pct': float(col7) if col7 is not None else 0.0,
            })
    
    return records


def parse_lease_details(file_path: str, property_id: str = None) -> List[Dict[str, Any]]:
    """Parse Lease Details report (CSV format from RealPage).
    
    CSV columns: Lease id, Floor plan, Occupancy status, Lease start date,
    Lease end date, Move-in date, Moved out date, Applied date,
    Lease approved date, Notice given date, Lease term, Lease Rent,
    Lease Total, Ledger Balance, Move out notice type, Move out reason
    """
    records = []
    content = Path(file_path).read_text(encoding='utf-8', errors='replace')
    reader = csv.DictReader(io.StringIO(content))
    
    for row in reader:
        def clean_money(v):
            if not v or not v.strip():
                return None
            return float(v.replace(',', '').replace('$', '').strip())
        
        def clean_str(v):
            if not v or not v.strip():
                return None
            return v.strip()
        
        records.append({
            'property_id': property_id,
            'lease_id': clean_str(row.get('Lease id')),
            'floorplan': clean_str(row.get('Floor plan')),
            'occupancy_status': clean_str(row.get('Occupancy status')),
            'lease_start_date': clean_str(row.get('Lease start date')),
            'lease_end_date': clean_str(row.get('Lease end date')),
            'move_in_date': clean_str(row.get('Move-in date')),
            'move_out_date': clean_str(row.get('Moved out date')),
            'applied_date': clean_str(row.get('Applied date')),
            'lease_approved_date': clean_str(row.get('Lease approved date')),
            'notice_given_date': clean_str(row.get('Notice given date')),
            'lease_term': clean_str(row.get('Lease term')),
            'lease_rent': clean_money(row.get('Lease Rent')),
            'lease_total': clean_money(row.get('Lease Total')),
            'ledger_balance': clean_money(row.get('Ledger Balance')),
            'move_out_notice_type': clean_str(row.get('Move out notice type')),
            'move_out_reason': clean_str(row.get('Move out reason')),
        })
    
    return records


def parse_report(file_path: str, property_id: str = None, file_id: str = None, report_type_hint: str = None) -> Dict[str, Any]:
    """
    Parse a report file and return structured data.
    Auto-detects report type, falls back to report_type_hint if detection fails.
    """
    # CSV files: route directly by hint (no Excel auto-detection)
    if file_path.endswith('.csv') and report_type_hint == 'lease_details':
        records = parse_lease_details(file_path, property_id)
        for r in records:
            r['file_id'] = file_id
        return {'report_type': 'lease_details', 'records': records, 'file_path': str(file_path), 'file_id': file_id}

    try:
        df = pd.read_excel(file_path, sheet_name=0, header=None)
    except Exception as e:
        return {'error': str(e), 'report_type': None, 'records': []}
    
    report_type = detect_report_type(df)
    
    # Fall back to hint if auto-detection failed
    if not report_type and report_type_hint:
        # Map download type keys to parser type keys
        hint_map = {
            'delinquency_prepaid': 'delinquency',
            'activity_report': 'activity',
            'monthly_activity_summary': 'monthly_summary',
            'projected_occupancy': 'projected_occupancy',
            'lease_expiration_renewal': 'lease_expiration_renewal',
            'monthly_transaction_summary': 'monthly_transaction_summary',
            'make_ready_summary': 'make_ready_summary',
            'closed_make_ready': 'closed_make_ready',
            'advertising_source': 'advertising_source',
            'lost_rent_summary': 'lost_rent_summary',
            'move_out_reasons': 'move_out_reasons',
            'lease_details': 'lease_details',
        }
        report_type = hint_map.get(report_type_hint, report_type_hint)
    
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
    elif report_type == 'lease_expiration_renewal':
        records = parse_lease_expiration_renewal(file_path, property_id)
    elif report_type == 'projected_occupancy':
        records = parse_projected_occupancy(file_path, property_id)
    elif report_type == 'monthly_transaction_summary':
        records = parse_monthly_transaction_summary(file_path, property_id)
    elif report_type == 'make_ready_summary':
        records = parse_make_ready_summary(file_path, property_id)
    elif report_type == 'closed_make_ready':
        records = parse_closed_make_ready(file_path, property_id)
    elif report_type == 'advertising_source':
        records = parse_advertising_source(file_path, property_id)
    elif report_type == 'lost_rent_summary':
        records = parse_lost_rent_summary(file_path, property_id)
    elif report_type == 'move_out_reasons':
        records = parse_move_out_reasons(file_path, property_id)
    elif report_type == 'lease_details':
        records = parse_lease_details(file_path, property_id)
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
