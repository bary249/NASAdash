"""
Sync RealPage report data to Unified database.

This script reads from realpage_raw.db (box_score, rent_roll, delinquency tables)
and populates the unified.db tables for dashboard display.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

# Database paths
DB_DIR = Path(__file__).parent / "data"
REALPAGE_DB_PATH = DB_DIR / "realpage_raw.db"
UNIFIED_DB_PATH = DB_DIR / "unified.db"

# Property mapping: RealPage property_id -> unified_property_id
# All Kairoi properties (PMC ID: 4248314)
PROPERTY_MAPPING = {
    # Original properties
    "4248319": {"unified_id": "edison_rino", "name": "Edison at RiNo"},
    "4779341": {"unified_id": "aspire_7th_grant", "name": "Aspire 7th and Grant"},
    "5446271": {"unified_id": "ridian", "name": "Ridian"},
    "5472172": {"unified_id": "nexus_east", "name": "Nexus East"},
    "5536211": {"unified_id": "parkside", "name": "Parkside at Round Rock"},
    # Additional Kairoi properties
    "5339721": {"unified_id": "kalaco", "name": "Kalaco"},
    "5481703": {"unified_id": "7_east", "name": "7 East"},
    "5473254": {"unified_id": "block_44", "name": "Block 44"},
    "4682517": {"unified_id": "curate_orchard", "name": "Curate at Orchard Town Center"},
    "5536209": {"unified_id": "eden_keller_ranch", "name": "Eden Keller Ranch"},
    "5507303": {"unified_id": "harvest", "name": "Harvest"},
    "5558216": {"unified_id": "heights_interlocken", "name": "Heights at Interlocken"},
    "5590740": {"unified_id": "luna", "name": "Luna"},
    "4481243": {"unified_id": "park_17", "name": "Park 17"},
    "5481704": {"unified_id": "pearl_lantana", "name": "Pearl Lantana"},
    "5486880": {"unified_id": "slate", "name": "Slate"},
    "5486881": {"unified_id": "sloane", "name": "Sloane"},
    "5481705": {"unified_id": "stonewood", "name": "Stonewood"},
    "5581218": {"unified_id": "ten50", "name": "Ten50"},
    "4996967": {"unified_id": "the_alcott", "name": "The Alcott"},
    "5286092": {"unified_id": "the_broadleaf", "name": "The Broadleaf"},
    "4832865": {"unified_id": "the_confluence", "name": "The Confluence"},
    "5558220": {"unified_id": "links_plum_creek", "name": "The Links at Plum Creek"},
    "5114464": {"unified_id": "the_pearl", "name": "thePearl"},
    "5286878": {"unified_id": "the_quinci", "name": "theQuinci"},
    # New properties from CSV
    "5618425": {"unified_id": "discovery_kingwood", "name": "Discovery at Kingwood"},
    "5618432": {"unified_id": "izzy", "name": "Izzy"},
    "5480255": {"unified_id": "the_avant", "name": "The Avant"},
    "5558217": {"unified_id": "the_hunter", "name": "The Hunter"},
    "5375283": {"unified_id": "the_northern", "name": "The Northern"},
    "4976258": {"unified_id": "station_riverfront", "name": "The Station at Riverfront Park"},
    # Manual imports
    "kairoi-northern": {"unified_id": "the_northern", "name": "The Northern"},
}


def get_realpage_conn():
    """Get connection to realpage_raw.db."""
    return sqlite3.connect(REALPAGE_DB_PATH)


def get_unified_conn():
    """Get connection to unified.db."""
    return sqlite3.connect(UNIFIED_DB_PATH)


def sync_properties():
    """Sync properties from RealPage to unified."""
    print("\n📍 Syncing properties...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    
    # Get distinct properties from box_score
    rp_cursor = rp_conn.cursor()
    rp_cursor.execute("""
        SELECT DISTINCT property_id, property_name 
        FROM realpage_box_score 
        WHERE property_id IS NOT NULL
    """)
    
    uni_cursor = uni_conn.cursor()
    count = 0
    
    for row in rp_cursor.fetchall():
        property_id, property_name = row
        
        if property_id not in PROPERTY_MAPPING:
            print(f"  ⚠️ Unknown property_id: {property_id}")
            continue
        
        mapping = PROPERTY_MAPPING[property_id]
        unified_id = mapping["unified_id"]
        name = mapping["name"] or property_name
        
        uni_cursor.execute("""
            INSERT OR REPLACE INTO unified_properties
            (unified_property_id, pms_source, pms_property_id, name, synced_at)
            VALUES (?, 'realpage', ?, ?, ?)
        """, (unified_id, property_id, name, datetime.now().isoformat()))
        count += 1
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} properties")
    return count


def sync_occupancy_metrics():
    """Sync occupancy metrics from box_score to unified."""
    print("\n📊 Syncing occupancy metrics...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    # Get latest box_score data per property
    rp_cursor.execute("""
        SELECT 
            property_id,
            report_date,
            SUM(total_units) as total_units,
            SUM(occupied_units) as occupied_units,
            SUM(vacant_units) as vacant_units,
            SUM(vacant_leased) as preleased_vacant,
            SUM(occupied_on_notice) as notice_units,
            SUM(model_units) as model_units,
            SUM(down_units) as down_units
        FROM realpage_box_score
        WHERE property_id IS NOT NULL
        GROUP BY property_id, report_date
        ORDER BY property_id, report_date DESC
    """)
    
    count = 0
    seen = set()
    
    for row in rp_cursor.fetchall():
        property_id = row[0]
        report_date = row[1]
        
        # Only take latest per property
        if property_id in seen:
            continue
        seen.add(property_id)
        
        if property_id not in PROPERTY_MAPPING:
            continue
        
        unified_id = PROPERTY_MAPPING[property_id]["unified_id"]
        
        total_units = row[2] or 0
        occupied_units = row[3] or 0
        vacant_units = row[4] or 0
        preleased_vacant = row[5] or 0
        notice_units = row[6] or 0
        model_units = row[7] or 0
        down_units = row[8] or 0
        
        leased_units = occupied_units + preleased_vacant
        physical_occupancy = (occupied_units / total_units * 100) if total_units > 0 else 0
        leased_percentage = (leased_units / total_units * 100) if total_units > 0 else 0
        
        # Calculate exposure: Vacant + Notices - Preleased
        # Exposure 30D: ~50% of notices expected within 30 days
        # Exposure 60D: ~100% of notices expected within 60 days
        exposure_30 = max(0, vacant_units + int(notice_units * 0.5) - preleased_vacant)
        exposure_60 = max(0, vacant_units + notice_units - preleased_vacant)
        
        uni_cursor.execute("""
            INSERT OR REPLACE INTO unified_occupancy_metrics
            (unified_property_id, snapshot_date, total_units, occupied_units, vacant_units,
             leased_units, preleased_vacant, notice_units, model_units, down_units,
             physical_occupancy, leased_percentage, exposure_30_days, exposure_60_days, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unified_id, report_date, total_units, occupied_units, vacant_units,
            leased_units, preleased_vacant, notice_units, model_units, down_units,
            round(physical_occupancy, 2), round(leased_percentage, 2),
            exposure_30, exposure_60,
            datetime.now().isoformat()
        ))
        count += 1
        print(f"  {PROPERTY_MAPPING[property_id]['name']}: {physical_occupancy:.1f}% occupied ({occupied_units}/{total_units})")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced occupancy for {count} properties")
    return count


