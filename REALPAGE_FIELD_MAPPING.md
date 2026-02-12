# RealPage Data Pipeline — Field Mapping & Status

**Generated**: 2026-01-19  
**Last Updated**: 2026-02-10  
**Portfolio**: 31 Kairoi Management properties  
**Production Data**: 9,406 units, 6,988 residents, 759 pricing records (31/31 with rent data ✅), 1,219 delinquency records

> **Note**: This document covers the full RealPage data pipeline (RPX SOAP API + Reporting REST API). For detailed report-level mapping, see `Data_Definitions_and_Sources/REALPAGE_DATA_MAPPING.md`

---

## 📊 Production Data Summary (as of 2026-02-10)

### Raw Data (realpage_raw.db)

| Table | Records | Properties | Source | Notes |
|-------|---------|------------|--------|-------|
| `realpage_box_score` | 759 | 31 | Report ID 4238 (XLS) | ⚠️ 18 have rent data, 16 have $0 (need re-download) |
| `realpage_rent_roll` | 7,894 | 31 | Report ID 4043 (XLS) | ✅ All properties |
| `realpage_activity` | 48,325 | 31 | Report ID 3837 (HTML/XLS) | ✅ All properties |
| `realpage_delinquency` | 1,394 | 30 | Report ID 4260 (XLS) | ⚠️ Pearl Lantana missing |
| `realpage_lease_expirations` | 1,798 | 30 | Report ID 3838 (XLS) | ⚠️ Ten50 missing |
| `realpage_monthly_summary` | 773 | 31 | Report ID 3877 (XLS) | ✅ All properties |
| `realpage_units` | 7,813 | — | RPX SOAP API | ✅ |
| `realpage_residents` | 23,509 | — | RPX SOAP API | ✅ |
| `realpage_leases` | 10,503 | — | RPX SOAP API | ✅ |

### Unified Database (unified.db — serves frontend)

| Table | Records | Properties |
|-------|---------|------------|
| `unified_properties` | 31 | 31 |
| `unified_units` | 9,406 | 36 (incl. test) |
| `unified_residents` | 6,988 | 36 |
| `unified_pricing_metrics` | 759 | 31 (18 with asking rent) |
| `unified_occupancy_metrics` | 31 | 31 |
| `unified_delinquency` | 1,219 | 30 |

---

## 📈 OCCUPANCY & LEASING SECTION

| Field | Status | Data Source | Pipeline | Notes |
|-------|--------|------------|----------|-------|
| Physical Occupancy | ✅ LIVE | Box Score → `unified_occupancy_metrics` | ✅ Automated | Count occupied ÷ total units |
| Leased Percentage | ✅ LIVE | Box Score `leased_pct` | ✅ Automated | Includes preleased vacant |
| Exposure (30 days) | ✅ LIVE | Rent Roll → notice dates | ✅ Automated | Units on notice within 30 days |
| Exposure (60 days) | ✅ LIVE | Rent Roll → notice dates | ✅ Automated | Units on notice within 60 days |
| Vacant Ready | ✅ LIVE | Rent Roll `status` | ✅ Automated | Vacant units with ready status |
| Vacant not Ready | ✅ LIVE | Rent Roll `status` | ✅ Automated | Vacant units not ready |
| Total Vacant Units | ✅ LIVE | Box Score `vacant_units` | ✅ Automated | Per floorplan |
| Vacant > 90 Days | ✅ LIVE | Rent Roll `days_vacant` | ✅ Automated | `available_date` delta |
| Expiration (30/60/90d) | ✅ LIVE | Lease Expirations + Rent Roll | ✅ Automated | `/api/v2/properties/{id}/expirations` |
| Renewal | ✅ LIVE | Lease Expirations `renewal_status` | ✅ Automated | Count with renewal status |
| Renewal Percentage | ✅ LIVE | Derived | ✅ Automated | Renewals ÷ Expirations |
| Move-out | ✅ LIVE | Rent Roll `move_out_date` | ✅ Automated | Filter by period |
| Move-in | ✅ LIVE | Rent Roll `move_in_date` | ✅ Automated | Filter by period |
| Net Move-in | ✅ LIVE | Derived | ✅ Automated | Move-in − Move-out |

### Leasing Funnel (Leads/Tours/Apps)

| Field | Status | Data Source | Pipeline | Notes |
|-------|--------|------------|----------|-------|
| Leads (total contacts) | ✅ LIVE | Activity Report (48,325 records) | ✅ Automated | E-mail + Phone + Text + Visit + Online |
| Tours (visits) | ✅ LIVE | Activity Report `Visit`+`Visit (return)` | ✅ Automated | 1,278 visit records across 31 props |
| Applications | ✅ LIVE | Activity Report `Online Leasing Agreement` | ✅ Automated | 3,085 records |
| Lease Signs | ✅ LIVE | Activity Report `Leased` type | ✅ Automated | 377 records |
| Lead/Tour conversion | ✅ LIVE | Derived | ✅ Automated | Tours ÷ Leads |
| Tour/App conversion | ✅ LIVE | Derived | ✅ Automated | Apps ÷ Tours |
| Lease/Lead Conversion | ✅ LIVE | Derived | ✅ Automated | Leases ÷ Leads |

