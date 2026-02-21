# Dashboard Feedback Implementation Plan

**Source**: Comments on Dashboard.docx (colleague review)
**Created**: 2026-02-20
**Response doc**: FEEDBACK_RESPONSE.md (our comments back to reviewer)

---

## Area 1: Portfolio Overview Tab
| ID | Task | Complexity | Status |
|----|------|-----------|--------|
| PO-1 | Show **total leased %** in metrics section | Low | ✅ DONE |
| PO-2 | Simplify conversion ratios to: Lead→Tour, Tour→App, App→Lease, Lead→Lease | Low | ✅ DONE |
| PO-3 | Add blended rate for renewal + trade outs | Low | ✅ DONE (already implemented) |
| PO-4 | Clarify weighted avg vs row matrix — add tooltip/label | Low | ✅ DONE |
| PO-5 | Bedroom consolidated: rename "Market" → "Asking", swap In-Place before Asking | Low | ✅ DONE |
| PO-6 | Unit Mix & Pricing: add Bedroom/Floorplan toggle on consolidated view | Medium | ✅ DONE |

### QA Checkpoint — Area 1
- [ ] Leased % visible in portfolio metrics
- [ ] Conversion ratios show only 4 (Lead→Lease, Lead→Tour, Tour→App, App→Lease)
- [ ] Blended card present (already done — verify)
- [ ] Weighted avg vs row matrix has clarifying tooltip
- [ ] Bedroom table: "Asking" column label, Asking before In-Place
- [ ] Unit type toggle functional on Unit Mix

---

## Area 2: Leasing Tab
| ID | Task | Complexity | Status |
|----|------|-----------|--------|
| LS-1 | Consider moving Availability/ATR + Market Comps from Overview → Leasing | Medium | DISCUSS |
| LS-2 | Show conversion ratios below leasing activity bars | Low | ✅ DONE (already implemented) |
| LS-3a | Lead Sources: add a **total row** | Low | ✅ DONE |
| LS-3b | Lead Sources: "Previous month" shows YTD dates instead of prior month — **BUG** | Low | ✅ DONE |
| LS-4a | Restructure Available Units by Floorplan columns: Floorplan, Units, Avail, Vacant, Pre-leased, NTV, In-Place, Asking + % bar | Medium | ✅ DONE |
| LS-4b | Add unit type toggle (same as PO-6) | Medium | ✅ DONE |
| LS-4c | Bottom totals row misaligned — **BUG** | Low | ✅ DONE |
| LS-5a | Occupancy Forecast: clarify purpose of Pre-leased/On Notice buttons (tooltip or remove) | Low | ✅ DONE (tooltips added) |
| LS-5b | Forecast table: add sub-headers "Net Move In" and "Expirations & Renewals" | Low | ✅ DONE |
| LS-5c | Proj. NTV drill-through not linked — **BUG** | Low | ✅ DONE (projected_notice_units missing from merge) |
| LS-5d | Rename "Notice Out" → "Move Out" (confirmed move-outs) | Low | ✅ DONE |

### QA Checkpoint — Area 2
- [ ] Conversion ratios visible below leasing bars
- [ ] Lead sources has total row
- [ ] "Previous month" period shows correct date range (not YTD)
- [ ] Floorplan table restructured with new columns
- [ ] Totals row alignment fixed
- [ ] Forecast table has grouped sub-headers
- [ ] Proj. NTV clickable with drill-through
- [ ] "Notice Out" renamed to "Move Out"

---

## Area 3: Renewal Tab
| ID | Task | Complexity | Status |
|----|------|-----------|--------|
| RN-1 | Monthly view: limit to **4 months ahead** only (remove Jun–Dec tiles) | Low | ✅ DONE |
| RN-2 | Add time period filter for Avg Renewal, Prior, Variance (currently hardcoded MTD) | Medium | ✅ DONE (already works via global time range) |
| RN-3 | Graph: rename "Vacating" → "NTV" | Low | ✅ DONE |
| RN-4 | Show if concession was given on renewals | Medium | TODO — needs data source investigation |
| RN-5 | Future: greyed-out renewal forecast + behavioral insights section (Venn scoring) | Future | PLANNED |
| RN-6a | Move-out reasons: clarify "Transfer to new unit" meaning | — | CLARIFY with data team |
| RN-6b | "Non-renewal" under eviction: clarify if eviction process or PM decision | — | CLARIFY with data team |
| RN-7 | Yardi "Selected" status mapping — how shown on dashboard? | — | CLARIFY (Yardi-only) |

### QA Checkpoint — Area 3
- [ ] Monthly tiles show only 4 months ahead
- [ ] Renewal avg/prior/variance has period filter
- [ ] Graph label says "NTV" not "Vacating"
- [ ] Concession indicator visible on renewal drill-through (if data available)

---

