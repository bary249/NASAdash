OwnerDashV2 — Data Fields & Sources Disclosure

Prepared for: Venn Legal Counsel
Date: February 17, 2026
Prepared by: Barak B., Product & Engineering


================================================================================
1. EXECUTIVE SUMMARY
================================================================================

OwnerDashV2 is a read-only portfolio analytics dashboard for multifamily property owners. It displays operational metrics (occupancy, pricing, leasing, financials, maintenance, reviews) sourced from property management systems (PMS) and public review platforms.

THE PLATFORM NEVER DISPLAYS PERSONALLY IDENTIFIABLE INFORMATION (PII). No resident names, contact details, Social Security numbers, or any other personally identifying data are shown in the user interface, exported, or returned by any API endpoint consumed by the frontend.

All data displayed is aggregate or unit-level (identified by unit number only, e.g. "Unit 204"), never resident-level.


================================================================================
2. ARCHITECTURE & DATA FLOW
================================================================================

The system follows a three-tier architecture:

Layer 1 — Data Ingestion (ETL Pipeline)
    Sources: RealPage PMS (reports + SOAP API), Snowflake DWH, Google Maps, Apartments.com
    Schedule: Automated every 6 hours via GitHub Actions
    Output: All data is normalized and stored in a single SQLite database (unified.db)

Layer 2 — Backend API (FastAPI)
    Reads exclusively from unified.db
    All endpoints are GET-only (read). No PUT, POST, DELETE, or any mutation of external PMS data
    The backend never calls live PMS APIs at request time
    Hosted on Railway (persistent volume for database)

Layer 3 — Frontend (React SPA)
    Displays data fetched from the backend API
    Hosted on Netlify (static files only)

Authentication: JWT tokens with bcrypt-hashed passwords. Users are scoped to their owner group and cannot access other groups' data.


================================================================================
3. DATA SOURCES
================================================================================

Source: RealPage
    Type: Property Management System (PMS)
    What We Pull: Reports (Excel/CSV), SOAP API unit & lease data
    How: Automated report download via RealPage Reporting API (read-only credentials)

Source: Snowflake DWH
    Type: Data Warehouse
    What We Pull: Resident risk scoring model outputs (aggregate scores only)
    How: SQL query to CSV export, then synced to unified.db

Source: Google Maps
    Type: Public Reviews
    What We Pull: Star rating, review count, review text, management responses
    How: Playwright browser scraper reading public Google Maps pages

Source: Apartments.com
    Type: Public Reviews
    What We Pull: Star rating, review count, review text, management responses
    How: Zembra API (third-party review aggregator)


================================================================================
4. COMPLETE FIELD INVENTORY BY DASHBOARD SECTION
================================================================================


4.1 Portfolio Overview (Landing Page)
--------------------------------------

Property Name — Display name of community
    Source: unified_properties table | Origin: RealPage property config

Owner Group — Ownership entity (e.g. "Kairoi", "PHH")
    Source: unified_properties table | Origin: Manual configuration

PMS Type — Property management system type
    Source: unified_properties table | Origin: Manual configuration

Total Units — Total unit count
    Source: unified_occupancy_metrics table | Origin: RealPage Box Score Report

Occupied Units — Number of occupied units
    Source: unified_occupancy_metrics table | Origin: RealPage Box Score Report

Vacant Units — Number of vacant units
    Source: unified_occupancy_metrics table | Origin: RealPage Box Score Report

Physical Occupancy % — Occupied divided by Total times 100
    Source: unified_occupancy_metrics table | Origin: Calculated from Box Score

Leased % — (Occupied + Pre-leased) divided by Total times 100
    Source: unified_occupancy_metrics table | Origin: Calculated from Box Score


4.2 KPI Cards (Top of Property Dashboard)
-------------------------------------------

Occupancy % — Physical occupancy rate
    Source: unified_occupancy_metrics table | Origin: RealPage Box Score (Report 3501)