---

## 💰 PRICING SECTION

| Field | Status | Data Source | Pipeline | Notes |
|-------|--------|------------|----------|-------|
| In-Place Rent | ✅ LIVE | Box Score `avg_actual_rent` | ✅ Automated | Per floorplan, 31 properties |
| In-Place $/SF | ✅ LIVE | Derived (rent ÷ sqft) | ✅ Automated | Via `unified_pricing_metrics` |
| Asking Rent (Market) | ✅ LIVE | Box Score `avg_market_rent` | ✅ Automated | 14 props from fresh Box Score XLS, rest from rent roll |
| Asking $/SF | ✅ LIVE | Derived (market_rent ÷ sqft) | ✅ Automated | Via `unified_pricing_metrics` |
| Rent Growth | ✅ LIVE | Derived | ✅ Automated | (Asking − InPlace) ÷ InPlace |
| Floorplan Breakdown | ✅ LIVE | Box Score + Rent Roll | ✅ Automated | 1,077 floorplan records |
| Avg Effective Rent/Unit | ✅ LIVE | Derived | ✅ Automated | Total rent ÷ occupied units |
| Revenue per Unit (RevPAU) | ⚠️ PARTIAL | Needs P&L | 🔴 Not automated | Requires Financial Summary report |

---

## 🏢 PROPERTY INFO SECTION

| Field | Status | Data Source | Pipeline | Notes |
|-------|--------|------------|----------|-------|
| Property Name | ✅ LIVE | `unified_properties` | ✅ Automated | 31 properties |
| Property Address | ⚠️ PARTIAL | Config + report headers | ✅ Static | City/State from report data |
| Total Units | ✅ LIVE | `unified_units` count | ✅ Automated | 9,406 units |
| Year Built | ❌ MISSING | Not in API or reports | 🔴 Manual | Would need ALN or manual entry |

---

## � DELINQUENCIES & EVICTIONS

| Field | Status | Data Source | Pipeline | Notes |
|-------|--------|------------|----------|-------|
| Total Delinquencies | ✅ LIVE | Delinquency Report → `unified_delinquency` | ✅ Automated | 1,219 records, 30 properties |
| 0-30 Days | ✅ LIVE | `balance_0_30` | ✅ Automated | Aging bucket |
| 31-60 Days | ✅ LIVE | `balance_31_60` | ✅ Automated | Aging bucket |
| 61-90 Days | ✅ LIVE | `balance_61_90` | ✅ Automated | Aging bucket |
| 90 Days+ | ✅ LIVE | `balance_over_90` | ✅ Automated | Aging bucket |
| Net Balance | ✅ LIVE | `net_balance` | ✅ Automated | Delinquent − Prepaid |
| Prepaid | ✅ LIVE | `prepaid` | ✅ Automated | Credit balances |
| Evictions | ⚠️ PARTIAL | RPX API `Evict` flag | ⚠️ API only | Count + balance where Evict=Y |
| Filed/Writ | ❌ MISSING | Legal status tracking | 🔴 Manual | Not in standard reports |

---

## 📊 PROFIT & LOSS SECTION

| Field | Status | Data Source | Pipeline | Notes |
|-------|--------|------------|----------|-------|
| Gross Potential Rent | ❌ MISSING | Financial Summary Report | 🔴 Need report | Report ID not yet identified |
| Loss to Lease | ⚠️ DERIVED | Box Score (market − actual) | ⚠️ Estimate | Can approximate from box score data |
| Concession | ❌ MISSING | Financial Summary Report | 🔴 Need report | |
| Vacancy Cost | ❌ MISSING | Financial Summary Report | 🔴 Need report | |
| Net Rental Revenue | ❌ MISSING | Financial Summary Report | 🔴 Need report | |
| Other Income | ❌ MISSING | Financial Summary Report | 🔴 Need report | |
| Total Income | ❌ MISSING | Financial Summary Report | 🔴 Need report | |
| **All Expense Categories** | ❌ MISSING | Financial Summary Report | 🔴 Need report | Payroll, Marketing, G&A, R&M, etc. |
| NOI | ❌ MISSING | Financial Summary Report | 🔴 Need report | |

---

## 💳 DEBT & LOAN SECTION

