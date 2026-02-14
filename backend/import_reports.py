#!/usr/bin/env python3
"""
RealPage Report Import Pipeline

Scans downloaded reports, parses them, and imports data into the database.
"""

import sqlite3
import json
import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from report_parsers import parse_report, detect_report_type
from app.db.schema import REALPAGE_DB_PATH, REALPAGE_SCHEMA

# Property ID mapping from report_definitions.json
PROPERTY_MAP = {
    'aspire 7th and grant': '4779341',
    'edison at rino': '4248319',
    'ridian': '5446271',
    'nexus east': '5472172',
    'parkside at round rock': '5536211',
    'the hunter': '4248314',
    'the station at riverfront park': '4248314',
}


def get_property_id(property_name: str) -> str:
    """Get property ID from name."""
    if not property_name:
        return 'unknown'
    name_lower = property_name.lower().strip()
    for key, pid in PROPERTY_MAP.items():
        if key in name_lower or name_lower in key:
            return pid
    return 'unknown'


def init_report_tables(conn: sqlite3.Connection):
    """Initialize report tables if they don't exist."""
    cursor = conn.cursor()
    
    # Extract just the report tables from REALPAGE_SCHEMA
    report_tables = """
    CREATE TABLE IF NOT EXISTS realpage_box_score (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id TEXT NOT NULL,
        property_name TEXT,
        report_date TEXT NOT NULL,
        fiscal_period TEXT,
        floorplan_group TEXT,
        floorplan TEXT NOT NULL,
        total_units INTEGER,
        vacant_units INTEGER,
        vacant_not_leased INTEGER,
        vacant_leased INTEGER,
        occupied_units INTEGER,
        occupied_no_notice INTEGER,
        occupied_on_notice INTEGER,
        occupied_mtm INTEGER,
        model_units INTEGER,
        down_units INTEGER,
        avg_sqft INTEGER,
        avg_market_rent REAL,
        avg_actual_rent REAL,
        occupancy_pct REAL,
        leased_pct REAL,
        exposure_pct REAL,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        file_id TEXT,
        UNIQUE(property_id, report_date, floorplan)
    );
    
    CREATE TABLE IF NOT EXISTS realpage_delinquency (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id TEXT NOT NULL,
        property_name TEXT,
        report_date TEXT NOT NULL,
        unit_number TEXT,
        resident_name TEXT,
        status TEXT,
        current_balance REAL,
        balance_0_30 REAL,
        balance_31_60 REAL,
        balance_61_90 REAL,
        balance_over_90 REAL,
        prepaid REAL,
        total_delinquent REAL,
        net_balance REAL,
        last_payment_date TEXT,
        last_payment_amount REAL,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        file_id TEXT
    );
    
    CREATE TABLE IF NOT EXISTS realpage_monthly_summary (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id TEXT NOT NULL,
        property_name TEXT,
        report_date TEXT NOT NULL,
        period_start TEXT,
        period_end TEXT,
        floorplan TEXT,
        beginning_occupancy INTEGER,
        move_ins INTEGER,
        move_outs INTEGER,
        transfers_in INTEGER,
        transfers_out INTEGER,
        ending_occupancy INTEGER,
        renewals INTEGER,
        notices INTEGER,
        avg_rent REAL,
        imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        file_id TEXT,
        UNIQUE(property_id, report_date, floorplan)
    );
    
    CREATE TABLE IF NOT EXISTS realpage_report_import_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        property_id TEXT NOT NULL,
        property_name TEXT,
        report_type TEXT NOT NULL,
        report_date TEXT,
        file_name TEXT,
        file_id TEXT,
        records_imported INTEGER,
        import_started_at TIMESTAMP,
        import_completed_at TIMESTAMP,
        status TEXT,
        error_message TEXT
    );
    
    CREATE INDEX IF NOT EXISTS idx_box_score_property ON realpage_box_score(property_id);
    CREATE INDEX IF NOT EXISTS idx_box_score_date ON realpage_box_score(report_date);
    CREATE INDEX IF NOT EXISTS idx_delinquency_property ON realpage_delinquency(property_id);
    """
    
    cursor.executescript(report_tables)
    conn.commit()


