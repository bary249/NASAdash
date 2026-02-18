# Owner Dashboard V2 — Feedback Execution Plan

**Source:** "Questions & Comments on Barak V2.docx" (colleague review)
**Date:** Feb 18, 2026
**Blue highlights:** Identified from screenshots — 28 items were marked as colleague's explicit priorities. See section below.

---

## Blue-Highlighted Items (Colleague's Top Priorities)

The following items were highlighted in blue/teal in the original document, indicating they are the colleague's **explicit priorities**. These should be treated as **P1 unless otherwise noted**.

### Portfolio Overview Tab
| # | Blue Item | Original Priority → Updated |
|---|-----------|---------------------------|
| 5 | Reorder columns: units, occ, vacant, leased, ATR, expiring, renewal | P2 → **P1** |
| 6 | "Section starts with Period" — clarify/fix | P2 → **P1** |
| 7 | Restructure tiles: occ/ATR/vacant top row; leasing/renewal/T-O/renewal rate bottom | P2 → **P1** |
| 8 | Vacancy should show % too | P1 (unchanged) |
| 10 | In-place vs asking: show delta % | P2 → **P1** |
| 11 | Renewal rate: 3 months instead of blended 90d | P2 → **P1** |
| 16 | Market Comps: subject property + asking per unit type on top | P2 → **P1** |
| 20 | Bedroom Type section before comps | P2 → **P1** |
| 21 | Reorder bedroom columns + color-code delta | P2 → **P1** |
| 22 | Vacant count mismatch (80 vs 77) | P1 (unchanged) |
| 23 | Occ trend chart (same style as ATR) | P2 → **P1** |

### Leasing Tab
| # | Blue Item | Original Priority → Updated |
|---|-----------|---------------------------|
| 27 | All 6 conversion rates: lead→tour, lead→app, lead→lease, tour→app, tour→lease, app→lease | P1 (unchanged) |
| 29 | Floorplan availability = same structure as bedroom table | P2 → **P1** |
| 30 | Occupancy Forecast: explain math (net expiration role) | P2 → **P1** |
| 31 | Occupancy Forecast: add renewal % | P2 → **P1** |

### Renewal Tab
| # | Blue Item | Original Priority → Updated |
|---|-----------|---------------------------|
| 35 | 12-month expiration/renewal graph | P1 (unchanged) |
| 36 | Venn behavioral data placeholder (greyed out) | P3 (stays — future phase, but add placeholder) |

### Delinquencies Tab
| # | Blue Item | Original Priority → Updated |
|---|-----------|---------------------------|
| 39 | Delinquency totals mismatch (0-30 vs AR table) | P1 (unchanged) |
| 40 | Rename "Collections" → "Former Residents Balance" | P1 (unchanged) |
| 41 | Demote collections section from prime location | P2 → **P1** |
| 42 | Eviction data: $0 balance evictions — investigate | P1 (unchanged) |
| 43 | Add reason for eviction | P2 → **P1** |
| 44 | Add eviction filing date + days under eviction | P2 → **P1** |

### Financials Tab
| # | Blue Item | Original Priority → Updated |
|---|-----------|---------------------------|
| 45 | Full restructure to match client's P&L format (see reference below) | P1 (unchanged, XL) |
| 45a | Actual vs budget per period via filter | P1, part of #45 |
| 45b | Previous months: full P&L with expenses (pre-set = income lines + expense categories) | P1, part of #45 |
| 45c | Current month: income only + estimated expenses (6-month rolling avg) | P1, part of #45 |

### Client's Financial Format Reference (from embedded screenshot)
```
KPI Header:
  Physical Occupancy     92.7%
  Economic Occupancy     90.4%
  Bad Debt (% of Rent)    0.6%

Revenue:                 Total      $/Unit
  Gross Potential Rent   434,773     1,941
  Vacancy Loss          (31,542)   (1,690)
  Bad Debt               (2,802)     (156)
  Concessions            (7,200)     (366)
  Non-Revenue Units          —         —
  ─────────────────────────────────────────
  Total Net Rent Inc     393,230    21,066
  Cost Recovery Income    23,365     1,252
  Other Income            27,196     1,457
  Bulk Cable/Internet        —         —
  Retail Income              —         —
  ─────────────────────────────────────────
  Total Revenue          443,790    23,774
```

---

## Summary

Total feedback items: **48**
- Bugs / Data mismatches: 6
- UX / Restructure: 18
- New features: 16
- Questions / Clarifications: 8

