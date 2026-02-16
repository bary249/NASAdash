# Report Data Migration Plan: realpage_raw.db → unified.db

## Architecture Principle

```
ETL Pipeline → Pull from PMSs (RP, Yardi), APIs, Reports
Sync Scripts → Map & push ALL raw data into unified.db
UI/API Layer → Read from unified.db ONLY
```

**Why:** Users will have Yardi + RealPage properties side by side in multi-prop mode.
All data must come from a single unified schema regardless of PMS source.

---

## Current State

### ✅ Already Unified (in unified.db)
| Unified Table | Source (RP) | Source (Yardi) | Used By |
|---|---|---|---|
| `unified_properties` | SOAP API | SOAP API | Property list, all lookups |
| `unified_units` | SOAP API | SOAP API | Raw units, occupancy calc |
| `unified_residents` | SOAP API | SOAP API | Raw residents, exposure calc |
| `unified_occupancy_metrics` | box_score sync | unit/resident calc | Occupancy tab |
| `unified_pricing_metrics` | box_score + rent_roll | unit info + lease charges | Pricing tab |
| `unified_leasing_metrics` | box_score sync | guest activity | Funnel summary |
| `unified_risk_scores` | computed | computed | Risk module |
| `imported_leasing_activity` | Excel import | — | Funnel detail |

### ❌ Still Reading from realpage_raw.db (needs migration)

| # | UI Feature | Raw Table(s) Read | Route(s) | Priority |
|---|---|---|---|---|
| 1 | **Leasing Activity (funnel fallback)** | `realpage_activity` | `GET /leasing-funnel` | High |
| 2 | **Delinquency** | `realpage_delinquency` | `GET /delinquency` | High |
| 3 | **Lease Expirations (detail)** | `realpage_leases`, `realpage_lease_expiration_renewal` | `GET /lease-expirations`, `GET /expirations` | High |
| 4 | **Tradeouts** | `realpage_leases`, `realpage_units` | `GET /tradeouts` | High |
| 5 | **Renewals** | `realpage_lease_expiration_renewal`, `realpage_leases` | `GET /renewals` | High |
| 6 | **Financials** | `realpage_monthly_transaction_summary`, `realpage_monthly_transaction_detail` | `GET /financials` | High |
| 7 | **Availability** | `realpage_rent_roll`, `realpage_projected_occupancy` | `GET /availability` | Medium |
| 8 | **Occupancy Forecast** | `realpage_projected_occupancy` | `GET /occupancy-forecast` | Medium |
| 9 | **Box Score by Floorplan** | `realpage_box_score` | `GET /box-score/floorplan` | Medium |
| 10 | **Box Score by Bedroom** | `realpage_box_score`, `unified_units` | `GET /box-score/bedroom` | Medium |
| 11 | **Maintenance / Make-Ready** | `realpage_make_ready`, closed turns | `GET /maintenance` | Medium |
| 12 | **Lost Rent / Loss-to-Lease** | `realpage_lost_rent_summary` | `GET /lost-rent` | Medium |
| 13 | **Move-Out Reasons** | `realpage_move_out_reasons` | `GET /move-out-reasons` | Medium |
| 14 | **Advertising Source** | `realpage_advertising_source` | `GET /advertising-sources` | Medium |
| 15 | **Shows/Tours by Date** | `realpage_activity` | `GET /shows` | Low |
| 16 | **Amenities** | `realpage_rentable_items` | `GET /amenities` | Low |

---

## New Unified Tables Needed

Each table uses `unified_property_id` (not PMS-specific site_id) and standardized column names.

### 1. `unified_leases`
Replaces: `realpage_leases` (SOAP), Yardi lease charges
```sql
CREATE TABLE IF NOT EXISTS unified_leases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,          -- 'realpage' | 'yardi'
    unit_number TEXT,
    resident_name TEXT,
    status TEXT,                        -- 'Current', 'Former', 'Future', etc.
    lease_type TEXT,                    -- 'First (Lease)', 'Renewal', etc.
    rent_amount REAL,
    lease_start_date TEXT,             -- ISO format YYYY-MM-DD
    lease_end_date TEXT,
    move_in_date TEXT,
    move_out_date TEXT,
    lease_term TEXT,
    next_lease_id TEXT,                -- for renewal tracking
    floorplan TEXT,
    sqft INTEGER,
    snapshot_date TEXT NOT NULL,
    UNIQUE(unified_property_id, unit_number, lease_start_date, resident_name)
);
```

