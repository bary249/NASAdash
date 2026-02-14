"""
Portfolio API Endpoints - Multi-property aggregated views.
READ-ONLY OPERATIONS ONLY.
"""
from fastapi import APIRouter, Query, HTTPException, Depends, Header
from typing import List, Optional
from app.services.portfolio_service import PortfolioService
from app.services.chat_service import chat_service
from app.services.occupancy_service import OccupancyService
from app.services.pricing_service import PricingService
from app.services.unit_query_service import unit_query_service
from app.models import Timeframe
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
    Falls back to unified.db for properties not in config.
    
    Args:
        property_ids: Comma-separated list of property IDs (must be registered or in unified.db)
        pms_types: Optional filter - if provided, only include matching PMS types
    
    Returns:
        List of PMSConfig objects from the registry or created from unified.db
    """
    import sqlite3
    from pathlib import Path
    
    ids = [p.strip() for p in property_ids.split(",") if p.strip()]
    
    # Optional PMS type filter
    type_filter = None
    if pms_types:
        type_filter = [t.strip().lower() for t in pms_types.split(",")]
    
    configs = []
    for prop_id in ids:
        # Look up from registry first
        if prop_id in ALL_PROPERTIES:
            prop = ALL_PROPERTIES[prop_id]
            # Apply type filter if specified
            if type_filter and prop.pms_config.pms_type.value not in type_filter:
                continue
            configs.append(prop.pms_config)
        else:
            # Try to find in unified.db
            db_path = Path(__file__).parent.parent / "db" / "data" / "unified.db"
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT pms_property_id, pms_source FROM unified_properties WHERE unified_property_id = ?",
                    (prop_id,)
                )
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    pms_property_id, pms_source = row
                    # Create a PMSConfig for unified.db properties
                    pms_type = PMSSource.REALPAGE if pms_source == 'realpage' else PMSSource.YARDI
                    if type_filter and pms_type.value not in type_filter:
                        continue
                    # Create config with unified_id as the property_id
                    config = PMSConfig(
                        pms_type=pms_type,
                        property_id=prop_id,
                        unified_property_id=prop_id,
                    )
                    configs.append(config)
                else:
                    # Not in registry or unified.db - skip silently
                    continue
            except Exception:
                continue
    
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
async def list_portfolio_properties(
    owner_group: Optional[str] = Query(None, description="Filter by owner group (e.g. 'PHH')"),
    authorization: Optional[str] = Header(None),
):
    """
    List all available properties in the portfolio registry.
    
    Returns property IDs, names, PMS source, and owner_group.
    If authenticated via JWT, forces owner_group to the user's group (cannot bypass).
    """
    # Enforce JWT group — override any query param
    if authorization:
        from app.services.auth_service import verify_token
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        payload = verify_token(token)
        if payload and payload.get("group"):
            owner_group = payload["group"]
    import sqlite3
    from pathlib import Path
    
    # Load owner_group from unified.db for all properties
    db_path = Path(__file__).parent.parent / "db" / "data" / "unified.db"
    owner_groups = {}
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT unified_property_id, owner_group FROM unified_properties")
        for row in cursor.fetchall():
            owner_groups[row[0]] = row[1] or "other"
        conn.close()
    except Exception:
        pass
    
    result = []
    seen_ids = set()
    
    # 1. Add configured properties
    properties = list_all_properties()
    for p in properties:
        og = owner_groups.get(p.unified_id, "other")
        if owner_group and og.lower() != owner_group.lower():
            continue
        result.append({
            "id": p.unified_id,
            "name": p.name,
            "pms_type": p.pms_config.pms_type.value,
            "owner_group": og,
        })
        seen_ids.add(p.unified_id)
    
    # Track names too to avoid duplicate property names
    seen_names = {p.name.lower() for p in properties}
    
    # 2. Add properties from unified.db that aren't in config
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT unified_property_id, name, pms_source, owner_group FROM unified_properties")
        for row in cursor.fetchall():
            prop_id, name, pms_source, og = row
            og = og or "other"
            if owner_group and og.lower() != owner_group.lower():
                continue
            # Skip if ID or name already seen
            if prop_id in seen_ids or (name and name.lower() in seen_names):
                continue
            result.append({
                "id": prop_id,
                "name": name,
                "pms_type": pms_source or "realpage",
                "owner_group": og,
            })
            seen_ids.add(prop_id)
            if name:
                seen_names.add(name.lower())
        conn.close()
    except Exception as e:
        pass  # Continue with config properties if db fails
    
    return result


@router.get("/owner-groups")
async def list_owner_groups():
    """Return distinct owner groups for filter dropdown."""
    import sqlite3
    from pathlib import Path
    
    db_path = Path(__file__).parent.parent / "db" / "data" / "unified.db"
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT owner_group FROM unified_properties WHERE owner_group IS NOT NULL ORDER BY owner_group")
        groups = [row[0] for row in cursor.fetchall()]
        conn.close()
        return groups
    except Exception:
        return ["other"]


@router.get("/watchlist")
async def get_watchlist(
    owner_group: Optional[str] = Query(None, description="Filter by owner group"),
    occ_threshold: float = Query(85.0, description="Occupancy % below which property is flagged"),
    delinq_threshold: float = Query(25000.0, description="Total delinquent $ above which property is flagged"),
    renewal_threshold: float = Query(30.0, description="Renewal rate % below which property is flagged"),
    review_threshold: float = Query(3.5, description="Google rating below which property is flagged"),
    authorization: Optional[str] = Header(None),
):
    # Enforce JWT group
    if authorization:
        from app.services.auth_service import verify_token
        token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
        payload = verify_token(token)
        if payload and payload.get("group"):
            owner_group = payload["group"]
    """
    GET: Watch List — underperforming properties.
    
    Scores each property against configurable thresholds:
    - Occupancy % < occ_threshold
    - Delinquency $ > delinq_threshold
    - Renewal rate (90d) < renewal_threshold
    - Google rating < review_threshold
    
    Returns properties sorted by number of flags (most flagged first).
    """
    import sqlite3
    from pathlib import Path
    
    db_path = Path(__file__).parent.parent / "db" / "data" / "unified.db"
    raw_db = Path(__file__).parent.parent / "db" / "data" / "realpage_raw.db"
    
    # Get all properties
    properties = []
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.unified_property_id, p.name, p.owner_group, p.pms_source,
                   o.total_units, o.occupied_units, o.vacant_units,
                   o.physical_occupancy, o.preleased_vacant, o.notice_units
            FROM unified_properties p
            LEFT JOIN unified_occupancy_metrics o
                ON o.unified_property_id = p.unified_property_id
                AND o.snapshot_date = (
                    SELECT MAX(snapshot_date) FROM unified_occupancy_metrics 
                    WHERE unified_property_id = p.unified_property_id
                )
            ORDER BY p.name
        """)
        
        for row in cursor.fetchall():
            og = row["owner_group"] or "other"
            if owner_group and og.lower() != owner_group.lower():
                continue
            
            prop_id = row["unified_property_id"]
            occ_pct = row["physical_occupancy"] or 0
            total_units = row["total_units"] or 0
            
            properties.append({
                "id": prop_id,
                "name": row["name"] or prop_id,
                "owner_group": og,
                "total_units": total_units,
                "occupancy_pct": occ_pct,
                "vacant": row["vacant_units"] or 0,
                "on_notice": row["notice_units"] or 0,
                "preleased": row["preleased_vacant"] or 0,
            })
        
        # Get delinquency totals per property
        try:
            cursor.execute("""
                SELECT unified_property_id,
                       SUM(CASE WHEN total_delinquent > 0 THEN total_delinquent ELSE 0 END) as total_delinq,
                       COUNT(CASE WHEN total_delinquent > 0 THEN 1 END) as delinq_units
                FROM unified_delinquency
                GROUP BY unified_property_id
            """)
            delinq_map = {}
            for row in cursor.fetchall():
                delinq_map[row["unified_property_id"]] = {
                    "total": row["total_delinq"] or 0,
                    "units": row["delinq_units"] or 0,
                }
        except Exception:
            delinq_map = {}
        
        # Get risk scores per property
        try:
            cursor.execute("""
                SELECT unified_property_id, avg_churn_score, at_risk_total
                FROM unified_risk_scores
                WHERE snapshot_date = (SELECT MAX(snapshot_date) FROM unified_risk_scores)
            """)
            risk_map = {}
            for row in cursor.fetchall():
                risk_map[row["unified_property_id"]] = {
                    "churn_score": row["avg_churn_score"] or 0,
                    "at_risk": row["at_risk_total"] or 0,
                }
        except Exception:
            risk_map = {}
        
        conn.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build watchlist: {str(e)}")
    
    # Get renewal rates — prefer report 4156 (realpage_lease_expiration_renewal),
    # fall back to realpage_leases
    renewal_map = {}
    try:
        raw_conn = sqlite3.connect(raw_db)
        rc = raw_conn.cursor()
        
        from app.property_config.properties import ALL_PROPERTIES as all_props
        date_expr = "date(substr(lease_end_date,7,4)||'-'||substr(lease_end_date,1,2)||'-'||substr(lease_end_date,4,2))"
        
        # Try report 4156 first for each property
        props_with_4156 = set()
        try:
            rc.execute("SELECT DISTINCT property_id FROM realpage_lease_expiration_renewal")
            props_with_4156 = {row[0] for row in rc.fetchall()}
        except Exception:
            pass
        
        for pid, p in all_props.items():
            try:
                site_id = p.pms_config.realpage_siteid
                if not site_id:
                    continue
                
                if site_id in props_with_4156:
                    rc.execute(f"""
                        SELECT COUNT(*) as total,
                               SUM(CASE WHEN decision = 'Renewed' THEN 1 ELSE 0 END) as renewed
                        FROM realpage_lease_expiration_renewal
                        WHERE property_id = ?
                          AND lease_end_date IS NOT NULL AND lease_end_date != ''
                          AND {date_expr} BETWEEN date('now') AND date('now', '+90 days')
                    """, (site_id,))
                else:
                    rc.execute("""
                        SELECT COUNT(*) as total,
                               SUM(CASE WHEN status_text = 'Current - Future' THEN 1 ELSE 0 END) as renewed
                        FROM realpage_leases
                        WHERE site_id = ?
                          AND status_text IN ('Current', 'Current - Future')
                          AND lease_end_date != ''
                          AND date(substr(lease_end_date,7,4)||'-'||substr(lease_end_date,1,2)||'-'||substr(lease_end_date,4,2))
                              BETWEEN date('now') AND date('now', '+90 days')
                    """, (site_id,))
                
                row = rc.fetchone()
                if row and row[0] > 0:
                    renewal_map[pid] = round(row[1] / row[0] * 100, 1)
            except Exception:
                continue
        raw_conn.close()
    except Exception:
        pass
    
    # Get Google ratings from reviews cache
    review_map = {}
    try:
        import json
        cache_path = Path(__file__).parent.parent / "db" / "data" / "google_reviews_cache.json"
        if cache_path.exists():
            cache = json.loads(cache_path.read_text())
            for pid, entry in cache.items():
                data = entry.get("data", {})
                if data.get("rating"):
                    review_map[pid] = data["rating"]
    except Exception:
        pass
    
    # Score each property
    watchlist = []
    for prop in properties:
        pid = prop["id"]
        flags = []
        
        # Occupancy check
        if prop["occupancy_pct"] > 0 and prop["occupancy_pct"] < occ_threshold:
            flags.append({
                "metric": "occupancy",
                "label": f"Occupancy {prop['occupancy_pct']}% (< {occ_threshold}%)",
                "severity": "high" if prop["occupancy_pct"] < occ_threshold - 10 else "medium",
                "value": prop["occupancy_pct"],
                "threshold": occ_threshold,
            })
        
        # Delinquency check
        delinq = delinq_map.get(pid, {})
        delinq_total = delinq.get("total", 0)
        if delinq_total > delinq_threshold:
            flags.append({
                "metric": "delinquency",
                "label": f"Delinquent ${delinq_total:,.0f} (> ${delinq_threshold:,.0f})",
                "severity": "high" if delinq_total > delinq_threshold * 2 else "medium",
                "value": delinq_total,
                "threshold": delinq_threshold,
            })
        
        # Renewal rate check
        renewal_pct = renewal_map.get(pid, None)
        if renewal_pct is not None and renewal_pct < renewal_threshold:
            flags.append({
                "metric": "renewal_rate",
                "label": f"Renewal rate {renewal_pct}% (< {renewal_threshold}%)",
                "severity": "high" if renewal_pct < renewal_threshold - 20 else "medium",
                "value": renewal_pct,
                "threshold": renewal_threshold,
            })
        
        # Review rating check
        rating = review_map.get(pid, None)
        if rating is not None and rating < review_threshold:
            flags.append({
                "metric": "review_rating",
                "label": f"Rating {rating} (< {review_threshold})",
                "severity": "high" if rating < 3.0 else "medium",
                "value": rating,
                "threshold": review_threshold,
            })
        
        prop["delinquent_total"] = delinq_total
        prop["delinquent_units"] = delinq.get("units", 0)
        prop["renewal_rate_90d"] = renewal_pct
        prop["google_rating"] = rating
        prop["churn_score"] = risk_map.get(pid, {}).get("churn_score")
        prop["at_risk_residents"] = risk_map.get(pid, {}).get("at_risk", 0)
        prop["flags"] = flags
        prop["flag_count"] = len(flags)
        
        watchlist.append(prop)
    
    # Sort: most flags first, then by occupancy ascending
    watchlist.sort(key=lambda p: (-p["flag_count"], p["occupancy_pct"]))
    
    flagged = [p for p in watchlist if p["flag_count"] > 0]
    
    return {
        "total_properties": len(watchlist),
        "flagged_count": len(flagged),
        "thresholds": {
            "occupancy_pct": occ_threshold,
            "delinquent_total": delinq_threshold,
            "renewal_rate_90d": renewal_threshold,
            "google_rating": review_threshold,
        },
        "watchlist": watchlist,
    }


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


