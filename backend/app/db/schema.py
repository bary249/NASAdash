"""
Database Schema Definitions for OwnerDashV2.

This module defines SQLite schemas for:
1. Yardi Raw Data - All fields extractable from Yardi APIs
2. RealPage Raw Data - All fields extractable from RealPage APIs  
3. Unified Data Layer - Normalized data from both PMS systems

Each PMS stores raw data exactly as received from the API.
The unified layer normalizes and combines data for dashboard queries.
"""

import sqlite3
from pathlib import Path
from datetime import datetime

# Database file paths
DB_DIR = Path(__file__).parent / "data"
YARDI_DB_PATH = DB_DIR / "yardi_raw.db"
REALPAGE_DB_PATH = DB_DIR / "realpage_raw.db"
UNIFIED_DB_PATH = DB_DIR / "unified.db"


# =============================================================================
# YARDI RAW DATA SCHEMA
# All fields extractable from Yardi Voyager APIs (READ-ONLY)
# =============================================================================

YARDI_SCHEMA = """
-- Yardi Properties (from GetPropertyConfigurations)
CREATE TABLE IF NOT EXISTS yardi_properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id TEXT UNIQUE NOT NULL,
    property_code TEXT,
    marketing_name TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    phone TEXT,
    email TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Yardi Units (from GetUnitInformation)
CREATE TABLE IF NOT EXISTS yardi_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id TEXT NOT NULL,
    unit_code TEXT NOT NULL,
    unit_type TEXT,
    unit_status TEXT,
    bedrooms INTEGER,
    bathrooms REAL,
    sqft INTEGER,
    market_rent REAL,
    building TEXT,
    floor TEXT,
    address TEXT,
    available_date TEXT,
    make_ready_date TEXT,
    move_in_date TEXT,
    move_out_date TEXT,
    lease_expiration_date TEXT,
    excluded_from_occupancy INTEGER DEFAULT 0,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, unit_code)
);

-- Yardi Residents (from GetResidentsByStatus)
CREATE TABLE IF NOT EXISTS yardi_residents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id TEXT NOT NULL,
    resident_code TEXT NOT NULL,
    unit_code TEXT,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    cell_phone TEXT,
    status TEXT,
    lease_from_date TEXT,
    lease_to_date TEXT,
    move_in_date TEXT,
    move_out_date TEXT,
    notice_date TEXT,
    notice_for_date TEXT,
    rent REAL,
    balance REAL,
    deposit REAL,
    is_head_of_household INTEGER DEFAULT 1,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, resident_code)
);

-- Yardi Lease Charges (from GetResidentLeaseCharges_Login)
CREATE TABLE IF NOT EXISTS yardi_lease_charges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id TEXT NOT NULL,
    resident_code TEXT NOT NULL,
    unit_code TEXT,
    charge_code TEXT,
    charge_description TEXT,
    charge_amount REAL,
    charge_frequency TEXT,
    effective_date TEXT,
    end_date TEXT,
    lease_from_date TEXT,
    lease_to_date TEXT,
    total_charges REAL,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Yardi Available Units (from AvailableUnits_Login)
CREATE TABLE IF NOT EXISTS yardi_available_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id TEXT NOT NULL,
    unit_code TEXT NOT NULL,
    unit_type TEXT,
    bedrooms INTEGER,
    bathrooms REAL,
    sqft INTEGER,
    market_rent REAL,
    min_rent REAL,
    max_rent REAL,
    deposit REAL,
    available_date TEXT,
    amenities TEXT,
    specials TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(property_id, unit_code)
);

-- Yardi Guest Activity (from GetYardiGuestActivity_Login)
CREATE TABLE IF NOT EXISTS yardi_guest_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id TEXT NOT NULL,
    guest_card_id TEXT,
    prospect_code TEXT,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    event_type TEXT,
    event_date TEXT,
    event_description TEXT,
    agent_name TEXT,
    source TEXT,
    preferred_floorplan TEXT,
    preferred_move_in TEXT,
    desired_rent REAL,
    status TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Metadata table for tracking extractions
CREATE TABLE IF NOT EXISTS yardi_extraction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    property_id TEXT NOT NULL,
    table_name TEXT NOT NULL,
    records_extracted INTEGER,
    extraction_started_at TIMESTAMP,
    extraction_completed_at TIMESTAMP,
    status TEXT,
    error_message TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_yardi_units_property ON yardi_units(property_id);
CREATE INDEX IF NOT EXISTS idx_yardi_units_status ON yardi_units(unit_status);
CREATE INDEX IF NOT EXISTS idx_yardi_residents_property ON yardi_residents(property_id);
CREATE INDEX IF NOT EXISTS idx_yardi_residents_status ON yardi_residents(status);
CREATE INDEX IF NOT EXISTS idx_yardi_residents_unit ON yardi_residents(unit_code);
"""


