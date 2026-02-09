# RealPage Complete Data Pipeline

Automated pipeline to download RealPage reports, sync to unified database, and make data available to the UI.

## Quick Start

### Run Complete Pipeline (All Properties)
```bash
# Python script
python3 sync_all_realpage.py

# Or use the shell wrapper
./sync_all_realpage.sh
```

This will:
1. 📥 Download reports from RealPage API for all 32 properties
2. 🔄 Sync data from `realpage_raw.db` to `unified.db`
3. ✅ Verify data is available to the UI

## Usage Options

### Download All Properties
```bash
python3 sync_all_realpage.py
```

### Download Specific Properties
```bash
python3 sync_all_realpage.py --properties "Kalaco" "Block 44" "The Northern"
```

### Skip Download, Only Sync Existing Data
```bash
python3 sync_all_realpage.py --skip-download
```

## What It Does

### Step 1: Download Reports
- Connects to RealPage Reporting API
- Downloads 6 report types per property:
  - Box Score (occupancy metrics)
  - Activity Report
  - Rent Roll (unit details)
  - Monthly Activity Summary
  - Lease Expiration
  - Delinquency Report
- Stores raw data in `app/db/data/realpage_raw.db`

### Step 2: Sync to Unified Database
- Reads from `realpage_raw.db`
- Transforms and normalizes data
- Writes to `app/db/data/unified.db`
- Syncs:
  - Properties
  - Occupancy metrics
  - Pricing by floorplan
  - Unit details (1,800+ units)
  - Resident information
  - Delinquency data

### Step 3: Data Available to UI
- FastAPI automatically reads from `unified.db`
- No additional steps needed
- Data appears immediately in dashboard

## Data Flow

```
RealPage API
    ↓ (batch_report_downloader.py)
realpage_raw.db
    ↓ (sync_realpage_to_unified.py)
unified.db
    ↓ (portfolio_service.py)
FastAPI Endpoints
    ↓
React UI Dashboard
```

## All 32 Properties

The pipeline processes these properties:
1. Kalaco
2. 7 East
3. Block 44
4. Curate at Orchard Town Center
5. Eden Keller Ranch
6. Harvest
7. Heights at Interlocken
8. Luna
9. Nexus East
10. Park 17
11. Parkside at Round Rock
12. Pearl Lantana
13. Slate
14. Sloane
15. Stonewood
16. Ten50
17. The Alcott
18. The Broadleaf
19. The Confluence
20. The Links at Plum Creek
21. thePearl
22. theQuinci
23. Aspire 7th and Grant
24. Edison at RiNo
25. Ridian
26. The Northern
27. The Avant
28. The Hunter
29. The Station at Riverfront Park
30. Discovery at Kingwood
31. Izzy

## Token Management

The RealPage Bearer token expires after 1 hour. To update:

1. Login to RealPage web UI
2. Open browser DevTools → Network tab
3. Trigger any API call
4. Copy the `authorization: Bearer <token>` header
5. Update `backend/realpage_token.json`:
   ```json
   {"access_token": "eyJhbGci..."}
   ```

## Manual Steps (if needed)

### 1. Download Single Property
```bash
python3 batch_report_downloader.py --property "Kalaco"
```

### 2. Sync to Unified
```bash
python3 -m app.db.sync_realpage_to_unified
```

### 3. Check Database
```bash
sqlite3 app/db/data/unified.db "SELECT COUNT(*) FROM unified_units"
```

## Troubleshooting

### Property Name Mismatch
The script now handles name variations (e.g., "7 East" vs "7East") automatically using normalization.

### Token Expired
```
Error: Token expired at 2026-02-08 15:50:30
```
→ Update the token in `realpage_token.json`

### No Reports Found
- Check if property name matches exactly in `report_definitions.json`
- Verify property has access in RealPage
- Check network connectivity

### Database Locked
```
Error: database is locked
```
→ Close any SQLite browsers or DB connections

## Output Example

```
======================================================================
  🚀 REALPAGE COMPLETE DATA PIPELINE
======================================================================
  Started: 2026-02-08T14:00:00.000000

======================================================================
  STEP 1: DOWNLOADING REPORTS FROM REALPAGE API
======================================================================

📋 Processing 32 properties...

[1/32] Kalaco
📥 Downloading reports for: Kalaco
  ✅ Success: 402 records imported

[2/32] Block 44
📥 Downloading reports for: Block 44
  ✅ Success: 327 records imported

...

📊 Download Summary:
  Properties processed: 32
  Successful: 30
  Total records: 9,850

======================================================================
  STEP 2: SYNCING TO UNIFIED DATABASE
======================================================================

📍 Syncing properties...
  ✅ Synced 32 properties

📊 Syncing occupancy metrics...
  ✅ Synced occupancy for 32 properties

💰 Syncing pricing metrics...
  ✅ Synced 450 floorplan pricing records

🏠 Syncing units from rent roll...
  ✅ Synced 1,870 units

💸 Syncing delinquency data...
  ✅ Synced 284 delinquency records

======================================================================
  STEP 3: VERIFYING DATA AVAILABILITY
======================================================================

✅ Unified Database Status:
  Properties: 32
  Units: 1,870
  Last synced: 2026-02-08T14:05:00.000000

🌐 Data is now available to the UI via FastAPI!

======================================================================
  PIPELINE COMPLETE
======================================================================
  Duration: 245.3 seconds
  Downloads: 30/32 successful
  Sync: ✅ Success
    - Properties: 32
    - Units: 1,870
    - Delinquency: 284
  UI Data: ✅ Available

✨ Complete! Data is live in your dashboard.
======================================================================
```

## Scheduling with Cron

To run daily at 6 AM:
```bash
crontab -e
```

Add:
```
0 6 * * * cd /Users/barak.b/Venn/OwnerDashV2/backend && ./sync_all_realpage.sh >> logs/sync.log 2>&1
```

## Files Created

- `sync_all_realpage.py` - Main Python pipeline script
- `sync_all_realpage.sh` - Simple shell wrapper
- `REALPAGE_SYNC_README.md` - This documentation
- `batch_report_downloader.py` - Updated with name normalization fix

## Support

For issues or questions, contact the engineering team.
