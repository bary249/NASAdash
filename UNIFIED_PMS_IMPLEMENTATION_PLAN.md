# Unified PMS Data Layer - Implementation Plan

## Overview

This document outlines the implementation plan for creating a unified data layer that abstracts Yardi and RealPage PMS systems, enabling a single view for property-level metrics across multiple buildings/properties.

---

## Phase 1: Unified PMS Client Interface

### 1.1 Create Abstract PMS Interface

**Goal:** Define a common interface that both Yardi and RealPage clients implement.

**File:** `backend/app/clients/pms_interface.py`

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date

class PMSInterface(ABC):
    """Abstract interface for PMS data providers (Yardi, RealPage)."""
    
    @abstractmethod
    async def get_properties(self) -> List[dict]:
        """Get list of properties/sites."""
        pass
    
    @abstractmethod
    async def get_units(self, property_id: str) -> List[dict]:
        """Get unit information for a property."""
        pass
    
    @abstractmethod
    async def get_residents(self, property_id: str, status: str = "Current") -> List[dict]:
        """Get residents by status."""
        pass
    
    @abstractmethod
    async def get_occupancy_metrics(self, property_id: str) -> dict:
        """Get occupancy metrics (total, occupied, vacant, leased)."""
        pass
    
    @abstractmethod
    async def get_lease_data(self, property_id: str) -> List[dict]:
        """Get lease/charge information."""
        pass
```

**Status:** [ ] Not Started

---

### 1.2 Implement RealPage Client

**Goal:** Create RealPage client implementing the PMS interface.

**File:** `backend/app/clients/realpage_client.py`

**Available RealPage Methods (READ-ONLY):**
| Method | Data |
|--------|------|
| `getBuildings` | Property structures |
| `getSiteList` | Site/property list |
| `getUnitList` | Unit details |
| `getResident` | Resident information |
| `getResidentListInfo` | Resident list |
| `getLeaseInfo` | Lease data |

**NOT Available (Needs RealPage authorization):**
- Guest Cards / Prospects
- Marketing Sources
- Activity Types
- Leasing Agents

**Status:** [ ] Not Started

---

### 1.3 Refactor Yardi Client

**Goal:** Update existing YardiClient to implement the PMS interface.

**File:** `backend/app/clients/yardi_client.py` (update existing)

**Status:** [ ] Not Started

---

## Phase 2: Unified Data Models

### 2.1 Create Canonical Data Models

**Goal:** Define unified data models that normalize data from both PMS systems.

**File:** `backend/app/models/unified.py`

```python
class UnifiedUnit:
    """Normalized unit data from any PMS."""
    unit_id: str
    property_id: str
    pms_source: str  # "yardi" | "realpage"
    unit_number: str
    floorplan: str
    bedrooms: int
    bathrooms: float
    square_feet: int
    market_rent: float
    status: str  # "occupied" | "vacant" | "notice" | "model" | "down"
    occupancy_status: str
    days_vacant: Optional[int]
    available_date: Optional[date]

class UnifiedResident:
    """Normalized resident data from any PMS."""
    resident_id: str
    property_id: str
    pms_source: str
    unit_id: str
    first_name: str
    last_name: str
    current_rent: float
    lease_start: Optional[date]
    lease_end: Optional[date]
    move_in_date: Optional[date]
    move_out_date: Optional[date]
    status: str  # "current" | "future" | "past" | "notice" | "applicant"

class UnifiedOccupancy:
    """Normalized occupancy metrics."""
    property_id: str
    pms_source: str
    total_units: int
    occupied_units: int
    vacant_units: int
    leased_units: int
    preleased_vacant: int
    physical_occupancy: float
    leased_percentage: float