# =============================================================================
# REALPAGE RAW DATA SCHEMA
# All fields extractable from RealPage RPX Gateway APIs (READ-ONLY)
# =============================================================================

REALPAGE_SCHEMA = """
-- RealPage Sites/Properties (from getSiteList)
CREATE TABLE IF NOT EXISTS realpage_properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pmc_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    site_name TEXT,
    address TEXT,
    address2 TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    phone TEXT,
    fax TEXT,
    email TEXT,
    accounting_period TEXT,
    accounting_year TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(pmc_id, site_id)
);

-- RealPage Buildings (from getBuildings)
CREATE TABLE IF NOT EXISTS realpage_buildings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pmc_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    building_id TEXT NOT NULL,
    building_name TEXT,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(site_id, building_id)
);

-- RealPage Units (from unitlist)
CREATE TABLE IF NOT EXISTS realpage_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pmc_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    unit_id TEXT NOT NULL,
    unit_number TEXT,
    building_id TEXT,
    building_name TEXT,
    floor TEXT,
    floorplan_id TEXT,
    floorplan_code TEXT,
    floorplan_name TEXT,
    bedrooms INTEGER,
    bathrooms REAL,
    rentable_sqft INTEGER,
    gross_sqft INTEGER,
    market_rent REAL,
    vacant TEXT,
    available TEXT,
    unit_status TEXT,
    available_date TEXT,
    made_ready_date TEXT,
    on_notice_date TEXT,
    on_notice_for_date TEXT,
    exclude_from_occupancy TEXT,
    exclude_reason TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(site_id, unit_id)
);

-- RealPage Residents (from getresidentlistinfo)
CREATE TABLE IF NOT EXISTS realpage_residents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pmc_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    resident_id TEXT,
    resident_member_id TEXT,
    unit_id TEXT,
    unit_number TEXT,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    home_phone TEXT,
    cell_phone TEXT,
    work_phone TEXT,
    lease_status TEXT,
    resident_type TEXT,
    begin_date TEXT,
    end_date TEXT,
    move_in_date TEXT,
    move_out_date TEXT,
    notice_given_date TEXT,
    notice_for_date TEXT,
    applied_date TEXT,
    approved_date TEXT,
    rent REAL,
    balance REAL,
    current_balance REAL,
    pending_balance REAL,
    deposit REAL,
    is_head_of_household INTEGER,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RealPage Leases (from getleaseinfo) - expanded with all available fields
CREATE TABLE IF NOT EXISTS realpage_leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pmc_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    lease_id TEXT,
    resh_id TEXT,
    resident_id TEXT,
    unit_id TEXT,
    unit_number TEXT,
    lease_start_date TEXT,
    lease_end_date TEXT,
    lease_term INTEGER,
    lease_term_desc TEXT,
    rent_amount REAL,
    security_deposit REAL,
    next_lease_id TEXT,
    prior_lease_id TEXT,
    status TEXT,
    status_text TEXT,
    type_code TEXT,
    type_text TEXT,
    move_in_date TEXT,
    sched_move_in_date TEXT,
    applied_date TEXT,
    active_date TEXT,
    inactive_date TEXT,
    last_renewal_date TEXT,
    initial_lease_date TEXT,
    bill_date TEXT,
    payment_due_date TEXT,
    current_balance REAL,
    total_paid REAL,
    late_day_of_month INTEGER,
    late_charge_pct REAL,
    evict TEXT,
    head_of_household_name TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- RealPage Rentable Items (from getRentableItems) - amenities, parking, storage
CREATE TABLE IF NOT EXISTS realpage_rentable_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pmc_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    rid_id TEXT,
    item_name TEXT,
    item_type TEXT,
    description TEXT,
    billing_amount REAL,
    frequency TEXT,
    transaction_code_id TEXT,
    in_service TEXT,
    serial_number TEXT,
    status TEXT,
    date_available TEXT,
    unit_id TEXT,
    lease_id TEXT,
    resh_id TEXT,
    resident_member_id TEXT,
    start_date TEXT,
    end_date TEXT,
    extracted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Metadata table for tracking extractions
CREATE TABLE IF NOT EXISTS realpage_extraction_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pmc_id TEXT NOT NULL,
    site_id TEXT NOT NULL,
    table_name TEXT NOT NULL,
    records_extracted INTEGER,
    extraction_started_at TIMESTAMP,
    extraction_completed_at TIMESTAMP,
    status TEXT,
    error_message TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_realpage_units_site ON realpage_units(site_id);
CREATE INDEX IF NOT EXISTS idx_realpage_units_vacant ON realpage_units(vacant);
CREATE INDEX IF NOT EXISTS idx_realpage_residents_site ON realpage_residents(site_id);
CREATE INDEX IF NOT EXISTS idx_realpage_residents_status ON realpage_residents(lease_status);
CREATE INDEX IF NOT EXISTS idx_realpage_residents_unit ON realpage_residents(unit_id);
CREATE INDEX IF NOT EXISTS idx_realpage_leases_site ON realpage_leases(site_id);
CREATE INDEX IF NOT EXISTS idx_realpage_rentable_items_site ON realpage_rentable_items(site_id);
CREATE INDEX IF NOT EXISTS idx_realpage_rentable_items_type ON realpage_rentable_items(item_type);
CREATE INDEX IF NOT EXISTS idx_realpage_rentable_items_status ON realpage_rentable_items(status);
"""