In-Place Rent — Weighted average rent of occupied units
    Source: unified_pricing_metrics table | Origin: RealPage Rent Roll

Asking Rent — Weighted average market rent
    Source: unified_pricing_metrics table | Origin: RealPage Rent Roll

Renewal Rate (90d) — Percentage of leases expiring in 90 days that are renewed
    Source: unified_lease_expirations / unified_leases tables | Origin: RealPage Report 4156

Trade-Outs — Average new rent vs prior tenant's rent on same unit
    Source: unified_units + unified_leases tables | Origin: RealPage Rent Roll + Lease data

Vacant (total / ready / aged) — Vacancy breakdown
    Source: unified_occupancy_metrics table | Origin: RealPage Box Score

ATR (Actual-to-Rent) — Vacant + On Notice minus Pre-leased
    Source: unified_units table | Origin: Calculated from Box Score data

Leads — Unique prospect contacts in period
    Source: unified_activity table | Origin: RealPage Activity Report

Tours — Unique prospects with visit events
    Source: unified_activity table | Origin: RealPage Activity Report

Applications — Unique prospects at application stage
    Source: unified_activity table | Origin: RealPage Activity Report

Leases Signed — Unique prospects with "Leased" status
    Source: unified_activity table | Origin: RealPage Activity Report

Renewals (count + avg rent) — Renewal lease details
    Source: unified_lease_expirations table | Origin: RealPage Report 4156


4.3 Overview Tab
-----------------

MARKET COMPS:

Comp Property Name — Nearby competitor property name
    Source: market_comps table | Origin: ALN API (public market data)

Comp Distance — Miles from subject property
    Source: market_comps table | Origin: ALN API

Comp Occupancy % — Competitor occupancy
    Source: market_comps table | Origin: ALN API

Comp Avg Rent — Competitor average rent
    Source: market_comps table | Origin: ALN API

Comp Year Built — Competitor year built
    Source: market_comps table | Origin: ALN API

CONSOLIDATED BY BEDROOM:

Bedroom Type — Studio, 1BR, 2BR, 3BR+
    Source: unified_units table | Origin: RealPage Rent Roll

Total / Occupied / Vacant per type — Unit counts by bedroom
    Source: unified_units table | Origin: RealPage Rent Roll

Avg Market Rent per type — Average asking rent
    Source: unified_units table | Origin: RealPage Rent Roll

Avg In-Place Rent per type — Average actual rent
    Source: unified_units table | Origin: RealPage Rent Roll

Expiring / Renewed (90d) per type — Renewal metrics by bedroom
    Source: unified_units + unified_leases tables | Origin: RealPage Lease data

AVAILABILITY & ATR:

ATR / Vacant / On Notice / Pre-leased — Unit count buckets
    Source: unified_units table | Origin: RealPage Box Score + Rent Roll

Availability Buckets (0-30d, 30-60d, 60+d) — Units available by timeframe
    Source: unified_units table | Origin: Calculated from available_date

7-Week ATR Trend — ATR over trailing 7 weeks
    Source: unified_projected_occupancy table | Origin: RealPage Report 3842

OCCUPANCY TREND:

Historical occupancy snapshots — Weekly/monthly occupancy over time
    Source: unified_occupancy_metrics table | Origin: RealPage Box Score (multiple snapshots)

UNIT MIX & PRICING:

Floorplan Name — Unit type identifier (e.g. "A1", "B2")
    Source: unified_pricing_metrics table | Origin: RealPage Rent Roll

Unit Count per floorplan — Number of units
    Source: unified_pricing_metrics table | Origin: RealPage Rent Roll

Bedrooms / Bathrooms — Bed/bath count
    Source: unified_pricing_metrics table | Origin: RealPage Rent Roll

Avg Square Feet — Average unit size
    Source: unified_pricing_metrics table | Origin: RealPage Rent Roll

In-Place Rent / per SF — Actual rent and per-sqft rate
    Source: unified_pricing_metrics table | Origin: RealPage Rent Roll

