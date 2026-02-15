"""
Owner Dashboard V2 API - READ-ONLY Backend
============================================
API for Asset Management Dashboard per spec.

IMPORTANT: All operations are GET-only. No PUT, POST, DELETE operations
are permitted to ensure no data modifications occur.

Data Sources:
- Yardi PMS (SOAP APIs): Occupancy, Leasing, Unit Pricing
- RealPage RPX (SOAP APIs): Units, Residents, Leases

Timeframe Logic (per spec Section 2):
- CM (Current Month): 1st of current month to now
- PM (Previous Month): Full previous month (static benchmark)
- YTD (Year-to-Date): Jan 1st to now
"""
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import router
from app.api.portfolio import router as portfolio_router
from app.api.imports import router as imports_router
from app.api.auth import router as auth_router
from app.api.admin import router as admin_router
from app.config import get_settings

app = FastAPI(
    title="Owner Dashboard V2 API",
    description="""
    Read-only API for Asset Manager Dashboard.
    
    ## Modules
    - **Occupancy & Exposure**: Physical occupancy, leased %, exposure 30/60, notices, aged vacancy
    - **Marketing Funnel**: Leads, Tours, Applications, Lease Signs, conversion rates
    - **Unit Pricing**: In-place rents, asking rents, rent growth by floorplan
    - **Portfolio View**: Multi-property aggregated metrics with weighted avg or row metrics mode
    
    ## Timeframes
    - **CM**: Current Month (1st to today) - for daily operations
    - **PM**: Previous Month (static benchmark) - for month-over-month comparison
    - **YTD**: Year-to-Date (Jan 1 to today) - for long-term trends
    
    ## Data Sources
    - Yardi PMS (SOAP APIs)
    - RealPage RPX (SOAP APIs)
    
    ## Important
    All endpoints are **GET-only**. This API does not modify any data.
    """,
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5172", 
        "http://localhost:3000", 
        "http://127.0.0.1:5172",
        os.environ.get("FRONTEND_URL", ""),  # Netlify URL in production
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # POST needed for file imports
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api", tags=["Auth"])
app.include_router(router, prefix="/api/v2", tags=["Dashboard V2"])
app.include_router(portfolio_router)  # Portfolio endpoints at /api/portfolio
app.include_router(imports_router, prefix="/api", tags=["Excel Imports"])
app.include_router(admin_router, prefix="/api", tags=["Admin"])


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "Owner Dashboard V2 API",
        "version": "2.0.0",
        "docs": "/docs",
        "status": "running",
        "note": "READ-ONLY API - All operations are GET only",
        "timeframes": ["cm (Current Month)", "pm (Previous Month)", "ytd (Year-to-Date)"]
    }