def import_box_score(conn: sqlite3.Connection, records: List[Dict], file_name: str, file_id: str) -> int:
    """Import Box Score records."""
    cursor = conn.cursor()
    imported = 0
    
    for r in records:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO realpage_box_score
                (property_id, property_name, report_date, fiscal_period, floorplan_group,
                 floorplan, total_units, vacant_units, vacant_not_leased, vacant_leased,
                 occupied_units, occupied_no_notice, occupied_on_notice, model_units,
                 down_units, avg_sqft, avg_market_rent, avg_actual_rent, occupancy_pct,
                 leased_pct, exposure_pct, file_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get('property_id'),
                r.get('property_name'),
                r.get('report_date'),
                r.get('fiscal_period'),
                r.get('floorplan_group'),
                r.get('floorplan'),
                r.get('total_units', 0),
                r.get('vacant_units', 0),
                r.get('vacant_not_leased', 0),
                r.get('vacant_leased', 0),
                r.get('occupied_units', 0),
                r.get('occupied_no_notice', 0),
                r.get('occupied_on_notice', 0),
                r.get('model_units', 0),
                r.get('down_units', 0),
                r.get('avg_sqft', 0),
                r.get('avg_market_rent', 0),
                r.get('avg_actual_rent', 0),
                r.get('occupancy_pct', 0),
                r.get('leased_pct', 0),
                r.get('exposure_pct', 0),
                file_id
            ))
            imported += 1
        except Exception as e:
            print(f"  Error inserting record: {e}")
    
    conn.commit()
    return imported


def import_delinquency(conn: sqlite3.Connection, records: List[Dict], file_name: str, file_id: str) -> int:
    """Import Delinquency records."""
    cursor = conn.cursor()
    imported = 0
    
    for r in records:
        try:
            cursor.execute("""
                INSERT INTO realpage_delinquency
                (property_id, property_name, report_date, unit_number, resident_name,
                 current_balance, balance_0_30, balance_31_60, balance_61_90,
                 balance_over_90, prepaid, status, net_balance, total_delinquent, file_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get('property_id'),
                r.get('property_name'),
                r.get('report_date'),
                r.get('unit_number'),
                r.get('resident_name'),
                r.get('current_balance', 0),
                r.get('balance_0_30', 0),
                r.get('balance_31_60', 0),
                r.get('balance_61_90', 0),
                r.get('balance_over_90', 0),
                r.get('prepaid', 0),
                r.get('status', ''),
                r.get('net_balance', 0),
                r.get('total_delinquent', 0),
                file_id
            ))
            imported += 1
        except Exception as e:
            print(f"  Error inserting record: {e}")
    
    conn.commit()
    return imported


def import_monthly_summary(conn: sqlite3.Connection, records: List[Dict], file_name: str, file_id: str) -> int:
    """Import Monthly Summary records."""
    cursor = conn.cursor()
    imported = 0
    
    for r in records:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO realpage_monthly_summary
                (property_id, property_name, report_date, floorplan,
                 beginning_occupancy, move_ins, move_outs, ending_occupancy,
                 renewals, notices, file_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get('property_id'),
                r.get('property_name'),
                r.get('report_date'),
                r.get('floorplan'),
                r.get('beginning_occupancy', 0),
                r.get('move_ins', 0),
                r.get('move_outs', 0),
                r.get('ending_occupancy', 0),
                r.get('renewals', 0),
                r.get('notices', 0),
                file_id
            ))
            imported += 1
        except Exception as e:
            print(f"  Error inserting record: {e}")
    
    conn.commit()
    return imported


def import_rent_roll(conn: sqlite3.Connection, records: List[Dict], file_name: str, file_id: str) -> int:
    """Import Rent Roll records."""
    cursor = conn.cursor()
    
    # Ensure table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS realpage_rent_roll (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL,
            property_name TEXT,
            report_date TEXT NOT NULL,
            unit_number TEXT NOT NULL,
            floorplan TEXT,
            sqft INTEGER,
            resident_name TEXT,
            lease_start TEXT,
            lease_end TEXT,
            move_in_date TEXT,
            move_out_date TEXT,
            market_rent REAL,
            actual_rent REAL,
            other_charges REAL,
            total_charges REAL,
            balance REAL,
            status TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_id TEXT,
            UNIQUE(property_id, report_date, unit_number)
        )
    """)
    
    imported = 0
    for r in records:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO realpage_rent_roll
                (property_id, property_name, report_date, unit_number, floorplan,
                 sqft, status, resident_name, lease_start, lease_end,
                 move_in_date, market_rent, actual_rent, balance, file_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get('property_id'),
                r.get('property_name'),
                r.get('report_date'),
                r.get('unit_number'),
                r.get('floorplan'),
                r.get('sqft', 0),
                r.get('status'),
                r.get('resident_name'),
                r.get('lease_start'),
                r.get('lease_end'),
                r.get('move_in_date'),
                r.get('market_rent', 0),
                r.get('actual_rent', 0),
                r.get('balance', 0),
                file_id
            ))
            imported += 1
        except Exception as e:
            print(f"  Error inserting record: {e}")
    
    conn.commit()
    return imported