# =============================================================================
# UNIFIED DATA LAYER SCHEMA
# Normalized data from both Yardi and RealPage
# =============================================================================

UNIFIED_SCHEMA = """
-- Unified Properties (normalized from both PMS systems)
CREATE TABLE IF NOT EXISTS unified_properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT UNIQUE NOT NULL,
    pms_source TEXT NOT NULL,  -- 'yardi' or 'realpage'
    pms_property_id TEXT NOT NULL,
    pms_pmc_id TEXT,  -- RealPage only
    name TEXT NOT NULL,
    address TEXT,
    city TEXT,
    state TEXT,
    zip TEXT,
    phone TEXT,
    email TEXT,
    total_units INTEGER,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Unified Units (normalized from both PMS systems)
CREATE TABLE IF NOT EXISTS unified_units (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    pms_unit_id TEXT NOT NULL,
    unit_number TEXT NOT NULL,
    building TEXT,
    floor TEXT,
    floorplan TEXT,
    floorplan_name TEXT,
    bedrooms INTEGER,
    bathrooms REAL,
    square_feet INTEGER,
    market_rent REAL,
    status TEXT,  -- 'occupied', 'vacant', 'notice', 'model', 'down'
    occupancy_status TEXT,  -- More detailed status
    available_date TEXT,
    days_vacant INTEGER,
    on_notice_date TEXT,
    made_ready_date TEXT,
    excluded_from_occupancy INTEGER DEFAULT 0,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(unified_property_id, pms_unit_id),
    FOREIGN KEY (unified_property_id) REFERENCES unified_properties(unified_property_id)
);

-- Unified Residents (normalized from both PMS systems)
CREATE TABLE IF NOT EXISTS unified_residents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    pms_resident_id TEXT NOT NULL,
    pms_unit_id TEXT,
    unit_number TEXT,
    first_name TEXT,
    last_name TEXT,
    full_name TEXT,
    email TEXT,
    phone TEXT,
    status TEXT,  -- 'current', 'future', 'past', 'notice', 'applicant'
    lease_start TEXT,
    lease_end TEXT,
    move_in_date TEXT,
    move_out_date TEXT,
    notice_date TEXT,
    current_rent REAL,
    balance REAL,
    is_head_of_household INTEGER DEFAULT 1,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unified_property_id) REFERENCES unified_properties(unified_property_id)
);

-- Unified Leases (normalized from both PMS systems)
CREATE TABLE IF NOT EXISTS unified_leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    pms_lease_id TEXT,
    pms_resident_id TEXT,
    pms_unit_id TEXT,
    unit_number TEXT,
    rent_amount REAL,
    lease_start TEXT,
    lease_end TEXT,
    lease_term_months INTEGER,
    is_renewal INTEGER DEFAULT 0,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (unified_property_id) REFERENCES unified_properties(unified_property_id)
);

-- Unified Occupancy Metrics (calculated from unit/resident data)
CREATE TABLE IF NOT EXISTS unified_occupancy_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    total_units INTEGER,
    occupied_units INTEGER,
    vacant_units INTEGER,
    leased_units INTEGER,
    preleased_vacant INTEGER DEFAULT 0,
    notice_units INTEGER DEFAULT 0,
    model_units INTEGER DEFAULT 0,
    down_units INTEGER DEFAULT 0,
    physical_occupancy REAL,
    leased_percentage REAL,
    exposure_30_days INTEGER,
    exposure_60_days INTEGER,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(unified_property_id, snapshot_date),
    FOREIGN KEY (unified_property_id) REFERENCES unified_properties(unified_property_id)
);

-- Unified Pricing Metrics (calculated by floorplan)
CREATE TABLE IF NOT EXISTS unified_pricing_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    floorplan TEXT NOT NULL,
    floorplan_name TEXT,
    unit_count INTEGER,
    bedrooms INTEGER,
    bathrooms REAL,
    avg_square_feet INTEGER,
    in_place_rent REAL,
    in_place_per_sf REAL,
    asking_rent REAL,
    asking_per_sf REAL,
    rent_growth REAL,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(unified_property_id, snapshot_date, floorplan),
    FOREIGN KEY (unified_property_id) REFERENCES unified_properties(unified_property_id)
);

-- Unified Leasing Metrics (move-ins, move-outs, renewals)
CREATE TABLE IF NOT EXISTS unified_leasing_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    snapshot_date TEXT NOT NULL,
    period TEXT NOT NULL,  -- 'current_month', 'prior_month', 'ytd'
    move_ins INTEGER DEFAULT 0,
    move_outs INTEGER DEFAULT 0,
    net_move_ins INTEGER DEFAULT 0,
    lease_expirations INTEGER DEFAULT 0,
    renewals INTEGER DEFAULT 0,
    renewal_percentage REAL,
    leads INTEGER DEFAULT 0,
    tours INTEGER DEFAULT 0,
    applications INTEGER DEFAULT 0,
    lease_signs INTEGER DEFAULT 0,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(unified_property_id, snapshot_date, period),
    FOREIGN KEY (unified_property_id) REFERENCES unified_properties(unified_property_id)
);

-- Sync metadata
CREATE TABLE IF NOT EXISTS unified_sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    sync_type TEXT NOT NULL,  -- 'full', 'incremental'
    tables_synced TEXT,  -- JSON array of table names
    records_synced INTEGER,
    sync_started_at TIMESTAMP,
    sync_completed_at TIMESTAMP,
    status TEXT,
    error_message TEXT
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_unified_units_property ON unified_units(unified_property_id);
CREATE INDEX IF NOT EXISTS idx_unified_units_status ON unified_units(status);
CREATE INDEX IF NOT EXISTS idx_unified_residents_property ON unified_residents(unified_property_id);
CREATE INDEX IF NOT EXISTS idx_unified_residents_status ON unified_residents(status);
CREATE INDEX IF NOT EXISTS idx_unified_occupancy_property ON unified_occupancy_metrics(unified_property_id);
CREATE INDEX IF NOT EXISTS idx_unified_occupancy_date ON unified_occupancy_metrics(snapshot_date);
CREATE INDEX IF NOT EXISTS idx_unified_pricing_property ON unified_pricing_metrics(unified_property_id);

-- =============================================================================
-- ANYONEHOME LEASING CRM DATA (Pre-Lease Funnel)
-- Data from AnyoneHome API for lead management and conversion tracking
-- =============================================================================

-- AnyoneHome Accounts (Management Companies)
CREATE TABLE IF NOT EXISTS anyonehome_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id TEXT UNIQUE NOT NULL,
    account_name TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- AnyoneHome Properties (linked to RealPage via external_id)
CREATE TABLE IF NOT EXISTS anyonehome_properties (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ah_property_id TEXT UNIQUE NOT NULL,
    account_id TEXT,
    property_name TEXT,
    preferred_id TEXT,
    realpage_site_id TEXT,
    listing_contact_email TEXT,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES anyonehome_accounts(account_id)
);

-- AnyoneHome Quotes (Rental quotes for prospects - key funnel data)
CREATE TABLE IF NOT EXISTS anyonehome_quotes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quote_id TEXT UNIQUE NOT NULL,
    ah_property_id TEXT NOT NULL,
    account_id TEXT,
    -- Guest/Prospect Information
    guest_name TEXT,
    guest_email TEXT,
    guest_phone TEXT,
    guest_mobile TEXT,
    -- Quote Details
    issued_on TEXT,
    created_by TEXT,
    apply_online_url TEXT,
    -- Property Info from Quote
    property_name TEXT,
    property_address TEXT,
    property_contact TEXT,
    -- Unit/Floorplan
    floorplan_name TEXT,
    floorplan_style TEXT,
    unit_number TEXT,
    -- Pricing
    base_rent REAL,
    total_rent REAL,
    deposit REAL,
    -- Lease Terms
    lease_term TEXT,
    move_in_date TEXT,
    -- Pet Info
    number_of_pets INTEGER,
    pet_types TEXT,
    -- Policies
    pet_policy TEXT,
    utility_notes TEXT,
    breed_restrictions TEXT,
    -- Status tracking
    quote_status TEXT,  -- 'issued', 'applied', 'converted', 'expired'
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ah_property_id) REFERENCES anyonehome_properties(ah_property_id)
);

-- AnyoneHome Funnel Metrics (aggregated conversion data)
CREATE TABLE IF NOT EXISTS anyonehome_funnel_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ah_property_id TEXT NOT NULL,
    unified_property_id TEXT,  -- Link to unified layer
    snapshot_date TEXT NOT NULL,
    period TEXT NOT NULL,  -- 'daily', 'weekly', 'monthly'
    -- Funnel Stages
    quotes_issued INTEGER DEFAULT 0,
    quotes_viewed INTEGER DEFAULT 0,
    applications_started INTEGER DEFAULT 0,
    applications_completed INTEGER DEFAULT 0,
    applications_approved INTEGER DEFAULT 0,
    leases_signed INTEGER DEFAULT 0,
    -- Conversion Rates
    quote_to_apply_rate REAL,
    apply_to_approve_rate REAL,
    approve_to_sign_rate REAL,
    overall_conversion_rate REAL,
    -- Time Metrics
    avg_days_quote_to_apply REAL,
    avg_days_apply_to_approve REAL,
    avg_days_approve_to_sign REAL,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(ah_property_id, snapshot_date, period),
    FOREIGN KEY (ah_property_id) REFERENCES anyonehome_properties(ah_property_id)
);

-- Indexes for AnyoneHome tables
CREATE INDEX IF NOT EXISTS idx_ah_properties_account ON anyonehome_properties(account_id);
CREATE INDEX IF NOT EXISTS idx_ah_properties_realpage ON anyonehome_properties(realpage_site_id);
CREATE INDEX IF NOT EXISTS idx_ah_quotes_property ON anyonehome_quotes(ah_property_id);
CREATE INDEX IF NOT EXISTS idx_ah_quotes_issued ON anyonehome_quotes(issued_on);
CREATE INDEX IF NOT EXISTS idx_ah_quotes_status ON anyonehome_quotes(quote_status);
CREATE INDEX IF NOT EXISTS idx_ah_funnel_property ON anyonehome_funnel_metrics(ah_property_id);
CREATE INDEX IF NOT EXISTS idx_ah_funnel_date ON anyonehome_funnel_metrics(snapshot_date);
"""