Asking Rent / per SF — Market rent and per-sqft rate
    Source: unified_pricing_metrics table | Origin: RealPage Rent Roll

Rent Growth % — (Asking divided by In-Place) minus 1
    Source: unified_pricing_metrics table | Origin: Calculated


4.4 Leasing Tab
----------------

Leads / Tours / Applications / Leases — Funnel counts (deduplicated by prospect)
    Source: unified_activity table | Origin: RealPage Activity Report

Tour to Application count — Prospects who toured AND applied
    Source: unified_activity table | Origin: RealPage Activity Report

Apps without Tour — Sight-unseen applications
    Source: unified_activity table | Origin: RealPage Activity Report

Lead to Lease conversion % — Overall conversion rate
    Source: unified_activity table | Origin: Calculated

Marketing Net Leases — Net leases by advertising source
    Source: unified_marketing table | Origin: RealPage Report 4158

LEAD SOURCES:

Source Name — Advertising channel (e.g. "Apartments.com")
    Source: unified_marketing table | Origin: RealPage Advertising Source Report

Prospects / Calls / Visits / Leases per source — Funnel by channel
    Source: unified_marketing table | Origin: RealPage Advertising Source Report

Cost per Lead / Cost per Lease — Marketing efficiency
    Source: unified_marketing table | Origin: RealPage Advertising Source Report

AVAILABLE UNITS BY FLOORPLAN:

Floorplan / Total / Vacant / Notice / Leased / Not Leased — Availability grid
    Source: unified_units table | Origin: RealPage Box Score + Rent Roll

Market Rent / Occupancy % per floorplan — Pricing by floorplan
    Source: unified_units table | Origin: RealPage Rent Roll

OCCUPANCY FORECAST:

Week # / Week Start-End — 12-week projection timeline
    Source: unified_projected_occupancy table | Origin: RealPage Report 3842

Projected Occupied / Occ % — Forecasted occupancy
    Source: unified_projected_occupancy table | Origin: RealPage Report 3842

Scheduled Move-Ins — Expected move-ins per week
    Source: unified_projected_occupancy + unified_units tables | Origin: RealPage Report 3842 + Rent Roll

Notice Move-Outs — NTV move-outs per week
    Source: unified_units table | Origin: RealPage Rent Roll

Net Change — Move-ins minus Move-outs
    Source: Calculated

Lease Expirations / Renewals per week — Leases expiring and renewed
    Source: unified_leases table | Origin: RealPage Lease data


4.5 Rentable Items Tab
-----------------------

Unit Number — Unit identifier (e.g. "204")
    Source: unified_units table | Origin: RealPage Rent Roll

Floorplan — Unit type
    Source: unified_units table | Origin: RealPage Rent Roll

Status — Occupied / Vacant / Notice / Down
    Source: unified_units table | Origin: RealPage Rent Roll

Square Feet — Unit size
    Source: unified_units table | Origin: RealPage Rent Roll

Market Rent — Asking rent
    Source: unified_units table | Origin: RealPage Rent Roll

Actual Rent — Current lease rent
    Source: unified_units table | Origin: RealPage Rent Roll

Lease Start / End — Lease dates
    Source: unified_units table | Origin: RealPage Rent Roll + Lease Details

Days Vacant — Days since last move-out
    Source: unified_units table | Origin: Calculated from lease details move-out date

Is Pre-leased — Whether vacant unit has a signed lease
    Source: unified_units table | Origin: RealPage Rent Roll


4.6 Renewals Tab
-----------------

Expiring (30d / 60d / 90d) — Lease count expiring per window
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

Renewed count — Leases with "Renewed" decision
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

Vacating count — Leases with "Vacating" decision
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

Pending count — Leases with no decision yet
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

MTM count — Month-to-month conversions
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

Moved Out count — Already departed
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

Renewal Rate % — Renewed divided by Total expiring
    Source: Calculated

DRILL-THROUGH FIELDS:

Unit Number — Unit identifier
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

Floorplan — Unit type
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

Actual Rent — Current lease rent
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