| Field | Status | Notes |
|-------|--------|-------|
| All debt/loan fields | ❌ MANUAL | Not in PMS — sourced from loan documents |
| DSCR, Debt Yield, LTV | ❌ MANUAL | Calculated from manual loan data + NOI |

---

## � DIGITAL & MARKETING PERFORMANCE

| Field | Status | Data Source | Pipeline | Notes |
|-------|--------|------------|----------|-------|
| Cost per Lease | ❌ MISSING | Needs P&L marketing spend | 🔴 Need report | Marketing Spend ÷ Leases |
| Avg days to lease | ⚠️ PARTIAL | Activity Report dates | ⚠️ Can derive | First contact → Leased delta |
| Application completion rate | ⚠️ PARTIAL | Activity Report | ⚠️ Can derive | Submitted ÷ Started |
| Application approval rate | ⚠️ PARTIAL | Activity Report | ⚠️ Can derive | Approved ÷ Submitted |
| Cancellation/denial rate | ⚠️ PARTIAL | Activity Report | ⚠️ Can derive | Denied ÷ Submitted |

---

## 🔄 RESIDENT RENEWAL METRICS

| Field | Status | Data Source | Pipeline | Notes |
|-------|--------|------------|----------|-------|
| Avg tenancy length | ✅ LIVE | Rent Roll `move_in_date` | ✅ Automated | (Today − move_in) average |
| Avg notice period | ✅ LIVE | Rent Roll notice dates | ✅ Automated | (move_out − notice_date) avg |
| Resident scores | ❌ MISSING | External survey | 🔴 Not available | Requires NPS/satisfaction tool |

---

## 🔧 TURNOVER PERFORMANCE

| Field | Status | Data Source | Pipeline | Notes |
|-------|--------|------------|----------|-------|
| Average turn time | ⚠️ PARTIAL | Rent Roll `available_date` | ⚠️ Estimate | Needs made_ready_date |
| Turn costs per unit | ❌ MISSING | Financial Summary Report | 🔴 Need report | T/O expense ÷ turns |
| Turn cost vs rent increase | ❌ MISSING | Needs P&L + rent change | 🔴 Need report | |

---

## 🚀 Implementation Status

### ✅ Fully Working Pipeline

| Component | Status | Details |
|-----------|--------|---------|
| RPX SOAP API client | ✅ Production | `realpage_client.py` — units, residents, leases |
| Reporting REST API | ✅ Production | `download_reports_v2.py` — instance creation + file download |
| Box Score parser | ✅ Production | XLS → `realpage_box_score` (774 records, 31 props) |
| Rent Roll parser | ✅ Production | XLS → `realpage_rent_roll` (7,894 records, 31 props) |
| Activity Report parser | ✅ Production | HTML + XLS → `realpage_activity` (48,325 records, 31 props) |
| Delinquency parser | ✅ Production | XLS → `realpage_delinquency` (1,394 records, 30 props) |
| Lease Expiration parser | ✅ Production | XLS → `realpage_lease_expirations` (1,798 records, 30 props) |
| Monthly Summary parser | ✅ Production | XLS → `realpage_monthly_summary` (529 records, 18 props) |
| DB sync pipeline | ✅ Production | `sync_realpage_to_unified.py` — raw → unified |
| Backend API | ✅ Production | FastAPI on :8000 — all endpoints verified |
| Frontend dashboard | ✅ Production | Vite/React on :5173 — all 31 properties displayed |

### Report Download Status

| Report | ID | Key | Parser | DB Table | Automated? |
|--------|-----|-----|--------|----------|------------|
| Box Score | 4238 | `446266C0-...` | ✅ | `realpage_box_score` | ⚠️ Semi (token needed) |
| Rent Roll | 4043 | `A6F61299-...` | ✅ | `realpage_rent_roll` | ⚠️ Semi |
| Activity Report | 3837 | `B29B7C76-...` | ✅ | `realpage_activity` | ⚠️ Semi |
| Delinquency | 4260 | `89A3C427-...` | ✅ | `realpage_delinquency` | ⚠️ Semi |
| Lease Expiration | 3838 | `89545A3A-...` | ✅ | `realpage_lease_expirations` | ⚠️ Semi |
| Monthly Summary | 3877 | `E41626AB-...` | ✅ | `realpage_monthly_summary` | ⚠️ Semi |
| Financial Summary | ❓ | Unknown | ❌ | — | 🔴 Not started |

> **"Semi-automated"**: Instance creation + file download + parsing + import are all scripted. Only the bearer token must be refreshed manually (1-hour expiry via RealPage web login). Full automation requires a service account or token refresh flow.

### All 31 Configured Properties