def sync_pricing_metrics():
    """Sync pricing metrics from box_score to unified (by floorplan)."""
    print("\n💰 Syncing pricing metrics...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    # Get latest box_score data per property/floorplan
    rp_cursor.execute("""
        SELECT 
            property_id,
            report_date,
            floorplan,
            total_units,
            avg_sqft,
            avg_market_rent,
            avg_actual_rent
        FROM realpage_box_score
        WHERE property_id IS NOT NULL
        ORDER BY property_id, report_date DESC
    """)
    
    count = 0
    seen = set()
    
    for row in rp_cursor.fetchall():
        property_id = row[0]
        report_date = row[1]
        floorplan = row[2]
        
        key = (property_id, floorplan)
        if key in seen:
            continue
        seen.add(key)
        
        if property_id not in PROPERTY_MAPPING:
            continue
        
        unified_id = PROPERTY_MAPPING[property_id]["unified_id"]
        
        unit_count = row[3] or 0
        avg_sqft = row[4] or 0
        asking_rent = row[5] or 0
        in_place_rent = row[6] or 0
        
        asking_per_sf = (asking_rent / avg_sqft) if avg_sqft > 0 else 0
        in_place_per_sf = (in_place_rent / avg_sqft) if avg_sqft > 0 else 0
        rent_growth = ((asking_rent - in_place_rent) / in_place_rent) if in_place_rent > 0 else 0
        
        uni_cursor.execute("""
            INSERT OR REPLACE INTO unified_pricing_metrics
            (unified_property_id, snapshot_date, floorplan, unit_count,
             avg_square_feet, in_place_rent, in_place_per_sf,
             asking_rent, asking_per_sf, rent_growth, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unified_id, report_date, floorplan, unit_count,
            avg_sqft, round(in_place_rent, 2), round(in_place_per_sf, 2),
            round(asking_rent, 2), round(asking_per_sf, 2), round(rent_growth, 4),
            datetime.now().isoformat()
        ))
        count += 1
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} floorplan pricing records")
    return count


def sync_units_from_rent_roll():
    """Sync unit-level data from rent_roll to unified_units."""
    print("\n🏠 Syncing units from rent roll...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    # Get latest rent roll data
    rp_cursor.execute("""
        SELECT 
            property_id,
            report_date,
            unit_number,
            floorplan,
            sqft,
            market_rent,
            actual_rent,
            status,
            resident_name
        FROM realpage_rent_roll
        WHERE property_id IS NOT NULL
        ORDER BY property_id, report_date DESC
    """)
    
    count = 0
    seen = set()
    
    for row in rp_cursor.fetchall():
        property_id = row[0]
        unit_number = row[2]
        
        key = (property_id, unit_number)
        if key in seen:
            continue
        seen.add(key)
        
        if property_id not in PROPERTY_MAPPING:
            continue
        
        unified_id = PROPERTY_MAPPING[property_id]["unified_id"]
        
        floorplan = row[3]
        sqft = row[4] or 0
        market_rent = row[5] or 0
        actual_rent = row[6] or 0
        status_raw = (row[7] or "").lower()
        
        # Map status from rent_roll status field
        if "occupied" in status_raw:
            status = "occupied"
        elif "vacant" in status_raw:
            status = "vacant"
        elif "notice" in status_raw:
            status = "notice"
        elif "model" in status_raw:
            status = "model"
        elif "down" in status_raw:
            status = "down"
        else:
            status = "vacant"
        
        uni_cursor.execute("""
            INSERT OR REPLACE INTO unified_units
            (unified_property_id, pms_source, pms_unit_id, unit_number,
             floorplan, square_feet, market_rent, status, synced_at)
            VALUES (?, 'realpage', ?, ?, ?, ?, ?, ?, ?)
        """, (
            unified_id, unit_number, unit_number,
            floorplan, sqft, market_rent, status,
            datetime.now().isoformat()
        ))
        count += 1
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} units")
    return count


def sync_residents_from_rent_roll():
    """Sync resident data from rent_roll to unified_residents."""
    print("\n👥 Syncing residents from rent roll...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    # Clear existing residents (we'll repopulate from latest data)
    uni_cursor.execute("DELETE FROM unified_residents WHERE pms_source = 'realpage'")
    
    # Get latest rent roll data - include occupied units even without names
    rp_cursor.execute("""
        SELECT 
            property_id,
            report_date,
            unit_number,
            resident_name,
            lease_start,
            lease_end,
            move_in_date,
            move_out_date,
            actual_rent,
            balance
        FROM realpage_rent_roll
        WHERE property_id IS NOT NULL 
          AND status IN ('Occupied', 'Occupied-NTV', 'Occupied-NTVL')
        ORDER BY property_id, report_date DESC
    """)
    
    count = 0
    seen = set()
    
    for row in rp_cursor.fetchall():
        property_id = row[0]
        unit_number = row[2]
        resident_name = row[3]
        
        key = (property_id, unit_number)
        if key in seen:
            continue
        seen.add(key)
        
        if property_id not in PROPERTY_MAPPING:
            continue
        
        unified_id = PROPERTY_MAPPING[property_id]["unified_id"]
        
        # Split name if available
        if resident_name:
            name_parts = resident_name.split(",")
            last_name = name_parts[0].strip() if name_parts else ""
            first_name = name_parts[1].strip() if len(name_parts) > 1 else ""
            full_name = resident_name
        else:
            first_name = ""
            last_name = ""
            full_name = f"Unit {unit_number} Resident"
        
        lease_start = row[4]
        lease_end = row[5]
        move_in = row[6]
        move_out = row[7]
        current_rent = row[8] or 0
        balance = row[9] or 0
        
        # Determine status
        status = "current"
        if move_out:
            status = "past"
        
        resident_id = f"{property_id}_{unit_number}"
        
        uni_cursor.execute("""
            INSERT INTO unified_residents
            (unified_property_id, pms_source, pms_resident_id, pms_unit_id, unit_number,
             first_name, last_name, full_name, status, lease_start, lease_end,
             move_in_date, move_out_date, current_rent, balance, synced_at)
            VALUES (?, 'realpage', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unified_id, resident_id, unit_number, unit_number,
            first_name, last_name, full_name, status, lease_start, lease_end,
            move_in, move_out, current_rent, balance,
            datetime.now().isoformat()
        ))
        count += 1
    
    # Fallback: generate residents from unified_units for properties missing from rent_roll
    synced_props = set()
    for (pid, _) in seen:
        if pid in PROPERTY_MAPPING:
            synced_props.add(PROPERTY_MAPPING[pid]["unified_id"])
    
    uni_cursor.execute("""
        SELECT unified_property_id, unit_number, floorplan, market_rent, status
        FROM unified_units
        WHERE pms_source = 'realpage' AND status = 'occupied'
    """)
    
    fallback_count = 0
    for row in uni_cursor.fetchall():
        uid, unit_num, floorplan, rent, status = row
        if uid in synced_props:
            continue  # Already have rent_roll data
        
        key_fb = f"fallback_{uid}_{unit_num}"
        uni_cursor.execute("""
            INSERT OR IGNORE INTO unified_residents
            (unified_property_id, pms_source, pms_resident_id, pms_unit_id, unit_number,
             first_name, last_name, full_name, status, current_rent, synced_at)
            VALUES (?, 'realpage', ?, ?, ?, '', '', ?, 'current', ?, ?)
        """, (
            uid, key_fb, unit_num, unit_num,
            f"Unit {unit_num} Resident", rent or 0,
            datetime.now().isoformat()
        ))
        fallback_count += 1
    
    if fallback_count > 0:
        print(f"  ℹ️  Added {fallback_count} residents from unified_units fallback")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count + fallback_count} residents total")
    return count + fallback_count


