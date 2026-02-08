# RealPage Reports Reference

**Source**: Unified Platform User Guide.pdf (306 pages)
**Last Updated**: 2026-02-03

---

## Key Reports for Dashboard

### 1. Box Score Report
**Navigation**: Reports > Manage Reports > Residents/Management > Box Score
**Priority**: HIGH - Core occupancy and leasing metrics

**Sections Included**:
- Property Totals Summary (units, occupancy %, rent totals)
- Leases – New Residents – Vacant Units Leased
- Leases – New Residents – Occupied Units
- Leases – Renewals
- Leases – Canceled/Denied
- Move-Ins – New Residents
- Move-Ins – Transferring Residents
- Move-Outs – Exiting Residents
- Move-Outs – Transferring Residents
- Notice to Vacate (NTV)
- Vacancies (Current Property Date)

**Key Fields**:
| Field | Description |
|-------|-------------|
| Unit | Unit number |
| Floor Plan | Floor plan code |
| Name | Head of household name |
| Status | Lease/occupancy status |
| Move-In | Move-in date |
| Move-Out | Move-out date |
| Reason | Reason for move out |
| Notice Given | Notice given date |
| Days Notice | Number of days notice |
| Market Rent | Current market rent for unit |
| Effective Rent | Calculated effective rent |
| Pre-Leased | Whether unit is pre-leased |
| Days Vacant | Number of days unit has been vacant |
| Estimated Vacancy Cost | (Market Rent ÷ 30.42) × Days Vacant |
| Deposits on Hand | Current deposit balance |

---

### 2. Monthly Activity Summary Report
**Navigation**: Reports > Manage Reports > Residents/Management > Monthly Activity Summary
**Priority**: HIGH - Monthly operations overview

**Parameters**:
- Accounting Activity Start Date
- Occupancy Activity Start Date
- Subtotals By (floor plan name or code)

**Key Fields**:
| Field | Description |
|-------|-------------|
| Floor Plan | Floor plan name/code |
| Market Rent | Total market rent for floor plan |
| Total Base Rent | Total base rent for floor plan |
| Total SQFT | Total square footage |
| Total Units | Number of units |
| Occupied No NTV | Occupied units not on notice |
| Vacant Not Leased | Vacant units not leased |
| Vacant Leased | Vacant but pre-leased units |
| Occupied NTV Not Leased | On notice, not pre-leased |
| Occupied NTV Leased | On notice, pre-leased |
| Vacant Administrative | Admin vacant units |
| Move-Outs | Total move-outs in period |
| Move-Ins | Total move-ins in period |
| Cancellations/Rejections | Canceled/rejected applications |
| Renewals | Leases renewed in period |
| Leases | New leases signed |
| Rent Charged | CA-type transactions total |
| Other Charges | Non-rent charges total |
| Payments | Total payments received |

**Leasing Activity Section**:
- Lease approved
- Moved in
- Moved out
- Move-out notice
- Transfer notice
- Renewed lease
- Transferred to new unit

---

### 3. Rent Roll Detail Report
**Navigation**: Reports > Manage Reports > Residents/Management > Rent Roll Detail
**Priority**: HIGH - Comprehensive unit/lease snapshot

**Parameters**:
- Property Date (historical or current)
- Account Status filter
- Unit Designation filter
- Display Unit Rent As (Market Rent, Market + Addl., Effective Rent)
- Sort By (Unit, Floor plan, Name)

**Key Fields**:
| Field | Description |
|-------|-------------|
| Bldg/Unit | Building and unit number |
| Status | Occupancy status |
| Name | Resident name |
| Sq Ft | Rentable square footage |
| Move-In | Move-in date |
| Lease End | Lease end date |
| NTV Date | Notice to vacate date |
| Market Rent | Base rent + amenity rent |
| Market +Addl | Market rent + non-CA charges |
| Effective Rent | Market rent + concession adjustments |
| Lease Rent | Rent in scheduled billing |
| Other Charges/Credits | Non-rent charges |
| Total Billing | Total billing amount |
| Dep on Hand | Total paid deposits |
| Balance | Open ledger balance |