```

**Status:** [ ] Not Started

---

### 2.2 Field Mapping Configuration

**Goal:** Create mapping configurations for each PMS.

**Files:**
- `backend/app/mappings/yardi_mapping.py`
- `backend/app/mappings/realpage_mapping.py`

**Yardi → Unified Mapping:**
| Yardi Field | Unified Field |
|-------------|---------------|
| `UnitCode` | `unit_number` |
| `UnitType` | `floorplan` |
| `UnitStatus` | `status` |
| `MarketRent` | `market_rent` |
| `SQFT` | `square_feet` |

**RealPage → Unified Mapping:**
| RealPage Field | Unified Field |
|----------------|---------------|
| `UnitID` | `unit_id` |
| `UnitNumber` | `unit_number` |
| `FloorPlanCode` | `floorplan` |
| `UnitStatus` | `status` |
| `MarketRent` | `market_rent` |
| `UnitSqFt` | `square_feet` |

**Status:** [ ] Not Started

---

## Phase 3: Property-Level Aggregation Service

### 3.1 Create Portfolio Service

**Goal:** Aggregate metrics across multiple properties into a single view.

**File:** `backend/app/services/portfolio_service.py`

**Aggregation Modes:**

The portfolio view supports **two aggregation modes** that users can toggle between:

| Mode | Description | Use Case |
|------|-------------|----------|
| **Average/Weighted Average** | Calculate metrics per property, then average | Quick portfolio health check |
| **Row Metrics (Combined)** | Combine all raw data, calculate metrics from combined dataset | Accurate portfolio-wide metrics |

**Example - Occupancy Calculation:**

```
Property A: 100 units, 90 occupied (90%)
Property B: 200 units, 180 occupied (90%)
Property C: 50 units, 40 occupied (80%)

Mode 1 - Weighted Average:
  (90*100 + 90*200 + 80*50) / (100+200+50) = 88.57%

Mode 2 - Row Metrics (Combined):
  Total units: 350
  Total occupied: 310
  Occupancy: 310/350 = 88.57%
  (Same result for occupancy, but differs for complex metrics like rent growth)
```

**Aggregation Logic:**
```python
from enum import Enum

class AggregationMode(str, Enum):
    WEIGHTED_AVERAGE = "weighted_avg"  # Calculate per-property, then average
    ROW_METRICS = "row_metrics"        # Combine all raw data, then calculate

class PortfolioService:
    """Aggregates metrics across multiple properties."""
    
    async def get_portfolio_occupancy(
        self, 
        property_ids: List[str],
        pms_configs: List[PMSConfig],
        mode: AggregationMode = AggregationMode.WEIGHTED_AVERAGE
    ) -> PortfolioOccupancy:
        """
        Aggregate occupancy across properties.
        
        WEIGHTED_AVERAGE mode:
        - Get occupancy metrics per property
        - physical_occupancy: weighted by unit count
        
        ROW_METRICS mode:
        - Fetch all units from all properties
        - Calculate occupancy from combined unit dataset
        """
        if mode == AggregationMode.ROW_METRICS:
            # Combine all raw unit data
            all_units = []
            for prop_id, config in zip(property_ids, pms_configs):
                units = await self.get_units(prop_id, config)
                all_units.extend(units)
            
            # Calculate metrics from combined data
            total = len(all_units)
            occupied = len([u for u in all_units if u.status == "occupied"])
            return PortfolioOccupancy(
                total_units=total,
                occupied_units=occupied,
                physical_occupancy=occupied/total if total > 0 else 0
            )
        else:
            # Weighted average of per-property metrics
            ...
    
    async def get_portfolio_pricing(
        self,
        property_ids: List[str],
        pms_configs: List[PMSConfig],
        mode: AggregationMode = AggregationMode.WEIGHTED_AVERAGE
    ) -> PortfolioPricing:
        """
        Aggregate pricing across properties.
        
        WEIGHTED_AVERAGE mode:
        - in_place_rent: weighted by unit count per floorplan
        - asking_rent: weighted by unit count
        
        ROW_METRICS mode:
        - Combine all lease/unit data
        - Calculate rent metrics from combined dataset
        """
        pass
