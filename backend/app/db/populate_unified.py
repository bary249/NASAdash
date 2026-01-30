"""
Populate Unified Data Layer.

Reads from Yardi and RealPage raw databases and creates normalized
unified data in unified.db. Also calculates occupancy and pricing metrics.
"""

import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db.schema import (
    YARDI_DB_PATH, REALPAGE_DB_PATH, UNIFIED_DB_PATH,
    UNIFIED_SCHEMA, init_database
)


def populate_unified_from_realpage():
    """
    Transform RealPage raw data into unified format.
    """
    print("\n📥 Processing RealPage data...")
    
    if not REALPAGE_DB_PATH.exists():
        print("   ⚠️  RealPage database not found, skipping...")
        return 0
    
    rp_conn = sqlite3.connect(REALPAGE_DB_PATH)
    rp_conn.row_factory = sqlite3.Row
    
    uni_conn = sqlite3.connect(UNIFIED_DB_PATH)
    uni_cursor = uni_conn.cursor()
    
    records_synced = 0
    
    try:
        # 1. Sync Properties
        print("   → Syncing properties...")
        rp_props = rp_conn.execute("SELECT * FROM realpage_properties").fetchall()
        for prop in rp_props:
            unified_id = f"rp-{prop['site_id']}"
            uni_cursor.execute("""
                INSERT OR REPLACE INTO unified_properties
                (unified_property_id, pms_source, pms_property_id, pms_pmc_id,
                 name, address, city, state, zip, phone, email, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                unified_id,
                'realpage',
                prop['site_id'],
                prop['pmc_id'],
                prop['site_name'],
                prop['address'],
                prop['city'],
                prop['state'],
                prop['zip'],
                prop['phone'],
                prop['email'],
                datetime.now().isoformat()
            ))
            records_synced += 1
        print(f"      ✅ {len(rp_props)} properties")
        
        # 2. Sync Units
        print("   → Syncing units...")
        rp_units = rp_conn.execute("SELECT * FROM realpage_units").fetchall()
        for unit in rp_units:
            unified_prop_id = f"rp-{unit['site_id']}"
            
            # Map vacant flag to status
            status = 'vacant' if unit['vacant'] == 'T' else 'occupied'
            
            # Calculate days vacant
            days_vacant = None
            if status == 'vacant' and unit['available_date']:
                try:
                    avail_date = datetime.strptime(unit['available_date'][:10], "%Y-%m-%d")
                    days_vacant = (datetime.now() - avail_date).days
                except:
                    pass
            
            uni_cursor.execute("""
                INSERT OR REPLACE INTO unified_units
                (unified_property_id, pms_source, pms_unit_id, unit_number,
                 building, floor, floorplan, floorplan_name, bedrooms, bathrooms,
                 square_feet, market_rent, status, available_date, days_vacant,
                 on_notice_date, made_ready_date, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                unified_prop_id,
                'realpage',
                unit['unit_id'],
                unit['unit_number'],
                unit['building_name'],
                unit['floor'],
                unit['floorplan_id'],
                unit['floorplan_name'],
                unit['bedrooms'],
                unit['bathrooms'],
                unit['rentable_sqft'],
                unit['market_rent'],
                status,
                unit['available_date'],
                days_vacant,
                unit['on_notice_for_date'],
                unit['made_ready_date'],
                datetime.now().isoformat()
            ))
            records_synced += 1
        print(f"      ✅ {len(rp_units)} units")
        
        # 3. Sync Residents
        print("   → Syncing residents...")
        rp_residents = rp_conn.execute("SELECT * FROM realpage_residents").fetchall()
        for res in rp_residents:
            unified_prop_id = f"rp-{res['site_id']}"
            
            # Map lease status to unified status
            lease_status = (res['lease_status'] or '').lower()
            if 'current' in lease_status:
                status = 'current'
            elif 'future' in lease_status:
                status = 'future'
            elif 'former' in lease_status or 'past' in lease_status:
                status = 'past'
            elif 'notice' in lease_status:
                status = 'notice'
            elif 'applicant' in lease_status:
                status = 'applicant'
            else:
                status = 'current'
            
            uni_cursor.execute("""
                INSERT INTO unified_residents
                (unified_property_id, pms_source, pms_resident_id, pms_unit_id,
                 unit_number, first_name, last_name, full_name, email, phone,
                 status, lease_start, lease_end, move_in_date, move_out_date,
                 notice_date, current_rent, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                unified_prop_id,
                'realpage',
                res['resident_id'] or res['resident_member_id'],
                res['unit_id'],
                res['unit_number'],
                res['first_name'],
                res['last_name'],
                f"{res['first_name'] or ''} {res['last_name'] or ''}".strip(),
                res['email'],
                res['cell_phone'] or res['home_phone'],
                status,
                res['begin_date'],
                res['end_date'],
                res['move_in_date'],
                res['move_out_date'],
                res['notice_given_date'],
                res['rent'],
                datetime.now().isoformat()
            ))
            records_synced += 1
        print(f"      ✅ {len(rp_residents)} residents")
        
        # 4. Sync Leases
        print("   → Syncing leases...")
        rp_leases = rp_conn.execute("SELECT * FROM realpage_leases").fetchall()
        for lease in rp_leases:
            unified_prop_id = f"rp-{lease['site_id']}"
            
            uni_cursor.execute("""
                INSERT INTO unified_leases
                (unified_property_id, pms_source, pms_lease_id, pms_resident_id,
                 pms_unit_id, unit_number, rent_amount, lease_start, lease_end,
                 lease_term_months, is_renewal, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                unified_prop_id,
                'realpage',
                lease['lease_id'],
                lease['resident_id'],
                lease['unit_id'],
                lease['unit_number'],
                lease['rent_amount'],
                lease['lease_start_date'],
                lease['lease_end_date'],
                lease['lease_term'],
                1 if lease['next_lease_id'] else 0,
                datetime.now().isoformat()
            ))
            records_synced += 1
        print(f"      ✅ {len(rp_leases)} leases")
        
        uni_conn.commit()
        
    finally:
        rp_conn.close()
        uni_conn.close()
    
    return records_synced


