"""
Sync Yardi API data to Unified database.

This script calls the Yardi SOAP APIs and populates the unified.db tables
for dashboard display, matching the same structure as RealPage sync.
"""
import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

# Add parent path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.clients.yardi_client import YardiClient
from app.config import get_settings

# Database path
DB_DIR = Path(__file__).parent / "data"
UNIFIED_DB_PATH = DB_DIR / "unified.db"

# Yardi property mapping
# Format: yardi_property_code -> {unified_id, name}
YARDI_PROPERTY_MAPPING = {
    "venn1": {"unified_id": "venn1", "name": "Interfaces Venn1 Test Property"},
    "venn2": {"unified_id": "venn2", "name": "Interfaces Venn2 Test Property"},
    # Add more Yardi properties here as they are onboarded
}


def get_unified_conn():
    """Get connection to unified.db."""
    return sqlite3.connect(UNIFIED_DB_PATH)


async def get_yardi_properties(client: YardiClient) -> list:
    """Get list of properties from Yardi API."""
    print("\n📍 Fetching Yardi properties...")
    
    try:
        data = await client.get_property_configurations()
        result = data.get("GetPropertyConfigurationsResult", data)
        
        if isinstance(result, dict):
            props = result.get("Properties", result)
            if isinstance(props, dict):
                prop_list = props.get("Property", [])
            else:
                prop_list = props
            
            if isinstance(prop_list, dict):
                prop_list = [prop_list]
            
            properties = []
            for p in prop_list if isinstance(prop_list, list) else []:
                properties.append({
                    "property_id": p.get("Code", p.get("PropertyCode", "")),
                    "name": p.get("MarketingName", p.get("Name", "")),
                    "address": p.get("Address", {}).get("Address1", "") if isinstance(p.get("Address"), dict) else "",
                    "city": p.get("Address", {}).get("City", "") if isinstance(p.get("Address"), dict) else "",
                    "state": p.get("Address", {}).get("State", "") if isinstance(p.get("Address"), dict) else "",
                })
            
            print(f"  ✅ Found {len(properties)} Yardi properties")
            return properties
    except Exception as e:
        print(f"  ❌ Error fetching properties: {e}")
    
    return []


async def sync_properties(client: YardiClient):
    """Sync properties from Yardi API to unified."""
    print("\n📍 Syncing Yardi properties...")
    
    properties = await get_yardi_properties(client)
    uni_conn = get_unified_conn()
    uni_cursor = uni_conn.cursor()
    count = 0
    
    for prop in properties:
        property_id = prop["property_id"]
        
        # Use mapping if available, otherwise use property_id as unified_id
        if property_id in YARDI_PROPERTY_MAPPING:
            mapping = YARDI_PROPERTY_MAPPING[property_id]
            unified_id = mapping["unified_id"]
            name = mapping["name"] or prop["name"]
        else:
            unified_id = f"yardi-{property_id}"
            name = prop["name"]
        
        uni_cursor.execute("""
            INSERT OR REPLACE INTO unified_properties
            (unified_property_id, pms_source, pms_property_id, name, address, city, state, synced_at)
            VALUES (?, 'yardi', ?, ?, ?, ?, ?, ?)
        """, (
            unified_id,
            property_id,
            name,
            prop.get("address", ""),
            prop.get("city", ""),
            prop.get("state", ""),
            datetime.now().isoformat()
        ))
        count += 1
    
    uni_conn.commit()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} properties")
    return count


