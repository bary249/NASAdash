"""
Sync RealPage report data to Unified database.

This script reads from realpage_raw.db (box_score, rent_roll, delinquency tables)
and populates the unified.db tables for dashboard display.
"""
import sqlite3
from datetime import datetime
from pathlib import Path

from app.db.schema import REALPAGE_DB_PATH, UNIFIED_DB_PATH

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
    "7_east": "Kairoi",
    "aspire_7th_grant": "Kairoi",
    "block_44": "Kairoi",
    "broadleaf": "Kairoi",
    "confluence": "Kairoi",
    "curate": "Kairoi",
    "discovery_kingwood": "Kairoi",
    "eden_keller_ranch": "Kairoi",
    "edison_rino": "Kairoi",
    "harvest": "Kairoi",
    "heights_interlocken": "Kairoi",
    "izzy": "Kairoi",
    "kalaco": "Kairoi",
    "links_plum_creek": "Kairoi",
    "luna": "Kairoi",
    "park_17": "Kairoi",
    "pearl_lantana": "Kairoi",
    "ridian": "Kairoi",
    "slate": "Kairoi",
    "sloane": "Kairoi",
    "station_riverfront": "Kairoi",
    "stonewood": "Kairoi",
    "ten50": "Kairoi",
    "the_alcott": "Kairoi",
    "the_avant": "Kairoi",
    "the_hunter": "Kairoi",
    "the_northern": "Kairoi",
    "thepearl": "Kairoi",
    "thequinci": "Kairoi",
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


def _parse_bedbath_from_code(floorplan: str):
    """Fallback: parse bed/bath from floorplan code when box_score group is missing.
    
    Common Kairoi/RealPage naming conventions:
      S*, ST*, STUDIO*, Studio*, Midrise S* = Studio (0 bed, 1 bath)
      A*, 1B*, 1BD*, 1BM*, 1x1 = 1 bed, 1 bath
      B*, 2B*, 2BD*, 2A*, 2x2 = 2 bed, 2 bath
      C*, 3B*, 3BD*, 3A*, 3B* = 3 bed, 2 bath (default)
      TH-2* = 2 bed, 2.5 bath (townhome)
      TH-3* = 3 bed, 3 bath (townhome)
    Returns (beds, baths) or None if can't determine.
    """
    import re
    fp = floorplan.strip()
    fp_upper = fp.upper()
    
    # Studio patterns
    if (fp_upper.startswith('S') and not fp_upper.startswith('SLATE')) or \
       fp_upper.startswith('ST ') or fp_upper.startswith('STUDIO') or \
       'STUDIO' in fp_upper or fp_upper.startswith('MIDRISE S'):
        # S1, S1r, S2, ST A, STUDIO A, etc.
        # But not S-1 which at some properties is a different naming
        if re.match(r'^S\d', fp_upper) or re.match(r'^S1[a-z]', fp, re.IGNORECASE) or \
           fp_upper.startswith('ST ') or fp_upper.startswith('STUDIO') or \
           fp_upper.startswith('MIDRISE S'):
            return (0, 1.0)
    
    # Explicit bed count prefix: "1B", "2B", "3B", "1BD", "2BD", etc.
    m = re.match(r'^(\d)[Bb][Dd]?\b', fp)
    if m:
        beds = int(m.group(1))
        baths = float(beds)  # assume beds=baths as default
        return (beds, baths)
    
    # Townhome patterns: TH-2, TH-3
    m = re.match(r'^TH[-_]?(\d)', fp_upper)
    if m:
        beds = int(m.group(1))
        baths = beds + 0.5 if beds == 2 else float(beds)
        return (beds, baths)
    
    # Letter prefix: A=1bed, B=2bed, C=3bed
    if re.match(r'^A[\d.]', fp_upper):
        return (1, 1.0)
    if re.match(r'^B[\d.]', fp_upper):
        return (2, 2.0)
    if re.match(r'^C[\d.]', fp_upper):
        return (3, 2.0)
    
    return None


