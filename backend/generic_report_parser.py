"""
Generic RealPage Report Parser
Handles parsing of downloaded RealPage Excel reports and extracts metrics.
"""
import pandas as pd
import json
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RealPageReportParser:
    """Generic parser for RealPage reports."""
    
    def __init__(self):
        self.parsers = {
            "Box Score": self.parse_box_score,
            "Activity Log": self.parse_activity_log,
            "Leasing Activity": self.parse_leasing_activity,
            "Rent Roll": self.parse_rent_roll,
            "Guestcard Summary": self.parse_guestcard_summary,
            "Lease Expiration": self.parse_lease_expiration,
            "Contact Level": self.parse_contact_level
        }
    
    def parse_report(self, file_path: str, report_type: str) -> Dict[str, Any]:
        """
        Parse a RealPage report Excel file.
        
        Args:
            file_path: Path to the Excel file
            report_type: Type of report (Box Score, Activity Log, etc.)
            
        Returns:
            Dictionary with parsed data and metrics
        """
        if report_type not in self.parsers:
            raise ValueError(f"Unknown report type: {report_type}")
        
        try:
            # Read Excel file
            xl_file = pd.ExcelFile(file_path)
            logger.info(f"Sheet names: {xl_file.sheet_names}")
            
            # Use appropriate parser
            parser_func = self.parsers[report_type]
            result = parser_func(xl_file, file_path)
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing {report_type}: {e}")
            return {"error": str(e), "report_type": report_type}
    
    def parse_box_score(self, xl_file: pd.ExcelFile, file_path: str) -> Dict[str, Any]:
        """Parse Box Score report."""
        logger.info("Parsing Box Score report...")
        
        # Try to find the main data sheet
        sheet_name = None
        for name in xl_file.sheet_names:
            if 'score' in name.lower() or 'summary' in name.lower() or 'box' in name.lower():
                sheet_name = name
                break
        
        if not sheet_name:
            sheet_name = xl_file.sheet_names[0]  # Use first sheet
        
        df = pd.read_excel(xl_file, sheet_name=sheet_name)
        
        # Initialize metrics
        metrics = {
            "report_type": "Box Score",
            "file_path": file_path,
            "sheet_name": sheet_name,
            "total_rows": len(df),
            "columns": list(df.columns),
            "data": []
        }
        
        # Look for key metrics in the data
        numeric_columns = df.select_dtypes(include=['number']).columns
        
        # Try to find summary data (usually at top or specific rows)
        for idx, row in df.iterrows():
            row_data = {}
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    row_data[col] = value
            
            if row_data:
                metrics["data"].append(row_data)
        
        # Extract specific metrics if possible
        if 'Occupancy' in str(df.columns):
            occupancy_data = df[df.iloc[:, 0].astype(str).str.contains('Occupancy', case=False, na=False)]
            if not occupancy_data.empty:
                metrics["occupancy"] = occupancy_data.iloc[0].to_dict()
        
        logger.info(f"Parsed {len(metrics['data'])} rows from Box Score")
        return metrics
    
    def parse_activity_log(self, xl_file: pd.ExcelFile, file_path: str) -> Dict[str, Any]:
        """Parse Activity Log report."""
        logger.info("Parsing Activity Log report...")
        
        # Similar structure to box score but with activity-specific fields
        sheet_name = xl_file.sheet_names[0]
        df = pd.read_excel(xl_file, sheet_name=sheet_name)
        
        metrics = {
            "report_type": "Activity Log",
            "file_path": file_path,
            "sheet_name": sheet_name,
            "total_rows": len(df),
            "columns": list(df.columns),
            "activities": []
        }
        
        # Parse activity records
        for idx, row in df.iterrows():
            activity = {}
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    activity[col] = value
            
            if activity:
                metrics["activities"].append(activity)
        
        logger.info(f"Parsed {len(metrics['activities'])} activities")
        return metrics
    
    def parse_leasing_activity(self, xl_file: pd.ExcelFile, file_path: str) -> Dict[str, Any]:
        """Parse Leasing Activity report."""
        logger.info("Parsing Leasing Activity report...")
        
        sheet_name = xl_file.sheet_names[0]
        df = pd.read_excel(xl_file, sheet_name=sheet_name)
        
        metrics = {
            "report_type": "Leasing Activity",
            "file_path": file_path,
            "sheet_name": sheet_name,
            "total_rows": len(df),
            "columns": list(df.columns),
            "leases": []
        }
        
        # Parse lease data
        for idx, row in df.iterrows():
            lease = {}
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    lease[col] = value
            
            if lease:
                metrics["leases"].append(lease)
        
        logger.info(f"Parsed {len(metrics['leases'])} lease activities")
        return metrics
    
    def parse_rent_roll(self, xl_file: pd.ExcelFile, file_path: str) -> Dict[str, Any]:
        """Parse Rent Roll report."""
        logger.info("Parsing Rent Roll report...")
        
        sheet_name = xl_file.sheet_names[0]
        df = pd.read_excel(xl_file, sheet_name=sheet_name)
        
        metrics = {
            "report_type": "Rent Roll",
            "file_path": file_path,
            "sheet_name": sheet_name,
            "total_rows": len(df),
            "columns": list(df.columns),
            "units": []
        }
        
        # Parse unit data
        for idx, row in df.iterrows():
            unit = {}
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    unit[col] = value
            
            if unit:
                metrics["units"].append(unit)
        
        logger.info(f"Parsed {len(metrics['units'])} units")
        return metrics
    
    def parse_guestcard_summary(self, xl_file: pd.ExcelFile, file_path: str) -> Dict[str, Any]:
        """Parse Guestcard Summary report."""
        logger.info("Parsing Guestcard Summary report...")
        
        sheet_name = xl_file.sheet_names[0]
        df = pd.read_excel(xl_file, sheet_name=sheet_name)
        
        metrics = {
            "report_type": "Guestcard Summary",
            "file_path": file_path,
            "sheet_name": sheet_name,
            "total_rows": len(df),
            "columns": list(df.columns),
            "guestcards": []
        }
        
        # Parse guestcard data
        for idx, row in df.iterrows():
            guestcard = {}
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    guestcard[col] = value
            
            if guestcard:
                metrics["guestcards"].append(guestcard)
        
        logger.info(f"Parsed {len(metrics['guestcards'])} guestcards")
        return metrics
    
    def parse_lease_expiration(self, xl_file: pd.ExcelFile, file_path: str) -> Dict[str, Any]:
        """Parse Lease Expiration report."""
        logger.info("Parsing Lease Expiration report...")
        
        sheet_name = xl_file.sheet_names[0]
        df = pd.read_excel(xl_file, sheet_name=sheet_name)
        
        metrics = {
            "report_type": "Lease Expiration",
            "file_path": file_path,
            "sheet_name": sheet_name,
            "total_rows": len(df),
            "columns": list(df.columns),
            "expirations": []
        }
        
        # Parse expiration data
        for idx, row in df.iterrows():
            expiration = {}
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    expiration[col] = value
            
            if expiration:
                metrics["expirations"].append(expiration)
        
        logger.info(f"Parsed {len(metrics['expirations'])} lease expirations")
        return metrics
    
    def parse_contact_level(self, xl_file: pd.ExcelFile, file_path: str) -> Dict[str, Any]:
        """Parse Contact Level Details report."""
        logger.info("Parsing Contact Level Details report...")
        
        sheet_name = xl_file.sheet_names[0]
        df = pd.read_excel(xl_file, sheet_name=sheet_name)
        
        metrics = {
            "report_type": "Contact Level",
            "file_path": file_path,
            "sheet_name": sheet_name,
            "total_rows": len(df),
            "columns": list(df.columns),
            "contacts": []
        }
        
        # Parse contact data
        for idx, row in df.iterrows():
            contact = {}
            for col in df.columns:
                value = row[col]
                if pd.notna(value):
                    contact[col] = value
            
            if contact:
                metrics["contacts"].append(contact)
        
        logger.info(f"Parsed {len(metrics['contacts'])} contacts")
        return metrics

def main():
    """Test the parser with downloaded report."""
    parser = RealPageReportParser()
    
    # Find the most recent Box Score file
    box_score_files = list(Path(".").glob("box_score_*.xlsx"))
    if not box_score_files:
        print("No Box Score files found. Run download_box_score_working.py first.")
        return
    
    latest_file = max(box_score_files, key=lambda f: f.stat().st_mtime)
    print(f"Parsing file: {latest_file}")
    
    # Parse the report
    result = parser.parse_report(str(latest_file), "Box Score")
    
    # Save parsed data
    output_file = latest_file.with_suffix('.json')
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2, default=str)
    
    print(f"✅ Parsed data saved to {output_file}")
    print(f"   Report type: {result.get('report_type')}")
    print(f"   Total rows: {result.get('total_rows')}")
    print(f"   Columns: {result.get('columns')}")

if __name__ == "__main__":
    main()