def import_lease_expiration(conn: sqlite3.Connection, records: List[Dict], file_name: str, file_id: str) -> int:
    """Import Lease Expiration records."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS realpage_lease_expirations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL,
            property_name TEXT,
            report_date TEXT NOT NULL,
            unit_number TEXT,
            floorplan TEXT,
            resident_name TEXT,
            lease_end TEXT,
            current_rent REAL,
            market_rent REAL,
            lease_term INTEGER,
            months_until_expiration INTEGER,
            renewal_status TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_id TEXT
        )
    """)
    imported = 0
    for r in records:
        try:
            cursor.execute("""
                INSERT INTO realpage_lease_expirations
                (property_id, property_name, report_date, unit_number, floorplan,
                 resident_name, lease_end, current_rent, market_rent, lease_term,
                 months_until_expiration, renewal_status, file_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get('property_id'),
                r.get('property_name'),
                r.get('report_date'),
                r.get('unit_number'),
                r.get('floorplan'),
                r.get('resident_name'),
                r.get('lease_end'),
                r.get('current_rent', 0),
                r.get('market_rent', 0),
                r.get('lease_term'),
                r.get('months_until_expiration'),
                r.get('renewal_status'),
                file_id
            ))
            imported += 1
        except Exception as e:
            print(f"  Error inserting lease expiration: {e}")
    conn.commit()
    return imported


def import_lease_expiration_renewal(conn: sqlite3.Connection, records: List[Dict], file_name: str, file_id: str) -> int:
    """Import Lease Expiration Renewal Detail records (Report 4156)."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS realpage_lease_expiration_renewal (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL,
            report_date TEXT NOT NULL,
            unit_number TEXT,
            floorplan TEXT,
            actual_rent REAL,
            other_billings REAL,
            last_increase_date TEXT,
            last_increase_amount REAL,
            market_rent REAL,
            move_in_date TEXT,
            lease_end_date TEXT,
            decision TEXT,
            new_lease_start TEXT,
            new_lease_term INTEGER,
            new_rent REAL,
            new_other_billings REAL,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_id TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS realpage_lease_exp_renewal_summary (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL,
            report_date TEXT NOT NULL,
            floorplan TEXT,
            total_possible INTEGER,
            renewed INTEGER,
            vacating INTEGER,
            unknown INTEGER,
            month_to_month INTEGER,
            avg_term_renewed REAL,
            avg_new_rent REAL,
            avg_market_rent REAL,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_id TEXT
        )
    """)
    imported = 0
    for r in records:
        try:
            if r.get('_type') == 'detail':
                cursor.execute("""
                    INSERT INTO realpage_lease_expiration_renewal
                    (property_id, report_date, unit_number, floorplan, actual_rent,
                     other_billings, last_increase_date, last_increase_amount, market_rent,
                     move_in_date, lease_end_date, decision, new_lease_start,
                     new_lease_term, new_rent, new_other_billings, file_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.get('property_id'),
                    r.get('report_date'),
                    r.get('unit_number'),
                    r.get('floorplan'),
                    r.get('actual_rent', 0),
                    r.get('other_billings', 0),
                    r.get('last_increase_date'),
                    r.get('last_increase_amount', 0),
                    r.get('market_rent', 0),
                    r.get('move_in_date'),
                    r.get('lease_end_date'),
                    r.get('decision'),
                    r.get('new_lease_start'),
                    r.get('new_lease_term', 0),
                    r.get('new_rent', 0),
                    r.get('new_other_billings', 0),
                    file_id
                ))
            elif r.get('_type') == 'summary':
                cursor.execute("""
                    INSERT INTO realpage_lease_exp_renewal_summary
                    (property_id, report_date, floorplan, total_possible, renewed,
                     vacating, unknown, month_to_month, avg_term_renewed,
                     avg_new_rent, avg_market_rent, file_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.get('property_id'),
                    r.get('report_date'),
                    r.get('floorplan'),
                    r.get('total_possible', 0),
                    r.get('renewed', 0),
                    r.get('vacating', 0),
                    r.get('unknown', 0),
                    r.get('month_to_month', 0),
                    r.get('avg_term_renewed', 0),
                    r.get('avg_new_rent', 0),
                    r.get('avg_market_rent', 0),
                    file_id
                ))
            imported += 1
        except Exception as e:
            print(f"  Error inserting lease expiration renewal: {e}")
    conn.commit()
    return imported


def import_activity(conn: sqlite3.Connection, records: List[Dict], file_name: str, file_id: str) -> int:
    """Import Activity Report records."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS realpage_activity (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL,
            property_name TEXT,
            report_date TEXT NOT NULL,
            activity_date TEXT,
            unit_number TEXT,
            floorplan TEXT,
            activity_type TEXT,
            resident_name TEXT,
            prior_rent REAL,
            new_rent REAL,
            rent_change REAL,
            lease_term INTEGER,
            move_in_date TEXT,
            move_out_date TEXT,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_id TEXT
        )
    """)
    imported = 0
    for r in records:
        try:
            cursor.execute("""
                INSERT INTO realpage_activity
                (property_id, property_name, report_date, activity_date, unit_number,
                 floorplan, activity_type, resident_name, prior_rent, new_rent,
                 rent_change, lease_term, move_in_date, move_out_date, file_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get('property_id'),
                r.get('property_name'),
                r.get('report_date'),
                r.get('activity_date'),
                r.get('unit_number'),
                r.get('floorplan'),
                r.get('activity_type'),
                r.get('resident_name'),
                r.get('prior_rent', 0),
                r.get('new_rent', 0),
                r.get('rent_change', 0),
                r.get('lease_term'),
                r.get('move_in_date'),
                r.get('move_out_date'),
                file_id
            ))
            imported += 1
        except Exception as e:
            print(f"  Error inserting activity: {e}")
    conn.commit()
    return imported