def sync_delinquency():
    """Sync delinquency data from realpage_delinquency to unified."""
    print("\n💸 Syncing delinquency data...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    # Create delinquency table in unified if not exists
    uni_cursor.execute("""
        CREATE TABLE IF NOT EXISTS unified_delinquency (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            unified_property_id TEXT NOT NULL,
            report_date TEXT,
            unit_number TEXT,
            resident_name TEXT,
            status TEXT,
            current_balance REAL,
            balance_0_30 REAL,
            balance_31_60 REAL,
            balance_61_90 REAL,
            balance_over_90 REAL,
            prepaid REAL,
            net_balance REAL,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Clear existing delinquency data
    uni_cursor.execute("DELETE FROM unified_delinquency")
    
    # Get latest delinquency data
    rp_cursor.execute("""
        SELECT 
            property_id,
            report_date,
            unit_number,
            resident_name,
            status,
            current_balance,
            balance_0_30,
            balance_31_60,
            balance_61_90,
            balance_over_90,
            prepaid,
            net_balance
        FROM realpage_delinquency
        WHERE property_id IS NOT NULL
        ORDER BY property_id, report_date DESC
    """)
    
    count = 0
    seen = set()
    
    for row in rp_cursor.fetchall():
        property_id = row[0]
        unit_number = row[2]
        
        key = (property_id, unit_number)
        if key in seen:
            continue
        seen.add(key)
        
        if property_id not in PROPERTY_MAPPING:
            continue
        
        unified_id = PROPERTY_MAPPING[property_id]["unified_id"]
        
        # Row indices: 0=property_id, 1=report_date, 2=unit_number, 3=resident_name,
        # 4=status, 5=current_balance, 6=balance_0_30, 7=balance_31_60, 8=balance_61_90,
        # 9=balance_over_90, 10=prepaid, 11=net_balance
        uni_cursor.execute("""
            INSERT INTO unified_delinquency
            (unified_property_id, report_date, unit_number, resident_name, status,
             current_balance, balance_0_30, balance_31_60, balance_61_90,
             balance_over_90, prepaid, net_balance, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unified_id, row[1], row[2], row[3], row[4] or '',
            row[5] or 0, row[6] or 0, row[7] or 0, row[8] or 0,
            row[9] or 0, row[10] or 0, row[11] or 0,
            datetime.now().isoformat()
        ))
        count += 1
    
    uni_conn.commit()
    
    # Summary by property
    uni_cursor.execute("""
        SELECT unified_property_id, COUNT(*), 
               SUM(CASE WHEN balance_0_30 > 0 THEN balance_0_30 ELSE 0 END) as total_30,
               SUM(CASE WHEN net_balance > 0 THEN net_balance ELSE 0 END) as total_net
        FROM unified_delinquency
        GROUP BY unified_property_id
    """)
    for r in uni_cursor.fetchall():
        print(f"  {r[0]}: {r[1]} units, 30-day: ${r[2]:,.2f}, net: ${r[3]:,.2f}")
    
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} delinquency records")
    return count


