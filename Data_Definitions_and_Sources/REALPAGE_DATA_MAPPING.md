# RealPage Data Mapping - Complete Field Reference

**Version**: 3.0  
**Last Updated**: 2026-02-04  
**Source Document**: Nasa_Dashboard.xlsx, report_definitions.json  
**Previous Version**: v2.0 (2026-02-03)

---

## Table of Contents

1. [Data Sources Overview](#data-sources-overview)
2. [Occupancy & Leasing Section](#occupancy--leasing-section)
3. [Leasing Funnel](#leasing-funnel)
4. [Pricing Section](#pricing-section)
5. [Delinquencies & Evictions](#delinquencies--evictions)
6. [Profit & Loss Section](#profit--loss-section)
7. [Debt & Loan Section](#debt--loan-section)
8. [Revenue Optimization Analysis](#revenue-optimization-analysis)
9. [Expense Analysis](#expense-analysis)
10. [Digital & Marketing Performance](#digital--marketing-performance)
11. [Resident Renewal Metrics](#resident-renewal-metrics)
12. [Turnover Performance](#turnover-performance)
13. [Portfolio & Predictive Analytics](#portfolio--predictive-analytics)
14. [API Reference](#api-reference)
15. [Known Report IDs](#known-report-ids)

---

## Data Sources Overview

### Available Data Sources

| Source Type | Source Name | Description |
|-------------|-------------|-------------|
| **API** | RPX Gateway SOAP API | Real-time property/unit/resident data |
| **API** | Reporting REST API | On-demand report generation & download |
| **Report** | Activity Log Report (ID: 4153) | Detailed activity tracking |
| **Report** | Issues Report (ID: 4188) | Maintenance/issue tracking |
| **Manual** | Export files (CSV/Excel) | Supplemental data not in APIs |

### API Endpoints (RPX Gateway)

| Endpoint | SOAP Action | Data Provided |
|----------|-------------|---------------|
| `getSiteList` | `getsitelist` | Property/site information |
| `getBuildings` | `getbuildings` | Building structures |
| `unitlist` | `unitlist` | Unit details, vacancy, market rent |
| `getResidentListInfo` | `getresidentlistinfo` | All residents with status |
| `getResident` | `getresident` | Current residents only |
| `getLeaseInfo` | `getleaseinfo` | Active lease contracts |
| `getRentableItems` | `getrentableitems` | Amenities, parking, storage |

---

## Occupancy & Leasing Section

| Dashboard Field | Source Type | Source Details | Calculation/Notes |
|-----------------|-------------|----------------|-------------------|
| **Leased Percentage** | API | `unitlist` + `getResidentListInfo` | Count units with `Vacant=F` OR `leasestatus=Future Lease` ÷ total units |
| **Physical Occupancy** | API | `unitlist` | Count where `Vacant=F` ÷ total units |
| **Exposure (30 days)** | API | `unitlist` | Current occupancy - units with `OnNoticeForDate` within 30 days |
| **Exposure (60 days)** | API | `unitlist` | Current occupancy - units with `OnNoticeForDate` within 60 days |
| **Vacant Ready** | API | `unitlist` | Count where `Vacant=T` AND `UnitMadeReadyDate` is recent |
| **Vacant not Ready** | API | `unitlist` | Count where `Vacant=T` AND no recent `UnitMadeReadyDate` |
| **Total Vacant Units** | API | `unitlist` | Count where `Vacant=T` |
| **Vacant > 90 Days** | API | `unitlist` | Count where `Vacant=T` AND `(today - AvailableDate) > 90` |
| **Expiration** | API | `getLeaseInfo` | Count where `LeaseEndDate` falls in current month |
| **Renewal** | API | `getLeaseInfo` | Count where `NextLeaseID > 0` OR `LastRenewalDate` in period |
| **Renewal Percentage** | Calculated | Derived | `Renewals ÷ Expirations × 100` |
| **Move-out** | API | `getResidentListInfo` | Count where `moveoutdate` falls in period |
| **Move-In** | API | `getResidentListInfo` | Count where `moveindate` falls in period |
| **Net Move in** | Calculated | Derived | `Move-In - Move-out` |

### API Field Mapping - Units

| RealPage API Field | Dashboard Use | Data Type |
|--------------------|---------------|-----------|
| `UnitID` | Unit identifier | String |
| `UnitNumber` | Display unit number | String |
| `Vacant` | Occupancy status (T/F) | Boolean |
| `Available` | Available for rent flag | Boolean |
| `AvailableDate` | Date unit became available | Date |
| `OnNoticeForDate` | Expected move-out date | Date |
| `UnitMadeReadyDate` | Turn completion date | Date |
| `MarketRent` | Asking rent | Decimal |
| `RentableSqft` | Square footage | Integer |
| `FloorplanID` | Floorplan code | String |
| `FloorplanName` | Floorplan description | String |
| `Bedrooms` | Bedroom count | Integer |
| `Bathrooms` | Bathroom count | Decimal |
| `BuildingName` | Building identifier | String |
| `Floor` | Floor number | String |

---

## Leasing Funnel

| Dashboard Field | Source Type | Source Details | Calculation/Notes |
|-----------------|-------------|----------------|-------------------|
| **Leads** | ⚠️ Partial | `getResidentListInfo` | Count `leasestatus=Applicant` (limited - no guest cards) |
| **Tours** | ❌ Not Available | Requires CrossFire API | Need Prospect Management API access |
| **Lead/Tour conversion** | ❌ Not Available | Requires CrossFire API | `Tours ÷ Leads` |
| **Applications** | API | `getResidentListInfo` | Count where `leasestatus=Applicant` AND `AppliedDate` present |
| **Tour/Application conversion** | ❌ Not Available | Requires CrossFire API | `Applications ÷ Tours` |
| **Leases** | API | `getResidentListInfo` | Count where `leasestatus=Applicant - Lease Signed` |
| **Lease/lead Conversion** | ⚠️ Partial | Calculated | `Leases ÷ Applicants` (treating applicants as leads) |
| **Lease/Tour Conversion** | ❌ Not Available | Requires CrossFire API | `Leases ÷ Tours` |
| **Lease/Application Conversion** | Calculated | Derived | `Leases ÷ Applications` |

### Resident Lease Status Values

| Status Value | Count Purpose | Dashboard Category |
|--------------|---------------|-------------------|
| `Current` | Active occupants | Occupied |
| `Future Lease` | Renewal signed | Preleased |
| `Applicant` | Pending applications | Leads |
| `Applicant - Lease Signed` | Approved, pending move-in | Pending Move-ins |
| `Former` | Past residents | Historical |
| `Former Applicant` | Denied/cancelled | Historical |

---

## Pricing Section

| Dashboard Field | Source Type | Source Details | Calculation/Notes |
|-----------------|-------------|----------------|-------------------|
| **In-Place Rent** | API | `getLeaseInfo` → `Rent` | Current rent per active lease |
| **In-Place $/SF** | Calculated | `getLeaseInfo` + `unitlist` | `Rent ÷ RentableSqft` |
| **Asking Rent** | API | `unitlist` → `MarketRent` | Market rent per unit |
| **Asking $/SF** | Calculated | `unitlist` | `MarketRent ÷ RentableSqft` |
| **Rent Growth** | Calculated | Derived | `(Asking - InPlace) ÷ InPlace × 100` |
| **Rent Growth vs. Market** | ⚠️ Manual/External | Market data needed | Subject rent growth as % of market growth |
| **Average Effective Rent per Unit** | Calculated | Derived | Total rent ÷ occupied units |
| **Revenue per unit (RevPAU)** | Calculated | Derived | Total revenue ÷ total units |

### Floorplan Breakdown

| Dashboard Field | Source Type | Source Details |
|-----------------|-------------|----------------|
| **Unit Type** | API | `unitlist` → `FloorplanName` |
| **# of Units** | API | `unitlist` → Count by `FloorplanID` |
| **SF (Sqft)** | API | `unitlist` → `RentableSqft` |
| **In-Place Rent** | API | `getLeaseInfo` → `Rent` averaged by floorplan |
| **In-Place $/SF** | Calculated | `Rent ÷ RentableSqft` |
| **Asking Rent** | API | `unitlist` → `MarketRent` |
| **Asking $/SF** | Calculated | `MarketRent ÷ RentableSqft` |
| **Rent Growth %** | Calculated | `(Asking - InPlace) ÷ InPlace` |

---

## Delinquencies & Evictions

| Dashboard Field | Source Type | Source Details | Calculation/Notes |
|-----------------|-------------|----------------|-------------------|
| **Total Delinquencies** | API | `getResidentListInfo` → `balance`, `curbalance` | Sum of positive balances |
| **0-30 Days** | API/Report | A/R aging report | Charges with transaction dates 0-30 days prior |
| **31-60 Days** | API/Report | A/R aging report | Charges with transaction dates 31-60 days prior |
| **61-90 Days** | API/Report | A/R aging report | Charges with transaction dates 61-90 days prior |
| **90 Days+** | API/Report | A/R aging report | Charges with transaction dates 90+ days prior |
| **Total Evictions (Balance)** | API | `getLeaseInfo` → `Evict` flag | Sum balances where `Evict=Y` |
| **# of Units (Eviction)** | API | `getLeaseInfo` | Count where `Evict=Y` |
| **Filed** | ⚠️ Report/Manual | Legal status tracking | Evictions with "Filed" status |
| **Writ** | ⚠️ Report/Manual | Legal status tracking | Evictions with "Writ" status |
| **Total Collections (Post Eviction)** | ⚠️ Report/Manual | Collections tracking | Amounts in collections status |

### API Field Mapping - Balances

| RealPage API Field | Dashboard Use | Source |
|--------------------|---------------|--------|
| `balance` | Total balance | `getResidentListInfo` |
| `curbalance` | Current period balance | `getResidentListInfo` |
| `pendingbalance` | Pending charges | `getResidentListInfo` |
| `CurBal` | Current balance | `getLeaseInfo` |
| `TotPaid` | Total paid | `getLeaseInfo` |
| `LateDOM` | Late day of month | `getLeaseInfo` |
| `LCPct` | Late charge percentage | `getLeaseInfo` |
| `Evict` | Eviction flag | `getLeaseInfo` |

---

## Profit & Loss Section

| Dashboard Field | Source Type | Source Details | Calculation/Notes |
|-----------------|-------------|----------------|-------------------|
| **Gross Potential Rent** | Report/API | Financial report | Total market rent × occupied + vacant units |
| **Loss to Lease** | Calculated | Derived | `(MarketRent - ActualRent) × units` |
| **Total Gross Potential Rent** | Calculated | Derived | `GPR - Loss to Lease` |
| **Model/Employee Unit** | Report | Financial report | Value of model/employee unit discounts |
| **Concession** | Report | Financial report | Total concession amounts |
| **Vacancy** | Calculated | Derived | `MarketRent × vacant days` |
| **Net Rental Revenue** | Calculated | Derived | `GPR - LTL - Model - Concessions - Vacancy` |
| **Other Income** | Report | Financial report | Fees, amenities, parking, etc. |
| **Total Income** | Calculated | Derived | `Net Rental Revenue + Other Income` |

### Expense Categories

| Category | Source Type | Notes |
|----------|-------------|-------|
| **Payroll** | Report | Staff salaries/benefits |
| **Marketing** | Report | Advertising, ILS fees |
| **G&A** | Report | General & Administrative |
| **Services** | Report | Contract services |
| **R&M** | Report | Repairs & Maintenance |
| **T/O (Turnover)** | Report | Make-ready costs |
| **Utilities** | Report | Property utilities |
| **Insurance** | Report | Property insurance |
| **RE Taxes** | Report | Real estate taxes |
| **Total Operating Expenses** | Calculated | Sum of all expense categories |
| **NOI (Net Operating Income)** | Calculated | `Total Income - Total Operating Expenses` |

---

## Debt & Loan Section

| Dashboard Field | Source Type | Source Details | Calculation/Notes |
|-----------------|-------------|----------------|-------------------|
| **Original Loan Amount** | Manual | Loan documents | Static value from closing |
| **Current Outstanding Balance** | Manual/Calculated | Loan amortization | Updated monthly |
| **Interest Rate Type** | Manual | Fixed/Floating | From loan terms |
| **Interest Rate Index** | Manual | SOFR, Treasury, etc. | Reference rate type |
| **Interest Rate - Index Value** | External | Market data | Current index rate |
| **Interest Rate - Spread** | Manual | Loan documents | Margin over index |
| **Interest Rate - All in Rate** | Calculated | Derived | `Index Value + Spread` |
| **Maturity Date** | Manual | Loan documents | Loan maturity |
| **Interest Only Period Ending** | Manual | Loan documents | I/O period end date |
| **MTD Debt Yield** | Calculated | Derived | `NOI (annualized) ÷ Loan Balance` |
| **YTD Debt Yield** | Calculated | Derived | `YTD NOI (annualized) ÷ Loan Balance` |
| **Loan to Value** | Calculated | Derived | `Loan Balance ÷ Property Value` |
| **Days to Maturity** | Calculated | Derived | `Maturity Date - Today` |
| **Days to I/O Expiration** | Calculated | Derived | `I/O End Date - Today` |
| **Min DSCR Required** | Manual | Loan documents | Covenant requirement |
| **Current DSCR vs. Required (%)** | Calculated | Derived | `Actual DSCR ÷ Required DSCR` |
| **Debt Yield Required** | Manual | Loan documents | Covenant requirement |
| **Current DY vs Required (%)** | Calculated | Derived | `Actual DY ÷ Required DY` |
| **Total Debt Service** | Calculated | Derived | Monthly P&I payment |
| **Annual Debt Service** | Calculated | Derived | `Monthly × 12` |
| **Principal Paydown YTD** | Calculated | Derived | Cumulative principal paid |
| **Principal Paydown Total** | Calculated | Derived | Total principal paid since origination |

### Reserve Accounts

| Dashboard Field | Source Type | Notes |
|-----------------|-------------|-------|
| **Replacement Reserves** | Manual/Report | Escrow balance |
| **Tax Escrow Balance** | Manual/Report | RE tax escrow |
| **Insurance Escrow Balance** | Manual/Report | Insurance escrow |

---

## Revenue Optimization Analysis

| Dashboard Field | Source Type | Source Details | Calculation/Notes |
|-----------------|-------------|----------------|-------------------|
| **Average Effective Rent per Unit** | Calculated | `getLeaseInfo` | Total rent ÷ occupied units |
| **Revenue per unit (RevPAU)** | Calculated | Derived | Total revenue ÷ total units |
| **Rent Growth** | Calculated | Derived | `(Current - Prior) ÷ Prior` |
| **Rent Growth vs. Market** | External + Calc | Market data needed | Subject growth ÷ Market growth |
| **Loss-to-lease as % of GPR** | Calculated | Derived | `LTL ÷ GPR` |
| **Concession Cost as % of Effective Rent** | Calculated | Derived | `Concessions ÷ Effective Rent` |
| **Bad Debt as % of Effective Rent** | Calculated | Derived | `Bad Debt ÷ Effective Rent` |
| **Economic Occupancy** | Calculated | Derived | `Collected Rent ÷ GPR` |

---

## Expense Analysis

| Dashboard Field | Source Type | Source Details | Calculation/Notes |
|-----------------|-------------|----------------|-------------------|
| **Operating expense/Unit/Year** | Calculated | Financial report | `Total OpEx ÷ Units` |
| **Controllable Expenses per Unit** | Calculated | Derived | `(Payroll + Marketing + G&A + Services + R&M) ÷ Units` |
| **Non-Controllable Expenses per Unit** | Calculated | Derived | `(Utilities + Insurance + RE Taxes) ÷ Units` |

### "Below the Line" Items

| Dashboard Field | Source Type | Notes |
|-----------------|-------------|-------|
| **Capex tracking ($ Spent)** | Report | Capital expenditures |
| **Debt Service ($$)** | Calculated | P&I payments |
| **Debt service coverage ratio** | Calculated | `NOI ÷ Debt Service` |
| **Non-Operating Expenses** | Report | One-time/non-recurring |
| **Free cash flow** | Calculated | `NOI - Debt Service - CapEx` |
| **Cash-on-cash return** | Calculated | `Free Cash Flow ÷ Equity` |

---

## Digital & Marketing Performance

| Dashboard Field | Source Type | Source Details | Calculation/Notes |
|-----------------|-------------|----------------|-------------------|
| **Cost per Lease** | ✅ Report | Financial/Expense report | `Marketing Spend ÷ Leases Signed` |
| **Ave. days to lease from first inquiry** | ❌ Not Available | Requires CrossFire | Need prospect tracking |
| **Application completion rate** | ⚠️ Partial | `getResidentListInfo` | `Submitted ÷ Started` (limited data) |
| **Application approval rate** | Calculated | `getResidentListInfo` | `Approved ÷ Submitted` |
| **Ave. time from app. to lease signing** | API | `getResidentListInfo` | `AppliedDate` to lease signed date |
| **Cancellation rate (denial rate)** | Calculated | `getResidentListInfo` | `Denied ÷ Submitted` |

**Note**: Marketing spend data is available in expense reports as part of "Controllable Expenses"

---

## Resident Renewal Metrics

| Dashboard Field | Source Type | Source Details | Calculation/Notes |
|-----------------|-------------|----------------|-------------------|
| **Ave. length of tenancy/residency (months)** | API | `getResidentListInfo` | `(Today - moveindate)` average |
| **Average Notice Period (Days)** | API | `getResidentListInfo` | `(moveoutdate - noticegivendate)` average |
| **Resident scores** | ❌ Not Available | External survey | Requires NPS/satisfaction survey |

---

## Turnover Performance

| Dashboard Field | Source Type | Source Details | Calculation/Notes |
|-----------------|-------------|----------------|-------------------|
| **Average turn time (Days)** | API | `unitlist` | `(UnitMadeReadyDate - moveoutdate)` average |
| **Turn costs per unit** | Report | Financial report | `T/O expense ÷ turns` |
| **Turn cost vs. rent increase analysis** | Calculated | Derived | `Turn Cost ÷ (New Rent - Old Rent) × 12` |

---

## Portfolio & Predictive Analytics

### Portfolio Comparison

| Dashboard Field | Source Type | Notes |
|-----------------|-------------|-------|
| **Property ranking matrix** | Calculated | Rank by key metrics |
| **Market rent survey comparison** | External | Comp data needed |

### Predictive/Forward-Looking

| Dashboard Field | Source Type | Notes |
|-----------------|-------------|-------|
| **Projected occupancy (30/60/90 days)** | Calculated | Based on notices + pipeline |
| **Revenue forecast vs. budget** | Report + Calc | Actual vs budget trend |
| **Lease expiration schedule** | API | `getLeaseInfo` → `LeaseEndDate` |
| **Seasonality trends** | Calculated | Historical pattern analysis |

### Insights (AI-Generated)

| Dashboard Field | Source Type | Notes |
|-----------------|-------------|-------|
| **Optimal rent recommendations** | Calculated | By unit/availability |
| **Tour-to-lease velocity by unit type** | ❌ CrossFire needed | Requires tour data |
| **Time on market by unit type** | API | `AvailableDate` analysis |

---

## API Reference

### RealPage RPX Gateway (SOAP)

**Base URL**: `https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc`

**Authentication**:
```xml
<tem:auth>
    <tem:pmcid>{PMC_ID}</tem:pmcid>
    <tem:siteid>{SITE_ID}</tem:siteid>
    <tem:licensekey>{LICENSE_KEY}</tem:licensekey>
    <tem:system>Onesite</tem:system>
</tem:auth>
```

### RealPage Reporting API (REST)

**Base URL**: `https://reportingapi.realpage.com/v1`

**Authentication**: Bearer token (from authenticated RealPage web session)

**Endpoints**:
- `POST /reports/{reportId}/report-instances` - Create report instance
- `POST /reports/{reportId}/report-instances/{instanceId}/files` - Download file

**Format Codes** (vary by report):
| Report | PDF | Excel | Other |
|--------|-----|-------|-------|
| Box Score | 1682 | 1683 | - |
| Rent Roll | 1 | 3 | Word: 2 |
| Delinquency | 1 | 3 | Word: 2 |
| Activity Report | - | 562 | CSV: 563, HTML: 561 |
| Monthly Activity Summary | 1 | 3 | Word: 2 |
| Lease Expiration | 1 | 3 | Word: 2 |

---

## Known Report IDs (Verified & Working)

| Report Name | Report ID | Report Key | Status |
|-------------|-----------|------------|--------|
| **Box Score** | 4238 | `446266C0-D572-4D8A-A6DA-310C0AE61037` | ✅ Working |
| **Rent Roll** | 4043 | `A6F61299-E960-4235-9DC2-44D2C2EF4F99` | ✅ Working |
| **Delinquency Report** | 4260 | `89A3C427-BE71-4A05-9D2B-BDF3923BF756` | ✅ Working |
| **Activity Report** | 3837 | `B29B7C76-04B8-4D6C-AABC-62127F0CAE63` | ✅ Working |
| **Monthly Activity Summary** | 3877 | `E41626AB-EC0F-4F6C-A6EA-D7A93909AA9B` | ✅ Working |
| **Lease Expiration** | 3838 | `89545A3A-C28A-49CC-8791-396AE71AB422` | ✅ Working |
| **Activity Log Report** | 4153 | `7929C3F8-0BD4-42D7-B537-BD5BE0DD667D` | ⚠️ Legacy |
| **Issues Report** | 4188 | `0F1AC604-DDD3-4547-8C26-46435FEFFDD5` | ⚠️ Legacy |

### Reports Still Needed

| Report Type | Dashboard Section | Priority |
|-------------|------------------|----------|
| **Financial Summary** | P&L, NOI | High |
| **Budget vs Actual** | P&L variance | Medium |
| **A/R Aging Detail** | Delinquencies breakdown | Medium |

### Data Coverage Estimate (with all reports discovered)

| Section | Current Coverage | With All Reports | Gap |
|---------|------------------|------------------|-----|
| Occupancy & Leasing | 30% | 95% | 5% (A/R Aging) |
| Pricing | 20% | 95% | 5% (Market rent details) |
| Delinquencies | 10% | 95% | 5% (A/R Aging) |
| P&L | 5% | 95% | 5% (Financial Summary) |
| Expenses | 5% | 100% | 0% |
| Marketing Performance | 5% | 90% | 10% (Lead sources) |
| Renewal Metrics | 30% | 100% | 0% |
| **Overall (excluding market comps & debt)** | **~15%** | **~98%** | **~2%** |

**IMPORTANT**: Current API coverage is ONLY ~15%, not 85%. The APIs we have are limited:
- ✅ getUnitList (basic unit info)
- ✅ getResidentListInfo (basic resident data)  
- ✅ getLeaseInfo (basic lease data)
- ❌ Many fields in the mapping document are NOT available via current APIs
- ❌ Most data requires report downloads

---

## Data Availability Summary

### ✅ AVAILABLE VIA API (RPX Gateway SOAP)

These fields are **already working** via `realpage_client.py`:

| Data Category | API Method | Key Fields |
|---------------|------------|------------|
| **Units** | `unitlist` | UnitNumber, Vacant, Available, AvailableDate, MarketRent, RentableSqft, FloorplanName, Bedrooms, Bathrooms |
| **Occupancy** | `unitlist` | Vacant (T/F), OnNoticeForDate, UnitMadeReadyDate |
| **Residents** | `getResidentListInfo` | name, leasestatus, moveindate, moveoutdate, balance, curbalance |
| **Leases** | `getLeaseInfo` | Rent, LeaseStartDate, LeaseEndDate, NextLeaseID, Evict flag |
| **Buildings** | `getBuildings` | Building structures and hierarchy |
| **Sites** | `getSiteList` | Property/site information |

### ✅ AVAILABLE VIA REPORTS (Reporting API / Exports)

| Data Category | Report Name | Status | Key Fields |
|---------------|-------------|--------|------------|
| **Leasing Activity** | Leasing Activity Detail (4256) | ✅ File Analyzed | Date, Contact Type, Return Visits, Ad Source, Leases, Lost Reason |
| **Traffic Sources** | Leasing Activity Detail (4256) | ✅ File Analyzed | Ad Source breakdown |
| **Tours** | Leasing Activity Detail (4256) | ✅ File Analyzed | Filter "Contact Type" = Visit/Tour |
| **Leads** | Leasing Activity Detail (4256) | ✅ File Analyzed | Unique Prospect Name count |
| **Lease Trade-Out** | Custom Dashboard (Nasa_Dashboard) | ✅ File Analyzed | Unit #, New Rent, Prior Rent, % Change, Move-in Date |

### 🔍 NEEDS REPORTS (Reporting API)

These fields require report downloads - **need report_id + report_key**:

| Data Category | Suggested Report | Status | Priority |
|---------------|------------------|--------|----------|
| **Move-out Reasons** | Box Score Report (4238) | ⚠️ API Error (400) | HIGH |
| **Days Vacant** | Box Score Report (4238) | ⚠️ API Error (400) | HIGH |
| **Vacancy Cost** | Box Score Report (4238) | ⚠️ API Error (400) | HIGH |
| **Concessions** | Rent Roll Detail (4295) | 🔍 Testing | HIGH |
| **Effective Rent** | Rent Roll Detail (4295) | 🔍 Testing | HIGH |
| **Lease Expirations** | Lease Expiration Detail (4299) | 🔍 Testing | MEDIUM |
| **Renewals Detail** | Renewal Statistics Report | 🔍 Need ID | HIGH |
| **A/R Aging** | Resident Ledgers / A/R Aging | 🔍 Need ID | HIGH |
| **P&L / Financials** | Financial Summary Report | 🔍 Need ID | HIGH |

### 🔍 NEEDS REPORTS - Lead/Traffic Data

Found in Unified Platform User Guide:

| Data Category | Report Name | Fields Available |
|---------------|-------------|------------------|
| **Guest Cards** | Guestcard Summary (4151) | Guest card count by traffic source |
| **Lead Counts** | Contact Level Details (4102) | Monthly totals by source |

### ✅ AVAILABLE VIA ALN API

| Data Category | Source |
|---------------|--------|
| **Market Comps** | ALN API (already integrated) |

### ❌ MANUAL ENTRY REQUIRED

| Data Category | Reason |
|---------------|--------|
| **Debt/Loan Data** | Not in PMS - from loan documents |

---

## Lease Trade-Out Analysis

| Dashboard Field | Source Type | Source Details | Calculation/Notes |
|-----------------|-------------|----------------|-------------------|
| **Unit #** | Report | `Nasa_Dashboard.xlsx` → `Unit #` | |
| **Unit Type** | Report | `Nasa_Dashboard.xlsx` → `Unit Type` | |
| **SF** | Report | `Nasa_Dashboard.xlsx` → `SF` | |
| **New Lease Effective Rent** | Report | `Nasa_Dashboard.xlsx` → `Effective Rent` | Verified: Column 13 (approx 1885) |
| **Prior Lease Effective Rent** | Report | `Nasa_Dashboard.xlsx` → `Effective Rent.1` | Verified: Column 14 (approx 1800) |
| **% Change** | Report/Calc | `Nasa_Dashboard.xlsx` → `% Change` | |
| **$ Change** | Report/Calc | `Nasa_Dashboard.xlsx` → `$ Change` | |
| **Move-in Date** | Report | `Nasa_Dashboard.xlsx` → `Move-in Date` | |

---

## Next Steps

1. **Obtain Report IDs** - User to provide report_id + report_key from RealPage browser sessions
2. **Test each report** - Use `test_report_discovery.py` to download and analyze
3. **Map report fields** - Document column mappings for each report
4. **Build report ingestion** - Parse Excel exports for dashboard data
5. **Create Yardi mapping** - Parallel document for Yardi data sources

---

## Report Implementation Status

| Report Name | Report ID | Tested | Parser | DB Import |
|-------------|-----------|--------|--------|------------|
| **Box Score** | 4238 | ✅ | ✅ `parse_box_score()` | ✅ `rp_box_score` |
| **Rent Roll** | 4043 | ✅ | ✅ `parse_rent_roll()` | ✅ `rp_rent_roll` |
| **Delinquency** | 4260 | ✅ | ✅ `parse_delinquency()` | ✅ `rp_delinquency` |
| **Activity Report** | 3837 | ✅ | ⏳ Pending | ⏳ `rp_activity` |
| **Monthly Activity Summary** | 3877 | ✅ | ⏳ Pending | ⏳ `rp_monthly_summary` |
| **Lease Expiration** | 3838 | ✅ | ⏳ Pending | ⏳ `rp_lease_expiration` |

### Smart Downloader

**File**: `batch_report_downloader.py`

**Features**:
- Auto-creates report instances
- Smart file ID scanning (finds files by content)
- Content-based report identification
- Automatic database import
- Temp file cleanup after import

**Usage**:
```bash
python3 batch_report_downloader.py --property "Nexus East" --reports box_score rent_roll delinquency
```

---

## Configured Properties

| Property | Property ID | Status |
|----------|-------------|--------|
| Aspire 7th and Grant | 4779341 | ✅ |
| Edison at RiNo | 4248319 | ✅ |
| Ridian | 5446271 | ✅ |
| Nexus East | 5472172 | ✅ |
| Parkside at Round Rock | 5536211 | ✅ |

---

## Database Schema

**Database**: `app/db/data/realpage_raw.db`

| Table | Description | Key Fields |
|-------|-------------|------------|
| `rp_box_score` | Floorplan occupancy metrics | property_id, floorplan, total_units, occupied, vacant, occupancy_pct |
| `rp_rent_roll` | Unit-level lease details | property_id, unit_number, resident_name, lease_start, lease_end, rent |
| `rp_delinquency` | Outstanding balances | property_id, unit_number, resident_name, balance, days_delinquent |
| `rp_activity` | Prospect activity log | property_id, activity_date, activity_type, prospect_name |
| `rp_monthly_summary` | Monthly leasing summary | property_id, month, move_ins, move_outs, renewals |
| `rp_lease_expiration` | Upcoming expirations | property_id, unit_number, expiration_date, renewal_status |

---

*Document maintained in: `/OwnerDashV2/Data_Definitions_and_Sources/REALPAGE_DATA_MAPPING.md`*