@router.get("/risk-scores")
async def get_portfolio_risk_scores(
    property_ids: Optional[str] = Query(None, description="Comma-separated list of property IDs. If omitted, returns all."),
):
    """
    GET: Aggregated risk scores across properties.
    
    Returns per-property churn and delinquency predictions plus portfolio totals.
    """
    import sqlite3
    from pathlib import Path
    
    db_path = Path(__file__).parent.parent / "db" / "data" / "unified.db"
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if property_ids:
            ids = [p.strip() for p in property_ids.split(",") if p.strip()]
            placeholders = ",".join("?" * len(ids))
            cursor.execute(f"""
                SELECT r.*, p.name as property_name
                FROM unified_risk_scores r
                LEFT JOIN unified_properties p
                    ON r.unified_property_id = p.unified_property_id
                WHERE r.unified_property_id IN ({placeholders})
                  AND r.snapshot_date = (
                      SELECT MAX(snapshot_date) FROM unified_risk_scores
                      WHERE unified_property_id = r.unified_property_id
                  )
                ORDER BY r.avg_churn_score ASC
            """, ids)
        else:
            cursor.execute("""
                SELECT r.*, p.name as property_name
                FROM unified_risk_scores r
                LEFT JOIN unified_properties p
                    ON r.unified_property_id = p.unified_property_id
                WHERE r.snapshot_date = (
                    SELECT MAX(snapshot_date) FROM unified_risk_scores
                    WHERE unified_property_id = r.unified_property_id
                )
                ORDER BY r.avg_churn_score ASC
            """)
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return {"properties": [], "summary": None}
        
        properties = []
        total_scored = 0
        weighted_churn = 0
        weighted_delinq = 0
        total_churn_high = 0
        total_delinq_high = 0
        
        for row in rows:
            n = row["total_scored"]
            total_scored += n
            weighted_churn += row["avg_churn_score"] * n
            weighted_delinq += row["avg_delinquency_score"] * n
            total_churn_high += row["churn_high_count"]
            total_delinq_high += row["delinq_high_count"]
            
            properties.append({
                "property_id": row["unified_property_id"],
                "property_name": row["property_name"] or row["unified_property_id"],
                "total_scored": n,
                "avg_churn_score": row["avg_churn_score"],
                "avg_delinquency_score": row["avg_delinquency_score"],
                "churn_high": row["churn_high_count"],
                "churn_medium": row["churn_medium_count"],
                "churn_low": row["churn_low_count"],
                "delinq_high": row["delinq_high_count"],
                "delinq_medium": row["delinq_medium_count"],
                "delinq_low": row["delinq_low_count"],
                "avg_tenure_months": row["avg_tenure_months"],
                "avg_rent": row["avg_rent"],
                "avg_open_tickets": row["avg_open_tickets"],
                "snapshot_date": row["snapshot_date"],
            })
        
        summary = {
            "total_properties": len(rows),
            "total_scored": total_scored,
            "avg_churn_score": round(weighted_churn / total_scored, 3) if total_scored > 0 else 0,
            "avg_delinquency_score": round(weighted_delinq / total_scored, 3) if total_scored > 0 else 0,
            "total_churn_high_risk": total_churn_high,
            "total_delinq_high_risk": total_delinq_high,
        }
        
        return {"properties": properties, "summary": summary}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get portfolio risk scores: {str(e)}")


