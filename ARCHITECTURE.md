# OwnerDashV2 Architecture Documentation

**Version**: 1.0  
**Last Updated**: 2026-02-05  
**Author**: Auto-generated

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Data Flow Architecture](#data-flow-architecture)
3. [Database Schema](#database-schema)
4. [Property Configuration](#property-configuration)
5. [PMS Data Sources](#pms-data-sources)
6. [Field Requirements & Coverage](#field-requirements--coverage)
7. [API Endpoints](#api-endpoints)
8. [File Structure](#file-structure)

---

## System Overview

OwnerDashV2 is a **READ-ONLY** property management dashboard that aggregates data from multiple Property Management Systems (PMS) into a unified view.

### Supported PMS Systems

| PMS | Connection Type | Data Access |
|-----|-----------------|-------------|
| **RealPage** | REST API (Reports) + SOAP API (RPX Gateway) | Reports downloaded as Excel, parsed, stored in DB |
| **Yardi** | SOAP API | Real-time API calls |

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              EXTERNAL SYSTEMS                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────┐          ┌──────────────────┐                        │
│   │   RealPage API   │          │    Yardi API     │                        │
│   │  (Reports REST)  │          │     (SOAP)       │                        │
│   └────────┬─────────┘          └────────┬─────────┘                        │
│            │                              │                                  │
└────────────┼──────────────────────────────┼──────────────────────────────────┘
             │                              │
             ▼                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DATA INGESTION LAYER                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────────┐          ┌──────────────────────┐                │
│   │ batch_report_        │          │   yardi_client.py    │                │
│   │ downloader.py        │          │                      │                │
│   │                      │          │   - Real-time calls  │                │
│   │ - Creates instances  │          │   - GetUnitInfo      │                │
│   │ - Smart file scan    │          │   - GetResidents     │                │
│   │ - Downloads Excel    │          │   - GetLeases        │                │
│   └──────────┬───────────┘          └──────────┬───────────┘                │
│              │                                  │                            │
│              ▼                                  │                            │
│   ┌──────────────────────┐                     │                            │
│   │  report_parsers.py   │                     │                            │
│   │                      │                     │                            │
│   │ - parse_box_score()  │                     │                            │
│   │ - parse_rent_roll()  │                     │                            │
│   │ - parse_delinquency()│                     │                            │
│   │ - parse_activity()   │                     │                            │
│   │ - parse_monthly()    │                     │                            │
│   │ - parse_lease_exp()  │                     │                            │
│   └──────────┬───────────┘                     │                            │
│              │                                  │                            │
└──────────────┼──────────────────────────────────┼────────────────────────────┘
               │                                  │
               ▼                                  ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            DATABASE LAYER                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐     │
│   │ realpage_raw.db  │    │   yardi_raw.db   │    │   unified.db     │     │
│   │                  │    │                  │    │                  │     │
│   │ - box_score      │    │ - yardi_units    │    │ - unified_props  │     │
│   │ - rent_roll      │    │ - yardi_residents│    │ - unified_units  │     │
│   │ - delinquency    │    │ - yardi_leases   │    │ - unified_occ    │     │
│   │ - activity       │    │                  │    │ - unified_price  │     │
│   │ - monthly_summary│    │                  │    │ - unified_delinq │     │
│   └────────┬─────────┘    └────────┬─────────┘    └────────▲─────────┘     │
│            │                       │                       │                │
│            └───────────────────────┴───────────────────────┘                │
│                                    │                                        │
│                       sync_realpage_to_unified.py                           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API LAYER                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   FastAPI Application (app/main.py)                                         │
│   └── /api/v2/                                                              │
│       ├── GET /properties                    → List all properties          │
│       ├── GET /properties/{id}/occupancy     → Occupancy metrics            │
│       ├── GET /properties/{id}/exposure      → Exposure metrics             │
│       ├── GET /properties/{id}/pricing       → Pricing by floorplan         │
│       ├── GET /properties/{id}/delinquency   → Delinquency data             │
│       ├── GET /properties/{id}/leasing-funnel→ Marketing funnel             │
│       └── GET /properties/{id}/summary       → Combined dashboard           │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (React)                                  │
│   http://localhost:5173                                                      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow Architecture

### RealPage Data Flow

```
1. REPORT CREATION
   batch_report_downloader.py
   └── POST /reports/{reportId}/report-instances
       ├── Payload includes: property_id, date_range, report_type
       └── Returns: instance_id

2. FILE DISCOVERY (Smart Scanning)
   └── Scan file IDs starting from known max
       ├── Try download each file_id
       ├── Read Excel content to identify report type
       └── Match to pending instances

3. PARSING
   report_parsers.py
   └── Auto-detect report type from content
       ├── Box Score → parse_box_score()
       ├── Rent Roll → parse_rent_roll()
       ├── Delinquency → parse_delinquency()
       └── Returns: List[Dict] with structured data

4. RAW STORAGE
   import_reports.py
   └── INSERT INTO realpage_box_score / rent_roll / delinquency
       └── Database: app/db/data/realpage_raw.db

5. UNIFIED SYNC
   sync_realpage_to_unified.py
   └── Read from realpage_raw.db
       ├── Transform to unified schema
       └── INSERT INTO unified.db tables

6. API SERVING
   occupancy_service.py
   └── Check property PMS type
       ├── If RealPage + not in config → Read from unified.db
       └── If Yardi → Call Yardi API directly
```

### Yardi Data Flow

```
1. API REQUEST
   sync_yardi_to_unified.py (scheduled) OR occupancy_service.py (real-time)
   └── SOAP call to Yardi Voyager
       ├── GetPropertyConfigurations
       ├── GetUnitInformation
       ├── GetResidentsByStatus
       └── GetResidentLeaseCharges_Login

2. UNIFIED SYNC (sync_yardi_to_unified.py)
   └── Parse API responses
       ├── sync_properties() → unified_properties
       ├── sync_occupancy() → unified_occupancy_metrics
       ├── sync_pricing() → unified_pricing_metrics
       ├── sync_units() → unified_units
       └── sync_residents() → unified_residents

3. API SERVING
   occupancy_service.py
   └── Read from unified.db (if synced) OR call Yardi API (real-time)
```

---

## Database Schema

### realpage_raw.db Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `realpage_box_score` | Floorplan occupancy metrics | property_id, floorplan, total_units, occupied_units, avg_market_rent |
| `realpage_rent_roll` | Unit-level status | property_id, unit_number, status, market_rent, actual_rent |
| `realpage_delinquency` | Outstanding balances | property_id, unit_number, current_balance, balance_0_30, balance_31_60 |
| `realpage_activity` | Leasing activity events | property_id, activity_date, activity_type, unit_number |
| `realpage_monthly_summary` | Monthly aggregates | property_id, move_ins, move_outs, renewals |
| `realpage_units` | Unit master (from API) | site_id, unit_id, vacant, market_rent |
| `realpage_residents` | Resident data (from API) | site_id, resident_id, lease_status, balance |
| `realpage_leases` | Lease details (from API) | site_id, lease_id, rent_amount, lease_end_date |

### unified.db Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `unified_properties` | Property master | unified_property_id, name, pms_source |
| `unified_units` | Normalized units | unified_property_id, unit_number, status, market_rent |
| `unified_occupancy_metrics` | Occupancy snapshots | unified_property_id, total_units, occupied_units, physical_occupancy |
| `unified_pricing_metrics` | Pricing by floorplan | unified_property_id, floorplan, in_place_rent, asking_rent |
| `unified_delinquency` | Delinquency data | unified_property_id, unit_number, current_balance |
| `unified_residents` | Normalized residents | unified_property_id, unit_number, status, current_rent |
| `unified_leases` | Normalized leases | unified_property_id, unit_number, rent_amount |

---

## Property Configuration

### Currently Synced Properties (unified.db)

| Property ID | Name | PMS | Units | Occupancy |
|-------------|------|-----|-------|-----------|
| `nexus_east` | Nexus East | RealPage | 352 | 95.74% |
| `aspire_7th_grant` | Aspire 7th and Grant | RealPage | 178 | 93.26% |
| `parkside` | Parkside at Round Rock | RealPage | 432 | 86.81% |
| `edison_rino` | Edison at RiNo | RealPage | 277 | 85.92% |
| `ridian` | Ridian | RealPage | 123 | 56.91% |

### Configured in report_definitions.json (25 properties)

All properties use **PMC ID: 4248314** (Kairoi)

| Property Key | Property Name | Site ID |
|--------------|---------------|---------|
| `kalaco` | Kalaco | 5339721 |
| `7_east` | 7 East | 5481703 |
| `block_44` | Block 44 | 5473254 |
| `curate_orchard` | Curate at Orchard Town Center | 4682517 |
| `eden_keller_ranch` | Eden Keller Ranch | 5536209 |
| `harvest` | Harvest | 5507303 |
| `heights_interlocken` | Heights at Interlocken | 5558216 |
| `luna` | Luna | 5590740 |
| `nexus_east` | Nexus East | 5472172 |
| `park_17` | Park 17 | 4481243 |
| `parkside` | Parkside at Round Rock | 5536211 |
| `pearl_lantana` | Pearl Lantana | 5481704 |
| `slate` | Slate | 5486880 |
| `sloane` | Sloane | 5486881 |
| `stonewood` | Stonewood | 5481705 |
| `ten50` | Ten50 | 5581218 |
| `the_alcott` | The Alcott | 4996967 |
| `the_broadleaf` | The Broadleaf | 5286092 |
| `the_confluence` | The Confluence | 4832865 |
| `links_plum_creek` | The Links at Plum Creek | 5558220 |
| `the_pearl` | thePearl | 5114464 |
| `the_quinci` | theQuinci | 5286878 |
| `aspire_7th_grant` | Aspire 7th and Grant | 4779341 |
| `edison_rino` | Edison at RiNo | 4248319 |
| `ridian` | Ridian | 5446271 |

---

## PMS Data Sources

### RealPage Reports (REST API)

| Report | ID | Key | Status | Parser | DB Table |
|--------|-----|-----|--------|--------|----------|
| **Box Score** | 4238 | `446266C0-D572-4D8A-A6DA-310C0AE61037` | ✅ Working | `parse_box_score()` | `realpage_box_score` |
| **Rent Roll** | 4043 | `A6F61299-E960-4235-9DC2-44D2C2EF4F99` | ✅ Working | `parse_rent_roll()` | `realpage_rent_roll` |
| **Delinquency** | 4260 | `89A3C427-BE71-4A05-9D2B-BDF3923BF756` | ✅ Working | `parse_delinquency()` | `realpage_delinquency` |
| **Activity Report** | 3837 | `B29B7C76-04B8-4D6C-AABC-62127F0CAE63` | ✅ Working | `parse_activity()` | `realpage_activity` |
| **Monthly Summary** | 3877 | `E41626AB-EC0F-4F6C-A6EA-D7A93909AA9B` | ✅ Working | `parse_monthly_summary()` | `realpage_monthly_summary` |
| **Lease Expiration** | 3838 | `89545A3A-C28A-49CC-8791-396AE71AB422` | ✅ Working | `parse_lease_expiration()` | `realpage_lease_expirations` |

### RealPage RPX Gateway (SOAP API)

| Endpoint | Data Provided | Status |
|----------|---------------|--------|
| `getSiteList` | Property info | ✅ Available |
| `getBuildings` | Building structures | ✅ Available |
| `unitlist` | Unit details, vacancy, market rent | ✅ Available |
| `getResidentListInfo` | All residents with status | ✅ Available |
| `getResident` | Current residents only | ✅ Available |
| `getLeaseInfo` | Active lease contracts | ✅ Available |
| `getRentableItems` | Amenities, parking, storage | ✅ Available |

### Yardi SOAP API

| Endpoint | Data Provided | Status |
|----------|---------------|--------|
| `GetPropertyConfigurations` | Property list | ✅ Available |
| `GetUnitInformation` | Unit details | ✅ Available |
| `GetResidentsByStatus` | Residents by status | ✅ Available |
| `GetResidentLeaseCharges_Login` | Lease charges | ✅ Available |
| `AvailableUnits_Login` | Available units | ✅ Available |
| `GetYardiGuestActivity_Login` | Guest/prospect activity | ⚠️ Limited |

---

## Field Requirements & Coverage

### Module 1: Occupancy & Leasing

| Dashboard Field | RealPage Source | Yardi Source | Status |
|-----------------|-----------------|--------------|--------|
| **Physical Occupancy %** | Box Score: `occupancy_pct` | `unitlist` calculation | ✅ Both |
| **Leased %** | Box Score: `leased_pct` | `unitlist` + `getResidentListInfo` | ✅ Both |
| **Total Units** | Box Score: `total_units` | `unitlist` count | ✅ Both |
| **Occupied Units** | Box Score: `occupied_units` | `unitlist` where `Vacant=F` | ✅ Both |
| **Vacant Units** | Box Score: `vacant_units` | `unitlist` where `Vacant=T` | ✅ Both |
| **Preleased Vacant** | Box Score: `vacant_leased` | Future lease status | ✅ Both |
| **Vacant Ready** | Rent Roll: status parsing | `UnitMadeReadyDate` check | ⚠️ Partial |
| **Vacant Not Ready** | Rent Roll: status parsing | `UnitMadeReadyDate` check | ⚠️ Partial |
| **Aged Vacancy (90+)** | Rent Roll: days calculation | `AvailableDate` calculation | ⚠️ Partial |
| **On Notice** | Box Score: `occupied_on_notice` | `getResidentListInfo` Notice status | ✅ Both |
| **Exposure 30 Days** | Box Score: `exposure_pct` | Calculated | ✅ Both |
| **Exposure 60 Days** | Calculated | Calculated | ✅ Both |

### Module 2: Leasing Funnel

| Dashboard Field | RealPage Source | Yardi Source | Status |
|-----------------|-----------------|--------------|--------|
| **Leads** | Activity Report | Guest Activity API | ⚠️ RealPage only |
| **Tours** | Activity Report: Visit type | Guest Activity API | ⚠️ Limited |
| **Applications** | `getResidentListInfo` Applicant | Applicant status | ✅ Both |
| **Lease Signs** | `getResidentListInfo` Approved | Approved Applicant | ✅ Both |
| **Lead/Tour Conversion** | Calculated | Calculated | ⚠️ Limited |
| **Tour/App Conversion** | Calculated | Calculated | ⚠️ Limited |
| **App/Lease Conversion** | Calculated | Calculated | ✅ Both |

### Module 3: Pricing

| Dashboard Field | RealPage Source | Yardi Source | Status |
|-----------------|-----------------|--------------|--------|
| **In-Place Rent** | Box Score: `avg_actual_rent` | Lease charges | ✅ Both |
| **In-Place $/SF** | Calculated | Calculated | ✅ Both |
| **Asking Rent** | Box Score: `avg_market_rent` | `unitlist`: `MarketRent` | ✅ Both |
| **Asking $/SF** | Calculated | Calculated | ✅ Both |
| **Rent Growth %** | Calculated | Calculated | ✅ Both |
| **By Floorplan** | Box Score grouped | `unitlist` grouped | ✅ Both |

### Module 4: Delinquency

| Dashboard Field | RealPage Source | Yardi Source | Status |
|-----------------|-----------------|--------------|--------|
| **Total Delinquent** | Delinquency Report | `getResidentListInfo`: balance | ✅ Both |
| **0-30 Days** | Delinquency: `balance_0_30` | A/R Aging report | ⚠️ RealPage only |
| **31-60 Days** | Delinquency: `balance_31_60` | A/R Aging report | ⚠️ RealPage only |
| **61-90 Days** | Delinquency: `balance_61_90` | A/R Aging report | ⚠️ RealPage only |
| **90+ Days** | Delinquency: `balance_over_90` | A/R Aging report | ⚠️ RealPage only |
| **Prepaid** | Delinquency: `prepaid` | Balance < 0 | ⚠️ RealPage only |

### Module 5: Move-In/Out Activity

| Dashboard Field | RealPage Source | Yardi Source | Status |
|-----------------|-----------------|--------------|--------|
| **Move-Ins (MTD)** | Monthly Summary: `move_ins` | `getResidentListInfo`: moveindate | ✅ Both |
| **Move-Outs (MTD)** | Monthly Summary: `move_outs` | `getResidentListInfo`: moveoutdate | ✅ Both |
| **Net Absorption** | Calculated | Calculated | ✅ Both |
| **Renewals** | Monthly Summary: `renewals` | `getLeaseInfo`: NextLeaseID | ✅ Both |
| **Renewal %** | Calculated | Calculated | ✅ Both |

### Coverage Summary

| Module | RealPage | Yardi | Notes |
|--------|----------|-------|-------|
| **Occupancy** | ✅ 100% | ✅ 100% | Full coverage both |
| **Leasing Funnel** | ⚠️ 70% | ⚠️ 50% | Tours limited, needs CrossFire for RealPage |
| **Pricing** | ✅ 100% | ✅ 100% | Full coverage both |
| **Delinquency** | ✅ 100% | ⚠️ 30% | Aging buckets RealPage only |
| **Activity** | ✅ 90% | ⚠️ 60% | RealPage reports more detailed |

---

## API Endpoints

### Base URL: `http://localhost:8000/api/v2`

| Endpoint | Method | Description | Data Source |
|----------|--------|-------------|-------------|
| `/properties` | GET | List all properties | unified.db + Yardi API |
| `/properties/{id}/occupancy` | GET | Occupancy metrics | unified.db (RealPage) / Yardi API |
| `/properties/{id}/exposure` | GET | Exposure & notices | unified.db / Yardi API |
| `/properties/{id}/pricing` | GET | Pricing by floorplan | unified.db / Yardi API |
| `/properties/{id}/delinquency` | GET | Delinquency data | unified.db |
| `/properties/{id}/leasing-funnel` | GET | Marketing funnel | Excel imports / API |
| `/properties/{id}/summary` | GET | Combined dashboard | All sources |
| `/properties/{id}/units/raw` | GET | Raw unit data | unified.db / Yardi API |
| `/properties/{id}/residents/raw` | GET | Raw resident data | unified.db / Yardi API |

---

## File Structure

```
OwnerDashV2/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py           # Main API endpoints
│   │   │   ├── portfolio.py        # Portfolio aggregation
│   │   │   └── imports.py          # Excel imports
│   │   ├── clients/
│   │   │   ├── yardi_client.py     # Yardi SOAP API client
│   │   │   └── realpage_client.py  # RealPage RPX client
│   │   ├── db/
│   │   │   ├── data/
│   │   │   │   ├── realpage_raw.db # RealPage report data
│   │   │   │   ├── yardi_raw.db    # Yardi raw data
│   │   │   │   └── unified.db      # Normalized data
│   │   │   ├── schema.py           # Database schemas
│   │   │   └── sync_realpage_to_unified.py  # Sync script
│   │   ├── models/
│   │   │   ├── __init__.py         # Pydantic models
│   │   │   └── unified.py          # Unified data models
│   │   ├── property_config/
│   │   │   └── properties.py       # Property registry
│   │   ├── services/
│   │   │   ├── occupancy_service.py # Occupancy calculations
│   │   │   └── pricing_service.py   # Pricing calculations
│   │   ├── main.py                 # FastAPI app
│   │   └── config.py               # Settings
│   ├── batch_report_downloader.py  # RealPage report automation
│   ├── report_parsers.py           # Excel report parsers
│   ├── import_reports.py           # DB import logic
│   ├── report_definitions.json     # Report configs & properties
│   └── realpage_token.json         # API auth token
├── frontend/
│   └── src/                        # React frontend
├── Data_Definitions_and_Sources/
│   └── REALPAGE_DATA_MAPPING.md    # Field mapping docs
├── REALPAGE_FIELD_MAPPING.md       # API field reference
└── ARCHITECTURE.md                 # This file
```

---

## Data Refresh Workflow

### Manual Refresh (Current)

```bash
# 1. Download reports for all properties
cd /Users/barak.b/Venn/OwnerDashV2/backend
python3 batch_report_downloader.py --property "Nexus East" --reports box_score rent_roll delinquency

# 2. Sync to unified database
python3 app/db/sync_realpage_to_unified.py

# 3. API automatically serves fresh data
```

### Token Management

- Token stored in: `realpage_token.json`
- Expires: ~1 hour (session-based)
- Refresh: Copy from RealPage browser session

---

## Known Limitations

1. **Delinquency Balances**: Currently returning $0 - parser column mapping needs review
2. **Tour Data**: Requires RealPage CrossFire API (not available)
3. **Yardi Funnel**: Guest Activity API returns limited data
4. **Token Expiration**: Manual refresh required

---

*Document maintained in: `/OwnerDashV2/ARCHITECTURE.md`*
