"""
Pull ALL available data from RealPage SOAP API for ALL Kairoi properties.

Flow:
1. Loop through all 18 Kairoi properties
2. For each: pull units, residents, leases, rentable items via SOAP API
3. Store in realpage_raw.db (clearing old API data per site first)
4. Run full sync to unified.db

READ-ONLY: Only GET operations against RealPage API.
"""

import asyncio
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.clients.realpage_client import RealPageClient
from app.db.schema import REALPAGE_DB_PATH, REALPAGE_SCHEMA, init_database
from app.config import get_settings

# All Kairoi properties: unified_id -> site_id
# These match the ALL_PROPERTIES in app/property_config/properties.py
KAIROI_PROPERTIES = {
    "7_east":              {"site_id": "5481703", "name": "7 East"},
    "aspire_7th_grant":    {"site_id": "4779341", "name": "Aspire 7th and Grant"},
    "block_44":            {"site_id": "5473254", "name": "Block 44"},
    "broadleaf":           {"site_id": "5286092", "name": "The Broadleaf"},
    "confluence":          {"site_id": "4832865", "name": "The Confluence"},
    "curate":              {"site_id": "4682517", "name": "Curate at Orchard Town Center"},
    "discovery_kingwood":  {"site_id": "5618425", "name": "Discovery at Kingwood"},
    "eden_keller_ranch":   {"site_id": "5536209", "name": "Eden Keller Ranch"},
    "edison_rino":         {"site_id": "4248319", "name": "Edison at RiNo"},
    "harvest":             {"site_id": "5507303", "name": "Harvest"},
    "heights_interlocken": {"site_id": "5558216", "name": "Heights at Interlocken"},
    "izzy":                {"site_id": "5618432", "name": "Izzy"},
    "kalaco":              {"site_id": "5339721", "name": "Kalaco"},
    "links_plum_creek":    {"site_id": "5558220", "name": "The Links at Plum Creek"},
    "luna":                {"site_id": "5590740", "name": "Luna"},
    "nexus_east":          {"site_id": "5472172", "name": "Nexus East"},
    "park_17":             {"site_id": "4481243", "name": "Park 17"},
    "parkside":            {"site_id": "5536211", "name": "Parkside at Round Rock"},
    "pearl_lantana":       {"site_id": "5481704", "name": "Pearl Lantana"},
    "ridian":              {"site_id": "5446271", "name": "Ridian"},
    "slate":               {"site_id": "5486880", "name": "Slate"},
    "sloane":              {"site_id": "5486881", "name": "Sloane"},
    "station_riverfront":  {"site_id": "4976258", "name": "The Station at Riverfront Park"},
    "stonewood":           {"site_id": "5481705", "name": "Stonewood"},
    "ten50":               {"site_id": "5581218", "name": "Ten50"},
    "the_alcott":          {"site_id": "4996967", "name": "The Alcott"},
    "the_avant":           {"site_id": "5480255", "name": "The Avant"},
    "the_hunter":          {"site_id": "5558217", "name": "The Hunter"},
    "the_northern":        {"site_id": "5375283", "name": "The Northern"},
    "thepearl":            {"site_id": "5114464", "name": "thePearl"},
    "thequinci":           {"site_id": "5286878", "name": "theQuinci"},
}

PMC_ID = "4248314"


def clear_api_data_for_site(conn, site_id: str):
    """Clear existing SOAP API data for a site (not report data)."""
    cursor = conn.cursor()
    # Only clear API tables, NOT report tables (box_score, rent_roll, etc.)
    api_tables = [
        "realpage_units",
        "realpage_residents", 
        "realpage_leases",
        "realpage_rentable_items",
    ]
    for table in api_tables:
        cursor.execute(f"DELETE FROM {table} WHERE site_id = ?", (site_id,))
    conn.commit()