Lease End Date — Expiration date
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

Decision — Renewed / Vacating / Unknown / MTM / Moved out
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

New Rent (if renewed) — Renewal lease rent
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

New Lease Term (if renewed) — Renewal term length
    Source: unified_lease_expirations table | Origin: RealPage Report 4156

MOVE-OUT REASONS:

Reason — Reason for departure (e.g. "Job Transfer")
    Source: unified_move_out_reasons table | Origin: RealPage Move-Out Reasons Report

Count — Number of move-outs per reason
    Source: unified_move_out_reasons table | Origin: RealPage Move-Out Reasons Report


4.7 Delinquencies Tab
-----------------------

Total Delinquent $ — Sum of all current-resident delinquency
    Source: unified_delinquency table | Origin: RealPage Report 4009

Total Prepaid $ — Sum of resident prepayments
    Source: unified_delinquency table | Origin: RealPage Report 4009

Net Balance $ — Delinquent minus Prepaid
    Source: unified_delinquency table | Origin: RealPage Report 4009

Current Resident Total / Count — Delinquency for current residents
    Source: unified_delinquency table | Origin: RealPage Report 4009

Former Resident Total / Count — Collections for former residents
    Source: unified_delinquency table | Origin: RealPage Report 4009

AGING BUCKETS:

Current — Charges in current billing period
    Source: unified_delinquency table | Origin: RealPage Report 4009

0-30 Days — 0-30 day past due
    Source: unified_delinquency table | Origin: RealPage Report 4009

31-60 Days — 31-60 day past due
    Source: unified_delinquency table | Origin: RealPage Report 4009

61-90 Days — 61-90 day past due
    Source: unified_delinquency table | Origin: RealPage Report 4009

90+ Days — Over 90 days past due
    Source: unified_delinquency table | Origin: RealPage Report 4009

EVICTIONS:

Eviction Unit Count — Units with eviction flag
    Source: unified_delinquency table | Origin: RealPage RPX SOAP API (eviction flag)

Eviction Total Balance — Total owed by eviction units
    Source: unified_delinquency table | Origin: RealPage Report 4009 + SOAP API

DRILL-THROUGH FIELDS:

Unit Number — Unit identifier (e.g. "204")
    Source: unified_delinquency table | Origin: RealPage Report 4009

Status — Current / Former / Eviction
    Source: unified_delinquency table | Origin: RealPage Report 4009

Total Delinquent per unit — Amount owed
    Source: unified_delinquency table | Origin: RealPage Report 4009

Aging breakdown per unit — Per-bucket amounts
    Source: unified_delinquency table | Origin: RealPage Report 4009


4.8 Financials Tab
-------------------

Fiscal Period — Accounting month (e.g. "022026")
    Source: unified_financial_summary table | Origin: RealPage Report 4020

Gross Market Rent — Total market rent potential
    Source: unified_financial_summary table | Origin: RealPage Report 4020

Gain / Loss to Lease — Difference from market rent
    Source: unified_financial_summary table | Origin: RealPage Report 4020; enriched by Lost Rent Report (4279)

Gross Potential — Market rent plus/minus gain/loss to lease
    Source: unified_financial_summary table | Origin: RealPage Report 4020

Total Other Charges — Non-rent charges (fees, utilities)
    Source: unified_financial_summary table | Origin: RealPage Report 4020

Total Possible Collections — Gross potential + other charges
    Source: unified_financial_summary table | Origin: RealPage Report 4020

Collection Losses — Vacancies, concessions, bad debt
    Source: unified_financial_summary table | Origin: RealPage Report 4020

Current / Total Monthly Collections — Cash collected
    Source: unified_financial_summary table | Origin: RealPage Report 4020

Collection Rate % — Collections divided by Possible times 100
    Source: Calculated

COMPUTED METRICS:

Economic Occupancy % — Collections divided by Possible collections
    Source: Calculated from Report 4020

Revenue per Occupied Unit — Collections divided by Occupied units
    Source: Report 4020 + Box Score