# Service instances for chat
_occupancy_service = OccupancyService()
_pricing_service = PricingService()


@router.post("/chat")
async def portfolio_chat(request: dict):
    """
    POST: Chat with AI about portfolio-level data.
    
    The AI acts as an Asset Manager / Owner Analyst, providing strategic insights
    across all properties in the portfolio.
    
    Request body:
    - message: User's question (e.g., "Give me highlights about my portfolio")
    - history: Optional list of previous messages [{role, content}]
    
    The AI has context about all properties' occupancy, pricing, exposure, and funnel metrics.
    """
    if not chat_service.is_available():
        raise HTTPException(status_code=503, detail="Chat service not available. Configure ANTHROPIC_API_KEY.")
    
    message = request.get("message", "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    history = request.get("history", [])
    
    try:
        # Gather data from ALL properties
        properties_data = []
        total_units = 0
        total_vacant = 0
        total_in_place_rent = 0
        total_asking_rent = 0
        weighted_occupancy = 0
        
        for prop_id, prop_mapping in ALL_PROPERTIES.items():
            try:
                # Fetch metrics for each property
                occupancy = await _occupancy_service.get_occupancy_metrics(prop_id, Timeframe.CM)
                funnel = await _occupancy_service.get_leasing_funnel(prop_id, Timeframe.CM)
                pricing = await _pricing_service.get_unit_pricing(prop_id)
                
                occ_dict = occupancy.model_dump() if hasattr(occupancy, 'model_dump') else vars(occupancy)
                funnel_dict = funnel.model_dump() if hasattr(funnel, 'model_dump') else vars(funnel)
                pricing_dict = pricing.model_dump() if hasattr(pricing, 'model_dump') else vars(pricing)
                
                units = occ_dict.get("total_units", 0)
                vacant = occ_dict.get("vacant_units", 0)
                phys_occ = occ_dict.get("physical_occupancy", 0)
                
                properties_data.append({
                    "property_id": prop_id,
                    "name": prop_mapping.name,
                    "occupancy": occ_dict,
                    "funnel": funnel_dict,
                    "pricing": {
                        "avg_in_place_rent": pricing_dict.get("total_in_place_rent", 0),
                        "avg_asking_rent": pricing_dict.get("total_asking_rent", 0),
                    },
                })
                
                # Accumulate for portfolio totals
                total_units += units
                total_vacant += vacant
                weighted_occupancy += phys_occ * units
                total_in_place_rent += pricing_dict.get("total_in_place_rent", 0) * units
                total_asking_rent += pricing_dict.get("total_asking_rent", 0) * units
                
            except Exception as e:
                # Log but continue with other properties
                print(f"Warning: Could not fetch data for {prop_id}: {e}")
                continue
        
        # Calculate portfolio summary
        portfolio_data = {
            "properties": properties_data,
            "summary": {
                "total_units": total_units,
                "total_vacant": total_vacant,
                "avg_occupancy": weighted_occupancy / total_units if total_units > 0 else 0,
                "avg_in_place_rent": total_in_place_rent / total_units if total_units > 0 else 0,
                "avg_asking_rent": total_asking_rent / total_units if total_units > 0 else 0,
            }
        }
        
        response = await chat_service.portfolio_chat(message, portfolio_data, history)
        
        # Check if this is a unit-level query and add structured data
        message_lower = message.lower()
        table_data = []
        columns = []
        actions = []
        
        # Detect renewal queries
        if 'renewal' in message_lower or 'expir' in message_lower or 'lease' in message_lower:
            # Get renewal data from all properties
            for prop_data in properties_data:
                prop_id = prop_data.get("property_id")
                prop_name = prop_data.get("name", "")
                
                # Get high-value renewals (>$3000/mo)
                min_rent = 3000 if 'high-value' in message_lower or 'high value' in message_lower else None
                days = 90
                if '30 day' in message_lower:
                    days = 30
                elif '60 day' in message_lower:
                    days = 60
                
                renewals = unit_query_service.get_upcoming_renewals(prop_id, days_ahead=days, min_rent=min_rent)
                for r in renewals:
                    r['property'] = prop_name
                table_data.extend(renewals)
            
            if table_data:
                columns = [
                    {'key': 'unit', 'label': 'Unit'},
                    {'key': 'resident', 'label': 'Resident'},
                    {'key': 'monthlyRent', 'label': 'Monthly Rent'},
                    {'key': 'expires', 'label': 'Expires'},
                    {'key': 'riskLevel', 'label': 'Risk Level'},
                    {'key': 'keyFactors', 'label': 'Key Factors'},
                    {'key': 'offerSent', 'label': 'Offer Sent?'},
                ]
                actions = [
                    {'label': 'Trigger personalized re-engagement workflow'},
                    {'label': 'Review maintenance tickets and assign priority repairs'},
                    {'label': 'Generate renewal offer letters'},
                ]
        
        # Detect delinquency queries
        elif 'delinquen' in message_lower or 'past due' in message_lower or 'balance' in message_lower:
            for prop_data in properties_data:
                prop_id = prop_data.get("property_id")
                prop_name = prop_data.get("name", "")
                
                min_days = 0
                if '30 day' in message_lower:
                    min_days = 30
                
                delinquents = unit_query_service.get_delinquent_units(prop_id, min_days_late=min_days)
                for d in delinquents:
                    d['property'] = prop_name
                table_data.extend(delinquents)
            
            if table_data:
                columns = [
                    {'key': 'unit', 'label': 'Unit'},
                    {'key': 'resident', 'label': 'Resident'},
                    {'key': 'amountDue', 'label': 'Amount Due'},
                    {'key': 'daysLate', 'label': 'Days Late'},
                    {'key': 'status', 'label': 'Status'},
                    {'key': 'lastContact', 'label': 'Last Contact'},
                ]
                actions = [
                    {'label': "Flag 'promised to pay' units for onsite to follow up"},
                    {'label': 'Review eviction timeline'},
                    {'label': 'Generate weekly delinquency trend report'},
                ]
        
        # Detect vacant unit queries
        elif 'vacant' in message_lower or 'empty' in message_lower:
            aged_only = 'aged' in message_lower or '90' in message_lower
            for prop_data in properties_data:
                prop_id = prop_data.get("property_id")
                prop_name = prop_data.get("name", "")
                
                vacants = unit_query_service.get_vacant_units(prop_id, aged_only=aged_only)
                for v in vacants:
                    v['property'] = prop_name
                table_data.extend(vacants)
            
            if table_data:
                columns = [
                    {'key': 'unit', 'label': 'Unit'},
                    {'key': 'floorplan', 'label': 'Floorplan'},
                    {'key': 'bedrooms', 'label': 'Beds'},
                    {'key': 'marketRent', 'label': 'Market Rent'},
                    {'key': 'daysVacant', 'label': 'Days Vacant'},
                    {'key': 'status', 'label': 'Status'},
                ]
                actions = [
                    {'label': 'Review pricing strategy for aged units'},
                    {'label': 'Generate marketing campaign for vacant units'},
                    {'label': 'Schedule make-ready inspections'},
                ]
        
        return {
            "response": response,
            "columns": columns,
            "data": table_data,
            "actions": actions,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