def populate_unified_from_yardi():
    """
    Transform Yardi raw data into unified format.
    """
    print("\n📥 Processing Yardi data...")
    
    if not YARDI_DB_PATH.exists():
        print("   ⚠️  Yardi database not found, skipping...")
        return 0
    
    yardi_conn = sqlite3.connect(YARDI_DB_PATH)
    yardi_conn.row_factory = sqlite3.Row
    
    uni_conn = sqlite3.connect(UNIFIED_DB_PATH)
    uni_cursor = uni_conn.cursor()
    
    records_synced = 0
    
    try:
        # 1. Sync Properties
        print("   → Syncing properties...")
        yardi_props = yardi_conn.execute("SELECT * FROM yardi_properties").fetchall()
        for prop in yardi_props:
            unified_id = f"yardi-{prop['property_id']}"
            uni_cursor.execute("""
                INSERT OR REPLACE INTO unified_properties
                (unified_property_id, pms_source, pms_property_id,
                 name, address, city, state, zip, phone, email, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                unified_id,
                'yardi',
                prop['property_id'],
                prop['marketing_name'] or prop['property_code'],
                prop['address'],
                prop['city'],
                prop['state'],
                prop['zip'],
                prop['phone'],
                prop['email'],
                datetime.now().isoformat()
            ))
            records_synced += 1
        print(f"      ✅ {len(yardi_props)} properties")
        
        # 2. Sync Units
        print("   → Syncing units...")
        yardi_units = yardi_conn.execute("SELECT * FROM yardi_units").fetchall()
        for unit in yardi_units:
            unified_prop_id = f"yardi-{unit['property_id']}"
            
            # Map unit status
            status_lower = (unit['unit_status'] or '').lower()
            if 'occupied' in status_lower:
                status = 'occupied'
            elif 'vacant' in status_lower:
                status = 'vacant'
            elif 'notice' in status_lower:
                status = 'notice'
            elif 'model' in status_lower:
                status = 'model'
            elif 'down' in status_lower or 'admin' in status_lower:
                status = 'down'
            else:
                status = 'occupied'  # Default
            
            uni_cursor.execute("""
                INSERT OR REPLACE INTO unified_units
                (unified_property_id, pms_source, pms_unit_id, unit_number,
                 building, floorplan, floorplan_name, bedrooms, bathrooms,
                 square_feet, market_rent, status, available_date,
                 made_ready_date, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                unified_prop_id,
                'yardi',
                unit['unit_code'],
                unit['unit_code'],
                unit['building'],
                unit['unit_type'],
                unit['unit_type'],
                unit['bedrooms'],
                unit['bathrooms'],
                unit['sqft'],
                unit['market_rent'],
                status,
                unit['available_date'],
                unit['make_ready_date'],
                datetime.now().isoformat()
            ))
            records_synced += 1
        print(f"      ✅ {len(yardi_units)} units")
        
        # 3. Sync Residents
        print("   → Syncing residents...")
        yardi_residents = yardi_conn.execute("SELECT * FROM yardi_residents").fetchall()
        for res in yardi_residents:
            unified_prop_id = f"yardi-{res['property_id']}"
            
            # Map status
            status_lower = (res['status'] or '').lower()
            if 'current' in status_lower:
                status = 'current'
            elif 'future' in status_lower:
                status = 'future'
            elif 'past' in status_lower or 'former' in status_lower:
                status = 'past'
            elif 'notice' in status_lower:
                status = 'notice'
            elif 'applicant' in status_lower:
                status = 'applicant'
            else:
                status = 'current'
            
            uni_cursor.execute("""
                INSERT INTO unified_residents
                (unified_property_id, pms_source, pms_resident_id, pms_unit_id,
                 unit_number, first_name, last_name, full_name, email, phone,
                 status, lease_start, lease_end, move_in_date, move_out_date,
                 notice_date, current_rent, balance, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                unified_prop_id,
                'yardi',
                res['resident_code'],
                res['unit_code'],
                res['unit_code'],
                res['first_name'],
                res['last_name'],
                f"{res['first_name'] or ''} {res['last_name'] or ''}".strip(),
                res['email'],
                res['cell_phone'] or res['phone'],
                status,
                res['lease_from_date'],
                res['lease_to_date'],
                res['move_in_date'],
                res['move_out_date'],
                res['notice_date'],
                res['rent'],
                res['balance'],
                datetime.now().isoformat()
            ))
            records_synced += 1
        print(f"      ✅ {len(yardi_residents)} residents")
        
        # 4. Sync Lease Charges
        print("   → Syncing leases...")
        yardi_leases = yardi_conn.execute("SELECT * FROM yardi_lease_charges").fetchall()
        for lease in yardi_leases:
            unified_prop_id = f"yardi-{lease['property_id']}"
            
            uni_cursor.execute("""
                INSERT INTO unified_leases
                (unified_property_id, pms_source, pms_resident_id, pms_unit_id,
                 unit_number, rent_amount, lease_start, lease_end, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                unified_prop_id,
                'yardi',
                lease['resident_code'],
                lease['unit_code'],
                lease['unit_code'],
                lease['total_charges'],
                lease['lease_from_date'],
                lease['lease_to_date'],
                datetime.now().isoformat()
            ))
            records_synced += 1
        print(f"      ✅ {len(yardi_leases)} leases")
        
        uni_conn.commit()
        
    finally:
        yardi_conn.close()
        uni_conn.close()
    
    return records_synced