def import_projected_occupancy(conn: sqlite3.Connection, records: List[Dict], file_name: str, file_id: str) -> int:
    """Import Projected Occupancy records."""
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS realpage_projected_occupancy (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL,
            property_name TEXT,
            report_date TEXT NOT NULL,
            week_ending TEXT NOT NULL,
            total_units INTEGER,
            occupied_begin INTEGER,
            pct_occupied_begin REAL,
            scheduled_move_ins INTEGER,
            scheduled_move_outs INTEGER,
            occupied_end INTEGER,
            pct_occupied_end REAL,
            imported_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            file_id TEXT,
            UNIQUE(property_id, report_date, week_ending)
        )
    """)
    imported = 0
    for r in records:
        try:
            cursor.execute("""
                INSERT OR REPLACE INTO realpage_projected_occupancy
                (property_id, property_name, report_date, week_ending, total_units,
                 occupied_begin, pct_occupied_begin, scheduled_move_ins, scheduled_move_outs,
                 occupied_end, pct_occupied_end, file_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                r.get('property_id'),
                r.get('property_name'),
                r.get('report_date'),
                r.get('week_ending'),
                r.get('total_units', 0),
                r.get('occupied_begin', 0),
                r.get('pct_occupied_begin', 0),
                r.get('scheduled_move_ins', 0),
                r.get('scheduled_move_outs', 0),
                r.get('occupied_end', 0),
                r.get('pct_occupied_end', 0),
                file_id
            ))
            imported += 1
        except Exception as e:
            print(f"  Error inserting projected occupancy: {e}")
    conn.commit()
    return imported


def log_import(conn: sqlite3.Connection, property_id: str, property_name: str,
               report_type: str, report_date: str, file_name: str, file_id: str,
               records_imported: int, status: str, error: str = None):
    """Log import to tracking table."""
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO realpage_report_import_log
        (property_id, property_name, report_type, report_date, file_name, file_id,
         records_imported, import_started_at, import_completed_at, status, error_message)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        property_id, property_name, report_type, report_date, file_name, file_id,
        records_imported, datetime.now().isoformat(), datetime.now().isoformat(),
        status, error
    ))
    conn.commit()


