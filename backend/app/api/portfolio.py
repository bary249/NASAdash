"""
Portfolio API Endpoints - Multi-property aggregated views.
READ-ONLY OPERATIONS ONLY.
"""
from fastapi import APIRouter, Query, HTTPException
from typing import List, Optional
from app.services.portfolio_service import PortfolioService
from app.models.unified import (
    AggregationMode,
    PMSSource,
    PMSConfig,
    UnifiedUnit,
    UnifiedResident,
    PortfolioOccupancy,
    PortfolioPricing,
    PortfolioSummary,
    PropertyMapping,
)
from app.property_config import (
    ALL_PROPERTIES,
    get_property,
    get_pms_config,
    list_all_properties,
)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

# Singleton service instance
_portfolio_service = None

def get_portfolio_service() -> PortfolioService:
    global _portfolio_service
    if _portfolio_service is None:
        _portfolio_service = PortfolioService()
    return _portfolio_service


def parse_property_configs(
    property_ids: str,
    pms_types: Optional[str] = None
) -> List[PMSConfig]:
    """
    Parse property IDs into PMSConfig list using the property registry.
    
    Args:
        property_ids: Comma-separated list of property IDs (must be registered)
        pms_types: Optional filter - if provided, only include matching PMS types
    
    Returns:
        List of PMSConfig objects from the registry
    """
    ids = [p.strip() for p in property_ids.split(",") if p.strip()]
    
    # Optional PMS type filter
    type_filter = None
    if pms_types:
        type_filter = [t.strip().lower() for t in pms_types.split(",")]
    
    configs = []
    for prop_id in ids:
        # Look up from registry
        if prop_id not in ALL_PROPERTIES:
            raise HTTPException(
                status_code=404,
                detail=f"Unknown property: {prop_id}. Available: {list(ALL_PROPERTIES.keys())}"
            )
        
        prop = ALL_PROPERTIES[prop_id]
        
        # Apply type filter if specified
        if type_filter and prop.pms_config.pms_type.value not in type_filter:
            continue
        
        configs.append(prop.pms_config)
    
    if not configs:
        raise HTTPException(
            status_code=400,
            detail="No properties matched the given filters"
        )
    
    return configs


@router.get("/occupancy", response_model=PortfolioOccupancy)
async def get_portfolio_occupancy(
    property_ids: str = Query(..., description="Comma-separated list of property IDs"),
    pms_types: Optional[str] = Query(None, description="Comma-separated list of PMS types (yardi/realpage)"),
    mode: AggregationMode = Query(
        AggregationMode.WEIGHTED_AVERAGE,
        description="Aggregation mode: weighted_avg or row_metrics"
    ),
):
    """
    Get aggregated occupancy metrics across multiple properties.
    
    **Aggregation Modes:**
    - `weighted_avg`: Calculate metrics per property, then weighted average by unit count
    - `row_metrics`: Combine all raw unit data, calculate metrics from combined dataset
    
    **Example:**
    ```
    GET /api/portfolio/occupancy?property_ids=prop1,prop2&mode=weighted_avg
    ```
    """
    try:
        configs = parse_property_configs(property_ids, pms_types)
        service = get_portfolio_service()
        return await service.get_portfolio_occupancy(configs, mode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pricing", response_model=PortfolioPricing)
async def get_portfolio_pricing(
    property_ids: str = Query(..., description="Comma-separated list of property IDs"),
    pms_types: Optional[str] = Query(None, description="Comma-separated list of PMS types (yardi/realpage)"),
    mode: AggregationMode = Query(
        AggregationMode.WEIGHTED_AVERAGE,
        description="Aggregation mode: weighted_avg or row_metrics"
    ),
):
    """
    Get aggregated pricing metrics across multiple properties.
    
    **Aggregation Modes:**
    - `weighted_avg`: Calculate metrics per property, then weighted average
    - `row_metrics`: Combine all raw lease/unit data, calculate from combined dataset
    
    **Example:**
    ```
    GET /api/portfolio/pricing?property_ids=prop1,prop2&mode=row_metrics
    ```
    """
    try:
        configs = parse_property_configs(property_ids, pms_types)
        service = get_portfolio_service()
        return await service.get_portfolio_pricing(configs, mode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=PortfolioSummary)
async def get_portfolio_summary(
    property_ids: str = Query(..., description="Comma-separated list of property IDs"),
    pms_types: Optional[str] = Query(None, description="Comma-separated list of PMS types (yardi/realpage)"),
    mode: AggregationMode = Query(
        AggregationMode.WEIGHTED_AVERAGE,
        description="Aggregation mode: weighted_avg or row_metrics"
    ),
):
    """
    Get complete portfolio summary with all metrics.
    
    Includes:
    - Occupancy metrics
    - Pricing metrics
    - Property breakdown
    - Unit and resident counts
    
    **Example:**
    ```
    GET /api/portfolio/summary?property_ids=prop1,prop2,prop3&mode=weighted_avg
    ```
    """
    try:
        configs = parse_property_configs(property_ids, pms_types)
        service = get_portfolio_service()
        return await service.get_portfolio_summary(configs, mode)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/units", response_model=List[UnifiedUnit])
async def get_portfolio_units(
    property_ids: str = Query(..., description="Comma-separated list of property IDs"),
    pms_types: Optional[str] = Query(None, description="Comma-separated list of PMS types (yardi/realpage)"),
    status: Optional[str] = Query(None, description="Filter by unit status (occupied/vacant/notice)"),
):
    """
    Get combined unit list from all properties (drill-through view).
    
    Each unit includes the `property_id` and `pms_source` for identification.
    
    **Example:**
    ```
    GET /api/portfolio/units?property_ids=prop1,prop2&status=vacant
    ```
    """
    try:
        configs = parse_property_configs(property_ids, pms_types)
        service = get_portfolio_service()
        units = await service.get_all_units(configs)
        
        # Filter by status if provided
        if status:
            units = [u for u in units if u.status == status.lower()]
        
        return units
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/residents", response_model=List[UnifiedResident])
async def get_portfolio_residents(
    property_ids: str = Query(..., description="Comma-separated list of property IDs"),
    pms_types: Optional[str] = Query(None, description="Comma-separated list of PMS types (yardi/realpage)"),
    status: Optional[str] = Query(None, description="Filter by resident status (current/future/past/notice)"),
):
    """
    Get combined resident list from all properties (drill-through view).
    
    Each resident includes the `property_id` and `pms_source` for identification.
    
    **Example:**
    ```
    GET /api/portfolio/residents?property_ids=prop1,prop2&status=current
    ```
    """
    try:
        configs = parse_property_configs(property_ids, pms_types)
        service = get_portfolio_service()
        residents = await service.get_all_residents(configs, status)
        return residents
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties")
async def list_portfolio_properties():
    """
    List all available properties in the portfolio registry.
    
    Returns property IDs, names, and their PMS source.
    """
    properties = list_all_properties()
    return [
        {
            "id": p.unified_id,
            "name": p.name,
            "pms_type": p.pms_config.pms_type.value,
        }
        for p in properties
    ]


@router.get("/health")
async def portfolio_health_check():
    """
    Health check endpoint for portfolio service.
    """
    return {
        "status": "ok",
        "service": "portfolio",
        "aggregation_modes": [m.value for m in AggregationMode],
        "supported_pms": [p.value for p in PMSSource],
        "registered_properties": list(ALL_PROPERTIES.keys()),
    }
