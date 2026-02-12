# NASA Dashboard — Work Plan to 100% Coverage

**Created**: 2026-02-09  
**Current Coverage**: 42/102 fields live (41%) + 10 partial (~51% effective)  
**Target**: 102/102 fields (100%)  
**Order**: Operational → Financial (easiest wins first)

---

## Coverage Snapshot

| Phase | Section | Now | After | Fields Unlocked |
|-------|---------|-----|-------|-----------------|
| 1 | Operational Polish | 51% | 60% | 9 fields ✅ Steps 1.1–1.5 done |
| 2 | Financial Reports | 60% | 77% | 17 fields |
| 3 | Debt & Manual Data | 77% | 97% | 20 fields |
| 4 | Advanced Analytics | 97% | 100% | 3 fields |

---

## Phase 1: Operational Polish (Current → 60%)

*Close the small gaps in sections that are already mostly working.*

### Step 1.1 — Eviction Detail from RPX API
- **Fields unlocked**: Evictions count + balance (1 field, partial → live)
- **Source**: RPX SOAP API `getLeaseInfo` → `Evict` flag
- **Work**: Add eviction aggregation to `sync_realpage_to_unified.py`, expose via `/api/v2/properties/{id}/delinquency`
- **Effort**: ~2 hours
- **Status**: ✅ **DONE** (2026-02-10) — 134 eviction-flagged leases resolved via unit_id→unit_number mapping through realpage_units. 56 matched to delinquency records across 11 properties. `is_eviction` + `eviction_balance` columns added to `unified_delinquency`. API endpoint updated to use RPX SOAP evict flag instead of status text guessing.

### Step 1.2 — Derive Marketing Metrics from Activity Report
- **Fields unlocked**: Avg days to lease, app completion rate, app approval rate (3 fields, partial → live)
- **Source**: `realpage_activity` — calculate time deltas between activity types per prospect
- **Work**: 
  - Group activity records by prospect name/unit
  - Calculate first_contact → leased delta = "avg days to lease"
  - Count `Online Leasing pre-qualify` → `Online Leasing Agreement` → `Leased` for completion/approval rates
  - Add to backend API response
- **Effort**: ~4 hours
- **Status**: ✅ **DONE** (2026-02-10) — Added `avg_days_to_lease`, `app_completion_rate`, `app_approval_rate` to `LeasingFunnelMetrics` model. Computed from prospect-level activity grouping (first_contact→leased delta, pre-qualify→agreement→leased funnel).

### Step 1.3 — Turn Time Calculation
- **Fields unlocked**: Avg turn time (1 field, partial → live)
- **Source**: `realpage_rent_roll` — `move_out_date` vs `move_in_date` for same unit
- **Work**: Match sequential residents on same unit, calculate gap
- **Effort**: ~2 hours
- **Status**: ✅ **DONE** (2026-02-10) — New `/properties/{id}/turn-time` endpoint. Calculates gap between Former lease `inactive_date` and next Current lease `move_in_date` per unit via `realpage_leases`. Returns avg/min/max turn days. 24 properties have measurable turns (avg 14–91 days).

### Step 1.4 — Loss-to-Lease Estimate
- **Fields unlocked**: Loss-to-lease as % (1 field, partial → live)
- **Source**: Box Score `avg_market_rent` − `avg_actual_rent` × `occupied_units`
- **Work**: Add calculation to pricing API endpoint
- **Effort**: ~1 hour
- **Status**: ✅ **DONE** (2026-02-10) — New `/properties/{id}/loss-to-lease` endpoint. Calculates (avg_asking − avg_in_place) × occupied_units from `unified_pricing_metrics` + `unified_occupancy_metrics`. Returns total loss, loss_per_unit, loss_pct. ~15 properties have pricing data.

### Step 1.5 — Projected Occupancy (30/60/90 day)
- **Fields unlocked**: Projected occupancy (1 field, partial → live)
- **Source**: Current occupancy + pipeline (scheduled move-ins from Activity "Leased") − scheduled move-outs (on-notice)
- **Work**: Add forward-looking calculation to occupancy endpoint
- **Effort**: ~3 hours
- **Status**: ✅ **DONE** (2026-02-10) — New `/properties/{id}/projected-occupancy` endpoint. Combines current occupancy + preleased_vacant (move-ins) − unrenewed expirations (move-outs) from `realpage_leases`. Returns 30/60/90d projections with breakdown.

