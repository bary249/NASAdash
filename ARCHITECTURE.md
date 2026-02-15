# OwnerDashV2 Architecture Documentation

**Version**: 3.0  
**Last Updated**: 2026-02-15  
**Status**: Production (Railway + Netlify)

---

## Table of Contents

1. [System Overview](#system-overview)
2. [Deployment Architecture](#deployment-architecture)
3. [Automated Data Pipeline](#automated-data-pipeline)
4. [Data Sources](#data-sources)
5. [Database Schema](#database-schema)
6. [API Endpoints](#api-endpoints)
7. [Authentication](#authentication)
8. [Frontend](#frontend)
9. [Monitoring & Smoke Tests](#monitoring--smoke-tests)
10. [Property Configuration](#property-configuration)
11. [Field Coverage by Module](#field-coverage-by-module)
12. [File Structure](#file-structure)
13. [Future: Financials Section](#future-financials-section)

---

## System Overview

OwnerDashV2 is a **READ-ONLY** property management dashboard that aggregates data from multiple sources into a unified view for property owners.

### Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                            EXTERNAL DATA SOURCES                                 │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌────────┐ ┌────────────┐ │
│  │ RealPage RPX │ │ RealPage     │ │ Yardi SOAP   │ │Google  │ │ Apartments │ │
│  │ SOAP Gateway │ │ Reports REST │ │ Voyager API  │ │Maps    │ │ .com       │ │
│  │              │ │              │ │              │ │Reviews │ │ (Zembra)   │ │
│  │ • unitlist   │ │ • Box Score  │ │ • GetUnits   │ │        │ │            │ │
│  │ • residents  │ │ • Rent Roll  │ │ • GetResiden │ │Playwri │ │ REST API   │ │
│  │ • leases     │ │ • Delinq.    │ │ • GetLeases  │ │ght     │ │            │ │
│  │ • rentables  │ │ • Activity   │ │              │ │Scraper │ │            │ │
│  │              │ │ • Monthly    │ │              │ │        │ │            │ │
│  │              │ │ • Lease Exp  │ │              │ │        │ │            │ │
│  │              │ │ • Proj. Occ  │ │              │ │        │ │            │ │
│  └──────┬───────┘ └──────┬───────┘ └──────┬───────┘ └───┬────┘ └─────┬──────┘ │
│         │                │                │              │            │         │
│  ┌──────────────┐                                                              │
│  │  Snowflake   │  (Risk Scores)                                               │
│  │  DWH_V2      │                                                              │
│  └──────┬───────┘                                                              │
└─────────┼────────────────┼────────────────┼──────────────┼────────────┼─────────┘
          │                │                │              │            │
          ▼                ▼                ▼              ▼            ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    GITHUB ACTIONS — AUTOMATED PIPELINE (every 6h)                │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  1. auto_token.py ──► Playwright headless login → RealPage JWT token            │
│  2. refresh_all.py ─► 5-step pipeline:                                          │
│     ├── STEP 1: SOAP API Pull (31 properties → realpage_raw.db)                │
│     ├── STEP 2: Report Downloads (217 reports → realpage_raw.db)               │
│     ├── STEP 3: Unified DB Sync (realpage_raw.db → unified.db)                 │
│     ├── STEP 4: Risk Score Sync (Snowflake → unified.db)                       │
│     └── STEP 5: Reviews Scrape (Google + Apartments.com → cache JSON)          │
│  3. push_to_deployed.py ──► Upload DBs + caches to Railway via admin API       │
│                                                                                  │
│  Total: ~17 minutes, 31 properties, 217 reports, 7806 units, 6032 residents    │
│                                                                                  │
└───────────────────────────────────────┬─────────────────────────────────────────┘
                                        │ HTTP upload
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                         RAILWAY — PRODUCTION BACKEND                             │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  FastAPI (uvicorn) on Railway persistent volume                                 │
│                                                                                  │
│  /data/                                                                          │
│  ├── unified.db          (3.5 MB)  — Normalized data for all endpoints          │
│  ├── realpage_raw.db     (22.7 MB) — Raw RealPage report + API data             │
│  ├── google_reviews_cache.json     — Google Reviews (434 KB)                    │
│  └── apartments_reviews_cache.json — Apartments.com Reviews (53 KB)             │
│                                                                                  │
│  API: https://brilliant-upliftment-production-3a4d.up.railway.app               │
│                                                                                  │
└───────────────────────────────────────┬─────────────────────────────────────────┘
                                        │ /api/* proxy
                                        ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                          NETLIFY — PRODUCTION FRONTEND                            │
├─────────────────────────────────────────────────────────────────────────────────┤
│                                                                                  │
│  React SPA + Vite build                                                          │
│  /api/* → proxied to Railway backend (netlify.toml rewrite)                     │
│  URL: https://nasadash.netlify.app                                              │
│                                                                                  │
│  JWT auth → Login page → Owner-group-scoped dashboard                           │
│                                                                                  │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Architecture

| Component | Platform | URL | Auto-deploy |
|-----------|----------|-----|-------------|
| **Backend** | Railway (nixpacks + persistent volume) | `https://brilliant-upliftment-production-3a4d.up.railway.app` | From GitHub `main` |
| **Frontend** | Netlify (React SPA) | `https://nasadash.netlify.app` | Manual `npx netlify deploy` |
| **Data Pipeline** | GitHub Actions (cron every 6h) | N/A | `refresh-data.yml` |
| **Smoke Test** | GitHub Actions (cron every 7h) | N/A | `smoke-test.yml` |
| **Code Repo** | GitHub | `github.com/bary249/NASAdash` | — |

### Railway Environment Variables

| Variable | Purpose |
|----------|---------|
| `RAILWAY_VOLUME_MOUNT_PATH` | `/data` — persistent storage for SQLite DBs |
| `ADMIN_API_KEY` | Shared secret for admin upload endpoints |
| `FRONTEND_URL` | Netlify URL for CORS |
| `JWT_SECRET` | JWT signing key for auth |
| `ANTHROPIC_API_KEY` | Claude API for AI insights |

### GitHub Actions Secrets

| Secret | Used By |
|--------|---------|
| `REALPAGE_EMAIL` / `REALPAGE_PASSWORD` | `auto_token.py` |
| `RAILWAY_API_URL` / `ADMIN_API_KEY` | `push_to_deployed.py`, `smoke_test.py` |
| `ZEMBRA_API_KEY` | `fetch_apartments_reviews.py` |
| `SNOWFLAKE_USER` / `SNOWFLAKE_PASSWORD` / `SNOWFLAKE_ACCOUNT` | `resident_risk_scores.py` |

---

## Automated Data Pipeline

### `refresh_all.py` — 5-Step Pipeline (runs every 6h via GH Actions)

```
STEP 1: SOAP API PULL (pull_all_api_data.py)
  └── 31 properties × (units + residents + leases + rentable items)
      ├── → realpage_raw.db: realpage_units (7,813 rows)
      ├── → realpage_raw.db: realpage_residents (23,509 rows)
      ├── → realpage_raw.db: realpage_leases (10,503 rows)
      ├── → realpage_raw.db: realpage_rentable_items (3,524 rows)
      └── → unified.db: sync properties, occupancy, pricing, delinquency, units, residents

STEP 2: REPORT DOWNLOADS (download_reports_v2.py)
  └── 31 properties × 7 report types = 217 reports
      ├── STEP 2a: Create 217 report instances via RealPage Reporting API
      ├── STEP 2b: Poll /v1/my/report-instances for reportFileId (status=3)
      ├── STEP 2c: Download 197+ Excel files (some reports empty)
      ├── STEP 2d: Retry box_score reports with date fallback (19 properties)
      └── STEP 2e: Parse & import all reports into realpage_raw.db

STEP 3: UNIFIED DB SYNC (sync_realpage_to_unified.py)
  └── realpage_raw.db → unified.db
      ├── 31 properties, occupancy for 31, 774 pricing records
      ├── 2,296 delinquency records, 7,806 units, 6,032 residents
      └── Latest snapshot_date only (prevents duplicate pricing rows)

STEP 4: RISK SCORE SYNC (app/db/sync_risk_scores.py)
  └── Snowflake DWH_V2 → unified_risk_scores table
      ├── 11 Kairoi properties matched (1,978 residents scored)
      └── Churn + delinquency prediction scores (0-1 scale)

STEP 5: REVIEWS SCRAPE
  └── Google Reviews: Playwright headless Chrome → google_reviews_cache.json
  └── Apartments.com: Zembra API → apartments_reviews_cache.json

PUSH: push_to_deployed.py
  └── Upload to Railway via admin API:
      ├── unified.db (3.5 MB)
      ├── realpage_raw.db (22.7 MB)
      ├── google_reviews_cache.json (434 KB)
      └── apartments_reviews_cache.json (53 KB)
```

### Token Management

| Aspect | Detail |
|--------|--------|
| **Script** | `auto_token.py` — Playwright headless browser login |
| **Token file** | `realpage_token.json` |
| **Client** | `greenbookpkce` (12 scopes, includes `unifiedreportingapi`) |
| **Expiry** | 60 minutes (refreshed at start of each pipeline run) |
| **Auth flow** | Navigate to realpage.com → fill email/password → capture OAuth token from network |

---

## Data Sources

### RealPage Reports (REST API) — 7 Report Types

| Report | ID | Key | Parser | DB Table | Records |
|--------|----|-----|--------|----------|---------|
| **Box Score** | 4238 | `446266C0-...` | `parse_box_score()` | `realpage_box_score` | 1,626 |
| **Rent Roll** | 4043 | `A6F61299-...` | `parse_rent_roll()` | `realpage_rent_roll` | 16,905 |
| **Delinquency (Full Financial)** | 4009 | `89A3C427-...` | `parse_delinquency()` | `realpage_delinquency` | 9,514 |
| **Activity Report** | 3837 | `B29B7C76-...` | `parse_activity()` | `realpage_activity` | 48,325 |
| **Monthly Activity Summary** | 3877 | `E41626AB-...` | `parse_monthly_summary()` | `realpage_monthly_summary` | 773 |
| **Lease Expiration & Renewal** | 4156 | `89545A3A-...` | `parse_lease_expiration()` | `realpage_lease_expiration_renewal` | 258 |
| **Projected Occupancy** | 3842 | `345C5708-...` | `parse_projected_occupancy()` | `realpage_projected_occupancy` | 60 |

### RealPage RPX Gateway (SOAP API)

| Endpoint | DB Table | Records | Key Fields |
|----------|----------|---------|------------|
| `unitlist` | `realpage_units` | 7,813 | unit_id, floorplan, bedrooms, sqft, market_rent, vacant, available, made_ready_date |
| `getResidentListInfo` | `realpage_residents` | 23,509 | resident_id, unit_number, lease_status, rent, balance, move_in/out_date |
| `getLeaseInfo` | `realpage_leases` | 10,503 | lease_id, rent_amount, lease_start/end_date, status, evict flag, current_balance |
| `getRentableItems` | `realpage_rentable_items` | 3,524 | item_name, item_type, billing_amount, unit_id |

### Additional Data Sources

| Source | Method | Storage | Data |
|--------|--------|---------|------|
| **Google Reviews** | Playwright headless Chrome scraper | `google_reviews_cache.json` | Star ratings, review text, management responses |
| **Apartments.com** | Zembra REST API | `apartments_reviews_cache.json` | Reviews, ratings, response tracking |
| **Snowflake DWH_V2** | SQL connector | `unified_risk_scores` table | Churn + delinquency prediction per property |
| **Anthropic Claude** | REST API (real-time) | Not cached | AI-generated property insights & alerts |
| **Yardi Voyager** | SOAP API | `yardi_raw.db` | Units, residents, leases (not actively used — Kairoi is all RealPage) |

---

## Database Schema

### realpage_raw.db (22.7 MB, 18 tables)

| Table | Records | Purpose |
|-------|---------|---------|
| `realpage_box_score` | 1,626 | Floorplan-level occupancy metrics per property |
| `realpage_rent_roll` | 16,905 | Unit-level status, rent, lease dates |
| `realpage_delinquency` | 9,514 | Outstanding balances with aging buckets + total_delinquent |
| `realpage_activity` | 48,325 | Leasing activity events (move-ins, tours, applications) |
| `realpage_monthly_summary` | 773 | Monthly move-in/out/renewal aggregates |
| `realpage_lease_expiration_renewal` | 258 | Unit-level lease exp decisions (Report 4156) |
| `realpage_lease_expirations` | 1,798 | Legacy lease expiration data (Report 3838) |
| `realpage_lease_exp_renewal_summary` | 48 | Floorplan-level expiration summaries |
| `realpage_projected_occupancy` | 60 | Weekly occupancy projections (Report 3842) |
| `realpage_units` | 7,813 | Unit master from SOAP API |
| `realpage_residents` | 23,509 | Resident data from SOAP API |
| `realpage_leases` | 10,503 | Lease details from SOAP API |
| `realpage_rentable_items` | 3,524 | Amenities, parking, storage |
| `realpage_properties` | 0 | Property master (populated via API) |
| `realpage_buildings` | 0 | Building structures |
| `realpage_extraction_log` | 4 | SOAP API extraction audit trail |
| `realpage_report_import_log` | 42 | Report import audit trail |

### unified.db (3.5 MB, 11 tables)

| Table | Records | Key Fields |
|-------|---------|------------|
| `unified_properties` | 31 | unified_property_id, name, pms_source, owner_group, address, total_units |
| `unified_occupancy_metrics` | 31 | total_units, occupied, vacant, leased, preleased, on_notice, model, down |
| `unified_pricing_metrics` | 774 | floorplan, unit_count, avg_square_feet, in_place_rent, asking_rent, rent_growth |
| `unified_delinquency` | 2,296 | unit_number, current_balance, balance_0_30/31_60/61_90/over_90, total_delinquent |
| `unified_units` | 7,806 | unit_number, floorplan, bedrooms, sqft, market_rent, status, days_vacant |
| `unified_residents` | 6,032 | unit_number, status, current_rent, lease_start/end, move_in_date |
| `unified_leases` | 0 | (populated for Yardi properties) |
| `unified_risk_scores` | 11 | avg_churn_score, avg_delinquency_score, risk bucket counts, insights |
| `unified_sync_log` | 35 | Sync audit trail |
| `users` | 2 | username, password_hash, owner_group (PHH, Kairoi) |
| `watchpoints` | — | User-defined metric watchpoints per property |

---

## API Endpoints

### Authentication — `/api/auth/`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/auth/login` | POST | JWT login (username + password → token) |
| `/api/auth/me` | GET | Get current user info from JWT |

### Admin — `/api/admin/` (protected by `X-Admin-Key` header)

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/admin/upload-db` | POST | Upload SQLite DB file to Railway volume |
| `/api/admin/upload-file` | POST | Upload cache file (reviews JSON) |
| `/api/admin/db-status` | GET | Check DB file sizes and modification times |

### Property Endpoints — `/api/v2/properties/{id}/`

| Endpoint | Method | Description | Data Source |
|----------|--------|-------------|-------------|
| `/health` | GET | Backend health check | — |
| `/properties` | GET | List all properties | unified_properties |
| `/properties/{id}/occupancy` | GET | Occupancy metrics | unified_occupancy_metrics |
| `/properties/{id}/exposure` | GET | Exposure & notices | Box score + rent roll |
| `/properties/{id}/availability` | GET | ATR, vacancy breakdown | Box score + rent roll + API |
| `/properties/{id}/availability-by-floorplan` | GET | Floorplan availability detail | rent_roll + box_score |
| `/properties/{id}/availability-by-floorplan/units` | GET | Unit-level drill-down | rent_roll + units |
| `/properties/{id}/consolidated-by-bedroom` | GET | Bedroom-consolidated view | rent_roll + box_score |
| `/properties/{id}/pricing` | GET | Pricing by floorplan | unified_pricing_metrics |
| `/properties/{id}/tradeouts` | GET | Lease trade-out analysis | leases |
| `/properties/{id}/renewals` | GET | Renewal analysis | leases |
| `/properties/{id}/turn-time` | GET | Unit turn time metrics | rent_roll + units |
| `/properties/{id}/loss-to-lease` | GET | Loss-to-lease analysis | rent_roll |
| `/properties/{id}/delinquency` | GET | Delinquency with aging buckets | unified_delinquency |
| `/properties/{id}/leasing-funnel` | GET | Marketing funnel | activity report |
| `/properties/{id}/occupancy-forecast` | GET | 12-week occupancy forecast | projected_occupancy + leases |
| `/properties/{id}/occupancy-trend` | GET | Historical occupancy trend | box_score |
| `/properties/{id}/all-trends` | GET | All metric trends | multiple tables |
| `/properties/{id}/expirations` | GET | Lease expirations 30/60/90d | lease_expiration_renewal |
| `/properties/{id}/expirations/details` | GET | Unit-level expiration details | lease_expiration_renewal |
| `/properties/{id}/projected-occupancy` | GET | Raw projected occupancy data | projected_occupancy |
| `/properties/{id}/risk-scores` | GET | Resident risk scores | unified_risk_scores |
| `/properties/{id}/reputation` | GET | Combined review ratings | Google + Apartments.com caches |
| `/properties/{id}/reviews` | GET | Google Reviews detail | google_reviews_cache.json |
| `/properties/{id}/apartments-reviews` | GET | Apartments.com reviews | apartments_reviews_cache.json |
| `/properties/{id}/ai-insights` | GET | AI-generated alerts | Claude API (real-time) |
| `/properties/{id}/watchpoints` | GET/POST/DELETE | Metric watchpoints CRUD | watchpoints table |
| `/properties/{id}/chat` | POST | AI chat Q&A | Claude API (real-time) |
| `/properties/{id}/shows` | GET | Showing/tour data | activity report |
| `/properties/{id}/amenities` | GET | Rentable items | realpage_rentable_items |
| `/properties/{id}/amenities/summary` | GET | Amenity summary | realpage_rentable_items |
| `/properties/{id}/summary` | GET | Combined dashboard data | All sources |
| `/properties/{id}/units/raw` | GET | Raw unit drill-through | unified_units |
| `/properties/{id}/residents/raw` | GET | Raw resident drill-through | unified_residents |
| `/properties/{id}/prospects/raw` | GET | Prospect drill-through | residents (applicant) |
| `/properties/{id}/location` | GET | Property location info | unified_properties |
| `/chat/status` | GET | AI chat availability | config check |

### Portfolio Endpoints — `/api/portfolio/`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/properties` | GET | Portfolio property list with KPIs (filtered by owner_group) |
| `/owner-groups` | GET | List owner groups |
| `/occupancy` | GET | Portfolio-wide occupancy |
| `/pricing` | GET | Portfolio-wide pricing |
| `/summary` | GET | Portfolio summary |
| `/units` | GET | All units across portfolio |
| `/residents` | GET | All residents across portfolio |
| `/watchlist` | GET | Flagged properties + thresholds |
| `/risk-scores` | GET | Portfolio risk score aggregation |
| `/chat` | POST | Portfolio-level AI chat |
| `/health` | GET | Portfolio service health |

### Market — `/api/v2/`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/submarkets` | GET | List available submarkets |
| `/market-comps` | GET | Market comp data (ALN API) |
| `/market-comps/search` | GET | Search market comps |

---

## Authentication

| Aspect | Detail |
|--------|--------|
| **Method** | JWT (JSON Web Token) with bcrypt password hashing |
| **Expiry** | 24 hours |
| **Users** | PHH (owner_group=PHH, 2 properties), Kairoi (owner_group=Kairoi, 29 properties) |
| **Backend** | `auth_service.py` — bcrypt verify + JWT create/verify |
| **Frontend** | `AuthContext.tsx` — AuthProvider, useAuth hook, localStorage persistence |
| **Scoping** | Portfolio endpoints filter by JWT `owner_group` claim — PHH can only see PHH properties |

---

## Frontend

### Tech Stack

- **Framework**: React + TypeScript + Vite
- **Styling**: Tailwind CSS
- **Icons**: Lucide React
- **Build**: `npm run build` → `dist/`

### Dashboard Tabs (TabNavigation.tsx)

| Tab | Component | Description |
|-----|-----------|-------------|
| **Overview** | `PortfolioView` + `OccupancySectionV2` | Portfolio table + property KPIs |
| **Availability** | `AvailabilitySection` + `BedroomConsolidatedView` | ATR, floorplan breakdown, unit drill-down |
| **Pricing** | `UnitMixPricing` + `TradeOutSection` | Floorplan pricing, trade-outs, loss-to-lease |
| **Delinquency** | `DelinquencySection` | Aging buckets, unit-level detail |
| **Risk Scores** | `ResidentRiskSection` | Churn/delinquency gauges, risk distribution |
| **Reputation** | `GoogleReviewsSection` + `ReputationOverview` | Google + Apartments.com reviews, response tracking |
| **Watchpoints** | `WatchpointsPanel` | User-defined metric alerts per property |
| **Watchlist** | `WatchListTab` | Flagged properties across portfolio |

### Key Components

| Component | Purpose |
|-----------|---------|
| `DashboardV3.tsx` | Main dashboard layout, tab routing, property selection |
| `LoginPage.tsx` | JWT login with glassmorphism UI |
| `AIInsightsPanel.tsx` | Collapsible AI insights + alerts (Claude-powered) |
| `AIChatPanel.tsx` | AI Q&A chat interface |
| `PortfolioView.tsx` | Portfolio table with sortable KPIs |
| `PropertyCard.tsx` | Property summary card |
| `DrillThroughModal.tsx` | Unit-level data drill-down modal |

---

## Monitoring & Smoke Tests

### Smoke Test (`smoke_test.py`)

Runs **every 7 hours** via GitHub Actions (`smoke-test.yml`) + manual trigger.

**40 checks across 5 categories:**

| Category | Checks | What's Verified |
|----------|--------|-----------------|
| **Infrastructure** (4) | Health, DB status, Auth, Chat | Backend alive, DBs exist, auth works |
| **Portfolio** (3) | Properties, Owner groups, Watchlist | Portfolio data loads correctly |
| **Per-Property** (24) | 3 properties × 8 endpoints | Availability, forecast, delinquency, expirations, risk, reviews, AI, watchpoints |
| **Data Freshness** (7) | DB age, pricing sanity ×3, report data ×3 | No stale data, no duplicate floorplans, real occupancy values |
| **Frontend** (2) | HTML render, API proxy | SPA loads, Netlify→Railway proxy works |

### Data Freshness Thresholds

| Check | Pass Criteria |
|-------|---------------|
| DB file age | Modified within 25 hours |
| Pricing sanity | 0 duplicate floorplans, 0 all-zero rows |
| Report data | Occupancy > 50% (sanity check for real data) |

---

## Property Configuration

### 31 Properties (29 Kairoi + 2 PHH)

All Kairoi properties use **PMC ID: 4248314**. PHH properties use their own PMC IDs.

| Owner Group | Properties | Count |
|-------------|------------|-------|
| **Kairoi** | 7 East, Aspire 7th & Grant, Block 44, Curate, Discovery Kingwood, Eden Keller Ranch, Edison at RiNo, Harvest, Heights at Interlocken, Izzy, Kalaco, Links at Plum Creek, Luna, Park 17, Pearl Lantana, Ridian, Slate, Sloane, Station Riverfront, Stonewood, Ten50, The Alcott, The Avant, The Broadleaf, The Confluence, The Hunter, The Northern, thePearl, theQuinci | 29 |
| **PHH** | Nexus East, Parkside at Round Rock | 2 |

---

## Field Coverage by Module

### Module 1: Occupancy & Availability

| Field | Source | Status |
|-------|--------|--------|
| Physical Occupancy % | Box Score `occupancy_pct` | ✅ |
| Leased % | Box Score `leased_pct` | ✅ |
| Total / Occupied / Vacant Units | Box Score | ✅ |
| Preleased Vacant | Box Score `vacant_leased` | ✅ |
| On Notice | Box Score `occupied_on_notice` | ✅ |
| Model / Down Units | Box Score | ✅ |
| Vacant Ready / Not Ready | API `made_ready_date` | ✅ |
| Days Vacant | Rent Roll date calc | ✅ |
| ATR (Available to Rent) | Box Score derived | ✅ |
| 12-Week Occupancy Forecast | Report 3842 Projected Occupancy | ✅ |
| Scheduled Move-Ins/Outs | Report 3842 | ✅ |

### Module 2: Lease Expirations & Renewals

| Field | Source | Status |
|-------|--------|--------|
| Expirations by 30/60/90 day | Report 4156 Lease Exp/Renewal | ✅ |
| Renewal decisions | Report 4156 `decision` column | ✅ |
| Monthly expiration periods | Report 4156 aggregated | ✅ |
| New rent on renewal | Report 4156 `new_rent` | ✅ |
| Trade-out analysis | SOAP leases (prior vs new rent) | ✅ |

### Module 3: Pricing

| Field | Source | Status |
|-------|--------|--------|
| In-Place Rent (by floorplan) | Box Score / SOAP leases | ✅ |
| Asking Rent (by floorplan) | Box Score `avg_market_rent` | ✅ |
| Rent Growth % | Calculated (asking/in-place) | ✅ |
| $/SF metrics | Calculated | ✅ |
| Loss-to-Lease | Rent Roll (market - actual) | ✅ |

### Module 4: Delinquency

| Field | Source | Status |
|-------|--------|--------|
| Total Delinquent | Report 4009 `total_delinquent` | ✅ |
| Current / 30 / 60 / 90+ aging | Report 4009 aging buckets | ✅ |
| Prepaid | Report 4009 `prepaid` | ✅ |
| Net Balance | Report 4009 `net_balance` | ✅ |
| Unit-level delinquency | Report 4009 detail rows | ✅ |
| Eviction flag | SOAP leases `evict` field | ✅ |

### Module 5: Activity & Leasing

| Field | Source | Status |
|-------|--------|--------|
| Move-Ins/Outs (MTD) | Monthly Summary Report | ✅ |
| Net Absorption | Calculated | ✅ |
| Renewals | Monthly Summary | ✅ |
| Shows/Tours | Activity Report | ✅ |
| Applications / Lease Signs | SOAP residents | ✅ |

### Module 6: Reputation & Reviews

| Field | Source | Status |
|-------|--------|--------|
| Google Rating + Reviews | Playwright scraper | ✅ (PHH only) |
| Google Response Rate | Scraper (management replies) | ✅ |
| Apartments.com Rating | Zembra API | ✅ (PHH only) |
| Apartments.com Response Rate | Zembra API | ✅ |
| Star Distribution | Both sources | ✅ |
| Overall Weighted Rating | Combined | ✅ |

### Module 7: Risk Scores

| Field | Source | Status |
|-------|--------|--------|
| Avg Churn Score | Snowflake DWH_V2 | ✅ (11 Kairoi properties) |
| Avg Delinquency Score | Snowflake DWH_V2 | ✅ |
| Risk Buckets (High/Med/Low) | Calculated from scores | ✅ |
| Contributing Factors | Snowflake (tenure, app usage, tickets) | ✅ |

### Module 8: AI Insights

| Field | Source | Status |
|-------|--------|--------|
| Auto-generated Alerts | Claude API (real-time) | ✅ |
| Q&A Chat | Claude API (real-time) | ✅ |
| Collapsible Panel | localStorage persistence | ✅ |

### Module 9: Financials *(PLANNED — not yet implemented)*

| Field | Potential Source | Status |
|-------|-----------------|--------|
| Revenue / NOI | RealPage Financial Reports (TBD) | 🔜 Planned |
| Budget vs Actual | RealPage Financial Reports (TBD) | 🔜 Planned |
| Expense Categories | RealPage Financial Reports (TBD) | 🔜 Planned |

---

## File Structure

```
OwnerDashV2/
├── .github/
│   └── workflows/
│       ├── refresh-data.yml          # Data pipeline (every 6h)
│       └── smoke-test.yml            # Smoke test (every 7h)
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes.py             # 40+ property endpoints
│   │   │   ├── portfolio.py          # Portfolio aggregation endpoints
│   │   │   ├── auth.py               # JWT login + /me
│   │   │   └── admin.py              # DB upload + status (admin key)
│   │   ├── clients/
│   │   │   ├── yardi_client.py       # Yardi SOAP client (READ-ONLY)
│   │   │   ├── realpage_client.py    # RealPage RPX SOAP client
│   │   │   └── aln_client.py         # ALN market data client
│   │   ├── db/
│   │   │   ├── data/
│   │   │   │   ├── realpage_raw.db   # Raw RealPage data (22.7 MB)
│   │   │   │   ├── unified.db        # Normalized data (3.5 MB)
│   │   │   │   ├── google_reviews_cache.json
│   │   │   │   └── apartments_reviews_cache.json
│   │   │   ├── schema.py             # All DB schemas + path config
│   │   │   ├── sync_realpage_to_unified.py
│   │   │   ├── sync_yardi_to_unified.py
│   │   │   └── sync_risk_scores.py   # Snowflake → unified_risk_scores
│   │   ├── services/
│   │   │   ├── occupancy_service.py  # Occupancy, forecast, expirations
│   │   │   ├── pricing_service.py    # Pricing, trade-outs, loss-to-lease
│   │   │   ├── auth_service.py       # JWT + bcrypt auth
│   │   │   ├── google_reviews_service.py
│   │   │   ├── apartments_reviews_service.py
│   │   │   └── portfolio_service.py  # Portfolio aggregation
│   │   ├── models.py                 # Pydantic response models
│   │   ├── main.py                   # FastAPI app + CORS + routers
│   │   └── config.py                 # Settings (env vars)
│   ├── auto_token.py                 # Playwright RealPage token capture
│   ├── refresh_all.py                # 5-step data pipeline orchestrator
│   ├── pull_all_api_data.py          # SOAP API extraction for all properties
│   ├── download_reports_v2.py        # Report download + import (v2 API)
│   ├── batch_report_downloader.py    # Legacy report downloader
│   ├── report_parsers.py             # Excel report parsers (7 types)
│   ├── import_reports.py             # DB import logic
│   ├── push_to_deployed.py           # Upload DBs to Railway
│   ├── smoke_test.py                 # Production smoke test (40 checks)
│   ├── scrape_reviews.py             # Google Reviews Playwright scraper
│   ├── fetch_apartments_reviews.py   # Apartments.com via Zembra API
│   ├── resident_risk_scores.py       # Snowflake risk score extraction
│   ├── report_definitions.json       # Report configs + property registry
│   ├── railway.toml                  # Railway deployment config
│   └── requirements.txt              # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DashboardV3.tsx        # Main dashboard (tabs, routing)
│   │   │   ├── LoginPage.tsx          # JWT login UI
│   │   │   ├── PortfolioView.tsx      # Portfolio table
│   │   │   ├── OccupancySectionV2.tsx # Occupancy metrics
│   │   │   ├── AvailabilitySection.tsx# ATR + floorplan breakdown
│   │   │   ├── UnitMixPricing.tsx     # Pricing by floorplan
│   │   │   ├── DelinquencySection.tsx # Delinquency detail
│   │   │   ├── ResidentRiskSection.tsx# Risk score gauges
│   │   │   ├── GoogleReviewsSection.tsx # Reviews (Google + Apts.com)
│   │   │   ├── AIInsightsPanel.tsx    # Collapsible AI insights
│   │   │   ├── AIChatPanel.tsx        # AI Q&A chat
│   │   │   ├── WatchpointsPanel.tsx   # Metric watchpoints
│   │   │   ├── WatchListTab.tsx       # Portfolio watchlist
│   │   │   ├── TabNavigation.tsx      # Tab bar + tab IDs
│   │   │   └── ... (34 components total)
│   │   ├── contexts/
│   │   │   └── AuthContext.tsx         # JWT auth provider
│   │   ├── api.ts                     # API client (fetchJson + auth headers)
│   │   └── App.tsx                    # Root (AuthGate → Dashboard)
│   ├── netlify.toml                   # Build + /api proxy to Railway
│   ├── package.json
│   └── index.html
├── ARCHITECTURE.md                    # This file
├── ARCHITECTURE_REVIEW.md             # Security review document
└── Data_Definitions_and_Sources/
    ├── REALPAGE_DATA_MAPPING.md
    └── REALPAGE_REPORTS_REFERENCE.md
```

---

## Future: Financials Section

**Status**: Planning phase.

### PDF Scan Results

The `Unified Platform User Guide.pdf` (306 pages) is the **Residents/Management Reports** guide only. It does **not** contain financial/accounting reports. Financial reports (Income Statement, Budget vs Actual, Balance Sheet, GL) are likely in a separate RealPage "Accounting Reports" guide.

### API Discovery Results (Feb 15, 2026)

Scanned RealPage Reporting API (`GET /reports/report-areas` + `GET /reports/{id}` for IDs 3800–4400).

**Key finding**: RealPage does **not** have a standalone "Income Statement" or "P&L" report. Financial data is structured around transaction summaries, ledger activity, and gain/loss reports within the **Accounts Receivable** report area (ID=8).

### Available Financial Reports (confirmed via API)

| Report ID | Name | Area | mappingKey | Owner Value |
|-----------|------|------|------------|-------------|
| **4020** | Monthly Transaction Summary | AR/Mgmt (8) | `81ADF4FF-...` | Revenue by transaction code per fiscal period — **closest to an income statement** |
| **4160** | Financial Account Ledger | AR/Mgmt (8) | `670D954E-...` | Unit-level charges, adjustments, payments, balances |
| **4279** | Lost Rent Summary (Excel) | AR/Mgmt (8) | `AD3AB1DD-...` | Vacancy loss, concession loss, gain/loss to lease |
| **4281** | Resident Balances by Fiscal Period (Excel) | AR/Mgmt (8) | `184BACD5-...` | Prepaid/delinquent balance breakdown by receivable account |
| **4010** | Bank Deposit Summary (Excel) | AR/Mgmt (8) | — | Bank deposit receipts for fiscal period |
| **4235** | Bank Deposit Details (Excel) | AR/Mgmt (8) | — | Individual deposit transaction detail |
| **4231** | Gain, Loss & Vacancy / Preclose | Tasks (69) | `A83889F3-...` | Period gain/loss amounts and vacancy amounts |

### GL/Accounting Exports (SDE area — XML format, for 3rd-party import)

| Report ID | Name | Area | Notes |
|-----------|------|------|-------|
| **4163** | GL Journal (V2) | SDE/Accounting (32) | Journal entries as XML — designed for GL system import |
| **4174** | GL Journal (V2) | SDE/Leasing (33) | Same as above, different area |
| **4098** | GL Balancing | SDE/Leasing (33) | GL cash balances extract |
| **4095** | Transaction Summary | SDE/Leasing (33) | 1099 transaction data extract |

### Recommended Approach for Financials Dashboard

**Phase 1**: Start with **Report 4020 (Monthly Transaction Summary)** — this is the closest to a P&L/income statement view. It shows revenue by transaction code (rent, fees, concessions, etc.) per fiscal period.

**Phase 2**: Add **Report 4279 (Lost Rent Summary)** — provides vacancy loss and concession metrics that owners care about.

**Phase 3**: Consider **Report 4160 (Financial Account Ledger)** for unit-level financial drill-down.

**Note**: All reports show `reportFormats: []` in the API response — format IDs need to be discovered by creating a test instance via the RealPage UI and capturing the format parameter.

### Additional Reports Found in PDF (not yet integrated)

| Report | Report Area | Page | Value |
|--------|-------------|------|-------|
| Lease Renewal Trend | Management | p.84 | Historical renewal % trends by month |
| Lease Variance by Move-In Date | Management | p.87 | Rent variance at move-in |
| Reasons for Move Outs | Management | p.125 | Churn reason categories |

### Approach

- **Local development only** until validated
- **Always ask before deploying** any new sections
- Incremental: discover reports → download one sample → build parser → build endpoint → build UI

---

*Document maintained in: `/OwnerDashV2/ARCHITECTURE.md`*