def derive_floorplan_bedrooms():
    """Derive bed/bath counts from box_score floorplan_group into realpage_floorplan_bedrooms.
    
    Raw layer only (realpage_raw.db → realpage_raw.db).
    Strategy:
      1. Parse box_score floorplan_group "NxM" format (authoritative)
      2. Fallback: parse floorplan code for any remaining unmatched floorplans
    """
    print("\n🛏️  Deriving floorplan bed/bath from box_score...")
    
    rp_conn = get_realpage_conn()
    cursor = rp_conn.cursor()
    
    # Create table if not exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS realpage_floorplan_bedrooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            property_id TEXT NOT NULL,
            floorplan TEXT NOT NULL,
            bedrooms INTEGER NOT NULL,
            bathrooms REAL NOT NULL,
            floorplan_group TEXT,
            derived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(property_id, floorplan)
        )
    """)
    
    # Step 1: Parse box_score floorplan_group (authoritative source)
    cursor.execute("""
        SELECT DISTINCT property_id, floorplan, floorplan_group
        FROM realpage_box_score
        WHERE floorplan_group IS NOT NULL AND floorplan_group != ''
    """)
    
    count = 0
    resolved = set()  # (property_id, floorplan) pairs already resolved
    for row in cursor.fetchall():
        property_id, floorplan, group = row
        
        # Parse "NxM" format, skip "Total" rows
        if not group or group.startswith("Total"):
            continue
        
        parts = group.lower().replace(" ", "").split("x")
        if len(parts) != 2:
            continue
        
        try:
            beds = int(float(parts[0]))
            baths = float(parts[1])
        except (ValueError, IndexError):
            continue
        
        cursor.execute("""
            INSERT OR REPLACE INTO realpage_floorplan_bedrooms
            (property_id, floorplan, bedrooms, bathrooms, floorplan_group, derived_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (property_id, floorplan, beds, baths, group, datetime.now().isoformat()))
        count += 1
        resolved.add((property_id, floorplan))
    
    # Step 2: Fallback — parse floorplan code for unmatched floorplans
    cursor.execute("""
        SELECT DISTINCT site_id, floorplan_name
        FROM realpage_units
        WHERE site_id IS NOT NULL AND floorplan_name IS NOT NULL AND floorplan_name != ''
    """)
    
    fallback_count = 0
    for row in cursor.fetchall():
        property_id, floorplan = row
        if (property_id, floorplan) in resolved:
            continue
        
        result = _parse_bedbath_from_code(floorplan)
        if result:
            beds, baths = result
            cursor.execute("""
                INSERT OR REPLACE INTO realpage_floorplan_bedrooms
                (property_id, floorplan, bedrooms, bathrooms, floorplan_group, derived_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (property_id, floorplan, beds, baths, f"parsed:{floorplan}", datetime.now().isoformat()))
            fallback_count += 1
            resolved.add((property_id, floorplan))
    
    rp_conn.commit()
    rp_conn.close()
    
    print(f"  ✅ Derived bed/bath for {count} floorplans (box_score) + {fallback_count} (code parsing)")
    return count + fallback_count


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
            resident_name,
            lease_start,
            lease_end,
            move_in_date
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
        lease_start = row[9] or ''
        lease_end = row[10] or ''
        move_in_date = row[11] or ''
        
        # Skip junk rows: header rows ("unit/lease status") and empty/null statuses
        if not status_raw or "unit/lease" in status_raw or "status" in status_raw:
            continue
        
        # Map status from rent_roll status field
        # Order matters: check NTV before occupied, vacant-leased before vacant
        is_preleased = 0
        if "ntvl" in status_raw:
            status = "notice"
            is_preleased = 1  # On notice but already re-leased
        elif "ntv" in status_raw:
            status = "notice"
        elif "occupied" in status_raw:
            status = "occupied"
        elif "vacant-leased" in status_raw or "vacant leased" in status_raw:
            status = "vacant"
            is_preleased = 1
        elif "vacant" in status_raw:
            status = "vacant"
        elif "model" in status_raw:
            status = "model"
        elif "down" in status_raw or "admin" in status_raw:
            status = "down"
        else:
            continue  # Skip any other unrecognized status
        
        # Set occupancy_status from status (API enrichment may override for vacant)
        # Down units are physically vacant (not ready) — status tracks them separately
        occupancy_status = "vacant_not_ready" if status == "down" else status
        
        uni_cursor.execute("""
            INSERT OR REPLACE INTO unified_units
            (unified_property_id, pms_source, pms_unit_id, unit_number,
             floorplan, square_feet, market_rent, status, occupancy_status,
             in_place_rent, sqft, lease_start, lease_end, move_in_date, is_preleased,
             synced_at)
            VALUES (?, 'realpage', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unified_id, unit_number, unit_number,
            floorplan, sqft, market_rent, status, occupancy_status,
            actual_rent, sqft, lease_start, lease_end, move_in_date, is_preleased,
            datetime.now().isoformat()
        ))
        count += 1
    
    uni_conn.commit()
    
    # --- Enrich unified_units with API data (made_ready_date, available_date, available) ---
    # The rent roll report doesn't include these fields, but realpage_units (API) does
    print("  📡 Enriching units with API data (market_rent, made_ready_date, available)...")
    enriched = 0
    
    # Build lookup: (property_id, unit_number) -> API fields
    rp_cursor.execute("""
        SELECT site_id, unit_number, made_ready_date, available_date, available, 
               on_notice_date, vacant, exclude_from_occupancy, market_rent
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
            "market_rent": arow[8],  # API market_rent = Venn UI price
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
                
                # API market_rent is authoritative (matches Venn UI / Snowflake ASKED_RENT)
                api_market_rent = api_data.get("market_rent")
                uni_cursor.execute("""
                    UPDATE unified_units 
                    SET made_ready_date = ?, available_date = ?, on_notice_date = ?,
                        excluded_from_occupancy = ?,
                        occupancy_status = COALESCE(?, occupancy_status),
                        market_rent = COALESCE(?, market_rent)
                    WHERE unified_property_id = ? AND pms_unit_id = ?
                """, (made_ready, avail_date, on_notice, is_excluded, occupancy_status, api_market_rent, unified_id, unit_num))
                if uni_cursor.rowcount > 0:
                    enriched += 1
    
    # --- Enrich bedrooms/bathrooms from realpage_floorplan_bedrooms (raw layer) ---
    print("  🛏️  Enriching units with bed/bath from floorplan lookup...")
    bedbath_enriched = 0
    try:
        rp_cursor.execute("""
            SELECT property_id, floorplan, bedrooms, bathrooms
            FROM realpage_floorplan_bedrooms
        """)
        fp_lookup = {}  # (property_id, floorplan) -> (beds, baths)
        for r in rp_cursor.fetchall():
            fp_lookup[(r[0], r[1])] = (r[2], r[3])
        
        for property_id, mapping in PROPERTY_MAPPING.items():
            unified_id = mapping["unified_id"]
            uni_cursor_r.execute(
                "SELECT pms_unit_id, floorplan FROM unified_units WHERE unified_property_id = ?",
                (unified_id,)
            )
            for unit_num, floorplan in uni_cursor_r.fetchall():
                bedbath = fp_lookup.get((property_id, floorplan))
                if bedbath:
                    beds, baths = bedbath
                    uni_cursor.execute("""
                        UPDATE unified_units SET bedrooms = ?, bathrooms = ?
                        WHERE unified_property_id = ? AND pms_unit_id = ?
                    """, (beds, baths, unified_id, unit_num))
                    if uni_cursor.rowcount > 0:
                        bedbath_enriched += 1
        
        uni_conn.commit()
    except Exception as e:
        print(f"  ⚠️  Bed/bath enrichment: {e}")
    print(f"  ✅ Enriched {bedbath_enriched} units with bed/bath")
    
    # --- Enrich in_place_rent from lease data ---
    # Leases use API unit_id as pms_unit_id; need realpage_units to map unit_id → unit_number
    print("  💰 Enriching units with in-place rent from leases...")
    rent_enriched = 0
    try:
        rp_cursor.execute("""
            SELECT site_id, unit_id, unit_number FROM realpage_units WHERE site_id IS NOT NULL
        """)
        uid_to_unum = {}  # (site_id, api_unit_id) -> unit_number
        for r in rp_cursor.fetchall():
            uid_to_unum[(r[0], r[1])] = r[2]
        
        rp_cursor.execute("""
            SELECT site_id, unit_id, rent_amount
            FROM realpage_leases
            WHERE status_text = 'Current' AND rent_amount > 0
        """)
        # Build (unified_id, unit_number) -> rent mapping
        rent_map = {}
        for r in rp_cursor.fetchall():
            site_id, api_uid, rent = r
            if site_id not in PROPERTY_MAPPING:
                continue
            unified_id = PROPERTY_MAPPING[site_id]["unified_id"]
            unit_num = uid_to_unum.get((site_id, str(api_uid)))
            if unit_num:
                rent_map[(unified_id, unit_num)] = rent
        
        for (uid, unum), rent in rent_map.items():
            uni_cursor.execute("""
                UPDATE unified_units SET in_place_rent = ?
                WHERE unified_property_id = ? AND unit_number = ?
            """, (rent, uid, unum))
            if uni_cursor.rowcount > 0:
                rent_enriched += 1
    except Exception as e:
        print(f"  ⚠️  Rent enrichment: {e}")
    
    # --- Enrich Vacant-Leased units with incoming lease_start ---
    # RealPage residents with lease_status='Future' have move_in_date for incoming tenants
    print("  📅 Enriching Vacant-Leased units with incoming lease_start...")
    lease_start_enriched = 0
    try:
        # Get all Vacant-Leased units missing lease_start
        uni_cursor_r2 = uni_conn.cursor()
        uni_cursor_r2.execute("""
            SELECT unified_property_id, unit_number FROM unified_units
            WHERE is_preleased = 1
              AND occupancy_status IN ('vacant', 'vacant_ready', 'vacant_not_ready')
              AND (lease_start IS NULL OR lease_start = '')
        """)
        preleased_missing = uni_cursor_r2.fetchall()
        
        if preleased_missing:
            # First try unified_leases Applicant
            for unified_id, unit_num in preleased_missing:
                uni_cursor_r2.execute("""
                    SELECT lease_start FROM unified_leases
                    WHERE unified_property_id = ? AND unit_number = ?
                      AND status = 'Applicant'
                      AND lease_start IS NOT NULL AND lease_start != ''
                    LIMIT 1
                """, (unified_id, unit_num))
                r = uni_cursor_r2.fetchone()
                if r:
                    uni_cursor.execute("""
                        UPDATE unified_units SET lease_start = ?
                        WHERE unified_property_id = ? AND unit_number = ?
                    """, (r[0], unified_id, unit_num))
                    if uni_cursor.rowcount > 0:
                        lease_start_enriched += 1
            
            # Then try realpage_residents Future move_in_date for remaining
            still_missing = []
            uni_cursor_r2.execute("""
                SELECT unified_property_id, unit_number FROM unified_units
                WHERE is_preleased = 1
                  AND occupancy_status IN ('vacant', 'vacant_ready', 'vacant_not_ready')
                  AND (lease_start IS NULL OR lease_start = '')
            """)
            still_missing = uni_cursor_r2.fetchall()
            
            if still_missing:
                # Group by property for efficient lookup
                by_prop = {}
                for uid, unum in still_missing:
                    by_prop.setdefault(uid, []).append(unum)
                
                # Reverse map: unified_id -> site_id
                uid_to_site = {v["unified_id"]: k for k, v in PROPERTY_MAPPING.items()}
                
                for uid, unit_nums in by_prop.items():
                    site_id = uid_to_site.get(uid)
                    if not site_id:
                        continue
                    ph = ','.join('?' * len(unit_nums))
                    rp_cursor.execute(f"""
                        SELECT unit_number, move_in_date
                        FROM realpage_residents
                        WHERE site_id = ?
                          AND unit_number IN ({ph})
                          AND lease_status IN ('Future', 'Current')
                          AND move_in_date IS NOT NULL AND move_in_date != ''
                    """, [site_id] + unit_nums)
                    for r in rp_cursor.fetchall():
                        uni_cursor.execute("""
                            UPDATE unified_units SET lease_start = ?
                            WHERE unified_property_id = ? AND unit_number = ?
                        """, (r[1], uid, r[0]))
                        if uni_cursor.rowcount > 0:
                            lease_start_enriched += 1
    except Exception as e:
        print(f"  ⚠️  Lease start enrichment: {e}")
    
    # --- Enrich lease_start from realpage_lease_details report ---
    # For Vacant-Leased units still missing lease_start, match Applicant leases
    # in lease_details by property + floorplan (direct match, no join chain).
    # Applicant leases in the report are often too new for the Leases API.
    print("  📋 Enriching lease_start from lease_details report...")
    lease_details_enriched = 0
    try:
        uni_cursor_ld = uni_conn.cursor()
        uni_cursor_ld.execute("""
            SELECT unified_property_id, unit_number, floorplan FROM unified_units
            WHERE is_preleased = 1
              AND occupancy_status IN ('vacant', 'vacant_ready', 'vacant_not_ready')
              AND (lease_start IS NULL OR lease_start = '')
              AND floorplan IS NOT NULL AND floorplan != ''
        """)
        still_missing = uni_cursor_ld.fetchall()
        
        if still_missing:
            uid_to_site_ld = {v["unified_id"]: k for k, v in PROPERTY_MAPPING.items()}
            
            # Pre-load all Applicant leases from lease_details per property
            # keyed by (site_id, floorplan_code) → earliest lease_start_date
            applicant_cache = {}
            site_ids = set()
            for uid, unum, fp in still_missing:
                sid = uid_to_site_ld.get(uid)
                if sid:
                    site_ids.add(sid)
            
            for sid in site_ids:
                rp_cursor.execute("""
                    SELECT floorplan, lease_start_date FROM realpage_lease_details
                    WHERE property_id = ? AND occupancy_status = 'Applicant'
                      AND lease_start_date IS NOT NULL AND lease_start_date != ''
                    ORDER BY lease_start_date ASC
                """, (sid,))
                for fp_full, start in rp_cursor.fetchall():
                    # Extract floorplan code: "1D - 1D" → "1D"
                    fp_code = fp_full.split(' - ')[0].strip() if fp_full else ''
                    cache_key = (sid, fp_code)
                    if cache_key not in applicant_cache:
                        applicant_cache[cache_key] = start  # first = earliest
            
            for uid, unum, fp in still_missing:
                site_id = uid_to_site_ld.get(uid)
                if not site_id:
                    continue
                start = applicant_cache.get((site_id, fp))
                if start:
                    uni_cursor.execute("""
                        UPDATE unified_units SET lease_start = ?
                        WHERE unified_property_id = ? AND unit_number = ?
                          AND (lease_start IS NULL OR lease_start = '')
                    """, (start, uid, unum))
                    if uni_cursor.rowcount > 0:
                        lease_details_enriched += 1
    except Exception as e:
        print(f"  ⚠️  Lease details enrichment: {e}")
    
    # --- Compute days_vacant from realpage_residents move_out_date ---
    # For vacant units where days_vacant is NULL, compute from last move_out
    print("  📊 Computing days_vacant from move_out dates...")
    days_vacant_enriched = 0
    try:
        uni_cursor_r3 = uni_conn.cursor()
        uni_cursor_r3.execute("""
            SELECT unified_property_id, unit_number FROM unified_units
            WHERE occupancy_status IN ('vacant', 'vacant_ready', 'vacant_not_ready')
              AND (days_vacant IS NULL)
        """)
        vacant_missing_dv = uni_cursor_r3.fetchall()
        
        if vacant_missing_dv:
            # First try unified_leases move_out_date
            for uid, unum in vacant_missing_dv:
                uni_cursor_r3.execute("""
                    SELECT MAX(move_out_date) FROM unified_leases
                    WHERE unified_property_id = ? AND unit_number = ?
                      AND move_out_date IS NOT NULL AND move_out_date != ''
                """, (uid, unum))
                r = uni_cursor_r3.fetchone()
                if r and r[0]:
                    mo_str = r[0]
                    try:
                        for fmt in ('%Y-%m-%d', '%m/%d/%Y'):
                            try:
                                mo_date = datetime.strptime(mo_str, fmt).date()
                                dv = (datetime.now().date() - mo_date).days
                                if dv < 0:
                                    dv = 0
                                uni_cursor.execute("""
                                    UPDATE unified_units SET days_vacant = ?
                                    WHERE unified_property_id = ? AND unit_number = ?
                                """, (dv, uid, unum))
                                if uni_cursor.rowcount > 0:
                                    days_vacant_enriched += 1
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass
            
            # Then try realpage_residents Past/Former for remaining
            uni_cursor_r3.execute("""
                SELECT unified_property_id, unit_number FROM unified_units
                WHERE occupancy_status IN ('vacant', 'vacant_ready', 'vacant_not_ready')
                  AND (days_vacant IS NULL)
            """)
            still_missing_dv = uni_cursor_r3.fetchall()
            
            if still_missing_dv:
                by_prop_dv = {}
                for uid, unum in still_missing_dv:
                    by_prop_dv.setdefault(uid, []).append(unum)
                
                uid_to_site = {v["unified_id"]: k for k, v in PROPERTY_MAPPING.items()}
                
                for uid, unit_nums in by_prop_dv.items():
                    site_id = uid_to_site.get(uid)
                    if not site_id:
                        continue
                    ph = ','.join('?' * len(unit_nums))
                    rp_cursor.execute(f"""
                        SELECT unit_number, MAX(move_out_date) as last_mo
                        FROM realpage_residents
                        WHERE site_id = ?
                          AND unit_number IN ({ph})
                          AND move_out_date IS NOT NULL AND move_out_date != ''
                          AND lease_status IN ('Past', 'Former')
                        GROUP BY unit_number
                    """, [site_id] + unit_nums)
                    for r in rp_cursor.fetchall():
                        mo_str = r[1]
                        try:
                            for fmt in ('%Y-%m-%d', '%m/%d/%Y'):
                                try:
                                    mo_date = datetime.strptime(mo_str, fmt).date()
                                    dv = (datetime.now().date() - mo_date).days
                                    if dv < 0:
                                        dv = 0
                                    uni_cursor.execute("""
                                        UPDATE unified_units SET days_vacant = ?
                                        WHERE unified_property_id = ? AND unit_number = ?
                                    """, (dv, uid, r[0]))
                                    if uni_cursor.rowcount > 0:
                                        days_vacant_enriched += 1
                                    break
                                except ValueError:
                                    continue
                        except Exception:
                            pass
    except Exception as e:
        print(f"  ⚠️  Days vacant enrichment: {e}")
    
    # --- Enrich days_vacant from realpage_lease_details move_out_date ---
    # For vacant units still missing days_vacant, try the lease_details report
    # which often has move_out_date before the Leases/Residents APIs catch up.
    lease_details_dv_enriched = 0
    try:
        uni_cursor_dv2 = uni_conn.cursor()
        uni_cursor_dv2.execute("""
            SELECT unified_property_id, unit_number FROM unified_units
            WHERE occupancy_status IN ('vacant', 'vacant_ready', 'vacant_not_ready')
              AND (days_vacant IS NULL)
        """)
        still_missing_dv = uni_cursor_dv2.fetchall()
        
        if still_missing_dv:
            uid_to_site_dv = {v["unified_id"]: k for k, v in PROPERTY_MAPPING.items()}
            by_prop_dv2 = {}
            for uid, unum in still_missing_dv:
                by_prop_dv2.setdefault(uid, []).append(unum)
            
            for uid, unit_nums in by_prop_dv2.items():
                site_id = uid_to_site_dv.get(uid)
                if not site_id:
                    continue
                
                # Get unit_number → unit_id mapping
                ph = ','.join('?' * len(unit_nums))
                rp_cursor.execute(f"""
                    SELECT unit_number, unit_id FROM realpage_units
                    WHERE site_id = ? AND unit_number IN ({ph})
                """, [site_id] + unit_nums)
                unum_to_uid = {r[0]: str(r[1]) for r in rp_cursor.fetchall()}
                
                # Get unit_id → lease_id mapping (any lease for the unit)
                for unum in unit_nums:
                    api_uid = unum_to_uid.get(unum)
                    if not api_uid:
                        continue
                    # Find lease_ids for this unit from realpage_leases
                    rp_cursor.execute("""
                        SELECT lease_id FROM realpage_leases
                        WHERE site_id = ? AND unit_id = ?
                    """, (site_id, api_uid))
                    lease_ids = [str(r[0]) for r in rp_cursor.fetchall()]
                    if not lease_ids:
                        continue
                    
                    ph2 = ','.join('?' * len(lease_ids))
                    rp_cursor.execute(f"""
                        SELECT MAX(move_out_date) FROM realpage_lease_details
                        WHERE property_id = ? AND lease_id IN ({ph2})
                          AND move_out_date IS NOT NULL AND move_out_date != ''
                    """, [site_id] + lease_ids)
                    r = rp_cursor.fetchone()
                    if r and r[0]:
                        mo_str = r[0]
                        for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
                            try:
                                mo_date = datetime.strptime(mo_str, fmt).date()
                                dv = (datetime.now().date() - mo_date).days
                                if dv < 0:
                                    dv = 0
                                uni_cursor.execute("""
                                    UPDATE unified_units SET days_vacant = ?
                                    WHERE unified_property_id = ? AND unit_number = ?
                                      AND (days_vacant IS NULL)
                                """, (dv, uid, unum))
                                if uni_cursor.rowcount > 0:
                                    lease_details_dv_enriched += 1
                                break
                            except ValueError:
                                continue
    except Exception as e:
        print(f"  ⚠️  Lease details days_vacant enrichment: {e}")
    
    # --- Final fallback: compute days_vacant from available_date ---
    # For never-leased units (lease-up properties) with no move_out anywhere,
    # use the available_date already in unified_units as the vacancy start.
    avail_date_dv_enriched = 0
    try:
        uni_cursor_dv3 = uni_conn.cursor()
        uni_cursor_dv3.execute("""
            SELECT unified_property_id, unit_number, available_date FROM unified_units
            WHERE occupancy_status IN ('vacant', 'vacant_ready', 'vacant_not_ready')
              AND (days_vacant IS NULL)
              AND available_date IS NOT NULL AND available_date != ''
        """)
        for uid, unum, avail_str in uni_cursor_dv3.fetchall():
            try:
                for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%m/%d/%Y'):
                    try:
                        avail_date = datetime.strptime(avail_str, fmt).date()
                        dv = (datetime.now().date() - avail_date).days
                        if dv < 0:
                            dv = 0
                        uni_cursor.execute("""
                            UPDATE unified_units SET days_vacant = ?
                            WHERE unified_property_id = ? AND unit_number = ?
                              AND (days_vacant IS NULL)
                        """, (dv, uid, unum))
                        if uni_cursor.rowcount > 0:
                            avail_date_dv_enriched += 1
                        break
                    except ValueError:
                        continue
            except Exception:
                pass
    except Exception as e:
        print(f"  ⚠️  Available date days_vacant fallback: {e}")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} units, enriched {enriched} with API data, {rent_enriched} with lease rent, {lease_start_enriched} with incoming lease_start, {lease_details_enriched} from lease_details report, {days_vacant_enriched}+{lease_details_dv_enriched}+{avail_date_dv_enriched} with days_vacant")
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


def sync_leases():
    """Sync leases from realpage_leases (SOAP API data) to unified_leases."""
    print("\n📜 Syncing leases...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    # Ensure new columns exist (migration for existing DBs)
    for col, ctype in [('resident_name', 'TEXT'), ('status', 'TEXT'), ('lease_type', 'TEXT'),
                       ('move_in_date', 'TEXT'), ('move_out_date', 'TEXT'),
                       ('next_lease_id', 'TEXT'), ('floorplan', 'TEXT'), ('sqft', 'INTEGER')]:
        try:
            uni_cursor.execute(f"ALTER TABLE unified_leases ADD COLUMN {col} {ctype}")
        except Exception:
            pass
    uni_conn.commit()
    
    # Build unit_id -> (unit_number, floorplan, sqft) lookup
    unit_lookup = {}
    try:
        rp_cursor.execute("SELECT site_id, unit_id, unit_number, floorplan_name, rentable_sqft FROM realpage_units WHERE site_id IS NOT NULL")
        for r in rp_cursor.fetchall():
            unit_lookup[(r[0], r[1])] = (r[2] or '', r[3] or '', r[4] or 0)
    except Exception:
        pass
    
    uni_cursor.execute("DELETE FROM unified_leases")
    
    rp_cursor.execute("""
        SELECT site_id, lease_id, resident_id, unit_id, unit_number,
               status_text, type_text, rent_amount,
               lease_start_date, lease_end_date,
               move_in_date, inactive_date, lease_term_desc,
               next_lease_id, head_of_household_name
        FROM realpage_leases
        WHERE site_id IS NOT NULL
    """)
    
    count = 0
    for row in rp_cursor.fetchall():
        site_id = row[0]
        if site_id not in PROPERTY_MAPPING:
            continue
        unified_id = PROPERTY_MAPPING[site_id]["unified_id"]
        
        unit_id = row[3] or ''
        unit_number = row[4] or ''
        floorplan = ''
        sqft = 0
        
        # Resolve unit details from lookup
        if (site_id, unit_id) in unit_lookup:
            lu = unit_lookup[(site_id, unit_id)]
            if not unit_number:
                unit_number = lu[0]
            floorplan = lu[1]
            sqft = lu[2]
        
        uni_cursor.execute("""
            INSERT OR IGNORE INTO unified_leases
            (unified_property_id, pms_source, pms_lease_id, pms_resident_id, pms_unit_id,
             unit_number, resident_name, status, lease_type, rent_amount,
             lease_start, lease_end, move_in_date, move_out_date,
             lease_term_months, next_lease_id, floorplan, sqft, synced_at)
            VALUES (?, 'realpage', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            unified_id, row[1], row[2], unit_id, unit_number,
            row[14] or '', row[5] or '', row[6] or '', row[7] or 0,
            row[8] or '', row[9] or '', row[10] or '', row[11] or '',
            row[12] or '', row[13] or '', floorplan, sqft,
            datetime.now().isoformat()
        ))
        count += 1
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} lease records")
    return count