### 2. `unified_activity`
Replaces: `realpage_activity`, Yardi guest activity
```sql
CREATE TABLE IF NOT EXISTS unified_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    resident_name TEXT,
    activity_type TEXT,                -- Normalized: 'lead', 'tour', 'application', 'lease_sign', etc.
    activity_type_raw TEXT,            -- Original PMS-specific type
    activity_date TEXT,                -- ISO format
    leasing_agent TEXT,
    source TEXT,                       -- Lead source / advertising source
    snapshot_date TEXT NOT NULL
);
```

### 3. `unified_delinquency`
Replaces: `realpage_delinquency`
```sql
CREATE TABLE IF NOT EXISTS unified_delinquency (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    unit_number TEXT,
    resident_name TEXT,
    total_balance REAL,
    current_charges REAL,
    days_30 REAL,
    days_60 REAL,
    days_90 REAL,
    days_90_plus REAL,
    prepaid REAL,
    move_out_date TEXT,
    status TEXT,                        -- 'current_resident', 'former_resident'
    snapshot_date TEXT NOT NULL
);
```

### 4. `unified_financials`
Replaces: `realpage_monthly_transaction_summary`, `realpage_monthly_transaction_detail`
```sql
CREATE TABLE IF NOT EXISTS unified_financial_summary (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    fiscal_period TEXT,                -- 'YYYY-MM'
    gross_potential_rent REAL,
    vacancy_loss REAL,
    concessions REAL,
    net_rent REAL,
    other_income REAL,
    total_income REAL,
    total_expenses REAL,
    noi REAL,
    snapshot_date TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS unified_financial_detail (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    fiscal_period TEXT,
    transaction_group TEXT,            -- 'income', 'expense', 'loss', etc.
    transaction_code TEXT,
    description TEXT,
    ytd_last_month REAL,
    this_month REAL,
    ytd_through_month REAL,
    snapshot_date TEXT NOT NULL
);
```

### 5. `unified_lease_expirations`
Replaces: `realpage_lease_expiration_renewal`
```sql
CREATE TABLE IF NOT EXISTS unified_lease_expirations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    unit_number TEXT,
    floorplan TEXT,
    resident_name TEXT,
    lease_end_date TEXT,
    decision TEXT,                      -- 'Renewed', 'Notice to Vacate', 'Undecided', etc.
    actual_rent REAL,                  -- Prior rent
    new_rent REAL,                     -- Renewal rent (if renewed)
    new_lease_start TEXT,
    new_lease_term INTEGER,
    report_date TEXT NOT NULL
);
```

### 6. `unified_maintenance`
Replaces: `realpage_make_ready`, closed turns
```sql
CREATE TABLE IF NOT EXISTS unified_maintenance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    unit_number TEXT,
    sqft INTEGER,
    days_vacant INTEGER,
    date_vacated TEXT,
    date_due TEXT,
    num_work_orders INTEGER,
    status TEXT,                        -- 'open', 'closed'
    snapshot_date TEXT NOT NULL
);
```

### 7. `unified_move_out_reasons`
Replaces: `realpage_move_out_reasons`
```sql
CREATE TABLE IF NOT EXISTS unified_move_out_reasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    resident_type TEXT,                -- 'Former Resident', 'Notice to Vacate'
    category TEXT,
    category_count INTEGER,
    category_pct REAL,
    reason TEXT,
    reason_count INTEGER,
    reason_pct REAL,
    date_range TEXT,
    snapshot_date TEXT NOT NULL
);
```

### 8. `unified_advertising_sources`
Replaces: `realpage_advertising_source`
```sql
CREATE TABLE IF NOT EXISTS unified_advertising_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    source_name TEXT,
    new_prospects INTEGER,
    visits INTEGER,
    leases INTEGER,
    net_leases INTEGER,
    cancelled_denied INTEGER,
    prospect_to_lease_pct REAL,
    visit_to_lease_pct REAL,
    date_range TEXT,
    timeframe_tag TEXT,                -- 'mtd', 'ytd', 'l30', etc.
    snapshot_date TEXT NOT NULL
);
```