```

**Status:** [ ] Not Started

---

### 3.2 Multi-Property View API

**Goal:** Create API endpoints for portfolio/multi-property views.

**File:** `backend/app/api/portfolio.py`

**Endpoints:**
| Endpoint | Description |
|----------|-------------|
| `GET /api/portfolio/occupancy` | Aggregated occupancy metrics |
| `GET /api/portfolio/pricing` | Aggregated pricing metrics |
| `GET /api/portfolio/units` | Combined unit list (drill-through) |
| `GET /api/portfolio/residents` | Combined resident list (drill-through) |

**Query Parameters:**
- `property_ids`: Comma-separated list of property IDs
- `timeframe`: cm, pm, ytd
- `pms`: Filter by PMS type (optional)
- `mode`: `weighted_avg` | `row_metrics` (default: weighted_avg)

**Status:** [ ] Not Started

---

## Phase 4: Frontend Updates

### 4.1 Property Selector Enhancement

**Goal:** Allow selecting multiple properties for portfolio view.

**Changes:**
- Multi-select dropdown for properties
- "All Properties" option
- Property grouping by PMS type

**Status:** [ ] Not Started

---

### 4.2 Aggregation Mode Toggle

**Goal:** Allow users to switch between aggregation modes.

**UI Component:**
```
┌─────────────────────────────────────────────┐
│  Aggregation Mode:                          │
│  ┌──────────────────┐ ┌──────────────────┐  │
│  │ Weighted Average │ │   Row Metrics    │  │
│  │     (active)     │ │                  │  │
│  └──────────────────┘ └──────────────────┘  │
│                                             │
│  ℹ️ Weighted Average: Per-property metrics  │
│     averaged by unit count                  │
│                                             │
│  ℹ️ Row Metrics: Combined raw data from     │
│     all buildings, metrics calculated once  │
└─────────────────────────────────────────────┘
```

**Behavior:**
- Toggle persists in user preferences
- Tooltips explain the difference
- Visual indicator shows current mode

**Status:** [ ] Not Started

---

### 4.3 Portfolio Dashboard View

**Goal:** New dashboard view showing aggregated metrics.

**Components:**
- **Aggregation mode toggle** (top of page)
- Portfolio occupancy card (respects selected mode)
- Portfolio pricing card (respects selected mode)
- Property breakdown table (click to drill into individual)
- Combined unit/resident lists with property column (for drill-through)

**Status:** [ ] Not Started

---

## Phase 5: Data ETL for RealPage Occupancy Gap

### 5.1 Problem Statement

RealPage API does not provide:
- Prospect/Lead data (Guest Cards)
- Marketing attribution
- Leasing funnel metrics

**Solution:** Export-based ETL mechanism to supplement API data.

---

### 5.2 Export Data Ingestion Service

**Goal:** Process exported data files (Excel/CSV) from RealPage OneSite.

**File:** `backend/app/services/export_ingestion_service.py`

**Supported Exports:**
| Export Type | Source | Data Provided |
|-------------|--------|---------------|
| Prospect Export | OneSite Reports | Guest cards, leads, activities |
| Occupancy Snapshot | OneSite Reports | Point-in-time occupancy |
| Traffic Report | OneSite Reports | Tours, calls, walk-ins |

**Process Flow:**
```
1. User uploads export file (CSV/Excel)
2. Service detects file type and format
3. Data is parsed and mapped to unified models
4. Data is stored in local database (SQLite/PostgreSQL)
5. Dashboard queries local DB for missing metrics
```

**Status:** [ ] Not Started

---

### 5.3 Local Data Store

**Goal:** Store supplemental data that's not available via API.

**File:** `backend/app/db/supplemental_data.py`

**Tables:**
```sql
-- Prospect/Lead data from exports
CREATE TABLE realpage_prospects (
    id INTEGER PRIMARY KEY,
    property_id TEXT,
    guest_card_id TEXT,
    first_name TEXT,
    last_name TEXT,
    email TEXT,
    phone TEXT,
    source TEXT,
    created_date DATE,
    last_activity_date DATE,
    status TEXT,
    imported_at TIMESTAMP
);