def log_sync(property_count, occupancy_count, pricing_count, unit_count, resident_count, delinquency_count=0):
    """Log the sync operation."""
    uni_conn = get_unified_conn()
    cursor = uni_conn.cursor()
    
    cursor.execute("""
        INSERT INTO unified_sync_log
        (unified_property_id, pms_source, sync_type, tables_synced, records_synced,
         sync_started_at, sync_completed_at, status)
        VALUES (?, 'realpage', 'full', ?, ?, ?, ?, 'success')
    """, (
        'all_properties',
        '["unified_properties", "unified_occupancy_metrics", "unified_pricing_metrics", "unified_units", "unified_residents"]',
        property_count + occupancy_count + pricing_count + unit_count + resident_count,
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))
    
    uni_conn.commit()
    uni_conn.close()


def run_full_sync():
    """Run full sync from RealPage to Unified."""
    print("=" * 60)
    print("RealPage → Unified Database Sync")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    
    property_count = sync_properties()
    occupancy_count = sync_occupancy_metrics()
    pricing_count = sync_pricing_metrics()
    unit_count = sync_units_from_rent_roll()
    resident_count = sync_residents_from_rent_roll()
    delinquency_count = sync_delinquency()
    
    log_sync(property_count, occupancy_count, pricing_count, unit_count, resident_count, delinquency_count)
    
    print("\n" + "=" * 60)
    print("SYNC COMPLETE")
    print("=" * 60)
    print(f"  Properties:   {property_count}")
    print(f"  Occupancy:    {occupancy_count}")
    print(f"  Pricing:      {pricing_count}")
    print(f"  Units:        {unit_count}")
    print(f"  Residents:    {resident_count}")
    print(f"  Delinquency:  {delinquency_count}")
    print(f"\nCompleted at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    run_full_sync()
