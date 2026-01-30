"""
Test Script: Populate RealPage Raw Database.

Pulls data from RealPage RPX Gateway API and stores in realpage_raw.db.
This is a READ-ONLY extraction - no modifications to RealPage data.
"""

import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.clients.realpage_client import RealPageClient
from app.db.schema import REALPAGE_DB_PATH, REALPAGE_SCHEMA, init_database


async def populate_realpage_database(site_id_override: str = None):
    """
    Pull all available data from RealPage API and store in local database.
    
    Args:
        site_id_override: Optional site ID to extract (overrides .env default)
    """
    print("=" * 60)
    print("RealPage Data Extraction")
    print("=" * 60)
    
    # Initialize database if needed
    if not REALPAGE_DB_PATH.exists():
        init_database(REALPAGE_DB_PATH, REALPAGE_SCHEMA)
    
    # Initialize client (optionally with site override)
    if site_id_override:
        client = RealPageClient(siteid=site_id_override)
    else:
        client = RealPageClient()
    
    if not client.url or not client.pmcid or not client.siteid:
        print("❌ RealPage credentials not configured in .env")
        print("   Required: REALPAGE_URL, REALPAGE_PMCID, REALPAGE_SITEID, REALPAGE_LICENSEKEY")
        return
    
    pmc_id = client.pmcid
    site_id = client.siteid
    
    print(f"\nConnecting to RealPage...")
    print(f"  PMC ID: {pmc_id}")
    print(f"  Site ID: {site_id}")
    
    conn = sqlite3.connect(REALPAGE_DB_PATH)
    cursor = conn.cursor()
    
    extraction_start = datetime.now()
    
    try:
        # 1. Extract Properties/Sites
        print("\n📦 Extracting properties (getSiteList)...")
        try:
            properties = await client.get_properties()
            for prop in properties:
                cursor.execute("""
                    INSERT OR REPLACE INTO realpage_properties 
                    (pmc_id, site_id, site_name, address, city, state, zip, extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pmc_id,
                    prop.get('property_id', site_id),
                    prop.get('name', ''),
                    prop.get('address', ''),
                    prop.get('city', ''),
                    prop.get('state', ''),
                    prop.get('zip', ''),
                    datetime.now().isoformat()
                ))
            print(f"   ✅ Extracted {len(properties)} properties")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 2. Extract Buildings
        print("\n🏢 Extracting buildings (getBuildings)...")
        try:
            buildings = await client.get_buildings()
            for bldg in buildings:
                cursor.execute("""
                    INSERT OR REPLACE INTO realpage_buildings
                    (pmc_id, site_id, building_id, building_name, address, extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    pmc_id,
                    site_id,
                    bldg.get('building_id', ''),
                    bldg.get('name', ''),
                    bldg.get('address', ''),
                    datetime.now().isoformat()
                ))
            print(f"   ✅ Extracted {len(buildings)} buildings")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 3. Extract Units
        print("\n🏠 Extracting units (unitlist)...")
        try:
            units = await client.get_units_raw(site_id)
            for unit in units:
                cursor.execute("""
                    INSERT OR REPLACE INTO realpage_units
                    (pmc_id, site_id, unit_id, unit_number, building_name, floor,
                     floorplan_id, floorplan_name, bedrooms, bathrooms, 
                     rentable_sqft, market_rent, vacant, available, available_date,
                     made_ready_date, on_notice_for_date, extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pmc_id,
                    site_id,
                    unit.get('UnitID', ''),
                    unit.get('UnitNumber', ''),
                    unit.get('BuildingName', ''),
                    unit.get('Floor', ''),
                    unit.get('FloorplanID', ''),
                    unit.get('FloorplanName', ''),
                    int(unit.get('Bedrooms', 0) or 0),
                    float(unit.get('Bathrooms', 0) or 0),
                    int(unit.get('RentableSqft', 0) or 0),
                    float(unit.get('MarketRent', 0) or 0),
                    unit.get('Vacant', 'F'),
                    unit.get('Available', 'F'),
                    unit.get('AvailableDate'),
                    unit.get('UnitMadeReadyDate'),
                    unit.get('OnNoticeForDate'),
                    datetime.now().isoformat()
                ))
            print(f"   ✅ Extracted {len(units)} units")
            
            # Count by status (using raw RealPage fields)
            vacant = len([u for u in units if u.get('Vacant') == 'T'])
            available = len([u for u in units if u.get('Available') == 'T'])
            print(f"      Vacant: {vacant}, Available: {available}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 4. Extract Residents
        print("\n👥 Extracting residents (getresidentlistinfo)...")
        try:
            residents = await client.get_residents(site_id, status="all")
            for res in residents:
                cursor.execute("""
                    INSERT INTO realpage_residents
                    (pmc_id, site_id, resident_id, unit_id, unit_number,
                     first_name, last_name, lease_status, begin_date, end_date,
                     move_in_date, move_out_date, notice_given_date, rent,
                     extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pmc_id,
                    site_id,
                    res.get('resident_id', ''),
                    res.get('unit_id', ''),
                    res.get('unit_number', ''),
                    res.get('first_name', ''),
                    res.get('last_name', ''),
                    res.get('status', ''),
                    res.get('lease_start'),
                    res.get('lease_end'),
                    res.get('move_in_date'),
                    res.get('move_out_date'),
                    res.get('notice_date'),
                    res.get('current_rent', 0),
                    datetime.now().isoformat()
                ))
            print(f"   ✅ Extracted {len(residents)} residents")
            
            # Count by status
            status_counts = {}
            for r in residents:
                s = r.get('status', 'unknown')
                status_counts[s] = status_counts.get(s, 0) + 1
            for status, count in status_counts.items():
                print(f"      {status}: {count}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 5. Extract Leases (expanded with all fields)
        print("\n📋 Extracting leases (getleaseinfo - expanded)...")
        try:
            leases = await client.get_leases_raw(site_id)
            for lease in leases:
                cursor.execute("""
                    INSERT INTO realpage_leases
                    (pmc_id, site_id, lease_id, resh_id, unit_id,
                     lease_start_date, lease_end_date, lease_term, lease_term_desc,
                     rent_amount, next_lease_id, prior_lease_id, status, status_text,
                     type_code, type_text, move_in_date, sched_move_in_date,
                     applied_date, active_date, inactive_date, last_renewal_date,
                     initial_lease_date, bill_date, payment_due_date,
                     current_balance, total_paid, late_day_of_month, late_charge_pct,
                     evict, head_of_household_name, extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pmc_id,
                    site_id,
                    lease.get('lease_id'),
                    lease.get('resh_id'),
                    lease.get('unit_id'),
                    lease.get('lease_start_date'),
                    lease.get('lease_end_date'),
                    lease.get('lease_term'),
                    lease.get('lease_term_desc'),
                    lease.get('rent_amount', 0),
                    lease.get('next_lease_id'),
                    lease.get('prior_lease_id'),
                    lease.get('status'),
                    lease.get('status_text'),
                    lease.get('type_code'),
                    lease.get('type_text'),
                    lease.get('move_in_date'),
                    lease.get('sched_move_in_date'),
                    lease.get('applied_date'),
                    lease.get('active_date'),
                    lease.get('inactive_date'),
                    lease.get('last_renewal_date'),
                    lease.get('initial_lease_date'),
                    lease.get('bill_date'),
                    lease.get('payment_due_date'),
                    lease.get('current_balance', 0),
                    lease.get('total_paid', 0),
                    lease.get('late_day_of_month'),
                    lease.get('late_charge_pct', 0),
                    lease.get('evict'),
                    lease.get('head_of_household_name'),
                    datetime.now().isoformat()
                ))
            print(f"   ✅ Extracted {len(leases)} leases")
            
            # Count by status
            status_counts = {}
            for l in leases:
                s = l.get('status_text', 'unknown')
                status_counts[s] = status_counts.get(s, 0) + 1
            for status, count in status_counts.items():
                print(f"      {status}: {count}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 6. Extract Rentable Items (amenities, parking, storage)
        print("\n🅿️ Extracting rentable items (getRentableItems)...")
        try:
            items = await client.get_rentable_items(site_id)
            for item in items:
                cursor.execute("""
                    INSERT INTO realpage_rentable_items
                    (pmc_id, site_id, rid_id, item_name, item_type, description,
                     billing_amount, frequency, transaction_code_id, in_service,
                     serial_number, status, date_available, unit_id, lease_id,
                     resh_id, resident_member_id, start_date, end_date, extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    pmc_id,
                    site_id,
                    item.get('rid_id'),
                    item.get('item_name'),
                    item.get('item_type'),
                    item.get('description'),
                    item.get('billing_amount', 0),
                    item.get('frequency'),
                    item.get('transaction_code_id'),
                    item.get('in_service'),
                    item.get('serial_number'),
                    item.get('status'),
                    item.get('date_available'),
                    item.get('unit_id'),
                    item.get('lease_id'),
                    item.get('resh_id'),
                    item.get('resident_member_id'),
                    item.get('start_date'),
                    item.get('end_date'),
                    datetime.now().isoformat()
                ))
            print(f"   ✅ Extracted {len(items)} rentable items")
            
            # Count by type
            type_counts = {}
            for i in items:
                t = i.get('item_type', 'unknown')
                type_counts[t] = type_counts.get(t, 0) + 1
            for item_type, count in type_counts.items():
                print(f"      {item_type}: {count}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 6. Log extraction
        cursor.execute("""
            INSERT INTO realpage_extraction_log
            (pmc_id, site_id, table_name, records_extracted, 
             extraction_started_at, extraction_completed_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            pmc_id,
            site_id,
            'all',
            cursor.rowcount,
            extraction_start.isoformat(),
            datetime.now().isoformat(),
            'success'
        ))
        
        conn.commit()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 EXTRACTION SUMMARY")
        print("=" * 60)
        
        cursor.execute("SELECT COUNT(*) FROM realpage_properties")
        print(f"  Properties: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM realpage_buildings")
        print(f"  Buildings:  {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM realpage_units")
        print(f"  Units:      {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM realpage_residents")
        print(f"  Residents:  {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM realpage_leases")
        print(f"  Leases:     {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM realpage_rentable_items")
        print(f"  Rentable Items: {cursor.fetchone()[0]}")
        
        print(f"\n✅ Data saved to: {REALPAGE_DB_PATH}")
        
    except Exception as e:
        print(f"\n❌ Extraction failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def show_realpage_summary():
    """Display summary of data in RealPage database."""
    if not REALPAGE_DB_PATH.exists():
        print("❌ RealPage database not found. Run extraction first.")
        return
    
    conn = sqlite3.connect(REALPAGE_DB_PATH)
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("📊 REALPAGE DATABASE CONTENTS")
    print("=" * 60)
    
    # Properties
    cursor.execute("SELECT site_id, site_name, city, state FROM realpage_properties")
    props = cursor.fetchall()
    print(f"\n🏢 Properties ({len(props)}):")
    for p in props:
        print(f"   [{p[0]}] {p[1]} - {p[2]}, {p[3]}")
    
    # Units summary
    cursor.execute("""
        SELECT vacant, COUNT(*) 
        FROM realpage_units 
        GROUP BY vacant
    """)
    unit_stats = cursor.fetchall()
    print(f"\n🏠 Units:")
    for status, count in unit_stats:
        label = "Vacant" if status == 'T' else "Occupied"
        print(f"   {label}: {count}")
    
    # Floorplan breakdown
    cursor.execute("""
        SELECT floorplan_name, bedrooms, COUNT(*), AVG(market_rent)
        FROM realpage_units
        GROUP BY floorplan_name, bedrooms
        ORDER BY bedrooms
    """)
    print(f"\n📐 Floorplans:")
    for fp in cursor.fetchall():
        print(f"   {fp[0]} ({fp[1]}BR): {fp[2]} units, ${fp[3]:.0f} avg rent")
    
    # Residents by status
    cursor.execute("""
        SELECT lease_status, COUNT(*)
        FROM realpage_residents
        GROUP BY lease_status
        ORDER BY COUNT(*) DESC
    """)
    print(f"\n👥 Residents by Status:")
    for status, count in cursor.fetchall():
        print(f"   {status}: {count}")
    
    # Rentable Items by type
    cursor.execute("""
        SELECT item_type, COUNT(*), SUM(billing_amount), 
               SUM(CASE WHEN status LIKE '%Available%' THEN 1 ELSE 0 END) as available
        FROM realpage_rentable_items
        GROUP BY item_type
        ORDER BY COUNT(*) DESC
    """)
    results = cursor.fetchall()
    if results:
        print(f"\n🅿️ Rentable Items (Amenities):")
        for item_type, count, total_rev, available in results:
            print(f"   {item_type}: {count} items, ${total_rev:.0f}/mo potential, {available} available")
    
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="RealPage Data Extraction")
    parser.add_argument("--summary", action="store_true", help="Show database summary only")
    parser.add_argument("--site", type=str, help="Override site ID (e.g., 5536211 for Parkside)")
    args = parser.parse_args()
    
    if args.summary:
        show_realpage_summary()
    else:
        asyncio.run(populate_realpage_database(site_id_override=args.site))
        show_realpage_summary()
