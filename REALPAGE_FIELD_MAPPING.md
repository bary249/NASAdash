# RealPage RPX API Field Mapping for Owner Dashboard

**Generated**: 2026-01-19  
**Site**: Venn - Meadow Bay (Site ID: 5230176)  
**Test Data**: 58 units, 962 residents, 32 active leases

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

## 🚀 Next Steps

1. **Implement RealPage client** using RPX endpoints for:
   - Occupancy metrics (units, vacancy)
   - Pricing metrics (market rent, in-place rent)
   - Resident/lease data (move-ins, move-outs, renewals)

2. **For full leasing funnel** (optional, requires credentials):
   - Request CrossFire Prospect Management API access
   - Add guest card/activity tracking for leads/tours

3. **Data normalization**:
   - Map `leasestatus` values to Yardi equivalents
   - Standardize date formats
   - Handle `Vacant` flag (T/F) vs Yardi's occupancy status
