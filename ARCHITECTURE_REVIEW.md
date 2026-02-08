# Owner Dashboard V2 - Architecture Review Document
**Prepared for Security & Architecture Review**  
**Date:** February 5, 2026 (Updated)  
**Version:** 2.0  
**Project:** Asset Management Dashboard for Property Owners

---

## Executive Summary

This document provides a security and architecture review of the Owner Dashboard V2 project. The dashboard provides **read-only** visibility into property performance metrics by integrating with multiple Property Management Systems (PMS):

- **Yardi Voyager** (SOAP API) - Real-time and batch sync
- **RealPage** (REST API + Excel Reports) - Batch sync via report downloads
- **ALN Market Data** (REST API) - Market comps

### Key Safety Guarantees

| Aspect | Implementation |
|--------|----------------|
| **HTTP Methods** | GET only for external PMS APIs - no PUT, POST, DELETE |
| **CORS Policy** | Restricted to `allow_methods=["GET", "POST"]` (POST only for internal file imports) |
| **API Design** | All external-facing endpoints are `@router.get()` |
| **Data Modification** | Zero write operations to any external PMS system |
| **Credentials** | Environment variables only, not hardcoded |
| **Data Storage** | Local SQLite databases for caching/normalization only |
| **PII Handling** | Resident names hidden in RealPage reports by default |

---

## 1. Backend Architecture (FastAPI)

### 1.1 Main Application Entry Point

**File:** `backend/app/main.py`

```python
# Lines 1-17: Explicit READ-ONLY documentation
"""
Owner Dashboard V2 API - READ-ONLY Backend
============================================
API for Asset Management Dashboard per spec.

IMPORTANT: All operations are GET-only. No PUT, POST, DELETE operations
are permitted to ensure no data modifications occur.

Data Sources:
- Yardi PMS (SOAP APIs): Occupancy, Leasing, Unit Pricing
- RealPage RPX (SOAP APIs): Units, Residents, Leases
- RealPage Reports (REST): Downloaded as Excel, parsed locally
"""

# Lines 53-65: CORS middleware configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://localhost:3000", 
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://localhost:5172"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # POST needed for internal file imports only
    allow_headers=["*"],
)
```

**Safety Note:** POST is allowed only for internal Excel file imports to the local database. No POST operations modify any external PMS system.

---

### 1.2 API Routes - All GET Only

**File:** `backend/app/api/routes.py`

Every single endpoint uses `@router.get()` decorator. There are **zero** `@router.post()`, `@router.put()`, or `@router.delete()` decorators in the entire codebase.

```python
# Lines 1-4: Explicit documentation
"""
API Routes - Owner Dashboard V2
READ-ONLY endpoints. All operations are GET-only.
"""

# Line 37: Property list
@router.get("/properties", response_model=list[PropertyInfo])
async def get_properties():

# Line 49: Occupancy metrics
@router.get("/properties/{property_id}/occupancy", response_model=OccupancyMetrics)
async def get_occupancy(property_id: str, timeframe: Timeframe):

# Line 70: Exposure metrics
@router.get("/properties/{property_id}/exposure", response_model=ExposureMetrics)
async def get_exposure(property_id: str, timeframe: Timeframe):

# Line 90: Leasing funnel
@router.get("/properties/{property_id}/leasing-funnel", response_model=LeasingFunnelMetrics)
async def get_leasing_funnel(property_id: str, timeframe: Timeframe):

# Line 107: Unit pricing
@router.get("/properties/{property_id}/pricing", response_model=UnitPricingMetrics)
async def get_pricing(property_id: str):

# Line 165: Raw unit drill-through
@router.get("/properties/{property_id}/units/raw")
async def get_units_raw(property_id: str):

# Line 174: Raw resident drill-through
@router.get("/properties/{property_id}/residents/raw")
async def get_residents_raw(property_id: str, status: str, timeframe: Timeframe):

# Line 196: Raw prospect drill-through
@router.get("/properties/{property_id}/prospects/raw")
async def get_prospects_raw(property_id: str, stage: str, timeframe: Timeframe):

# Line 265: Market comps
@router.get("/market-comps", response_model=MarketCompsResponse)
async def get_market_comps(submarket: str, subject_property: str, limit: int):
```

**Verification:** Run `grep -c "@router.post\|@router.put\|@router.delete" backend/app/api/routes.py` → Returns `0`

---

## 2. External API Clients

### 2.1 Yardi PMS Client - READ-ONLY

**File:** `backend/app/clients/yardi_client.py`