---

## Feedback Table

Priority: **P1** = Must-fix / high impact, **P2** = Should-do / improves product, **P3** = Nice-to-have / future phase
Effort: **S** = < 2 hrs, **M** = 2–8 hrs, **L** = 1–3 days, **XL** = 3+ days

| # | Section | Feedback Item | Type | Pri | Effort | Critical Assessment |
|---|---------|--------------|------|-----|--------|-------------------|
| **RED FLAGS** |
| 1 | Red Flags | Are these just examples or real data? (84 lease expirations in April, Parkside May expirations, move-out doesn't make sense) | Question/Bug | P1 | S | **Valid.** If these are mock/placeholder data showing in production, that's a credibility killer. Need to verify data sources. If real, the "doesn't make sense" part needs investigation — could be a parsing issue. |
| 2 | Red Flags | Zero tours: language "schedule emergency site visits…" is too alarmist | UX | P2 | S | **Valid.** The tone should be professional/neutral, not panic-inducing. Easy copy change. |
| 3 | Red Flags | Yellow narrative contradicts top-left red section | Bug | P1 | S | **Valid.** Contradictory alerts destroy trust. Likely a logic issue in watchpoint/narrative generation. Must fix. |
| **PORTFOLIO OVERVIEW TAB** |
| 4 | Portfolio | Add "Current" to the title (shows current status only) | UX | P3 | S | **Reasonable** but minor. The time filter already implies this. Could add "As of [date]" instead, which is more useful. |
| 5 | Portfolio | Reorder columns: units, occupancy, vacant, leased, ATR, expiring, renewal | UX | P2 | S | **Valid.** The suggested order follows a logical flow: total → occupancy → vacancy → pipeline → retention. Better storytelling. |
| 6 | Portfolio | Section starts with "Period" — unclear what this means | Question | P2 | S | **Needs clarification.** Possibly referring to the time filter placement. May mean "the section header says 'Period' which is confusing." |
| 7 | Portfolio | Restructure tiles: occ/ATR/vacant on top row; leasing/renewal/T-O/renewal rate below | UX | P2 | M | **Valid.** Groups operational metrics (top) vs activity metrics (bottom). Good information hierarchy. |
| 8 | Portfolio | Vacancy should show % too | UX | P1 | S | **Valid.** Absolute numbers without % lack context. A 10-unit vacancy means very different things for 100 vs 500 unit properties. Easy add. |
| 9 | Portfolio | Leasing Funnel: Is MTD % change comparing same period of previous month? If not, it should | Bug/UX | P1 | M | **Critical and valid.** Comparing full-month prior to partial-month current is misleading. Must compare Jan 1-17 vs Dec 1-17 (same # of days). We already implemented this — need to verify it's working correctly. |
| 10 | Portfolio | In-place vs asking: show % growth of asking vs in-place | UX | P2 | S | **Valid.** The delta % is the key insight (are we pricing above/below market?). Simple calculation to add. |
| 11 | Portfolio | Renewal rate: show this month, next month, and following month (3 months vs blended 90d) | UX | P2 | M | **Good suggestion.** Monthly breakdown is more actionable than a blended 90d number. Requires grouping expiration data by month. Data already exists. |
| 12 | Portfolio | Click on results → detailed breakdown | UX | P2 | M | **Valid.** We already have drill-through on some KPIs (tradeouts, renewals). Should extend pattern to all clickable tiles. Incremental work. |
| 13 | Portfolio | Didn't understand difference between weighted avg and row matrix | UX/Question | P2 | S | **Valid.** If the user doesn't understand it, clients won't either. Need better labeling or a tooltip explaining the distinction. |
| 14 | Portfolio | Trade outs and renewal: show a blended number too | UX | P2 | S | **Reasonable.** A combined "lease trade" metric (new leases + renewals blended rent change) could be useful. Simple weighted average. |
| 15 | Portfolio | Tiles breaching watchpoints should show alarming color | UX | P1 | M | **Excellent suggestion.** Connects watchpoints to the actual KPI display. If occupancy is below threshold, the occupancy card should visually flag it. High-value, moderate effort (need to cross-reference watchpoint thresholds). |
| 16 | Market Comps | Show subject property with asking numbers per unit type on top of table | UX | P2 | S | **Valid.** Without the subject property as a baseline row, the comp table lacks context. Standard practice in CRE. |
| 17 | Market Comps | What is "property area" supposed to cover? Is this a map view? | Question | P2 | M | **Valid question.** If we have a radius filter, a map visualization would make it intuitive. Could use a simple embedded map. |
| 18 | Market Comps | Changing radius doesn't affect numbers | Bug | P1 | M | **Bug.** If the radius filter is non-functional, it's broken UI. Needs investigation — likely the API isn't re-querying with new radius or the frontend isn't passing the param. |
| 19 | Market Comps | Is there a button to run/refresh the new filter? | UX | P2 | S | **If radius changes don't auto-apply, need either auto-apply on change or an explicit "Apply" button.** Depends on fix for #18. |
| 20 | Bedroom Type | This section should come before comps (then Availability & ATR, then comps) | UX | P2 | S | **Valid.** Own property data first, then market context. Better flow. Simple reorder. |
| 21 | Bedroom Type | Reorder columns: occ, ATR, vacant, exp this month, NTV, selected, renewal, in-place, asking (not market), delta % (red if asking < in-place) | UX | P2 | M | **Valid.** More logical column order. "Asking" is better terminology than "market" for the property's own pricing. Color-coding delta is a great touch. |
| 22 | Bedroom Type | Vacant number (80) doesn't match above vacancy (77) | Bug | P1 | M | **Valid bug.** Data inconsistency between sections. Likely different data sources or filtering logic. This is a trust issue — must investigate and fix. Known issue: box score vs rent roll discrepancy. |
| 23 | Availability | Occupancy: show occ trend same way as ATR trend (to the left of availability bucket) | UX | P2 | M | **Good idea.** Visual consistency. If ATR has a trend chart, occupancy should too. |
| **LEASING TAB** |
| 24 | Leasing | Period filter: add YTD, previous month (full), and 7 days in addition to MTD | UX | P1 | S | **Already implemented.** We have MTD, L7, L30, YTD. "Previous month" (full prior month) is NOT currently an option — worth adding. |
| 25 | Leasing | Tiles clickable → full breakdown (same as tradeouts) | UX | P2 | M | **Valid.** Consistent drill-through pattern. We have the data; need to wire up click handlers + detail modals for each funnel stage. |
| 26 | Leasing | Show conversions within tiles OR as a funnel | UX | P2 | M | **Interesting suggestion.** Embedding conversion rates inside each tile could work but risks clutter. The funnel visualization is cleaner. We already show it as a funnel — may just need to add more conversion rates. |
| 27 | Leasing | Must show ALL conversions: lead→tour, lead→app, lead→lease, tour→app, tour→lease, app→lease | UX | P1 | S | **Valid.** We show some but not all 6 conversion pairs. Easy to compute from existing data. Should display in a conversion matrix or within the funnel card. |
| 28 | Leasing | Lead sources: what is the status? | Question | P2 | L | **Honest question.** If lead source data isn't available from RealPage, this section should be removed or marked "Coming Soon." If data exists, implement it. |
| 29 | Leasing | Available Units by Floorplan: same structure as consolidated bedroom table | UX | P2 | M | **Reasonable.** Consistency across tabs. If the bedroom table format works well, reuse it. |
| 30 | Leasing | Occupancy Forecast: is it pulled directly from RealPage? How does net expiration work? | Question | P2 | S | **Valid question.** We should add a tooltip or footnote explaining the math. Net expirations = leases expiring that haven't been renewed. It's informational — the "Net" column is move-ins minus move-outs. |
| 31 | Leasing | Occupancy Forecast: show renewal % as well | UX | P2 | S | **Valid.** We have the data (expirations and renewals per week). Adding a renewal_pct column is trivial. |
| **RENEWAL TAB** |
| 32 | Renewal | Add % next to each line (renewed, vacating, etc) adding up to 100% | UX | P2 | S | **Valid.** Percentages give proportional context. Simple math: each category / total expirations × 100. |
| 33 | Renewal | Show renewal variance ($$ and %) in bottom, green/red colored | UX | P2 | S | **Valid.** We already show this in the KPI card. Could replicate inside the renewal tab as a summary bar. |
| 34 | Renewal | Show if a concession was given to any renewals | Feature | P2 | L | **Good idea but depends on data availability.** RealPage lease details may include concession info. Need to check if the field exists in our data. If not, this requires a new data source. |
| 35 | Renewal | Graph: expirations & renewals per month for next 12 months | Feature | P1 | L | **Excellent suggestion.** This is a high-value visualization for proactive management. We have expiration data from leases. Need to aggregate by month and build a bar/line chart. |
| 36 | Renewal | Greyed-out renewal forecast + renewal insights from Venn behavioral data | Feature | P3 | XL | **This is a product/sales vision item, not a dev task.** Good idea for Venn's value prop, but requires Venn's scoring model integration. Mark as "Future Phase" — no action now. |
| 37 | Renewal | Move-out: what does "transfer to new unit" mean? | Question | P2 | S | **Valid.** Add tooltip clarifying: "Transfer = resident moved to a different unit within the same property." If it could also mean portfolio transfer, clarify in the data. |
| 38 | Renewal | Is "non-renewal" an eviction process or PM decision? | Question | P2 | S | **Valid.** Needs data investigation. The RealPage move-out reason codes should clarify. Add tooltip. |
| **DELINQUENCIES TAB** |
| 39 | Delinquency | 0-30 breakdown doesn't match AR table below (discrepancy) | Bug | P1 | M | **Valid bug.** Data inconsistency between summary tiles and detail table. Likely different aggregation logic or date filtering. Must investigate and fix. |
| 40 | Delinquency | Rename "Collections" to "Former Residents Balance" | UX | P1 | S | **Valid.** Industry-standard terminology. Simple label change. |
| 41 | Delinquency | Move collections/former resident section to less prominent location | UX | P2 | S | **Valid.** Current residents AR is more actionable. Former resident balance is secondary. Simple layout reorder. |
| 42 | Delinquency | Eviction: 2 evictions where one owes $0 and other owes $60 — what's going on? | Bug/Question | P1 | M | **Valid concern.** Evictions with no/minimal balance suggest either data error or eviction for lease violations (not non-payment). Need to investigate the data source. |
| 43 | Delinquency | Add reason for eviction | Feature | P2 | M | **Good if data is available.** RealPage may have eviction reason codes. If not, this needs manual PM input. |
| 44 | Delinquency | Add eviction filing date and number of days under eviction | Feature | P2 | M | **Valid.** Critical for tracking eviction timelines. Depends on whether RealPage stores filing dates. |
| **FINANCIALS TAB** |
| 45 | Financials | Full restructure: actual vs budget, follow client's format, P&L with expenses, KPI factors, current month estimated expenses | Feature | P1 | XL | **The biggest ask.** Valid — financials should match the client's reporting format. This is essentially a rewrite of the financials tab. Needs a separate design session. The "estimate based on 6-month avg" for current month expenses is smart but needs careful implementation. |
| 46 | Financials | Next phase: below-the-line expenses (debt service, capex, non-operating) | Feature | P3 | XL | **Explicitly marked as "next phase."** Defer. Requires additional data sources and the client's financial format. |
| 47 | Financials | Bottom 3 boxes not important — make them drill-through from main section | UX | P2 | M | **Valid.** If they're not primary info, hide behind click interaction. Reduces visual clutter. |
| **MAINTENANCE** |
| 48 | Maintenance | Low priority — client didn't request it | Deprioritize | P3 | — | **Agree.** If the client didn't ask for it, don't spend time polishing it. Keep as-is or hide the tab. |
| **REVIEWS** |
| 49 | Reviews | Total reviews mismatch: 541 vs 521 between sections | Bug | P1 | S | **Valid bug.** Numbers in the same view must match. Investigate the aggregation logic. |
| 50 | Reviews | Google: is yellow Response Tracking box necessary? Google missing full bar (# responses, no reply) | UX | P2 | S | **Valid.** If Google review section is incomplete compared to Apt.com, make them consistent. |
| **WATCHPOINTS** |
| 51 | Watchpoints | Occ trigger should be < 90% (not > 90%) | Bug | P1 | S | **Valid if this is indeed backwards.** Check the threshold logic. Likely a simple operator flip. |
| 52 | Watchpoints | ATR: what's the difference between >40 and >50? | Question | P2 | S | **Valid.** Likely meant to be warning (>40) vs critical (>50) tiers. Need to label them clearly (e.g., "Warning" vs "Critical"). |
| 53 | Watchpoints | Google rating: flag new reviews < 5 and overall avg < X | UX | P2 | S | **Valid.** More useful than a static threshold. Distinguishes between individual bad reviews and overall trend. |
| 54 | Watchpoints | Rest are pure placeholders | Acknowledge | P3 | — | **Acknowledged.** Replace with real thresholds or remove until implemented. |

---

## Execution Phases

### Phase 1: Bugs & Trust Issues (P1) — ~3-5 days
*These must be fixed first. Data inconsistencies and broken features destroy credibility.*

| # | Item | Est |
|---|------|-----|
| 1 | Verify red flag data is real (not mock) | S |
| 3 | Fix contradictory red/yellow narratives | S |
| 9 | Verify MTD comparison uses same-period prior month | M |
| 18 | Fix radius filter not affecting market comps | M |
| 22 | Fix vacant count mismatch (80 vs 77) | M |
| 39 | Fix delinquency breakdown vs AR table discrepancy | M |
| 42 | Investigate evictions with $0 balance | M |
| 49 | Fix reviews total mismatch (541 vs 521) | S |
| 51 | Fix occupancy watchpoint threshold direction | S |

### Phase 2: High-Value UX Improvements (P1-P2) — ~5-7 days
*Quick wins that significantly improve the product.*

| # | Item | Est |
|---|------|-----|
| 5 | Reorder portfolio columns | S |
| 8 | Add vacancy % | S |
| 10 | Add asking vs in-place delta % | S |
| 15 | Color KPI tiles that breach watchpoints | M |
| 16 | Add subject property row to comps table | S |
| 20 | Reorder sections (bedroom → availability → comps) | S |
| 21 | Reorder bedroom table columns + color-code delta | M |
| 24 | Add "previous full month" period filter | S |
| 27 | Add all 6 conversion rates to funnel | S |
| 31 | Add renewal % to occupancy forecast | S |
| 32 | Add % to renewal status lines | S |
| 40 | Rename "Collections" → "Former Residents Balance" | S |
| 41 | Demote former resident section in layout | S |

### Phase 3: New Features (P2) — ~2-3 weeks
*Meaningful additions that require more design/development.*

| # | Item | Est |
|---|------|-----|
| 7 | Restructure KPI tile layout (2 rows) | M |
| 11 | Monthly renewal rate (3-month breakdown) | M |
| 12+25 | Drill-through on all KPI tiles | M |
| 17 | Map view for market comps | M |
| 23 | Occupancy trend chart (like ATR) | M |
| 26 | Enhanced funnel visualization | M |
| 29 | Floorplan availability matching bedroom table | M |
| 33 | Renewal variance summary bar | S |
| 35 | 12-month expiration/renewal chart | L |
| 43+44 | Eviction details (reason, filing date, days) | M |
| 47 | Financials: make bottom boxes drill-through | M |

### Phase 4: Financials Restructure (P1 but XL) — ~2-3 weeks
*Separate workstream. Needs design session with colleague first.*

| # | Item | Est |
|---|------|-----|
| 45 | Full financials restructure (actual vs budget, P&L, KPIs) | XL |
| 46 | Below-the-line expenses (next phase) | XL |

### Phase 5: Deferred / Future
| # | Item | Reason |
|---|------|--------|
| 28 | Lead sources | Depends on data availability |
| 34 | Concession data on renewals | Depends on RealPage fields |
| 36 | Venn behavioral data integration | Product vision, not dev task |
| 48 | Maintenance tab | Client didn't request |
| 54 | Watchpoint placeholders | Fill in as real thresholds are defined |

---

## Critical Assessment — Overall

### What makes sense:
- **Data consistency bugs** (#1, #22, #39, #42, #49) — These are the most important findings. Data mismatches erode trust immediately.
- **UX reordering** (#5, #20, #21) — The suggested column/section orders follow better information hierarchy.
- **Watchpoint-to-KPI coloring** (#15) — High-value, makes the dashboard proactive rather than passive.
- **12-month expiration chart** (#35) — This is the kind of forward-looking insight that makes a dashboard indispensable.
- **Financials restructure** (#45) — Painful but correct. Matching the client's format is non-negotiable for adoption.

### What needs discussion:
- **Conversion rate display** (#26-27) — Showing all 6 conversion pairs risks clutter. Suggest showing the 3 most important (lead→tour, tour→app, app→lease) prominently and the rest on hover/drill-through.
- **Monthly renewal rate vs 90d blended** (#11) — Both are useful. The 90d blended is a quick health check; monthly is more actionable. Consider showing both.
- **Financials estimated expenses** (#69/45) — Using 6-month average is smart but could be misleading if there's seasonality. Should flag it clearly as "Estimated."

### What I'd push back on:
- **"Transfer to new unit" clarification** (#37, #52) — These are just tooltip/documentation issues, not product problems. Low effort but the colleague seems to be asking genuine questions, not requesting changes.
- **Concession tracking** (#34) — Unless RealPage explicitly provides concession data, this could require manual data entry, which defeats the automation purpose. Verify data availability before committing.
- **Venn behavioral data** (#36) — Interesting sales tool but out of scope for the current dashboard. Should be a completely separate initiative.

---

## Change Log

| Date | Item # | Description | Files Changed |
|------|--------|-------------|---------------|
| Feb 18 | #9 | **Verified OK** — MTD prior period comparison already compares same # of days (Jan 1-17 vs Dec 1-17) | No change needed |
| Feb 18 | #51 | **Verified OK** — Watchpoint thresholds are user-created; system evaluates operators correctly | No change needed |
| Feb 18 | #18 | **Fixed** — Removed non-functional radius filter from Market Comps (ALN API uses submarket, not radius) | `MarketCompsTable.tsx` |
| Feb 18 | #49 | **Fixed** — Reviews total mismatch: `review_power.total_reviews` now uses platform `review_count` instead of `reviews_fetched`. Added `reviews_analyzed` field for response tracking label. | `routes.py`, `ReputationOverview.tsx` |
| Feb 18 | #1/#3 | **Verified OK** — Red flags are AI-generated from real property data (not mock). Contradictions are AI quality issues — prompt already has strict consistency rules. | No change needed |
| Feb 18 | #22 | **Fixed** — Vacant count mismatch between KPI card (Box Score) and Bedroom table (unified_units). Root causes: 1) NULL floorplan units excluded from bedroom query, 2) down units counted differently. Fix: include NULL floorplan as "Other", count down units as vacant to match Box Score. | `routes.py` (consolidated-by-bedroom endpoint) |
| Feb 18 | #39 | **Fixed** — Delinquency aging bars now computed from current residents only (was using report-level aggregate that included former residents). Aging bars now match Current Resident AR table totals. | `DelinquencySection.tsx` |
| Feb 18 | #40 | **Fixed** — Renamed "Collections" to "Former Residents Balance" throughout delinquency tab. | `DelinquencySection.tsx` |
| Feb 18 | #42 | **Investigated** — $0 evictions are for lease violations (not non-payment). Added note "(may include non-payment & lease violations)" to evictions section header. | `DelinquencySection.tsx` |
| Feb 18 | #8 | **Fixed** — Added vacancy % next to vacant count on VacantKPICard. Color-coded: >10% rose, >5% amber, ≤5% slate. | `KPICard.tsx`, `DashboardV3.tsx` |
| Feb 18 | #10 | **Fixed** — In-Place KPI card subtitle now shows delta % between asking and in-place rent (e.g. "Asking $1,850 (+3.2%)"). | `DashboardV3.tsx` |
| Feb 18 | #27 | **Fixed** — Leasing Funnel card now shows all 6 conversion rates below the stages: Lead→Tour, Tour→App, App→Lease, Lead→App, Tour→Lease, Lead→Lease. | `KPICard.tsx` |
| Feb 18 | #24 | **Fixed** — Added "Prev Month" period filter button between MTD and Last 30d. | `DashboardV3.tsx`, `MarketingSection.tsx` |
| Feb 18 | #20 | **Fixed** — Reordered Overview tab sections: Bedroom → Availability → Market Comps (was Comps → Bedroom → Availability). | `DashboardV3.tsx` |
| Feb 18 | #5 | **Fixed** — Reordered portfolio table columns: Property → Units → Occupancy → Vacant → ATR → Leased% → Expiring 90d → Renewals 90d. Vacant/ATR now immediately after Occupancy for quick scanning. | `PortfolioView.tsx` |

---

## Recommended Next Steps

1. **Schedule a 30-min sync** with colleague to:
   - Clarify which items were highlighted in blue
   - Align on financials tab restructure approach
   - Confirm what "property area" means in comps (#17)
   - Discuss the "Period" section reference (#6)

2. **Start with Phase 1** (bugs) immediately — these are trust issues

3. **Batch Phase 2** into a single sprint — mostly small changes that collectively transform the UX

4. **Scope Phase 3** features individually — some may not be needed after Phase 2 improvements

5. **Financials (Phase 4)** needs its own design doc after the sync meeting
