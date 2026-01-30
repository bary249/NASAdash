# AnyoneHome Integration Analysis for OwnerDashV2

## Executive Summary

AnyoneHome provides **pre-lease funnel data** (leads, quotes, applications) that perfectly complements the existing **post-lease occupancy data** from RealPage. This integration enables a complete prospect-to-resident journey view in the Owner Dashboard.

## Data Synced (GET-Only)

| Table | Records | Description |
|-------|---------|-------------|
| `anyonehome_accounts` | 3 | Management companies |
| `anyonehome_properties` | 199 | All Kairoi properties with RealPage mapping |
| `anyonehome_quotes` | 0* | Rental quotes (requires quote_id) |
| `anyonehome_funnel_metrics` | 0* | Aggregated funnel data |

*Quote and funnel data requires active quote_ids or separate API endpoints from AnyoneHome.

## Property Mapping Success

**3 tracked properties successfully linked:**

| Property | AnyoneHome ID | RealPage ID | Unified ID |
|----------|---------------|-------------|------------|
| Nexus East | `enGC13P6mp78djA6Wj` | 5472172 | `kairoi-nexus-east` |
| Parkside at Round Rock | `5E65sfQNCvtwvp8Hgw` | 5536211 | `kairoi-parkside` |
| Ridian | `ZP1RibN1SKDsFbYjZQ` | 5446271 | `kairoi-ridian` |

**186 of 199 Kairoi properties have RealPage mappings** - ready for dashboard integration.

---

## Funnel & Conversion Rate Integration Proposal

### Current UI Structure

The dashboard already has `LeasingFunnelMetrics` in `types.ts`:

```typescript
export interface LeasingFunnelMetrics {
  leads: number;
  tours: number;
  applications: number;
  lease_signs: number;
  lead_to_tour_rate: number;
  tour_to_app_rate: number;
  lead_to_lease_rate: number;
}
```

### Proposed AnyoneHome Data Integration

#### 1. **Extended Funnel Types** (add to `types.ts`)

```typescript
// AnyoneHome-specific quote data
export interface AnyoneHomeQuote {
  quote_id: string;
  guest_name: string;
  guest_email: string;
  issued_on: string;
  property_name: string;
  floorplan_name: string;
  unit_number: string;
  base_rent: number;
  move_in_date: string;
  quote_status: 'issued' | 'applied' | 'converted' | 'expired';
}

// Extended funnel with AnyoneHome stages
export interface ExtendedFunnelMetrics extends LeasingFunnelMetrics {
  // AnyoneHome-specific stages
  quotes_issued: number;
  quotes_viewed: number;
  applications_started: number;
  applications_completed: number;
  applications_approved: number;
  
  // Extended conversion rates
  quote_to_apply_rate: number;
  apply_to_approve_rate: number;
  approve_to_sign_rate: number;
  
  // Time-to-convert metrics
  avg_days_quote_to_apply: number;
  avg_days_apply_to_sign: number;
}
```

#### 2. **New API Endpoints** (add to backend)

```python
# GET /api/{property_id}/anyonehome/properties
# Returns AnyoneHome property info with RealPage mapping

# GET /api/{property_id}/anyonehome/funnel
# Returns funnel metrics for the property

# GET /api/{property_id}/anyonehome/quotes
# Returns recent quotes (drill-through data)
```

#### 3. **UI Components** (new or extended)

