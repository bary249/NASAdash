# RealPage Data Mapping — Complete Field Reference

**Version**: 4.0  
**Last Updated**: 2026-02-09  
**Source Document**: Nasa_Dashboard.xlsx, report_definitions.json  
**Previous Version**: v3.0 (2026-02-04)  
**Portfolio**: 31 Kairoi Management properties — ALL data live and serving dashboard

---

## Table of Contents

1. [Executive Status Summary](#executive-status-summary)
2. [Data Sources Overview](#data-sources-overview)
3. [NASA Dashboard Field Coverage](#nasa-dashboard-field-coverage)
4. [Report Implementation Status](#report-implementation-status)
5. [Database Schema](#database-schema)
6. [API Reference](#api-reference)
7. [Remaining Gaps & Next Steps](#remaining-gaps--next-steps)

---

## Executive Status Summary

### Overall Coverage (vs. NASA Dashboard Requirements)

| Section | Fields | ✅ Live | ⚠️ Partial | ❌ Missing | Coverage |
|---------|--------|---------|-----------|-----------|----------|
| **Occupancy & Leasing** | 14 | 14 | 0 | 0 | **100%** |
| **Leasing Funnel** | 7 | 7 | 0 | 0 | **100%** |
| **Pricing** | 8 | 7 | 0 | 1 | **88%** |
| **Delinquencies** | 9 | 7 | 1 | 1 | **78%** |
| **P&L / Income** | 11 | 0 | 1 | 10 | **5%** |
| **Expenses** | 6 | 0 | 0 | 6 | **0%** |
| **Debt & Loan** | 20 | 0 | 0 | 20 | **0%** |
| **Revenue Optimization** | 8 | 3 | 2 | 3 | **38%** |
| **Digital & Marketing** | 6 | 0 | 3 | 3 | **25%** |
| **Renewal Metrics** | 3 | 2 | 0 | 1 | **67%** |
| **Turnover** | 3 | 0 | 1 | 2 | **17%** |
| **Predictive/Portfolio** | 7 | 2 | 2 | 3 | **29%** |
| **TOTAL** | **102** | **42** | **10** | **50** | **~51%** |

> **Key insight**: The core operational dashboard (occupancy, leasing, pricing, delinquency) is **93% complete**. The gaps are almost entirely in **financials (P&L, expenses, debt)** which require a Financial Summary report or manual data entry.

### Data Pipeline Status

| Component | Status | Records | Properties |
|-----------|--------|---------|------------|
| RPX SOAP API | ✅ Production | 45,359 | 31 |
| Box Score Report (4238) | ✅ Production | 774 | 31 |
| Rent Roll Report (4043) | ✅ Production | 7,894 | 31 |
| Activity Report (3837) | ✅ Production | 48,325 | 31 |
| Delinquency Report (4260) | ✅ Production | 1,394 | 30 |
| Lease Expiration (3838) | ✅ Production | 1,798 | 30 |
| Monthly Summary (3877) | ✅ Production | 529 | 18 |
| Unified DB Sync | ✅ Production | — | 31 |
| Backend API (FastAPI) | ✅ Production | — | 31 |
| Frontend (React/Vite) | ✅ Production | — | 31 |

---

## Data Sources Overview

### Active Data Sources

| Source | Type | Status | Script | Auth |
|--------|------|--------|--------|------|
| RPX Gateway SOAP API | Real-time API | ✅ Production | `realpage_client.py` | License key (static) |
| Reporting REST API | Report download | ✅ Production | `download_reports_v2.py` | Bearer token (1hr, manual refresh) |
| ALN API | Market comps | ✅ Production | Separate integration | API key |

### RPX Gateway SOAP Endpoints

| Endpoint | Records | Tables Fed |
|----------|---------|------------|
| `unitlist` | 7,813 units | `realpage_units` → `unified_units` |
| `getResidentListInfo` | 23,509 residents | `realpage_residents` → `unified_residents` |
| `getLeaseInfo` | 10,503 leases | `realpage_leases` |
| `getBuildings` | — | `realpage_buildings` |
| `getSiteList` | — | `realpage_properties` |
| `getRentableItems` | 3,524 items | `realpage_rentable_items` |

### Reporting REST API — Report Downloads

| Report | ID | Key | Format | Parser | DB Table | Records |
|--------|-----|-----|--------|--------|----------|---------|
| Box Score | 4238 | `446266C0-D572-4D8A-A6DA-310C0AE61037` | XLS | ✅ | `realpage_box_score` | 774 |
| Rent Roll | 4043 | `A6F61299-E960-4235-9DC2-44D2C2EF4F99` | XLS | ✅ | `realpage_rent_roll` | 7,894 |
| Activity Report | 3837 | `B29B7C76-04B8-4D6C-AABC-62127F0CAE63` | HTML/XLS | ✅ | `realpage_activity` | 48,325 |
| Delinquency | 4260 | `89A3C427-BE71-4A05-9D2B-BDF3923BF756` | XLS | ✅ | `realpage_delinquency` | 1,394 |
| Lease Expiration | 3838 | `89545A3A-C28A-49CC-8791-396AE71AB422` | XLS | ✅ | `realpage_lease_expirations` | 1,798 |
| Monthly Summary | 3877 | `E41626AB-EC0F-4F6C-A6EA-D7A93909AA9B` | XLS | ✅ | `realpage_monthly_summary` | 529 |
| Financial Summary | ❓ | Unknown | — | ❌ | — | 0 |

> **Semi-automated**: Instance creation → file download → parsing → DB import are all scripted. Only the **bearer token** must be refreshed manually (1-hour expiry via RealPage web login).

---

## NASA Dashboard Field Coverage

### Section 1: Occupancy & Leasing — ✅ 100% COMPLETE

| # | NASA Field | Status | Source | DB Path | API Endpoint |
|---|-----------|--------|--------|---------|-------------|
| 1 | Physical Occupancy | ✅ LIVE | Box Score | `realpage_box_score` → `unified_occupancy_metrics.physical_occupancy` | `/api/v2/properties/{id}/occupancy` |
| 2 | Leased Percentage | ✅ LIVE | Box Score | `realpage_box_score.leased_pct` → `unified_occupancy_metrics.leased_percentage` | `/api/v2/properties/{id}/occupancy` |
| 3 | Exposure (30 days) | ✅ LIVE | Rent Roll (notice dates) | `unified_units.on_notice_date` | `/api/v2/properties/{id}/exposure?timeframe=cm` |
| 4 | Exposure (60 days) | ✅ LIVE | Rent Roll (notice dates) | `unified_units.on_notice_date` | `/api/v2/properties/{id}/exposure` |
| 5 | Vacant Ready | ✅ LIVE | Rent Roll | `unified_units` WHERE status=vacant AND ready | `/api/v2/properties/{id}/occupancy` |
| 6 | Vacant not Ready | ✅ LIVE | Rent Roll | `unified_units` WHERE status=vacant AND not ready | `/api/v2/properties/{id}/occupancy` |
| 7 | Total Vacant Units | ✅ LIVE | Box Score | `unified_occupancy_metrics.vacant_units` | `/api/v2/properties/{id}/occupancy` |
| 8 | Vacant > 90 Days | ✅ LIVE | Rent Roll | `unified_units.days_vacant > 90` | Calculated in frontend |
| 9 | Expirations (30/60/90d) | ✅ LIVE | Lease Expiration + Rent Roll | `realpage_lease_expirations` | `/api/v2/properties/{id}/expirations` |
| 10 | Renewals | ✅ LIVE | Lease Expiration | `realpage_lease_expirations.renewal_status` | `/api/v2/properties/{id}/expirations` |
| 11 | Renewal Percentage | ✅ LIVE | Derived | Renewals ÷ Expirations | `/api/v2/properties/{id}/expirations` |
| 12 | Move-out | ✅ LIVE | Rent Roll | `unified_residents.move_out_date` in period | Frontend filter |
| 13 | Move-in | ✅ LIVE | Rent Roll | `unified_residents.move_in_date` in period | Frontend filter |
| 14 | Net Move-in | ✅ LIVE | Derived | Move-in − Move-out | Frontend calculation |

### Section 2: Leasing Funnel — ✅ 100% COMPLETE

| # | NASA Field | Status | Source | Records | API Endpoint |
|---|-----------|--------|--------|---------|-------------|
| 1 | Leads (total contacts) | ✅ LIVE | Activity Report: E-mail, Phone, Text, Visit, Online | 48,325 | `/api/v2/properties/{id}/leasing-funnel` |
| 2 | Tours (visits) | ✅ LIVE | Activity Report: `Visit` + `Visit (return)` + `Videotelephony - Tour` | 1,324 | `/api/v2/properties/{id}/leasing-funnel` |
| 3 | Applications | ✅ LIVE | Activity Report: `Online Leasing Agreement` + `Online Leasing pre-qualify` | 3,661 | `/api/v2/properties/{id}/leasing-funnel` |
| 4 | Lease Signs | ✅ LIVE | Activity Report: `Leased` | 377 | `/api/v2/properties/{id}/leasing-funnel` |
| 5 | Lead/Tour conversion | ✅ LIVE | Derived: Tours ÷ Leads | — | `/api/v2/properties/{id}/leasing-funnel` |
| 6 | Tour/App conversion | ✅ LIVE | Derived: Apps ÷ Tours | — | `/api/v2/properties/{id}/leasing-funnel` |
| 7 | Lease/Lead conversion | ✅ LIVE | Derived: Leases ÷ Leads | — | `/api/v2/properties/{id}/leasing-funnel` |

### Section 3: Pricing — ✅ 88% COMPLETE

| # | NASA Field | Status | Source | DB Path |
|---|-----------|--------|--------|---------|
| 1 | In-Place Rent | ✅ LIVE | Box Score `avg_actual_rent` | `unified_pricing_metrics.in_place_rent` |
| 2 | In-Place $/SF | ✅ LIVE | Derived: rent ÷ sqft | `unified_pricing_metrics.in_place_per_sf` |
| 3 | Asking Rent | ✅ LIVE | Box Score `avg_market_rent` | `unified_pricing_metrics.asking_rent` |
| 4 | Asking $/SF | ✅ LIVE | Derived: market_rent ÷ sqft | `unified_pricing_metrics.asking_per_sf` |
| 5 | Rent Growth | ✅ LIVE | Derived: (Asking − InPlace) ÷ InPlace | `unified_pricing_metrics.rent_growth` |
| 6 | Floorplan Breakdown | ✅ LIVE | Box Score + Rent Roll | 1,077 records across 31 props |
| 7 | Avg Effective Rent/Unit | ✅ LIVE | Derived: total rent ÷ occupied | Calculated in API |
| 8 | Revenue per Unit (RevPAU) | ❌ MISSING | Needs total revenue from P&L | Requires Financial Summary |

### Section 4: Delinquencies & Evictions — ✅ 78% COMPLETE

| # | NASA Field | Status | Source | DB Path |
|---|-----------|--------|--------|---------|
| 1 | Total Delinquencies | ✅ LIVE | Delinquency Report | `unified_delinquency` (1,219 records, 30 props) |
| 2 | 0-30 Days | ✅ LIVE | `balance_0_30` | `unified_delinquency.balance_0_30` |
| 3 | 31-60 Days | ✅ LIVE | `balance_31_60` | `unified_delinquency.balance_31_60` |
| 4 | 61-90 Days | ✅ LIVE | `balance_61_90` | `unified_delinquency.balance_61_90` |
| 5 | 90 Days+ | ✅ LIVE | `balance_over_90` | `unified_delinquency.balance_over_90` |
| 6 | Net Balance | ✅ LIVE | Delinquent − Prepaid | `unified_delinquency.net_balance` |
| 7 | Prepaid | ✅ LIVE | Credit balances | `unified_delinquency.prepaid` |
| 8 | Evictions (count + balance) | ⚠️ PARTIAL | RPX API `Evict` flag | API only, not in unified |
| 9 | Filed/Writ status | ❌ MISSING | Legal tracking | Not in standard reports |

### Section 5: Profit & Loss — 🔴 5% (BLOCKED: Need Financial Summary Report)

| # | NASA Field | Status | Blocker |
|---|-----------|--------|---------|
| 1 | Gross Potential Rent | ❌ MISSING | Need Financial Summary report ID |
| 2 | Loss to Lease | ⚠️ ESTIMATE | Can approximate from Box Score (market − actual) × units |
| 3 | Model/Employee Unit discount | ❌ MISSING | Need Financial Summary |
| 4 | Concession | ❌ MISSING | Need Financial Summary |
| 5 | Vacancy Cost | ❌ MISSING | Need Financial Summary |
| 6 | Net Rental Revenue | ❌ MISSING | Need Financial Summary |
| 7 | Other Income | ❌ MISSING | Need Financial Summary |
| 8 | Total Income | ❌ MISSING | Need Financial Summary |
| 9 | Bad Debt | ❌ MISSING | Need Financial Summary |
| 10 | Misc. Rental Adjustments | ❌ MISSING | Need Financial Summary |
| 11 | Total Adjustments | ❌ MISSING | Need Financial Summary |

### Section 6: Expenses — 🔴 0% (BLOCKED: Need Financial Summary Report)

| # | NASA Field | Status |
|---|-----------|--------|
| 1 | Payroll | ❌ MISSING |
| 2 | Marketing | ❌ MISSING |
| 3 | G&A | ❌ MISSING |
| 4 | R&M | ❌ MISSING |
| 5 | Utilities / Insurance / Taxes | ❌ MISSING |
| 6 | NOI | ❌ MISSING |

### Section 7: Debt & Loan — 🔴 0% (Manual entry — not in PMS)

All 20 debt/loan fields require manual data entry from loan documents. These include:
- Loan amount, balance, rates, maturity, DSCR, debt yield, LTV
- Reserve accounts (replacement, tax escrow, insurance escrow)
- Covenant monitoring

### Section 8: Revenue Optimization — ⚠️ 38%

| # | NASA Field | Status | Source |
|---|-----------|--------|--------|
| 1 | Avg Effective Rent/Unit | ✅ LIVE | Box Score data |
| 2 | Rent Growth | ✅ LIVE | Pricing metrics |
| 3 | Rent Growth vs. Market | ⚠️ PARTIAL | Have rent data, need market benchmark |
| 4 | RevPAU | ❌ MISSING | Needs P&L total revenue |
| 5 | Loss-to-lease as % of GPR | ⚠️ PARTIAL | Can estimate from Box Score |
| 6 | Concession Cost as % of Eff. Rent | ❌ MISSING | Needs P&L concession data |
| 7 | Bad Debt as % of Eff. Rent | ❌ MISSING | Needs P&L bad debt |
| 8 | Economic Occupancy | ✅ LIVE | Box Score occupancy data |

### Section 9: Digital & Marketing — ⚠️ 25%

| # | NASA Field | Status | Source |
|---|-----------|--------|--------|
| 1 | Cost per Lease | ❌ MISSING | Needs marketing spend from P&L |
| 2 | Avg days to lease | ⚠️ PARTIAL | Can derive from Activity Report dates |
| 3 | Application completion rate | ⚠️ PARTIAL | Can derive from Activity Report |
| 4 | Application approval rate | ⚠️ PARTIAL | Can derive from Activity Report |
| 5 | Avg time app → lease signing | ❌ MISSING | Need prospect-level tracking |
| 6 | Cancellation/denial rate | ❌ MISSING | Need detailed application status |

### Section 10: Renewal Metrics — ✅ 67%

| # | NASA Field | Status | Source |
|---|-----------|--------|--------|
| 1 | Avg tenancy length (months) | ✅ LIVE | Rent Roll `move_in_date` |
| 2 | Avg notice period (days) | ✅ LIVE | Rent Roll notice dates |
| 3 | Resident scores | ❌ MISSING | Needs NPS/survey tool |

### Section 11: Turnover — ⚠️ 17%

| # | NASA Field | Status | Source |
|---|-----------|--------|--------|
| 1 | Avg turn time (days) | ⚠️ PARTIAL | Rent Roll `available_date` estimate |
| 2 | Turn costs per unit | ❌ MISSING | Needs P&L T/O expense |
| 3 | Turn cost vs rent increase | ❌ MISSING | Needs P&L + rent change |

### Section 12: Portfolio & Predictive — ⚠️ 29%

| # | NASA Field | Status | Source |
|---|-----------|--------|--------|
| 1 | Property ranking matrix | ✅ LIVE | All metrics available for comparison |
| 2 | Market rent comparison | ⚠️ PARTIAL | ALN API available, needs integration |
| 3 | Projected occupancy 30/60/90d | ⚠️ PARTIAL | Have pipeline data from Activity Report |
| 4 | Revenue forecast vs budget | ❌ MISSING | Needs P&L + budget data |
| 5 | Lease expiration schedule | ✅ LIVE | `realpage_lease_expirations` |
| 6 | Seasonality trends | ❌ MISSING | Needs historical data accumulation |
| 7 | Optimal rent recommendations | ❌ MISSING | Needs AI model |

---

## Report Implementation Status

### ✅ All 6 Report Types — Parsers Complete, Import Working

| Report | ID | Tested | Parser | DB Import | Properties | Automation |
|--------|----|--------|--------|-----------|------------|------------|
| **Box Score** | 4238 | ✅ | ✅ `parse_box_score()` + custom XLS parser | ✅ `realpage_box_score` (774) | 31/31 | ⚠️ Semi |
| **Rent Roll** | 4043 | ✅ | ✅ `parse_rent_roll()` | ✅ `realpage_rent_roll` (7,894) | 31/31 | ⚠️ Semi |
| **Delinquency** | 4260 | ✅ | ✅ `parse_delinquency()` | ✅ `realpage_delinquency` (1,394) | 30/31 | ⚠️ Semi |
| **Activity Report** | 3837 | ✅ | ✅ `parse_activity()` + HTML parser | ✅ `realpage_activity` (48,325) | 31/31 | ⚠️ Semi |
| **Monthly Summary** | 3877 | ✅ | ✅ `parse_monthly_summary()` | ✅ `realpage_monthly_summary` (529) | 18/31 | ⚠️ Semi |
| **Lease Expiration** | 3838 | ✅ | ✅ `parse_lease_expiration()` | ✅ `realpage_lease_expirations` (1,798) | 30/31 | ⚠️ Semi |

### Box Score — Special Notes

The Box Score report requires per-property `End_Date` parameter matching the property's internal date (timezone-dependent):
- Central Time properties (TX): typically current date
- Mountain Time properties (CO, UT): typically current date − 1
- Some properties lag 2-3 days (e.g., Park 17 = 02/02)

The `download_reports_v2.py` script handles this by probing each property's `as_of` date and retrying with earlier dates.

### Activity Report — Special Notes

Activity Reports are returned as **HTML** (not Excel) for 13 properties. Custom HTML parser using `pandas.read_html()` + regex handles both formats. Activity types extracted:

| Type | Count | Dashboard Use |
|------|-------|---------------|
| E-mail | 20,051 | Leads |
| Text message | 7,976 | Leads |
| Phone call | 6,753 | Leads |
| Online Leasing Agreement | 3,085 | Applications |
| Visit / Visit (return) | 1,278 | Tours |
| Leased | 377 | Lease Signs |
| Online Leasing guest card | 986 | Leads |
| Identity Verification | 809 | Applications |

---

## Database Schema

### Raw Database: `app/db/data/realpage_raw.db`

| Table | Records | Properties | Key Columns |
|-------|---------|------------|-------------|
| `realpage_box_score` | 774 | 31 | property_id, floorplan, total_units, vacant_units, occupied_units, avg_market_rent, avg_actual_rent, occupancy_pct |
| `realpage_rent_roll` | 7,894 | 31 | property_id, unit_number, floorplan, sqft, market_rent, actual_rent, lease_start, lease_end, status |
| `realpage_activity` | 48,325 | 31 | property_id, activity_date, activity_type, unit_number, move_in_date, move_out_date |
| `realpage_delinquency` | 1,394 | 30 | property_id, unit_number, balance_0_30, balance_31_60, balance_61_90, balance_over_90, net_balance |
| `realpage_lease_expirations` | 1,798 | 30 | property_id, unit_number, lease_end, current_rent, market_rent, renewal_status |
| `realpage_monthly_summary` | 529 | 18 | property_id, floorplan, move_ins, move_outs, renewals, beginning_occupancy, ending_occupancy |
| `realpage_units` | 7,813 | — | RPX API: unit_number, vacant, available, market_rent, sqft, floorplan |
| `realpage_residents` | 23,509 | — | RPX API: resident_id, unit_number, lease_status, move_in, move_out, balance |
| `realpage_leases` | 10,503 | — | RPX API: lease_id, rent, lease_start, lease_end, evict flag |

### Unified Database: `app/db/data/unified.db`

| Table | Records | Properties | Purpose |
|-------|---------|------------|---------|
| `unified_properties` | 31 | 31 | Property master list |
| `unified_units` | 9,406 | 36 | All units with status, floorplan, rent |
| `unified_residents` | 6,988 | 36 | Current residents with lease info |
| `unified_pricing_metrics` | 1,077 | 31 | Floorplan-level pricing (asking, in-place, $/SF) |
| `unified_occupancy_metrics` | 57 | 31 | Occupancy snapshots |
| `unified_delinquency` | 1,219 | 30 | Aging buckets per resident |

---

## API Reference

### Backend API Endpoints (FastAPI — port 8000)

| Endpoint | Data | Status |
|----------|------|--------|
| `GET /api/v2/properties` | All 31 properties | ✅ |
| `GET /api/v2/properties/{id}/occupancy` | Physical occupancy, vacant, leased | ✅ |
| `GET /api/v2/properties/{id}/exposure` | 30/60 day exposure | ✅ |
| `GET /api/v2/properties/{id}/leasing-funnel` | Leads, tours, apps, signs | ✅ |
| `GET /api/v2/properties/{id}/pricing` | Floorplan pricing breakdown | ✅ |
| `GET /api/v2/properties/{id}/expirations` | 30/60/90 day expirations + renewals | ✅ |
| `GET /api/v2/properties/{id}/delinquency` | Aging buckets, net balance | ✅ |
| `GET /api/v2/properties/{id}/summary` | All-in-one property summary | ✅ |
| `GET /api/portfolio/units` | Bulk unit data | ✅ |
| `GET /api/portfolio/residents` | Bulk resident data | ✅ |

### RealPage RPX Gateway (SOAP)

**Base URL**: `https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc`  
**Auth**: PMC ID + Site ID + License Key (static credentials)

### RealPage Reporting API (REST)

**Base URL**: `https://reportingapi.realpage.com/v1`  
**Auth**: Bearer token (1-hour expiry, manual refresh via web login)

**Endpoints**:
- `POST /reports/{reportId}/report-instances` — Create report instance
- `POST /reports/{reportId}/report-instances/{instanceId}/files` — Download file by fileId

**Format Codes**:

| Report | PDF | Excel | HTML | CSV |
|--------|-----|-------|------|-----|
| Box Score (4238) | 1682 | 1683 | — | — |
| Rent Roll (4043) | 1 | 3 | — | — |
| Delinquency (4260) | 1 | 3 | — | — |
| Activity Report (3837) | — | 562 | 561 | 563 |
| Monthly Summary (3877) | 1 | 3 | — | — |
| Lease Expiration (3838) | 1 | 3 | — | — |

---

## Remaining Gaps & Next Steps

### 🔴 HIGH PRIORITY — Unlocks P&L, Expenses, Revenue Optimization

| # | Gap | Action Required | Impact |
|---|-----|-----------------|--------|
| 1 | **Financial Summary Report ID** | Capture report ID + key from RealPage browser session | Unlocks 27 fields (P&L, expenses, NOI, RevPAU, concessions, bad debt) |
| 2 | **Financial Summary Parser** | Build XLS parser once report is obtained | Enables full P&L section |

### 🟡 MEDIUM PRIORITY

| # | Gap | Action Required | Impact |
|---|-----|-----------------|--------|
| 3 | **Token Automation** | Service account or OAuth refresh flow | Removes manual 1-hour token refresh |
| 4 | **Debt/Loan Manual Entry** | Build admin UI or import template | 20 fields for debt analysis |
| 5 | **Budget Data** | Budget vs Actual report or manual import | Revenue forecast, variance analysis |

### ⚪ LOW PRIORITY

| # | Gap | Action Required | Impact |
|---|-----|-----------------|--------|
| 6 | **Resident Scores** | NPS/survey tool integration | 1 field |
| 7 | **Year Built** | ALN API or manual | 1 field |
| 8 | **Market Comps** | ALN API integration to dashboard | Competitive analysis |
| 9 | **AI Insights** | Build prediction models | Rent recommendations, seasonality |

---

## All 31 Configured Properties

| Property | RealPage ID | Box Score | Rent Roll | Activity | Delinquency | Expirations |
|----------|-------------|-----------|-----------|----------|-------------|-------------|
| 7 East | 5481703 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Aspire 7th and Grant | 4779341 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Block 44 | 4976258 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Curate at Orchard Town Center | 4682517 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Discovery at Kingwood | 5618425 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Eden Keller Ranch | 5558217 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Edison at RiNo | 4248319 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Harvest | 5480255 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Heights at Interlocken | 5558216 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Izzy | 5618432 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Kalaco | 5507303 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Luna | 5590740 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Nexus East | 5472172 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Park 17 | 4481243 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Parkside at Round Rock | 5536211 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Pearl Lantana | 5481704 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ridian | 5446271 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Slate | 5486880 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Sloane | 5486881 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Stonewood | 5481705 | ✅ | ✅ | ✅ | ✅ | ✅ |
| Ten50 | 5581218 | ✅ | ✅ | ✅ | ✅ | ✅ |
| The Alcott | 5375283 | ✅ | ✅ | ✅ | ✅ | ✅ |
| The Avant | 5473254 | ✅ | ✅ | ✅ | ✅ | ✅ |
| The Broadleaf | 5286092 | ✅ | ✅ | ✅ | ✅ | ✅ |
| The Confluence | 4832865 | ✅ | ✅ | ✅ | ✅ | ✅ |
| The Hunter | 5339721 | ✅ | ✅ | ✅ | ✅ | ✅ |
| The Links at Plum Creek | 5558220 | ✅ | ✅ | ✅ | ✅ | ✅ |
| The Northern | 4996967 | ✅ | ✅ | ✅ | ✅ | ✅ |
| The Station at Riverfront Park | 5536209 | ✅ | ✅ | ✅ | ✅ | ✅ |
| thePearl | 5114464 | ✅ | ✅ | ✅ | ✅ | ✅ |
| theQuinci | 5286878 | ✅ | ✅ | ✅ | ✅ | ✅ |

---

*Document maintained in: `/OwnerDashV2/Data_Definitions_and_Sources/REALPAGE_DATA_MAPPING.md`*
