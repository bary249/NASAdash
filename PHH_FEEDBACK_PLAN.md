# PHH Design Partner Feedback — Execution Plan

**Date**: Feb 14, 2026  
**Source**: PHH feedback session  
**Status**: DRAFT — Awaiting approval

---

## Workstream Overview

| # | Workstream | Priority | Effort | Status |
|---|-----------|----------|--------|--------|
| 0 | Test Infrastructure | PREREQUISITE | M | Not started |
| 1 | Renewals & Definitions | HIGH | L | Not started |
| 2 | Availability & Occupancy (ATR) | HIGH | L | Not started |
| 3 | AR Separation (Current vs Former) | HIGH | S | Not started |
| 4 | Reviews & Reputation (ILS) | HIGH | L | Not started |
| 5 | Dashboard Consolidation | MEDIUM | L | Not started |
| 6 | Watch List Tab | MEDIUM | M | Not started |
| 7 | Collections & AR Deep | WISH LIST | — | Deferred |

---

## WS0: Test Infrastructure (PREREQUISITE)

> Protect what we have before changing anything. Regression tests for every existing endpoint.

### Backend Tests (pytest + httpx AsyncClient)

| Task | File | Description |
|------|------|-------------|
| 0.1 | `backend/tests/conftest.py` | Test fixtures: FastAPI test client, sample unified.db with seed data |
| 0.2 | `backend/tests/test_occupancy.py` | Test `/properties/{id}/occupancy` returns valid OccupancyMetrics shape |
| 0.3 | `backend/tests/test_pricing.py` | Test `/properties/{id}/pricing` returns valid floorplan data |
| 0.4 | `backend/tests/test_expirations.py` | Test `/properties/{id}/expirations` and `/expirations/details` |
| 0.5 | `backend/tests/test_renewals.py` | Test `/properties/{id}/renewals` shape + summary fields |
| 0.6 | `backend/tests/test_tradeouts.py` | Test `/properties/{id}/tradeouts` shape + prior_rent field |
| 0.7 | `backend/tests/test_delinquency.py` | Test `/properties/{id}/delinquency` aging buckets + totals |
| 0.8 | `backend/tests/test_reviews.py` | Test `/properties/{id}/reviews` returns reviews array |
| 0.9 | `backend/tests/test_forecast.py` | Test `/properties/{id}/forecast` weekly projections |
| 0.10 | `backend/tests/test_portfolio.py` | Test `/portfolio/summary`, `/portfolio/risk-scores` |
| 0.11 | `backend/tests/test_chat.py` | Test `/properties/{id}/chat` returns string response |

### Frontend Tests (vitest)

| Task | File | Description |
|------|------|-------------|
| 0.12 | `frontend/src/__tests__/api.test.ts` | API client method signatures & URL construction |
| 0.13 | `frontend/vitest.config.ts` | Vitest setup for React/TSX |

---

## WS1: Renewals & Definitions

> PHH wants: calendar month tracking, "Selected" status, comparison vs prior resident rent (not market rent).

### What exists today
- `pricing_service.get_renewal_leases()` — Filters by trailing `days` window, compares renewal rent **vs market rent**
- `pricing_service.get_lease_tradeouts()` — Already compares **prior resident rent vs new rent** ✓
- Expirations tracked by 30/60/90-day windows

### Tasks

| Task | Where | Description |
|------|-------|-------------|
| 1.1 | `pricing_service.py` | Add `month` parameter to `get_renewal_leases()` — filter by calendar month (e.g. `2026-04`) instead of trailing days |
| 1.2 | `pricing_service.py` | Add `prior_rent` to renewal response — JOIN to prior lease on same unit to get the rent the resident was paying before renewal |
| 1.3 | `pricing_service.py` | Renewal summary: add `avg_prior_rent`, `avg_vs_prior`, `avg_vs_prior_pct` alongside existing vs-market fields |
| 1.4 | `routes.py` | Update `/renewals` endpoint: accept `month=2026-04` param, pass to service |
| 1.5 | `routes.py` | Update `/expirations` endpoint: add `month` param option (alongside existing `days`) |
| 1.6 | `TradeOutSection.tsx` | Verify trade-out already uses prior rent (it does ✓) — no change needed |
| 1.7 | `DashboardV3.tsx` | Update renewals tab: month selector (Apr/May/Jun/Jul...) replacing 30/60/90 |
| 1.8 | New component | `RenewalsByMonth.tsx` — calendar month view with prior-rent comparison columns |
| 1.9 | `schema.py` / sync | Handle Yardi "Selected" status: map to `renewal_selected` (terms chosen, paperwork pending) |

### Definition changes
- **Trade-out base**: Prior resident rent (ALREADY CORRECT ✓)
- **Renewal comparison**: vs prior resident rent (NEW — currently vs market rent)
- **"Selected" in Yardi**: Resident has chosen renewal terms but lease paperwork not yet completed → distinct from "Renewed"

---

## WS2: Availability & Occupancy (ATR)

> PHH wants: ATR metric, 0-30/30-60 buckets, 7-week trend, direction indicator.

### What exists today
- `OccupancySectionV2.tsx` — Shows occupancy, exposure 30/60, vacancy breakdown
- `occupancy_service.py` — Calculates vacant, leased, preleased, notices
- `/forecast` endpoint — Already has weekly projections

### Tasks

