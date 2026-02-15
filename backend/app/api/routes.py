"""
API Routes - Owner Dashboard V2
READ-ONLY endpoints. All operations are GET-only.
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from datetime import datetime

from app.db.schema import UNIFIED_DB_PATH, REALPAGE_DB_PATH
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
    import sqlite3
    from pathlib import Path
    from datetime import date
    
    # Try database first for properties without full PMS config
    db_path = UNIFIED_DB_PATH
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT exposure_30_days, exposure_60_days, notice_units, vacant_units
            FROM unified_occupancy_metrics
            WHERE unified_property_id = ?
            ORDER BY snapshot_date DESC
            LIMIT 1
        """, (property_id,))
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0] is not None:
            today = date.today()
            return ExposureMetrics(
                property_id=property_id,
                timeframe=timeframe.value,
                period_start=today.replace(day=1).isoformat(),
                period_end=today.isoformat(),
                exposure_30_days=row[0] or 0,
                exposure_60_days=row[1] or 0,
                notices_total=row[2] or 0,
                notices_30_days=int((row[2] or 0) * 0.5),
                notices_60_days=row[2] or 0,
                pending_moveouts_30=int((row[2] or 0) * 0.5),
                pending_moveouts_60=row[2] or 0,
                pending_moveins_30=0,
                pending_moveins_60=0,
                move_ins=0,
                move_outs=0,
                net_absorption=0,
            )
    except Exception as db_err:
        print(f"DB fallback failed: {db_err}")
    
    # Fall back to live API call
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
    
    # Fall back to realpage_activity table
    try:
        from app.property_config.properties import ALL_PROPERTIES
        from app.services.timeframe import get_date_range
        import sqlite3
        prop_cfg = ALL_PROPERTIES.get(property_id)
        if prop_cfg and prop_cfg.pms_config.realpage_siteid:
            site_id = prop_cfg.pms_config.realpage_siteid
            raw_db = REALPAGE_DB_PATH
            if raw_db.exists():
                conn = sqlite3.connect(str(raw_db))
                c = conn.cursor()
                
                # Filter by timeframe — activity_date is MM/DD/YYYY format
                period_start, period_end = get_date_range(timeframe)
                start_iso = period_start.strftime("%Y-%m-%d")
                end_iso = period_end.strftime("%Y-%m-%d")
                
                date_expr = "date(substr(activity_date,7,4) || '-' || substr(activity_date,1,2) || '-' || substr(activity_date,4,2))"
                
                # Count unique prospects per funnel stage (deduplicated by resident_name)
                LEAD_TYPES_SQL = "'Online Leasing guest card','Call Center guest card','Internet','Phone call','Event'"
                TOUR_TYPES_SQL = "'Visit','Visit (return)'"
                APP_TYPES_SQL = "'Online Leasing pre-qualify','Identity Verification','Online Leasing Agreement'"
                LEASE_TYPES_SQL = "'Leased'"
                
                TOUR_TYPES_ALL_SQL = "'Visit','Visit (return)','Videotelephony - Tour'"
                c.execute(f"""
                    SELECT
                        (SELECT COUNT(DISTINCT resident_name) FROM realpage_activity
                         WHERE property_id = ? AND activity_type IN ({LEAD_TYPES_SQL})
                         AND resident_name IS NOT NULL AND resident_name != ''
                         AND activity_date IS NOT NULL AND activity_date != ''
                         AND {date_expr} BETWEEN ? AND ?),
                        (SELECT COUNT(DISTINCT resident_name) FROM realpage_activity
                         WHERE property_id = ? AND activity_type IN ({TOUR_TYPES_SQL})
                         AND resident_name IS NOT NULL AND resident_name != ''
                         AND activity_date IS NOT NULL AND activity_date != ''
                         AND {date_expr} BETWEEN ? AND ?),
                        (SELECT COUNT(DISTINCT resident_name) FROM realpage_activity
                         WHERE property_id = ? AND activity_type IN ({APP_TYPES_SQL})
                         AND resident_name IS NOT NULL AND resident_name != ''
                         AND activity_date IS NOT NULL AND activity_date != ''
                         AND {date_expr} BETWEEN ? AND ?),
                        (SELECT COUNT(DISTINCT resident_name) FROM realpage_activity
                         WHERE property_id = ? AND activity_type IN ({LEASE_TYPES_SQL})
                         AND resident_name IS NOT NULL AND resident_name != ''
                         AND activity_date IS NOT NULL AND activity_date != ''
                         AND {date_expr} BETWEEN ? AND ?),
                        -- Apps without Tour: applied prospects who never had a tour/visit
                        (SELECT COUNT(DISTINCT resident_name) FROM realpage_activity
                         WHERE property_id = ? AND activity_type IN ({APP_TYPES_SQL})
                         AND resident_name IS NOT NULL AND resident_name != ''
                         AND activity_date IS NOT NULL AND activity_date != ''
                         AND {date_expr} BETWEEN ? AND ?
                         AND resident_name NOT IN (
                             SELECT DISTINCT resident_name FROM realpage_activity
                             WHERE property_id = ? AND activity_type IN ({TOUR_TYPES_ALL_SQL})
                             AND resident_name IS NOT NULL AND resident_name != ''
                         )),
                        -- Tour to App: prospects who toured AND applied
                        (SELECT COUNT(DISTINCT a.resident_name) FROM realpage_activity a
                         WHERE a.property_id = ? AND a.activity_type IN ({APP_TYPES_SQL})
                         AND a.resident_name IS NOT NULL AND a.resident_name != ''
                         AND a.activity_date IS NOT NULL AND a.activity_date != ''
                         AND {date_expr} BETWEEN ? AND ?
                         AND a.resident_name IN (
                             SELECT DISTINCT t.resident_name FROM realpage_activity t
                             WHERE t.property_id = ? AND t.activity_type IN ({TOUR_TYPES_ALL_SQL})
                             AND t.resident_name IS NOT NULL AND t.resident_name != ''
                         ))
                """, (site_id, start_iso, end_iso,
                      site_id, start_iso, end_iso,
                      site_id, start_iso, end_iso,
                      site_id, start_iso, end_iso,
                      site_id, start_iso, end_iso, site_id,
                      site_id, start_iso, end_iso, site_id))
                row = c.fetchone()
                conn.close()
                
                if row and any(v > 0 for v in row[:4]):
                    leads, tours, applications, lease_signs, sight_unseen, tour_to_app = row
                    
                    l2t = round(tours / leads * 100, 1) if leads > 0 else 0.0
                    t2a = round(applications / tours * 100, 1) if tours > 0 else 0.0
                    a2l = round(lease_signs / applications * 100, 1) if applications > 0 else 0.0
                    l2l = round(lease_signs / leads * 100, 1) if leads > 0 else 0.0
                    
                    # Step 1.2: Derive marketing metrics from prospect-level activity
                    avg_days_to_lease = None
                    app_completion_rate = None
                    app_approval_rate = None
                    try:
                        conn2 = sqlite3.connect(str(raw_db))
                        c2 = conn2.cursor()
                        date_expr = "date(substr(activity_date,7,4) || '-' || substr(activity_date,1,2) || '-' || substr(activity_date,4,2))"
                        
                        # Avg days to lease: first_contact → leased per prospect
                        c2.execute(f"""
                            SELECT resident_name,
                                   MIN({date_expr}) as first_contact,
                                   MAX(CASE WHEN activity_type = 'Leased' THEN {date_expr} END) as leased_date
                            FROM realpage_activity
                            WHERE property_id = ?
                              AND resident_name IS NOT NULL AND resident_name != ''
                              AND activity_date IS NOT NULL AND activity_date != ''
                              AND {date_expr} BETWEEN ? AND ?
                            GROUP BY resident_name
                            HAVING leased_date IS NOT NULL
                        """, (site_id, start_iso, end_iso))
                        lease_deltas = []
                        for r in c2.fetchall():
                            if r[1] and r[2]:
                                from datetime import datetime as dt
                                try:
                                    d1 = dt.strptime(r[1], "%Y-%m-%d")
                                    d2 = dt.strptime(r[2], "%Y-%m-%d")
                                    delta = (d2 - d1).days
                                    if delta >= 0:
                                        lease_deltas.append(delta)
                                except ValueError:
                                    pass
                        if lease_deltas:
                            avg_days_to_lease = round(sum(lease_deltas) / len(lease_deltas), 1)
                        
                        # App completion rate: pre-qualify → agreement per prospect
                        c2.execute(f"""
                            SELECT resident_name,
                                   GROUP_CONCAT(DISTINCT activity_type) as activities
                            FROM realpage_activity
                            WHERE property_id = ?
                              AND resident_name IS NOT NULL AND resident_name != ''
                              AND activity_date IS NOT NULL AND activity_date != ''
                              AND {date_expr} BETWEEN ? AND ?
                              AND activity_type IN ('Online Leasing pre-qualify', 'Online Leasing Agreement', 'Leased')
                            GROUP BY resident_name
                        """, (site_id, start_iso, end_iso))
                        prequalify_count = 0
                        agreement_count = 0
                        leased_from_agreement = 0
                        for r in c2.fetchall():
                            acts = r[1] or ''
                            has_pq = 'Online Leasing pre-qualify' in acts
                            has_ag = 'Online Leasing Agreement' in acts
                            has_ls = 'Leased' in acts
                            if has_pq:
                                prequalify_count += 1
                                if has_ag:
                                    agreement_count += 1
                            if has_ag:
                                if has_ls:
                                    leased_from_agreement += 1
                        
                        if prequalify_count > 0:
                            app_completion_rate = round(agreement_count / prequalify_count * 100, 1)
                        # App approval rate: agreement → leased
                        total_agreements = agreement_count  # Those who reached agreement
                        if total_agreements > 0:
                            app_approval_rate = round(leased_from_agreement / total_agreements * 100, 1)
                        
                        conn2.close()
                    except Exception as e:
                        import logging
                        logging.warning(f"Could not compute marketing metrics for {property_id}: {e}")
                    
                    return LeasingFunnelMetrics(
                        property_id=property_id,
                        timeframe=timeframe.value,
                        period_start=start_iso,
                        period_end=end_iso,
                        leads=leads,
                        tours=tours,
                        applications=applications,
                        lease_signs=lease_signs,
                        denials=0,
                        sight_unseen=sight_unseen or 0,
                        tour_to_app=tour_to_app or 0,
                        lead_to_tour_rate=l2t,
                        tour_to_app_rate=t2a,
                        app_to_lease_rate=a2l,
                        lead_to_lease_rate=l2l,
                        avg_days_to_lease=avg_days_to_lease,
                        app_completion_rate=app_completion_rate,
                        app_approval_rate=app_approval_rate,
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
async def get_tradeouts(property_id: str, days: Optional[int] = None):
    """
    GET: Lease trade-out data.
    
    Trade-out = when a resident moves out and a new one moves in.
    Compares prior lease rent vs new lease rent for same unit.
    
    Query params:
    - days: Optional filter for trailing window (e.g. 7, 30)
    
    Returns:
    - tradeouts: List of individual trade-outs with rent change
    - summary: Average rent change metrics
    """
    try:
        return await pricing_service.get_lease_tradeouts(property_id, days=days)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/renewals")
async def get_renewal_leases(
    property_id: str,
    days: Optional[int] = None,
    month: Optional[str] = Query(None, description="Calendar month filter (e.g. '2026-04')")
):
    """
    GET: Renewal lease data.
    
    Shows renewal rent vs prior resident rent for residents who renewed.
    Prior rent = what the resident was paying before the renewal.
    
    Query params:
    - month: Calendar month filter (e.g. '2026-04') — preferred
    - days: Optional trailing window in days (fallback)
    
    Returns:
    - renewals: List of individual renewals with prior rent comparison
    - summary: Average renewal rent, prior rent, and variance
    """
    try:
        return await pricing_service.get_renewal_leases(property_id, days=days, month=month)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/turn-time")
async def get_turn_time(property_id: str):
    """
    GET: Average unit turn time for a property.
    
    Calculates days between former lease inactive_date and next lease move_in_date
    for the same unit using realpage_leases data.
    """
    import sqlite3
    from pathlib import Path
    
    raw_db = REALPAGE_DB_PATH
    
    try:
        from app.property_config.properties import get_pms_config
        pms_config = get_pms_config(property_id)
        site_id = pms_config.realpage_siteid
    except Exception:
        raise HTTPException(status_code=404, detail="Property not configured for RealPage")
    
    if not site_id:
        raise HTTPException(status_code=404, detail="No RealPage site_id for property")
    
    try:
        conn = sqlite3.connect(str(raw_db))
        c = conn.cursor()
        
        # Convert MM/DD/YYYY dates to ISO for julianday()
        date_iso = "substr({col},7,4)||'-'||substr({col},1,2)||'-'||substr({col},4,2)"
        mi_iso = date_iso.format(col="move_in_date")
        ia_iso = date_iso.format(col="inactive_date")
        
        c.execute(f"""
            WITH unit_leases AS (
                SELECT unit_id, move_in_date, inactive_date, status_text,
                       {mi_iso} as mi_iso,
                       {ia_iso} as ia_iso,
                       ROW_NUMBER() OVER (PARTITION BY unit_id ORDER BY 
                           substr(move_in_date,7,4)||substr(move_in_date,1,2)||substr(move_in_date,4,2) DESC) as rn
                FROM realpage_leases
                WHERE site_id = ?
                  AND unit_id IS NOT NULL AND unit_id != ''
                  AND move_in_date IS NOT NULL AND move_in_date != ''
                  AND status_text IN ('Current', 'Former', 'Current - Past')
            ),
            turns AS (
                SELECT cur.unit_id,
                       prev.ia_iso as move_out,
                       cur.mi_iso as move_in,
                       CAST(julianday(cur.mi_iso) - julianday(prev.ia_iso) AS INTEGER) as gap_days
                FROM unit_leases cur
                JOIN unit_leases prev ON cur.unit_id = prev.unit_id
                WHERE cur.rn = 1 AND prev.rn = 2
                  AND prev.ia_iso IS NOT NULL AND prev.ia_iso NOT LIKE '--%'
                  AND prev.status_text = 'Former'
                  AND CAST(julianday(cur.mi_iso) - julianday(prev.ia_iso) AS INTEGER) BETWEEN 0 AND 180
            )
            SELECT COUNT(*) as turn_count, ROUND(AVG(gap_days), 1) as avg_days,
                   MIN(gap_days) as min_days, MAX(gap_days) as max_days,
                   ROUND(AVG(CASE WHEN gap_days <= 30 THEN gap_days END), 1) as avg_under_30
            FROM turns
        """, (site_id,))
        
        row = c.fetchone()
        conn.close()
        
        if not row or row[0] == 0:
            return {
                "property_id": property_id,
                "turn_count": 0,
                "avg_turn_days": None,
                "min_turn_days": None,
                "max_turn_days": None,
                "avg_under_30_days": None,
            }
        
        return {
            "property_id": property_id,
            "turn_count": row[0],
            "avg_turn_days": row[1],
            "min_turn_days": row[2],
            "max_turn_days": row[3],
            "avg_under_30_days": row[4],
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate turn time: {str(e)}")


@router.get("/properties/{property_id}/loss-to-lease")
async def get_loss_to_lease(property_id: str):
    """
    GET: Loss-to-lease estimate for a property.
    
    Loss-to-lease = (avg_market_rent - avg_actual_rent) × occupied_units
    Expressed as total dollars and as percentage of potential gross rent.
    Source: unified_pricing_metrics (asking vs in-place) + unified_occupancy_metrics.
    """
    import sqlite3
    from pathlib import Path
    
    uni_db = UNIFIED_DB_PATH
    
    # Normalize property_id
    normalized_id = property_id
    if property_id.startswith("kairoi-"):
        normalized_id = property_id.replace("kairoi-", "").replace("-", "_")
    
    try:
        conn = sqlite3.connect(str(uni_db))
        c = conn.cursor()
        
        # Get weighted avg asking and in-place rent from pricing metrics
        c.execute("""
            SELECT 
                SUM(asking_rent * unit_count) / NULLIF(SUM(CASE WHEN asking_rent > 0 THEN unit_count ELSE 0 END), 0) as avg_asking,
                SUM(in_place_rent * unit_count) / NULLIF(SUM(CASE WHEN in_place_rent > 0 THEN unit_count ELSE 0 END), 0) as avg_in_place,
                SUM(CASE WHEN asking_rent > 0 THEN unit_count ELSE 0 END) as units_with_data
            FROM unified_pricing_metrics
            WHERE unified_property_id = ? OR unified_property_id = ?
        """, (property_id, normalized_id))
        pricing_row = c.fetchone()
        
        # Get occupancy data
        c.execute("""
            SELECT occupied_units, total_units
            FROM unified_occupancy_metrics
            WHERE unified_property_id = ? OR unified_property_id = ?
            ORDER BY snapshot_date DESC LIMIT 1
        """, (property_id, normalized_id))
        occ_row = c.fetchone()
        conn.close()
        
        if not pricing_row or not pricing_row[0] or not pricing_row[1]:
            return {
                "property_id": property_id,
                "avg_market_rent": None,
                "avg_actual_rent": None,
                "loss_per_unit": None,
                "total_loss_to_lease": None,
                "loss_to_lease_pct": None,
                "occupied_units": occ_row[0] if occ_row else None,
                "data_available": False,
            }
        
        avg_asking = round(pricing_row[0], 2)
        avg_in_place = round(pricing_row[1], 2)
        occupied_units = occ_row[0] if occ_row else 0
        total_units = occ_row[1] if occ_row else 0
        
        loss_per_unit = round(avg_asking - avg_in_place, 2)
        total_loss = round(loss_per_unit * occupied_units, 2)
        potential_gross = avg_asking * total_units if total_units > 0 else 0
        loss_pct = round((total_loss / potential_gross) * 100, 1) if potential_gross > 0 else 0
        
        return {
            "property_id": property_id,
            "avg_market_rent": avg_asking,
            "avg_actual_rent": avg_in_place,
            "loss_per_unit": loss_per_unit,
            "total_loss_to_lease": total_loss,
            "loss_to_lease_pct": loss_pct,
            "occupied_units": occupied_units,
            "total_units": total_units,
            "data_available": True,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate loss-to-lease: {str(e)}")


@router.get("/properties/{property_id}/projected-occupancy")
async def get_projected_occupancy(property_id: str):
    """
    GET: Projected occupancy at 30, 60, and 90 days.
    
    Formula: current_occupied + scheduled_move_ins - expected_move_outs
    Sources:
    - Current: unified_occupancy_metrics
    - Move-ins: box_score preleased_vacant (already signed leases on vacant units)
    - Move-outs: lease expirations not yet renewed (from realpage_leases)
    """
    import sqlite3
    from pathlib import Path
    
    uni_db = UNIFIED_DB_PATH
    raw_db = REALPAGE_DB_PATH
    
    normalized_id = property_id
    if property_id.startswith("kairoi-"):
        normalized_id = property_id.replace("kairoi-", "").replace("-", "_")
    
    try:
        # Get current occupancy from unified
        uni_conn = sqlite3.connect(str(uni_db))
        uc = uni_conn.cursor()
        uc.execute("""
            SELECT total_units, occupied_units, preleased_vacant, notice_units, physical_occupancy
            FROM unified_occupancy_metrics
            WHERE unified_property_id = ? OR unified_property_id = ?
            ORDER BY snapshot_date DESC LIMIT 1
        """, (property_id, normalized_id))
        occ = uc.fetchone()
        uni_conn.close()
        
        if not occ:
            raise HTTPException(status_code=404, detail="No occupancy data found")
        
        total_units = occ[0] or 0
        occupied = occ[1] or 0
        preleased_vacant = occ[2] or 0  # Signed leases not yet moved in
        on_notice = occ[3] or 0
        current_occ_pct = occ[4] or 0
        
        # Get lease expirations by period from realpage_leases
        try:
            from app.property_config.properties import get_pms_config
            pms_config = get_pms_config(property_id)
            site_id = pms_config.realpage_siteid
        except Exception:
            site_id = None
        
        expiring_30 = 0
        expiring_60 = 0
        expiring_90 = 0
        renewed_30 = 0
        renewed_60 = 0
        renewed_90 = 0
        
        if site_id:
            try:
                raw_conn = sqlite3.connect(str(raw_db))
                rc = raw_conn.cursor()
                date_expr = "date(substr(lease_end_date,7,4)||'-'||substr(lease_end_date,1,2)||'-'||substr(lease_end_date,4,2))"
                
                for days, label in [(30, '30'), (60, '60'), (90, '90')]:
                    rc.execute(f"""
                        SELECT COUNT(*) as expiring,
                               SUM(CASE WHEN next_lease_id IS NOT NULL AND next_lease_id != '' THEN 1 ELSE 0 END) as renewed
                        FROM realpage_leases
                        WHERE site_id = ?
                          AND status_text IN ('Current', 'Current - Past')
                          AND lease_end_date IS NOT NULL AND lease_end_date != ''
                          AND {date_expr} BETWEEN date('now') AND date('now', '+{days} days')
                    """, (site_id,))
                    row = rc.fetchone()
                    if row:
                        if label == '30':
                            expiring_30, renewed_30 = row[0] or 0, row[1] or 0
                        elif label == '60':
                            expiring_60, renewed_60 = row[0] or 0, row[1] or 0
                        else:
                            expiring_90, renewed_90 = row[0] or 0, row[1] or 0
                
                raw_conn.close()
            except Exception:
                pass
        
        # Calculate projections
        # Net move-outs = expiring leases that haven't renewed (approximation)
        def project(days_label, expiring, renewed):
            not_renewed = max(0, expiring - renewed)
            # Assume preleased_vacant move in within 30 days
            scheduled_in = preleased_vacant if days_label == '30' else preleased_vacant
            projected_occupied = occupied + scheduled_in - not_renewed
            projected_occupied = max(0, min(total_units, projected_occupied))
            projected_pct = round(projected_occupied / total_units * 100, 1) if total_units > 0 else 0
            return {
                "period": f"{days_label}d",
                "projected_occupied": projected_occupied,
                "projected_occupancy_pct": projected_pct,
                "scheduled_move_ins": scheduled_in,
                "expiring_leases": expiring,
                "renewed_leases": renewed,
                "expected_move_outs": not_renewed,
            }
        
        projections = [
            project('30', expiring_30, renewed_30),
            project('60', expiring_60, renewed_60),
            project('90', expiring_90, renewed_90),
        ]
        
        return {
            "property_id": property_id,
            "current_occupancy_pct": current_occ_pct,
            "current_occupied": occupied,
            "total_units": total_units,
            "preleased_vacant": preleased_vacant,
            "on_notice": on_notice,
            "projections": projections,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate projected occupancy: {str(e)}")


@router.get("/properties/{property_id}/availability")
async def get_availability(property_id: str):
    """
    GET: Availability metrics per PHH feedback.
    
    Returns:
    - ATR (Actual-To-Rent): total vacant + on notice - pre-leased
    - Availability buckets: 0-30 days, 30-60 days available
    - Total availability %
    - 7-week availability trend with direction indicator
    
    Sources: unified_occupancy_metrics, realpage_rent_roll, realpage_projected_occupancy
    """
    import sqlite3
    from pathlib import Path
    from datetime import datetime, timedelta
    from app.property_config.properties import get_pms_config
    
    uni_db = UNIFIED_DB_PATH
    raw_db = REALPAGE_DB_PATH
    
    normalized_id = property_id
    if property_id.startswith("kairoi-"):
        normalized_id = property_id.replace("kairoi-", "").replace("-", "_")
    
    try:
        # --- Current occupancy snapshot ---
        uni_conn = sqlite3.connect(str(uni_db))
        uc = uni_conn.cursor()
        uc.execute("""
            SELECT total_units, occupied_units, vacant_units, preleased_vacant, notice_units
            FROM unified_occupancy_metrics
            WHERE unified_property_id = ? OR unified_property_id = ?
            ORDER BY snapshot_date DESC LIMIT 1
        """, (property_id, normalized_id))
        occ = uc.fetchone()
        uni_conn.close()
        
        if not occ:
            raise HTTPException(status_code=404, detail="No occupancy data found")
        
        total_units = occ[0] or 0
        occupied = occ[1] or 0
        vacant = occ[2] or 0
        preleased = occ[3] or 0
        on_notice = occ[4] or 0
        
        # ATR = total vacant + on notice - pre-leased (matches Yardi definition)
        atr = vacant + on_notice - preleased
        atr = max(0, atr)
        atr_pct = round(atr / total_units * 100, 1) if total_units > 0 else 0
        availability_pct = round(atr / total_units * 100, 1) if total_units > 0 else 0
        
        # --- Availability buckets from rent_roll (available_date or days_vacant) ---
        avail_0_30 = 0
        avail_30_60 = 0
        avail_60_plus = 0
        
        try:
            pms_config = get_pms_config(property_id)
            site_id = pms_config.realpage_siteid
        except Exception:
            site_id = None
        
        if site_id:
            try:
                raw_conn = sqlite3.connect(str(raw_db))
                rc = raw_conn.cursor()
                today = datetime.now()
                
                # Count available units by days-until-available
                # Vacant units available now = bucket 0-30
                # Units becoming available (on notice with move-out in 0-30 or 30-60) 
                rc.execute("""
                    SELECT 
                        SUM(CASE WHEN status IN ('Vacant', 'Admin/Down') THEN 1 ELSE 0 END) as vacant_now,
                        SUM(CASE WHEN status IN ('Occupied-NTV', 'Occupied-NTVL') 
                                AND lease_end IS NOT NULL AND lease_end != ''
                                AND date(substr(lease_end,7,4)||'-'||substr(lease_end,1,2)||'-'||substr(lease_end,4,2))
                                    <= date('now', '+30 days')
                            THEN 1 ELSE 0 END) as notice_0_30,
                        SUM(CASE WHEN status IN ('Occupied-NTV', 'Occupied-NTVL')
                                AND lease_end IS NOT NULL AND lease_end != ''
                                AND date(substr(lease_end,7,4)||'-'||substr(lease_end,1,2)||'-'||substr(lease_end,4,2))
                                    BETWEEN date('now', '+31 days') AND date('now', '+60 days')
                            THEN 1 ELSE 0 END) as notice_30_60,
                        SUM(CASE WHEN status IN ('Occupied-NTV', 'Occupied-NTVL')
                                AND (lease_end IS NULL OR lease_end = ''
                                     OR date(substr(lease_end,7,4)||'-'||substr(lease_end,1,2)||'-'||substr(lease_end,4,2))
                                        > date('now', '+60 days'))
                            THEN 1 ELSE 0 END) as notice_60_plus
                    FROM realpage_rent_roll
                    WHERE property_id = ?
                      AND report_date = (SELECT MAX(report_date) FROM realpage_rent_roll WHERE property_id = ?)
                """, (site_id, site_id))
                row = rc.fetchone()
                if row:
                    avail_0_30 = (row[0] or 0) + (row[1] or 0)  # Vacant now + notice expiring in 0-30
                    avail_30_60 = row[2] or 0  # Notice expiring in 30-60
                    avail_60_plus = row[3] or 0  # Notice expiring beyond 60 days
                
                raw_conn.close()
            except Exception:
                # Fallback: use ATR as 0-30 bucket
                avail_0_30 = atr
        else:
            avail_0_30 = atr
        
        # --- 7-week availability trend from projected_occupancy ---
        trend_weeks = []
        trend_direction = "flat"
        
        if site_id:
            try:
                raw_conn = sqlite3.connect(str(raw_db))
                rc = raw_conn.cursor()
                rc.execute("""
                    SELECT week_ending, MAX(total_units), MAX(occupied_end), MAX(pct_occupied_end),
                           MAX(scheduled_move_ins), MAX(scheduled_move_outs)
                    FROM realpage_projected_occupancy
                    WHERE property_id = ?
                    GROUP BY week_ending
                    ORDER BY week_ending ASC
                    LIMIT 7
                """, (site_id,))
                
                for row in rc.fetchall():
                    week_end, t_units, occ_end, occ_pct, mi, mo = row
                    t_units = t_units or total_units
                    week_atr = max(0, (t_units or 0) - (occ_end or 0))
                    week_atr_pct = round(week_atr / t_units * 100, 1) if t_units > 0 else 0
                    trend_weeks.append({
                        "week_ending": week_end,
                        "atr": week_atr,
                        "atr_pct": week_atr_pct,
                        "occupancy_pct": occ_pct or 0,
                        "move_ins": mi or 0,
                        "move_outs": mo or 0,
                    })
                raw_conn.close()
                
                # Determine direction: compare first vs last week ATR
                if len(trend_weeks) >= 2:
                    first_atr = trend_weeks[0]["atr_pct"]
                    last_atr = trend_weeks[-1]["atr_pct"]
                    if last_atr > first_atr + 1:
                        trend_direction = "increasing"  # ATR going up = bad
                    elif last_atr < first_atr - 1:
                        trend_direction = "decreasing"  # ATR going down = good
                    else:
                        trend_direction = "flat"
            except Exception:
                pass
        
        return {
            "property_id": property_id,
            "total_units": total_units,
            "occupied": occupied,
            "vacant": vacant,
            "on_notice": on_notice,
            "preleased": preleased,
            "atr": atr,
            "atr_pct": atr_pct,
            "availability_pct": availability_pct,
            "buckets": {
                "available_0_30": avail_0_30,
                "available_30_60": avail_30_60,
                "available_60_plus": avail_60_plus,
                "total": avail_0_30 + avail_30_60 + avail_60_plus,
            },
            "trend": {
                "direction": trend_direction,
                "weeks": trend_weeks,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get availability: {str(e)}")


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


@router.get("/properties/{property_id}/expirations/details")
async def get_expiration_details(
    property_id: str,
    days: int = Query(90, description="Lookahead window in days (30, 60, or 90)"),
    filter: Optional[str] = Query(None, description="Decision filter: renewed, vacating, pending, mtm, moved_out, expiring (all non-renewed)"),
):
    """
    GET: Individual lease records expiring within the given window.
    
    Primary source: realpage_lease_expiration_renewal (Report 4156) when available,
    fallback to realpage_leases. Same source as the summary /expirations endpoint
    so that drill-through counts always match the summary numbers.
    
    Filter (report 4156):
      'renewed'   = decision = Renewed
      'vacating'  = decision = Vacating
      'pending'   = decision = Unknown
      'mtm'       = decision = MTM
      'moved_out' = decision = Moved out
      'expiring'  = all non-renewed
    Filter (fallback):
      'renewed'  = status_text = Current - Future
      'expiring' = status_text = Current
    """
    import sqlite3
    from app.db.schema import REALPAGE_DB_PATH
    from app.property_config.properties import get_pms_config

    pms_config = get_pms_config(property_id)
    if not pms_config.realpage_siteid:
        return {"leases": []}

    site_id = pms_config.realpage_siteid
    try:
        conn = sqlite3.connect(REALPAGE_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if report 4156 data is available (same source as summary endpoint)
        use_4156 = False
        try:
            cursor.execute("SELECT COUNT(*) FROM realpage_lease_expiration_renewal WHERE property_id = ?", (site_id,))
            if (cursor.fetchone()[0] or 0) > 0:
                use_4156 = True
        except Exception:
            pass

        leases = []

        if use_4156:
            # Report 4156: decision-based filtering (matches summary endpoint exactly)
            date_expr = "date(substr(lease_end_date,7,4)||'-'||substr(lease_end_date,1,2)||'-'||substr(lease_end_date,4,2))"
            decision_cond = ""
            if filter == "renewed":
                decision_cond = "AND decision = 'Renewed'"
            elif filter == "vacating":
                decision_cond = "AND decision = 'Vacating'"
            elif filter == "pending":
                decision_cond = "AND decision = 'Unknown'"
            elif filter == "mtm":
                decision_cond = "AND decision = 'MTM'"
            elif filter == "moved_out":
                decision_cond = "AND decision = 'Moved out'"
            elif filter == "expiring":
                decision_cond = "AND decision != 'Renewed'"

            cursor.execute(f"""
                SELECT e.unit_number, e.floorplan, e.actual_rent, e.market_rent,
                       e.lease_end_date, e.decision, e.new_lease_start, e.new_lease_term,
                       e.new_rent, e.move_in_date,
                       rr.sqft
                FROM realpage_lease_expiration_renewal e
                LEFT JOIN realpage_rent_roll rr
                    ON rr.property_id = e.property_id
                    AND rr.unit_number = e.unit_number
                    AND rr.report_date = (SELECT MAX(report_date) FROM realpage_rent_roll WHERE property_id = e.property_id)
                WHERE e.property_id = ?
                  AND e.lease_end_date IS NOT NULL AND e.lease_end_date != ''
                  AND {date_expr} BETWEEN date('now') AND date('now', '+' || ? || ' days')
                  {decision_cond}
                ORDER BY {date_expr}
            """, (site_id, days))

            for row in cursor.fetchall():
                decision = row["decision"] or ""
                if decision == "Renewed":
                    display_status = "Renewed"
                elif decision == "Vacating":
                    display_status = "Vacating"
                elif decision == "Moved out":
                    display_status = "Moved Out"
                elif decision == "MTM":
                    display_status = "Month-to-Month"
                else:
                    display_status = "Pending"

                lease_rec = {
                    "unit": row["unit_number"] or "—",
                    "lease_end": row["lease_end_date"] or "",
                    "market_rent": row["market_rent"] or row["actual_rent"] or 0,
                    "actual_rent": row["actual_rent"] or 0,
                    "status": display_status,
                    "floorplan": row["floorplan"] or "",
                    "sqft": row["sqft"] or 0,
                    "move_in": (row["move_in_date"] or ""),
                    "lease_start": "",
                    "decision": decision,
                }
                if decision == "Renewed":
                    lease_rec["new_rent"] = row["new_rent"] or 0
                    lease_rec["new_lease_term"] = row["new_lease_term"] or ""
                leases.append(lease_rec)
        else:
            # Fallback: realpage_leases
            status_cond = "AND status_text IN ('Current', 'Current - Future')"
            if filter == "renewed":
                status_cond = "AND status_text = 'Current - Future'"
            elif filter == "expiring":
                status_cond = "AND status_text = 'Current'"

            cursor.execute(f"""
                SELECT l.unit_id, l.lease_start_date, l.lease_end_date, l.rent_amount,
                       l.status_text, l.type_text, l.move_in_date,
                       COALESCE(u.unit_number, l.unit_id) as unit_display,
                       r.floorplan, r.sqft, r.market_rent as rr_market_rent,
                       r.move_in_date as rr_move_in, r.status as rr_status
                FROM realpage_leases l
                LEFT JOIN realpage_units u
                    ON u.unit_id = l.unit_id AND u.site_id = l.site_id
                LEFT JOIN realpage_rent_roll r
                    ON r.property_id = l.site_id
                    AND r.lease_end = l.lease_end_date
                    AND r.lease_start = l.lease_start_date
                    AND r.unit_number NOT IN ('Unit', 'details')
                WHERE l.site_id = ?
                    AND l.lease_end_date != ''
                    AND date(substr(l.lease_end_date,7,4) || '-' || substr(l.lease_end_date,1,2) || '-' || substr(l.lease_end_date,4,2))
                        BETWEEN date('now') AND date('now', '+' || ? || ' days')
                    {status_cond}
                ORDER BY date(substr(l.lease_end_date,7,4) || '-' || substr(l.lease_end_date,1,2) || '-' || substr(l.lease_end_date,4,2))
            """, (site_id, days))

            for row in cursor.fetchall():
                is_renewed = row["status_text"] == "Current - Future"
                if is_renewed:
                    display_status = "Renewal Signed"
                else:
                    rr_status = row["rr_status"] or ""
                    display_status = "Notice Given" if "NTV" in rr_status else "No Notice"

                unit = row["unit_display"] or row["unit_id"] or "—"
                lease_rec = {
                    "unit": unit,
                    "lease_end": row["lease_end_date"] or "",
                    "market_rent": row["rr_market_rent"] or row["rent_amount"] or 0,
                    "status": display_status,
                    "floorplan": row["floorplan"] or "",
                    "sqft": row["sqft"] or 0,
                    "move_in": ((row["rr_move_in"] or row["move_in_date"] or "").split("\n")[0]),
                    "lease_start": row["lease_start_date"] or "",
                }
                if is_renewed:
                    renewal_type = row["type_text"] or ""
                    lease_rec["renewal_type"] = "Renewal" if "Renewal" in renewal_type else "Lease Extension"
                leases.append(lease_rec)

        conn.close()
        return {"leases": leases, "count": len(leases)}

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
    
    Data source: unified_delinquency table (synced from RealPage reports).
    Returns: DelinquencyReport format for frontend consumption.
    """
    import sqlite3
    from pathlib import Path
    from datetime import datetime
    
    db_path = UNIFIED_DB_PATH
    
    # Normalize property_id for legacy kairoi- format
    normalized_id = property_id
    if property_id.startswith("kairoi-"):
        normalized_id = property_id.replace("kairoi-", "").replace("-", "_")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Get delinquency records for property with eviction columns
        # Try both the original and normalized property_id
        cursor.execute("""
            SELECT unit_number, resident_name, status, current_balance,
                   balance_0_30, balance_31_60, balance_61_90, balance_over_90, 
                   prepaid, net_balance, report_date,
                   COALESCE(is_eviction, 0), COALESCE(eviction_balance, 0),
                   COALESCE(total_delinquent, 0)
            FROM unified_delinquency
            WHERE unified_property_id = ? OR unified_property_id = ?
            ORDER BY balance_0_30 DESC
        """, (property_id, normalized_id))
        
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            raise HTTPException(status_code=404, detail="No delinquency data found")
        
        # Calculate totals
        total_delinquent = 0
        total_collections = 0
        total_prepaid = 0
        total_net = 0
        aging = {"current": 0, "0_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
        collections = {"current": 0, "0_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
        eviction_units = []
        resident_details = []
        report_date = rows[0][10] if rows[0][10] else datetime.now().strftime("%Y-%m-%d")
        
        for row in rows:
            unit_number = row[0]
            status = row[2] or ""
            current_bal = row[3] or 0
            bal_0_30 = row[4] or 0
            bal_31_60 = row[5] or 0
            bal_61_90 = row[6] or 0
            bal_90_plus = row[7] or 0
            prepaid = row[8] or 0
            net_balance = row[9] or 0
            report_total_delinquent = row[13] or 0
            
            # Use the report's total_delinquent directly (accurate per-unit value from RealPage)
            unit_delinquent = report_total_delinquent
            
            # Check if former resident (collections)
            is_former = "former" in status.lower()
            # Use RPX SOAP API evict flag (column 11=is_eviction, 12=eviction_balance)
            is_eviction = bool(row[11])
            eviction_balance_from_lease = row[12] or 0
            
            # Aging bars include ALL residents (current + former)
            aging["current"] += max(0, current_bal)
            aging["0_30"] += max(0, bal_0_30)
            aging["31_60"] += max(0, bal_31_60)
            aging["61_90"] += max(0, bal_61_90)
            aging["90_plus"] += max(0, bal_90_plus)
            
            # Collections tracks former residents separately
            if is_former:
                collections["current"] += max(0, current_bal)
                collections["0_30"] += max(0, bal_0_30)
                collections["31_60"] += max(0, bal_31_60)
                collections["61_90"] += max(0, bal_61_90)
                collections["90_plus"] += max(0, bal_90_plus)
                if unit_delinquent > 0:
                    total_collections += unit_delinquent
            
            if unit_delinquent > 0:
                total_delinquent += unit_delinquent
            
            # Prepaid: use the report's prepaid value directly
            # Exclude "Misc. Income" status — RealPage Financial Summary excludes these
            is_misc = "misc" in status.lower()
            if prepaid < 0 and not is_misc:
                total_prepaid += prepaid
            total_net += net_balance
            
            if is_eviction:
                eviction_units.append({"unit": unit_number, "balance": unit_delinquent, "lease_balance": eviction_balance_from_lease})
            
            # Build resident detail record
            unit_prepaid = abs(prepaid) if prepaid < 0 else (abs(net_balance) if net_balance < 0 and unit_delinquent == 0 else 0)
            resident_details.append({
                "unit": unit_number,
                "status": status,
                "total_prepaid": round(unit_prepaid, 2),
                "total_delinquent": round(unit_delinquent, 2),
                "net_balance": round(net_balance, 2),
                "current": current_bal,
                "days_30": bal_0_30,
                "days_60": bal_31_60,
                "days_90_plus": bal_90_plus,
                "deposits_held": 0,
                "is_eviction": is_eviction,
                "is_former": is_former
            })
        
        # Count all residents with actual delinquency, split by current/former
        delinquent_count = len([r for r in resident_details if r["total_delinquent"] > 0])
        current_residents = [r for r in resident_details if r["total_delinquent"] > 0 and not r["is_former"]]
        former_residents = [r for r in resident_details if r["total_delinquent"] > 0 and r["is_former"]]
        
        return {
            "property_name": property_id,
            "report_date": report_date,
            "total_prepaid": round(abs(total_prepaid), 2),
            "total_delinquent": round(total_delinquent, 2),
            "current_resident_total": round(sum(r["total_delinquent"] for r in current_residents), 2),
            "former_resident_total": round(sum(r["total_delinquent"] for r in former_residents), 2),
            "current_resident_count": len(current_residents),
            "former_resident_count": len(former_residents),
            "net_balance": round(total_net, 2),
            "delinquency_aging": {
                "current": round(aging["current"], 2),
                "days_0_30": round(aging["0_30"], 2),
                "days_31_60": round(aging["31_60"], 2),
                "days_61_90": round(aging["61_90"], 2),
                "days_90_plus": round(aging["90_plus"], 2),
                "total": round(sum(aging.values()), 2)
            },
            "evictions": {
                "total_balance": round(sum(e["balance"] for e in eviction_units), 2),
                "unit_count": len(eviction_units),
                "filed_count": 0,
                "writ_count": 0
            },
            "collections": {
                "current": round(collections["current"], 2),
                "days_0_30": round(collections["0_30"], 2),
                "days_31_60": round(collections["31_60"], 2),
                "days_61_90": round(collections["61_90"], 2),
                "days_90_plus": round(collections["90_plus"], 2),
                "total": round(total_collections, 2)
            },
            "deposits_held": 0,
            "outstanding_deposits": 0,
            "resident_count": delinquent_count,
            "resident_details": resident_details
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get delinquency data: {str(e)}")


# =========================================================================
# Resident Risk Scores (Churn & Delinquency Prediction)
# =========================================================================

@router.get("/properties/{property_id}/risk-scores")
async def get_risk_scores(property_id: str):
    """
    GET: Resident risk scores for a property.
    
    Returns property-level churn and delinquency prediction aggregates
    sourced from the Snowflake scoring engine via sync_risk_scores.py.
    
    Scores: 0 = high risk, 1 = healthy.
    Risk buckets: HIGH (<0.3), MEDIUM (0.3-0.6), LOW (>0.6).
    """
    import sqlite3
    from pathlib import Path
    
    db_path = UNIFIED_DB_PATH
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT *
            FROM unified_risk_scores
            WHERE unified_property_id = ?
            ORDER BY snapshot_date DESC
            LIMIT 1
        """, (property_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            raise HTTPException(status_code=404, detail="No risk score data for this property")
        
        return {
            "property_id": property_id,
            "snapshot_date": row["snapshot_date"],
            "total_scored": row["total_scored"],
            "notice_count": row["notice_count"],
            "at_risk_total": row["at_risk_total"],
            "churn": {
                "avg_score": row["avg_churn_score"],
                "median_score": row["median_churn_score"],
                "high_risk": row["churn_high_count"],
                "medium_risk": row["churn_medium_count"],
                "low_risk": row["churn_low_count"],
                "threshold_high": row["churn_threshold_high"],
                "threshold_low": row["churn_threshold_low"],
            },
            "delinquency": {
                "avg_score": row["avg_delinquency_score"],
                "median_score": row["median_delinquency_score"],
                "high_risk": row["delinq_high_count"],
                "medium_risk": row["delinq_medium_count"],
                "low_risk": row["delinq_low_count"],
            },
            "insights": {
                "pct_scheduled_moveout": row["pct_scheduled_moveout"],
                "pct_with_app": row["pct_with_app"],
                "avg_tenure_months": row["avg_tenure_months"],
                "avg_rent": row["avg_rent"],
                "avg_open_tickets": row["avg_open_tickets"],
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get risk scores: {str(e)}")


# =========================================================================
# Customer-Requested KPIs (Feb 2026)
# =========================================================================

@router.get("/properties/{property_id}/availability-by-floorplan")
async def get_availability_by_floorplan(property_id: str):
    """
    GET: Available units broken out by floorplan, showing vacant vs on-notice counts.
    
    Uses box_score data which has per-floorplan breakdowns.
    Returns: list of floorplan records with total, vacant, notice, leased counts.
    """
    import sqlite3
    from pathlib import Path
    from app.property_config.properties import get_pms_config
    
    try:
        pms_config = get_pms_config(property_id)
        site_id = pms_config.realpage_siteid
        if not site_id:
            return {"floorplans": []}
        
        raw_db = REALPAGE_DB_PATH
        conn = sqlite3.connect(raw_db)
        cursor = conn.cursor()
        
        # Get latest box_score data per floorplan (exclude summary rows)
        cursor.execute("""
            SELECT floorplan, floorplan_group, total_units, vacant_units,
                   vacant_not_leased, vacant_leased, occupied_units,
                   occupied_on_notice, model_units, down_units,
                   avg_market_rent, occupancy_pct, leased_pct
            FROM realpage_box_score
            WHERE property_id = ?
              AND floorplan IS NOT NULL
              AND floorplan != ''
              AND report_date = (
                  SELECT MAX(report_date) FROM realpage_box_score WHERE property_id = ?
              )
            ORDER BY floorplan_group, floorplan
        """, (site_id, site_id))
        
        floorplans = []
        totals = {"total": 0, "vacant": 0, "notice": 0, "vacant_leased": 0, 
                  "vacant_not_leased": 0, "occupied": 0, "model": 0, "down": 0}
        
        for row in cursor.fetchall():
            fp = {
                "floorplan": row[0],
                "group": row[1],
                "total_units": row[2] or 0,
                "vacant_units": row[3] or 0,
                "vacant_not_leased": row[4] or 0,
                "vacant_leased": row[5] or 0,
                "occupied_units": row[6] or 0,
                "on_notice": row[7] or 0,
                "model_units": row[8] or 0,
                "down_units": row[9] or 0,
                "avg_market_rent": row[10] or 0,
                "occupancy_pct": row[11] or 0,
                "leased_pct": row[12] or 0,
            }
            floorplans.append(fp)
            totals["total"] += fp["total_units"]
            totals["vacant"] += fp["vacant_units"]
            totals["notice"] += fp["on_notice"]
            totals["vacant_leased"] += fp["vacant_leased"]
            totals["vacant_not_leased"] += fp["vacant_not_leased"]
            totals["occupied"] += fp["occupied_units"]
            totals["model"] += fp["model_units"]
            totals["down"] += fp["down_units"]
        
        conn.close()
        return {"floorplans": floorplans, "totals": totals}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/consolidated-by-bedroom")
async def get_consolidated_by_bedroom(property_id: str):
    """
    GET: Dashboard Consolidation — aggregates occupancy, pricing, and availability
    by bedroom type (Studio, 1BR, 2BR, 3BR+).
    
    Combines box_score (occupancy/availability) with unified_pricing_metrics (rent)
    into a single consolidated view per bedroom count.
    """
    import sqlite3
    from pathlib import Path
    from app.property_config.properties import get_pms_config
    
    try:
        pms_config = get_pms_config(property_id)
        site_id = pms_config.realpage_siteid
        if not site_id:
            return {"bedrooms": [], "totals": {}}
        
        raw_db = REALPAGE_DB_PATH
        unified_db = UNIFIED_DB_PATH
        
        # Aggregate box_score by bedroom count
        conn = sqlite3.connect(raw_db)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT floorplan_group, floorplan,
                   total_units, occupied_units, vacant_units,
                   vacant_leased, vacant_not_leased, occupied_on_notice,
                   model_units, down_units, avg_market_rent,
                   occupancy_pct, leased_pct, avg_actual_rent
            FROM realpage_box_score
            WHERE property_id = ?
              AND floorplan IS NOT NULL AND floorplan != ''
              AND report_date = (
                  SELECT MAX(report_date) FROM realpage_box_score WHERE property_id = ?
              )
        """, (site_id, site_id))
        
        # Derive bedroom count from floorplan_group (e.g. "1x1" -> 1) or floorplan prefix (S=Studio, A=1BR, B=2BR, C=3BR)
        def _derive_bedrooms(fg: str, fp: str) -> int:
            # Try floorplan_group first (if it looks like NxN format)
            if fg and len(fg) >= 3 and fg[0].isdigit() and fg[1] == 'x':
                return int(fg[0])
            # Fallback: derive from floorplan name prefix
            if fp:
                first = fp[0].upper()
                if first == 'S': return 0  # Studio
                if first == 'A': return 1
                if first == 'B': return 2
                if first == 'C': return 3
                if first == 'D': return 4
            return 0
        
        bedroom_data = {}
        for row in cursor.fetchall():
            fg = row[0] or ""
            fp = row[1] or ""
            beds = _derive_bedrooms(fg, fp)
            
            bed_label = "Studio" if beds == 0 else f"{beds}BR"
            
            if bed_label not in bedroom_data:
                bedroom_data[bed_label] = {
                    "bedroom_type": bed_label,
                    "bedrooms": beds,
                    "floorplans": [],
                    "total_units": 0,
                    "occupied": 0,
                    "vacant": 0,
                    "vacant_leased": 0,
                    "vacant_not_leased": 0,
                    "on_notice": 0,
                    "model": 0,
                    "down": 0,
                    "_market_rent_sum": 0,
                    "_actual_rent_sum": 0,
                    "_rent_count": 0,
                }
            
            bd = bedroom_data[bed_label]
            bd["floorplans"].append(row[1])
            bd["total_units"] += row[2] or 0
            bd["occupied"] += row[3] or 0
            bd["vacant"] += row[4] or 0
            bd["vacant_leased"] += row[5] or 0
            bd["vacant_not_leased"] += row[6] or 0
            bd["on_notice"] += row[7] or 0
            bd["model"] += row[8] or 0
            bd["down"] += row[9] or 0
            if row[10] and row[10] > 0:
                bd["_market_rent_sum"] += (row[10] or 0) * (row[2] or 0)
                bd["_actual_rent_sum"] += (row[13] or 0) * (row[3] or 0)
                bd["_rent_count"] += row[2] or 0
        
        conn.close()
        
        # Get expiration data by floorplan from rent_roll (leases table has NULL unit_number)
        renewal_map = {}
        total_renewed = 0
        total_expiring_leases = 0
        try:
            conn2 = sqlite3.connect(raw_db)
            c2 = conn2.cursor()
            
            # Expirations by floorplan from rent_roll (has unit_number + floorplan + lease_end)
            c2.execute("""
                SELECT floorplan, COUNT(*) as expiring
                FROM realpage_rent_roll
                WHERE property_id = ?
                  AND report_date = (SELECT MAX(report_date) FROM realpage_rent_roll WHERE property_id = ?)
                  AND status = 'Occupied'
                  AND lease_end IS NOT NULL AND lease_end != ''
                  AND floorplan IS NOT NULL AND floorplan != '' AND floorplan != 'Floorplan'
                  AND date(substr(lease_end,7,4)||'-'||substr(lease_end,1,2)||'-'||substr(lease_end,4,2))
                      BETWEEN date('now') AND date('now', '+90 days')
                GROUP BY floorplan
            """, (site_id, site_id))
            for row in c2.fetchall():
                renewal_map[row[0]] = {"expiring": row[1], "renewed": 0}
            
            # Total renewals from leases table (works for totals, just can't map to floorplan)
            c2.execute("""
                SELECT COUNT(*) as total_exp,
                       SUM(CASE WHEN status_text = 'Current - Future' THEN 1 ELSE 0 END) as renewed
                FROM realpage_leases
                WHERE site_id = ?
                  AND status_text IN ('Current', 'Current - Future')
                  AND lease_end_date != ''
                  AND date(substr(lease_end_date,7,4)||'-'||substr(lease_end_date,1,2)||'-'||substr(lease_end_date,4,2))
                      BETWEEN date('now') AND date('now', '+90 days')
            """, (site_id,))
            row = c2.fetchone()
            if row:
                total_expiring_leases = row[0] or 0
                total_renewed = row[1] or 0
            
            # Proportionally distribute renewals across floorplans by their expiration count
            if total_expiring_leases > 0 and total_renewed > 0:
                total_rr_exp = sum(v["expiring"] for v in renewal_map.values())
                for fp_data in renewal_map.values():
                    if total_rr_exp > 0:
                        fp_data["renewed"] = round(fp_data["expiring"] * total_renewed / total_rr_exp)
            
            conn2.close()
        except Exception:
            pass
        
        # Build final result
        result = []
        grand_totals = {
            "total_units": 0, "occupied": 0, "vacant": 0,
            "vacant_leased": 0, "on_notice": 0,
            "expiring_90d": 0, "renewed_90d": 0,
        }
        
        for bed_label in sorted(bedroom_data.keys(), key=lambda x: bedroom_data[x]["bedrooms"]):
            bd = bedroom_data[bed_label]
            total = bd["total_units"]
            occ_pct = round(bd["occupied"] / total * 100, 1) if total > 0 else 0
            avg_market = round(bd["_market_rent_sum"] / bd["_rent_count"], 0) if bd["_rent_count"] > 0 else 0
            avg_actual = round(bd["_actual_rent_sum"] / bd["occupied"], 0) if bd["occupied"] > 0 else 0
            
            # Renewal data for this bedroom type's floorplans
            expiring = sum(renewal_map.get(fp, {}).get("expiring", 0) for fp in bd["floorplans"])
            renewed = sum(renewal_map.get(fp, {}).get("renewed", 0) for fp in bd["floorplans"])
            renewal_pct = round(renewed / expiring * 100, 1) if expiring > 0 else None
            
            entry = {
                "bedroom_type": bed_label,
                "bedrooms": bd["bedrooms"],
                "floorplan_count": len(bd["floorplans"]),
                "floorplans": bd["floorplans"],
                "total_units": total,
                "occupied": bd["occupied"],
                "vacant": bd["vacant"],
                "vacant_leased": bd["vacant_leased"],
                "vacant_not_leased": bd["vacant_not_leased"],
                "on_notice": bd["on_notice"],
                "occupancy_pct": occ_pct,
                "avg_market_rent": avg_market,
                "avg_in_place_rent": avg_actual,
                "rent_delta": round(avg_market - avg_actual, 0) if avg_market and avg_actual else 0,
                "expiring_90d": expiring,
                "renewed_90d": renewed,
                "renewal_pct_90d": renewal_pct,
            }
            result.append(entry)
            
            grand_totals["total_units"] += total
            grand_totals["occupied"] += bd["occupied"]
            grand_totals["vacant"] += bd["vacant"]
            grand_totals["vacant_leased"] += bd["vacant_leased"]
            grand_totals["on_notice"] += bd["on_notice"]
            grand_totals["expiring_90d"] += expiring
            grand_totals["renewed_90d"] += renewed
        
        gt = grand_totals
        gt["occupancy_pct"] = round(gt["occupied"] / gt["total_units"] * 100, 1) if gt["total_units"] > 0 else 0
        gt["renewal_pct_90d"] = round(gt["renewed_90d"] / gt["expiring_90d"] * 100, 1) if gt["expiring_90d"] > 0 else None
        
        return {"bedrooms": result, "totals": gt}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/availability-by-floorplan/units")
async def get_availability_units(property_id: str, floorplan: str = None, status: str = None):
    """
    GET: Unit-level drill-down for availability by floorplan.
    
    Query params:
    - floorplan: Filter to specific floorplan
    - status: Filter to status (Vacant, Occupied-NTV, Vacant-Leased, Occupied, etc.)
    """
    import sqlite3
    from pathlib import Path
    from app.property_config.properties import get_pms_config
    
    try:
        pms_config = get_pms_config(property_id)
        site_id = pms_config.realpage_siteid
        if not site_id:
            return {"units": []}
        
        raw_db = REALPAGE_DB_PATH
        conn = sqlite3.connect(raw_db)
        cursor = conn.cursor()
        
        # Build floorplan avg_actual_rent lookup from box_score as fallback
        fp_rent = {}
        cursor.execute("""
            SELECT floorplan, avg_actual_rent
            FROM realpage_box_score
            WHERE property_id = ?
              AND floorplan IS NOT NULL AND floorplan != ''
              AND report_date = (SELECT MAX(report_date) FROM realpage_box_score WHERE property_id = ?)
        """, (site_id, site_id))
        for row in cursor.fetchall():
            if row[1] and row[1] > 0:
                fp_rent[row[0]] = row[1]
        
        query = """
            SELECT DISTINCT rr.unit_number, rr.floorplan, rr.status, rr.sqft,
                   rr.market_rent, rr.actual_rent, rr.lease_start, rr.lease_end,
                   rr.move_in_date, rr.move_out_date,
                   l.rent_amount,
                   ru.available_date
            FROM realpage_rent_roll rr
            LEFT JOIN realpage_leases l
                ON l.site_id = rr.property_id
                AND l.lease_start_date = rr.lease_start
                AND l.lease_end_date = rr.lease_end
                AND l.status_text IN ('Current', 'Current - Future')
            LEFT JOIN realpage_units ru
                ON ru.site_id = rr.property_id
                AND ru.unit_number = rr.unit_number
            WHERE rr.property_id = ?
              AND rr.report_date = (SELECT MAX(report_date) FROM realpage_rent_roll WHERE property_id = ?)
        """
        params = [site_id, site_id]
        
        if floorplan:
            query += " AND rr.floorplan = ?"
            params.append(floorplan)
        if status:
            if status.lower() == 'vacant':
                query += " AND rr.status IN ('Vacant', 'Vacant-Leased', 'Admin/Down')"
            elif status.lower() == 'notice':
                query += " AND rr.status IN ('Occupied-NTV', 'Occupied-NTVL')"
            elif status.lower() == 'occupied':
                query += " AND rr.status = 'Occupied'"
            elif status.lower() == 'preleased':
                query += " AND rr.status = 'Vacant-Leased'"
            else:
                query += " AND rr.status = ?"
                params.append(status)
        
        query += " ORDER BY rr.unit_number"
        cursor.execute(query, params)
        
        seen = set()
        units = []
        for row in cursor.fetchall():
            unit_num = row[0]
            if unit_num in seen:
                continue
            seen.add(unit_num)
            
            # Determine actual rent: rent_roll > lease rent_amount > box_score avg
            actual = row[5] if row[5] and row[5] > 0 else None
            if not actual and row[10] and row[10] > 0:
                actual = row[10]
            if not actual:
                actual = fp_rent.get(row[1])
            
            # Compute days_vacant from realpage_units.available_date
            days_vacant = None
            avail_date_raw = row[11]  # available_date from realpage_units
            unit_status = row[2] or ''
            if unit_status in ('Vacant', 'Vacant-Leased', 'Admin/Down') and avail_date_raw:
                try:
                    from datetime import datetime as dt
                    # Handle "YYYY-MM-DD HH:MM:SS" format from realpage_units
                    avail_dt = dt.strptime(avail_date_raw.strip()[:10], '%Y-%m-%d')
                    days_vacant = (dt.now() - avail_dt).days
                    if days_vacant < 0:
                        days_vacant = 0
                except Exception:
                    pass

            units.append({
                "unit": unit_num,
                "floorplan": row[1],
                "status": row[2],
                "sqft": row[3],
                "market_rent": row[4],
                "actual_rent": actual,
                "lease_start": row[6],
                "lease_end": row[7],
                "move_in": row[8],
                "move_out": row[9],
                "days_vacant": days_vacant,
            })
        
        conn.close()
        return {"units": units, "count": len(units)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/shows")
async def get_shows(property_id: str, days: int = 7):
    """
    GET: Number of property shows/tours in the last N days.
    
    Counts Visit, Visit (return), and Videotelephony - Tour events
    from the realpage_activity table.
    
    Query params:
    - days: Trailing window in days (default 7)
    """
    import sqlite3
    from datetime import datetime, timedelta
    from pathlib import Path
    from app.property_config.properties import get_pms_config
    
    try:
        pms_config = get_pms_config(property_id)
        site_id = pms_config.realpage_siteid
        if not site_id:
            return {"total_shows": 0, "by_date": [], "days": days}
        
        raw_db = REALPAGE_DB_PATH
        conn = sqlite3.connect(raw_db)
        cursor = conn.cursor()
        
        cutoff = datetime.now() - timedelta(days=days)
        
        # Get all show events for this property (with unit-level detail)
        cursor.execute("""
            SELECT activity_date, activity_type, unit_number, floorplan
            FROM realpage_activity
            WHERE property_id = ?
              AND activity_type IN ('Visit', 'Visit (return)', 'Videotelephony - Tour', 'Unit shown')
            ORDER BY activity_date DESC
        """, (site_id,))
        
        total = 0
        by_date = {}
        by_type = {}
        show_details = []
        
        for row in cursor.fetchall():
            act_date_str, act_type, unit_num, fp = row
            try:
                act_date = datetime.strptime(act_date_str, "%m/%d/%Y")
            except (ValueError, TypeError):
                continue
            
            if act_date >= cutoff:
                total += 1
                date_key = act_date.strftime("%Y-%m-%d")
                by_date[date_key] = by_date.get(date_key, 0) + 1
                by_type[act_type] = by_type.get(act_type, 0) + 1
                show_details.append({
                    "date": date_key,
                    "type": act_type,
                    "unit": unit_num,
                    "floorplan": fp,
                })
        
        conn.close()
        
        date_list = [{"date": k, "count": v} for k, v in sorted(by_date.items())]
        
        return {
            "total_shows": total,
            "days": days,
            "by_date": date_list,
            "by_type": by_type,
            "details": show_details,
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/occupancy-forecast")
async def get_occupancy_forecast(property_id: str, weeks: int = 12):
    """
    GET: Weekly occupancy forecast showing projected move-ins and move-outs.
    
    Prefers RealPage Projected Occupancy report (3842) when available in
    realpage_projected_occupancy table. Falls back to rent_roll-based estimation.
    
    Also returns notice_units and move_in_units from rent_roll for drill-down.
    """
    import sqlite3
    from datetime import datetime, timedelta
    from pathlib import Path
    from app.property_config.properties import get_pms_config
    
    try:
        pms_config = get_pms_config(property_id)
        site_id = pms_config.realpage_siteid
        if not site_id:
            return {"forecast": [], "current_occupied": 0, "total_units": 0}
        
        raw_db = REALPAGE_DB_PATH
        conn = sqlite3.connect(raw_db)
        cursor = conn.cursor()
        
        # Get current occupied and total from box_score summary (latest report_date only)
        cursor.execute("""
            SELECT SUM(total_units), SUM(occupied_units), SUM(occupied_on_notice),
                   SUM(vacant_leased)
            FROM realpage_box_score
            WHERE property_id = ? AND floorplan IS NOT NULL
              AND report_date = (
                  SELECT MAX(report_date) FROM realpage_box_score WHERE property_id = ?
              )
        """, (site_id, site_id))
        row = cursor.fetchone()
        total_units = row[0] or 0
        current_occupied = row[1] or 0
        current_notice = row[2] or 0
        vacant_leased_count = row[3] or 0
        
        today = datetime.now()
        
        # ---- Drill-down units from rent_roll (always gathered) ----
        # Notice move-out units (use market_rent as fallback when actual_rent is 0)
        cursor.execute("""
            SELECT DISTINCT unit_number, lease_end, floorplan,
                   CASE WHEN actual_rent > 0 THEN actual_rent ELSE market_rent END AS rent
            FROM realpage_rent_roll
            WHERE property_id = ? AND status = 'Occupied-NTV'
              AND lease_end IS NOT NULL AND lease_end != ''
        """, (site_id,))
        notice_units = []
        for unit_num, date_str, fp, rent in cursor.fetchall():
            notice_units.append({
                "unit": unit_num, "date": date_str, "floorplan": fp,
                "rent": rent, "type": "notice_move_out"
            })
        
        # Pre-leased / move-in units
        # Join with leases to pick up sched_move_in_date when rent_roll lacks dates
        cursor.execute("""
            SELECT DISTINCT r.unit_number,
                   COALESCE(r.move_in_date, r.lease_start, l.sched_move_in_date, l.lease_start_date) AS best_date,
                   r.floorplan, r.market_rent
            FROM realpage_rent_roll r
            LEFT JOIN realpage_leases l
              ON l.site_id = r.property_id AND l.unit_id = r.unit_number
              AND l.sched_move_in_date IS NOT NULL AND l.sched_move_in_date != ''
            WHERE r.property_id = ? AND r.status = 'Vacant-Leased'
        """, (site_id,))
        move_in_units = []
        undated_move_ins = 0
        seen_units = set()
        for unit_num, date_str, fp, rent in cursor.fetchall():
            if unit_num in seen_units:
                continue
            seen_units.add(unit_num)
            move_in_units.append({
                "unit": unit_num, "date": date_str, "floorplan": fp,
                "rent": rent, "type": "scheduled_move_in" if date_str else "scheduled_move_in_undated"
            })
            if not date_str:
                undated_move_ins += 1
        
        # Lease expirations (for drill-down)
        # Include both Current and Current-Future (renewed) to match renewal tab counts
        expiration_units = []
        cursor.execute("""
            SELECT unit_id, lease_end_date, lease_term_desc, rent_amount, status_text
            FROM realpage_leases
            WHERE site_id = ?
              AND status_text IN ('Current', 'Current - Future')
              AND lease_end_date IS NOT NULL AND lease_end_date != ''
        """, (site_id,))
        for unit_id, date_str, fp, rent, status in cursor.fetchall():
            try:
                dt = datetime.strptime(date_str, "%m/%d/%Y")
                if dt >= today:
                    is_renewed = status == 'Current - Future'
                    expiration_units.append({
                        "unit": unit_id, "date": date_str, "floorplan": fp,
                        "rent": rent,
                        "type": "lease_expiration_renewed" if is_renewed else "lease_expiration"
                    })
            except (ValueError, TypeError):
                pass
        
        # ---- Try Projected Occupancy report (3842) first ----
        has_projected = False
        try:
            cursor.execute("""
                SELECT week_ending, MAX(total_units), MAX(occupied_begin), MAX(pct_occupied_begin),
                       MAX(scheduled_move_ins), MAX(scheduled_move_outs), MAX(occupied_end), MAX(pct_occupied_end)
                FROM realpage_projected_occupancy
                WHERE property_id = ?
                GROUP BY week_ending
                ORDER BY week_ending
            """, (site_id,))
            proj_rows = cursor.fetchall()
            if proj_rows:
                has_projected = True
        except Exception:
            proj_rows = []
        
        if has_projected and proj_rows:
            # Use the real RealPage Projected Occupancy data for projections,
            # but derive clickable column counts from rent_roll unit data
            # so drill-through record counts match exactly.
            forecast = []
            # Use total_units from report if box_score didn't have it
            report_total = proj_rows[0][1] or total_units
            if report_total > 0:
                total_units = report_total
            
            # Build date ranges for each projected week
            week_ranges = []
            for prow in proj_rows[:weeks]:
                try:
                    we_dt = datetime.strptime(prow[0], "%m/%d/%Y")
                    ws_dt = we_dt - timedelta(days=6)
                    week_ranges.append((ws_dt, we_dt))
                except (ValueError, TypeError):
                    week_ranges.append((None, None))
            
            # Count rent_roll units per week (same filter as drill-through)
            def count_units_in_week(units, ws_dt, we_dt):
                if not ws_dt or not we_dt:
                    return 0
                count = 0
                for u in units:
                    if not u.get("date"):
                        continue
                    try:
                        dt = datetime.strptime(u["date"], "%m/%d/%Y")
                        if ws_dt <= dt <= we_dt:
                            count += 1
                    except (ValueError, TypeError):
                        pass
                return count
            
            for w, prow in enumerate(proj_rows[:weeks]):
                week_ending = prow[0]
                report_move_ins = prow[4] or 0   # from Projected Occupancy report
                report_move_outs = prow[5] or 0  # from Projected Occupancy report
                occupied_end = prow[6] or 0
                pct_end = prow[7] or 0.0
                
                ws_dt, we_dt = week_ranges[w]
                week_start_str = ws_dt.strftime("%Y-%m-%d") if ws_dt else week_ending
                week_end_str = we_dt.strftime("%Y-%m-%d") if we_dt else week_ending
                
                # Expirations from leases (have dates, match drill-through)
                expiry_count = count_units_in_week(expiration_units, ws_dt, we_dt)
                # Renewals = expiration units that are 'Current - Future' (already renewed)
                renewal_units = [u for u in expiration_units if u.get("type") == "lease_expiration_renewed"]
                renewal_count = count_units_in_week(renewal_units, ws_dt, we_dt)
                # Notice count from rent_roll for drill-through
                notice_count = count_units_in_week(notice_units, ws_dt, we_dt)
                # Move-ins & move-outs from report (matches projected occ progression)
                rr_movein_count = count_units_in_week(move_in_units, ws_dt, we_dt)
                movein_count = rr_movein_count if rr_movein_count > 0 else report_move_ins
                # Net from report data so it matches Occ% change
                net_change = report_move_ins - report_move_outs
                
                forecast.append({
                    "week": w + 1,
                    "week_start": week_start_str,
                    "week_end": week_end_str,
                    "projected_occupied": occupied_end,
                    "projected_occupancy_pct": round(pct_end, 1),
                    "scheduled_move_ins": movein_count,
                    "scheduled_move_outs": report_move_outs,
                    "notice_move_outs": notice_count,
                    "lease_expirations": expiry_count,
                    "renewals": renewal_count,
                    "net_expirations": expiry_count - renewal_count,
                    "net_change": net_change,
                })
            
            conn.close()
            return {
                "forecast": forecast,
                "current_occupied": current_occupied,
                "total_units": total_units,
                "current_notice": len(notice_units),
                "vacant_leased": len(move_in_units),
                "undated_move_ins": undated_move_ins,
                "notice_units": notice_units,
                "move_in_units": move_in_units,
                "expiration_units": expiration_units,
                "data_source": "projected_occupancy_report",
            }
        
        # ---- Fallback: rent_roll-based estimation ----
        notice_outs_by_week = {}
        for nu in notice_units:
            try:
                dt = datetime.strptime(nu["date"], "%m/%d/%Y")
                if dt >= today:
                    week_num = (dt - today).days // 7
                    if 0 <= week_num < weeks:
                        notice_outs_by_week[week_num] = notice_outs_by_week.get(week_num, 0) + 1
            except (ValueError, TypeError):
                pass
        
        move_ins_by_week = {}
        for mu in move_in_units:
            if mu.get("date"):
                try:
                    dt = datetime.strptime(mu["date"], "%m/%d/%Y")
                    if dt >= today:
                        week_num = (dt - today).days // 7
                        if 0 <= week_num < weeks:
                            move_ins_by_week[week_num] = move_ins_by_week.get(week_num, 0) + 1
                except (ValueError, TypeError):
                    pass
        
        expirations_by_week = {}
        renewals_by_week = {}
        for eu in expiration_units:
            try:
                dt = datetime.strptime(eu["date"], "%m/%d/%Y")
                week_num = (dt - today).days // 7
                if 0 <= week_num < weeks:
                    expirations_by_week[week_num] = expirations_by_week.get(week_num, 0) + 1
                    if eu.get("type") == "lease_expiration_renewed":
                        renewals_by_week[week_num] = renewals_by_week.get(week_num, 0) + 1
            except (ValueError, TypeError):
                pass
        
        conn.close()
        
        # Build weekly forecast
        forecast = []
        running_occupied = current_occupied
        
        for w in range(weeks):
            week_start = today + timedelta(weeks=w)
            week_end = week_start + timedelta(days=6)
            
            scheduled_ins = move_ins_by_week.get(w, 0)
            notice_outs = notice_outs_by_week.get(w, 0)
            lease_expirations = expirations_by_week.get(w, 0)
            renewals = renewals_by_week.get(w, 0)
            
            net_change = scheduled_ins - notice_outs
            running_occupied = max(0, min(total_units, running_occupied + net_change))
            
            forecast.append({
                "week": w + 1,
                "week_start": week_start.strftime("%Y-%m-%d"),
                "week_end": week_end.strftime("%Y-%m-%d"),
                "projected_occupied": running_occupied,
                "projected_occupancy_pct": round(running_occupied / total_units * 100, 1) if total_units > 0 else 0,
                "scheduled_move_ins": scheduled_ins,
                "notice_move_outs": notice_outs,
                "lease_expirations": lease_expirations,
                "renewals": renewals,
                "net_expirations": lease_expirations - renewals,
                "net_change": net_change,
            })
        
        return {
            "forecast": forecast,
            "current_occupied": current_occupied,
            "total_units": total_units,
            "current_notice": len(notice_units),
            "vacant_leased": len(move_in_units),
            "undated_move_ins": undated_move_ins,
            "notice_units": notice_units,
            "move_in_units": move_in_units,
            "expiration_units": expiration_units,
            "data_source": "rent_roll_estimated",
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =========================================================================
# Reputation & Reviews
# =========================================================================

@router.get("/properties/{property_id}/reputation")
async def get_reputation(property_id: str):
    """
    GET: Multi-source reputation summary per PHH feedback.
    
    Returns:
    - sources: Array of {source, rating, review_count, url} for each ILS
    - review_power: Response rate, avg response time, needs_attention count
    - overall_rating: Weighted average across sources
    
    Currently supports Google. Architecture ready for Apartments.com, Zillow, Yelp.
    """
    from app.services.google_reviews_service import get_property_reviews
    
    sources = []
    review_power = {
        "response_rate": 0,
        "avg_response_hours": None,
        "avg_response_label": None,
        "needs_attention": 0,
        "responded": 0,
        "not_responded": 0,
        "total_reviews": 0,
    }
    
    # Google Reviews (primary source)
    try:
        google_data = await get_property_reviews(property_id)
        if google_data and not google_data.get("error"):
            sources.append({
                "source": "google",
                "name": "Google",
                "rating": google_data.get("rating"),
                "review_count": google_data.get("review_count", 0),
                "url": google_data.get("google_maps_url", ""),
                "star_distribution": google_data.get("star_distribution"),
            })
            review_power["response_rate"] = google_data.get("response_rate", 0)
            review_power["avg_response_hours"] = google_data.get("avg_response_hours")
            review_power["avg_response_label"] = google_data.get("avg_response_label")
            review_power["needs_attention"] = google_data.get("needs_response", 0)
            review_power["responded"] = google_data.get("responded", 0)
            review_power["not_responded"] = google_data.get("not_responded", 0)
            review_power["total_reviews"] = google_data.get("reviews_fetched", 0)
    except Exception:
        pass
    
    # Apartments.com reviews (via Zembra API cache)
    try:
        from app.services.apartments_reviews_service import get_apartments_reviews
        apt_data = get_apartments_reviews(property_id)
        if apt_data and apt_data.get("rating"):
            sources.append({
                "source": "apartments_com",
                "name": "Apartments.com",
                "rating": apt_data.get("rating"),
                "review_count": apt_data.get("review_count", 0),
                "url": apt_data.get("url", ""),
                "star_distribution": apt_data.get("star_distribution"),
            })
            # Aggregate review power across sources
            apt_responded = apt_data.get("responded", 0)
            apt_not_responded = apt_data.get("not_responded", 0)
            review_power["responded"] += apt_responded
            review_power["not_responded"] += apt_not_responded
            review_power["total_reviews"] += apt_data.get("reviews_fetched", 0)
            review_power["needs_attention"] += apt_data.get("needs_response", 0)
            total_resp = review_power["responded"] + review_power["not_responded"]
            review_power["response_rate"] = round((review_power["responded"] / total_resp) * 100, 1) if total_resp > 0 else 0
    except Exception:
        pass
    
    # Overall rating = weighted average of sources with data
    active_sources = [s for s in sources if s["rating"] is not None]
    if active_sources:
        total_weight = sum(s["review_count"] for s in active_sources)
        overall = sum(s["rating"] * s["review_count"] for s in active_sources) / total_weight if total_weight > 0 else 0
    else:
        overall = 0
    
    return {
        "property_id": property_id,
        "overall_rating": round(overall, 2),
        "sources": sources,
        "review_power": review_power,
    }


@router.get("/properties/{property_id}/reviews")
async def get_reviews(property_id: str):
    """
    GET: Google reviews for a property.
    Returns rating, review count, top reviews, star distribution, and response tracking metrics.
    Results are cached for 12 hours.
    """
    from app.services.google_reviews_service import get_property_reviews
    try:
        return await get_property_reviews(property_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/properties/{property_id}/apartments-reviews")
async def get_apartments_reviews_endpoint(property_id: str):
    """
    GET: Apartments.com reviews for a property (via Zembra API cache).
    Run fetch_apartments_reviews.py to refresh the cache.
    """
    from app.services.apartments_reviews_service import get_apartments_reviews
    data = get_apartments_reviews(property_id)
    if not data:
        return {"error": "No Apartments.com reviews found", "reviews": [], "source": "none"}
    return data


# =========================================================================
# AI Insights (Auto-generated Red Flags & Q&A)
# =========================================================================

@router.get("/properties/{property_id}/ai-insights")
async def get_ai_insights(property_id: str, refresh: int = 0):
    """
    GET: AI-generated red flags, alerts, and pre-computed Q&A for a property.
    Uses Claude to analyze all available property data and produce actionable insights.
    Results are cached for 1 hour. Pass refresh=1 to bust cache.
    """
    from app.services.ai_insights_service import generate_insights, _cache
    if refresh:
        _cache.pop(property_id, None)

    try:
        import asyncio

        # Gather all available data for the property
        property_data: dict = {"property_id": property_id}

        # Parallel async fetches (biggest speed win — these were sequential before)
        async def _fetch_occ():
            try:
                occ = await occupancy_service.get_occupancy_metrics(property_id, Timeframe.CM)
                return ("occupancy", occ.model_dump() if hasattr(occ, 'model_dump') else {}, occ.property_name)
            except Exception:
                return None

        async def _fetch_pricing():
            try:
                p = await pricing_service.get_unit_pricing(property_id)
                return ("pricing", p.model_dump() if hasattr(p, 'model_dump') else {})
            except Exception:
                return None

        async def _fetch_funnel():
            try:
                f = await get_leasing_funnel(property_id, Timeframe.L30)
                return ("funnel", f.model_dump() if hasattr(f, 'model_dump') else {})
            except Exception:
                return None

        async def _fetch_expirations():
            try:
                return ("expirations", await occupancy_service.get_lease_expirations(property_id))
            except Exception:
                return None

        async def _fetch_tradeouts():
            try:
                return ("tradeouts", await pricing_service.get_lease_tradeouts(property_id))
            except Exception:
                return None

        async def _fetch_ltl():
            try:
                return ("loss_to_lease", await pricing_service.get_loss_to_lease(property_id))
            except Exception:
                return None

        results = await asyncio.gather(
            _fetch_occ(), _fetch_pricing(), _fetch_funnel(),
            _fetch_expirations(), _fetch_tradeouts(), _fetch_ltl(),
            return_exceptions=True
        )

        for r in results:
            if r is None or isinstance(r, Exception):
                continue
            if r[0] == "occupancy":
                property_data["occupancy"] = r[1]
                property_data["property_name"] = r[2]
            else:
                property_data[r[0]] = r[1]

        # Delinquency from unified DB (same source as the Delinquency tab)
        try:
            from app.db.schema import UNIFIED_DB_PATH
            import sqlite3
            
            # Normalize property_id for unified DB lookup
            norm_id = property_id
            if property_id.startswith("kairoi-"):
                norm_id = property_id.replace("kairoi-", "").replace("-", "_")
            
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            c = conn.cursor()
            c.execute("""
                SELECT SUM(CASE WHEN total_delinquent > 0 THEN total_delinquent ELSE 0 END),
                       COUNT(CASE WHEN total_delinquent > 0 THEN 1 END),
                       SUM(CASE WHEN balance_0_30 > 0 THEN balance_0_30 ELSE 0 END),
                       SUM(CASE WHEN balance_31_60 > 0 THEN balance_31_60 ELSE 0 END),
                       SUM(CASE WHEN balance_over_90 > 0 THEN balance_over_90 ELSE 0 END),
                       SUM(CASE WHEN is_eviction = 1 THEN 1 ELSE 0 END)
                FROM unified_delinquency
                WHERE unified_property_id = ? OR unified_property_id = ?
            """, (property_id, norm_id))
            row = c.fetchone()
            conn.close()
            if row and row[0]:
                property_data["delinquency"] = {
                    "total_delinquent": row[0] or 0,
                    "delinquent_units": row[1] or 0,
                    "over_30": row[2] or 0,
                    "over_60": row[3] or 0,
                    "over_90": row[4] or 0,
                    "eviction_count": row[5] or 0,
                }
        except Exception:
            pass

        # Risk scores
        try:
            from app.db.schema import UNIFIED_DB_PATH
            import sqlite3
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            c = conn.cursor()
            c.execute("SELECT * FROM unified_risk_scores WHERE unified_property_id = ?", (property_id,))
            row = c.fetchone()
            conn.close()
            if row:
                cols = [d[0] for d in c.description]
                risk_dict = dict(zip(cols, row))
                property_data["risk_scores"] = {
                    "total_scored": risk_dict.get("total_scored", 0),
                    "churn": {
                        "high_risk": risk_dict.get("churn_high_risk", 0),
                        "medium_risk": risk_dict.get("churn_medium_risk", 0),
                        "low_risk": risk_dict.get("churn_low_risk", 0),
                    },
                    "delinquency": {
                        "high_risk": risk_dict.get("delinq_high_risk", 0),
                        "medium_risk": risk_dict.get("delinq_medium_risk", 0),
                    },
                }
        except Exception:
            pass

        # Shows
        try:
            from app.db.schema import REALPAGE_DB_PATH
            import sqlite3
            pms = get_pms_config(property_id)
            if pms.realpage_siteid:
                conn = sqlite3.connect(REALPAGE_DB_PATH)
                c = conn.cursor()
                c.execute("""
                    SELECT COUNT(*) FROM realpage_activity
                    WHERE property_id = ?
                      AND activity_type IN ('Visit', 'Visit (return)', 'Videotelephony - Tour')
                      AND activity_date >= date('now', '-7 days')
                """, (pms.realpage_siteid,))
                row = c.fetchone()
                conn.close()
                property_data["shows"] = {"total_shows": row[0] if row else 0}
        except Exception:
            pass

        # Reputation data (Google + Apartments.com)
        try:
            from app.services.google_reviews_service import get_property_reviews
            google_rev = await get_property_reviews(property_id)
            if google_rev and not google_rev.get("error"):
                property_data["google_reviews"] = {
                    "rating": google_rev.get("rating"),
                    "review_count": google_rev.get("review_count", 0),
                    "response_rate": google_rev.get("response_rate", 0),
                    "needs_response": google_rev.get("needs_response", 0),
                }
        except Exception:
            pass
        try:
            from app.services.apartments_reviews_service import get_apartments_reviews
            apt_rev = get_apartments_reviews(property_id)
            if apt_rev and apt_rev.get("rating"):
                property_data["apartments_reviews"] = {
                    "rating": apt_rev.get("rating"),
                    "review_count": apt_rev.get("review_count", 0),
                    "response_rate": apt_rev.get("response_rate", 0),
                    "needs_response": apt_rev.get("needs_response", 0),
                }
        except Exception:
            pass

        # Inject custom watchpoints (WS8)
        try:
            from app.services.watchpoint_service import format_watchpoints_for_ai
            current_metrics = await _gather_current_metrics(property_id)
            wp_text = format_watchpoints_for_ai(property_id, current_metrics)
            if wp_text:
                property_data["watchpoint_summary"] = wp_text
        except Exception:
            pass

        result = await generate_insights(property_id, property_data)
        # Include property_name so frontend can tag alerts in multi-property mode
        result["property_name"] = property_data.get("property_name", property_id)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


# =========================================================================
# Custom AI Watchpoints (WS8)
# =========================================================================

@router.get("/properties/{property_id}/watchpoints")
async def get_watchpoints(property_id: str):
    """
    GET: User-defined metric watchpoints for a property.
    Returns watchpoints with their current evaluation status.
    """
    from app.services.watchpoint_service import (
        get_watchpoints as _get_wps,
        evaluate_watchpoints,
        AVAILABLE_METRICS,
    )
    
    # Gather current metrics for evaluation
    current_metrics = await _gather_current_metrics(property_id)
    
    wps = _get_wps(property_id)
    evaluated = evaluate_watchpoints(property_id, current_metrics)
    
    return {
        "property_id": property_id,
        "watchpoints": evaluated,
        "available_metrics": AVAILABLE_METRICS,
        "current_metrics": current_metrics,
    }


@router.post("/properties/{property_id}/watchpoints")
async def create_watchpoint(property_id: str, body: dict):
    """
    POST: Create a new watchpoint for a property.
    Body: { metric, operator, threshold, label? }
    """
    from app.services.watchpoint_service import add_watchpoint
    
    metric = body.get("metric")
    operator = body.get("operator")
    threshold = body.get("threshold")
    label = body.get("label")
    
    if not metric or not operator or threshold is None:
        raise HTTPException(status_code=400, detail="Required: metric, operator, threshold")
    
    try:
        wp = add_watchpoint(property_id, metric, operator, float(threshold), label)
        return wp
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/properties/{property_id}/watchpoints/{watchpoint_id}")
async def delete_watchpoint(property_id: str, watchpoint_id: str):
    """DELETE: Remove a watchpoint."""
    from app.services.watchpoint_service import remove_watchpoint
    
    removed = remove_watchpoint(property_id, watchpoint_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Watchpoint not found")
    return {"deleted": True}


@router.patch("/properties/{property_id}/watchpoints/{watchpoint_id}/toggle")
async def toggle_watchpoint_endpoint(property_id: str, watchpoint_id: str):
    """PATCH: Toggle a watchpoint's enabled/disabled state."""
    from app.services.watchpoint_service import toggle_watchpoint
    
    wp = toggle_watchpoint(property_id, watchpoint_id)
    if not wp:
        raise HTTPException(status_code=404, detail="Watchpoint not found")
    return wp


async def _gather_current_metrics(property_id: str) -> dict:
    """Collect current metric values for watchpoint evaluation."""
    metrics = {}
    
    try:
        occ = await occupancy_service.get_occupancy_metrics(property_id, Timeframe.CM)
        if occ:
            metrics["occupancy_pct"] = occ.physical_occupancy or 0
            metrics["vacant_units"] = occ.vacant_units or 0
            metrics["on_notice_units"] = occ.notice_break_units or 0
            metrics["aged_vacancy_90"] = occ.aged_vacancy_90_plus or 0
    except Exception:
        pass
    
    try:
        import sqlite3
        from pathlib import Path
        db_path = UNIFIED_DB_PATH
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("""
            SELECT SUM(CASE WHEN total_delinquent > 0 THEN total_delinquent ELSE 0 END),
                   COUNT(CASE WHEN total_delinquent > 0 THEN 1 END)
            FROM unified_delinquency WHERE unified_property_id = ?
        """, (property_id,))
        row = c.fetchone()
        if row:
            metrics["delinquent_total"] = row[0] or 0
            metrics["delinquent_units"] = row[1] or 0
        conn.close()
    except Exception:
        pass
    
    try:
        p = await pricing_service.get_unit_pricing(property_id)
        if p and p.floorplans:
            total_rent = sum(f.in_place_rent * f.unit_count for f in p.floorplans if f.in_place_rent)
            total_units = sum(f.unit_count for f in p.floorplans if f.in_place_rent)
            metrics["avg_rent"] = round(total_rent / total_units, 0) if total_units > 0 else 0
    except Exception:
        pass
    
    try:
        import sqlite3 as _sq
        _conn = _sq.connect(UNIFIED_DB_PATH)
        _c = _conn.cursor()
        _c.execute("""
            SELECT total_units, vacant_units, preleased_vacant, notice_units
            FROM unified_occupancy_metrics
            WHERE unified_property_id = ?
            ORDER BY snapshot_date DESC LIMIT 1
        """, (property_id,))
        _row = _c.fetchone()
        _conn.close()
        if _row:
            total_u = _row[0] or 0
            vacant = _row[1] or 0
            preleased = _row[2] or 0
            on_notice = _row[3] or 0
            atr = max(0, vacant + on_notice - preleased)
            metrics["atr"] = atr
            metrics["atr_pct"] = round(atr / total_u * 100, 1) if total_u > 0 else 0
    except Exception:
        pass
    
    try:
        from app.services.google_reviews_service import get_property_reviews
        reviews = await get_property_reviews(property_id)
        if reviews and not reviews.get("error"):
            if reviews.get("rating"):
                metrics["google_rating"] = reviews["rating"]
            if reviews.get("response_rate") is not None:
                metrics["response_rate"] = reviews["response_rate"]
    except Exception:
        pass
    
    return metrics


# =========================================================================
# Financials (Monthly Transaction Summary — Report 4020)
# =========================================================================

@router.get("/properties/{property_id}/financials")
async def get_financials(property_id: str):
    """
    GET: Financial summary and transaction detail for a property.
    
    Data source: realpage_monthly_transaction_summary + realpage_monthly_transaction_detail
    in realpage_raw.db, keyed by RealPage site_id.
    
    Returns P&L-like summary (gross rent, charges, losses, collections)
    plus transaction-level detail grouped by category.
    """
    import sqlite3
    from app.property_config.properties import get_pms_config
    
    try:
        pms_config = get_pms_config(property_id)
        site_id = pms_config.realpage_siteid
        if not site_id:
            raise HTTPException(status_code=404, detail="No RealPage site_id for property")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Property not found")
    
    raw_db = REALPAGE_DB_PATH
    try:
        conn = sqlite3.connect(raw_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get latest summary
        cursor.execute("""
            SELECT * FROM realpage_monthly_transaction_summary
            WHERE property_id = ?
            ORDER BY fiscal_period DESC
            LIMIT 1
        """, (site_id,))
        summary_row = cursor.fetchone()
        
        if not summary_row:
            conn.close()
            raise HTTPException(status_code=404, detail="No financial data found")
        
        fiscal_period = summary_row["fiscal_period"]
        
        summary = {
            "fiscal_period": fiscal_period,
            "report_date": summary_row["report_date"],
            "gross_market_rent": summary_row["gross_market_rent"],
            "gain_to_lease": summary_row["gain_to_lease"],
            "loss_to_lease": summary_row["loss_to_lease"],
            "gross_potential": summary_row["gross_potential"],
            "total_other_charges": summary_row["total_other_charges"],
            "total_possible_collections": summary_row["total_possible_collections"],
            "total_collection_losses": summary_row["total_collection_losses"],
            "total_adjustments": summary_row["total_adjustments"],
            "past_due_end_prior": summary_row["past_due_end_prior"],
            "prepaid_end_prior": summary_row["prepaid_end_prior"],
            "past_due_end_current": summary_row["past_due_end_current"],
            "prepaid_end_current": summary_row["prepaid_end_current"],
            "net_change_past_due_prepaid": summary_row["net_change_past_due_prepaid"],
            "total_losses_and_adjustments": summary_row["total_losses_and_adjustments"],
            "current_monthly_collections": summary_row["current_monthly_collections"],
            "total_monthly_collections": summary_row["total_monthly_collections"],
        }
        
        # Effective collection rate
        if summary["total_possible_collections"] and summary["total_possible_collections"] > 0:
            summary["collection_rate"] = round(
                summary["total_monthly_collections"] / summary["total_possible_collections"] * 100, 1
            )
        else:
            summary["collection_rate"] = 0
        
        # Get transaction detail for same fiscal period
        cursor.execute("""
            SELECT transaction_group, transaction_code, description,
                   ytd_last_month, this_month, ytd_through_month
            FROM realpage_monthly_transaction_detail
            WHERE property_id = ? AND fiscal_period = ?
            ORDER BY transaction_group, transaction_code
        """, (site_id, fiscal_period))
        detail_rows = cursor.fetchall()
        
        # Cross-reference box score for unit counts and avg rents (latest date only)
        cursor.execute("""
            SELECT SUM(total_units), SUM(occupied_units), SUM(vacant_units),
                   SUM(total_units * avg_market_rent) / NULLIF(SUM(total_units), 0),
                   SUM(occupied_units * avg_actual_rent) / NULLIF(SUM(occupied_units), 0)
            FROM realpage_box_score
            WHERE property_id = ? AND report_date = (
                SELECT MAX(report_date) FROM realpage_box_score WHERE property_id = ?
            )
        """, (site_id, site_id))
        bs = cursor.fetchone()
        total_units = bs[0] or 0 if bs else 0
        occupied_units = bs[1] or 0 if bs else 0
        vacant_units = bs[2] or 0 if bs else 0
        avg_market_rent = round(bs[3] or 0, 2) if bs else 0
        avg_effective_rent = round(bs[4] or 0, 2) if bs else 0
        
        # Group by accounting categories
        group_names = {
            "CA": "Rent",
            "CB": "Late Fees",
            "CC": "NSF Fees",
            "CE": "Keys/Locks/Gate Cards",
            "CG": "Transfer/Termination Fees",
            "CH": "Administrative Fees",
            "CI": "Pet Rent",
            "CJ": "Utilities & Services",
            "CL": "Parking & Storage",
            "IU": "Incoming Deposits",
            "OU": "Outgoing Deposits",
            "PP": "Referral Credits",
            "PS": "Deposit Activity",
            "PT": "Vacancy Loss",
            "PV": "Bad Debt",
            "PW": "Concessions",
            "PX": "Gain/Loss to Lease",
            "PZ": "Payments",
        }
        
        charges = []
        losses = []
        payments = []
        
        # Accumulators for computed metrics
        concession_total = 0.0
        bad_debt_total = 0.0
        vacancy_loss_total = 0.0
        other_income_total = 0.0
        payment_methods = {}
        
        for row in detail_rows:
            item = {
                "group": row["transaction_group"],
                "group_name": group_names.get(row["transaction_group"], row["transaction_group"]),
                "code": row["transaction_code"],
                "description": row["description"],
                "ytd_last_month": row["ytd_last_month"],
                "this_month": row["this_month"],
                "ytd_through": row["ytd_through_month"],
            }
            grp = row["transaction_group"]
            amt = row["this_month"] or 0
            
            if grp in ("CA", "CB", "CC", "CE", "CG", "CH", "CI", "CJ", "CL"):
                charges.append(item)
                if grp != "CA":
                    other_income_total += amt
            elif grp in ("PT", "PW", "PX", "PV", "PP"):
                losses.append(item)
                if grp == "PW":
                    concession_total += abs(amt)
                elif grp == "PV":
                    bad_debt_total += abs(amt)
                elif grp == "PT":
                    vacancy_loss_total += abs(amt)
            elif grp in ("PS", "PZ", "IU", "OU"):
                payments.append(item)
                if grp == "PZ" and amt != 0:
                    desc = row["description"] or "Other"
                    payment_methods[desc] = payment_methods.get(desc, 0) + amt
        
        # Compute derived metrics
        gp = summary["gross_potential"] or 0
        gmr = summary["gross_market_rent"] or 0
        ltl = summary["loss_to_lease"] or 0
        collections = summary["total_monthly_collections"] or 0
        possible = summary["total_possible_collections"] or 0
        
        # Enrich from Lost Rent Summary (Report 4279) when transaction summary has 0
        if ltl == 0 or vacancy_loss_total == 0:
            try:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='realpage_lost_rent_summary'")
                if cursor.fetchone():
                    cursor.execute("""
                        SELECT SUM(market_rent - lease_rent), SUM(lost_rent_not_charged),
                               SUM(CASE WHEN move_out_date IS NOT NULL AND move_out_date != '' THEN market_rent ELSE 0 END)
                        FROM realpage_lost_rent_summary
                        WHERE property_id = ?
                    """, (site_id,))
                    lr_row = cursor.fetchone()
                    if lr_row:
                        lr_loss_to_lease = lr_row[0] or 0
                        lr_vacant_rent = lr_row[2] or 0
                        if ltl == 0 and lr_loss_to_lease != 0:
                            ltl = -abs(lr_loss_to_lease)
                        if vacancy_loss_total == 0 and lr_vacant_rent != 0:
                            vacancy_loss_total = abs(lr_vacant_rent)
            except Exception:
                pass  # Lost rent table not available
        
        conn.close()
        
        computed = {
            "total_units": total_units,
            "occupied_units": occupied_units,
            "vacant_units": vacant_units,
            "avg_market_rent": avg_market_rent,
            "avg_effective_rent": avg_effective_rent,
            "rev_pau": round(collections / total_units, 2) if total_units > 0 else 0,
            "economic_occupancy": round(collections / possible * 100, 1) if possible > 0 else 0,
            "loss_to_lease_pct": round(ltl / gmr * 100, 2) if gmr > 0 else 0,
            "concession_total": round(concession_total, 2),
            "concession_pct": round(concession_total / gp * 100, 2) if gp > 0 else 0,
            "bad_debt_total": round(bad_debt_total, 2),
            "bad_debt_pct": round(bad_debt_total / gp * 100, 2) if gp > 0 else 0,
            "vacancy_loss_total": round(vacancy_loss_total, 2),
            "vacancy_loss_pct": round(vacancy_loss_total / gp * 100, 2) if gp > 0 else 0,
            "other_income": round(other_income_total, 2),
            "other_income_per_unit": round(other_income_total / total_units, 2) if total_units > 0 else 0,
            "payment_methods": [{"method": k, "amount": round(v, 2)} for k, v in sorted(payment_methods.items(), key=lambda x: -abs(x[1]))],
        }
        
        return {
            "property_id": property_id,
            "summary": summary,
            "computed": computed,
            "charges": charges,
            "losses": losses,
            "payments": payments,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get financials: {str(e)}")


# =========================================================================
# Marketing (Primary Advertising Source — Report 4158)
# =========================================================================

@router.get("/properties/{property_id}/marketing")
async def get_marketing(property_id: str, timeframe: str = "ytd"):
    """Marketing funnel data from RealPage Primary Advertising Source report.
    
    timeframe: ytd | mtd | l30 | l7 — matches leasing funnel timeframes.
    Filters stored data by date_range tag, falling back to best available.
    """
    import sqlite3
    from app.property_config.properties import get_pms_config
    from datetime import datetime, timedelta
    
    try:
        pms_config = get_pms_config(property_id)
        site_id = pms_config.realpage_siteid
        if not site_id:
            raise HTTPException(status_code=404, detail="No RealPage site_id for property")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Property not found")
    
    # Compute expected date range label for the timeframe
    now = datetime.now()
    if timeframe == "mtd":
        tf_start = now.replace(day=1).strftime("%m/%d/%Y")
    elif timeframe == "l30":
        tf_start = (now - timedelta(days=30)).strftime("%m/%d/%Y")
    elif timeframe == "l7":
        tf_start = (now - timedelta(days=7)).strftime("%m/%d/%Y")
    else:  # ytd
        tf_start = f"01/01/{now.year}"
    tf_tag = f"{timeframe}"
    
    raw_db = REALPAGE_DB_PATH
    try:
        conn = sqlite3.connect(raw_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Check table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='realpage_advertising_source'")
        if not cursor.fetchone():
            conn.close()
            return {"property_id": property_id, "sources": [], "totals": {}, "date_range": "", "timeframe": timeframe}
        
        # Try exact timeframe match first, then fall back to any data
        cursor.execute("""
            SELECT source, new_prospects, phone_calls, visits, return_visits,
                   leases, net_leases, cancelled_denied, 
                   prospect_to_lease_pct, visit_to_lease_pct, date_range,
                   COALESCE(timeframe_tag, '') as timeframe_tag
            FROM realpage_advertising_source
            WHERE property_id = ? AND timeframe_tag = ?
            ORDER BY new_prospects DESC
        """, (site_id, tf_tag))
        rows = cursor.fetchall()
        
        # Fallback: if no timeframe-tagged data, return whatever we have
        if not rows:
            cursor.execute("""
                SELECT source, new_prospects, phone_calls, visits, return_visits,
                       leases, net_leases, cancelled_denied, 
                       prospect_to_lease_pct, visit_to_lease_pct, date_range,
                       COALESCE(timeframe_tag, '') as timeframe_tag
                FROM realpage_advertising_source
                WHERE property_id = ?
                ORDER BY new_prospects DESC
            """, (site_id,))
            rows = cursor.fetchall()
        
        conn.close()
        
        if not rows:
            return {"property_id": property_id, "sources": [], "totals": {}, "date_range": "", "timeframe": timeframe}
        
        sources = []
        t_prospects = t_calls = t_visits = t_leases = t_net = 0
        date_range = rows[0]["date_range"] if rows else ""
        
        for row in rows:
            src = {
                "source": row["source"],
                "new_prospects": row["new_prospects"] or 0,
                "phone_calls": row["phone_calls"] or 0,
                "visits": row["visits"] or 0,
                "return_visits": row["return_visits"] or 0,
                "leases": row["leases"] or 0,
                "net_leases": row["net_leases"] or 0,
                "cancelled_denied": row["cancelled_denied"] or 0,
                "prospect_to_lease_pct": row["prospect_to_lease_pct"] or 0,
                "visit_to_lease_pct": row["visit_to_lease_pct"] or 0,
            }
            sources.append(src)
            t_prospects += src["new_prospects"]
            t_calls += src["phone_calls"]
            t_visits += src["visits"]
            t_leases += src["leases"]
            t_net += src["net_leases"]
        
        totals = {
            "total_prospects": t_prospects,
            "total_calls": t_calls,
            "total_visits": t_visits,
            "total_leases": t_leases,
            "total_net_leases": t_net,
            "overall_prospect_to_lease": round(t_net / t_prospects * 100, 1) if t_prospects > 0 else 0,
            "overall_visit_to_lease": round(t_net / t_visits * 100, 1) if t_visits > 0 else 0,
        }
        
        return {"property_id": property_id, "sources": sources, "totals": totals, "date_range": date_range, "timeframe": timeframe}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get marketing data: {str(e)}")


# =========================================================================
# Maintenance / Make Ready (Reports 4186 + 4189)
# =========================================================================

@router.get("/properties/{property_id}/maintenance")
async def get_maintenance(property_id: str):
    """Make-ready pipeline + closed turns from RealPage reports."""
    import sqlite3
    from app.property_config.properties import get_pms_config
    
    try:
        pms_config = get_pms_config(property_id)
        site_id = pms_config.realpage_siteid
        if not site_id:
            raise HTTPException(status_code=404, detail="No RealPage site_id for property")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Property not found")
    
    raw_db = REALPAGE_DB_PATH
    try:
        conn = sqlite3.connect(raw_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Open make-ready pipeline
        pipeline = []
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='realpage_make_ready'")
        if cursor.fetchone():
            cursor.execute("""
                SELECT unit, sqft, days_vacant, date_vacated, date_due, num_work_orders
                FROM realpage_make_ready
                WHERE property_id = ?
                ORDER BY days_vacant DESC
            """, (site_id,))
            make_ready_rows = cursor.fetchall()
            
            # Join unit status from unified_units (rent roll)
            unit_status_map = {}
            try:
                import os
                from app.db.schema import DB_DIR
                unified_path = os.path.join(DB_DIR, "unified.db")
                uconn = sqlite3.connect(unified_path)
                uconn.row_factory = sqlite3.Row
                ucur = uconn.cursor()
                ucur.execute("""
                    SELECT unit_number, status, occupancy_status
                    FROM unified_units
                    WHERE unified_property_id = ?
                """, (property_id,))
                for urow in ucur.fetchall():
                    unit_status_map[str(urow["unit_number"]).strip()] = {
                        "status": urow["status"] or "",
                        "lease_status": urow["occupancy_status"] or "",
                    }
                uconn.close()
            except Exception:
                pass  # unified DB not available, skip status enrichment
            
            for row in make_ready_rows:
                unit_key = str(row["unit"]).strip()
                unit_info = unit_status_map.get(unit_key, {})
                pipeline.append({
                    "unit": row["unit"],
                    "sqft": row["sqft"] or 0,
                    "days_vacant": row["days_vacant"] or 0,
                    "date_vacated": row["date_vacated"] or "",
                    "date_due": row["date_due"] or "",
                    "num_work_orders": row["num_work_orders"] or 0,
                    "unit_status": unit_info.get("status", ""),
                    "lease_status": unit_info.get("lease_status", ""),
                })
        
        # Closed make-ready
        completed = []
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='realpage_closed_make_ready'")
        if cursor.fetchone():
            cursor.execute("""
                SELECT unit, num_work_orders, date_closed, amount_charged
                FROM realpage_closed_make_ready
                WHERE property_id = ?
                ORDER BY date_closed DESC
            """, (site_id,))
            for row in cursor.fetchall():
                completed.append({
                    "unit": row["unit"],
                    "num_work_orders": row["num_work_orders"] or 0,
                    "date_closed": row["date_closed"] or "",
                    "amount_charged": row["amount_charged"] or 0,
                })
        
        conn.close()
        
        # Summary stats
        total_pipeline = len(pipeline)
        avg_days = round(sum(p["days_vacant"] for p in pipeline) / total_pipeline, 1) if total_pipeline > 0 else 0
        overdue = sum(1 for p in pipeline if p["days_vacant"] > 14)
        total_completed = len(completed)
        
        return {
            "property_id": property_id,
            "pipeline": pipeline,
            "completed": completed,
            "summary": {
                "units_in_pipeline": total_pipeline,
                "avg_days_vacant": avg_days,
                "overdue_count": overdue,
                "completed_this_period": total_completed,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get maintenance data: {str(e)}")


# =========================================================================
# Lost Rent Summary (Report 4279) — enhances financials
# =========================================================================

@router.get("/properties/{property_id}/lost-rent")
async def get_lost_rent(property_id: str):
    """Unit-level loss-to-lease data from RealPage Lost Rent Summary report."""
    import sqlite3
    from app.property_config.properties import get_pms_config
    
    try:
        pms_config = get_pms_config(property_id)
        site_id = pms_config.realpage_siteid
        if not site_id:
            raise HTTPException(status_code=404, detail="No RealPage site_id for property")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=404, detail="Property not found")
    
    raw_db = REALPAGE_DB_PATH
    try:
        conn = sqlite3.connect(raw_db)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='realpage_lost_rent_summary'")
        if not cursor.fetchone():
            conn.close()
            return {"property_id": property_id, "units": [], "summary": {}}
        
        cursor.execute("""
            SELECT unit, market_rent, lease_rent, rent_charged, loss_to_rent,
                   gain_to_rent, vacancy_current, lost_rent_not_charged,
                   move_in_date, move_out_date, fiscal_period
            FROM realpage_lost_rent_summary
            WHERE property_id = ?
            ORDER BY lost_rent_not_charged DESC
        """, (site_id,))
        rows = cursor.fetchall()
        conn.close()
        
        if not rows:
            return {"property_id": property_id, "units": [], "summary": {}}
        
        units = []
        total_market = total_lease = total_lost = 0
        occupied_count = vacant_count = 0
        
        for row in rows:
            mr = row["market_rent"] or 0
            lr = row["lease_rent"] or 0
            lost = row["lost_rent_not_charged"] or 0
            units.append({
                "unit": row["unit"],
                "market_rent": mr,
                "lease_rent": lr,
                "rent_charged": row["rent_charged"] or 0,
                "lost_rent": lost,
                "loss_pct": round((mr - lr) / mr * 100, 1) if mr > 0 else 0,
                "move_out_date": row["move_out_date"] or "",
            })
            total_market += mr
            total_lease += lr
            total_lost += lost
            if row["move_out_date"]:
                vacant_count += 1
            else:
                occupied_count += 1
        
        fiscal = rows[0]["fiscal_period"] if rows else ""
        
        summary = {
            "fiscal_period": fiscal,
            "total_units": len(units),
            "occupied_count": occupied_count,
            "vacant_count": vacant_count,
            "avg_market_rent": round(total_market / len(units), 0) if units else 0,
            "avg_lease_rent": round(total_lease / len(units), 0) if units else 0,
            "total_lost_rent": round(total_lost, 0),
            "loss_to_lease_pct": round((total_market - total_lease) / total_market * 100, 1) if total_market > 0 else 0,
            "avg_loss_per_unit": round(total_lost / len(units), 0) if units else 0,
        }
        
        return {"property_id": property_id, "units": units, "summary": summary}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get lost rent data: {str(e)}")