Loss-to-Lease % — Loss-to-Lease divided by Gross Market Rent
    Source: Report 4020 / Report 4279

Concession $ / % — Total concessions and % of gross potential
    Source: unified_financial_detail table | Origin: RealPage Report 4020

Bad Debt $ / % — Write-offs and % of gross potential
    Source: unified_financial_detail table | Origin: RealPage Report 4020

Vacancy Loss $ / % — Revenue lost to vacancy
    Source: unified_financial_detail table | Origin: RealPage Report 4020 / Report 4279

Other Income / per unit — Non-rent revenue
    Source: unified_financial_detail table | Origin: RealPage Report 4020

TRANSACTION DETAIL:

Transaction Group — Category (Rent, Late Fees, Utilities, etc.)
    Source: unified_financial_detail table | Origin: RealPage Report 4020

Transaction Code — Accounting code
    Source: unified_financial_detail table | Origin: RealPage Report 4020

Description — Line item description
    Source: unified_financial_detail table | Origin: RealPage Report 4020

This Month / YTD amounts — Dollar amounts
    Source: unified_financial_detail table | Origin: RealPage Report 4020


4.9 Maintenance Tab
--------------------

PIPELINE (OPEN MAKE-READY):

Unit Number — Unit identifier
    Source: unified_maintenance table | Origin: RealPage Make Ready Summary (Report 4186)

Square Feet — Unit size
    Source: unified_maintenance table | Origin: RealPage Report 4186

Days Vacant — Days since vacated
    Source: unified_maintenance table | Origin: RealPage Report 4186

Date Vacated — Move-out date
    Source: unified_maintenance table | Origin: RealPage Report 4186

Date Due — Target ready date
    Source: unified_maintenance table | Origin: RealPage Report 4186

Work Order Count — Number of open work orders
    Source: unified_maintenance table | Origin: RealPage Report 4186

Unit Status / Lease Status — Current unit state
    Source: unified_units table | Origin: RealPage Rent Roll

COMPLETED TURNS:

Unit Number — Unit identifier
    Source: unified_maintenance table | Origin: RealPage Report 4189

Work Order Count — Completed work orders
    Source: unified_maintenance table | Origin: RealPage Report 4189

Date Closed — Completion date
    Source: unified_maintenance table | Origin: RealPage Report 4189

Amount Charged — Turn cost
    Source: unified_maintenance table | Origin: RealPage Report 4189

SUMMARY STATS:

Units in Pipeline — Count of open make-readies
    Source: Calculated from Report 4186

Avg Days Vacant — Average turn time
    Source: Calculated from Report 4186

Overdue Count — Units vacant > 14 days
    Source: Calculated from Report 4186


4.10 Risk Scores Tab
---------------------

Total Scored — Number of residents scored
    Source: unified_risk_scores table | Origin: Snowflake DWH scoring engine

Avg Churn Score — 0-1 scale (0 = high risk, 1 = healthy)
    Source: unified_risk_scores table | Origin: Snowflake DWH scoring engine

Avg Delinquency Score — 0-1 scale (0 = high risk, 1 = healthy)
    Source: unified_risk_scores table | Origin: Snowflake DWH scoring engine

High / Medium / Low risk counts — Buckets: below 0.3, 0.3-0.6, above 0.6
    Source: unified_risk_scores table | Origin: Snowflake DWH scoring engine

CONTRIBUTING FACTORS:

% Scheduled Move-out — Residents with upcoming move-out
    Source: unified_risk_scores table | Origin: Snowflake DWH

% With App — Residents using resident app
    Source: unified_risk_scores table | Origin: Snowflake DWH

Avg Tenure (months) — Average length of residency
    Source: unified_risk_scores table | Origin: Snowflake DWH

Avg Rent — Average rent of scored residents
    Source: unified_risk_scores table | Origin: Snowflake DWH

Avg Open Tickets — Average open maintenance tickets
    Source: unified_risk_scores table | Origin: Snowflake DWH

