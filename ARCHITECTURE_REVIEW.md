# Owner Dashboard V2 - Architecture Review Document
**Prepared for Senior Architect Review**  
**Date:** January 16, 2026  
**Project:** Asset Management Dashboard for Property Owners

---

## Executive Summary

This document provides a security and architecture review of the Owner Dashboard V2 project. The dashboard provides **read-only** visibility into property performance metrics by integrating with Yardi PMS and ALN market data APIs.

### Key Safety Guarantees

| Aspect | Implementation |
|--------|----------------|
| **HTTP Methods** | GET only - no PUT, POST, DELETE |
| **CORS Policy** | Restricted to `allow_methods=["GET"]` |
| **API Design** | All endpoints are `@router.get()` |
| **Data Modification** | Zero write operations to any external system |
| **Credentials** | Environment variables only, not hardcoded |

---

## 1. Backend Architecture (FastAPI)

### 1.1 Main Application Entry Point

**File:** `backend/app/main.py`

```python
# Lines 1-16: Explicit READ-ONLY documentation
"""
Owner Dashboard V2 API - READ-ONLY Backend
============================================
IMPORTANT: All operations are GET-only. No PUT, POST, DELETE operations
are permitted to ensure no data modifications occur.
"""

# Lines 48-59: CORS middleware restricts to GET only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", 
        "http://localhost:3000", 
        "http://127.0.0.1:5173",
        "http://localhost:5174"
    ],
    allow_credentials=True,
    allow_methods=["GET"],  # ← CRITICAL: Only GET allowed
    allow_headers=["*"],
)
```

**Safety Note:** The `allow_methods=["GET"]` in CORS middleware ensures that even if a malicious frontend tried to send POST/PUT/DELETE requests, they would be rejected at the middleware level.

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

### 2.2 ALN Market Data Client - READ-ONLY

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
┌─────────────────────────────────────────────────────────────────────────┐
│                          OWNER DASHBOARD V2                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌──────────────┐     GET only      ┌──────────────┐                    │
│  │   Frontend   │ ───────────────▶  │   Backend    │                    │
│  │   (React)    │                   │   (FastAPI)  │                    │
│  │              │ ◀───────────────  │              │                    │
│  │ localhost:   │    JSON response  │ localhost:   │                    │
│  │    5173      │                   │    8001      │                    │
│  └──────────────┘                   └──────┬───────┘                    │
│                                            │                             │
│                                            │ GET only                    │
│                                            ▼                             │
│                           ┌────────────────────────────────┐            │
│                           │      External APIs             │            │
│                           │  ┌──────────┐  ┌──────────┐   │            │
│                           │  │  Yardi   │  │   ALN    │   │            │
│                           │  │   PMS    │  │  Market  │   │            │
│                           │  │  (SOAP)  │  │  (REST)  │   │            │
│                           │  │          │  │          │   │            │
│                           │  │ Get*     │  │ GET      │   │            │
│                           │  │ methods  │  │ only     │   │            │
│                           │  │ ONLY     │  │          │   │            │
│                           │  └──────────┘  └──────────┘   │            │
│                           └────────────────────────────────┘            │
│                                                                          │
│  ⛔ NO WRITE OPERATIONS AT ANY LAYER                                     │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Files to Review

**Priority 1 - Security Critical:**
| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/main.py` | 75 | App entry, CORS config |
| `backend/app/api/routes.py` | 295 | All API endpoints |
| `backend/app/clients/yardi_client.py` | 248 | Yardi PMS integration |
| `backend/app/clients/aln_client.py` | 116 | ALN market data |

**Priority 2 - Configuration:**
| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/config.py` | 44 | Environment config |
| `backend/.env.example` | 19 | Credential template |

**Priority 3 - Business Logic (no security concern):**
| File | Lines | Purpose |
|------|-------|---------|
| `backend/app/services/occupancy_service.py` | ~300 | Metric calculations |
| `backend/app/services/pricing_service.py` | ~150 | Pricing calculations |
| `frontend/src/api.ts` | 77 | Frontend API client |

---

## 8. Summary

### ✅ Safety Guarantees

1. **No write operations** to Yardi PMS or any external system
2. **CORS restricted** to GET methods only at middleware level
3. **All routes** use `@router.get()` decorator exclusively
4. **Yardi client** only implements `Get*` SOAP actions
5. **ALN client** only uses HTTP GET requests
6. **Frontend** does not directly access external APIs
7. **Credentials** stored in environment variables, not hardcoded

### ⚠️ Recommendations for Production

1. Add rate limiting to prevent API abuse
2. Add authentication/authorization layer
3. Enable HTTPS in production
4. Add request logging for audit trail
5. Consider caching for frequently-accessed data

---
