# Customer KPI Request vs Current Dashboard Capabilities

**Customer**: Kairoi Management (via Andrew)
**Date**: Feb 11, 2026

---

## Comparison Matrix

| # | Requested KPI | Status | Details |
|---|--------------|--------|---------|
| 1 | **Occupancy** | ✅ HAVE | KPI card showing physical occupancy %, occupied/total units |
| 2 | **Pre-leased** | ✅ HAVE | `preleased_vacant` count from box score + future residents |
| 3 | **ATR (Asking Rent)** | ✅ HAVE | Asking rent by floorplan in Unit Mix & Pricing table; also available_units count |
| 4 | **Live delinquency with unit dropdown** | ✅ HAVE | Full DelinquencySection with unit-level drill-through |
| 4a | — Less than 30 | ✅ HAVE | "Current" aging bucket from delinquency report |
| 4b | — 31-60 | ✅ HAVE | 30-day aging bucket |
| 4c | — 61-90 | ✅ HAVE | 60-day aging bucket |
| 4d | — 90+ | ✅ HAVE | 90+ aging bucket |
| 5 | **# of appointments for today** | ❌ MISSING | Needs CRM/leasing platform integration |
| 6 | **# of Shows in Last 7 Days** | ⚠️ PARTIAL | Have `tours` count in leasing funnel but only L30, not L7 |
| 7 | **Live feed on CRM queue** | ❌ MISSING | Needs CRM integration (Knock, RealPage ILS, etc.) |
| 7a | — Unreviewed | ❌ MISSING | Needs CRM |
| 7b | — Prospects w/o active follow ups | ❌ MISSING | Needs CRM |
| 7c | — Follow ups | ❌ MISSING | Needs CRM |
| 8 | **In-Place rent vs Asking by floor plan** | ✅ HAVE | UnitMixPricing component with delta column |
| 9 | **# of available units by floor plan** | ⚠️ GAP | Have per-floorplan unit count but NOT vacancy per floorplan |
| 9a | — Broken out into vacant vs on notice | ⚠️ GAP | Have property-level totals but not per-floorplan breakdown |
| 10 | **Comp data – market survey comparison** | ✅ HAVE | MarketCompsTable with ALN data by bedroom type |
| 11 | **Future occupancy by week + weekly move ins/outs** | ⚠️ GAP | Have exposure (30d/60d) and move-in/out counts but not weekly time series |
| 12 | **Trailing 7 and Trailing 30 trade outs** | ⚠️ PARTIAL | Have `get_lease_tradeouts` endpoint but not split into T7 vs T30 windows |
| 13 | **Google rating with recent trends and reviews** | ❌ MISSING | Need Google Places API integration |

---

## Summary

| Category | Count |
|----------|-------|
| ✅ Fully covered | **8** (Occupancy, Pre-leased, ATR, Delinquency w/ buckets, In-Place vs Asking, Comps) |
| ⚠️ Partial / Small gap | **4** (Shows L7, Available by floorplan, Future occupancy weekly, Trade-outs T7/T30) |
| ❌ Missing entirely | **3** (Appointments today, CRM queue feed, Google reviews) |

---

## Gap Analysis & Steps to Fill

### GAP 1: Available Units by Floorplan (Vacant vs Notice) — EASY
**Effort**: ~2 hours | **Data source**: Already in `unified_units`

We already store `status` (vacant/notice/occupied) and `floorplan_name` per unit. Just need to:
1. Add a query in `unit_query_service.py` that groups by floorplan and status
2. Add an API endpoint `/properties/{id}/availability-by-floorplan`
3. Add a small table/card in the frontend showing: Floorplan | Total | Vacant | On Notice | Available

### GAP 2: Future Occupancy by Week + Weekly Move Ins/Outs — MODERATE
**Effort**: ~4 hours | **Data source**: `unified_residents` (lease_end, move_in_date)

We have all the lease dates. Need to:
1. Build a weekly projection: for each of the next 8-12 weeks, calculate expected move-outs (lease_end in that week) and move-ins (future residents with move_in in that week)
2. Project occupancy: current occupied - cumulative move-outs + cumulative move-ins
3. Add endpoint `/properties/{id}/occupancy-forecast`
4. Add a small line chart in the frontend

### GAP 3: Trailing 7 / Trailing 30 Trade Outs — EASY
**Effort**: ~1 hour | **Data source**: Already in `realpage_leases`

We already have `get_lease_tradeouts()` in pricing_service.py. Just need to:
1. Add `days` parameter to filter by move-in date (T7 = last 7 days, T30 = last 30 days)
2. Return separate T7 and T30 summaries (avg prior rent, avg new rent, avg change)
3. Show as a KPI card or mini-table

### GAP 4: Shows in Last 7 Days — EASY
**Effort**: ~1 hour | **Data source**: RealPage activity report (already imported)

We have the activity report data. Just need to:
1. Query `realpage_activity` for "Show" events in the last 7 days
2. Add to leasing funnel response or as a separate field

### GAP 5: Google Rating + Reviews — MODERATE
**Effort**: ~3 hours | **Data source**: Google Places API

**Recommended approach**: Google Places API (NOT scraping)
- Use a personal Gmail to create a Google Cloud project
- Enable the **Places API (New)** 
- Free tier: $200/month credit (~28,000 basic lookups or ~5,000 with reviews)
- The `places.get` endpoint returns: rating, user_ratings_total, reviews (up to 5 recent)
- Store results in `unified.db` with a `google_reviews` table
- Refresh weekly (31 properties × 1 call = 31 calls/week = negligible cost)

**Why not scraping**: Google actively blocks scrapers, results are unreliable, and it violates ToS. The Places API is cheap/free for this volume and gives structured data.

**Gmail vs service account**: A personal Gmail works fine. Create a project at console.cloud.google.com, enable Places API, create an API key. No billing needed until you exceed $200/month (we'd use ~$0.50/month).

### GAP 6: Appointments Today — HARD (External dependency)
**Effort**: Depends on CRM | **Data source**: CRM platform

This requires integration with whatever CRM/leasing platform Kairoi uses:
- **If RealPage CRM (OneSite Leasing)**: May be available via RealPage reporting API
- **If Knock/Funnel/Anyone Home**: Would need separate API integration
- **Action**: Ask Kairoi which CRM they use for appointment scheduling

### GAP 7: Live CRM Queue Feed — HARD (External dependency)
**Effort**: Significant | **Data source**: CRM platform

Same CRM dependency as appointments. The "unreviewed", "prospects w/o follow ups", and "follow ups" categories are CRM-specific concepts:
- **RealPage CRM**: Would need Guest Card API access
- **Third-party CRM**: Would need their specific API
- **Action**: Determine CRM platform, evaluate API access

---

## Recommended Priority Order

| Priority | Item | Effort | Impact |
|----------|------|--------|--------|
| 1 | Available by floorplan (vacant/notice) | 2h | High — directly requested, data ready |
| 2 | Trade-outs T7/T30 | 1h | High — data ready, just needs filtering |
| 3 | Shows in L7 | 1h | Medium — data likely available |
| 4 | Future occupancy weekly chart | 4h | High — impressive visualization |
| 5 | Google reviews | 3h | Medium — needs API key setup |
| 6 | Appointments today | ? | High — needs CRM clarification |
| 7 | CRM queue feed | ? | High — needs CRM clarification |

**Items 1-4 can be done immediately (~8 hours total) with existing data.**
**Item 5 needs a Google Cloud API key (free).**
**Items 6-7 need clarification on which CRM platform is used.**