### Step 1.6 — Market Rent Comparison (ALN)
- **Fields unlocked**: Rent growth vs market, market rent comparison (2 fields)
- **Source**: ALN API (already integrated in separate project)
- **Work**: Connect ALN comp data to dashboard, store in unified.db
- **Effort**: ~4 hours
- **Status**: 🔲 Not started

**Phase 1 Total**: ~16 hours | +9 fields → **60% coverage** — ✅ Steps 1.1–1.5 complete (Step 1.6 ALN Market Comps pending)

---

## Phase 2: Financial Reports (60% → 77%)

*The single biggest unlock. One report type opens 17+ fields.*

### Step 2.1 — Discover Financial Summary Report ID
- **Fields unlocked**: Prerequisite for all P&L fields
- **Work**:
  1. Log into RealPage web UI
  2. Navigate to Reports → Financial → run a Financial Summary / Income Statement
  3. Open browser DevTools → Network tab
  4. Capture the `reportId` and `reportKey` from the API call
  5. Document in `REALPAGE_DATA_MAPPING.md`
- **Effort**: ~30 minutes (requires user action)
- **Status**: 🔲 Not started — **BLOCKED on user capturing report ID**

### Step 2.2 — Download & Analyze Financial Summary
- **Fields unlocked**: Understanding file structure
- **Work**:
  1. Use `download_reports_v2.py` with new report ID to create instance + download
  2. Analyze XLS structure (headers, columns, layout)
  3. Identify column mappings for: GPR, LTL, concessions, vacancy, net rental revenue, other income, all expense categories, NOI
- **Effort**: ~2 hours
- **Status**: 🔲 Not started

### Step 2.3 — Build Financial Summary Parser
- **Fields unlocked**: 11 P&L fields + 6 expense fields = 17 fields
- **Work**:
  1. Add `parse_financial_summary()` to `report_parsers.py`
  2. Create `realpage_financial_summary` table in raw DB
  3. Map columns: GPR, loss_to_lease, concessions, vacancy_cost, net_rental_revenue, other_income, total_income, payroll, marketing, ga, rm, utilities, insurance, re_taxes, total_opex, noi
  4. Add to `import_downloaded_reports.py`
  5. Add sync to `sync_realpage_to_unified.py` → new `unified_financials` table
  6. Create `/api/v2/properties/{id}/financials` endpoint
- **Effort**: ~8 hours
- **Status**: 🔲 Not started

### Step 2.4 — Revenue Optimization Fields (Derived from Financials)
- **Fields unlocked**: RevPAU, concession cost %, bad debt %, economic occupancy, operating expense/unit (5 fields)
- **Source**: All derived from financial summary data + existing occupancy data
- **Work**: Add calculated fields to API responses
- **Effort**: ~3 hours
- **Status**: 🔲 Not started

### Step 2.5 — Cost per Lease
- **Fields unlocked**: Cost per lease (1 field)
- **Source**: Marketing expense (from financial summary) ÷ lease signs (from activity report)
- **Work**: Add to marketing performance endpoint
- **Effort**: ~1 hour
- **Status**: 🔲 Not started

### Step 2.6 — Turn Cost Analysis
- **Fields unlocked**: Turn costs per unit, turn cost vs rent increase (2 fields)
- **Source**: T/O expense (from financial summary) ÷ move-outs
- **Work**: Add to turnover endpoint
- **Effort**: ~1 hour
- **Status**: 🔲 Not started

**Phase 2 Total**: ~15.5 hours | +26 fields → **77% coverage**

---

## Phase 3: Debt & Manual Data Entry (77% → 97%)

*These 20 fields are NOT in the PMS — they come from loan documents and must be manually entered or imported.*

### Step 3.1 — Debt Data Model
- **Fields covered**: All 20 debt/loan fields
- **Work**:
  1. Create `unified_debt` table: loan_amount, current_balance, rate_type, rate_index, index_value, spread, all_in_rate, maturity_date, io_period_end, min_dscr, debt_yield_required, monthly_debt_service, replacement_reserves, tax_escrow, insurance_escrow
  2. Add property_id FK