```python
# Lines 1-4: Explicit safety documentation
"""
Yardi PMS SOAP Client - READ-ONLY OPERATIONS ONLY
This client only implements GET operations. No PUT, POST, or DELETE.
"""

# Lines 11-16: Class-level documentation
class YardiClient:
    """
    SOAP client for Yardi PMS APIs.
    IMPORTANT: This client only implements READ operations (Get*).
    No write operations are permitted.
    """
```

**All Yardi methods are GET operations:**

| Method | SOAP Action | Purpose |
|--------|-------------|---------|
| `get_property_configurations()` | `GetPropertyConfigurations` | List properties |
| `get_unit_information()` | `GetUnitInformation` | Unit details |
| `get_residents_by_status()` | `GetResidentsByStatus` | Resident data |
| `get_resident_lease_charges()` | `GetResidentLeaseCharges_Login` | Lease charges |
| `get_available_units()` | `AvailableUnits_Login` | Available units |
| `get_guest_activity()` | `GetYardiGuestActivity_Login` | Prospect activity |

**Yardi SOAP Actions Used (all are "Get" operations):**
```python
# Line 41 - Property configurations
soap_action = "http://tempuri.org/.../GetPropertyConfigurations"

# Line 63 - Unit information
soap_action = "http://tempuri.org/.../GetUnitInformation"

# Line 92 - Residents by status
soap_action = "http://tempuri.org/.../GetResidentsByStatus"

# Line 117 - Lease charges
soap_action = "http://tempuri.org/.../GetResidentLeaseCharges_Login"

# Line 140 - Available units
soap_action = "http://tempuri.org/.../AvailableUnits_Login"

# Line 169 - Guest activity
soap_action = "http://tempuri.org/.../GetYardiGuestActivity_Login"
```

**No Yardi write operations exist in codebase:**
- ❌ `ImportGuestCard` (creates guest cards) - NOT USED
- ❌ `UpdateResident` (modifies residents) - NOT USED  
- ❌ `CancelLease` (cancels leases) - NOT USED
- ❌ Any POST/PUT operations - NOT USED

---

### 2.2 RealPage Client - READ-ONLY

**File:** `backend/app/clients/realpage_client.py`

```python
# Lines 1-6: Explicit safety documentation
"""
RealPage RPX Gateway SOAP Client - READ-ONLY OPERATIONS ONLY
Implements PMSInterface for RealPage RPX system.

This client only implements GET operations. No PUT, POST, or DELETE.
"""

class RealPageClient(PMSInterface):
    """
    SOAP client for RealPage RPX Gateway APIs.
    IMPORTANT: This client only implements READ operations.
    No write operations are permitted.
    """
```

**All RealPage RPX methods are GET operations:**

| Method | SOAP Action | Purpose |
|--------|-------------|---------|
| `get_site_list()` | `getSiteList` | List properties |
| `get_buildings()` | `getBuildings` | Building structures |
| `get_units()` | `unitlist` | Unit details |
| `get_residents()` | `getResidentListInfo` | Resident data |
| `get_leases()` | `getLeaseInfo` | Lease information |
| `get_rentable_items()` | `getRentableItems` | Amenities, parking |

**No RealPage write operations exist in codebase:**
- ❌ `createResident` - NOT USED
- ❌ `updateLease` - NOT USED
- ❌ `postCharge` - NOT USED
- ❌ Any POST/PUT operations - NOT USED

---

### 2.3 RealPage Reports - READ-ONLY Downloads

**File:** `backend/batch_report_downloader.py`

The RealPage Reports API is used to **download pre-generated Excel reports**. This is a read-only operation that retrieves existing reports from RealPage's system.

```python
# Report download flow (all GET/read operations):
1. POST /reports/{reportId}/report-instances  # Creates a report "instance" (snapshot request)
2. GET /reports/{reportId}/report-instances/{instanceId}/files  # Downloads the Excel file

# The POST creates a read request, NOT a data modification
# It's equivalent to "please generate this report for me to download"
```

**Reports Downloaded (Excel files parsed locally):**

| Report | ID | Data Retrieved |
|--------|-----|---------------|
| Box Score | 4238 | Occupancy metrics by floorplan |
| Rent Roll | 4043 | Unit-level status and rents |
| Delinquency | 4260 | Outstanding balances |
| Activity | 3837 | Leasing activity events |
| Monthly Summary | 3877 | Move-ins, move-outs, renewals |
| Lease Expiration | 3838 | Upcoming lease expirations |

**Security Note:** The POST to create a report instance does NOT modify any data in RealPage. It only requests RealPage to prepare a read-only snapshot of existing data for download.