def sync_financials():
    """Sync financial summary + detail from realpage_monthly_transaction tables."""
    print("\n💰 Syncing financials...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    now_iso = datetime.now().isoformat()
    
    # -- Summary --
    uni_cursor.execute("DELETE FROM unified_financial_summary")
    summary_count = 0
    try:
        rp_cursor.execute("""
            SELECT property_id, report_date, fiscal_period,
                   gross_market_rent, gain_to_lease, loss_to_lease, gross_potential,
                   total_other_charges, total_possible_collections,
                   total_collection_losses, total_adjustments,
                   past_due_end_prior, prepaid_end_prior,
                   past_due_end_current, prepaid_end_current,
                   net_change_past_due_prepaid, total_losses_and_adjustments,
                   current_monthly_collections, total_monthly_collections
            FROM realpage_monthly_transaction_summary
            WHERE property_id IS NOT NULL
        """)
        for row in rp_cursor.fetchall():
            if row[0] not in PROPERTY_MAPPING:
                continue
            unified_id = PROPERTY_MAPPING[row[0]]["unified_id"]
            uni_cursor.execute("""
                INSERT INTO unified_financial_summary
                (unified_property_id, pms_source, report_date, fiscal_period,
                 gross_market_rent, gain_to_lease, loss_to_lease, gross_potential,
                 total_other_charges, total_possible_collections,
                 total_collection_losses, total_adjustments,
                 past_due_end_prior, prepaid_end_prior,
                 past_due_end_current, prepaid_end_current,
                 net_change_past_due_prepaid, total_losses_and_adjustments,
                 current_monthly_collections, total_monthly_collections, snapshot_date)
                VALUES (?, 'realpage', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (unified_id, row[1], row[2], row[3], row[4], row[5], row[6],
                  row[7], row[8], row[9], row[10], row[11], row[12], row[13],
                  row[14], row[15], row[16], row[17], row[18], now_iso))
            summary_count += 1
    except Exception as e:
        print(f"  ⚠️  Financial summary: {e}")
    
    # -- Detail --
    uni_cursor.execute("DELETE FROM unified_financial_detail")
    detail_count = 0
    try:
        rp_cursor.execute("""
            SELECT property_id, fiscal_period, transaction_group, transaction_code,
                   description, ytd_last_month, this_month, ytd_through_month
            FROM realpage_monthly_transaction_detail
            WHERE property_id IS NOT NULL
        """)
        for row in rp_cursor.fetchall():
            if row[0] not in PROPERTY_MAPPING:
                continue
            unified_id = PROPERTY_MAPPING[row[0]]["unified_id"]
            uni_cursor.execute("""
                INSERT INTO unified_financial_detail
                (unified_property_id, pms_source, fiscal_period, transaction_group,
                 transaction_code, description, ytd_last_month, this_month,
                 ytd_through_month, snapshot_date)
                VALUES (?, 'realpage', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (unified_id, row[1], row[2] or '', row[3] or '',
                  row[4] or '', row[5] or 0, row[6] or 0, row[7] or 0,
                  now_iso))
            detail_count += 1
    except Exception as e:
        print(f"  ⚠️  Financial detail: {e}")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {summary_count} summary + {detail_count} detail records")
    return summary_count + detail_count


def sync_lease_expirations():
    """Sync lease expiration/renewal data from report 4156."""
    print("\n📅 Syncing lease expirations...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    uni_cursor.execute("DELETE FROM unified_lease_expirations")
    
    count = 0
    try:
        # Deduplicate: pick latest report_date per unit, breaking ties arbitrarily
        rp_cursor.execute("""
            SELECT property_id, MAX(report_date) as report_date, unit_number, floorplan,
                   actual_rent, lease_end_date, decision,
                   new_rent, new_lease_start, new_lease_term,
                   move_in_date, market_rent
            FROM realpage_lease_expiration_renewal
            WHERE property_id IS NOT NULL
            GROUP BY property_id, unit_number, lease_end_date
        """)
        for row in rp_cursor.fetchall():
            if row[0] not in PROPERTY_MAPPING:
                continue
            unified_id = PROPERTY_MAPPING[row[0]]["unified_id"]
            uni_cursor.execute("""
                INSERT INTO unified_lease_expirations
                (unified_property_id, pms_source, unit_number, floorplan, resident_name,
                 lease_end_date, decision, actual_rent, new_rent,
                 new_lease_start, new_lease_term, sqft, report_date)
                VALUES (?, 'realpage', ?, ?, '', ?, ?, ?, ?, ?, ?, 0, ?)
            """, (unified_id, row[2] or '', row[3] or '',
                  row[5] or '', row[6] or '', row[4] or 0, row[7] or 0,
                  row[8] or '', row[9] or 0, row[1] or ''))
            count += 1
    except Exception as e:
        print(f"  ⚠️  Lease expirations: {e}")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} lease expiration records")
    return count


def sync_activity():
    """Sync leasing activity from realpage_activity (Excel report data)."""
    print("\n📋 Syncing activity...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    now_iso = datetime.now().isoformat()
    uni_cursor.execute("DELETE FROM unified_activity")
    
    count = 0
    try:
        rp_cursor.execute("""
            SELECT property_id, resident_name, activity_type, activity_date
            FROM realpage_activity
            WHERE property_id IS NOT NULL
        """)
        for row in rp_cursor.fetchall():
            if row[0] not in PROPERTY_MAPPING:
                continue
            unified_id = PROPERTY_MAPPING[row[0]]["unified_id"]
            
            # Normalize activity_date from MM/DD/YYYY to ISO
            raw_date = row[3] or ''
            iso_date = raw_date
            if raw_date and len(raw_date) >= 10 and '/' in raw_date:
                parts = raw_date.split('/')
                if len(parts) == 3:
                    iso_date = f"{parts[2]}-{parts[0].zfill(2)}-{parts[1].zfill(2)}"
            
            uni_cursor.execute("""
                INSERT INTO unified_activity
                (unified_property_id, pms_source, resident_name, activity_type,
                 activity_type_raw, activity_date, leasing_agent, source, snapshot_date)
                VALUES (?, 'realpage', ?, ?, ?, ?, '', '', ?)
            """, (unified_id, row[1] or '', row[2] or '', row[2] or '',
                  iso_date, now_iso))
            count += 1
    except Exception as e:
        print(f"  ⚠️  Activity: {e}")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} activity records")
    return count


def sync_projected_occupancy():
    """Sync projected occupancy from report 3842."""
    print("\n📈 Syncing projected occupancy...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    now_iso = datetime.now().isoformat()
    uni_cursor.execute("DELETE FROM unified_projected_occupancy")
    
    count = 0
    try:
        rp_cursor.execute("""
            SELECT property_id, week_ending, total_units, occupied_begin,
                   pct_occupied_begin, scheduled_move_ins, scheduled_move_outs,
                   occupied_end, pct_occupied_end
            FROM realpage_projected_occupancy
            WHERE property_id IS NOT NULL
        """)
        for row in rp_cursor.fetchall():
            if row[0] not in PROPERTY_MAPPING:
                continue
            unified_id = PROPERTY_MAPPING[row[0]]["unified_id"]
            uni_cursor.execute("""
                INSERT INTO unified_projected_occupancy
                (unified_property_id, pms_source, week_ending, total_units,
                 occupied_begin, pct_occupied_begin, scheduled_move_ins,
                 scheduled_move_outs, occupied_end, pct_occupied_end, snapshot_date)
                VALUES (?, 'realpage', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (unified_id, row[1] or '', row[2] or 0, row[3] or 0,
                  row[4] or 0, row[5] or 0, row[6] or 0,
                  row[7] or 0, row[8] or 0, now_iso))
            count += 1
    except Exception as e:
        print(f"  ⚠️  Projected occupancy: {e}")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} projected occupancy records")
    return count


def sync_maintenance():
    """Sync make-ready pipeline (open + closed) from realpage_make_ready + realpage_closed_make_ready."""
    print("\n🔧 Syncing maintenance...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    now_iso = datetime.now().isoformat()
    uni_cursor.execute("DELETE FROM unified_maintenance")
    
    open_count = 0
    closed_count = 0
    
    # Open make-ready pipeline
    try:
        rp_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='realpage_make_ready'")
        if rp_cursor.fetchone():
            rp_cursor.execute("""
                SELECT property_id, unit, sqft, days_vacant, date_vacated,
                       date_due, num_work_orders
                FROM realpage_make_ready
                WHERE property_id IS NOT NULL
            """)
            for row in rp_cursor.fetchall():
                if row[0] not in PROPERTY_MAPPING:
                    continue
                unified_id = PROPERTY_MAPPING[row[0]]["unified_id"]
                uni_cursor.execute("""
                    INSERT INTO unified_maintenance
                    (unified_property_id, pms_source, record_type, unit, sqft, days_vacant,
                     date_vacated, date_due, num_work_orders, snapshot_date)
                    VALUES (?, 'realpage', 'open', ?, ?, ?, ?, ?, ?, ?)
                """, (unified_id, row[1] or '', row[2] or 0, row[3] or 0,
                      row[4] or '', row[5] or '', row[6] or 0, now_iso))
                open_count += 1
    except Exception as e:
        print(f"  ⚠️  Maintenance (open): {e}")
    
    # Closed make-ready
    try:
        rp_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='realpage_closed_make_ready'")
        if rp_cursor.fetchone():
            rp_cursor.execute("""
                SELECT property_id, unit, num_work_orders, date_closed, amount_charged
                FROM realpage_closed_make_ready
                WHERE property_id IS NOT NULL
            """)
            for row in rp_cursor.fetchall():
                if row[0] not in PROPERTY_MAPPING:
                    continue
                unified_id = PROPERTY_MAPPING[row[0]]["unified_id"]
                uni_cursor.execute("""
                    INSERT INTO unified_maintenance
                    (unified_property_id, pms_source, record_type, unit, num_work_orders,
                     date_closed, amount_charged, snapshot_date)
                    VALUES (?, 'realpage', 'closed', ?, ?, ?, ?, ?)
                """, (unified_id, row[1] or '', row[2] or 0,
                      row[3] or '', row[4] or 0, now_iso))
                closed_count += 1
    except Exception as e:
        print(f"  ⚠️  Maintenance (closed): {e}")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    count = open_count + closed_count
    print(f"  ✅ Synced {count} maintenance records ({open_count} open, {closed_count} closed)")
    return count


def sync_move_out_reasons():
    """Sync move-out reasons from report 3879."""
    print("\n🚪 Syncing move-out reasons...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    now_iso = datetime.now().isoformat()
    uni_cursor.execute("DELETE FROM unified_move_out_reasons")
    
    count = 0
    try:
        rp_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='realpage_move_out_reasons'")
        if rp_cursor.fetchone():
            rp_cursor.execute("""
                SELECT property_id, resident_type, category, category_count, category_pct,
                       reason, reason_count, reason_pct, date_range
                FROM realpage_move_out_reasons
                WHERE property_id IS NOT NULL
            """)
            for row in rp_cursor.fetchall():
                if row[0] not in PROPERTY_MAPPING:
                    continue
                unified_id = PROPERTY_MAPPING[row[0]]["unified_id"]
                uni_cursor.execute("""
                    INSERT INTO unified_move_out_reasons
                    (unified_property_id, pms_source, resident_type, category, category_count,
                     category_pct, reason, reason_count, reason_pct, date_range, snapshot_date)
                    VALUES (?, 'realpage', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (unified_id, row[1] or '', row[2] or '', row[3] or 0,
                      row[4] or 0, row[5] or '', row[6] or 0, row[7] or 0,
                      row[8] or '', now_iso))
                count += 1
    except Exception as e:
        print(f"  ⚠️  Move-out reasons: {e}")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} move-out reason records")
    return count


def sync_advertising_sources():
    """Sync advertising source data."""
    print("\n📢 Syncing advertising sources...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    now_iso = datetime.now().isoformat()
    uni_cursor.execute("DELETE FROM unified_advertising_sources")
    
    count = 0
    try:
        rp_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='realpage_advertising_source'")
        if rp_cursor.fetchone():
            rp_cursor.execute("""
                SELECT property_id, source, new_prospects, visits,
                       leases, net_leases, cancelled_denied,
                       prospect_to_lease_pct, visit_to_lease_pct, date_range,
                       COALESCE(timeframe_tag, '') as timeframe_tag
                FROM realpage_advertising_source
                WHERE property_id IS NOT NULL
            """)
            for row in rp_cursor.fetchall():
                if row[0] not in PROPERTY_MAPPING:
                    continue
                unified_id = PROPERTY_MAPPING[row[0]]["unified_id"]
                uni_cursor.execute("""
                    INSERT INTO unified_advertising_sources
                    (unified_property_id, pms_source, source_name, new_prospects, visits,
                     leases, net_leases, cancelled_denied, prospect_to_lease_pct,
                     visit_to_lease_pct, date_range, timeframe_tag, snapshot_date)
                    VALUES (?, 'realpage', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (unified_id, row[1] or '', row[2] or 0, row[3] or 0,
                      row[4] or 0, row[5] or 0, row[6] or 0,
                      row[7] or 0, row[8] or 0, row[9] or '', row[10] or '',
                      now_iso))
                count += 1
    except Exception as e:
        print(f"  ⚠️  Advertising sources: {e}")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} advertising source records")
    return count


def sync_lost_rent():
    """Sync lost rent summary from report 4279."""
    print("\n💸 Syncing lost rent...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    now_iso = datetime.now().isoformat()
    uni_cursor.execute("DELETE FROM unified_lost_rent")
    
    count = 0
    try:
        rp_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='realpage_lost_rent_summary'")
        if rp_cursor.fetchone():
            rp_cursor.execute("""
                SELECT property_id, unit, market_rent, lease_rent, rent_charged,
                       loss_to_rent, gain_to_rent, vacancy_current,
                       lost_rent_not_charged, move_in_date, move_out_date, fiscal_period
                FROM realpage_lost_rent_summary
                WHERE property_id IS NOT NULL
            """)
            for row in rp_cursor.fetchall():
                if row[0] not in PROPERTY_MAPPING:
                    continue
                unified_id = PROPERTY_MAPPING[row[0]]["unified_id"]
                uni_cursor.execute("""
                    INSERT INTO unified_lost_rent
                    (unified_property_id, pms_source, unit_number, market_rent, lease_rent,
                     rent_charged, loss_to_rent, gain_to_rent, vacancy_current,
                     lost_rent_not_charged, move_in_date, move_out_date, fiscal_period,
                     snapshot_date)
                    VALUES (?, 'realpage', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (unified_id, row[1] or '', row[2] or 0, row[3] or 0,
                      row[4] or 0, row[5] or 0, row[6] or 0, row[7] or 0,
                      row[8] or 0, row[9] or '', row[10] or '', row[11] or '',
                      now_iso))
                count += 1
    except Exception as e:
        print(f"  ⚠️  Lost rent: {e}")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} lost rent records")
    return count


def sync_amenities():
    """Sync rentable items from realpage_rentable_items (SOAP API data)."""
    print("\n🏊 Syncing amenities...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    now_iso = datetime.now().isoformat()
    uni_cursor.execute("DELETE FROM unified_amenities")
    
    count = 0
    rented = 0
    try:
        rp_cursor.execute("""
            SELECT site_id, item_type, description, billing_amount,
                   status, unit_id, '', lease_id
            FROM realpage_rentable_items
            WHERE site_id IS NOT NULL
        """)
        for row in rp_cursor.fetchall():
            if row[0] not in PROPERTY_MAPPING:
                continue
            unified_id = PROPERTY_MAPPING[row[0]]["unified_id"]
            raw_lease_id = row[7] or ''
            unit_id = row[5] or ''
            # Determine rented status: lease_id present means assigned to a resident
            is_rented = raw_lease_id not in ('', '0', 'None')
            computed_status = 'Rented' if is_rented else 'Available'
            uni_cursor.execute("""
                INSERT INTO unified_amenities
                (unified_property_id, pms_source, item_type, item_description,
                 monthly_charge, status, unit_number, resident_name, lease_id, snapshot_date)
                VALUES (?, 'realpage', ?, ?, ?, ?, ?, ?, ?, ?)
            """, (unified_id, row[1] or '', row[2] or '', row[3] or 0,
                  computed_status, unit_id, row[6] or '', raw_lease_id, now_iso))
            count += 1
            if is_rented:
                rented += 1
    except Exception as e:
        print(f"  ⚠️  Amenities: {e}")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} amenity records ({rented} rented, {count - rented} available)")
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


def sync_income_statement():
    """Sync income statement from report 3836."""
    print("\n📊 Syncing income statement...")
    
    rp_conn = get_realpage_conn()
    uni_conn = get_unified_conn()
    rp_cursor = rp_conn.cursor()
    uni_cursor = uni_conn.cursor()
    
    now_iso = datetime.now().isoformat()
    uni_cursor.execute("DELETE FROM unified_income_statement")
    
    count = 0
    try:
        rp_cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='realpage_income_statement'")
        if rp_cursor.fetchone():
            rp_cursor.execute("""
                SELECT property_id, fiscal_period, section, category,
                       gl_account_code, gl_account_name, sign, amount, line_type
                FROM realpage_income_statement
                WHERE property_id IS NOT NULL
            """)
            for row in rp_cursor.fetchall():
                if row[0] not in PROPERTY_MAPPING:
                    continue
                unified_id = PROPERTY_MAPPING[row[0]]["unified_id"]
                uni_cursor.execute("""
                    INSERT INTO unified_income_statement
                    (unified_property_id, pms_source, fiscal_period, section, category,
                     gl_account_code, gl_account_name, sign, amount, line_type, snapshot_date)
                    VALUES (?, 'realpage', ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (unified_id, row[1] or '', row[2] or '', row[3] or '',
                      row[4] or '', row[5] or '', row[6] or '', row[7] or 0,
                      row[8] or '', now_iso))
                count += 1
    except Exception as e:
        print(f"  ⚠️  Income statement: {e}")
    
    uni_conn.commit()
    rp_conn.close()
    uni_conn.close()
    
    print(f"  ✅ Synced {count} income statement records")
    return count


def run_full_sync():
    """Run full sync from RealPage to Unified."""
    print("=" * 60)
    print("RealPage → Unified Database Sync")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    
    # Raw layer derivations (realpage_raw.db → realpage_raw.db)
    bedbath_count = derive_floorplan_bedrooms()
    
    # Core metrics (existing)
    property_count = sync_properties()
    occupancy_count = sync_occupancy_metrics()
    pricing_count = sync_pricing_metrics()
    unit_count = sync_units_from_rent_roll()
    resident_count = sync_residents_from_rent_roll()
    delinquency_count = sync_delinquency()
    
    # Report data (new — full unified layer)
    lease_count = sync_leases()
    financial_count = sync_financials()
    lease_exp_count = sync_lease_expirations()
    activity_count = sync_activity()
    proj_occ_count = sync_projected_occupancy()
    maintenance_count = sync_maintenance()
    move_out_count = sync_move_out_reasons()
    ad_source_count = sync_advertising_sources()
    lost_rent_count = sync_lost_rent()
    amenity_count = sync_amenities()
    income_stmt_count = sync_income_statement()
    
    log_sync(property_count, occupancy_count, pricing_count, unit_count, resident_count, delinquency_count)
    
    print("\n" + "=" * 60)
    print("SYNC COMPLETE")
    print("=" * 60)
    print(f"  Properties:        {property_count}")
    print(f"  Occupancy:         {occupancy_count}")
    print(f"  Pricing:           {pricing_count}")
    print(f"  Units:             {unit_count}")
    print(f"  Residents:         {resident_count}")
    print(f"  Delinquency:       {delinquency_count}")
    print(f"  Leases:            {lease_count}")
    print(f"  Financials:        {financial_count}")
    print(f"  Lease Expirations: {lease_exp_count}")
    print(f"  Activity:          {activity_count}")
    print(f"  Proj. Occupancy:   {proj_occ_count}")
    print(f"  Maintenance:       {maintenance_count}")
    print(f"  Move-Out Reasons:  {move_out_count}")
    print(f"  Ad Sources:        {ad_source_count}")
    print(f"  Lost Rent:         {lost_rent_count}")
    print(f"  Amenities:         {amenity_count}")
    print(f"  Income Statement:  {income_stmt_count}")
    print(f"\nCompleted at: {datetime.now().isoformat()}")


if __name__ == "__main__":
    run_full_sync()
