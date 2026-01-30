# Owner Dashboard V2

Asset Management Dashboard implementing the Owners Dashboard Specification.

## Features

### Module 1: Occupancy & Exposure (Vital Signs)
- **Physical Occupancy**: Occupied Units / Total Units
- **Leased %**: (Occupied + Preleased Vacant) / Total Units
- **Exposure 30/60 Days**: (Vacant + Pending Move-outs) - Pending Move-ins
- **Notices 30/60 Days**: NTVs with move-out in next 30/60 days
- **Aged Vacancy (>90 days)**: Units vacant > 90 days
- **Vacant Ready/Not Ready**: Move-in ready status

### Module 2: Marketing Funnel (Pipeline)
- **Leads**: Unique contacts/inquiries (Guest Cards)
- **Tours**: Verified visits (Show events)
- **Applications**: Submitted applications
- **Lease Signs**: Countersigned leases
- **Conversion Rates**: Lead→Tour, Tour→App, App→Lease

### Module 3: Unit Pricing
- **In-Place Rent**: Weighted average rent paid by current residents
- **Asking Rent**: Weighted average market rent
- **Rent Growth**: (Asking / In-Place) - 1
- Per-floorplan breakdown

## Timeframe Logic (per spec Section 2)

| Timeframe | Description | Use Case |
|-----------|-------------|----------|
| **CM** (Current Month) | 1st of current month to today | Daily operations |
| **PM** (Previous Month) | Full previous month (static) | Month-over-month comparison |
| **YTD** (Year-to-Date) | Jan 1st to today | Long-term trends |

## Tech Stack

- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **Data Source**: Yardi PMS (SOAP APIs)

## Quick Start

### Backend

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file and configure
cp .env.example .env
# Edit .env with your Yardi credentials

# Run server
uvicorn app.main:app --reload --port 8001
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

Frontend runs on http://localhost:5174 and proxies API requests to backend on port 8001.

## API Endpoints (READ-ONLY)

All endpoints are GET-only. No data modifications.

| Endpoint | Description |
|----------|-------------|
| `GET /api/v2/properties` | List all properties |
| `GET /api/v2/properties/{id}/occupancy?timeframe=cm` | Occupancy metrics |
| `GET /api/v2/properties/{id}/exposure?timeframe=cm` | Exposure metrics |
| `GET /api/v2/properties/{id}/leasing-funnel?timeframe=cm` | Marketing funnel |
| `GET /api/v2/properties/{id}/pricing` | Unit pricing |
| `GET /api/v2/properties/{id}/summary?timeframe=cm` | Complete dashboard |
| `GET /api/v2/properties/{id}/units/raw` | Raw unit data (drill-through) |
| `GET /api/v2/properties/{id}/residents/raw` | Raw resident data |
| `GET /api/v2/properties/{id}/prospects/raw` | Raw prospect data |

## Project Structure

```
OwnerDashV2/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py        # API endpoints
│   │   ├── clients/
│   │   │   └── yardi_client.py  # Yardi SOAP client
│   │   ├── services/
│   │   │   ├── occupancy_service.py  # Occupancy & leasing logic
│   │   │   ├── pricing_service.py    # Unit pricing logic
│   │   │   └── timeframe.py          # CM/PM/YTD calculations
│   │   ├── config.py
│   │   ├── main.py
│   │   └── models.py
│   ├── .env.example
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── DrillThroughModal.tsx
│   │   │   ├── MetricCard.tsx
│   │   │   ├── OccupancySection.tsx
│   │   │   ├── SectionHeader.tsx
│   │   │   ├── TimeframeSelector.tsx
│   │   │   └── UnitPricingSection.tsx
│   │   ├── api.ts
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── types.ts
│   ├── package.json
│   └── vite.config.ts
└── README.md
```

## Important Notes

1. **READ-ONLY**: This dashboard only reads data from Yardi. No write operations.
2. **Financials Module**: Not yet implemented (pending Yardi Voyager access)
3. **All lint errors in IDE**: Will resolve after running `npm install`
