import pandas as pd
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class RealPageReportParser:
    """
    Parses RealPage Excel reports into structured data.
    Handles dynamic header detection and data extraction.
    """
    
    def __init__(self):
        pass

    def _find_header_row(self, df: pd.DataFrame, keywords: List[str]) -> int:
        """
        Find the row index that contains the most matching keywords.
        """
        max_matches = 0
        header_idx = 0
        
        # Scan first 30 rows
        for i in range(min(30, len(df))):
            row_values = [str(x).lower() for x in df.iloc[i].values if pd.notna(x)]
            row_str = " ".join(row_values)
            
            matches = sum(1 for k in keywords if k.lower() in row_str)
            
            if matches > max_matches:
                max_matches = matches
                header_idx = i
                
        return header_idx

    def parse_leasing_activity(self, file_path: str) -> Dict[str, Any]:
        """
        Parses the Leasing Activity Detail report (Excel).
        
        Returns:
            Dict containing:
            - summary: Aggregate metrics (Leads, Tours, Leases, etc.)
            - traffic_sources: Breakdown by Ad Source
            - data: List of individual records
        """
        try:
            # Read file
            xlsx = pd.ExcelFile(file_path)
            sheet_name = xlsx.sheet_names[0] # Assume first sheet
            
            # Read raw to find header
            df_raw = pd.read_excel(xlsx, sheet_name=sheet_name, header=None)
            
            # Keywords expected in Leasing Activity report header
            keywords = ["Date", "Contact Type", "Prospect Name", "Ad Source", "Leases", "Results"]
            header_idx = self._find_header_row(df_raw, keywords)
            
            # Read with correct header
            df = pd.read_excel(xlsx, sheet_name=sheet_name, header=header_idx)
            
            # Clean column names (strip whitespace, newlines)
            df.columns = [str(c).replace('\n', ' ').strip() for c in df.columns]
            
            # Filter out empty rows or invalid dates
            df = df.dropna(subset=['Date'])
            
            # Initialize metrics
            records = []
            metrics = {
                "total_contacts": 0,
                "leads": 0,
                "tours": 0,
                "leases": 0,
                "leases_cancelled": 0,
                "leases_denied": 0
            }
            
            traffic_sources = {}
            
            for _, row in df.iterrows():
                record = {
                    "date": row.get("Date"),
                    "contact_type": row.get("This Contact Type"),
                    "prospect_name": row.get("Prospect Name"),
                    "ad_source": row.get("Ad Source"),
                    "initial_contact": row.get("Initial Contact Type"),
                    "leases": row.get("Leases"),
                    "cancelled_denied": row.get("Cancelled/ Denied"),
                    "result_reason": row.get("Results/ Lost Reason")
                }
                records.append(record)
                
                # Update Metrics
                metrics["total_contacts"] += 1
                
                ct = str(record["contact_type"]).lower()
                if "visit" in ct or "tour" in ct:
                    metrics["tours"] += 1
                
                # Lead logic: Unique prospects are leads? Or specific contact type?
                # For now, let's count unique prospect names as leads if not 'nan'
                
                # Leases
                if pd.notna(record["leases"]):
                    metrics["leases"] += 1
                    
                # Cancelled/Denied
                if pd.notna(record["cancelled_denied"]):
                     if "cancel" in str(record["cancelled_denied"]).lower():
                         metrics["leases_cancelled"] += 1
                     elif "denied" in str(record["cancelled_denied"]).lower():
                         metrics["leases_denied"] += 1
                
                # Traffic Sources
                source = str(record["ad_source"])
                if source != "nan":
                    traffic_sources[source] = traffic_sources.get(source, 0) + 1

            # Unique leads count
            unique_prospects = df["Prospect Name"].nunique()
            metrics["leads"] = unique_prospects

            return {
                "metrics": metrics,
                "traffic_sources": traffic_sources,
                "records": records
            }

        except Exception as e:
            logger.error(f"Error parsing Leasing Activity report: {e}")
            raise

    def parse_lease_trade_out(self, file_path: str) -> Dict[str, Any]:
        """
        Parses the Lease Trade-Out data from Nasa_Dashboard.xlsx (Custom Report).
        
        Returns:
            Dict containing:
            - summary: Aggregate metrics (Average Trade-Out, etc.)
            - records: List of unit trade-out records
        """
        try:
            # Read file
            xlsx = pd.ExcelFile(file_path)
            # Find the sheet - usually "NASA Dashboard"
            sheet_name = next((s for s in xlsx.sheet_names if "NASA" in s.upper()), xlsx.sheet_names[0])
            
            # Read raw to find header
            df_raw = pd.read_excel(xlsx, sheet_name=sheet_name, header=None)
            
            # Keywords for Lease Trade-Out
            keywords = ["Unit #", "Effective Rent", "Move-in Date", "Unit Type"]
            header_idx = self._find_header_row(df_raw, keywords)
            
            # Read with correct header
            df = pd.read_excel(xlsx, sheet_name=sheet_name, header=header_idx)
            
            # Clean column names
            df.columns = [str(c).strip() for c in df.columns]
            
            # Identify columns (pandas handles duplicates with .1, .2 suffix)
            # Based on analysis: 
            # Effective Rent (Left) = New Rent? Or Prior?
            # Effective Rent.1 (Right) = ?
            # Logic: If % Change is positive, and New > Old.
            # Sample: 1885 vs 1800 -> 1885 is New, 1800 is Prior.
            # Check column order in file: Effective Rent, Effective Rent.1
            # Usually Left is Current/New, Right is Prior? Or vice versa?
            # Let's rely on the column names if possible, but they are duplicates.
            # Assumption based on sample data: 
            # Unit 112: 1885 (Left), 1800 (Right), Change 4.7%. 
            # (1885 - 1800) / 1800 = 0.0472. Correct.
            # So Left (Effective Rent) is NEW, Right (Effective Rent.1) is PRIOR.
            
            col_new_rent = "Effective Rent"
            col_prior_rent = "Effective Rent.1"
            
            records = []
            metrics = {
                "total_units": 0,
                "avg_trade_out_pct": 0.0,
                "total_dollar_gain": 0.0
            }
            
            trade_out_pcts = []
            
            for _, row in df.iterrows():
                # Get raw unit number
                unit_num = str(row.get("Unit #", "")).strip()
                
                # Stop conditions / Skip logic
                if not unit_num or unit_num.lower() == "nan":
                    continue
                    
                # If we hit a "Total" row or a new section header (long text), stop or skip
                # Units are usually short (e.g., "101", "A-202"). 
                # "Insurance Escrow Balance" is definitely not a unit.
                if len(unit_num) > 10 or "total" in unit_num.lower():
                    # If it looks like a section header (contains spaces, long text), 
                    # and we already have records, it's safe to assume the table ended.
                    if len(records) > 0 and " " in unit_num:
                        break 
                    continue

                record = {
                    "unit_number": unit_num,
                    "unit_type": row.get("Unit Type"),
                    "sqft": row.get("SF"),
                    "new_effective_rent": row.get(col_new_rent),
                    "prior_effective_rent": row.get(col_prior_rent),
                    "percent_change": row.get("% Change"),
                    "dollar_change": row.get("$ Change"),
                    "move_in_date": row.get("Move-in Date")
                }
                
                # Validation and Type Conversion
                try:
                    # Parse Percentage
                    pct_val = record["percent_change"]
                    pct_change = float(pct_val)
                    
                    # Filter out insane percentage values (e.g. > 500% or < -100%) which indicate bad data mapping
                    if pd.isna(pct_change) or abs(pct_change) > 5.0: 
                        continue 
                        
                    # Parse Dollar Change
                    dollar_val = record["dollar_change"]
                    dollar_change = float(dollar_val) if pd.notna(dollar_val) else 0.0
                    
                    # Update record with clean floats
                    record["percent_change"] = pct_change
                    record["dollar_change"] = dollar_change
                    
                    records.append(record)
                    trade_out_pcts.append(pct_change)
                    metrics["total_dollar_gain"] += dollar_change
                except (ValueError, TypeError):
                    # Skip row if values aren't valid numbers
                    continue
            
            metrics["total_units"] = len(records)
            if trade_out_pcts:
                metrics["avg_trade_out_pct"] = sum(trade_out_pcts) / len(trade_out_pcts)
                
            return {
                "metrics": metrics,
                "records": records
            }
            
        except Exception as e:
            logger.error(f"Error parsing Lease Trade-Out report: {e}")
            raise

