"""
Test Script: Populate Yardi Raw Database.

Pulls data from Yardi Voyager API and stores in yardi_raw.db.
This is a READ-ONLY extraction - no modifications to Yardi data.
"""

import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.clients.yardi_client import YardiClient
from app.db.schema import YARDI_DB_PATH, YARDI_SCHEMA, init_database


async def populate_yardi_database(property_id: str = None):
    """
    Pull all available data from Yardi API and store in local database.
    
    Args:
        property_id: Specific property to extract. If None, extracts all.
    """
    print("=" * 60)
    print("Yardi Data Extraction")
    print("=" * 60)
    
    # Initialize database if needed
    if not YARDI_DB_PATH.exists():
        init_database(YARDI_DB_PATH, YARDI_SCHEMA)
    
    # Initialize client
    client = YardiClient()
    
    if not client.settings.yardi_username:
        print("❌ Yardi credentials not configured in .env")
        print("   Required: YARDI_USERNAME, YARDI_PASSWORD, YARDI_SERVER_NAME, etc.")
        return
    
    print(f"\nConnecting to Yardi...")
    print(f"  Server: {client.settings.yardi_server_name}")
    print(f"  Database: {client.settings.yardi_database}")
    
    conn = sqlite3.connect(YARDI_DB_PATH)
    cursor = conn.cursor()
    
    extraction_start = datetime.now()
    
    try:
        # 1. Extract Properties
        print("\n📦 Extracting properties (GetPropertyConfigurations)...")
        try:
            properties = await client.get_properties()
            for prop in properties:
                cursor.execute("""
                    INSERT OR REPLACE INTO yardi_properties 
                    (property_id, property_code, marketing_name, address, extracted_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    prop.get('property_id', ''),
                    prop.get('property_id', ''),
                    prop.get('name', ''),
                    prop.get('address', ''),
                    datetime.now().isoformat()
                ))
            print(f"   ✅ Extracted {len(properties)} properties")
            
            # Use first property if none specified
            if not property_id and properties:
                property_id = properties[0].get('property_id')
                print(f"   Using property: {property_id}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
            return
        
        if not property_id:
            print("❌ No property ID available")
            return
        
        # 2. Extract Units
        print(f"\n🏠 Extracting units for {property_id} (GetUnitInformation)...")
        try:
            units = await client.get_units(property_id)
            for unit in units:
                cursor.execute("""
                    INSERT OR REPLACE INTO yardi_units
                    (property_id, unit_code, unit_type, unit_status,
                     bedrooms, bathrooms, sqft, market_rent, building, extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    property_id,
                    unit.get('unit_number', ''),
                    unit.get('floorplan', ''),
                    unit.get('status', ''),
                    unit.get('bedrooms', 0),
                    unit.get('bathrooms', 0),
                    unit.get('square_feet', 0),
                    unit.get('market_rent', 0),
                    unit.get('building', ''),
                    datetime.now().isoformat()
                ))
            print(f"   ✅ Extracted {len(units)} units")
            
            # Count by status
            status_counts = {}
            for u in units:
                s = u.get('status', 'unknown')
                status_counts[s] = status_counts.get(s, 0) + 1
            for status, count in status_counts.items():
                print(f"      {status}: {count}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 3. Extract Residents
        print(f"\n👥 Extracting residents for {property_id} (GetResidentsByStatus)...")
        try:
            residents = await client.get_residents(property_id, status="all")
            for res in residents:
                cursor.execute("""
                    INSERT OR REPLACE INTO yardi_residents
                    (property_id, resident_code, unit_code, first_name, last_name,
                     status, lease_from_date, lease_to_date, move_in_date, 
                     move_out_date, rent, extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    property_id,
                    res.get('resident_id', ''),
                    res.get('unit_number', ''),
                    res.get('first_name', ''),
                    res.get('last_name', ''),
                    res.get('status', ''),
                    res.get('lease_start'),
                    res.get('lease_end'),
                    res.get('move_in_date'),
                    res.get('move_out_date'),
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
        
        # 4. Extract Lease Charges
        print(f"\n💰 Extracting lease charges for {property_id} (GetResidentLeaseCharges_Login)...")
        try:
            leases = await client.get_lease_data(property_id)
            for lease in leases:
                cursor.execute("""
                    INSERT INTO yardi_lease_charges
                    (property_id, resident_code, unit_code, total_charges,
                     lease_from_date, lease_to_date, extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    property_id,
                    lease.get('resident_id', ''),
                    lease.get('unit_id', ''),
                    lease.get('rent_amount', 0),
                    lease.get('lease_start'),
                    lease.get('lease_end'),
                    datetime.now().isoformat()
                ))
            print(f"   ✅ Extracted {len(leases)} lease records")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 5. Extract Available Units (for asking rent)
        print(f"\n🏷️ Extracting available units for {property_id} (AvailableUnits_Login)...")
        try:
            result = await client.get_available_units(property_id)
            avail_units = result.get("AvailableUnits", {}).get("Unit", [])
            if not isinstance(avail_units, list):
                avail_units = [avail_units] if avail_units else []
            
            for unit in avail_units:
                if not isinstance(unit, dict):
                    continue
                cursor.execute("""
                    INSERT OR REPLACE INTO yardi_available_units
                    (property_id, unit_code, unit_type, bedrooms, bathrooms,
                     sqft, market_rent, min_rent, max_rent, available_date,
                     extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    property_id,
                    unit.get('UnitCode', ''),
                    unit.get('UnitType', ''),
                    unit.get('Bedrooms', 0),
                    unit.get('Bathrooms', 0),
                    unit.get('SQFT', 0),
                    unit.get('MarketRent', 0),
                    unit.get('MinRent', 0),
                    unit.get('MaxRent', 0),
                    unit.get('AvailableDate', ''),
                    datetime.now().isoformat()
                ))
            print(f"   ✅ Extracted {len(avail_units)} available units")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 6. Extract Guest Activity (for leads/tours)
        print(f"\n📊 Extracting guest activity for {property_id} (GetYardiGuestActivity_Login)...")
        try:
            result = await client.get_guest_activity(property_id)
            activities = result.get("GuestActivity", {}).get("Activity", [])
            if not isinstance(activities, list):
                activities = [activities] if activities else []
            
            for activity in activities:
                if not isinstance(activity, dict):
                    continue
                cursor.execute("""
                    INSERT INTO yardi_guest_activity
                    (property_id, guest_card_id, prospect_code, first_name, last_name,
                     email, phone, event_type, event_date, source, status, extracted_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    property_id,
                    activity.get('GuestCardID', ''),
                    activity.get('ProspectCode', ''),
                    activity.get('FirstName', ''),
                    activity.get('LastName', ''),
                    activity.get('Email', ''),
                    activity.get('Phone', ''),
                    activity.get('EventType', ''),
                    activity.get('EventDate', ''),
                    activity.get('Source', ''),
                    activity.get('Status', ''),
                    datetime.now().isoformat()
                ))
            print(f"   ✅ Extracted {len(activities)} guest activities")
            
            # Count by event type
            event_counts = {}
            for a in activities:
                if isinstance(a, dict):
                    e = a.get('EventType', 'unknown')
                    event_counts[e] = event_counts.get(e, 0) + 1
            for event, count in event_counts.items():
                print(f"      {event}: {count}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
        
        # 7. Log extraction
        cursor.execute("""
            INSERT INTO yardi_extraction_log
            (property_id, table_name, records_extracted, 
             extraction_started_at, extraction_completed_at, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            property_id,
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
        
        cursor.execute("SELECT COUNT(*) FROM yardi_properties")
        print(f"  Properties:      {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM yardi_units")
        print(f"  Units:           {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM yardi_residents")
        print(f"  Residents:       {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM yardi_lease_charges")
        print(f"  Lease Charges:   {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM yardi_available_units")
        print(f"  Available Units: {cursor.fetchone()[0]}")
        
        cursor.execute("SELECT COUNT(*) FROM yardi_guest_activity")
        print(f"  Guest Activity:  {cursor.fetchone()[0]}")
        
        print(f"\n✅ Data saved to: {YARDI_DB_PATH}")
        
    except Exception as e:
        print(f"\n❌ Extraction failed: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


def show_yardi_summary():
    """Display summary of data in Yardi database."""
    if not YARDI_DB_PATH.exists():
        print("❌ Yardi database not found. Run extraction first.")
        return
    
    conn = sqlite3.connect(YARDI_DB_PATH)
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("📊 YARDI DATABASE CONTENTS")
    print("=" * 60)
    
    # Properties
    cursor.execute("SELECT property_id, marketing_name, address FROM yardi_properties")
    props = cursor.fetchall()
    print(f"\n🏢 Properties ({len(props)}):")
    for p in props:
        print(f"   [{p[0]}] {p[1]} - {p[2]}")
    
    # Units summary
    cursor.execute("""
        SELECT unit_status, COUNT(*) 
        FROM yardi_units 
        GROUP BY unit_status
    """)
    unit_stats = cursor.fetchall()
    print(f"\n🏠 Units by Status:")
    for status, count in unit_stats:
        print(f"   {status}: {count}")
    
    # Floorplan breakdown
    cursor.execute("""
        SELECT unit_type, bedrooms, COUNT(*), AVG(market_rent)
        FROM yardi_units
        WHERE unit_type IS NOT NULL
        GROUP BY unit_type, bedrooms
        ORDER BY bedrooms
    """)
    floorplans = cursor.fetchall()
    if floorplans:
        print(f"\n📐 Floorplans:")
        for fp in floorplans:
            print(f"   {fp[0]} ({fp[1]}BR): {fp[2]} units, ${fp[3]:.0f} avg rent")
    
    # Residents by status
    cursor.execute("""
        SELECT status, COUNT(*)
        FROM yardi_residents
        GROUP BY status
        ORDER BY COUNT(*) DESC
    """)
    print(f"\n👥 Residents by Status:")
    for status, count in cursor.fetchall():
        print(f"   {status}: {count}")
    
    # Guest activity by type
    cursor.execute("""
        SELECT event_type, COUNT(*)
        FROM yardi_guest_activity
        GROUP BY event_type
        ORDER BY COUNT(*) DESC
    """)
    activities = cursor.fetchall()
    if activities:
        print(f"\n📊 Guest Activity by Type:")
        for event_type, count in activities:
            print(f"   {event_type}: {count}")
    
    conn.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Yardi Data Extraction")
    parser.add_argument("--property", "-p", help="Property ID to extract")
    parser.add_argument("--summary", action="store_true", help="Show database summary only")
    args = parser.parse_args()
    
    if args.summary:
        show_yardi_summary()
    else:
        asyncio.run(populate_yardi_database(args.property))
        show_yardi_summary()
