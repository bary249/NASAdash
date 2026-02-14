"""
Occupancy & Leasing Service - Owner Dashboard V2
Implements Module 1 (Occupancy & Exposure) and Module 2 (Marketing Funnel) from spec.
READ-ONLY: Only retrieves and transforms data, no modifications.
"""
import logging
from typing import List, Optional, Dict, Any
from datetime import date, timedelta
from app.clients.yardi_client import YardiClient
from app.clients.realpage_client import RealPageClient
from app.models import (
    Timeframe, OccupancyMetrics, ExposureMetrics, LeasingFunnelMetrics,
    UnitRaw, ResidentRaw, ProspectRaw, PropertyInfo
)
from app.models.unified import PMSSource
from app.property_config.properties import get_pms_config, ALL_PROPERTIES
from app.services.timeframe import (
    get_date_range, format_date_iso, format_date_yardi,
    parse_yardi_date, days_between, is_within_days, is_in_period
)

logger = logging.getLogger(__name__)


class OccupancyService:
    """Service for calculating occupancy and leasing metrics from PMS data."""
    
    def __init__(self):
        self.yardi = YardiClient()
    
    def _get_realpage_client(self, property_id: str) -> RealPageClient:
        """Get a RealPage client configured for the specific property."""
        pms_config = get_pms_config(property_id)
        return RealPageClient(
            pmcid=pms_config.realpage_pmcid,
            siteid=pms_config.realpage_siteid,
            licensekey=pms_config.realpage_licensekey,
        )
    
    def _get_pms_type(self, property_id: str) -> PMSSource:
        """Determine PMS type for a property."""
        if property_id in ALL_PROPERTIES:
            return get_pms_config(property_id).pms_type
        
        # Check unified.db for RealPage properties
        import sqlite3
        from pathlib import Path
        try:
            db_path = Path(__file__).parent.parent / "db" / "data" / "unified.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT pms_source FROM unified_properties WHERE unified_property_id = ?", (property_id,))
            row = cursor.fetchone()
            conn.close()
            if row and row[0] == 'realpage':
                return PMSSource.REALPAGE
        except Exception:
            pass
        
        return PMSSource.YARDI
    
    async def get_property_list(self) -> List[PropertyInfo]:
        """Get list of all properties from Yardi and unified.db (RealPage)."""
        import sqlite3
        from pathlib import Path
        
        properties = []
        
        # Get RealPage properties from unified.db first
        try:
            db_path = Path(__file__).parent.parent / "db" / "data" / "unified.db"
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT unified_property_id, name, city, state, address
                FROM unified_properties
                WHERE pms_source = 'realpage'
            """)
            prop_rows = cursor.fetchall()
            
            # Derive floor count per property from unit numbers
            # Heuristic: unit 502 → floor 5, unit 1134 → floor 11
            # Skip 5-digit units (garden-style BBBUU encoding) and max floor > 20
            floor_counts: dict = {}
            has_5digit: set = set()
            cursor.execute("""
                SELECT unified_property_id, unit_number
                FROM unified_units
            """)
            for urow in cursor.fetchall():
                pid, unum = urow[0], urow[1]
                try:
                    num = int(unum)
                    if num >= 10000:
                        has_5digit.add(pid)
                        continue
                    if num >= 100:
                        floor = num // 100
                    else:
                        floor = 1
                    if pid not in floor_counts:
                        floor_counts[pid] = set()
                    floor_counts[pid].add(floor)
                except (ValueError, TypeError):
                    pass
            # Remove properties with building-encoded units or unreasonable floor counts
            for pid in has_5digit:
                floor_counts.pop(pid, None)
            for pid in list(floor_counts.keys()):
                if max(floor_counts[pid]) > 20:
                    floor_counts.pop(pid)
            
            conn.close()
            
            # Get Google Places ratings (cached)
            google_ratings = {}
            try:
                from app.services.google_places_service import get_all_property_ratings
                google_ratings = await get_all_property_ratings()
            except Exception as e:
                logger.warning(f"[OCCUPANCY] Failed to get Google ratings: {e}")

            for row in prop_rows:
                pid = row[0]
                fc = len(floor_counts.get(pid, set())) or None
                g_data = google_ratings.get(pid, {})
                properties.append(PropertyInfo(
                    id=pid,
                    name=row[1] or pid,
                    city=row[2] or "",
                    state=row[3] or "",
                    address=row[4] or "",
                    floor_count=fc,
                    google_rating=g_data.get("rating"),
                    google_review_count=g_data.get("review_count"),
                ))
        except Exception:
            pass
        
        # Get Yardi properties
        try:
            data = await self.yardi.get_property_configurations()
            
            if isinstance(data, dict):
                result = data.get("GetPropertyConfigurationsResult", data)
                if isinstance(result, dict):
                    props = result.get("Properties", result)
                    if isinstance(props, dict):
                        prop_list = props.get("Property", [])
                    else:
                        prop_list = props
                    
                    if isinstance(prop_list, dict):
                        prop_list = [prop_list]
                    
                    for p in prop_list if isinstance(prop_list, list) else []:
                        address = p.get("Address", {})
                        properties.append(PropertyInfo(
                            id=p.get("Code", p.get("PropertyCode", "")),
                            name=p.get("MarketingName", p.get("Name", p.get("Code", ""))),
                            city=address.get("City", "") if isinstance(address, dict) else "",
                            state=address.get("State", "") if isinstance(address, dict) else "",
                            address=address.get("Address1", "") if isinstance(address, dict) else ""
                        ))
        except Exception:
            pass
        
        return properties
    
    async def get_occupancy_metrics(
        self, 
        property_id: str, 
        timeframe: Timeframe = Timeframe.CM
    ) -> OccupancyMetrics:
        """
        Calculate occupancy metrics per spec Module 1.
        
        For YTD: Returns averaged occupancy over the period.
        For CM/PM: Returns point-in-time occupancy.
        """
        period_start, period_end = get_date_range(timeframe)
        today = date.today()
        
        pms_type = self._get_pms_type(property_id)
        
        # Get unit data based on PMS type
        if pms_type == PMSSource.REALPAGE:
            # Use unified_occupancy_metrics as primary source (has correct preleased data)
            unified_result = await self._get_occupancy_from_unified(property_id, timeframe)
            if unified_result.total_units > 0:
                return unified_result
            
            # Fall back to SOAP API if unified.db has no data
            if property_id not in ALL_PROPERTIES:
                return unified_result
            
            units = await self._get_realpage_units(property_id)
            # Get future residents (Applicant - Lease Signed) from RealPage
            future_list = await self._get_realpage_future_residents(property_id)
            property_name = ALL_PROPERTIES.get(property_id, type('', (), {'name': property_id})).name
            
            # If no units from API, return empty
            if not units:
                return unified_result
        else:
            units_data = await self.yardi.get_unit_information(property_id)
            units = self._extract_units(units_data)
            future_residents = await self.yardi.get_residents_by_status(property_id, "Future")
            future_list = self._extract_residents_raw(future_residents, "Future")
            property_name = self._extract_property_name_from_units(units_data, property_id)
        
        total_units = len(units)
        occupied_units = sum(1 for u in units if u.get("occupancy_status") == "occupied")
        vacant_units = total_units - occupied_units
        
        # Preleased vacant: vacant units that have a future lease
        preleased_units = set(r.get("unit", "") for r in future_list)
        preleased_vacant = sum(1 for u in units 
                              if u.get("occupancy_status") == "vacant" 
                              and u.get("unit_id") in preleased_units)
        
        leased_units = occupied_units + preleased_vacant
        
        # Calculate available units (RealPage specific)
        available_units = 0
        if pms_type == PMSSource.REALPAGE:
            available_units = sum(1 for u in units if u.get("available", False))
        else:
            # For Yardi, available = vacant and ready
            available_units = sum(1 for u in units 
                                if u.get("occupancy_status") == "vacant" 
                                and u.get("ready_status") == "ready")
        
        # Vacancy breakdown
        vacant_ready = sum(1 for u in units 
                         if u.get("occupancy_status") == "vacant" 
                         and u.get("ready_status") == "ready")
        vacant_not_ready = vacant_units - vacant_ready
        
        # Aged vacancy (>90 days)
        aged_vacancy = sum(1 for u in units 
                         if u.get("occupancy_status") == "vacant"
                         and u.get("days_vacant", 0) > 90)
        
        # Calculate percentages
        physical_occupancy = round(occupied_units / total_units * 100, 1) if total_units > 0 else 0
        leased_percentage = round(leased_units / total_units * 100, 1) if total_units > 0 else 0
        
        return OccupancyMetrics(
            property_id=property_id,
            property_name=property_name,
            timeframe=timeframe.value,
            period_start=format_date_iso(period_start),
            period_end=format_date_iso(period_end),
            total_units=total_units,
            occupied_units=occupied_units,
            vacant_units=vacant_units,
            leased_units=leased_units,
            preleased_vacant=preleased_vacant,
            physical_occupancy=physical_occupancy,
            leased_percentage=leased_percentage,
            vacant_ready=vacant_ready,
            vacant_not_ready=vacant_not_ready,
            available_units=available_units,
            aged_vacancy_90_plus=aged_vacancy
        )
    
    async def _get_occupancy_from_unified(
        self,
        property_id: str,
        timeframe: Timeframe = Timeframe.CM
    ) -> OccupancyMetrics:
        """Fallback to read occupancy from unified.db for synced RealPage data."""
        import sqlite3
        from pathlib import Path
        
        period_start, period_end = get_date_range(timeframe)
        db_path = Path(__file__).parent.parent / "db" / "data" / "unified.db"
        
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Get property name
            cursor.execute("SELECT name FROM unified_properties WHERE unified_property_id = ?", (property_id,))
            row = cursor.fetchone()
            property_name = row[0] if row else property_id
            
            # Get occupancy metrics
            cursor.execute("""
                SELECT total_units, occupied_units, vacant_units, leased_units,
                       preleased_vacant, notice_units, model_units, down_units,
                       physical_occupancy, leased_percentage,
                       COALESCE(vacant_ready, 0), COALESCE(vacant_not_ready, 0),
                       COALESCE(notice_break_units, 0)
                FROM unified_occupancy_metrics
                WHERE unified_property_id = ?
                ORDER BY snapshot_date DESC LIMIT 1
            """, (property_id,))
            row = cursor.fetchone()
            
            if not row:
                conn.close()
            else:
                conn.close()
                vacant_units = row[2] or 0
                vacant_ready = row[10] or 0
                vacant_not_ready = row[11] or 0
                notice_break = row[12] or 0
                # Fallback: if no vacant_ready data, use total vacant
                if vacant_ready == 0 and vacant_not_ready == 0 and vacant_units > 0:
                    vacant_ready = vacant_units
                return OccupancyMetrics(
                    property_id=property_id,
                    property_name=property_name,
                    timeframe=timeframe.value,
                    period_start=format_date_iso(period_start),
                    period_end=format_date_iso(period_end),
                    total_units=row[0] or 0,
                    occupied_units=row[1] or 0,
                    vacant_units=vacant_units,
                    leased_units=row[3] or 0,
                    preleased_vacant=row[4] or 0,
                    physical_occupancy=row[8] or 0,
                    leased_percentage=row[9] or 0,
                    notice_break_units=notice_break,
                    vacant_ready=vacant_ready,
                    vacant_not_ready=vacant_not_ready,
                    available_units=vacant_ready if vacant_ready > 0 else vacant_units,
                    aged_vacancy_90_plus=0
                )
        except Exception:
            pass
        
        # Return empty metrics if nothing found
        return OccupancyMetrics(
            property_id=property_id,
            property_name=property_id,
            timeframe=timeframe.value,
            period_start=format_date_iso(period_start),
            period_end=format_date_iso(period_end),
            total_units=0, occupied_units=0, vacant_units=0, leased_units=0,
            preleased_vacant=0, physical_occupancy=0, leased_percentage=0,
            vacant_ready=0, vacant_not_ready=0, available_units=0, aged_vacancy_90_plus=0
        )
    
    async def get_exposure_metrics(
        self, 
        property_id: str, 
        timeframe: Timeframe = Timeframe.CM
    ) -> ExposureMetrics:
        """
        Calculate exposure metrics per spec Module 1.
        
        Exposure = (Vacant + Pending Move-outs) - Pending Move-ins
        """
        period_start, period_end = get_date_range(timeframe)
        today = date.today()
        
        pms_type = self._get_pms_type(property_id)
        
        if pms_type == PMSSource.REALPAGE:
            # RealPage path
            units = await self._get_realpage_units(property_id)
            all_residents = await self._get_all_realpage_residents(property_id)
            future_residents = await self._get_realpage_future_residents(property_id)
            
            # Filter by status
            notice_residents = [r for r in all_residents if r.get("status") == "Notice"]
            past_residents = [r for r in all_residents if r.get("status") == "Past"]
            current_residents = [r for r in all_residents if r.get("status") == "Current"]
        else:
            # Yardi path
            notice_data = await self.yardi.get_residents_by_status(property_id, "Notice")
            past_data = await self.yardi.get_residents_by_status(property_id, "Past")
            future_data = await self.yardi.get_residents_by_status(property_id, "Future")
            current_data = await self.yardi.get_residents_by_status(property_id, "Current")
            
            notice_residents = self._extract_residents_raw(notice_data, "Notice")
            past_residents = self._extract_residents_raw(past_data, "Past")
            future_residents = self._extract_residents_raw(future_data, "Future")
            current_residents = self._extract_residents_raw(current_data, "Current")
            
            units_data = await self.yardi.get_unit_information(property_id)
            units = self._extract_units(units_data)
        
        # Total notices
        notices_total = len(notice_residents)
        vacant_count = sum(1 for u in units if u.get("occupancy_status") == "vacant")
        
        # Notices by timeframe (move-out within 30/60 days)
        notices_30 = sum(1 for r in notice_residents 
                       if self._move_out_within_days(r, 30, today))
        notices_60 = sum(1 for r in notice_residents 
                       if self._move_out_within_days(r, 60, today))
        
        # Pending move-outs within 30/60 days
        pending_moveouts_30 = notices_30
        pending_moveouts_60 = notices_60
        
        # Pending move-ins within 30/60 days
        pending_moveins_30 = sum(1 for r in future_residents 
                                if self._move_in_within_days(r, 30, today))
        pending_moveins_60 = sum(1 for r in future_residents 
                                if self._move_in_within_days(r, 60, today))
        
        # Exposure calculation: (Vacant + Pending Move-outs) - Pending Move-ins
        exposure_30 = (vacant_count + pending_moveouts_30) - pending_moveins_30
        exposure_60 = (vacant_count + pending_moveouts_60) - pending_moveins_60
        
        # Move-ins/outs in period
        move_ins = sum(1 for r in (future_residents + current_residents)
                      if self._is_in_period(r, "move_in_date", period_start, period_end))
        move_outs = sum(1 for r in past_residents
                       if self._is_in_period(r, "move_out_date", period_start, period_end))
        
        return ExposureMetrics(
            property_id=property_id,
            timeframe=timeframe.value,
            period_start=format_date_iso(period_start),
            period_end=format_date_iso(period_end),
            exposure_30_days=max(0, exposure_30),
            exposure_60_days=max(0, exposure_60),
            notices_total=notices_total,
            notices_30_days=notices_30,
            notices_60_days=notices_60,
            pending_moveins_30_days=pending_moveins_30,
            pending_moveins_60_days=pending_moveins_60,
            move_ins=move_ins,
            move_outs=move_outs,
            net_absorption=move_ins - move_outs
        )
    
    async def get_leasing_funnel(
        self, 
        property_id: str, 
        timeframe: Timeframe = Timeframe.CM
    ) -> LeasingFunnelMetrics:
        """
        Calculate leasing funnel metrics per spec Module 2.
        
        Lead: Unique contact/inquiry (Guest Card)
        Tour: Verified visit (Show event)
        Application: Submitted application
        Lease Sign: Countersigned lease
        
        For RealPage properties: Uses imported Excel report data if available.
        """
        period_start, period_end = get_date_range(timeframe)
        pms_type = self._get_pms_type(property_id)
        
        # For RealPage properties, try to use imported Excel data first
        if pms_type == PMSSource.REALPAGE:
            imported_data = self._get_imported_leasing_data(property_id, period_start, period_end)
            if imported_data:
                return self._build_funnel_from_imported(property_id, timeframe, period_start, period_end, imported_data)
        
        # Fall back to Yardi guest activity
        guest_data = await self.yardi.get_guest_activity(
            property_id, 
            format_date_yardi(period_start),
            format_date_yardi(period_end)
        )
        
        events = self._extract_events(guest_data)
        
        # Count by event type
        # Lead = first contact (Email, CallFromProspect, Webservice, Walkin)
        leads = sum(1 for e in events 
                   if e.get("event_type") in ["Email", "CallFromProspect", "Webservice", "Walkin"]
                   and e.get("first_contact") == True)
        
        # Tour = Show event
        tours = sum(1 for e in events if e.get("event_type") == "Show")
        
        # Application = Application event
        applications = sum(1 for e in events if e.get("event_type") == "Application")
        
        # Lease Sign = LeaseSign event (must be countersigned per spec)
        lease_signs = sum(1 for e in events if e.get("event_type") == "LeaseSign")
        
        # Denials
        denials = sum(1 for e in events if e.get("event_type") == "ApplicationDenied")
        
        # Calculate conversion rates
        lead_to_tour = round(tours / leads * 100, 1) if leads > 0 else 0
        tour_to_app = round(applications / tours * 100, 1) if tours > 0 else 0
        app_to_lease = round(lease_signs / applications * 100, 1) if applications > 0 else 0
        lead_to_lease = round(lease_signs / leads * 100, 1) if leads > 0 else 0
        
        return LeasingFunnelMetrics(
            property_id=property_id,
            timeframe=timeframe.value,
            period_start=format_date_iso(period_start),
            period_end=format_date_iso(period_end),
            leads=leads,
            tours=tours,
            applications=applications,
            lease_signs=lease_signs,
            denials=denials,
            lead_to_tour_rate=lead_to_tour,
            tour_to_app_rate=tour_to_app,
            app_to_lease_rate=app_to_lease,
            lead_to_lease_rate=lead_to_lease
        )
    
    def _get_imported_leasing_data(self, property_id: str, period_start: date, period_end: date) -> Optional[Dict[str, Any]]:
        """Get imported leasing activity data from database."""
        import sqlite3
        from app.db.schema import UNIFIED_DB_PATH
        
        try:
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Get totals row for the property
            cursor.execute("""
                SELECT * FROM imported_leasing_activity 
                WHERE property_id = ? AND section_type = 'totals'
                ORDER BY imported_at DESC
                LIMIT 1
            """, (property_id,))
            
            totals_row = cursor.fetchone()
            if not totals_row:
                conn.close()
                return None
            
            totals = dict(totals_row)
            
            # Get consultant breakdown
            cursor.execute("""
                SELECT * FROM imported_leasing_activity 
                WHERE property_id = ? AND section_type = 'by_consultant'
                AND imported_at = (SELECT MAX(imported_at) FROM imported_leasing_activity WHERE property_id = ?)
            """, (property_id, property_id))
            consultants = [dict(row) for row in cursor.fetchall()]
            
            # Get day breakdown
            cursor.execute("""
                SELECT * FROM imported_leasing_activity 
                WHERE property_id = ? AND section_type = 'by_day_of_week'
                AND imported_at = (SELECT MAX(imported_at) FROM imported_leasing_activity WHERE property_id = ?)
            """, (property_id, property_id))
            days = [dict(row) for row in cursor.fetchall()]
            
            # Get applications from lease summary report (if available)
            applications = 0
            try:
                cursor.execute("""
                    SELECT applications FROM imported_lease_summary 
                    WHERE property_id = ?
                    ORDER BY imported_at DESC
                    LIMIT 1
                """, (property_id,))
                lease_summary_row = cursor.fetchone()
                if lease_summary_row:
                    applications = lease_summary_row['applications']
            except:
                pass  # Table might not exist yet
            
            conn.close()
            
            return {
                'totals': totals,
                'by_consultant': consultants,
                'by_day_of_week': days,
                'applications': applications
            }
            
        except Exception as e:
            logger.warning(f"Error getting imported leasing data: {e}")
            return None
    
    def _build_funnel_from_imported(
        self, 
        property_id: str, 
        timeframe: Timeframe,
        period_start: date,
        period_end: date,
        imported_data: Dict[str, Any]
    ) -> LeasingFunnelMetrics:
        """Build leasing funnel metrics from imported Excel data."""
        totals = imported_data.get('totals', {})
        consultants = imported_data.get('by_consultant', [])
        
        # Sum up metrics from consultant data (more accurate than totals)
        new_prospects = sum(c.get('new_prospects', 0) for c in consultants)
        activities = sum(c.get('activities', 0) for c in consultants)
        visits = sum(c.get('visits', 0) for c in consultants)
        quotes = sum(c.get('quotes', 0) for c in consultants)
        leases = sum(c.get('leases', 0) for c in consultants)
        move_ins = sum(c.get('move_ins', 0) for c in consultants)
        
        # Map to funnel stages:
        # - Leads = new_prospects (first contacts)
        # - Tours = visits (property visits)
        # - Applications = from Lease Summary report (imported_lease_summary table)
        # - Lease Signs = leases
        leads = new_prospects if new_prospects > 0 else totals.get('activities', 0)
        tours = visits if visits > 0 else 0
        applications = imported_data.get('applications', 0)  # From Lease Summary report
        lease_signs = leases if leases > 0 else 0
        
        # Calculate conversion rates
        lead_to_tour = round(tours / leads * 100, 1) if leads > 0 else 0
        tour_to_app = round(applications / tours * 100, 1) if tours > 0 else 0
        app_to_lease = round(lease_signs / applications * 100, 1) if applications > 0 else 0
        lead_to_lease = round(lease_signs / leads * 100, 1) if leads > 0 else 0
        
        return LeasingFunnelMetrics(
            property_id=property_id,
            timeframe=timeframe.value,
            period_start=format_date_iso(period_start),
            period_end=format_date_iso(period_end),
            leads=leads,
            tours=tours,
            applications=applications,
            lease_signs=lease_signs,
            denials=0,  # Not available in RealPage report
            lead_to_tour_rate=lead_to_tour,
            tour_to_app_rate=tour_to_app,
            app_to_lease_rate=app_to_lease,
            lead_to_lease_rate=lead_to_lease
        )
    
    async def get_raw_units(self, property_id: str) -> List[dict]:
        """Get raw unit data for drill-through. Supports both Yardi and RealPage."""
        pms_type = self._get_pms_type(property_id)
        
        if pms_type == PMSSource.REALPAGE:
            return await self._get_realpage_units(property_id)
        else:
            units_data = await self.yardi.get_unit_information(property_id)
            return self._extract_units(units_data)
    
    async def get_raw_residents(
        self, 
        property_id: str, 
        status: str = "all",
        timeframe: Timeframe = Timeframe.CM,
        metric_filter: Optional[str] = None
    ) -> List[dict]:
        """
        Get raw resident data for drill-through.
        
        metric_filter options:
        - "move_ins": Only residents who moved in during the period
        - "move_outs": Only residents who moved out during the period
        - "notices_30": Notices with move-out in next 30 days
        - "notices_60": Notices with move-out in next 60 days
        - None: All residents matching status
        """
        period_start, period_end = get_date_range(timeframe)
        today = date.today()
        all_residents = []
        
        pms_type = self._get_pms_type(property_id)
        
        # For RealPage, use the unified resident fetch
        if pms_type == PMSSource.REALPAGE:
            rp_residents = await self._get_all_realpage_residents(property_id)
            # Also get applicants as future residents
            future_residents = await self._get_realpage_future_residents(property_id)
            
            # Map RealPage status to filter
            for r in rp_residents:
                r_status = r.get("status", "").lower()
                if status != "all" and r_status != status.lower():
                    continue
                all_residents.append(r)
            
            # Add future residents (applicants)
            if status == "all" or status.lower() == "future":
                for r in future_residents:
                    all_residents.append(r)
            
            return all_residents
        
        # Yardi flow
        # Determine which statuses to query based on metric_filter
        if metric_filter == "move_ins":
            statuses = ["Current", "Future"]
        elif metric_filter == "move_outs":
            statuses = ["Past"]
        elif metric_filter in ["notices_30", "notices_60"]:
            statuses = ["Notice"]
        elif status == "all":
            statuses = ["Current", "Notice", "Past", "Future"]
        else:
            statuses = [status]
        
        for s in statuses:
            data = await self.yardi.get_residents_by_status(property_id, s)
            residents = self._extract_residents_raw(data, s)
            
            for r in residents:
                # Apply metric-specific filtering to match exact counts
                if metric_filter == "move_ins":
                    # Only include if move-in date is within period
                    move_in = parse_yardi_date(r.get("move_in_date", ""))
                    if move_in and is_in_period(move_in, period_start, period_end):
                        all_residents.append(r)
                elif metric_filter == "move_outs":
                    # Only include if move-out date is within period
                    move_out = parse_yardi_date(r.get("move_out_date", ""))
                    if move_out and is_in_period(move_out, period_start, period_end):
                        all_residents.append(r)
                elif metric_filter == "notices_30":
                    # Notices with move-out in next 30 days
                    move_out = parse_yardi_date(r.get("move_out_date", "") or r.get("lease_end", ""))
                    if move_out and is_within_days(move_out, today, 30):
                        all_residents.append(r)
                elif metric_filter == "notices_60":
                    # Notices with move-out in next 60 days
                    move_out = parse_yardi_date(r.get("move_out_date", "") or r.get("lease_end", ""))
                    if move_out and is_within_days(move_out, today, 60):
                        all_residents.append(r)
                else:
                    # No special filter - return all matching status
                    all_residents.append(r)
        
        return all_residents
    
    async def get_raw_prospects(
        self, 
        property_id: str,
        stage: Optional[str] = None,
        timeframe: Timeframe = Timeframe.CM
    ) -> List[dict]:
        """Get raw prospect data for drill-through."""
        period_start, period_end = get_date_range(timeframe)
        
        data = await self.yardi.get_guest_activity(
            property_id,
            format_date_yardi(period_start),
            format_date_yardi(period_end)
        )
        
        prospects = self._extract_prospects(data)
        
        # Filter by stage if specified
        if stage:
            stage_events = {
                "leads": ["Email", "CallFromProspect", "Webservice", "Walkin"],
                "tours": ["Show"],
                "applications": ["Application"],
                "lease_signs": ["LeaseSign"]
            }
            if stage in stage_events:
                prospects = [p for p in prospects if p.get("last_event") in stage_events[stage]]
        
        return prospects
    
    async def get_occupancy_trend(
        self, 
        property_id: str,
        start_date_str: Optional[str] = None,
        end_date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate historical occupancy trend by reconstructing from move-in/move-out dates.
        
        Returns selected period vs equivalent prior period physical occupancy.
        
        Args:
            property_id: Property identifier
            start_date_str: Start date (YYYY-MM-DD). Defaults to 7 days ago.
            end_date_str: End date (YYYY-MM-DD). Defaults to today.
        
        Methodology:
        - For each historical date, count units that were occupied
        - A unit is occupied if: move_in_date <= target_date AND (move_out_date is null OR move_out_date > target_date)
        - Compares selected period to the same duration before start_date
        """
        today = date.today()
        
        # Parse dates or use defaults
        if end_date_str:
            end_date = parse_yardi_date(end_date_str) or today
        else:
            end_date = today
            
        if start_date_str:
            start_date = parse_yardi_date(start_date_str) or (end_date - timedelta(days=7))
        else:
            start_date = end_date - timedelta(days=7)
        
        # Calculate period duration and prior period
        period_days = (end_date - start_date).days
        prior_end = start_date - timedelta(days=1)
        prior_start = prior_end - timedelta(days=period_days)
        
        pms_type = self._get_pms_type(property_id)
        logger.info(f"[TREND] Property {property_id} uses {pms_type.value}")
        logger.info(f"[TREND] Period: {start_date} to {end_date} ({period_days} days)")
        logger.info(f"[TREND] Prior: {prior_start} to {prior_end}")
        
        # Get all residents (current, past, future) to reconstruct history
        if pms_type == PMSSource.REALPAGE:
            residents = await self._get_all_realpage_residents(property_id)
            units = await self._get_realpage_units(property_id)
        else:
            residents = await self._get_all_yardi_residents(property_id)
            units_data = await self.yardi.get_unit_information(property_id)
            units = self._extract_units(units_data)
        
        total_units = len(units)
        
        # Current period occupancy (at end_date)
        if end_date == today:
            # Use live unit status for today
            current_occupied = sum(1 for u in units if u.get("occupancy_status") == "occupied")
        else:
            # Reconstruct for historical end_date
            current_occupied = self._calculate_occupied_at_date(residents, end_date)
        current_occupancy = round(current_occupied / total_units * 100, 1) if total_units > 0 else 0
        
        # Prior period occupancy (at prior_end)
        prior_occupied = self._calculate_occupied_at_date(residents, prior_end)
        prior_occupancy = round(prior_occupied / total_units * 100, 1) if total_units > 0 else 0
        
        # Calculate change
        occupancy_change = round(current_occupancy - prior_occupancy, 1)
        
        logger.info(f"[TREND] {property_id}: Current={current_occupancy}%, Prior={prior_occupancy}%, Change={occupancy_change}%")
        
        return {
            "property_id": property_id,
            "current_period": {
                "start_date": format_date_iso(start_date),
                "end_date": format_date_iso(end_date),
                "days": period_days,
                "occupied_units": current_occupied,
                "total_units": total_units,
                "physical_occupancy": current_occupancy
            },
            "previous_period": {
                "start_date": format_date_iso(prior_start),
                "end_date": format_date_iso(prior_end),
                "days": period_days,
                "occupied_units": prior_occupied,
                "total_units": total_units,
                "physical_occupancy": prior_occupancy
            },
            "change": {
                "occupancy_points": occupancy_change,
                "direction": "up" if occupancy_change > 0 else ("down" if occupancy_change < 0 else "flat")
            },
            "methodology": (
                f"Historical occupancy is reconstructed from resident move-in and move-out dates. "
                f"A unit is counted as occupied on a given date if a resident had moved in before or on that date "
                f"and had not yet moved out. Compares {period_days}-day period ending {format_date_iso(end_date)} "
                f"to the prior {period_days}-day period."
            )
        }
    
    async def get_all_trends(
        self, 
        property_id: str,
        start_date_str: Optional[str] = None,
        end_date_str: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate trends for ALL metrics: occupancy, exposure, and funnel.
        
        Returns current period vs equivalent prior period for each metric.
        """
        today = date.today()
        
        # Parse dates or use defaults
        if end_date_str:
            end_date = parse_yardi_date(end_date_str) or today
        else:
            end_date = today
            
        if start_date_str:
            start_date = parse_yardi_date(start_date_str) or (end_date - timedelta(days=7))
        else:
            start_date = end_date - timedelta(days=7)
        
        # Calculate period duration and prior period
        period_days = (end_date - start_date).days
        prior_end = start_date - timedelta(days=1)
        prior_start = prior_end - timedelta(days=period_days)
        
        logger.info(f"[ALL_TRENDS] Property {property_id}")
        logger.info(f"[ALL_TRENDS] Current: {start_date} to {end_date} ({period_days} days)")
        logger.info(f"[ALL_TRENDS] Prior: {prior_start} to {prior_end}")
        
        pms_type = self._get_pms_type(property_id)
        
        # Get all data needed for calculations
        if pms_type == PMSSource.REALPAGE:
            residents = await self._get_all_realpage_residents(property_id)
            units = await self._get_realpage_units(property_id)
        else:
            residents = await self._get_all_yardi_residents(property_id)
            units_data = await self.yardi.get_unit_information(property_id)
            units = self._extract_units(units_data)
        
        total_units = len(units)
        
        # === OCCUPANCY TRENDS ===
        # Current period occupancy (at end_date)
        if end_date == today:
            current_occupied = sum(1 for u in units if u.get("occupancy_status") == "occupied")
            current_vacant = total_units - current_occupied
        else:
            current_occupied = self._calculate_occupied_at_date(residents, end_date)
            current_vacant = total_units - current_occupied
        
        # Prior period occupancy (at prior_end)
        prior_occupied = self._calculate_occupied_at_date(residents, prior_end)
        prior_vacant = total_units - prior_occupied
        
        current_occupancy = round(current_occupied / total_units * 100, 1) if total_units > 0 else 0
        prior_occupancy = round(prior_occupied / total_units * 100, 1) if total_units > 0 else 0
        
        # === EXPOSURE TRENDS (Move-ins, Move-outs) ===
        current_move_ins = self._count_moves_in_period(residents, "move_in_date", start_date, end_date)
        current_move_outs = self._count_moves_in_period(residents, "move_out_date", start_date, end_date)
        prior_move_ins = self._count_moves_in_period(residents, "move_in_date", prior_start, prior_end)
        prior_move_outs = self._count_moves_in_period(residents, "move_out_date", prior_start, prior_end)
        
        current_net_absorption = current_move_ins - current_move_outs
        prior_net_absorption = prior_move_ins - prior_move_outs
        
        # === FUNNEL TRENDS (Leads, Tours, Applications, Lease Signs) ===
        # Get guest activity for both periods
        current_funnel = await self._get_funnel_counts(property_id, start_date, end_date)
        prior_funnel = await self._get_funnel_counts(property_id, prior_start, prior_end)
        
        return {
            "property_id": property_id,
            "period_days": period_days,
            "current_period": {
                "start_date": format_date_iso(start_date),
                "end_date": format_date_iso(end_date),
            },
            "prior_period": {
                "start_date": format_date_iso(prior_start),
                "end_date": format_date_iso(prior_end),
            },
            "occupancy": {
                "current": {
                    "occupied_units": current_occupied,
                    "vacant_units": current_vacant,
                    "total_units": total_units,
                    "physical_occupancy": current_occupancy,
                    "leased_percentage": current_occupancy,  # Approximation without preleased data
                },
                "prior": {
                    "occupied_units": prior_occupied,
                    "vacant_units": prior_vacant,
                    "total_units": total_units,
                    "physical_occupancy": prior_occupancy,
                    "leased_percentage": prior_occupancy,
                }
            },
            "exposure": {
                "current": {
                    "move_ins": current_move_ins,
                    "move_outs": current_move_outs,
                    "net_absorption": current_net_absorption,
                },
                "prior": {
                    "move_ins": prior_move_ins,
                    "move_outs": prior_move_outs,
                    "net_absorption": prior_net_absorption,
                }
            },
            "funnel": {
                "current": current_funnel,
                "prior": prior_funnel,
            },
            "methodology": (
                f"Compares {period_days}-day period ({format_date_iso(start_date)} to {format_date_iso(end_date)}) "
                f"to the prior {period_days}-day period ({format_date_iso(prior_start)} to {format_date_iso(prior_end)}). "
                f"Occupancy is reconstructed from move-in/move-out dates. "
                f"Exposure counts moves within each period. "
                f"Funnel counts guest activity events within each period."
            )
        }
    
    def _count_moves_in_period(
        self, 
        residents: List[dict], 
        date_field: str, 
        period_start: date, 
        period_end: date
    ) -> int:
        """Count residents with a move date within the specified period."""
        count = 0
        for res in residents:
            date_str = res.get(date_field, "")
            if date_str:
                move_date = parse_yardi_date(date_str)
                if move_date and period_start <= move_date <= period_end:
                    count += 1
        return count
    
    async def _get_funnel_counts(
        self, 
        property_id: str, 
        period_start: date, 
        period_end: date
    ) -> Dict[str, Any]:
        """Get funnel metric counts for a specific period."""
        try:
            guest_data = await self.yardi.get_guest_activity(
                property_id, 
                format_date_yardi(period_start),
                format_date_yardi(period_end)
            )
            events = self._extract_events(guest_data)
            
            leads = sum(1 for e in events 
                       if e.get("event_type") in ["Email", "CallFromProspect", "Webservice", "Walkin"]
                       and e.get("first_contact") == True)
            tours = sum(1 for e in events if e.get("event_type") == "Show")
            applications = sum(1 for e in events if e.get("event_type") == "Application")
            lease_signs = sum(1 for e in events if e.get("event_type") == "LeaseSign")
            
            # Calculate conversion rates
            lead_to_tour = round(tours / leads * 100, 1) if leads > 0 else 0
            tour_to_app = round(applications / tours * 100, 1) if tours > 0 else 0
            lead_to_lease = round(lease_signs / leads * 100, 1) if leads > 0 else 0
            
            return {
                "leads": leads,
                "tours": tours,
                "applications": applications,
                "lease_signs": lease_signs,
                "lead_to_tour_rate": lead_to_tour,
                "tour_to_app_rate": tour_to_app,
                "lead_to_lease_rate": lead_to_lease,
            }
        except Exception as e:
            logger.warning(f"Failed to get funnel data for {property_id}: {e}")
            return {
                "leads": 0,
                "tours": 0,
                "applications": 0,
                "lease_signs": 0,
                "lead_to_tour_rate": 0,
                "tour_to_app_rate": 0,
                "lead_to_lease_rate": 0,
            }
    
    def _calculate_occupied_at_date(self, residents: List[dict], target_date: date) -> int:
        """
        Calculate how many units were occupied on a specific date.
        
        A unit is occupied if: move_in_date <= target_date AND (move_out_date is null OR move_out_date > target_date)
        """
        occupied_units = set()
        
        for res in residents:
            unit_id = res.get("unit") or res.get("unit_id") or res.get("unit_number")
            if not unit_id:
                continue
            
            move_in_str = res.get("move_in_date", "")
            move_out_str = res.get("move_out_date", "")
            
            move_in = parse_yardi_date(move_in_str) if move_in_str else None
            move_out = parse_yardi_date(move_out_str) if move_out_str else None
            
            # Unit is occupied if resident had moved in and not yet moved out
            if move_in and move_in <= target_date:
                if move_out is None or move_out > target_date:
                    occupied_units.add(str(unit_id))
        
        return len(occupied_units)
    
    async def _get_all_yardi_residents(self, property_id: str) -> List[dict]:
        """Get all residents (current, past, future) from Yardi."""
        all_residents = []
        for status in ["Current", "Past", "Future", "Notice"]:
            data = await self.yardi.get_residents_by_status(property_id, status)
            all_residents.extend(self._extract_residents_raw(data, status))
        return all_residents
    
    async def _get_all_realpage_residents(self, property_id: str) -> List[dict]:
        """Get all residents from RealPage."""
        client = self._get_realpage_client(property_id)
        residents = await client.get_residents(property_id, status=None)  # All statuses
        
        # RealPage doesn't have "Notice" status - residents who gave notice are still "Current"
        # Re-categorize Current residents with notice_date to "Notice" status
        for r in residents:
            if r.get("status") == "Current" and r.get("notice_date"):
                r["status"] = "Notice"
        
        return residents
    
    async def _get_realpage_future_residents(self, property_id: str) -> List[dict]:
        """Get future residents (Applicant - Lease Signed) from RealPage."""
        client = self._get_realpage_client(property_id)
        all_residents = await client.get_residents(property_id, status=None)
        
        # Filter for "Applicant - Lease Signed" only (exclude "Former Applicant")
        future_residents = []
        for r in all_residents:
            status = r.get("status", "").lower()
            # Must contain "applicant" but NOT "former"
            if "applicant" in status and "former" not in status:
                future_residents.append({
                    "unit": r.get("unit", ""),
                    "first_name": r.get("first_name", ""),
                    "last_name": r.get("last_name", ""),
                    "move_in_date": r.get("move_in_date", ""),
                    "status": "Future",
                })
        
        logger.info(f"[REALPAGE] Found {len(future_residents)} future residents (Applicant - Lease Signed)")
        return future_residents
    
    async def _get_realpage_units(self, property_id: str) -> List[dict]:
        """Get units from RealPage with occupancy status and drill-through fields."""
        client = self._get_realpage_client(property_id)
        units_raw = await client.get_units_raw(property_id)
        today = date.today()
        
        units = []
        for u in units_raw:
            # Map RealPage fields to standard format
            vacant = u.get("Vacant", "F") == "T"
            available = u.get("Available", "F") == "T"
            on_notice_date = u.get("OnNoticeForDate", "")
            available_date_str = u.get("AvailableDate", "")
            made_ready_date = u.get("UnitMadeReadyDate", "")
            
            # Calculate days vacant (from available_date if vacant)
            days_vacant = 0
            if vacant and available_date_str:
                try:
                    avail_date = parse_yardi_date(available_date_str)
                    if avail_date and avail_date <= today:
                        days_vacant = (today - avail_date).days
                except:
                    pass
            
            units.append({
                "unit_id": u.get("UnitID", ""),
                "unit_number": u.get("UnitNumber", ""),
                "occupancy_status": "vacant" if vacant else "occupied",
                "ready_status": "ready" if made_ready_date else "not_ready",
                "available": available,  # RealPage Available flag (vacant ready OR occupied on notice)
                "floorplan": u.get("FloorplanName", ""),
                "bedrooms": int(u.get("Bedrooms", 0) or 0),
                "bathrooms": float(u.get("Bathrooms", 0) or 0),
                "square_feet": int(u.get("RentableSqft", 0) or 0),
                "market_rent": float(u.get("MarketRent", 0) or 0),
                "available_date": available_date_str,
                "on_notice_date": on_notice_date,
                "made_ready_date": made_ready_date,
                "days_vacant": days_vacant
            })
        return units
    
    # ---- Private extraction methods ----
    
    def _extract_property_name_from_units(self, units_data: dict, default: str) -> str:
        """Extract property name from Yardi units response."""
        property_name = default
        if isinstance(units_data, dict):
            result = units_data.get("GetUnitInformationResult", units_data)
            if isinstance(result, dict):
                ui = result.get("UnitInformation", result)
                if isinstance(ui, dict):
                    prop = ui.get("Property", ui)
                    if isinstance(prop, dict):
                        property_name = prop.get("@attributes", {}).get("MarketingName", default)
        return property_name
    
    def _extract_units(self, data: dict) -> List[dict]:
        """Extract unit list from Yardi response."""
        units = []
        seen_ids = set()
        today = date.today()
        
        if isinstance(data, dict):
            result = data.get("GetUnitInformationResult", data)
            if isinstance(result, dict):
                unit_info = result.get("UnitInformation", result)
            else:
                unit_info = result
            if isinstance(unit_info, dict):
                prop = unit_info.get("Property", unit_info)
                if isinstance(prop, dict):
                    units_container = prop.get("Units", prop)
                    if isinstance(units_container, dict):
                        unit_data = units_container.get("UnitInfo", [])
                    else:
                        unit_data = units_container
                    
                    if isinstance(unit_data, dict):
                        unit_data = [unit_data]
                    
                    for u in unit_data if isinstance(unit_data, list) else []:
                        unit_elem = u.get("Unit", u)
                        unit_id = str(u.get("UnitID", ""))
                        
                        if unit_id in seen_ids:
                            continue
                        seen_ids.add(unit_id)
                        
                        if isinstance(unit_elem, dict):
                            status_desc = unit_elem.get("UnitEconomicStatusDescription", "").lower()
                            
                            is_vacant = "vacant" in status_desc
                            is_ready = "ready" in status_desc or "market ready" in status_desc
                            
                            # Calculate days vacant
                            available_date_str = unit_elem.get("DateAvailable", "")
                            available_date = parse_yardi_date(available_date_str)
                            days_vacant = days_between(available_date, today) if available_date and is_vacant else 0
                            
                            units.append({
                                "unit_id": unit_id,
                                "floorplan": unit_elem.get("FloorplanName", ""),
                                "unit_type": unit_elem.get("UnitType", unit_elem.get("FloorplanName", "")),
                                "unit_number": unit_elem.get("UnitID", ""),
                                "bedrooms": self._safe_int(unit_elem.get("UnitBedrooms", 0)),
                                "bathrooms": self._safe_float(unit_elem.get("UnitBathrooms", 0)),
                                "square_feet": self._safe_int(unit_elem.get("MinSquareFeet", 0)),
                                "market_rent": self._safe_float(unit_elem.get("MarketRent", 0)),
                                "status": unit_elem.get("UnitEconomicStatusDescription", ""),
                                "occupancy_status": "vacant" if is_vacant else "occupied",
                                "ready_status": "ready" if is_ready else "not_ready",
                                "available": is_vacant and is_ready,  # Available = vacant AND ready
                                "days_vacant": days_vacant,
                                "available_date": available_date_str
                            })
        return units
    
    def _extract_residents_raw(self, data: dict, status: str) -> List[dict]:
        """Extract resident list from Yardi response."""
        residents = []
        if isinstance(data, dict):
            result = data.get("GetResidentsByStatusResult", data)
            if isinstance(result, dict):
                mits = result.get("MITS-ResidentData", result)
            else:
                mits = result
            
            if isinstance(mits, dict):
                prop_res = mits.get("PropertyResidents", mits)
                if isinstance(prop_res, dict):
                    res_container = prop_res.get("Residents", prop_res)
                    if isinstance(res_container, dict):
                        res_data = res_container.get("Resident", [])
                    else:
                        res_data = res_container
                    
                    if isinstance(res_data, dict):
                        res_data = [res_data]
                    
                    for r in res_data if isinstance(res_data, list) else []:
                        residents.append({
                            "resident_id": r.get("@attributes", {}).get("tCode", r.get("tCode", "")),
                            "first_name": r.get("FirstName", ""),
                            "last_name": r.get("LastName", ""),
                            "unit": r.get("UnitCode", ""),
                            "rent": self._safe_float(r.get("Rent", 0)),
                            "status": r.get("Status", status),
                            "move_in_date": r.get("MoveInDate", ""),
                            "move_out_date": r.get("MoveOutDate", ""),
                            "lease_start": r.get("LeaseFromDate", ""),
                            "lease_end": r.get("LeaseToDate", ""),
                            "notice_date": r.get("NoticeDate", "")
                        })
        return residents
    
    def _extract_events(self, data: dict) -> List[dict]:
        """Extract guest activity events from Yardi ILS response."""
        events = []
        if isinstance(data, dict):
            result = data.get("GetYardiGuestActivity_LoginResult", data)
            if isinstance(result, dict):
                lead_mgmt = result.get("LeadManagement", result)
            else:
                lead_mgmt = result
            
            if isinstance(lead_mgmt, dict):
                prospects_container = lead_mgmt.get("Prospects", lead_mgmt)
                if isinstance(prospects_container, dict):
                    prospects = prospects_container.get("Prospect", [])
                else:
                    prospects = prospects_container
                
                if isinstance(prospects, dict):
                    prospects = [prospects]
                
                for p in prospects if isinstance(prospects, list) else []:
                    events_container = p.get("Events", {})
                    if isinstance(events_container, dict):
                        event_list = events_container.get("Event", [])
                    else:
                        event_list = events_container
                    
                    if isinstance(event_list, dict):
                        event_list = [event_list]
                    
                    for i, e in enumerate(event_list if isinstance(event_list, list) else []):
                        event_type = e.get("@attributes", {}).get("EventType", e.get("EventType", ""))
                        events.append({
                            "event_type": event_type,
                            "event_date": e.get("@attributes", {}).get("EventDate", e.get("EventDate", "")),
                            "first_contact": i == 0  # First event is first contact
                        })
        return events
    
    def _extract_prospects(self, data: dict) -> List[dict]:
        """Extract prospect list from Yardi ILS response."""
        prospects = []
        if isinstance(data, dict):
            result = data.get("GetYardiGuestActivity_LoginResult", data)
            if isinstance(result, dict):
                lead_mgmt = result.get("LeadManagement", result)
            else:
                lead_mgmt = result
            
            if isinstance(lead_mgmt, dict):
                prospects_container = lead_mgmt.get("Prospects", lead_mgmt)
                if isinstance(prospects_container, dict):
                    prospect_list = prospects_container.get("Prospect", [])
                else:
                    prospect_list = prospects_container
                
                if isinstance(prospect_list, dict):
                    prospect_list = [prospect_list]
                
                for p in prospect_list if isinstance(prospect_list, list) else []:
                    customers = p.get("Customers", {})
                    customer = customers.get("Customer", {}) if isinstance(customers, dict) else {}
                    name = customer.get("Name", {}) if isinstance(customer, dict) else {}
                    prefs = p.get("CustomerPreferences", {})
                    
                    events = p.get("Events", {})
                    event_list = events.get("Event", []) if isinstance(events, dict) else []
                    if isinstance(event_list, dict):
                        event_list = [event_list]
                    
                    last_event = event_list[-1] if event_list else {}
                    event_type = last_event.get("@attributes", {}).get("EventType", last_event.get("EventType", "")) if isinstance(last_event, dict) else ""
                    event_date = last_event.get("@attributes", {}).get("EventDate", last_event.get("EventDate", "")) if isinstance(last_event, dict) else ""
                    
                    prospects.append({
                        "first_name": name.get("FirstName", "") if isinstance(name, dict) else "",
                        "last_name": name.get("LastName", "") if isinstance(name, dict) else "",
                        "email": customer.get("Email", "") if isinstance(customer, dict) else "",
                        "phone": "",
                        "desired_floorplan": prefs.get("DesiredFloorplan", "") if isinstance(prefs, dict) else "",
                        "target_move_in": prefs.get("TargetMoveInDate", "") if isinstance(prefs, dict) else "",
                        "last_event": event_type,
                        "event_date": event_date,
                        "event_count": len(event_list)
                    })
        return prospects
    
    # ---- Helper methods ----
    
    def _move_out_within_days(self, resident: dict, days: int, ref_date: date) -> bool:
        """Check if move-out is within N days."""
        move_out = resident.get("move_out_date") or resident.get("lease_end")
        move_out_date = parse_yardi_date(move_out)
        return is_within_days(move_out_date, ref_date, days)
    
    def _move_in_within_days(self, resident: dict, days: int, ref_date: date) -> bool:
        """Check if move-in is within N days."""
        move_in = resident.get("move_in_date")
        move_in_date = parse_yardi_date(move_in)
        return is_within_days(move_in_date, ref_date, days)
    
    def _is_in_period(self, resident: dict, date_field: str, start: date, end: date) -> bool:
        """Check if resident's date falls in period."""
        date_str = resident.get(date_field, "")
        d = parse_yardi_date(date_str)
        return is_in_period(d, start, end)
    
    def _resident_in_period(self, resident: dict, start: date, end: date) -> bool:
        """Check if any resident date falls in period."""
        for field in ["move_in_date", "move_out_date", "notice_date"]:
            if self._is_in_period(resident, field, start, end):
                return True
        return True  # Include if no date filter matches
    
    def _safe_int(self, value) -> int:
        """Safely convert value to int."""
        try:
            return int(float(value)) if value else 0
        except (ValueError, TypeError):
            return 0
    
    def _safe_float(self, value) -> float:
        """Safely convert value to float."""
        try:
            return float(value) if value else 0.0
        except (ValueError, TypeError):
            return 0.0
    
    # ---- Amenities methods ----
    
    async def get_amenities(self, property_id: str, item_type: Optional[str] = None) -> List[dict]:
        """
        Get rentable items (amenities) for a property.
        Currently only supports RealPage properties - reads from local DB.
        """
        pms_type = self._get_pms_type(property_id)
        
        if pms_type == "realpage":
            # Get site_id from property config
            pms_config = get_pms_config(property_id)
            site_id = pms_config.realpage_siteid
            
            if not site_id:
                return []
            
            # Read from local RealPage database
            import sqlite3
            import os
            db_path = os.path.join(os.path.dirname(__file__), "../db/data/realpage_raw.db")
            
            if not os.path.exists(db_path):
                return []
            
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Filter by site_id
            query = "SELECT * FROM realpage_rentable_items WHERE site_id = ?"
            params = [site_id]
            if item_type:
                query += " AND LOWER(item_type) LIKE ?"
                params.append(f"%{item_type.lower()}%")
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        else:
            # Yardi doesn't have this API
            return []
    
    async def get_amenities_summary(self, property_id: str) -> dict:
        """
        Get summary of amenities by type with revenue potential.
        """
        items = await self.get_amenities(property_id)
        
        if not items:
            return {
                "total_items": 0,
                "total_available": 0,
                "total_rented": 0,
                "monthly_potential": 0,
                "monthly_actual": 0,
                "by_type": []
            }
        
        # Group by item type
        by_type = {}
        for item in items:
            item_type = item.get("item_type") or "Other"
            if item_type not in by_type:
                by_type[item_type] = {
                    "type": item_type,
                    "total": 0,
                    "available": 0,
                    "rented": 0,
                    "monthly_rate": item.get("billing_amount", 0),
                    "potential_revenue": 0,
                    "actual_revenue": 0
                }
            
            by_type[item_type]["total"] += 1
            # Determine rented status by lease_id (not status text which is misleading)
            lease_id = item.get("lease_id")
            is_rented = lease_id and str(lease_id) not in ('', '0', 'None')
            
            if is_rented:
                by_type[item_type]["rented"] += 1
                by_type[item_type]["actual_revenue"] += item.get("billing_amount", 0)
            else:
                by_type[item_type]["available"] += 1
            
            by_type[item_type]["potential_revenue"] += item.get("billing_amount", 0)
        
        # Calculate totals
        total_items = len(items)
        total_available = sum(t["available"] for t in by_type.values())
        total_rented = sum(t["rented"] for t in by_type.values())
        monthly_potential = sum(t["potential_revenue"] for t in by_type.values())
        monthly_actual = sum(t["actual_revenue"] for t in by_type.values())
        
        return {
            "total_items": total_items,
            "total_available": total_available,
            "total_rented": total_rented,
            "monthly_potential": monthly_potential,
            "monthly_actual": monthly_actual,
            "occupancy_rate": round((total_rented / total_items * 100) if total_items > 0 else 0, 1),
            "by_type": list(by_type.values())
        }

    async def get_lease_expirations(self, property_id: str) -> dict:
        """
        Get lease expiration and renewal metrics for 30/60/90 day periods.
        
        Primary source: realpage_lease_expiration_renewal (Report 4156) — has
        Decision column: Renewed, Vacating, Unknown, Moved out, MTM.
        Fallback: realpage_leases (Current / Current-Future status).
        
        READ-ONLY operation.
        """
        import sqlite3
        from app.db.schema import REALPAGE_DB_PATH
        from app.property_config.properties import get_pms_config
        
        pms_config = get_pms_config(property_id)
        if not pms_config.realpage_siteid:
            return {"periods": []}
        
        site_id = pms_config.realpage_siteid
        
        try:
            conn = sqlite3.connect(REALPAGE_DB_PATH)
            cursor = conn.cursor()
            
            # Try report 4156 data first (has richer decision statuses)
            use_4156 = False
            try:
                cursor.execute("""
                    SELECT COUNT(*) FROM realpage_lease_expiration_renewal
                    WHERE property_id = ?
                """, (site_id,))
                if (cursor.fetchone()[0] or 0) > 0:
                    use_4156 = True
            except Exception:
                pass
            
            periods = []
            
            # Build list of next 4 calendar months for monthly view
            from calendar import monthrange as _monthrange
            today = date.today()
            month_ranges = []
            for offset in range(4):
                m = today.month + offset
                y = today.year
                while m > 12:
                    m -= 12
                    y += 1
                _, last_day = _monthrange(y, m)
                m_start = date(y, m, 1)
                m_end = date(y, m, last_day)
                # For current month, start from today
                if offset == 0:
                    m_start = today
                month_label = m_start.strftime('%b')  # e.g. "Feb", "Mar"
                month_ranges.append((month_label, m_start.isoformat(), m_end.isoformat()))
            
            if use_4156:
                # Report 4156: lease_end_date is in MM/DD/YYYY format
                date_expr = "date(substr(lease_end_date,7,4)||'-'||substr(lease_end_date,1,2)||'-'||substr(lease_end_date,4,2))"
                
                # --- Rolling day periods (30d/60d/90d) ---
                for days, label in [(30, "30d"), (60, "60d"), (90, "90d")]:
                    cursor.execute(f"""
                        SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN decision = 'Renewed' THEN 1 ELSE 0 END) as renewed,
                            SUM(CASE WHEN decision = 'Vacating' THEN 1 ELSE 0 END) as vacating,
                            SUM(CASE WHEN decision = 'Unknown' THEN 1 ELSE 0 END) as unknown,
                            SUM(CASE WHEN decision = 'MTM' THEN 1 ELSE 0 END) as mtm,
                            SUM(CASE WHEN decision = 'Moved out' THEN 1 ELSE 0 END) as moved_out
                        FROM realpage_lease_expiration_renewal
                        WHERE property_id = ?
                          AND lease_end_date IS NOT NULL AND lease_end_date != ''
                          AND {date_expr} BETWEEN date('now') AND date('now', '+{days} days')
                    """, (site_id,))
                    
                    row = cursor.fetchone()
                    total = row[0] or 0
                    renewed = row[1] or 0
                    vacating = row[2] or 0
                    unknown = row[3] or 0
                    mtm = row[4] or 0
                    moved_out = row[5] or 0
                    renewal_pct = round((renewed / total * 100), 1) if total > 0 else 0
                    
                    periods.append({
                        "label": label,
                        "expirations": total,
                        "renewals": renewed,
                        "signed": renewed,
                        "vacating": vacating,
                        "unknown": unknown,
                        "mtm": mtm,
                        "moved_out": moved_out,
                        "submitted": 0,
                        "selected": 0,
                        "renewal_pct": renewal_pct
                    })
                
                # --- Monthly periods ---
                for m_label, m_start, m_end in month_ranges:
                    cursor.execute(f"""
                        SELECT 
                            COUNT(*) as total,
                            SUM(CASE WHEN decision = 'Renewed' THEN 1 ELSE 0 END) as renewed,
                            SUM(CASE WHEN decision = 'Vacating' THEN 1 ELSE 0 END) as vacating,
                            SUM(CASE WHEN decision = 'Unknown' THEN 1 ELSE 0 END) as unknown,
                            SUM(CASE WHEN decision = 'MTM' THEN 1 ELSE 0 END) as mtm,
                            SUM(CASE WHEN decision = 'Moved out' THEN 1 ELSE 0 END) as moved_out
                        FROM realpage_lease_expiration_renewal
                        WHERE property_id = ?
                          AND lease_end_date IS NOT NULL AND lease_end_date != ''
                          AND {date_expr} BETWEEN ? AND ?
                    """, (site_id, m_start, m_end))
                    
                    row = cursor.fetchone()
                    total = row[0] or 0
                    renewed = row[1] or 0
                    vacating = row[2] or 0
                    unknown = row[3] or 0
                    mtm = row[4] or 0
                    moved_out = row[5] or 0
                    renewal_pct = round((renewed / total * 100), 1) if total > 0 else 0
                    
                    periods.append({
                        "label": m_label,
                        "expirations": total,
                        "renewals": renewed,
                        "signed": renewed,
                        "vacating": vacating,
                        "unknown": unknown,
                        "mtm": mtm,
                        "moved_out": moved_out,
                        "submitted": 0,
                        "selected": 0,
                        "renewal_pct": renewal_pct
                    })
            else:
                # Fallback: realpage_leases (no decision breakdown)
                for days, label in [(30, "30d"), (60, "60d"), (90, "90d")]:
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as expirations,
                            SUM(CASE WHEN status_text = 'Current - Future' THEN 1 ELSE 0 END) as signed_renewals
                        FROM realpage_leases 
                        WHERE site_id = ?
                            AND status_text IN ('Current', 'Current - Future')
                            AND lease_end_date != ''
                            AND date(substr(lease_end_date,7,4) || '-' || substr(lease_end_date,1,2) || '-' || substr(lease_end_date,4,2)) 
                                BETWEEN date('now') AND date('now', ? || ' days')
                    """, (site_id, f"+{days}"))
                    
                    row = cursor.fetchone()
                    expirations = row[0] or 0
                    signed = row[1] or 0
                    renewal_pct = round((signed / expirations * 100), 1) if expirations > 0 else 0
                    
                    periods.append({
                        "label": label,
                        "expirations": expirations,
                        "renewals": signed,
                        "signed": signed,
                        "vacating": 0,
                        "unknown": 0,
                        "mtm": 0,
                        "moved_out": 0,
                        "submitted": 0,
                        "selected": 0,
                        "renewal_pct": renewal_pct
                    })
                
                # --- Monthly periods (fallback) ---
                for m_label, m_start, m_end in month_ranges:
                    cursor.execute("""
                        SELECT 
                            COUNT(*) as expirations,
                            SUM(CASE WHEN status_text = 'Current - Future' THEN 1 ELSE 0 END) as signed_renewals
                        FROM realpage_leases 
                        WHERE site_id = ?
                            AND status_text IN ('Current', 'Current - Future')
                            AND lease_end_date != ''
                            AND date(substr(lease_end_date,7,4) || '-' || substr(lease_end_date,1,2) || '-' || substr(lease_end_date,4,2)) 
                                BETWEEN ? AND ?
                    """, (site_id, m_start, m_end))
                    
                    row = cursor.fetchone()
                    expirations = row[0] or 0
                    signed = row[1] or 0
                    renewal_pct = round((signed / expirations * 100), 1) if expirations > 0 else 0
                    
                    periods.append({
                        "label": m_label,
                        "expirations": expirations,
                        "renewals": signed,
                        "signed": signed,
                        "vacating": 0,
                        "unknown": 0,
                        "mtm": 0,
                        "moved_out": 0,
                        "submitted": 0,
                        "selected": 0,
                        "renewal_pct": renewal_pct
                    })
            
            conn.close()
            logger.info(f"[OCCUPANCY] Lease expirations for site {site_id} (source={'4156' if use_4156 else 'leases'}): {periods}")
            return {"periods": periods}
            
        except Exception as e:
            logger.warning(f"[OCCUPANCY] Failed to get lease expirations: {e}")
            return {"periods": []}