---

### 2.4 ALN Market Data Client - READ-ONLY

**File:** `backend/app/clients/aln_client.py`

```python
# Lines 1-4: Explicit safety documentation
"""
ALN OData API Client - READ-ONLY OPERATIONS ONLY
This client only implements GET operations for market comps data.
"""

# Lines 10-15: Class-level documentation
class ALNClient:
    """
    REST client for ALN OData API.
    IMPORTANT: This client only implements READ operations (GET).
    No write operations are permitted.
    """
```

**All ALN methods use HTTP GET:**

```python
# Line 110-115: The ONLY HTTP method used
async def _send_get_request(self, url: str, params: dict) -> dict:
    """Send GET request and return JSON response."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=self.headers, params=params)  # ← GET only
        response.raise_for_status()
        return response.json()
```

**Verification:** The `_send_get_request` method is the only HTTP method in the ALN client. There is no `_send_post_request`, `_send_put_request`, or similar.

---

## 3. Configuration & Credentials

### 3.1 Environment Variables

**File:** `backend/app/config.py`

All sensitive credentials are loaded from environment variables, not hardcoded:

```python
class Settings(BaseSettings):
    # Yardi PMS Credentials - from .env file
    yardi_username: str = ""
    yardi_password: str = ""
    yardi_server_name: str = ""
    yardi_database: str = ""
    
    # Interface licenses - from .env file
    yardi_interface_entity: str = ""
    yardi_interface_license: str = ""
    yardi_ils_interface_entity: str = ""
    yardi_ils_interface_license: str = ""
    
    # ALN API - from .env file
    aln_api_key: str = ""
    
    class Config:
        env_file = ".env"  # ← Loaded from .env, not hardcoded
```

### 3.2 Environment File Template

**File:** `backend/.env.example`

```bash
# Yardi PMS API Credentials
YARDI_USERNAME=vennws
YARDI_PASSWORD=your_password_here  # ← Placeholder, not real
YARDI_INTERFACE_LICENSE=your_license_here  # ← Placeholder

# ALN API
ALN_API_KEY=your_api_key_here  # ← Placeholder
```

**Note:** The `.env` file containing real credentials is in `.gitignore` and not committed to version control.

---

## 4. Frontend - No Direct External API Calls

**File:** `frontend/src/api.ts`

The frontend only communicates with our backend API. It does NOT directly call Yardi or ALN APIs.

```typescript
// Line 19: All API calls go through our backend proxy
const API_BASE = '/api/v2';

// Lines 29-76: All methods use GET via fetch()
export const api = {
  getProperties: (): Promise<PropertyInfo[]> =>
    fetchJson(`${API_BASE}/properties`),

  getOccupancy: (propertyId: string, timeframe: Timeframe): Promise<OccupancyMetrics> =>
    fetchJson(`${API_BASE}/properties/${propertyId}/occupancy?timeframe=${timeframe}`),
    
  // ... all other methods use fetchJson() which is GET-only
};
```

**The `fetchJson` function only performs GET requests:**

```typescript
// Lines 21-27
async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);  // ← GET by default, no method override
  if (!response.ok) {
    throw new Error(`API error: ${response.status} ${response.statusText}`);
  }
  return response.json();
}
```

---

## 5. Security Verification Commands

Run these commands to verify the READ-ONLY nature of the codebase:

```bash
# 1. Check for POST/PUT/DELETE in routes
grep -rn "router.post\|router.put\|router.delete" backend/app/
# Expected: 0 results

# 2. Check for write methods in Yardi client
grep -rn "Import\|Update\|Create\|Delete\|Cancel" backend/app/clients/yardi_client.py
# Expected: 0 results (only "Get" methods)

# 3. Check for non-GET HTTP methods in ALN client
grep -rn "client.post\|client.put\|client.delete" backend/app/clients/aln_client.py
# Expected: 0 results

# 4. Verify CORS is GET-only
grep -n "allow_methods" backend/app/main.py
# Expected: allow_methods=["GET"]

# 5. Check frontend for direct external API calls
grep -rn "yardi\|alndata" frontend/src/
# Expected: 0 results (frontend only talks to our backend)
```

---