- **Effort**: ~2 hours
- **Status**: 🔲 Not started

### Step 3.2 — Debt Admin Import UI
- **Fields covered**: Data entry mechanism
- **Work**:
  1. Build admin page in frontend (or Excel import template)
  2. Create `/api/v2/admin/debt` POST endpoint
  3. Support CSV/Excel upload for bulk entry
  4. Calculate derived fields (DSCR, debt yield, LTV, days to maturity)
- **Effort**: ~8 hours
- **Status**: 🔲 Not started

### Step 3.3 — Debt Dashboard Section
- **Work**:
  1. Add Debt & Loan section to property detail view
  2. Display covenant monitoring (DSCR vs required, DY vs required)
  3. Maturity timeline visualization
- **Effort**: ~6 hours
- **Status**: 🔲 Not started

### Step 3.4 — Budget Data Import
- **Fields covered**: Revenue forecast vs budget (1 field)
- **Work**: Build budget import (Excel template or API) + variance calculation
- **Effort**: ~4 hours
- **Status**: 🔲 Not started

**Phase 3 Total**: ~20 hours | +21 fields → **97% coverage**

---

## Phase 4: Advanced Analytics & External (97% → 100%)

*Final 3 fields requiring external tools or AI models.*

### Step 4.1 — Resident Satisfaction Scores
- **Field**: Resident scores (1 field)
- **Options**:
  - A) Integrate NPS survey tool (SurveyMonkey, Medallia, etc.)
  - B) Pull from RealPage Reputation Management if available
  - C) Manual entry per property
- **Effort**: 2-8 hours depending on approach
- **Status**: 🔲 Not started

### Step 4.2 — Seasonality Trends
- **Field**: Seasonality trends (1 field)
- **Work**: Accumulate 6+ months of historical data, then build trend analysis
- **Note**: This is time-dependent — data must accumulate before analysis is possible
- **Effort**: ~4 hours (once data exists)
- **Status**: 🔲 Blocked on time (need historical data)

### Step 4.3 — AI Rent Recommendations
- **Field**: Optimal rent recommendations (1 field)
- **Work**: Build ML model using occupancy + pricing + market data to suggest pricing
- **Effort**: ~20 hours
- **Status**: 🔲 Not started

**Phase 4 Total**: ~26-32 hours | +3 fields → **100% coverage**

---

## Timeline Summary

| Phase | Focus | Fields | Effort | Blockers |
|-------|-------|--------|--------|----------|
| **Phase 1** | Operational Polish | +9 → 60% | ~16 hrs | None |
| **Phase 2** | Financial Reports | +26 → 77% | ~15.5 hrs | User must capture Financial Summary report ID |
| **Phase 3** | Debt & Manual Data | +21 → 97% | ~20 hrs | Need loan documents from asset management |
| **Phase 4** | Advanced Analytics | +3 → 100% | ~26-32 hrs | Historical data accumulation, AI model |
| **TOTAL** | | **102 fields** | **~78-84 hrs** | |

---

## Immediate Next 3 Steps

### ✅ DONE: Steps 1.1–1.5 completed 2026-02-10

All 5 steps implemented:
- **1.1** Eviction aggregation from RPX SOAP API evict flag → 56 matched records
- **1.2** Marketing metrics (avg_days_to_lease, app_completion_rate, app_approval_rate)
- **1.3** Turn time calculation from lease chain analysis (24 properties)
- **1.4** Loss-to-lease estimate from pricing metrics (~15 properties with data)
- **1.5** Projected occupancy 30/60/90d from pipeline data

### ➡️ NEXT: Step 1.6 — ALN Market Rent Comparison
**Why**: Last step in Phase 1. Connects ALN comp data (already available in separate project) to dashboard.
- Connect ALN API data to unified.db
- **~4 hours**

### ➡️ THEN: Phase 2 — Financial Reports
**Why**: Single biggest unlock — one report type opens 17+ fields.
- **BLOCKED** on user capturing Financial Summary report ID from RealPage web UI

---

*Work plan maintained in: `/OwnerDashV2/NASA_WORKPLAN.md`*