IMPORTANT: Risk scores are property-level aggregates only. No individual resident scores are displayed. The scoring engine runs on anonymized cohort data.


4.11 Reviews Tab
-----------------

REPUTATION OVERVIEW:

Overall Rating — Weighted average across all sources
    Source: Calculated | Origin: Google + Apartments.com

Source Ratings — Per-platform star rating
    Source: Cache files | Origin: Google Maps (public), Apartments.com (Zembra API)

Review Count per source — Number of reviews
    Source: Cache files | Origin: Google Maps, Apartments.com

Response Rate % — Percentage of reviews with management reply
    Source: Cache files | Origin: Parsed from public review pages

Needs Attention count — Reviews without a response
    Source: Cache files | Origin: Parsed from public review pages

REVIEW CARDS:

Reviewer Name — Public display name on review platform
    Source: Cache files | Origin: Google Maps (public), Apartments.com (public)

Star Rating — 1-5 stars
    Source: Cache files | Origin: Public review platforms

Review Text — Review body content
    Source: Cache files | Origin: Public review platforms

Review Date — Date posted
    Source: Cache files | Origin: Public review platforms

Management Response — Property's public reply
    Source: Cache files | Origin: Public review platforms

Star Distribution — Count of 1/2/3/4/5-star reviews
    Source: Cache files | Origin: Public review platforms

NOTE: Reviewer names shown in the Reviews tab are publicly posted usernames from Google Maps and Apartments.com. These are public information visible to anyone browsing these platforms. They are not sourced from any PMS or private resident data.


4.12 Watch List Tab
--------------------

Property Name — Community name
    Source: unified_properties table | Origin: Configuration

Occupancy % — Current physical occupancy
    Source: unified_occupancy_metrics table | Origin: RealPage Box Score

Delinquent $ — Total current-resident delinquency
    Source: unified_delinquency table | Origin: RealPage Report 4009

Renewal Rate (90d) — Percentage renewed in 90-day window
    Source: unified_lease_expirations / unified_leases tables | Origin: RealPage Lease data

Google Rating — Star rating from Google Maps
    Source: Cache file | Origin: Google Maps (public)

Flags — Metrics exceeding configurable thresholds
    Source: Calculated | Origin: All above sources


4.13 Watchpoints Tab
---------------------

Metric Name — User-selected KPI to monitor
    Source: User-defined | Origin: User configuration

Operator / Threshold — Comparison rule (e.g. "< 85%")
    Source: User-defined | Origin: User configuration

Current Value — Live metric value
    Source: Various unified tables | Origin: RealPage / calculated

Status — Triggered / OK
    Source: Calculated | Origin: Comparison result


4.14 AI Chat & Insights
-------------------------

AI-generated red flags — Automated alerts about property issues
    Source: All unified tables | Origin: Claude AI analysis of aggregate property data

Chat responses — Natural language answers to user questions
    Source: All unified tables | Origin: Claude AI with property context

The AI receives only aggregate/unit-level data as context — never resident names or PII. AI prompts are explicitly instructed not to reference or generate PII.


================================================================================
5. PII PROTECTION — COMPREHENSIVE STATEMENT
================================================================================


5.1 What Is NOT Displayed
---------------------------

The following data points exist in the raw PMS data but are NEVER displayed in the dashboard UI, never returned by frontend-facing API endpoints, and never included in any export:

    - Resident names (first name, last name, full name)
    - Phone numbers
    - Email addresses
    - Social Security numbers (not collected at all)
    - Date of birth (not collected at all)
    - Bank account / payment details (not collected at all)
    - Government-issued ID numbers (not collected at all)


5.2 Architectural Enforcement
-------------------------------

PII protection is enforced at multiple layers:

1. Database Schema: The unified_delinquency table stores unit_number as the identifier. While resident_name exists in the raw import table for deduplication during ETL, the API endpoint does not return it to the frontend.