async def sync_occupancy(client: YardiClient):
    """Sync occupancy metrics from Yardi API to unified."""
    print("\n📊 Syncing Yardi occupancy metrics...")
    
    uni_conn = get_unified_conn()
    uni_cursor = uni_conn.cursor()
    
    # Get Yardi properties from unified
    uni_cursor.execute("""
        SELECT unified_property_id, pms_property_id 
        FROM unified_properties 
        WHERE pms_source = 'yardi'
    """)
    properties = uni_cursor.fetchall()
    
    count = 0
    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    
    for unified_id, yardi_property_id in properties:
        try:
            # Get units from Yardi API
            units = await client.get_units(yardi_property_id)
            
            if not units:
                print(f"  ⚠️ No units for {unified_id}")
                continue
            
            # Calculate metrics
            total_units = len(units)
            occupied_units = sum(1 for u in units if u.get("status") == "occupied")
            vacant_units = sum(1 for u in units if u.get("status") == "vacant")
            notice_units = sum(1 for u in units if u.get("status") == "notice")
            model_units = sum(1 for u in units if u.get("status") == "model")
            down_units = sum(1 for u in units if u.get("status") == "down")
            
            leased_units = occupied_units + notice_units
            preleased_vacant = 0  # Would need future resident data
            
            physical_occupancy = round(occupied_units / total_units * 100, 2) if total_units > 0 else 0
            leased_percentage = round(leased_units / total_units * 100, 2) if total_units > 0 else 0
            
            uni_cursor.execute("""
                INSERT OR REPLACE INTO unified_occupancy_metrics
                (unified_property_id, snapshot_date, total_units, occupied_units, vacant_units,
                 leased_units, preleased_vacant, notice_units, model_units, down_units,
                 physical_occupancy, leased_percentage, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                unified_id, snapshot_date, total_units, occupied_units, vacant_units,
                leased_units, preleased_vacant, notice_units, model_units, down_units,
                physical_occupancy, leased_percentage, datetime.now().isoformat()
            ))
            count += 1
            print(f"  ✅ {unified_id}: {total_units} units, {physical_occupancy}% occupied")
            
        except Exception as e:
            print(f"  ❌ Error syncing {unified_id}: {e}")
    
    uni_conn.commit()
    uni_conn.close()
    
    print(f"  ✅ Synced occupancy for {count} properties")
    return count


async def sync_pricing(client: YardiClient):
    """Sync pricing metrics from Yardi API to unified."""
    print("\n💰 Syncing Yardi pricing metrics...")
    
    uni_conn = get_unified_conn()
    uni_cursor = uni_conn.cursor()
    
    # Get Yardi properties from unified
    uni_cursor.execute("""
        SELECT unified_property_id, pms_property_id 
        FROM unified_properties 
        WHERE pms_source = 'yardi'
    """)
    properties = uni_cursor.fetchall()
    
    count = 0
    snapshot_date = datetime.now().strftime("%Y-%m-%d")
    
    for unified_id, yardi_property_id in properties:
        try:
            # Get units with pricing
            units = await client.get_units(yardi_property_id)
            
            if not units:
                continue
            
            # Get lease charges for in-place rents
            try:
                leases = await client.get_lease_data(yardi_property_id)
                lease_rents = {l["unit_id"]: l["rent_amount"] for l in leases}
            except Exception:
                lease_rents = {}
            
            # Group by floorplan
            floorplans = {}
            for unit in units:
                fp = unit.get("floorplan", "Unknown")
                if fp not in floorplans:
                    floorplans[fp] = {
                        "units": 0,
                        "market_rents": [],
                        "in_place_rents": [],
                        "sqft": []
                    }
                
                floorplans[fp]["units"] += 1
                
                if unit.get("market_rent", 0) > 0:
                    floorplans[fp]["market_rents"].append(unit["market_rent"])
                
                if unit.get("square_feet", 0) > 0:
                    floorplans[fp]["sqft"].append(unit["square_feet"])
                
                # Get in-place rent from lease charges
                unit_id = unit.get("unit_id")
                if unit_id in lease_rents and lease_rents[unit_id] > 0:
                    floorplans[fp]["in_place_rents"].append(lease_rents[unit_id])
            
            # Insert pricing by floorplan
            for floorplan, data in floorplans.items():
                avg_market = sum(data["market_rents"]) / len(data["market_rents"]) if data["market_rents"] else 0
                avg_in_place = sum(data["in_place_rents"]) / len(data["in_place_rents"]) if data["in_place_rents"] else 0
                avg_sqft = sum(data["sqft"]) / len(data["sqft"]) if data["sqft"] else 0
                
                uni_cursor.execute("""
                    INSERT OR REPLACE INTO unified_pricing_metrics
                    (unified_property_id, snapshot_date, floorplan, unit_count,
                     avg_sqft, avg_market_rent, avg_in_place_rent, synced_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    unified_id, snapshot_date, floorplan, data["units"],
                    round(avg_sqft, 0), round(avg_market, 2), round(avg_in_place, 2),
                    datetime.now().isoformat()
                ))
                count += 1
            
            print(f"  ✅ {unified_id}: {len(floorplans)} floorplans")
            
        except Exception as e:
            print(f"  ❌ Error syncing pricing for {unified_id}: {e}")
    
    uni_conn.commit()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} pricing records")
    return count