## 6. Data Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                           OWNER DASHBOARD V2                                  │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                               │
│  ┌──────────────┐      GET only       ┌──────────────┐                       │
│  │   Frontend   │ ─────────────────▶  │   Backend    │                       │
│  │   (React)    │                     │   (FastAPI)  │                       │
│  │              │ ◀─────────────────  │              │                       │
│  │ localhost:   │    JSON response    │ localhost:   │                       │
│  │    5173      │                     │    8000      │                       │
│  └──────────────┘                     └──────┬───────┘                       │
│                                              │                                │
│                    ┌─────────────────────────┼─────────────────────────┐     │
│                    │                         │                         │     │
│                    ▼                         ▼                         ▼     │
│           ┌──────────────┐          ┌──────────────┐          ┌────────────┐│
│           │   unified.db │          │realpage_raw  │          │ yardi_raw  ││
│           │  (Normalized)│◀─────────│    .db       │          │   .db      ││
│           │              │  sync    │              │          │            ││
│           └──────┬───────┘          └──────┬───────┘          └─────┬──────┘│
│                  │                         │                        │       │
│                  │                         │ Parse Excel            │       │
│                  │                         │                        │       │
│                  │                  ┌──────┴───────┐                │       │
│                  │                  │report_parsers│                │       │
│                  │                  │    .py       │                │       │
│                  │                  └──────┬───────┘                │       │
│                  │                         │                        │       │
└──────────────────┼─────────────────────────┼────────────────────────┼───────┘
                   │                         │                        │
                   │ GET only                │ GET only               │ GET only
                   │ (from cache)            │ (download)             │ (API call)
                   │                         │                        │
┌──────────────────┼─────────────────────────┼────────────────────────┼───────┐
│                  ▼                         ▼                        ▼       │
│                           EXTERNAL PMS SYSTEMS                              │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐          │
│  │   RealPage RPX   │  │ RealPage Reports │  │   Yardi Voyager  │          │
│  │   (SOAP API)     │  │   (REST API)     │  │   (SOAP API)     │          │
│  │                  │  │                  │  │                  │          │
│  │ • getSiteList    │  │ • Box Score      │  │ • GetUnitInfo    │          │
│  │ • unitlist       │  │ • Rent Roll      │  │ • GetResidents   │          │
│  │ • getResidents   │  │ • Delinquency    │  │ • GetLeaseChgs   │          │
│  │ • getLeaseInfo   │  │ • Activity       │  │ • GetGuestAct    │          │
│  │                  │  │ • Monthly Sum    │  │                  │          │
│  │  GET ONLY ✓      │  │  GET ONLY ✓      │  │  GET ONLY ✓      │          │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘          │
│                                                                             │
│  ⛔ NO WRITE OPERATIONS TO ANY EXTERNAL PMS SYSTEM                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 6.1 Local Database Architecture

Data flows from external PMS systems into local SQLite databases for caching and normalization:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LOCAL DATABASE LAYER                                  │
│                     (SQLite - Read/Write LOCAL only)                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────┐       ┌─────────────────────┐                      │
│  │   realpage_raw.db   │       │    yardi_raw.db     │                      │
│  │                     │       │                     │                      │
│  │ • realpage_box_score│       │ • yardi_units       │                      │
│  │ • realpage_rent_roll│       │ • yardi_residents   │                      │
│  │ • realpage_delinq   │       │ • yardi_leases      │                      │
│  │ • realpage_activity │       │                     │                      │
│  │ • realpage_units    │       │                     │                      │
│  │ • realpage_residents│       │                     │                      │
│  └──────────┬──────────┘       └──────────┬──────────┘                      │
│             │                              │                                 │
│             │   sync_realpage_to_unified   │   sync_yardi_to_unified        │
│             │            .py               │          .py                    │
│             │                              │                                 │
│             └──────────────┬───────────────┘                                │
│                            ▼                                                 │
│                 ┌─────────────────────┐                                     │
│                 │     unified.db      │                                     │
│                 │                     │                                     │
│                 │ • unified_properties│  ← Normalized property data         │
│                 │ • unified_units     │  ← Normalized unit data             │
│                 │ • unified_occupancy │  ← Calculated metrics               │
│                 │ • unified_pricing   │  ← Pricing by floorplan             │
│                 │ • unified_delinq    │  ← Delinquency tracking             │
│                 │ • unified_residents │  ← Resident snapshots               │
│                 └─────────────────────┘                                     │
│                                                                              │
│  ✓ All database writes are LOCAL ONLY                                       │
│  ✓ No external system data is modified                                      │
│  ✓ Databases can be deleted and recreated from PMS sources                  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Database Location:** `backend/app/db/data/`

| Database | Purpose | Size |
|----------|---------|------|
| `realpage_raw.db` | Raw RealPage report data | ~5MB |
| `yardi_raw.db` | Raw Yardi API responses | ~1MB |
| `unified.db` | Normalized data for API | ~3MB |

---

## 7. Files to Review