### 9. `unified_projected_occupancy`
Replaces: `realpage_projected_occupancy`
```sql
CREATE TABLE IF NOT EXISTS unified_projected_occupancy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    week_ending TEXT,
    total_units INTEGER,
    occupied_begin INTEGER,
    pct_occupied_begin REAL,
    scheduled_move_ins INTEGER,
    scheduled_move_outs INTEGER,
    occupied_end INTEGER,
    pct_occupied_end REAL,
    snapshot_date TEXT NOT NULL
);
```

### 10. `unified_lost_rent`
Replaces: `realpage_lost_rent_summary`
```sql
CREATE TABLE IF NOT EXISTS unified_lost_rent (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    unit_number TEXT,
    market_rent REAL,
    lease_rent REAL,
    rent_charged REAL,
    loss_to_rent REAL,
    gain_to_rent REAL,
    vacancy_current REAL,
    lost_rent_not_charged REAL,
    move_in_date TEXT,
    move_out_date TEXT,
    fiscal_period TEXT,
    snapshot_date TEXT NOT NULL
);
```

### 11. `unified_amenities`
Replaces: `realpage_rentable_items`
```sql
CREATE TABLE IF NOT EXISTS unified_amenities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unified_property_id TEXT NOT NULL,
    pms_source TEXT NOT NULL,
    item_type TEXT,
    item_description TEXT,
    monthly_charge REAL,
    status TEXT,                        -- 'Available', 'Rented', etc.
    unit_number TEXT,
    resident_name TEXT,
    snapshot_date TEXT NOT NULL
);
```

---

## Implementation Order

### Phase 1: High Priority (blocks multi-PMS)
1. `unified_leases` — needed by tradeouts, renewals, expirations, availability
2. `unified_delinquency` — standalone, high visibility
3. `unified_financials` — standalone, high visibility
4. `unified_lease_expirations` — needed by expirations tab, renewals

For each table:
- **Step A:** Add CREATE TABLE to `schema.py` UNIFIED_SCHEMA
- **Step B:** Add sync function in `sync_realpage_to_unified.py` (map site_id → unified_property_id)
- **Step C:** Stub sync function in `sync_yardi_to_unified.py` (empty for now, filled when Yardi data available)
- **Step D:** Update route to read from unified table instead of raw table
- **Step E:** Remove `get_pms_config` / `REALPAGE_DB_PATH` dependency from that route

### Phase 2: Medium Priority
5. `unified_activity` — leasing funnel detail, shows
6. `unified_projected_occupancy` — availability, forecast
7. `unified_maintenance` — make-ready pipeline
8. `unified_move_out_reasons`
9. `unified_advertising_sources`
10. `unified_lost_rent`
11. `unified_amenities`

### Phase 3: Cleanup
- Remove all `REALPAGE_DB_PATH` imports from routes.py
- Remove all `get_pms_config` calls from routes.py
- Remove `realpage_raw.db` dependency from UI read path entirely
- `realpage_raw.db` becomes ETL-internal only (write target, not read source for UI)

---

## Sync Script Pattern

Each sync function follows this pattern:
```python
def sync_TABLE_to_unified(site_id: str, unified_property_id: str):
    """Read from realpage_raw.db, write to unified.db."""
    raw_conn = sqlite3.connect(REALPAGE_DB_PATH)
    uni_conn = sqlite3.connect(UNIFIED_DB_PATH)
    
    rows = raw_conn.execute("SELECT ... FROM realpage_TABLE WHERE site_id = ?", (site_id,))
    
    uni_conn.execute("DELETE FROM unified_TABLE WHERE unified_property_id = ?", (unified_property_id,))
    for row in rows:
        uni_conn.execute("INSERT INTO unified_TABLE (...) VALUES (...)", 
                        (unified_property_id, 'realpage', ...normalized_fields...))
    
    uni_conn.commit()
```

When Yardi sync is added later, same pattern:
```python
def sync_yardi_TABLE_to_unified(yardi_property_id: str, unified_property_id: str):
    """Read from yardi_raw.db, write to unified.db."""
    # Same target table, different source mapping
```
