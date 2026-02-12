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
    "5481703": {"unified_id": "7_east", "name": "7 East"},
    "4779341": {"unified_id": "aspire_7th_grant", "name": "Aspire 7th and Grant"},
    "5473254": {"unified_id": "block_44", "name": "Block 44"},
    "5286092": {"unified_id": "broadleaf", "name": "The Broadleaf"},
    "4832865": {"unified_id": "confluence", "name": "The Confluence"},
    "4682517": {"unified_id": "curate", "name": "Curate at Orchard Town Center"},
    "5618425": {"unified_id": "discovery_kingwood", "name": "Discovery at Kingwood"},
    "5536209": {"unified_id": "eden_keller_ranch", "name": "Eden Keller Ranch"},
    "4248319": {"unified_id": "edison_rino", "name": "Edison at RiNo"},
    "5507303": {"unified_id": "harvest", "name": "Harvest"},
    "5558216": {"unified_id": "heights_interlocken", "name": "Heights at Interlocken"},
    "5618432": {"unified_id": "izzy", "name": "Izzy"},
    "5339721": {"unified_id": "kalaco", "name": "Kalaco"},
    "5558220": {"unified_id": "links_plum_creek", "name": "The Links at Plum Creek"},
    "5590740": {"unified_id": "luna", "name": "Luna"},
    "5472172": {"unified_id": "nexus_east", "name": "Nexus East"},
    "4481243": {"unified_id": "park_17", "name": "Park 17"},
    "5536211": {"unified_id": "parkside", "name": "Parkside at Round Rock"},
    "5481704": {"unified_id": "pearl_lantana", "name": "Pearl Lantana"},
    "5446271": {"unified_id": "ridian", "name": "Ridian"},
    "5486880": {"unified_id": "slate", "name": "Slate"},
    "5486881": {"unified_id": "sloane", "name": "Sloane"},
    "4976258": {"unified_id": "station_riverfront", "name": "The Station at Riverfront Park"},
    "5481705": {"unified_id": "stonewood", "name": "Stonewood"},
    "5581218": {"unified_id": "ten50", "name": "Ten50"},
    "4996967": {"unified_id": "the_alcott", "name": "The Alcott"},
    "5480255": {"unified_id": "the_avant", "name": "The Avant"},
    "5558217": {"unified_id": "the_hunter", "name": "The Hunter"},
    "5375283": {"unified_id": "the_northern", "name": "The Northern"},
    "5114464": {"unified_id": "thepearl", "name": "thePearl"},
    "5286878": {"unified_id": "thequinci", "name": "theQuinci"},
}

# Owner group assignments: unified_property_id -> owner_group
OWNER_GROUPS = {
    "nexus_east": "PHH",
    "parkside": "PHH",
}

def get_owner_group(unified_id: str) -> str:
    """Get owner group for a property. Defaults to 'other'."""
    return OWNER_GROUPS.get(unified_id, "other")


def get_realpage_conn():
    """Get connection to realpage_raw.db."""
    return sqlite3.connect(REALPAGE_DB_PATH)


def get_unified_conn():
    """Get connection to unified.db."""
    return sqlite3.connect(UNIFIED_DB_PATH)