| Task | Where | Description |
|------|-------|-------------|
| 2.1 | `occupancy_service.py` | New method `get_availability_metrics()` — calculates ATR = vacant + on_notice − preleased |
| 2.2 | `occupancy_service.py` | Availability buckets: units available in 0-30 days, 30-60 days, total availability % |
| 2.3 | `routes.py` | New endpoint `GET /properties/{id}/availability` returning ATR + buckets |
| 2.4 | `routes.py` or service | 7-week ATR trend: compute ATR at each of the last 7 week-ends (from box_score history or forecast) |
| 2.5 | `OccupancySectionV2.tsx` | Add ATR card with trend arrow (↑ = worsening, ↓ = improving) |
| 2.6 | New component | `AvailabilityTrend.tsx` — 7-week sparkline/mini-chart for ATR |
| 2.7 | `api.ts` + `types.ts` | Add `getAvailability()` method and TypeScript types |

### Definitions
- **ATR** = Total Vacant + On Notice (NOT preleased). Matches Yardi definition.
- **Availability %** = ATR / Total Units
- **Direction**: Is ATR trending up (bad) or down (good)?

---

## WS3: AR Separation (Current vs Former Residents)

> Moved-out residents should be separated from standard AR. Quick win — data already has status.

### What exists today
- Delinquency report has `status` column (Current resident, Former resident, etc.)
- `unified_delinquency` table has `status` field
- UI shows all delinquent residents in one list

### Tasks

| Task | Where | Description |
|------|-------|-------------|
| 3.1 | `routes.py` | Delinquency endpoint: split response into `current_residents` and `former_residents` sections |
| 3.2 | `routes.py` | Add summary subtotals: current_total_delinquent, former_total_delinquent |
| 3.3 | `DelinquencySection.tsx` | Two sections: "Current Resident AR" (primary) and "Former Resident AR" (secondary/collapsible) |
| 3.4 | `PortfolioView.tsx` | Portfolio delinquency: show current vs former breakdown |

---

## WS4: Reviews & Reputation (ILS Expansion)

> Only top-volume ILS sites. Andrew has detailed data. "Review Power" scatter plot.

### What exists today
- Google Reviews only (SerpAPI, Places API, Playwright scraper)
- `GoogleReviewsSection.tsx` — star distribution, response tracking, review cards

### Tasks

| Task | Where | Description |
|------|-------|-------------|
| 4.1 | Research | Identify scraping/API approach for Apartments.com and ApartmentRatings.com |
| 4.2 | New service | `ils_reviews_service.py` — Fetch reviews from top ILS sites (Apartments.com, ApartmentRatings) |
| 4.3 | `routes.py` | Extend `/reviews` endpoint to include `sources` array (Google, Apartments.com, etc.) |
| 4.4 | `GoogleReviewsSection.tsx` → rename | Rename to `ReviewsSection.tsx` — multi-source tabs (Google, Apartments.com, etc.) |
| 4.5 | New component | `ReviewPowerChart.tsx` — Scatter plot: X=review velocity, Y=avg rating, bubble=volume |
| 4.6 | Service | Add review recency metric (% of reviews in last 30/90/180 days) |
| 4.7 | Service | Add time-over-time performance (avg rating trailing 90d vs prior 90d) |
| 4.8 | **BLOCKER** | Schedule working session with Andrew to review his metrics and align on which sites |

---

## WS5: Dashboard Consolidation

> Combine occupancy + units-on-market + asking into one table. Bedroom-type view. Subject property first then comps.

### Tasks

| Task | Where | Description |
|------|-------|-------------|
| 5.1 | New component | `CombinedOccupancyTable.tsx` — Occupancy, units on market, asking rent in one table |
| 5.2 | Above component | Row-per-bedroom-type view (Studio, 1BR, 2BR, 3BR) instead of floorplan |
| 5.3 | `pricing_service.py` | Add bedroom-type aggregation method (group floorplans by bedroom count) |
| 5.4 | `routes.py` | New endpoint or param `?group_by=bedrooms` on `/pricing` |
| 5.5 | New component | `CombinedMarketView.tsx` — Available units + market comps + unit mix in one table |
| 5.6 | Above component | Format: subject property row first, then comp set rows below for comparison |
| 5.7 | `DashboardV3.tsx` | Wire new combined components into Overview tab, replacing separate sections |

---

## WS6: Watch List Tab

> Surface properties not meeting performance thresholds.

### Tasks

| Task | Where | Description |
|------|-------|-------------|
| 6.1 | `routes.py` or `portfolio.py` | New endpoint `GET /portfolio/watch-list` — properties below thresholds |
| 6.2 | Backend | Define threshold config: min occupancy %, max aged vacancy, min conversion rate, max delinquency %, min ATR direction |
| 6.3 | `TabNavigation.tsx` | Add "Watch List" tab to portfolio view |
| 6.4 | New component | `WatchListView.tsx` — Table of flagged properties with the metric(s) that triggered the flag |
| 6.5 | Component | Red/yellow severity indicators, link to drill into each property |

---

## WS7: Collections & AR Deep (WISH LIST — Deferred)

> Collections data not in Yardi. Requires agency integration. Deferred per PHH.

- No action now
- Track as future integration opportunity

---

## Execution Order

```
Phase 1 (Week 1): WS0 (Tests) — protect everything
Phase 2 (Week 1-2): WS3 (AR Separation — quick win) + WS1 (Renewals — core)
Phase 3 (Week 2-3): WS2 (Availability/ATR — core)
Phase 4 (Week 3): WS4 (Reviews — scaffold + Andrew session)
Phase 5 (Week 3-4): WS5 (Dashboard consolidation) + WS6 (Watch List)
```

---

## Access & Follow-up

- [ ] Peter: ongoing dashboard access for deeper review
- [ ] Andrew: working session on review metrics, "Review Power" scatter plot
- [ ] Define performance thresholds for Watch List (with PHH input)