async def pull_property(conn, site_id: str, prop_name: str):
    """Pull all SOAP API data for a single property."""
    settings = get_settings()
    client = RealPageClient(
        url=settings.realpage_url,
        pmcid=PMC_ID,
        siteid=site_id,
        licensekey=settings.realpage_licensekey,
    )
    
    if not client.url or not client.licensekey:
        print(f"  ❌ RealPage credentials not configured")
        return {"units": 0, "residents": 0, "leases": 0, "rentable_items": 0, "error": "No credentials"}
    
    cursor = conn.cursor()
    results = {"units": 0, "residents": 0, "leases": 0, "rentable_items": 0}
    
    # 1. Units
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
                PMC_ID, site_id,
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
        results["units"] = len(units)
        print(f"    Units: {len(units)}")
    except Exception as e:
        print(f"    Units: ❌ {e}")
    
    # 2. Residents
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
                PMC_ID, site_id,
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
        results["residents"] = len(residents)
        print(f"    Residents: {len(residents)}")
    except Exception as e:
        print(f"    Residents: ❌ {e}")
    
    # 3. Leases
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
                PMC_ID, site_id,
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
        results["leases"] = len(leases)
        print(f"    Leases: {len(leases)}")
    except Exception as e:
        print(f"    Leases: ❌ {e}")
    
    # 4. Rentable Items
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
                PMC_ID, site_id,
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
        results["rentable_items"] = len(items)
        print(f"    Rentable Items: {len(items)}")
    except Exception as e:
        print(f"    Rentable Items: ❌ {e}")
    
    conn.commit()
    return results


async def pull_all_properties():
    """Pull SOAP API data for all Kairoi properties."""
    print("=" * 70)
    print("RealPage SOAP API Extraction - ALL Properties")
    print("=" * 70)
    print(f"Properties to pull: {len(KAIROI_PROPERTIES)}")
    print(f"PMC ID: {PMC_ID}")
    print()
    
    # Initialize database if needed
    if not REALPAGE_DB_PATH.exists():
        init_database(REALPAGE_DB_PATH, REALPAGE_SCHEMA)
    
    conn = sqlite3.connect(REALPAGE_DB_PATH)
    
    totals = {"units": 0, "residents": 0, "leases": 0, "rentable_items": 0}
    errors = []
    
    for unified_id, info in KAIROI_PROPERTIES.items():
        site_id = info["site_id"]
        name = info["name"]
        
        print(f"\n🏢 [{unified_id}] {name} (site: {site_id})")
        
        # Clear old API data for this site
        clear_api_data_for_site(conn, site_id)
        
        try:
            results = await pull_property(conn, site_id, name)
            for key in totals:
                totals[key] += results.get(key, 0)
            if results.get("error"):
                errors.append(f"{name}: {results['error']}")
        except Exception as e:
            print(f"  ❌ FAILED: {e}")
            errors.append(f"{name}: {e}")
    
    conn.close()
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 EXTRACTION SUMMARY")
    print("=" * 70)
    print(f"  Properties processed: {len(KAIROI_PROPERTIES)}")
    print(f"  Units:           {totals['units']:,}")
    print(f"  Residents:       {totals['residents']:,}")
    print(f"  Leases:          {totals['leases']:,}")
    print(f"  Rentable Items:  {totals['rentable_items']:,}")
    
    if errors:
        print(f"\n⚠️ Errors ({len(errors)}):")
        for err in errors:
            print(f"  - {err}")
    
    print(f"\n✅ Data saved to: {REALPAGE_DB_PATH}")
    return totals


def run_sync():
    """Run the sync from realpage_raw.db to unified.db."""
    print("\n" + "=" * 70)
    print("🔄 Syncing to Unified Database")
    print("=" * 70)
    
    from app.db.sync_realpage_to_unified import (
        sync_properties,
        sync_occupancy_metrics,
        sync_pricing_metrics,
        sync_delinquency,
        sync_units_from_rent_roll,
        sync_residents_from_rent_roll,
    )
    
    sync_properties()
    sync_occupancy_metrics()
    sync_pricing_metrics()
    sync_delinquency()
    sync_units_from_rent_roll()
    sync_residents_from_rent_roll()
    
    print("\n✅ Sync complete!")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Pull RealPage SOAP API data for all properties")
    parser.add_argument("--skip-sync", action="store_true", help="Skip unified DB sync after extraction")
    parser.add_argument("--only", type=str, help="Only pull for specific property (unified_id)")
    args = parser.parse_args()
    
    if args.only:
        if args.only not in KAIROI_PROPERTIES:
            print(f"❌ Unknown property: {args.only}")
            print(f"Available: {', '.join(sorted(KAIROI_PROPERTIES.keys()))}")
            sys.exit(1)
        # Filter to just this one
        KAIROI_PROPERTIES_FILTERED = {args.only: KAIROI_PROPERTIES[args.only]}
        # Monkey-patch for single property
        import pull_all_api_data
        pull_all_api_data.KAIROI_PROPERTIES = KAIROI_PROPERTIES_FILTERED
    
    # Pull API data
    asyncio.run(pull_all_properties())
    
    # Sync to unified
    if not args.skip_sync:
        run_sync()