def sync_properties():
    """Sync properties from RealPage to unified.
    Sources: box_score, rent_roll, and realpage_units (API data)."""
    print("\n📍 Syncing properties...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    # Gather property_ids from all sources
    seen_ids = set()
    for table in ['realpage_box_score', 'realpage_rent_roll', 'realpage_units']:
        try:
            col = 'site_id' if table == 'realpage_units' else 'property_id'
            rp_cursor.execute(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL")
            for row in rp_cursor.fetchall():
                seen_ids.add(row[0])
        except Exception:
            pass
    
    # Ensure owner_group column exists
    try:
        uni_cursor.execute("ALTER TABLE unified_properties ADD COLUMN owner_group TEXT DEFAULT 'other'")
    except Exception:
        pass  # Column already exists
    
    count = 0
    for property_id in seen_ids:
        if property_id not in PROPERTY_MAPPING:
            continue
        mapping = PROPERTY_MAPPING[property_id]
        unified_id = mapping["unified_id"]
        name = mapping["name"]
        owner_group = get_owner_group(unified_id)
        uni_cursor.execute("""
            INSERT OR REPLACE INTO unified_properties
            (unified_property_id, pms_source, pms_property_id, name, owner_group, synced_at)
            VALUES (?, 'realpage', ?, ?, ?, ?)
        """, (unified_id, property_id, name, owner_group, datetime.now().isoformat()))
        count += 1
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} properties")
    return count


def sync_occupancy_metrics():
    """Sync occupancy metrics from box_score + API fallback to unified."""
    print("\n📊 Syncing occupancy metrics...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    # Ensure new columns exist (migration for existing DBs)
    for col in ['notice_break_units', 'vacant_ready', 'vacant_not_ready']:
        try:
            uni_cursor.execute(f"ALTER TABLE unified_occupancy_metrics ADD COLUMN {col} INTEGER DEFAULT 0")
        except Exception:
            pass
    uni_conn.commit()
    
    # --- Build lookups from API + rent roll for vacant_ready and notice_break ---
    # Vacant ready/not-ready: from realpage_units API available flag
    # {property_id: {"vacant_ready": N, "vacant_not_ready": N}}
    api_vacancy = {}
    rp_cursor.execute("""
        SELECT site_id,
            SUM(CASE WHEN vacant = 'T' AND available = 'T' THEN 1 ELSE 0 END) as vacant_ready,
            SUM(CASE WHEN vacant = 'T' AND available = 'F' THEN 1 ELSE 0 END) as vacant_not_avail
        FROM realpage_units
        WHERE site_id IS NOT NULL
        GROUP BY site_id
    """)
    for arow in rp_cursor.fetchall():
        api_vacancy[arow[0]] = {"vacant_ready": arow[1] or 0, "vacant_not_avail": arow[2] or 0}
    
    # Notice break detection: compare rent_roll lease_end with API available_date for NTV units
    # {property_id: notice_break_count}
    notice_breaks = {}
    # Get NTV units from latest rent roll
    rp_cursor.execute("""
        SELECT rr.property_id, rr.unit_number, rr.lease_end
        FROM realpage_rent_roll rr
        INNER JOIN (
            SELECT property_id, unit_number, MAX(imported_at) as max_imported
            FROM realpage_rent_roll
            WHERE status = 'Occupied-NTV'
            GROUP BY property_id, unit_number
        ) latest ON rr.property_id = latest.property_id 
            AND rr.unit_number = latest.unit_number 
            AND rr.imported_at = latest.max_imported
        WHERE rr.status = 'Occupied-NTV'
    """)
    ntv_units = {}  # (property_id, unit_number) -> lease_end
    for nrow in rp_cursor.fetchall():
        ntv_units[(nrow[0], nrow[1])] = nrow[2]  # lease_end string like "03/14/2026"
    
    # Get available_date from API for NTV units
    rp_cursor.execute("""
        SELECT site_id, unit_number, available_date
        FROM realpage_units
        WHERE available = 'T' AND vacant = 'F'
    """)
    for arow in rp_cursor.fetchall():
        site_id, unit_num, avail_date = arow[0], arow[1], arow[2]
        lease_end = ntv_units.get((site_id, unit_num))
        if lease_end and avail_date:
            try:
                # Parse dates: lease_end is MM/DD/YYYY, avail_date is YYYY-MM-DD HH:MM:SS
                from datetime import datetime as dt
                le = dt.strptime(lease_end.strip(), "%m/%d/%Y")
                ad = dt.strptime(avail_date.strip()[:10], "%Y-%m-%d")
                # If available_date is > 30 days before lease_end, it's a break
                if (le - ad).days > 30:
                    notice_breaks[site_id] = notice_breaks.get(site_id, 0) + 1
            except (ValueError, TypeError):
                pass
    
    count = 0
    seen = set()
    
    # 1. Box score data (most accurate, from reports)
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
    
    for row in rp_cursor.fetchall():
        property_id = row[0]
        report_date = row[1]
        
        if property_id in seen or property_id not in PROPERTY_MAPPING:
            continue
        seen.add(property_id)
        
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
        
        exposure_30 = max(0, vacant_units + int(notice_units * 0.5) - preleased_vacant)
        exposure_60 = max(0, vacant_units + notice_units - preleased_vacant)
        
        # Compute vacant_ready/not_ready from API data
        api_data = api_vacancy.get(property_id, {})
        vacant_ready = api_data.get("vacant_ready", 0)
        # vacant_not_ready = total vacant (box score) minus vacant_ready minus preleased minus model/down
        # The API "vacant_not_avail" includes preleased units, so derive from box score totals
        vacant_not_leased = vacant_units - preleased_vacant - model_units
        vacant_not_ready = max(0, vacant_not_leased - vacant_ready)
        
        # Notice break count
        notice_break = notice_breaks.get(property_id, 0)
        
        uni_cursor.execute("""
            INSERT OR REPLACE INTO unified_occupancy_metrics
            (unified_property_id, snapshot_date, total_units, occupied_units, vacant_units,
             leased_units, preleased_vacant, notice_units, notice_break_units, model_units, down_units,
             vacant_ready, vacant_not_ready,
             physical_occupancy, leased_percentage, exposure_30_days, exposure_60_days, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unified_id, report_date, total_units, occupied_units, vacant_units,
            leased_units, preleased_vacant, notice_units, notice_break, model_units, down_units,
            vacant_ready, vacant_not_ready,
            round(physical_occupancy, 2), round(leased_percentage, 2),
            exposure_30, exposure_60,
            datetime.now().isoformat()
        ))
        count += 1
        print(f"  {PROPERTY_MAPPING[property_id]['name']}: {physical_occupancy:.1f}% occupied ({occupied_units}/{total_units}), vac_ready={vacant_ready}, notice_break={notice_break}")
    
    # 2. Fallback: API data (realpage_units) for properties without box_score
    rp_cursor.execute("""
        SELECT site_id,
            COUNT(*) as total_units,
            SUM(CASE WHEN vacant = 'F' THEN 1 ELSE 0 END) as occupied,
            SUM(CASE WHEN vacant = 'T' THEN 1 ELSE 0 END) as vacant,
            SUM(CASE WHEN available = 'T' AND vacant = 'F' THEN 1 ELSE 0 END) as on_notice
        FROM realpage_units
        WHERE site_id IS NOT NULL
        GROUP BY site_id
    """)
    
    today = datetime.now().strftime("%m/%d/%Y")
    for row in rp_cursor.fetchall():
        site_id = row[0]
        if site_id in seen or site_id not in PROPERTY_MAPPING:
            continue
        seen.add(site_id)
        
        unified_id = PROPERTY_MAPPING[site_id]["unified_id"]
        total_units = row[1] or 0
        occupied_units = row[2] or 0
        vacant_units = row[3] or 0
        notice_units = row[4] or 0
        
        leased_units = occupied_units
        physical_occupancy = (occupied_units / total_units * 100) if total_units > 0 else 0
        leased_percentage = physical_occupancy  # Approximate without box_score
        
        exposure_30 = max(0, vacant_units + int(notice_units * 0.5))
        exposure_60 = max(0, vacant_units + notice_units)
        
        # Vacant ready/not-ready from API data
        api_data = api_vacancy.get(site_id, {})
        vacant_ready = api_data.get("vacant_ready", 0)
        vacant_not_ready = max(0, vacant_units - vacant_ready)
        notice_break = notice_breaks.get(site_id, 0)
        
        uni_cursor.execute("""
            INSERT OR REPLACE INTO unified_occupancy_metrics
            (unified_property_id, snapshot_date, total_units, occupied_units, vacant_units,
             leased_units, preleased_vacant, notice_units, notice_break_units, model_units, down_units,
             vacant_ready, vacant_not_ready,
             physical_occupancy, leased_percentage, exposure_30_days, exposure_60_days, calculated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unified_id, today, total_units, occupied_units, vacant_units,
            leased_units, 0, notice_units, notice_break, 0, 0,
            vacant_ready, vacant_not_ready,
            round(physical_occupancy, 2), round(leased_percentage, 2),
            exposure_30, exposure_60,
            datetime.now().isoformat()
        ))
        count += 1
        print(f"  {PROPERTY_MAPPING[site_id]['name']}: {physical_occupancy:.1f}% occupied ({occupied_units}/{total_units}) [API]")
    
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
        status_raw = (row[7] or "").lower().strip()
        
        # Skip junk rows: header rows ("unit/lease status") and empty/null statuses
        if not status_raw or "unit/lease" in status_raw or "status" in status_raw:
            continue
        
        # Map status from rent_roll status field
        if "occupied" in status_raw:
            status = "occupied"
        elif "vacant" in status_raw:
            status = "vacant"
        elif "notice" in status_raw:
            status = "notice"
        elif "model" in status_raw:
            status = "model"
        elif "down" in status_raw or "admin" in status_raw:
            status = "down"
        else:
            continue  # Skip any other unrecognized status
        
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
    
    # --- Enrich unified_units with API data (made_ready_date, available_date, available) ---
    # The rent roll report doesn't include these fields, but realpage_units (API) does
    print("  📡 Enriching units with API data (made_ready_date, available)...")
    enriched = 0
    
    # Build lookup: (property_id, unit_number) -> API fields
    rp_cursor.execute("""
        SELECT site_id, unit_number, made_ready_date, available_date, available, 
               on_notice_date, vacant, exclude_from_occupancy
        FROM realpage_units
        WHERE site_id IS NOT NULL
    """)
    api_lookup = {}
    for arow in rp_cursor.fetchall():
        site_id = arow[0]
        unit_num = arow[1]
        api_lookup[(site_id, unit_num)] = {
            "made_ready_date": arow[2],
            "available_date": arow[3],
            "available": arow[4],  # 'T' or 'F'
            "on_notice_date": arow[5],
            "vacant": arow[6],  # 'T' or 'F'
            "excluded": arow[7],
        }
    
    uni_cursor_r = uni_conn.cursor()
    for property_id, mapping in PROPERTY_MAPPING.items():
        unified_id = mapping["unified_id"]
        # Get all units for this property in unified_units
        uni_cursor_r.execute(
            "SELECT pms_unit_id FROM unified_units WHERE unified_property_id = ?",
            (unified_id,)
        )
        for (unit_num,) in uni_cursor_r.fetchall():
            api_data = api_lookup.get((property_id, unit_num))
            if api_data:
                made_ready = api_data["made_ready_date"] or None
                avail_date = api_data["available_date"] or None
                on_notice = api_data["on_notice_date"] or None
                # available = 'T' means vacant + ready (can be shown/leased)
                is_available = 1 if api_data["available"] == "T" else 0
                is_excluded = 1 if api_data.get("excluded") in (1, "1", "True", True) else 0
                
                # Set occupancy_status based on API available flag for vacant units
                # available = 'T' means "vacant + ready to lease" in RealPage
                occupancy_status = None
                if api_data["vacant"] == "T":
                    occupancy_status = "vacant_ready" if api_data["available"] == "T" else "vacant_not_ready"
                
                uni_cursor.execute("""
                    UPDATE unified_units 
                    SET made_ready_date = ?, available_date = ?, on_notice_date = ?,
                        excluded_from_occupancy = ?,
                        occupancy_status = COALESCE(?, occupancy_status)
                    WHERE unified_property_id = ? AND pms_unit_id = ?
                """, (made_ready, avail_date, on_notice, is_excluded, occupancy_status, unified_id, unit_num))
                if uni_cursor.rowcount > 0:
                    enriched += 1
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} units, enriched {enriched} with API data")
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
    """Sync delinquency data from realpage_delinquency to unified.
    Cross-references realpage_leases evict flag for eviction status."""
    print("\n💸 Syncing delinquency data...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    # Create delinquency table in unified if not exists (with is_eviction column)
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
            total_delinquent REAL,
            net_balance REAL,
            is_eviction INTEGER DEFAULT 0,
            eviction_balance REAL DEFAULT 0,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Add is_eviction column if missing (for existing DBs)
    for col_stmt in [
        "ALTER TABLE unified_delinquency ADD COLUMN is_eviction INTEGER DEFAULT 0",
        "ALTER TABLE unified_delinquency ADD COLUMN eviction_balance REAL DEFAULT 0",
        "ALTER TABLE unified_delinquency ADD COLUMN total_delinquent REAL DEFAULT 0",
    ]:
        try:
            uni_cursor.execute(col_stmt)
        except Exception:
            pass
    
    # Clear existing delinquency data
    uni_cursor.execute("DELETE FROM unified_delinquency")
    
    # Build eviction lookup from realpage_leases (RPX SOAP API getLeaseInfo → Evict flag)
    # Leases have unit_id but empty unit_number, so we map via realpage_units
    eviction_units = set()  # (site_id, unit_number) pairs with evict='Y'
    eviction_balances = {}  # (site_id, unit_number) -> current_balance from lease
    try:
        # First build unit_id -> unit_number mapping from realpage_units
        unit_id_to_number = {}  # (site_id, unit_id) -> unit_number
        rp_cursor.execute("SELECT site_id, unit_id, unit_number FROM realpage_units WHERE site_id IS NOT NULL")
        for urow in rp_cursor.fetchall():
            unit_id_to_number[(urow[0], urow[1])] = urow[2] or ''
        
        # Now get eviction-flagged leases and resolve unit numbers
        rp_cursor.execute("""
            SELECT site_id, unit_id, unit_number, current_balance
            FROM realpage_leases
            WHERE evict = 'Y' AND site_id IS NOT NULL
        """)
        for erow in rp_cursor.fetchall():
            site_id = erow[0]
            unit_id = erow[1] or ''
            unit_num = erow[2] or ''
            balance = erow[3] or 0
            
            # Resolve unit_number from unit_id if empty
            if not unit_num and unit_id:
                unit_num = unit_id_to_number.get((site_id, unit_id), '')
            
            if unit_num:
                eviction_units.add((site_id, unit_num))
                eviction_balances[(site_id, unit_num)] = balance
        print(f"  📋 Found {len(eviction_units)} eviction-flagged leases from RPX API")
    except Exception as e:
        print(f"  ⚠️  Could not load eviction data from leases: {e}")
    
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
            net_balance,
            total_delinquent
        FROM realpage_delinquency
        WHERE property_id IS NOT NULL
        ORDER BY property_id, report_date DESC
    """)
    
    count = 0
    eviction_count = 0
    seen = set()
    
    for row in rp_cursor.fetchall():
        property_id = row[0]
        unit_number = row[2] or ''
        
        key = (property_id, unit_number)
        if key in seen:
            continue
        seen.add(key)
        
        if property_id not in PROPERTY_MAPPING:
            continue
        
        unified_id = PROPERTY_MAPPING[property_id]["unified_id"]
        
        # Check eviction status from lease data
        is_eviction = 1 if (property_id, unit_number) in eviction_units else 0
        evict_bal = eviction_balances.get((property_id, unit_number), 0) if is_eviction else 0
        if is_eviction:
            eviction_count += 1
        
        uni_cursor.execute("""
            INSERT INTO unified_delinquency
            (unified_property_id, report_date, unit_number, resident_name, status,
             current_balance, balance_0_30, balance_31_60, balance_61_90,
             balance_over_90, prepaid, net_balance, total_delinquent,
             is_eviction, eviction_balance, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unified_id, row[1], row[2], row[3], row[4] or '',
            row[5] or 0, row[6] or 0, row[7] or 0, row[8] or 0,
            row[9] or 0, row[10] or 0, row[11] or 0, row[12] or 0,
            is_eviction, evict_bal,
            datetime.now().isoformat()
        ))
        count += 1
    
    uni_conn.commit()
    
    # Summary by property
    uni_cursor.execute("""
        SELECT unified_property_id, COUNT(*), 
               SUM(CASE WHEN balance_0_30 > 0 THEN balance_0_30 ELSE 0 END) as total_30,
               SUM(CASE WHEN net_balance > 0 THEN net_balance ELSE 0 END) as total_net,
               SUM(is_eviction) as evictions,
               SUM(CASE WHEN is_eviction = 1 THEN eviction_balance ELSE 0 END) as evict_bal
        FROM unified_delinquency
        GROUP BY unified_property_id
    """)
    for r in uni_cursor.fetchall():
        evict_str = f", evictions: {r[4]} (${r[5]:,.2f})" if r[4] > 0 else ""
        print(f"  {r[0]}: {r[1]} units, 30-day: ${r[2]:,.2f}, net: ${r[3]:,.2f}{evict_str}")
    
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} delinquency records ({eviction_count} with eviction flag)")
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