def import_reports(reports_dir: str = 'reports', db_path: str = None):
    """
    Import all reports from directory into database.
    """
    reports_path = Path(reports_dir)
    db_path = db_path or str(REALPAGE_DB_PATH)
    
    # Ensure DB directory exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    init_report_tables(conn)
    
    print(f"Scanning {reports_path} for reports...")
    
    # Find all Excel files
    xlsx_files = list(reports_path.glob('*.xlsx'))
    print(f"Found {len(xlsx_files)} Excel files")
    
    stats = {
        'box_score': 0,
        'delinquency': 0,
        'monthly_summary': 0,
        'unknown': 0,
        'errors': 0
    }
    
    for file_path in xlsx_files:
        file_name = file_path.name
        
        # Extract file_id from filename if present
        file_id_match = re.search(r'_(\d{7,})\.xlsx$', file_name)
        file_id = file_id_match.group(1) if file_id_match else None
        
        print(f"\nProcessing: {file_name}")
        
        try:
            result = parse_report(str(file_path))
            report_type = result.get('report_type')
            records = result.get('records', [])
            
            if not report_type:
                print(f"  ⚠ Unknown report type, skipping")
                stats['unknown'] += 1
                continue
            
            if not records:
                print(f"  ⚠ No records parsed")
                continue
            
            # Get property info from first record
            property_name = records[0].get('property_name') if records else None
            property_id = get_property_id(property_name)
            report_date = records[0].get('report_date') if records else None
            
            # Update property_id in all records
            for r in records:
                if r.get('property_id') in (None, 'test', 'unknown'):
                    r['property_id'] = property_id
            
            print(f"  Type: {report_type}, Property: {property_name} ({property_id})")
            print(f"  Date: {report_date}, Records: {len(records)}")
            
            # Import based on type
            if report_type == 'box_score':
                imported = import_box_score(conn, records, file_name, file_id)
                stats['box_score'] += imported
            elif report_type == 'delinquency':
                imported = import_delinquency(conn, records, file_name, file_id)
                stats['delinquency'] += imported
            elif report_type == 'monthly_summary':
                imported = import_monthly_summary(conn, records, file_name, file_id)
                stats['monthly_summary'] += imported
            elif report_type == 'rent_roll':
                imported = import_rent_roll(conn, records, file_name, file_id)
                stats['rent_roll'] = stats.get('rent_roll', 0) + imported
            else:
                imported = 0
                stats['unknown'] += 1
            
            print(f"  ✓ Imported {imported} records")
            
            log_import(conn, property_id, property_name, report_type, report_date,
                      file_name, file_id, imported, 'success')
            
        except Exception as e:
            print(f"  ✗ Error: {e}")
            stats['errors'] += 1
            log_import(conn, 'unknown', None, 'unknown', None,
                      file_name, file_id, 0, 'error', str(e))
    
    conn.close()
    
    print("\n" + "=" * 50)
    print("IMPORT SUMMARY")
    print("=" * 50)
    print(f"  Box Score records:      {stats['box_score']}")
    print(f"  Delinquency records:    {stats['delinquency']}")
    print(f"  Monthly Summary records: {stats['monthly_summary']}")
    print(f"  Unknown/skipped:        {stats['unknown']}")
    print(f"  Errors:                 {stats['errors']}")
    print(f"\nDatabase: {db_path}")
    
    return stats


def show_summary(db_path: str = None):
    """Show summary of imported data."""
    db_path = db_path or str(REALPAGE_DB_PATH)
    
    if not Path(db_path).exists():
        print("Database not found. Run import first.")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n" + "=" * 50)
    print("DATABASE SUMMARY")
    print("=" * 50)
    
    # Box Score
    cursor.execute("SELECT COUNT(*) FROM realpage_box_score")
    count = cursor.fetchone()[0]
    print(f"\nBox Score: {count} records")
    
    cursor.execute("""
        SELECT property_name, report_date, COUNT(*), 
               SUM(total_units), ROUND(AVG(occupancy_pct), 1)
        FROM realpage_box_score 
        GROUP BY property_id, report_date
        ORDER BY report_date DESC
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]} ({row[1]}): {row[2]} floorplans, {row[3]} units, {row[4]}% occ")
    
    # Delinquency
    cursor.execute("SELECT COUNT(*) FROM realpage_delinquency")
    count = cursor.fetchone()[0]
    print(f"\nDelinquency: {count} records")
    
    cursor.execute("""
        SELECT property_name, report_date, COUNT(*), SUM(current_balance)
        FROM realpage_delinquency 
        GROUP BY property_id, report_date
    """)
    for row in cursor.fetchall():
        print(f"  {row[0]} ({row[1]}): {row[2]} residents, ${row[3]:,.0f} total balance")
    
    conn.close()


if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == '--summary':
        show_summary()
    else:
        import_reports()
        show_summary()