def init_database(db_path: Path, schema: str) -> None:
    """Initialize a database with the given schema."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(schema)
        conn.commit()
        print(f"✅ Initialized database: {db_path}")
    finally:
        conn.close()


def init_all_databases() -> None:
    """Initialize all three databases."""
    print("Initializing OwnerDashV2 databases...")
    print("=" * 50)
    
    init_database(YARDI_DB_PATH, YARDI_SCHEMA)
    init_database(REALPAGE_DB_PATH, REALPAGE_SCHEMA)
    init_database(UNIFIED_DB_PATH, UNIFIED_SCHEMA)
    
    print("=" * 50)
    print("✅ All databases initialized successfully!")
    print(f"\nDatabase locations:")
    print(f"  - Yardi:    {YARDI_DB_PATH}")
    print(f"  - RealPage: {REALPAGE_DB_PATH}")
    print(f"  - Unified:  {UNIFIED_DB_PATH}")


def get_connection(db_type: str) -> sqlite3.Connection:
    """Get a database connection by type."""
    db_map = {
        'yardi': YARDI_DB_PATH,
        'realpage': REALPAGE_DB_PATH,
        'unified': UNIFIED_DB_PATH,
    }
    
    if db_type not in db_map:
        raise ValueError(f"Unknown database type: {db_type}. Use 'yardi', 'realpage', or 'unified'")
    
    db_path = db_map[db_type]
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}. Run init_all_databases() first.")
    
    return sqlite3.connect(db_path)


if __name__ == "__main__":
    init_all_databases()