2. API Response Filtering: Delinquency drill-through data returns only:
    - Unit number (e.g. "204")
    - Status (Current / Former)
    - Total delinquent, net balance (dollar amounts)
    - Aging buckets (dollar amounts)
    - Eviction flag (boolean)
    Resident names are explicitly excluded from the response payload.

3. Leasing Funnel: Prospect counting uses name-based deduplication in the database query, but names are never returned in API responses. The frontend sees only aggregate counts (e.g. "14 leads", "6 tours").

4. Lease Expiration Drill-Through: Returns unit-level data only:
    - Unit number, floorplan, square feet
    - Lease dates, rent amounts, renewal decision
    - No resident names

5. Risk Scores: Only property-level aggregates are stored and displayed. No individual resident risk scores are exposed. The scoring engine output is aggregated before being synced to the dashboard database.

6. Maintenance Pipeline: Shows unit numbers and work order counts. No resident identifiers.

7. AI Chat Context: Property data sent to the AI model contains occupancy metrics, pricing, unit statuses, and aggregate statistics. Resident names are not included in AI context.


5.3 Public Review Data
------------------------

The only "names" shown anywhere in the dashboard are public reviewer usernames from Google Maps and Apartments.com. These are:
    - Publicly visible to anyone on the internet
    - Published voluntarily by the reviewers themselves
    - Not sourced from PMS resident records
    - Not cross-referenced with any internal resident data


================================================================================
6. DATA RETENTION & ACCESS CONTROL
================================================================================

Data refresh cycle: Every 6 hours via automated pipeline (GitHub Actions).

Data age: Dashboard shows the most recent snapshot; historical snapshots retained for trend analysis.

Access control: JWT-based authentication. Each user is locked to their owner group (e.g., "PHH" users can only see PHH properties).

No data export feature: The dashboard is view-only with no CSV/Excel export functionality.

No external data sharing: Data is not shared with third parties. The AI chat feature sends property metrics to Anthropic's Claude API for analysis, but this contains only aggregate operational data — no PII.


================================================================================
7. THIRD-PARTY SERVICES
================================================================================

RealPage — Source PMS
    Data Sent: Read-only API credentials
    PII Risk: N/A (data source, not destination)

Railway — Backend hosting
    Data Sent: Entire unified.db (operational data)
    PII Risk: No PII in served responses

Netlify — Frontend hosting
    Data Sent: Static React app (no data)
    PII Risk: None

Anthropic (Claude) — AI chat and insights
    Data Sent: Aggregate property metrics
    PII Risk: No PII sent

Zembra — Apartments.com reviews
    Data Sent: Property slug/name
    PII Risk: No PII — public review data only

Google Maps — Public reviews
    Data Sent: Property name search
    PII Risk: No PII — public page scraping

Snowflake — Risk score source
    Data Sent: Read-only query
    PII Risk: Aggregated before export — no PII in dashboard


================================================================================
8. REALPAGE REPORTS USED
================================================================================

Report 3501 — Box Score
    Data Extracted: Unit counts, occupancy %, vacancy breakdown

Report 3842 — Projected Occupancy
    Data Extracted: 12-week occupancy forecast (move-in/out counts)

Report 4009 — Delinquent & Prepaid
    Data Extracted: Per-unit delinquency aging, prepaid, eviction status

Report 4020 — Monthly Transaction Summary
    Data Extracted: P&L summary, transaction detail by category

Report 4048 — Lease Details
    Data Extracted: Lease dates, floorplan matching

Report 4156 — Lease Expiration Renewal Detail
    Data Extracted: Expiring leases, renewal decisions, new rent

Report 4158 — Primary Advertising Source
    Data Extracted: Marketing funnel by ad source

Report 4186 — Make Ready Summary
    Data Extracted: Open make-ready pipeline, days vacant

Report 4189 — Closed Make Ready Summary
    Data Extracted: Completed turns, costs

Report 4279 — Lost Rent Summary
    Data Extracted: Unit-level market vs lease rent, loss-to-lease


================================================================================

This document reflects the system as of February 17, 2026. For questions, contact Barak B.