##### Option A: Extend Existing Funnel Section
Add AnyoneHome metrics to the existing leasing funnel in `OccupancySectionV2.tsx`:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  LEASING FUNNEL (AnyoneHome + RealPage)                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   📊 Quotes Issued    →    👁️ Quotes Viewed    →    📝 Applications    │
│        45                      38 (84%)                 22 (58%)        │
│                                                                         │
│   ✅ Approved         →    🏠 Leases Signed    →    🎉 Move-Ins        │
│        18 (82%)               15 (83%)                 12              │
│                                                                         │
│   ──────────────────────────────────────────────────────────────────   │
│   Overall: Quote → Move-In = 27% (Target: 30%)                         │
│   Avg Days: Quote → Lease = 8.2 days                                   │
└─────────────────────────────────────────────────────────────────────────┘
```

##### Option B: New Pre-Lease Section
Create a dedicated `PreLeaseFunnelSection.tsx`:

```
┌─────────────────────────────────────────────────────────────────────────┐
│  🏠 PRE-LEASE FUNNEL (via AnyoneHome)                                  │
├─────────────┬─────────────┬─────────────┬─────────────┬────────────────┤
│   QUOTES    │   VIEWS     │    APPS     │  APPROVED   │    SIGNED      │
│     45      │     38      │     22      │     18      │      15        │
│             │   (84%)     │   (58%)     │   (82%)     │    (83%)       │
├─────────────┴─────────────┴─────────────┴─────────────┴────────────────┤
│   ▼ Recent Quotes (click to expand)                                    │
│   • Kelsey Canoe - 2BR @ $1,850 - Issued 12/16/25 - APPLIED            │
│   • John Smith - 1BR @ $1,450 - Issued 12/14/25 - EXPIRED              │
│   • Jane Doe - Studio @ $1,200 - Issued 12/12/25 - CONVERTED           │
└─────────────────────────────────────────────────────────────────────────┘
```

### 4. **Dashboard Data Flow**

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   AnyoneHome    │     │    RealPage     │     │    Unified      │
│   (Pre-Lease)   │     │   (Post-Lease)  │     │   Dashboard     │
├─────────────────┤     ├─────────────────┤     ├─────────────────┤
│ • Quotes        │ ──► │ • Units         │ ──► │ • Full Funnel   │
│ • Applications  │     │ • Residents     │     │ • Occupancy     │
│ • Approvals     │     │ • Leases        │     │ • Conversion    │
│                 │     │ • Move-ins      │     │ • Trends        │
└─────────────────┘     └─────────────────┘     └─────────────────┘
        │                       │                       │
        └───────────── Property Mapping ────────────────┘
              (via RealPage Site ID = anyonehome_properties.realpage_site_id)
```

---

## Implementation Roadmap

### Phase 1: Data Layer (Completed ✅)
- [x] Create `anyonehome_client.py` with GET-only middleware
- [x] Add AnyoneHome tables to `unified.db`
- [x] Sync Kairoi accounts and properties
- [x] Map to RealPage Site IDs

### Phase 2: API Endpoints (Next)
- [ ] Create `/api/{property_id}/anyonehome/funnel` endpoint
- [ ] Create `/api/{property_id}/anyonehome/quotes` endpoint
- [ ] Add property linking via `realpage_site_id`

### Phase 3: Frontend Integration
- [ ] Add `AnyoneHomeFunnel` types to `types.ts`
- [ ] Create `PreLeaseFunnelSection.tsx` component
- [ ] Add drill-through for quote details
- [ ] Integrate with existing trend comparisons

### Phase 4: Analytics
- [ ] Calculate funnel conversion rates
- [ ] Track time-to-convert metrics
- [ ] Add funnel trend comparisons
- [ ] Create AI insights for funnel optimization

---

## Key Insights from Data

### 1. **Property Coverage**
- 199 Kairoi properties in AnyoneHome
- 186 (93%) have RealPage mapping
- Ready for immediate dashboard integration

### 2. **Data Gaps**
- Quote data requires active quote_ids (per-quote retrieval)
- No bulk quote export API discovered yet
- May need to work with AnyoneHome (Inhabit) on reporting API

### 3. **Integration Value**
- **Pre-lease visibility**: See prospects before they become applicants
- **Conversion optimization**: Identify funnel drop-off points
- **Revenue forecasting**: Quotes → Expected move-ins
- **Marketing ROI**: Lead source tracking through conversion

---

## Files Created

| File | Description |
|------|-------------|
| `app/api/anyonehome_client.py` | GET-only API client with middleware |
| `app/db/sync_anyonehome.py` | Data sync script for Kairoi properties |
| `app/db/schema.py` | Extended with AnyoneHome tables |
| `test_anyonehome_api.py` | API test script |

---

## Next Steps

1. **Ask AnyoneHome team** for bulk quote/funnel reporting API
2. **Implement API endpoints** for frontend consumption
3. **Build UI components** for funnel visualization
4. **Add to sync schedule** for daily data refresh