-- Occupancy snapshots from exports
CREATE TABLE realpage_occupancy_snapshots (
    id INTEGER PRIMARY KEY,
    property_id TEXT,
    snapshot_date DATE,
    total_units INTEGER,
    occupied_units INTEGER,
    vacant_units INTEGER,
    physical_occupancy FLOAT,
    imported_at TIMESTAMP
);
```

**Status:** [ ] Not Started

---

### 5.4 Hybrid Data Service

**Goal:** Combine API data with exported data seamlessly.

**File:** `backend/app/services/hybrid_data_service.py`

**Logic:**
```python
class HybridDataService:
    """Combines API data with supplemental export data."""
    
    async def get_occupancy(self, property_id: str, pms_type: str) -> UnifiedOccupancy:
        if pms_type == "yardi":
            # Full data available via API
            return await self.yardi_client.get_occupancy_metrics(property_id)
        
        elif pms_type == "realpage":
            # API provides basic data
            api_data = await self.realpage_client.get_occupancy_metrics(property_id)
            
            # Check for supplemental export data
            export_data = await self.get_latest_export_snapshot(property_id)
            
            # Merge: API takes precedence, export fills gaps
            return self.merge_occupancy_data(api_data, export_data)
```

**Status:** [ ] Not Started

---

## Implementation Tracking

### Sprint 1: Foundation (Week 1-2)
| Task | Status | Notes |
|------|--------|-------|
| 1.1 Create PMS Interface | [x] | `app/clients/pms_interface.py` |
| 1.2 Implement RealPage Client | [x] | `app/clients/realpage_client.py` |
| 1.3 Refactor Yardi Client | [x] | Updated `app/clients/yardi_client.py` |
| 2.1 Unified Data Models | [x] | `app/models/unified.py` |

### Sprint 2: Aggregation (Week 3-4)
| Task | Status | Notes |
|------|--------|-------|
| 2.2 Field Mappings | [x] | Included in client implementations |
| 3.1 Portfolio Service (with mode toggle) | [x] | `app/services/portfolio_service.py` |
| 3.2 Portfolio API | [x] | `app/api/portfolio.py` |

### Sprint 3: Frontend (Week 5-6)
| Task | Status | Notes |
|------|--------|-------|
| 4.1 Property Selector | [x] | Multi-select checkboxes in PortfolioView |
| 4.2 Aggregation Mode Toggle | [x] | Weighted Avg / Row Metrics toggle |
| 4.3 Portfolio Dashboard | [x] | Enhanced totals row, info tooltip |

### Sprint 4: ETL Layer (Week 7-8)
| Task | Status | Notes |
|------|--------|-------|
| 5.2 Export Ingestion | [ ] | |
| 5.3 Local Data Store | [ ] | |
| 5.4 Hybrid Data Service | [ ] | |

---

## Dependencies & Risks

### Dependencies
1. RealPage API access for basic property/unit/resident data ✅
2. Yardi API access (existing) ✅
3. Export file formats documented

### Risks
| Risk | Impact | Mitigation |
|------|--------|------------|
| RealPage Prospect API not enabled | No leasing funnel from API | ETL from exports |
| Export format changes | Ingestion breaks | Schema validation |
| Different property IDs across systems | Aggregation fails | Property mapping config |

---

## Configuration

**New Environment Variables:**
```env
# RealPage credentials
REALPAGE_URL=https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc
REALPAGE_PMCID=5230170
REALPAGE_SITEID=5230176
REALPAGE_LICENSEKEY=402b831f-a045-40ce-9ee8-cc2aa6c3ab72

# Supplemental data store
SUPPLEMENTAL_DB_PATH=./data/supplemental.db

# Property mappings (JSON file path)
PROPERTY_MAPPINGS_PATH=./config/property_mappings.json
```

**Property Mappings Config:**
```json
{
  "portfolios": {
    "kairoi": {
      "name": "Kairoi Management",
      "properties": [
        {
          "unified_id": "prop-001",
          "name": "The Residences",
          "pms": "realpage",
          "pms_property_id": "5230176",
          "pms_pmc_id": "5230170"
        },
        {
          "unified_id": "prop-002", 
          "name": "Downtown Lofts",
          "pms": "yardi",
          "pms_property_id": "dloft1"
        }
      ]
    }
  }
}
```

---

## Next Steps

1. **Immediate:** Start with Phase 1.2 - RealPage Client implementation
2. **Parallel:** Document RealPage export file formats for ETL planning
3. **Validate:** Test RealPage API data completeness against Yardi

---

*Last Updated: 2026-01-21*
