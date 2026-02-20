# Dashboard Review — Our Response

**Responding to**: Comments on Dashboard.docx
**Date**: 2026-02-20

---

## Portfolio Overview Tab

**2a. Total leased %** → Will add to metrics section. Data already available from box score.

**2b. Conversion ratios** → Will simplify to 4: Lead→Lease, Lead→Tour, Tour→App, App→Lease. Removing the others.

**3a. Blended rate** → ✅ Already implemented. Blended card shows weighted avg of renewals + trade outs.

**3b. Weighted avg vs Row matrix** → Will add a tooltip explaining: "Weighted Avg" averages across all properties weighted by unit count; "Row Metrics" shows each property's own calculated values. Will make labels clearer.

**5. Bedroom consolidated — Market vs Asking** → Will rename "Market" → "Asking" and swap column order so Asking comes before In-Place.

**6. Unit type toggle** → Will add a toggle to switch between unit type view (Studio, 1BR, 2BR, 3BR) and full rent roll. Applies to both Unit Mix & Pricing and Available Units by Floorplan.

---

## Leasing Tab

**1. Move Availability/ATR + Market Comps to Leasing** → Let's discuss. Pro: unloads Overview. Con: ATR is a core KPI that owners want front-and-center. Possible compromise: keep ATR number on Overview but move the detailed breakdown to Leasing.

**2a. Conversion ratios below bars** → Will add.

**3a. Lead sources total row** → Will add.

**3b. "Previous month" date range bug** → Confirmed bug. When switching to "Previous Month", the date range shows 1/1–2/19 (which is YTD). Will fix to show only the prior calendar month.

**4a. Restructure Available Units by Floorplan** → Will restructure columns to: Floorplan, Units, Available, Vacant, Pre-leased, NTV, In-Place Rent, Asking Rent, % Available bar. Dropping occupancy column (as suggested — we show vacant count anyway).

**4b. Unit type toggle** → Shared with PO-6 above.

**4c. Bottom line misaligned** → Will fix alignment.

**5a. Pre-leased / On Notice buttons** → These filter the forecast to show only the impact of preleased or notice units on future occupancy. Will add tooltips explaining this, or remove if not useful.

**5b. Forecast sub-headers** → Will add: "Net Move In" above (Move Ins, Notice Out, Proj NTV, Net) and "Expirations & Renewals" above (Exp, Renewal, Rnw%, Next Exp).

**5c. Proj. NTV drill-through** → This should already be linked. Will verify and fix if broken.

**5d. "Notice Out" → "Move Out"** → Will rename. These are confirmed move-outs so "Move Out" is clearer.

---

## Renewal Tab

**6a. Monthly tiles — limit to 4 months** → Will cap at 4 months ahead since the graph below covers the full timeline.

**6b. Period filter for Avg Renewal/Prior/Variance** → Currently hardcoded to MTD. Will add a filter matching the leasing funnel timeframes (MTD, L30, Prior Month, YTD).

**6c. "Vacating" → "NTV"** → Will rename on graph.

**7. Concession flag on renewals** → Need to investigate data source. RealPage Concessions Report (3889) returns empty for most properties. May need to derive from lease rent vs market rent delta. Will report back.

**8. Renewal forecast + behavioral insights** → Noted as future phase. Will add a greyed-out placeholder section that references Venn's behavioral scoring. Good sales tool.

**9a. "Transfer to new unit"** → This comes from RealPage move-out reason codes. "Transfer" typically means within the same property or portfolio (internal transfer). Will verify with RealPage data dictionary and add clarification in the UI.

**9b. "Non-renewal" under eviction** → In RealPage, this is a PM decision not to renew the lease (distinct from eviction filing). Will verify and add clarifying label.

**10. Yardi "Selected" status** → This is a Yardi-specific status. Our RealPage equivalent is "Current - Future" (lease signed but not yet started). These show as "Renewed" in our renewal tracking. Will document the mapping.

---

## Delinquencies Tab

**1. Aging vs AR discrepancy** → **Known issue being investigated.** The RealPage delinquency report's aging bucket sums don't always equal the `total_delinquent` column (due to late fees, utility charges, and other non-rent items that aren't broken into aging buckets). We use `total_delinquent` as the authoritative number. Will add a note in the UI explaining the source of discrepancy, and add a data validation test.

**2a. Move Eviction next to Delinquent** → Will restructure: Total Delinquent | Active Evictions side by side. Pre-paid moved to secondary position.

**3. Evictions with $0 / $60 balance** → Investigating. Possible explanations: (a) eviction filed before balance accrued (notice period), (b) balance was paid after eviction filing, (c) eviction for lease violations (not non-payment). Will add eviction reason if available in data.

**3a. Eviction reason** → Need to check if RealPage provides this. Lease Details report has `MoveOutNoticeType` and `moutName` which may contain reason codes.

**3b. Eviction filing date + days under eviction** → Need to check data availability. May require additional report or API field.

---

## Financials Tab

**4. Full restructure** → Waiting for your financial format to ensure we build to spec. Key decisions needed:
- Which expense categories to show by default?
- Budget data source — is this in RealPage or a separate upload?
- KPI factors placement (above or beside the P&L?)

**4a. Actual vs Budget** → Ready to build once format received.

**4b. KPI factors** → Can add physical/economic occupancy, delinquency rate, etc. above the P&L.

**4c. Below-the-line expenses** → Noted as next phase.

**4d. Bottom 3 boxes** → Will convert to drill-through from line items instead of always-visible.

**4e. Discussion** → Let's schedule.

---

## Maintenance

**a. Remove from PHH** → Will hide Maintenance tab when logged in as PHH. Already have user-group-based tab filtering.

---

## Watchpoints

**a. Occ < 90%** → Will fix. Current threshold was inverted.

**b. ATR >40 vs >50** → Will simplify to single threshold (>40 = warning, or make it configurable).

**c. Google rating** → Will implement: flag individual new reviews < 5 stars + alert if overall avg drops below configurable threshold (default 4.0).

**d. Placeholders** → Acknowledged. Will build out as data sources become available.

---

## AI Questions

**Broken questions** → Will investigate each. Most likely cause: the AI doesn't have access to lead source breakdown data (apt.com, zillow) in the prompt context. Need to add marketing/lead source data to the AI context.

**Decision workflow format** → Great feedback. Will update the AI system prompt to follow: **Observation → Diagnosis → Financial Impact → Recommended Action** for every answer.

**10 categories** → Will map each category against our current data sources and identify gaps. Categories 1, 2, 5, 6 have good data coverage. Categories 3, 4, 7, 8, 9 need additional data sources or are future phase.