def calculate_occupancy_metrics():
    """
    Calculate occupancy metrics from unified unit data.
    """
    print("\n📊 Calculating occupancy metrics...")
    
    conn = sqlite3.connect(UNIFIED_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    today = date.today().isoformat()
    
    try:
        # Get all properties
        properties = cursor.execute(
            "SELECT unified_property_id, name FROM unified_properties"
        ).fetchall()
        
        for prop in properties:
            prop_id = prop['unified_property_id']
            
            # Get unit counts by status
            units = cursor.execute("""
                SELECT status, COUNT(*) as count
                FROM unified_units
                WHERE unified_property_id = ?
                GROUP BY status
            """, (prop_id,)).fetchall()
            
            status_counts = {row['status']: row['count'] for row in units}
            
            total_units = sum(status_counts.values())
            occupied = status_counts.get('occupied', 0)
            vacant = status_counts.get('vacant', 0)
            notice = status_counts.get('notice', 0)
            model = status_counts.get('model', 0)
            down = status_counts.get('down', 0)
            
            leased = occupied + notice
            
            physical_occ = (occupied / total_units * 100) if total_units > 0 else 0
            leased_pct = (leased / total_units * 100) if total_units > 0 else 0
            
            # Calculate exposure (units with on_notice_date within 30/60 days)
            exposure_30 = cursor.execute("""
                SELECT COUNT(*) FROM unified_units
                WHERE unified_property_id = ?
                AND on_notice_date IS NOT NULL
                AND date(on_notice_date) <= date('now', '+30 days')
            """, (prop_id,)).fetchone()[0]
            
            exposure_60 = cursor.execute("""
                SELECT COUNT(*) FROM unified_units
                WHERE unified_property_id = ?
                AND on_notice_date IS NOT NULL
                AND date(on_notice_date) <= date('now', '+60 days')
            """, (prop_id,)).fetchone()[0]
            
            # Insert metrics
            cursor.execute("""
                INSERT OR REPLACE INTO unified_occupancy_metrics
                (unified_property_id, snapshot_date, total_units, occupied_units,
                 vacant_units, leased_units, notice_units, model_units, down_units,
                 physical_occupancy, leased_percentage, exposure_30_days,
                 exposure_60_days, calculated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prop_id, today, total_units, occupied, vacant, leased,
                notice, model, down, round(physical_occ, 2), round(leased_pct, 2),
                exposure_30, exposure_60, datetime.now().isoformat()
            ))
            
            print(f"   ✅ {prop['name']}: {occupied}/{total_units} occupied ({physical_occ:.1f}%)")
        
        conn.commit()
        
    finally:
        conn.close()


def calculate_pricing_metrics():
    """
    Calculate pricing metrics by floorplan from unified data.
    """
    print("\n💰 Calculating pricing metrics...")
    
    conn = sqlite3.connect(UNIFIED_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    today = date.today().isoformat()
    
    try:
        # Get properties
        properties = cursor.execute(
            "SELECT unified_property_id, name FROM unified_properties"
        ).fetchall()
        
        for prop in properties:
            prop_id = prop['unified_property_id']
            
            # Get floorplan metrics from units
            floorplans = cursor.execute("""
                SELECT 
                    floorplan,
                    floorplan_name,
                    bedrooms,
                    bathrooms,
                    COUNT(*) as unit_count,
                    AVG(square_feet) as avg_sqft,
                    AVG(market_rent) as avg_asking_rent
                FROM unified_units
                WHERE unified_property_id = ?
                AND floorplan IS NOT NULL
                GROUP BY floorplan, floorplan_name, bedrooms, bathrooms
            """, (prop_id,)).fetchall()
            
            for fp in floorplans:
                # Get in-place rent from current residents
                in_place_result = cursor.execute("""
                    SELECT AVG(current_rent) as avg_rent
                    FROM unified_residents
                    WHERE unified_property_id = ?
                    AND status = 'current'
                    AND pms_unit_id IN (
                        SELECT pms_unit_id FROM unified_units
                        WHERE unified_property_id = ?
                        AND floorplan = ?
                    )
                """, (prop_id, prop_id, fp['floorplan'])).fetchone()
                
                in_place_rent = in_place_result['avg_rent'] or fp['avg_asking_rent'] or 0
                asking_rent = fp['avg_asking_rent'] or 0
                avg_sqft = fp['avg_sqft'] or 1
                
                in_place_per_sf = in_place_rent / avg_sqft if avg_sqft > 0 else 0
                asking_per_sf = asking_rent / avg_sqft if avg_sqft > 0 else 0
                rent_growth = ((asking_rent / in_place_rent) - 1) * 100 if in_place_rent > 0 else 0
                
                cursor.execute("""
                    INSERT OR REPLACE INTO unified_pricing_metrics
                    (unified_property_id, snapshot_date, floorplan, floorplan_name,
                     unit_count, bedrooms, bathrooms, avg_square_feet,
                     in_place_rent, in_place_per_sf, asking_rent, asking_per_sf,
                     rent_growth, calculated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prop_id, today,
                    fp['floorplan'], fp['floorplan_name'],
                    fp['unit_count'], fp['bedrooms'], fp['bathrooms'],
                    int(avg_sqft),
                    round(in_place_rent, 2), round(in_place_per_sf, 2),
                    round(asking_rent, 2), round(asking_per_sf, 2),
                    round(rent_growth, 2),
                    datetime.now().isoformat()
                ))
            
            print(f"   ✅ {prop['name']}: {len(floorplans)} floorplans")
        
        conn.commit()
        
    finally:
        conn.close()


def calculate_leasing_metrics():
    """
    Calculate leasing metrics (move-ins, move-outs, renewals) from unified data.
    """
    print("\n📈 Calculating leasing metrics...")
    
    conn = sqlite3.connect(UNIFIED_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    today = date.today()
    today_str = today.isoformat()
    
    # Calculate date ranges
    cm_start = today.replace(day=1).isoformat()
    cm_end = today_str
    
    # Prior month
    pm_end = (today.replace(day=1) - timedelta(days=1)).isoformat()
    pm_start = (today.replace(day=1) - timedelta(days=1)).replace(day=1).isoformat()
    
    # YTD
    ytd_start = today.replace(month=1, day=1).isoformat()
    ytd_end = today_str
    
    periods = [
        ('current_month', cm_start, cm_end),
        ('prior_month', pm_start, pm_end),
        ('ytd', ytd_start, ytd_end),
    ]
    
    try:
        properties = cursor.execute(
            "SELECT unified_property_id, name FROM unified_properties"
        ).fetchall()
        
        for prop in properties:
            prop_id = prop['unified_property_id']
            
            for period_name, start_date, end_date in periods:
                # Move-ins
                move_ins = cursor.execute("""
                    SELECT COUNT(*) FROM unified_residents
                    WHERE unified_property_id = ?
                    AND move_in_date BETWEEN ? AND ?
                """, (prop_id, start_date, end_date)).fetchone()[0]
                
                # Move-outs
                move_outs = cursor.execute("""
                    SELECT COUNT(*) FROM unified_residents
                    WHERE unified_property_id = ?
                    AND move_out_date BETWEEN ? AND ?
                """, (prop_id, start_date, end_date)).fetchone()[0]
                
                # Lease expirations
                expirations = cursor.execute("""
                    SELECT COUNT(*) FROM unified_leases
                    WHERE unified_property_id = ?
                    AND lease_end BETWEEN ? AND ?
                """, (prop_id, start_date, end_date)).fetchone()[0]
                
                # Renewals
                renewals = cursor.execute("""
                    SELECT COUNT(*) FROM unified_leases
                    WHERE unified_property_id = ?
                    AND lease_start BETWEEN ? AND ?
                    AND is_renewal = 1
                """, (prop_id, start_date, end_date)).fetchone()[0]
                
                renewal_pct = (renewals / expirations * 100) if expirations > 0 else 0
                
                cursor.execute("""
                    INSERT OR REPLACE INTO unified_leasing_metrics
                    (unified_property_id, snapshot_date, period,
                     move_ins, move_outs, net_move_ins, lease_expirations,
                     renewals, renewal_percentage, calculated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    prop_id, today_str, period_name,
                    move_ins, move_outs, move_ins - move_outs,
                    expirations, renewals, round(renewal_pct, 2),
                    datetime.now().isoformat()
                ))
            
            print(f"   ✅ {prop['name']}: metrics calculated")
        
        conn.commit()
        
    finally:
        conn.close()


def populate_unified_database():
    """
    Main function to populate the unified database from all PMS sources.
    """
    print("=" * 60)
    print("Unified Data Layer Population")
    print("=" * 60)
    
    # Initialize unified database if needed
    if not UNIFIED_DB_PATH.exists():
        init_database(UNIFIED_DB_PATH, UNIFIED_SCHEMA)
    
    # Clear existing data for fresh sync
    conn = sqlite3.connect(UNIFIED_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM unified_units")
    cursor.execute("DELETE FROM unified_residents")
    cursor.execute("DELETE FROM unified_leases")
    cursor.execute("DELETE FROM unified_occupancy_metrics")
    cursor.execute("DELETE FROM unified_pricing_metrics")
    cursor.execute("DELETE FROM unified_leasing_metrics")
    conn.commit()
    conn.close()
    
    # Populate from each source
    rp_records = populate_unified_from_realpage()
    yardi_records = populate_unified_from_yardi()
    
    # Calculate metrics
    calculate_occupancy_metrics()
    calculate_pricing_metrics()
    calculate_leasing_metrics()
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 UNIFIED DATABASE SUMMARY")
    print("=" * 60)
    
    conn = sqlite3.connect(UNIFIED_DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM unified_properties")
    print(f"  Properties:        {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM unified_units")
    print(f"  Units:             {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM unified_residents")
    print(f"  Residents:         {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM unified_leases")
    print(f"  Leases:            {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM unified_occupancy_metrics")
    print(f"  Occupancy Metrics: {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM unified_pricing_metrics")
    print(f"  Pricing Metrics:   {cursor.fetchone()[0]}")
    
    cursor.execute("SELECT COUNT(*) FROM unified_leasing_metrics")
    print(f"  Leasing Metrics:   {cursor.fetchone()[0]}")
    
    # Show occupancy summary
    print("\n📈 Occupancy Summary:")
    occupancy = cursor.execute("""
        SELECT p.name, p.pms_source, o.total_units, o.occupied_units, 
               o.physical_occupancy, o.leased_percentage
        FROM unified_properties p
        JOIN unified_occupancy_metrics o ON p.unified_property_id = o.unified_property_id
        ORDER BY p.name
    """).fetchall()
    
    for row in occupancy:
        print(f"   [{row[1].upper()[:2]}] {row[0]}: {row[3]}/{row[2]} units, "
              f"{row[4]:.1f}% physical, {row[5]:.1f}% leased")
    
    conn.close()
    
    print(f"\n✅ Unified data saved to: {UNIFIED_DB_PATH}")


def show_unified_summary():
    """Display detailed summary of unified database."""
    if not UNIFIED_DB_PATH.exists():
        print("❌ Unified database not found. Run population first.")
        return
    
    conn = sqlite3.connect(UNIFIED_DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("📊 UNIFIED DATABASE DETAILED VIEW")
    print("=" * 60)
    
    # Properties
    props = cursor.execute("""
        SELECT unified_property_id, pms_source, name, address, city, state
        FROM unified_properties
    """).fetchall()
    
    print(f"\n🏢 Properties ({len(props)}):")
    for p in props:
        print(f"   [{p['pms_source'].upper()[:2]}] {p['unified_property_id']}")
        print(f"       Name: {p['name']}")
        print(f"       Location: {p['address']}, {p['city']}, {p['state']}")
    
    # Unit Status
    print(f"\n🏠 Units by Status:")
    unit_status = cursor.execute("""
        SELECT pms_source, status, COUNT(*)
        FROM unified_units
        GROUP BY pms_source, status
        ORDER BY pms_source, status
    """).fetchall()
    for row in unit_status:
        print(f"   [{row[0].upper()[:2]}] {row[1]}: {row[2]}")
    
    # Pricing by floorplan
    print(f"\n💰 Pricing by Floorplan:")
    pricing = cursor.execute("""
        SELECT p.name, pm.floorplan_name, pm.bedrooms, pm.unit_count,
               pm.asking_rent, pm.in_place_rent, pm.rent_growth
        FROM unified_pricing_metrics pm
        JOIN unified_properties p ON pm.unified_property_id = p.unified_property_id
        ORDER BY p.name, pm.bedrooms
    """).fetchall()
    
    current_prop = None
    for row in pricing:
        if row[0] != current_prop:
            current_prop = row[0]
            print(f"\n   {current_prop}:")
        print(f"      {row[1]} ({row[2]}BR): {row[3]} units, "
              f"Asking ${row[4]:.0f}, In-Place ${row[5]:.0f}, Growth {row[6]:.1f}%")
    
    # Leasing metrics
    print(f"\n📈 Leasing Metrics (Current Month):")
    leasing = cursor.execute("""
        SELECT p.name, lm.move_ins, lm.move_outs, lm.net_move_ins,
               lm.renewals, lm.renewal_percentage
        FROM unified_leasing_metrics lm
        JOIN unified_properties p ON lm.unified_property_id = p.unified_property_id
        WHERE lm.period = 'current_month'
    """).fetchall()
    
    for row in leasing:
        print(f"   {row[0]}:")
        print(f"      Move-ins: {row[1]}, Move-outs: {row[2]}, Net: {row[3]}")
        print(f"      Renewals: {row[4]} ({row[5]:.1f}%)")
    
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Unified Data Layer Population")
    parser.add_argument("--summary", action="store_true", help="Show database summary only")
    args = parser.parse_args()
    
    if args.summary:
        show_unified_summary()
    else:
        populate_unified_database()