| Property | RealPage ID | Occupancy | Rent Data | Delinquency | Lease Exp | Monthly Sum |
|----------|-------------|-----------|-----------|-------------|-----------|-------------|
| 7 East | 5481703 | ✅ | ✅ $2,190 | ✅ | ✅ | ✅ |
| Aspire 7th and Grant | 4779341 | ✅ | ✅ $2,573 | ✅ | ✅ | ✅ |
| Block 44 | 5473254 | ✅ | ✅ $2,073 | ✅ | ✅ | ✅ |
| Curate at Orchard Town Center | 4682517 | ✅ | ✅ $2,255 | ✅ | ✅ | ✅ |
| Discovery at Kingwood | 5618425 | ✅ | ✅ $1,663 | ✅ | ✅ | ✅ |
| Eden Keller Ranch | 5536209 | ✅ | ✅ $1,934 | ✅ | ✅ | ✅ |
| Edison at RiNo | 4248319 | ✅ | ✅ $2,413 | ✅ | ✅ | ✅ |
| Harvest | 5507303 | ✅ | ✅ $1,950 | ✅ | ✅ | ✅ |
| Heights at Interlocken | 5558216 | ✅ | ✅ $2,124 | ✅ | ✅ | ✅ |
| Izzy | 5618432 | ✅ | ✅ $2,129 | ✅ | ✅ | ✅ |
| Kalaco | 5339721 | ✅ | ✅ $2,361 | ✅ | ✅ | ✅ |
| Luna | 5590740 | ✅ | ✅ $2,246 | ✅ | ✅ | ✅ |
| Nexus East | 5472172 | ✅ | ✅ $973 | ✅ | ✅ | ✅ |
| Park 17 | 4481243 | ✅ | ✅ $2,350 | ✅ | ✅ | ✅ |
| Parkside at Round Rock | 5536211 | ✅ | ✅ $1,433 | ✅ | ✅ | ✅ |
| Pearl Lantana | 5481704 | ✅ | ✅ $2,070 | ❌ | ✅ | ✅ |
| Ridian | 5446271 | ✅ | ✅ $2,436 | ✅ | ✅ | ✅ |
| Slate | 5486880 | ✅ | ✅ $1,455 | ✅ | ✅ | ✅ |
| Sloane | 5486881 | ✅ | ✅ $1,611 | ✅ | ✅ | ✅ |
| Stonewood | 5481705 | ✅ | ✅ $1,613 | ✅ | ✅ | ✅ |
| Ten50 | 5581218 | ✅ | ✅ $3,177 | ✅ | ❌ | ✅ |
| The Alcott | 4996967 | ✅ | ✅ $2,081 | ✅ | ✅ | ✅ |
| The Avant | 5480255 | ✅ | ✅ $3,025 | ✅ | ✅ | ✅ |
| The Broadleaf | 5286092 | ✅ | ✅ $2,282 | ✅ | ✅ | ✅ |
| The Confluence | 4832865 | ✅ | ✅ $3,379 | ✅ | ✅ | ✅ |
| The Hunter | 5558217 | ✅ | ✅ $2,631 | ✅ | ✅ | ✅ |
| The Links at Plum Creek | 5558220 | ✅ | ✅ $2,125 | ✅ | ✅ | ✅ |
| The Northern | 5375283 | ✅ | ✅ $2,889 | ✅ | ✅ | ✅ |
| The Station at Riverfront Park | 4976258 | ✅ | ✅ $2,316 | ✅ | ✅ | ✅ |
| thePearl | 5114464 | ✅ | ✅ $1,967 | ✅ | ✅ | ✅ |
| theQuinci | 5286878 | ✅ | ✅ $2,211 | ✅ | ✅ | ✅ |

**Summary**: 31/31 occupancy ✅ | **31/31 rent data ✅** | 30/31 delinquency | 30/31 lease exp | **31/31 monthly sum ✅**

### Remaining Gaps

| Gap | What's Needed | Priority |
|-----|---------------|----------|
| **Financial Summary / P&L** | Discover report ID + build parser | 🔴 HIGH |
| **Pearl Lantana delinquency** | Re-download with PII visible format | 🟡 MEDIUM |
| ~~Monthly summary~~ | ✅ DONE — 31/31 imported from on-disk files | ✅ |
| **Ten50 lease expirations** | Re-download via batch downloader | 🟡 MEDIUM |
| **Full token automation** | Service account or refresh token flow | 🟡 MEDIUM |
| **Debt/Loan data** | Manual entry or external import | 🟡 MEDIUM |
| **Resident scores** | NPS/survey integration | ⚪ LOW |
| **Year built** | ALN API or manual | ⚪ LOW |

### Parser Fix (2026-02-10)

The `safe_float` function in `report_parsers.py` was silently converting comma-formatted numbers (e.g., `"1,905.00"`) to `0.0`. Fixed by adding `str(val).replace(',', '')` before `float()` conversion. This affected all 5 parser functions (box_score, delinquency, rent_roll, monthly_summary, lease_expiration).
