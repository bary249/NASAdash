# RealPage RPX API Field Mapping for Owner Dashboard

**Generated**: 2026-01-19  
**Last Updated**: 2026-02-04  
**Site**: Venn - Meadow Bay (Site ID: 5230176)  
**Test Data**: 58 units, 962 residents, 32 active leases

> **Note**: This document covers the RPX SOAP API. For the Reporting REST API (report downloads), see `Data_Definitions_and_Sources/REALPAGE_DATA_MAPPING.md`

---

## 📊 Data Summary from API Test

| Endpoint | Records | Key Data |
|----------|---------|----------|
| `getBuildings` | 3 | Building addresses, IDs |
| `getSiteList` | 1 | Property info, accounting period |
| `unitlist` | 58 | Unit details, vacancy, market rent |
| `getresidentlistinfo` | 962 | All residents (Current, Former, Applicant) |
| `getresident` | 38 | Current residents only |
| `getleaseinfo` | 32 | Active lease contracts |

---

## 📈 OCCUPANCY & LEASING SECTION

| Field | RealPage Source | API/Endpoint | Notes |
|-------|-----------------|--------------|-------|
| Physical Occupancy | ✅ Available | `unitlist` | Count `Vacant=F` ÷ total units |
| Leased Percentage | ✅ Available | `unitlist` + `getresidentlistinfo` | Include Future Lease status |
| Exposure (30 days) | ✅ Available | `unitlist` | Filter by `OnNoticeForDate` within 30 days |
| Exposure (60 days) | ✅ Available | `unitlist` | Filter by `OnNoticeForDate` within 60 days |
| Vacant Ready | ⚠️ Partial | `unitlist` | `Vacant=T` + check `UnitMadeReadyDate` |
| Vacant not Ready | ⚠️ Partial | `unitlist` | `Vacant=T` + no recent `UnitMadeReadyDate` |
| Total Vacant Units | ✅ Available | `unitlist` | Count `Vacant=T` (28 in test) |
| Vacant > 90 Days | ✅ Available | `unitlist` | Compare `AvailableDate` to today |
| Expiration | ✅ Available | `getleaseinfo` | Filter `LeaseEndDate` in period |
| Renewal | ✅ Available | `getleaseinfo` | `NextLeaseID > 0` or status change |
| Renewal Percentage | ✅ Calculated | Derived | Renewals ÷ Expirations |
| Move-out | ✅ Available | `getresidentlistinfo` | `moveoutdate` in period |
| Move-in | ✅ Available | `getresidentlistinfo` | `moveindate` in period |
| Net Move-in | ✅ Calculated | Derived | Move-in - Move-out |

### Leasing Funnel (Leads/Tours/Apps)

| Field | RealPage Source | API/Endpoint | Notes |
|-------|-----------------|--------------|-------|
| Leads | ⚠️ Partial | `getresidentlistinfo` | Can count `leasestatus=Applicant` (33 found) |
| Tours | ❌ Not in RPX | **CrossFire needed** | Requires Prospect Management API |
| Applications | ✅ Available | `getresidentlistinfo` | `leasestatus=Applicant` + `AppliedDate` |
| Lease Signs | ✅ Available | `getresidentlistinfo` | `leasestatus=Applicant - Lease Signed` (1 found) |
| Lead/Tour conversion | ❌ Missing | **CrossFire needed** | No tour data in RPX |
| Tour/Application conversion | ❌ Missing | **CrossFire needed** | No tour data in RPX |
| Lease/Lead Conversion | ⚠️ Partial | Calculated | Can compute if treating Applicants as leads |

---

## 💰 PRICING SECTION

| Field | RealPage Source | API/Endpoint | Notes |
|-------|-----------------|--------------|-------|
| In-Place Rent | ✅ Available | `getleaseinfo` | `Rent` field per lease |
| In-Place $/SF | ✅ Calculated | `getleaseinfo` + `unitlist` | Rent ÷ `RentableSqft` |
| Asking Rent | ✅ Available | `unitlist` | `MarketRent` field |
| Asking $/SF | ✅ Calculated | `unitlist` | MarketRent ÷ `RentableSqft` |
| Rent Growth | ✅ Calculated | Derived | (Asking - InPlace) ÷ InPlace |
| Floorplan Breakdown | ✅ Available | `unitlist` | Group by `FloorplanID`/`FloorplanName` |

---

## 🏢 PROPERTY INFO SECTION