## Area 4: Delinquencies Tab
| ID | Task | Complexity | Status |
|----|------|-----------|--------|
| DQ-1 | **DATA BUG**: Aging bucket totals don't match resident AR table — investigate & fix | High | ✅ DONE (negative bucket offsets now reconciled to current) |
| DQ-2 | Move Active Eviction next to Total Delinquent; de-emphasize Pre-paid | Low | ✅ DONE |
| DQ-3a | Add **eviction reason** to eviction records | Medium | TODO — needs data source |
| DQ-3b | Add **eviction filing date** and **days under eviction** | Medium | TODO — needs data source |
| DQ-4 | Investigate: evictions that owe $0 or $60 — is data correct? | — | INVESTIGATE |

### QA Checkpoint — Area 4
- [ ] Aging bucket sum matches total delinquent (with documented tolerance)
- [ ] Eviction KPI moved next to Total Delinquent
- [ ] Test: `test_delinquency_aging_vs_summary_consistency` passes
- [ ] Eviction details show reason/filing date (if data available)

---

## Area 5: Financials Tab — MAJOR RESTRUCTURE
| ID | Task | Complexity | Status |
|----|------|-----------|--------|
| FN-1 | Actual vs Budget P&L per selected period (filter) | High | DISCUSS |
| FN-2 | Closed months: full P&L with expenses; default = income lines + expense categories | High | DISCUSS |
| FN-3 | Current month: income only + estimated expenses (6-month avg) | High | DISCUSS |
| FN-4 | Show KPI factors: physical/economic occupancy, delinquency rate | Medium | DISCUSS |
| FN-5 | Future: "below the line" expenses (debt service, capex, non-operating) | Future | PLANNED |
| FN-6 | Bottom 3 boxes → make drill-through instead of always visible | Low | ✅ DONE |

### QA Checkpoint — Area 5
- [ ] REQUIRES DISCUSSION before implementation — colleague will send financial format
- [ ] Budget data source identified

---

## Area 6: Other Sections
| ID | Task | Complexity | Status |
|----|------|-----------|--------|
| MT-1 | Remove Maintenance tab for PHH users | Low | ✅ DONE |
| WP-1 | Watchpoints: Occ trigger default changed to **< 90%** | Low | ✅ DONE |
| WP-2 | Watchpoints: clarify ATR >40 vs >50 — simplify to single threshold | Low | ✅ DONE (ATR + ATR% both available) |
| WP-3 | Watchpoints: Google rating → Overall Rating (Google + Apartments.com combined) | Low | ✅ DONE |
| WP-4 | Watchpoints: remaining are placeholders — acknowledge | — | NOTE |

### QA Checkpoint — Area 6
- [ ] PHH login → no Maintenance tab visible
- [ ] Watchpoint defaults corrected
- [ ] Watchpoint thresholds make semantic sense

---

## Area 7: AI / Ask Me Anything
| ID | Task | Complexity | Status |
|----|------|-----------|--------|
| AI-1 | Fix failing questions: lead source queries (apt.com, zillow) | Medium | ✅ DONE |
| AI-2 | Fix: total leads month-over-month insights | Medium | ✅ DONE (YTD+MTD data in context) |
| AI-3 | Fix: lowest occupancy in last 6 months | Medium | ✅ DONE (DATA GAP: only ~4 days of snapshots — needs longer collection) |
| AI-4 | Fix: occupancy projection assuming no new activity | Medium | ✅ DONE |
| AI-5 | Fix: unit type vacancy/demand analysis | Medium | ✅ DONE |
| AI-6 | Implement decision-workflow response format: Observation → Diagnosis → Financial Impact → Action | High | ✅ DONE |
| AI-7 | Map 10 AI categories to available data sources (gap analysis) | Medium | ✅ DONE (see below) |

### AI-7: Gap Analysis — AI Categories vs Data Sources

| # | AI Category | Data Source | Status | Gap |
|---|------------|-------------|--------|-----|
| 1 | **Occupancy Analysis** | `unified_occupancy_metrics`, `unified_units` | ✅ Full | — |
| 2 | **Lead Source Performance** | `unified_advertising_sources` (YTD + MTD) | ✅ Full | — |
| 3 | **Pricing & Loss-to-Lease** | `unified_pricing_metrics`, `unified_units` | ✅ Full | — |
| 4 | **Leasing Funnel** | `occupancy_service.get_leasing_funnel()` | ✅ Full | — |
| 5 | **Occupancy Projections** | `unified_projected_occupancy` (12 weeks) | ✅ Full | — |
| 6 | **Unit Type / Demand** | `unified_units` (bedrooms, vacancy, rent) | ✅ Full | — |
| 7 | **Delinquency & Collections** | `unified_delinquency` | ✅ Full | — |
| 8 | **Renewals & Trade-outs** | `unified_renewals`, `unified_tradeouts` | ✅ Full | — |
| 9 | **Historical Trends (6mo)** | `unified_occupancy_metrics` snapshots | ⚠️ Partial | Only ~4 days of snapshots; need 6+ months of box_score downloads |
| 10 | **Online Reputation** | Google reviews cache + Apartments.com cache | ✅ Full | PHH fully covered; Kairoi Apartments.com mapping needed if/when onboarded |

