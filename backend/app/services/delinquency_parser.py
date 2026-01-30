"""
Parser for RealPage Delinquent and Prepaid Reports.

Extracts delinquency, eviction, and collections data from Excel reports.
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, asdict
import re


@dataclass
class DelinquencyAging:
    """Delinquency amounts by aging bucket."""
    current: float = 0.0
    days_0_30: float = 0.0
    days_31_60: float = 0.0
    days_61_90: float = 0.0
    days_90_plus: float = 0.0
    total: float = 0.0


@dataclass
class EvictionSummary:
    """Eviction status summary."""
    total_balance: float = 0.0
    unit_count: int = 0
    filed_count: int = 0
    writ_count: int = 0


@dataclass
class CollectionsSummary:
    """Post-eviction collections by aging bucket."""
    days_0_30: float = 0.0
    days_31_60: float = 0.0
    days_61_90: float = 0.0
    days_90_plus: float = 0.0
    total: float = 0.0


@dataclass
class PropertyDelinquencyReport:
    """Complete delinquency report for a property."""
    property_name: str
    report_date: str
    total_prepaid: float
    total_delinquent: float
    net_balance: float
    delinquency_aging: DelinquencyAging
    evictions: EvictionSummary
    collections: CollectionsSummary
    deposits_held: float
    outstanding_deposits: float
    resident_details: List[Dict[str, Any]]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'property_name': self.property_name,
            'report_date': self.report_date,
            'total_prepaid': self.total_prepaid,
            'total_delinquent': self.total_delinquent,
            'net_balance': self.net_balance,
            'delinquency_aging': asdict(self.delinquency_aging),
            'evictions': asdict(self.evictions),
            'collections': asdict(self.collections),
            'deposits_held': self.deposits_held,
            'outstanding_deposits': self.outstanding_deposits,
            'resident_count': len(self.resident_details),
        }


class DelinquencyReportParser:
    """Parser for RealPage Delinquent and Prepaid Reports."""
    
    # Column indices based on report structure (0-indexed)
    # Unit header row columns
    COL_UNIT = 1
    COL_STATUS = 9
    COL_MOVE_DATE = 13
    COL_DEPOSITS_HELD = 65
    COL_OUTSTANDING_DEPOSIT = 70
    
    # Transaction/subtotal row columns
    COL_CODE_DESC = 18
    COL_TOTAL_PREPAID = 23  # In transaction rows
    COL_TOTAL_DELINQUENT = 29  # In transaction rows
    COL_NET_BALANCE = 39
    COL_CURRENT = 43
    COL_30_DAYS = 48
    COL_60_DAYS = 52
    COL_90_PLUS_DAYS = 55
    
    def __init__(self, file_path: str):
        self.file_path = Path(file_path)
        self.df: Optional[pd.DataFrame] = None
        self.property_name: str = ""
        self.report_date: str = ""
        
    def parse(self) -> PropertyDelinquencyReport:
        """Parse the Excel report and extract all data."""
        self.df = pd.read_excel(self.file_path, header=None)
        
        # Extract metadata from header rows
        self._extract_metadata()
        
        # Find Grand Totals row
        totals = self._extract_grand_totals()
        
        # Extract resident-level details
        residents = self._extract_resident_details()
        
        # Calculate eviction summary from resident details
        evictions = self._calculate_eviction_summary(residents)
        
        # Build aging breakdown
        aging = DelinquencyAging(
            current=totals.get('current', 0),
            days_0_30=totals.get('current', 0),  # Current = 0-30 days
            days_31_60=totals.get('days_30', 0),
            days_61_90=totals.get('days_60', 0),
            days_90_plus=totals.get('days_90_plus', 0),
            total=totals.get('total_delinquent', 0),
        )
        
        # Collections (former residents with balances)
        collections = self._calculate_collections_summary(residents)
        
        return PropertyDelinquencyReport(
            property_name=self.property_name,
            report_date=self.report_date,
            total_prepaid=totals.get('total_prepaid', 0),
            total_delinquent=totals.get('total_delinquent', 0),
            net_balance=totals.get('net_balance', 0),
            delinquency_aging=aging,
            evictions=evictions,
            collections=collections,
            deposits_held=totals.get('deposits_held', 0),
            outstanding_deposits=totals.get('outstanding_deposit', 0),
            resident_details=residents,
        )
    
    def _extract_metadata(self):
        """Extract property name and report date from header."""
        for i in range(min(15, len(self.df))):
            row = self.df.iloc[i]
            row_values = [str(x) for x in row.values if pd.notna(x)]
            row_str = ' '.join(row_values)
            
            # Look for property name in row 1 (format: "Company - Property")
            if i == 1 and len(row_values) >= 2:
                # Second value typically has "Company - Property Name"
                name_part = row_values[1] if len(row_values) > 1 else row_values[0]
                if ' - ' in name_part:
                    self.property_name = name_part.split(' - ')[-1].strip()
                else:
                    self.property_name = name_part.strip()
            
            # Look for date pattern
            date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', row_str)
            if date_match:
                self.report_date = date_match.group(1)
    
    def _extract_grand_totals(self) -> Dict[str, float]:
        """Extract grand totals from the report."""
        totals = {}
        
        # Search for Grand Totals row with aging data (has numeric values after "Grand Totals:")
        for i in range(len(self.df)):
            row = self.df.iloc[i]
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            
            # Look for Grand Totals row that has aging data (not the summary one)
            if 'Grand Totals:' in row_str:
                # Check if this row has numeric aging data (col 43, 48, 52, 55)
                has_aging = (
                    len(row) > 55 and 
                    pd.notna(row.iloc[43]) and 
                    pd.notna(row.iloc[48])
                )
                
                if has_aging:
                    # Extract values from known column positions
                    totals['total_prepaid'] = self._safe_float(row.iloc[23] if len(row) > 23 else None)
                    totals['total_delinquent'] = self._safe_float(row.iloc[30] if len(row) > 30 else None)
                    totals['net_balance'] = self._safe_float(row.iloc[39] if len(row) > 39 else None)
                    totals['current'] = self._safe_float(row.iloc[43] if len(row) > 43 else None)
                    totals['days_30'] = self._safe_float(row.iloc[48] if len(row) > 48 else None)
                    totals['days_60'] = self._safe_float(row.iloc[52] if len(row) > 52 else None)
                    totals['days_90_plus'] = self._safe_float(row.iloc[55] if len(row) > 55 else None)
                    totals['deposits_held'] = self._safe_float(row.iloc[60] if len(row) > 60 else None)
                    totals['outstanding_deposit'] = self._safe_float(row.iloc[65] if len(row) > 65 else None)
                    break
        
        return totals
    
    def _extract_resident_details(self) -> List[Dict[str, Any]]:
        """Extract individual resident delinquency details.
        
        Report structure:
        - Unit header row: Col 1=unit, Col 9=status, Col 13=move date, Col 65=deposits
        - Transaction rows: Col 18=code, Col 23=prepaid, Col 29=delinquent, Col 43-55=aging
        - Subtotals row: Aggregates all transactions for the unit
        """
        residents = []
        seen_units = set()
        
        current_unit = None
        current_status = ''
        current_is_eviction = False
        current_deposits = 0.0
        
        for i, row in self.df.iterrows():
            row_str = ' '.join([str(x) for x in row.values if pd.notna(x)])
            
            # Skip header rows
            if 'Unit' in row_str and 'Status' in row_str and 'Delinquent' in row_str:
                continue
            
            # Stop at Grand Totals
            if 'Grand Totals:' in row_str:
                break
            
            # Skip parameter rows
            if any(term in row_str for term in ['Parameters:', 'Statuses to include', 'Subproperties:', 'Subjournals:']):
                continue
            
            # Check if this is a unit header row (has unit number in col 1)
            unit = row.iloc[self.COL_UNIT] if len(row) > self.COL_UNIT else None
            if pd.notna(unit) and str(unit).strip():
                unit_str = str(unit).strip()
                # New unit - store info for when we hit subtotals
                current_unit = unit_str
                current_status = ''
                if len(row) > self.COL_STATUS and pd.notna(row.iloc[self.COL_STATUS]):
                    current_status = str(row.iloc[self.COL_STATUS]).strip().replace('\n', ' ')
                current_is_eviction = '*' in row_str
                current_deposits = self._safe_float(row.iloc[self.COL_DEPOSITS_HELD] if len(row) > self.COL_DEPOSITS_HELD else None)
                continue
            
            # Check if this is a Subtotals row for the current unit
            code_desc = row.iloc[self.COL_CODE_DESC] if len(row) > self.COL_CODE_DESC else None
            if pd.notna(code_desc) and 'Subtotals:' in str(code_desc):
                if current_unit and current_unit not in seen_units:
                    # Extract subtotals data
                    total_prepaid = self._safe_float(row.iloc[self.COL_TOTAL_PREPAID] if len(row) > self.COL_TOTAL_PREPAID else None)
                    total_delinquent = self._safe_float(row.iloc[self.COL_TOTAL_DELINQUENT] if len(row) > self.COL_TOTAL_DELINQUENT else None)
                    
                    # Only include if there's actual balance data
                    if total_delinquent != 0 or total_prepaid != 0:
                        resident = {
                            'unit': current_unit,
                            'status': current_status,
                            'total_prepaid': total_prepaid,
                            'total_delinquent': total_delinquent,
                            'net_balance': self._safe_float(row.iloc[self.COL_NET_BALANCE] if len(row) > self.COL_NET_BALANCE else None),
                            'current': self._safe_float(row.iloc[self.COL_CURRENT] if len(row) > self.COL_CURRENT else None),
                            'days_30': self._safe_float(row.iloc[self.COL_30_DAYS] if len(row) > self.COL_30_DAYS else None),
                            'days_60': self._safe_float(row.iloc[self.COL_60_DAYS] if len(row) > self.COL_60_DAYS else None),
                            'days_90_plus': self._safe_float(row.iloc[self.COL_90_PLUS_DAYS] if len(row) > self.COL_90_PLUS_DAYS else None),
                            'deposits_held': current_deposits,
                            'is_eviction': current_is_eviction,
                        }
                        residents.append(resident)
                        seen_units.add(current_unit)
        
        return residents
    
    def _calculate_eviction_summary(self, residents: List[Dict[str, Any]]) -> EvictionSummary:
        """Calculate eviction summary from resident details."""
        eviction_residents = [r for r in residents if r.get('is_eviction', False)]
        
        total_balance = sum(r.get('total_delinquent', 0) for r in eviction_residents)
        unit_count = len(eviction_residents)
        
        # Filed/Writ counts would need additional data from the report
        # For now, we count all evictions as filed
        filed_count = unit_count
        writ_count = 0  # Would need eviction stage data
        
        return EvictionSummary(
            total_balance=total_balance,
            unit_count=unit_count,
            filed_count=filed_count,
            writ_count=writ_count,
        )
    
    def _calculate_collections_summary(self, residents: List[Dict[str, Any]]) -> CollectionsSummary:
        """Calculate post-eviction collections from former residents."""
        # Former residents with balances are collections
        former = [r for r in residents if 'former' in r.get('status', '').lower()]
        
        total_0_30 = sum(r.get('current', 0) for r in former if r.get('current', 0) > 0)
        total_31_60 = sum(r.get('days_30', 0) for r in former if r.get('days_30', 0) > 0)
        total_61_90 = sum(r.get('days_60', 0) for r in former if r.get('days_60', 0) > 0)
        total_90_plus = sum(r.get('days_90_plus', 0) for r in former if r.get('days_90_plus', 0) > 0)
        
        return CollectionsSummary(
            days_0_30=total_0_30,
            days_31_60=total_31_60,
            days_61_90=total_61_90,
            days_90_plus=total_90_plus,
            total=total_0_30 + total_31_60 + total_61_90 + total_90_plus,
        )
    
    @staticmethod
    def _safe_float(value) -> float:
        """Safely convert value to float."""
        if pd.isna(value):
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0


def parse_delinquency_report(file_path: str) -> Dict[str, Any]:
    """
    Parse a RealPage Delinquent and Prepaid Report.
    
    Args:
        file_path: Path to the Excel report file
        
    Returns:
        Dictionary with parsed delinquency data
    """
    parser = DelinquencyReportParser(file_path)
    report = parser.parse()
    return report.to_dict()


if __name__ == '__main__':
    import json
    import sys
    
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
    else:
        file_path = '/Users/barak.b/Venn/OwnerDashV2/backend/app/db/Delinquent and Prepaid Report (3).xls'
    
    result = parse_delinquency_report(file_path)
    print(json.dumps(result, indent=2))