| Field | RealPage Source | API/Endpoint | Notes |
|-------|-----------------|--------------|-------|
| Property Name | ✅ Available | `getsitelist` | `SiteName` |
| Property Address | ✅ Available | `getsitelist` | `Adr1`, `City`, `State`, `Zip` |
| Total Units | ✅ Available | `unitlist` | Count of units |
| Buildings | ✅ Available | `getbuildings` | Building list with addresses |
| Year Built | ❌ Missing | Not in API | Would need ALN or manual entry |

---

## 📋 RESIDENT DATA SECTION

| Field | RealPage Source | API/Endpoint | Notes |
|-------|-----------------|--------------|-------|
| Resident Name | ✅ Available | `getresidentlistinfo` | `firstname`, `lastname` |
| Unit Number | ✅ Available | `getresidentlistinfo` | `unitnumber` |
| Lease Dates | ✅ Available | `getresidentlistinfo` | `begindate`, `enddate` |
| Move-in Date | ✅ Available | `getresidentlistinfo` | `moveindate` |
| Move-out Date | ✅ Available | `getresidentlistinfo` | `moveoutdate` |
| Notice Date | ✅ Available | `getresidentlistinfo` | `noticegivendate`, `noticefordate` |
| Balance | ✅ Available | `getresidentlistinfo` | `balance`, `curbalance`, `pendingbalance` |
| Contact Info | ✅ Available | `getresidentlistinfo` | `email`, `homephone`, `cellphone` |
| Lease Status | ✅ Available | `getresidentlistinfo` | `leasestatus` (Current, Future, Applicant, Former) |

---

## 🔍 Resident Lease Statuses Found

| Status | Count | Dashboard Use |
|--------|-------|---------------|
| `Current` | 45 | Active occupants |
| `Future Lease` | 2 | Preleased units |
| `Applicant` | 33 | Leads/Prospects |
| `Applicant - Lease Signed` | 1 | Pending move-ins |
| `Former` | 674 | Historical data |
| `Former Applicant` | 207 | Denied/Cancelled apps |

---

## ✅ Summary: RealPage vs Yardi Coverage

| Category | Yardi | RealPage RPX | RealPage + CrossFire |
|----------|-------|--------------|----------------------|
| **Occupancy** | ✅ Full | ✅ Full | ✅ Full |
| **Pricing** | ✅ Full | ✅ Full | ✅ Full |
| **Move-in/out** | ✅ Full | ✅ Full | ✅ Full |
| **Lease Expirations** | ✅ Full | ✅ Full | ✅ Full |
| **Renewals** | ✅ Full | ✅ Full | ✅ Full |
| **Leads** | ✅ Full | ⚠️ Applicants only | ✅ Full |
| **Tours** | ✅ Full | ❌ Missing | ✅ Full |
| **Lead Sources** | ✅ Full | ❌ Missing | ✅ Full |
| **Activity History** | ✅ Full | ❌ Missing | ✅ Full |

---

## 🚀 Implementation Status

### Completed
- ✅ RPX SOAP client (`realpage_client.py`) - Unit, resident, lease data
- ✅ Reporting REST API integration (`batch_report_downloader.py`)
- ✅ Smart file ID scanner with content-based matching
- ✅ Report parsers for Box Score, Rent Roll, Delinquency
- ✅ Database import pipeline (`import_reports.py`)

### Report Downloads Working
| Report | ID | Parser | DB Table |
|--------|-----|--------|----------|
| Box Score | 4238 | ✅ | `rp_box_score` |
| Rent Roll | 4043 | ✅ | `rp_rent_roll` |
| Delinquency | 4260 | ✅ | `rp_delinquency` |
| Activity Report | 3837 | ⏳ | `rp_activity` |
| Monthly Activity Summary | 3877 | ⏳ | `rp_monthly_summary` |
| Lease Expiration | 3838 | ⏳ | `rp_lease_expiration` |

### Configured Properties
| Property | ID |
|----------|----|
| Aspire 7th and Grant | 4779341 |
| Edison at RiNo | 4248319 |
| Ridian | 5446271 |
| Nexus East | 5472172 |
| Parkside at Round Rock | 5536211 |

### Usage
```bash
# Download and import reports
python3 batch_report_downloader.py --property "Nexus East" --reports box_score rent_roll delinquency
```

### Next Steps
1. Complete parsers for Activity, Monthly Summary, Lease Expiration reports
2. Connect `realpage_raw.db` to `unified.db` for dashboard UI
3. Request CrossFire API access for full leasing funnel data