**Summary Sections**:
- Rent Analysis by Floor Plan (# Units, Avg SqFt, Avg Rent)
- Potential Rent by Occupancy Status
- Summary Billing by Subjournal
- Summary Billing by Transaction Code

---

### 4. Lease Expiration Reports

#### Lease Expiration Detail Report
**Navigation**: Reports > Manage Reports > Residents/Management > Lease Expiration Detail

#### Lease Expiration Renewal Detail (Excel)
**Navigation**: Reports > Manage Reports > Residents/Management > Lease Expiration Renewal Detail (Excel)
**Priority**: HIGH - Renewal tracking

#### Lease Expiration Summary by Floor Plan
**Navigation**: Reports > Manage Reports > Residents/Management > Lease Expiration Summary by Floor Plan

---

### 5. Current Renewal Status Report
**Navigation**: Reports > Manage Reports > Residents/Management > Current Renewal Status
**Priority**: HIGH - Active renewal tracking

---

### 6. Renewal Statistics Report
**Navigation**: Reports > Manage Reports > Residents/Management > Renewal Statistics
**Priority**: MEDIUM - Renewal performance metrics

---

### 7. Projected Occupancy Report
**Navigation**: Reports > Manage Reports > Residents/Management > Projected Occupancy
**Priority**: MEDIUM - Forward-looking occupancy

---

### 8. Reasons for Move Outs Report
**Navigation**: Reports > Manage Reports > Residents/Management > Reasons for Move Outs
**Priority**: MEDIUM - Turnover analysis

---

### 9. Resident Ledgers Report
**Navigation**: Reports > Manage Reports > Residents/Management > Resident Ledgers
**Priority**: MEDIUM - A/R and delinquency data

---

### 10. All Residents (Excel) Report
**Navigation**: Reports > Manage Reports > Residents/Management > All Residents (Excel)
**Priority**: MEDIUM - Complete resident roster

**Key Fields**:
- Name, Status, Contact Status
- Bldg/Unit, Age, Phone
- Move-In, Expires, Notice for Date, Move-Out
- Rent, Other charges
- Deposit, NSF count, Late payment count

---

## Report Formats Available

| Format | Code | Description |
|--------|------|-------------|
| PDF | 2015 | Standard PDF format |
| Excel | 2016 | XLS/XLSX format |
| Raw Data | 2105 | CSV or raw data export |
| XML | varies | Standard XML format |
| HTML | varies | Browser-viewable format |

---

## Report API Integration

Reports are accessed via the RealPage Reporting API:
- **Base URL**: `https://reportingapi.realpage.com/v1`
- **Endpoint**: `POST /reports/{report_id}/report-instances`

Each report requires:
1. `report_id` - Numeric ID for the report type
2. `report_key` - GUID key for the specific report
3. `reportFormat` - Format code (e.g., "2016" for Excel)
4. `parameters` - Report-specific parameters (dates, filters, etc.)
5. `properties` - List of property IDs to include

---

## Next Steps

1. Obtain report_id and report_key for each priority report
2. Test API calls to download sample data
3. Extract and map column headers to dashboard schema
4. Document field mappings in REALPAGE_DATA_MAPPING.md

---

## API Implementation Notes (2026-02-04)

### Reporting API Flow

1. **Create Instance**: `POST /reports/{report_id}/report-instances`
   - Returns `instanceId` (format: `xxx-yyy-zzz`)
   - Instance is created but file not immediately ready

2. **Download File**: `POST /reports/{report_id}/report-instances/{instanceId}/files`
   - Requires `fileId` in payload (NOT the same as instance ID middle part)
   - `fileId` comes from SignalR/WebSocket notification (complex to implement)

### File ID Discovery Challenge

The RealPage UI uses **SignalR/WebSocket** to receive notifications when a report file is ready. The `fileId` is sent via this real-time channel, not through a REST API endpoint.

**Workaround Options**:
1. Use curl with known file IDs from browser network capture
2. Implement SignalR client to receive file ID notifications
3. Poll notifications API (requires different token scope)

### Confirmed Working Curl Pattern

```bash
# Step 1: Create instance
curl -X POST 'https://reportingapi.realpage.com/v1/reports/4238/report-instances' \
  -H 'Authorization: Bearer {token}' \
  -H 'Content-Type: application/json' \
  --data-raw '{"reportKey":"446266C0-D572-4D8A-A6DA-310C0AE61037",...}'

# Step 2: Download file (requires correct fileId from UI)
curl -X POST 'https://reportingapi.realpage.com/v1/reports/4238/report-instances/{instanceId}/files' \
  -H 'Authorization: Bearer {token}' \
  -H 'Content-Type: application/json' \
  --data-raw '{"reportId":4238,"fileId":"{fileId}","propertyName":"..."}'
```

### Token Notes

- Tokens expire after ~1 hour
- Token must match exact character-by-character (corrupted tokens fail silently)
- Get fresh token from browser DevTools → Network → copy Authorization header