### QA Checkpoint — Area 7
- [x] All 7 listed "broken" questions return useful answers
- [x] AI responses follow Observation → Diagnosis → Impact → Action format
- [x] Gap analysis doc complete

---

## Test Coverage Requirements
Every data validation fix must add a test to `backend/tests/test_ui_data_integrity.py`:

| Test ID | Validates | For Task |
|---------|-----------|----------|
| `test_delinquency_aging_vs_summary_consistency` | Aging buckets sum ≈ total_delinquent per resident (with documented tolerance) | DQ-1 |
| `test_delinquency_eviction_has_balance` | Eviction residents have non-zero balance | DQ-4 |
| `test_lead_sources_total_row` | Lead sources total matches sum of sources | LS-3a |
| `test_lead_sources_period_dates_correct` | Previous month date range doesn't bleed into current | LS-3b |
| `test_forecast_proj_ntv_drill_through` | Proj. NTV units are clickable and return data | LS-5c |

---

## Execution Order (Round 1 — COMPLETE)
1. ~~Quick wins (Area 1 partial + Area 6)~~
2. ~~Leasing fixes (Area 2)~~
3. ~~Delinquency (Area 4)~~
4. ~~Renewals (Area 3)~~
5. **Financials** (Area 5): REQUIRES DISCUSSION — don't start until format received
6. ~~AI (Area 7)~~

---

# Round 2 Feedback (2026-02-21)

**Source**: Comments on Dashboard (1).docx — reviewer re-tested deployed version

## Key Insight
Many "still broken" items were **already fixed locally but not deployed**. Priority #1 is a fresh deploy.

## R2: Portfolio Overview
| ID | Task | Type | Status |
|----|------|------|--------|
| R2-1 | Rename "Vacancy Rate" → just "Vacancy" (show % only) | UI label | TODO |
| R2-2 | Simplify conversion ratios: keep only **Lead→Lease** + **Lead→App** (remove Tour→App, Lead→Tour) | UI simplify | TODO |
| R2-3 | Remove period comparison below metrics (not comparing equivalent periods) or fix to compare same period | UI/data | TODO |
| R2-4 | **BUG**: In-Place tile ($1,451) vs table ($1,459) mismatch — different aggregation? Also: color the % green/red | Data bug | TODO |
| R2-5 | Restore ATR bar chart — "why did you remove the bar?" | UI regression | TODO |

## R2: Leasing Tab
| ID | Task | Type | Status |
|----|------|------|--------|
| R2-6 | **BUG**: L7 view — leads bar shows 16 but total prospects shows 6 | Data bug | TODO |
| R2-7 | Rename "CoStar" → "Apt.com" in lead sources (same company, different brand for leads) | UI rename | TODO |
| R2-8 | **BUG**: "Previous Month" dates show 2/1-2/19 instead of January (was fixed locally — deploy needed) | Deploy | TODO |
| R2-9 | Remove pre-leased / on-notice toggle buttons from forecast section ("only relevant to today") | UI cleanup | TODO |

## R2: Occupancy Forecast
| ID | Task | Type | Status |
|----|------|------|--------|
| R2-10 | Proj NTV + RNW% columns not aligned/bolded like others; add visible divider between "Net Move In" and "Expirations" groups | UI formatting | TODO |

## R2: Delinquencies
| ID | Task | Type | Status |
|----|------|------|--------|
| R2-11 | **BUG**: DQ aging bar vs AR table STILL mismatched on deployed (fixed locally — deploy needed) | Deploy | TODO |
| R2-12 | DQ tiles color mismatch — tile is red but table is grey; make consistent | UI styling | TODO |

## R2: Watchpoints
| ID | Task | Type | Status |
|----|------|------|--------|
| R2-13 | Two occupancy watchpoints contradict each other — remove duplicate | Config | TODO |
| R2-14 | ATR: remove 50% threshold (or give 40/50 different severity colors) | Config | TODO |
| R2-15 | Google rating watchpoints contradict each other — consolidate | Config | TODO |

## R2: AI
| ID | Task | Type | Status |
|----|------|------|--------|
| R2-16 | "Same answer as before" on 4 questions — deployed AI context is stale, needs redeploy | Deploy | TODO |

## R2 Execution Order
1. **Batch 1 — Quick UI fixes** (R2-1, R2-2, R2-7, R2-9, R2-10, R2-12): labels, simplify, cleanup
2. **Batch 2 — Watchpoint fixes** (R2-13, R2-14, R2-15): config contradictions
3. **Batch 3 — Data bugs** (R2-4, R2-6): investigate tile vs table, leads vs prospects
4. **Batch 4 — Medium** (R2-3, R2-5): period comparison, ATR bar restore
5. **Deploy** (R2-8, R2-11, R2-16): push all fixes to Railway + Netlify