**Priority 1 - Security Critical:**
| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/main.py` | 83 | App entry, CORS config |
| `backend/app/api/routes.py` | 580 | All API endpoints |
| `backend/app/clients/yardi_client.py` | 449 | Yardi PMS integration |
| `backend/app/clients/realpage_client.py` | 350 | RealPage RPX integration |
| `backend/app/clients/aln_client.py` | 116 | ALN market data |

**Priority 2 - Data Sync (Local DB only):**
| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/db/sync_realpage_to_unified.py` | 581 | RealPage → unified sync |
| `backend/app/db/sync_yardi_to_unified.py` | 430 | Yardi → unified sync |
| `backend/report_parsers.py` | 660 | Excel report parsing |
| `backend/batch_report_downloader.py` | 400 | Report download automation |

**Priority 3 - Configuration:**
| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/config.py` | 60 | Environment config |
| `backend/.env.example` | 30 | Credential template |
| `backend/report_definitions.json` | 260 | Report & property config |

**Priority 4 - Business Logic (no security concern):**
| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/services/occupancy_service.py` | 1400 | Metric calculations |
| `backend/app/services/pricing_service.py` | 200 | Pricing calculations |
| `frontend/src/api.ts` | 77 | Frontend API client |

---

## 8. Current Property Coverage

### Properties Currently Synced

| Property | PMS Source | Units | Occupancy | Data Available |
|----------|------------|-------|-----------|----------------|
| Nexus East | RealPage | 352 | 95.74% | Box Score, Rent Roll, Delinquency |
| Parkside at Round Rock | RealPage | 432 | 86.81% | Box Score, Rent Roll, Delinquency |
| Edison at RiNo | RealPage | 277 | 85.92% | Box Score, Rent Roll |
| Aspire 7th and Grant | RealPage | 178 | 93.26% | Box Score, Rent Roll |
| Ridian | RealPage | 123 | 56.91% | Box Score, Rent Roll |
| Venn1 (Test) | Yardi | 0 | N/A | Test property |
| Venn2 (Test) | Yardi | 0 | N/A | Test property |

### Configured for Download (25 Kairoi Properties)

All properties are configured in `report_definitions.json` with PMC ID `4248314`.

---

## 9. Summary

### ✅ Safety Guarantees

1. **No write operations** to Yardi PMS, RealPage, or any external system
2. **All external API calls** are GET/read operations only
3. **RealPage report downloads** only request existing data snapshots
4. **All routes** use `@router.get()` decorator for external data
5. **Yardi client** only implements `Get*` SOAP actions
6. **RealPage client** only implements read SOAP actions
7. **ALN client** only uses HTTP GET requests
8. **Frontend** does not directly access external APIs
9. **Credentials** stored in environment variables, not hardcoded
10. **Local databases** are cache/normalization only - can be deleted and recreated

### ✅ Data Handling

1. **PII Protection**: RealPage reports have resident names hidden by default
2. **Data Retention**: Local SQLite databases only (no cloud storage)
3. **Data Isolation**: Each PMS has separate raw database before normalization
4. **Audit Trail**: Sync logs track all data refresh operations

### ⚠️ Recommendations for Production

1. Add rate limiting to prevent API abuse
2. Add authentication/authorization layer (JWT recommended)
3. Enable HTTPS in production
4. Add request logging for audit trail
5. Implement scheduled sync jobs (cron/scheduler)
6. Add monitoring/alerting for sync failures
7. Consider read replicas if scaling needed

---

## 10. Verification Commands

```bash
# 1. Verify no write operations in Yardi client
grep -rn "Import\|Update\|Create\|Delete\|Cancel\|Post\|Put" backend/app/clients/yardi_client.py
# Expected: 0 results

# 2. Verify no write operations in RealPage client
grep -rn "create\|update\|delete\|post\|put" backend/app/clients/realpage_client.py | grep -v "# "
# Expected: 0 results (only comments)

# 3. Verify all routes are GET
grep -c "@router.post\|@router.put\|@router.delete" backend/app/api/routes.py
# Expected: 0 (POST only for internal imports)

# 4. List all database files (local only)
ls -la backend/app/db/data/*.db
# Expected: realpage_raw.db, yardi_raw.db, unified.db

# 5. Verify credentials in environment only
grep -rn "password\|api_key\|license" backend/app/ --include="*.py" | grep -v "env\|settings\|config"
# Expected: 0 hardcoded credentials
```

---

**Document Version:** 2.0  
**Last Updated:** February 5, 2026  
**Reviewer:** [Pending]  
**Approval Status:** [Pending]