async def sync_units(client: YardiClient):
    """Sync unit data from Yardi API to unified."""
    print("\n🏠 Syncing Yardi units...")
    
    uni_conn = get_unified_conn()
    uni_cursor = uni_conn.cursor()
    
    # Get Yardi properties from unified
    uni_cursor.execute("""
        SELECT unified_property_id, pms_property_id 
        FROM unified_properties 
        WHERE pms_source = 'yardi'
    """)
    properties = uni_cursor.fetchall()
    
    count = 0
    
    for unified_id, yardi_property_id in properties:
        try:
            units = await client.get_units(yardi_property_id)
            
            for unit in units:
                uni_cursor.execute("""
                    INSERT OR REPLACE INTO unified_units
                    (unified_property_id, unit_number, floorplan, bedrooms, bathrooms,
                     square_feet, market_rent, status, synced_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    unified_id,
                    unit.get("unit_number", ""),
                    unit.get("floorplan", ""),
                    unit.get("bedrooms", 0),
                    unit.get("bathrooms", 0),
                    unit.get("square_feet", 0),
                    unit.get("market_rent", 0),
                    unit.get("status", ""),
                    datetime.now().isoformat()
                ))
                count += 1
            
            print(f"  ✅ {unified_id}: {len(units)} units")
            
        except Exception as e:
            print(f"  ❌ Error syncing units for {unified_id}: {e}")
    
    uni_conn.commit()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} units")
    return count


async def sync_residents(client: YardiClient):
    """Sync resident data from Yardi API to unified."""
    print("\n👥 Syncing Yardi residents...")
    
    uni_conn = get_unified_conn()
    uni_cursor = uni_conn.cursor()
    
    # Get Yardi properties from unified
    uni_cursor.execute("""
        SELECT unified_property_id, pms_property_id 
        FROM unified_properties 
        WHERE pms_source = 'yardi'
    """)
    properties = uni_cursor.fetchall()
    
    count = 0
    
    for unified_id, yardi_property_id in properties:
        try:
            # Get all residents (current, future, notice)
            residents = await client.get_residents(yardi_property_id, "all")
            
            for res in residents:
                uni_cursor.execute("""
                    INSERT OR REPLACE INTO unified_residents
                    (unified_property_id, unit_number, resident_name, status,
                     current_rent, lease_start, lease_end, move_in_date, move_out_date, synced_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    unified_id,
                    res.get("unit_number", ""),
                    f"{res.get('first_name', '')} {res.get('last_name', '')}".strip(),
                    res.get("status", ""),
                    res.get("current_rent", 0),
                    res.get("lease_start"),
                    res.get("lease_end"),
                    res.get("move_in_date"),
                    res.get("move_out_date"),
                    datetime.now().isoformat()
                ))
                count += 1
            
            print(f"  ✅ {unified_id}: {len(residents)} residents")
            
        except Exception as e:
            print(f"  ❌ Error syncing residents for {unified_id}: {e}")
    
    uni_conn.commit()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} residents")
    return count


def log_sync(property_count: int, occupancy_count: int, pricing_count: int, 
             unit_count: int, resident_count: int):
    """Log sync results."""
    uni_conn = get_unified_conn()
    uni_cursor = uni_conn.cursor()
    
    uni_cursor.execute("""
        INSERT INTO unified_sync_log
        (unified_property_id, pms_source, sync_type, tables_synced, records_synced,
         sync_started_at, sync_completed_at, status)
        VALUES (?, 'yardi', 'full', ?, ?, ?, ?, 'success')
    """, (
        'all_yardi_properties',
        '["unified_properties", "unified_occupancy_metrics", "unified_pricing_metrics", "unified_units", "unified_residents"]',
        property_count + occupancy_count + pricing_count + unit_count + resident_count,
        datetime.now().isoformat(),
        datetime.now().isoformat()
    ))
    
    uni_conn.commit()
    uni_conn.close()


async def run_full_sync():
    """Run full sync from Yardi API to unified database."""
    print("=" * 60)
    print("🔄 YARDI → UNIFIED DATABASE SYNC")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Initialize Yardi client
    client = YardiClient()
    
    # Run all sync operations
    property_count = await sync_properties(client)
    occupancy_count = await sync_occupancy(client)
    pricing_count = await sync_pricing(client)
    unit_count = await sync_units(client)
    resident_count = await sync_residents(client)
    
    # Log sync
    log_sync(property_count, occupancy_count, pricing_count, unit_count, resident_count)
    
    print("\n" + "=" * 60)
    print("✅ SYNC COMPLETE")
    print("=" * 60)
    print(f"Properties: {property_count}")
    print(f"Occupancy records: {occupancy_count}")
    print(f"Pricing records: {pricing_count}")
    print(f"Units: {unit_count}")
    print(f"Residents: {resident_count}")
    print(f"Completed at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    asyncio.run(run_full_sync())
