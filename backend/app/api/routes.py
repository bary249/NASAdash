"""
API Routes - Owner Dashboard V2
READ-ONLY endpoints. All operations are GET-only.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime

from app.services.occupancy_service import OccupancyService
from app.services.pricing_service import PricingService
from app.services.market_comps_service import MarketCompsService
from app.services.chat_service import chat_service
from app.models import (
    Timeframe,
    OccupancyMetrics,
    ExposureMetrics,
    LeasingFunnelMetrics,
    UnitPricingMetrics,
    DashboardSummary,
    PropertyInfo,
    MarketCompsResponse,
    MarketComp
)

router = APIRouter()

occupancy_service = OccupancyService()
pricing_service = PricingService()
market_comps_service = MarketCompsService()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@router.get("/properties", response_model=list[PropertyInfo])
async def get_properties():
    """
    GET: List all properties.
    Used for property selector dropdown.
    """
    try:
        return await occupancy_service.get_property_list()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/occupancy", response_model=OccupancyMetrics)
async def get_occupancy(
    property_id: str,
    timeframe: Timeframe = Query(Timeframe.CM, description="Timeframe: cm, pm, or ytd")
):
    """
    GET: Occupancy metrics for a property.
    
    Timeframes:
    - cm: Current Month (1st to today)
    - pm: Previous Month (full month, static benchmark)
    - ytd: Year-to-Date (Jan 1 to today)
    
    Returns: Physical occupancy, leased %, vacancy breakdown, aged vacancy.
    """
    try:
        return await occupancy_service.get_occupancy_metrics(property_id, timeframe)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/exposure", response_model=ExposureMetrics)
async def get_exposure(
    property_id: str,
    timeframe: Timeframe = Query(Timeframe.CM, description="Timeframe: cm, pm, or ytd")
):
    """
    GET: Exposure and movement metrics.
    
    Returns:
    - Exposure 30/60 days: (Vacant + Pending Move-outs) - Pending Move-ins
    - Notices 30/60 days: NTVs with move-out in next 30/60 days
    - Move-ins/outs for period
    - Net absorption
    """
    try:
        return await occupancy_service.get_exposure_metrics(property_id, timeframe)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/leasing-funnel", response_model=LeasingFunnelMetrics)
async def get_leasing_funnel(
    property_id: str,
    timeframe: Timeframe = Query(Timeframe.CM, description="Timeframe: cm, pm, or ytd")
):
    """
    GET: Leasing funnel metrics (Marketing Pipeline).
    
    Returns: Leads, Tours, Applications, Lease Signs, conversion rates.
    Data source: ILS Guest Card API, falls back to Excel reports for RealPage properties.
    """
    from app.services.leasing_parser import parse_leasing_funnel
    from pathlib import Path
    
    # First try ILS API
    try:
        result = await occupancy_service.get_leasing_funnel(property_id, timeframe)
        if result.leads > 0:
            return result
    except Exception:
        pass
    
    # Fall back to Excel reports for properties that have them
    PROPERTY_LEASING_REPORTS = {
        "kairoi-the-northern": {
            "funnel": "Online Leasing Lease Summary (1).xls",
            "activity": "Leasing Activity Summary (2).xls"
        }
    }
    
    reports = PROPERTY_LEASING_REPORTS.get(property_id)
    if reports:
        db_path = Path(__file__).parent.parent / "db"
        funnel_path = db_path / reports["funnel"]
        activity_path = db_path / reports["activity"]
        
        if funnel_path.exists() and activity_path.exists():
            try:
                excel_data = parse_leasing_funnel(str(funnel_path), str(activity_path))
                # Parse date range to get period dates
                date_range = excel_data.get("date_range", "")
                parts = date_range.split(" - ") if " - " in date_range else ["", ""]
                return LeasingFunnelMetrics(
                    property_id=property_id,
                    timeframe=timeframe.value,
                    period_start=parts[0] if parts[0] else "2026-01-01",
                    period_end=parts[1] if len(parts) > 1 else "2026-01-31",
                    leads=excel_data["leads"],
                    tours=excel_data["tours"],
                    applications=excel_data["applications"],
                    lease_signs=excel_data["lease_signs"],
                    denials=excel_data["denials"],
                    lead_to_tour_rate=excel_data["lead_to_tour_rate"],
                    tour_to_app_rate=excel_data["tour_to_app_rate"],
                    app_to_lease_rate=excel_data["app_to_lease_rate"],
                    lead_to_lease_rate=excel_data["lead_to_lease_rate"],
                )
            except Exception:
                pass
    
    # Return empty metrics if no data available
    return await occupancy_service.get_leasing_funnel(property_id, timeframe)


@router.get("/properties/{property_id}/pricing", response_model=UnitPricingMetrics)
async def get_pricing(property_id: str):
    """
    GET: Unit pricing metrics.
    
    Returns per-floorplan and total:
    - In-Place Effective Rent (weighted avg current resident rents)
    - Asking Effective Rent (weighted avg market rents)
    - Rent per SF
    - Rent Growth: (Asking / In-Place) - 1
    """
    try:
        return await pricing_service.get_unit_pricing(property_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/tradeouts")
async def get_tradeouts(property_id: str):
    """
    GET: Lease trade-out data.
    
    Trade-out = when a resident moves out and a new one moves in.
    Compares prior lease rent vs new lease rent for same unit.
    
    Returns:
    - tradeouts: List of individual trade-outs with rent change
    - summary: Average rent change metrics
    """
    try:
        return await pricing_service.get_lease_tradeouts(property_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/expirations")
async def get_expirations(property_id: str):
    """
    GET: Lease expiration and renewal metrics.
    
    Returns expiration count, renewal count, and renewal percentage
    for 30/60/90 day periods.
    """
    try:
        return await occupancy_service.get_lease_expirations(property_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/occupancy-trend")
async def get_occupancy_trend(
    property_id: str,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD). Defaults to 7 days ago."),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD). Defaults to today.")
):
    """
    GET: Occupancy trend comparing selected period vs equivalent prior period.
    
    Reconstructs historical occupancy from move-in/move-out dates.
    If custom dates provided, compares that range to the same duration before start_date.
    """
    try:
        return await occupancy_service.get_occupancy_trend(property_id, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/all-trends")
async def get_all_trends(
    property_id: str,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD). Defaults to 7 days ago."),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD). Defaults to today.")
):
    """
    GET: Comprehensive trends for ALL metrics - occupancy, exposure, and funnel.
    
    Compares selected period vs equivalent prior period for:
    - Occupancy: physical occupancy, vacant units
    - Exposure: move-ins, move-outs, net absorption
    - Funnel: leads, tours, applications, lease signs, conversion rates
    """
    try:
        return await occupancy_service.get_all_trends(property_id, start_date, end_date)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/summary", response_model=DashboardSummary)
async def get_summary(
    property_id: str,
    timeframe: Timeframe = Query(Timeframe.CM, description="Timeframe: cm, pm, or ytd"),
    include_pricing: bool = Query(True, description="Include pricing data")
):
    """
    GET: Complete dashboard summary for a property.
    
    Combines occupancy, exposure, leasing funnel, and pricing.
    """
    try:
        properties = await occupancy_service.get_property_list()
        property_info = next((p for p in properties if p.id == property_id), 
                            PropertyInfo(id=property_id, name=property_id))
        
        occupancy = await occupancy_service.get_occupancy_metrics(property_id, timeframe)
        exposure = await occupancy_service.get_exposure_metrics(property_id, timeframe)
        funnel = await occupancy_service.get_leasing_funnel(property_id, timeframe)
        
        pricing = None
        if include_pricing:
            try:
                pricing = await pricing_service.get_unit_pricing(property_id)
            except Exception:
                pass
        
        return DashboardSummary(
            property_info=property_info,
            timeframe=timeframe.value,
            occupancy=occupancy,
            exposure=exposure,
            leasing_funnel=funnel,
            pricing=pricing
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Drill-through endpoints ----

@router.get("/properties/{property_id}/units/raw")
async def get_units_raw(
    property_id: str,
    status: Optional[str] = Query(None, description="Filter by status: occupied, vacant, available, aged")
):
    """GET: Raw unit data for drill-through.
    
    Can filter by status:
    - occupied: Currently occupied units
    - vacant: All vacant units  
    - available: Units available for rent (RealPage: Available=T flag, includes vacant ready + occupied on notice)
    - aged: Vacant units with days_vacant > 90
    """
    try:
        units = await occupancy_service.get_raw_units(property_id)
        
        # Filter by status if provided
        if status:
            status = status.lower()
            if status == "available":
                units = [u for u in units if u.get("available", False)]
            elif status == "aged":
                units = [u for u in units if u.get("occupancy_status") == "vacant" and u.get("days_vacant", 0) > 90]
            else:
                units = [u for u in units if u.get("occupancy_status") == status]
        
        return units
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/residents/raw")
async def get_residents_raw(
    property_id: str,
    status: str = Query("all", description="Status filter: all, Current, Notice, Past, Future"),
    timeframe: Timeframe = Query(Timeframe.CM, description="Timeframe for filtering"),
    metric_filter: Optional[str] = Query(None, description="Metric filter: move_ins, move_outs, notices_30, notices_60")
):
    """
    GET: Raw resident data for drill-through.
    
    metric_filter ensures drill-through counts match metric counts exactly:
    - move_ins: Residents who moved in during the timeframe period
    - move_outs: Residents who moved out during the timeframe period  
    - notices_30: Notices with move-out in next 30 days
    - notices_60: Notices with move-out in next 60 days
    """
    try:
        return await occupancy_service.get_raw_residents(property_id, status, timeframe, metric_filter)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/prospects/raw")
async def get_prospects_raw(
    property_id: str,
    stage: Optional[str] = Query(None, description="Funnel stage: leads, tours, applications, lease_signs"),
    timeframe: Timeframe = Query(Timeframe.CM, description="Timeframe for filtering")
):
    """GET: Raw prospect data for drill-through."""
    try:
        return await occupancy_service.get_raw_prospects(property_id, stage, timeframe)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Amenities/Rentable Items endpoints ----

@router.get("/properties/{property_id}/amenities")
async def get_amenities(
    property_id: str,
    item_type: Optional[str] = Query(None, description="Filter by type: carport, storage, etc.")
):
    """
    GET: Rentable items (amenities, parking, storage) for a property.
    
    Returns inventory of rentable items with pricing and availability status.
    """
    try:
        return await occupancy_service.get_amenities(property_id, item_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/amenities/summary")
async def get_amenities_summary(property_id: str):
    """
    GET: Summary of amenities by type with revenue potential.
    """
    try:
        return await occupancy_service.get_amenities_summary(property_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---- Market Comps endpoints ----

@router.get("/submarkets")
async def get_submarkets():
    """GET: List of all submarkets from ALN API for market comps dropdown."""
    try:
        data = await market_comps_service.aln.get_all_submarkets()
        submarkets = data.get("value", [])
        
        # Transform to frontend-friendly format, sorted alphabetically
        result = [
            {
                "id": sm.get("SubMarketDescription", ""),
                "name": sm.get("SubMarketDescription", ""),
                "market": sm.get("Market", "")
            }
            for sm in submarkets
            if sm.get("SubMarketDescription")
        ]
        
        return result
    except Exception as e:
        print(f"[ALN] Error fetching submarkets: {e}")
        # Fallback to static list if ALN fails
        return [
            {"id": "South Asheville / Arden", "name": "South Asheville / Arden", "market": "AVL"},
            {"id": "Downtown", "name": "Downtown", "market": ""},
        ]


@router.get("/properties/{property_id}/location")
async def get_property_location(property_id: str):
    """GET: Property location for market comps submarket matching."""
    try:
        properties = await occupancy_service.get_property_list()
        prop = next((p for p in properties if p.id == property_id), None)
        
        if prop:
            return {
                "property_id": prop.id,
                "name": prop.name,
                "city": prop.city or "Santa Monica",
                "state": prop.state or "CA"
            }
        
        # Fallback if property not found
        return {
            "property_id": property_id,
            "name": property_id,
            "city": "Santa Monica",
            "state": "CA"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-comps", response_model=MarketCompsResponse)
async def get_market_comps(
    submarket: str = Query(..., description="Submarket name to search"),
    subject_property: Optional[str] = Query(None, description="Exclude this property from results"),
    limit: int = Query(20, description="Maximum number of comps to return"),
    min_units: Optional[int] = Query(None, description="Minimum number of units"),
    max_units: Optional[int] = Query(None, description="Maximum number of units"),
    min_year_built: Optional[int] = Query(None, description="Minimum year built"),
    max_year_built: Optional[int] = Query(None, description="Maximum year built"),
    amenities: Optional[str] = Query(None, description="Comma-separated amenities: pool,fitness,clubhouse,gated,parking,washer_dryer,pet_friendly")
):
    """
    GET: Market comparable properties from ALN with filters.
    
    Returns properties in the same submarket with average rents and occupancy.
    Supports filtering by building size, year built, and amenities.
    """
    try:
        amenities_list = [a.strip() for a in amenities.split(",")] if amenities else None
        return await market_comps_service.get_market_comps(
            submarket=submarket,
            subject_property=subject_property,
            limit=limit,
            min_units=min_units,
            max_units=max_units,
            min_year_built=min_year_built,
            max_year_built=max_year_built,
            amenities=amenities_list
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/market-comps/search", response_model=list[MarketComp])
async def search_market_comps(
    city: Optional[str] = Query(None, description="Filter by city"),
    state: Optional[str] = Query(None, description="Filter by state"),
    min_units: Optional[int] = Query(None, description="Minimum number of units"),
    max_units: Optional[int] = Query(None, description="Maximum number of units"),
    limit: int = Query(20, description="Maximum results")
):
    """GET: Search for market comps by criteria."""
    try:
        return await market_comps_service.search_comps(city, state, min_units, max_units, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Delinquency API
# =========================================================================

@router.get("/properties/{property_id}/delinquency")
async def get_delinquency(property_id: str):
    """
    GET: Delinquency, eviction, and collections data for a property.
    
    Data source: RealPage Delinquent and Prepaid Report (Excel).
    Returns: Total delinquent, prepaid, aging buckets, collections summary.
    """
    from app.services.delinquency_parser import parse_delinquency_report
    from pathlib import Path
    
    # Map property IDs to their delinquency report files
    # Currently only The Northern has a report
    PROPERTY_REPORTS = {
        "kairoi-the-northern": "Delinquent and Prepaid Report (3).xls",  # The Northern
    }
    
    report_filename = PROPERTY_REPORTS.get(property_id)
    if not report_filename:
        raise HTTPException(status_code=404, detail="No delinquency report available for this property")
    
    report_path = Path(__file__).parent.parent / "db" / report_filename
    
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Delinquency report file not found")
    
    try:
        return parse_delinquency_report(str(report_path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to parse delinquency report: {str(e)}")


# =========================================================================
# AI Chat API
# =========================================================================

@router.get("/chat/status")
async def get_chat_status():
    """GET: Check if AI chat is available."""
    return {
        "available": chat_service.is_available(),
        "message": "Chat ready" if chat_service.is_available() else "ANTHROPIC_API_KEY not configured"
    }


@router.post("/properties/{property_id}/chat")
async def chat_with_ai(
    property_id: str,
    request: dict
):
    """
    POST: Send a message to the AI chat agent.
    
    Request body:
    - message: User's question
    - history: Optional list of previous messages [{role, content}]
    
    The AI has context about the property's occupancy, pricing, exposure, and funnel metrics.
    """
    if not chat_service.is_available():
        raise HTTPException(status_code=503, detail="Chat service not available. Configure ANTHROPIC_API_KEY.")
    
    message = request.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    history = request.get("history", [])
    
    try:
        # Gather property data for context
        occupancy = await occupancy_service.get_occupancy_metrics(property_id, Timeframe.CM)
        exposure = await occupancy_service.get_exposure_metrics(property_id, Timeframe.CM)
        funnel = await occupancy_service.get_leasing_funnel(property_id, Timeframe.CM)
        pricing = await pricing_service.get_unit_pricing(property_id)
        
        # Get raw data for deeper context
        units_raw = await occupancy_service.get_raw_units(property_id)
        residents_raw = await occupancy_service.get_raw_residents(property_id, "all", Timeframe.CM)
        
        property_data = {
            "property_id": property_id,
            "property_name": occupancy.property_name,
            "occupancy": occupancy.model_dump() if hasattr(occupancy, 'model_dump') else vars(occupancy),
            "exposure": exposure.model_dump() if hasattr(exposure, 'model_dump') else vars(exposure),
            "funnel": funnel.model_dump() if hasattr(funnel, 'model_dump') else vars(funnel),
            "pricing": pricing.model_dump() if hasattr(pricing, 'model_dump') else vars(pricing),
            "units": units_raw,
            "residents": residents_raw,
        }
        
        response = await chat_service.chat(message, property_data, history)
        return {"response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
