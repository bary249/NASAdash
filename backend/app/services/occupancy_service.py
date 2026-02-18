"""
Occupancy & Leasing Service - Owner Dashboard V2
Implements Module 1 (Occupancy & Exposure) and Module 2 (Marketing Funnel) from spec.
READ-ONLY: Only retrieves and transforms data, no modifications.
"""
import logging
import sqlite3
from typing import List, Optional, Dict, Any
from datetime import date, timedelta
from app.models import (
    Timeframe, OccupancyMetrics, ExposureMetrics, LeasingFunnelMetrics,
    UnitRaw, ResidentRaw, ProspectRaw, PropertyInfo
)
from app.db.schema import UNIFIED_DB_PATH
from app.services.timeframe import (
    get_date_range, format_date_iso, format_date_yardi,
    parse_yardi_date, days_between, is_within_days, is_in_period
)

logger = logging.getLogger(__name__)


class OccupancyService:
    """Service for occupancy and leasing metrics. Reads from unified.db ONLY."""
    
    def __init__(self):
        pass
    
    # ---- Unified DB helpers ----
    
    def _get_db_units(self, property_id: str) -> List[dict]:
        """Read units from unified.db."""
        try:
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM unified_units WHERE unified_property_id = ?", (property_id,))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            # Normalize field names for backward compat
            for u in rows:
                u["unit_id"] = u.get("unit_number") or u.get("pms_unit_id", "")
                u["occupancy_status"] = u.get("status", "vacant")
                u["ready_status"] = "ready" if u.get("made_ready_date") else "not_ready"
                u["available"] = u.get("status") == "vacant" and bool(u.get("made_ready_date"))
                u["days_vacant"] = u.get("days_vacant") or 0
            return rows
        except Exception as e:
            logger.warning(f"[OCCUPANCY] Failed to read units from DB for {property_id}: {e}")
            return []
    
    def _get_db_residents(self, property_id: str, status: Optional[str] = None) -> List[dict]:
        """Read residents from unified.db."""
        try:
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            if status and status.lower() != "all":
                cursor.execute(
                    "SELECT * FROM unified_residents WHERE unified_property_id = ? AND LOWER(status) = LOWER(?)",
                    (property_id, status)
                )
            else:
                cursor.execute("SELECT * FROM unified_residents WHERE unified_property_id = ?", (property_id,))
            rows = [dict(r) for r in cursor.fetchall()]
            conn.close()
            # Normalize field names for backward compat
            for r in rows:
                r["unit"] = r.get("unit_number", "")
                r["resident_id"] = r.get("pms_resident_id", "")
                r["rent"] = r.get("current_rent", 0)
                r["status"] = (r.get("status") or "Current").capitalize()
            return rows
        except Exception as e:
            logger.warning(f"[OCCUPANCY] Failed to read residents from DB for {property_id}: {e}")
            return []
    
    def _get_property_name(self, property_id: str) -> str:
        """Get property name from unified.db."""
        try:
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM unified_properties WHERE unified_property_id = ?", (property_id,))
            row = cursor.fetchone()
            conn.close()
            return row[0] if row else property_id
        except Exception:
            return property_id
    
    async def get_property_list(self) -> List[PropertyInfo]:
        """Get list of all properties from unified.db."""
        properties = []
        
        try:
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT unified_property_id, name, city, state, address
                FROM unified_properties
            """)
            prop_rows = cursor.fetchall()
            
            # Derive floor count per property from unit numbers
            floor_counts: dict = {}
            has_5digit: set = set()
            cursor.execute("SELECT unified_property_id, unit_number FROM unified_units")
            for urow in cursor.fetchall():
                pid, unum = urow[0], urow[1]
                try:
                    num = int(unum)
                    if num >= 10000:
                        has_5digit.add(pid)
                        continue
                    floor = num // 100 if num >= 100 else 1
                    if pid not in floor_counts:
                        floor_counts[pid] = set()
                    floor_counts[pid].add(floor)
                except (ValueError, TypeError):
                    pass
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
        
        return properties
    
    def get_occupancy_metrics(
        self, 
        property_id: str, 
        timeframe: Timeframe = Timeframe.CM
    ) -> OccupancyMetrics:
        """
        Get occupancy metrics from unified.db.
        Primary source: unified_occupancy_metrics table.
        Fallback: compute from unified_units + unified_residents.
        """
        return self._get_occupancy_from_unified(property_id, timeframe)
    
    def _get_occupancy_from_unified(
        self,
        property_id: str,
        timeframe: Timeframe = Timeframe.CM
    ) -> OccupancyMetrics:
        """Read occupancy from unified.db."""
        
        period_start, period_end = get_date_range(timeframe)
        
        try:
            conn = sqlite3.connect(UNIFIED_DB_PATH)
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
    
    def get_exposure_metrics(
        self, 
        property_id: str, 
        timeframe: Timeframe = Timeframe.CM
    ) -> ExposureMetrics:
        """
        Calculate exposure metrics from unified.db.
        
        Exposure = (Vacant + Pending Move-outs) - Pending Move-ins
        """
        period_start, period_end = get_date_range(timeframe)
        today = date.today()
        
        # Read all data from unified DB
        units = self._get_db_units(property_id)
        all_residents = self._get_db_residents(property_id)
        
        notice_residents = [r for r in all_residents if r.get("status", "").lower() == "notice"]
        past_residents = [r for r in all_residents if r.get("status", "").lower() == "past"]
        current_residents = [r for r in all_residents if r.get("status", "").lower() == "current"]
        future_residents = [r for r in all_residents if r.get("status", "").lower() == "future"]
        
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
    
    def get_leasing_funnel(
        self, 
        property_id: str, 
        timeframe: Timeframe = Timeframe.CM
    ) -> LeasingFunnelMetrics:
        """
        Get leasing funnel metrics from unified.db.
        Uses imported Excel report data (imported_leasing_activity table).
        Returns empty metrics if no imported data is available.
        """
        period_start, period_end = get_date_range(timeframe)
        
        # First try: granular activity data (date-filtered, supports all timeframes)
        activity_funnel = self._build_funnel_from_activity(property_id, timeframe, period_start, period_end)
        if activity_funnel and activity_funnel.leads > 0:
            return activity_funnel
        
        # Fallback: imported leasing summary (monthly aggregate, not date-filtered)
        imported_data = self._get_imported_leasing_data(property_id, period_start, period_end)
        if imported_data:
            return self._build_funnel_from_imported(property_id, timeframe, period_start, period_end, imported_data)
        
        # No data available — return empty metrics
        return LeasingFunnelMetrics(
            property_id=property_id,
            timeframe=timeframe.value,
            period_start=format_date_iso(period_start),
            period_end=format_date_iso(period_end),
            leads=0, tours=0, applications=0, lease_signs=0, denials=0,
            lead_to_tour_rate=0, tour_to_app_rate=0,
            app_to_lease_rate=0, lead_to_lease_rate=0
        )
    
    def _build_funnel_from_activity(
        self,
        property_id: str,
        timeframe: Timeframe,
        period_start: date,
        period_end: date,
    ) -> Optional[LeasingFunnelMetrics]:
        """Build funnel from granular unified_activity records (date-filtered)."""
        try:
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            cursor = conn.cursor()

            # Build set of possible IDs for this property (API key, unified_id, kairoi- variants)
            id_variants = {property_id}
            if property_id.startswith("kairoi-"):
                id_variants.add(property_id.replace("kairoi-", "").replace("-", "_"))
            # Look up unified_id from PROPERTY_MAPPING (numeric RealPage ID → unified_id)
            try:
                from app.db.sync_realpage_to_unified import PROPERTY_MAPPING
                # Forward: if property_id is a numeric RealPage ID
                if property_id in PROPERTY_MAPPING:
                    id_variants.add(PROPERTY_MAPPING[property_id]["unified_id"])
                # Reverse: find unified_id that matches this property key
                def _strip(s: str) -> str:
                    return s.replace("the_", "").replace("the", "").replace("kairoi-", "").replace("-", "_")
                pid_clean = _strip(property_id)
                for _num_id, mapping in PROPERTY_MAPPING.items():
                    uid = mapping["unified_id"]
                    uid_clean = _strip(uid)
                    # Match: exact, suffix, or stripped versions match
                    if (uid == property_id or property_id.endswith(uid) or
                        uid_clean == pid_clean or uid_clean.startswith(pid_clean) or pid_clean.startswith(uid_clean)):
                        id_variants.add(uid)
            except Exception:
                pass
            id_list = list(id_variants)
            id_placeholders = ",".join("?" for _ in id_list)

            start_str = period_start.strftime("%Y-%m-%d")
            end_str = period_end.strftime("%Y-%m-%d")

            # Tour events
            tour_types = ("Visit", "Visit (return)", "Videotelephony - Tour", "Self-guided - Tour", "Pre-recorded - Tour")
            # Application events
            app_types = (
                "Online Leasing pre-qualify", "Online Leasing Agreement",
                "Identity Verification", "Online Leasing reservation",
                "Online Leasing Payment", "Quote",
            )
            # Lease signed
            lease_types = ("Leased",)

            def count_unique(types: tuple) -> int:
                type_ph = ",".join("?" for _ in types)
                cursor.execute(f"""
                    SELECT COUNT(DISTINCT resident_name) FROM unified_activity
                    WHERE unified_property_id IN ({id_placeholders})
                      AND activity_date >= ? AND activity_date <= ?
                      AND activity_type IN ({type_ph})
                """, (*id_list, start_str, end_str, *types))
                return cursor.fetchone()[0] or 0

            # Leads = truly new prospects whose first-ever activity is within this period
            cursor.execute(f"""
                SELECT COUNT(*) FROM (
                    SELECT resident_name, MIN(activity_date) as first_date
                    FROM unified_activity
                    WHERE unified_property_id IN ({id_placeholders})
                      AND resident_name IS NOT NULL AND resident_name != ''
                    GROUP BY resident_name
                    HAVING first_date >= ? AND first_date <= ?
                )
            """, (*id_list, start_str, end_str))
            leads = cursor.fetchone()[0] or 0

            tours = count_unique(tour_types)
            applications = count_unique(app_types)
            lease_signs = count_unique(lease_types)

            if leads == 0 and tours == 0:
                conn.close()
                return None

            # tour_to_app count: applicants (in period) who also toured (all-time)
            tour_type_ph = ",".join("?" for _ in tour_types)
            app_type_ph = ",".join("?" for _ in app_types)
            cursor.execute(f"""
                SELECT COUNT(DISTINCT a.resident_name) FROM unified_activity a
                WHERE a.unified_property_id IN ({id_placeholders})
                  AND a.activity_type IN ({app_type_ph})
                  AND a.activity_date >= ? AND a.activity_date <= ?
                  AND a.resident_name IS NOT NULL AND a.resident_name != ''
                  AND a.resident_name IN (
                      SELECT DISTINCT t.resident_name FROM unified_activity t
                      WHERE t.unified_property_id IN ({id_placeholders})
                        AND t.activity_type IN ({tour_type_ph})
                        AND t.resident_name IS NOT NULL AND t.resident_name != ''
                  )
            """, (*id_list, *app_types, start_str, end_str, *id_list, *tour_types))
            tour_to_app_count = cursor.fetchone()[0] or 0

            # sight_unseen count: applicants (in period) who never toured (all-time)
            sight_unseen_count = applications - tour_to_app_count

            conn.close()

            lead_to_tour = round(tours / leads * 100, 1) if leads > 0 else 0
            tour_to_app_rate = round(applications / tours * 100, 1) if tours > 0 else 0
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
                denials=0,
                sight_unseen=max(0, sight_unseen_count),
                tour_to_app=tour_to_app_count,
                lead_to_tour_rate=lead_to_tour,
                tour_to_app_rate=tour_to_app_rate,
                app_to_lease_rate=app_to_lease,
                lead_to_lease_rate=lead_to_lease,
            )
        except Exception as e:
            logger.warning(f"Error building funnel from activity: {e}")
            return None

    def _get_imported_leasing_data(self, property_id: str, period_start: date, period_end: date) -> Optional[Dict[str, Any]]:
        """Get imported leasing activity data from database."""
        
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
    
    def get_raw_units(self, property_id: str) -> List[dict]:
        """Get raw unit data for drill-through from unified.db."""
        return self._get_db_units(property_id)
    
    def get_raw_residents(
        self, 
        property_id: str, 
        status: str = "all",
        timeframe: Timeframe = Timeframe.CM,
        metric_filter: Optional[str] = None
    ) -> List[dict]:
        """
        Get raw resident data for drill-through from unified.db.
        
        metric_filter options:
        - "move_ins": Only residents who moved in during the period
        - "move_outs": Only residents who moved out during the period
        - "notices_30": Notices with move-out in next 30 days
        - "notices_60": Notices with move-out in next 60 days
        - None: All residents matching status
        """
        period_start, period_end = get_date_range(timeframe)
        today = date.today()
        
        # Determine which statuses to query based on metric_filter
        if metric_filter == "move_ins":
            db_status = "all"  # Need current + future
        elif metric_filter == "move_outs":
            db_status = "past"
        elif metric_filter in ["notices_30", "notices_60"]:
            db_status = "notice"
        else:
            db_status = status
        
        raw_residents = self._get_db_residents(property_id, db_status if db_status != "all" else None)
        
        if not metric_filter:
            return raw_residents
        
        # Apply metric-specific filtering
        filtered = []
        for r in raw_residents:
            if metric_filter == "move_ins":
                move_in = parse_yardi_date(r.get("move_in_date", ""))
                if move_in and is_in_period(move_in, period_start, period_end):
                    filtered.append(r)
            elif metric_filter == "move_outs":
                move_out = parse_yardi_date(r.get("move_out_date", ""))
                if move_out and is_in_period(move_out, period_start, period_end):
                    filtered.append(r)
            elif metric_filter == "notices_30":
                move_out = parse_yardi_date(r.get("move_out_date", "") or r.get("lease_end", ""))
                if move_out and is_within_days(move_out, today, 30):
                    filtered.append(r)
            elif metric_filter == "notices_60":
                move_out = parse_yardi_date(r.get("move_out_date", "") or r.get("lease_end", ""))
                if move_out and is_within_days(move_out, today, 60):
                    filtered.append(r)
        return filtered
    
    def get_raw_prospects(
        self, 
        property_id: str,
        stage: Optional[str] = None,
        timeframe: Timeframe = Timeframe.CM
    ) -> List[dict]:
        """Get raw prospect data. Returns empty — prospect data not stored in unified.db."""
        return []
    
    def get_occupancy_trend(
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
        
        logger.info(f"[TREND] Property {property_id}")
        logger.info(f"[TREND] Period: {start_date} to {end_date} ({period_days} days)")
        logger.info(f"[TREND] Prior: {prior_start} to {prior_end}")
        
        # Get all data from unified DB
        residents = self._get_db_residents(property_id)
        units = self._get_db_units(property_id)
        
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
    
    def get_all_trends(
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
        
        # Get all data from unified DB
        residents = self._get_db_residents(property_id)
        units = self._get_db_units(property_id)
        
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
        current_funnel = self._get_funnel_counts(property_id, start_date, end_date)
        prior_funnel = self._get_funnel_counts(property_id, prior_start, prior_end)
        
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
    
    def _get_funnel_counts(
        self, 
        property_id: str, 
        period_start: date, 
        period_end: date
    ) -> Dict[str, Any]:
        """Get funnel metric counts for a specific period from imported data."""
        imported_data = self._get_imported_leasing_data(property_id, period_start, period_end)
        if imported_data:
            totals = imported_data.get('totals', {})
            consultants = imported_data.get('by_consultant', [])
            leads = sum(c.get('new_prospects', 0) for c in consultants) or totals.get('activities', 0)
            tours = sum(c.get('visits', 0) for c in consultants)
            applications = imported_data.get('applications', 0)
            lease_signs = sum(c.get('leases', 0) for c in consultants)
            lead_to_tour = round(tours / leads * 100, 1) if leads > 0 else 0
            tour_to_app = round(applications / tours * 100, 1) if tours > 0 else 0
            lead_to_lease = round(lease_signs / leads * 100, 1) if leads > 0 else 0
            return {
                "leads": leads, "tours": tours, "applications": applications,
                "lease_signs": lease_signs, "lead_to_tour_rate": lead_to_tour,
                "tour_to_app_rate": tour_to_app, "lead_to_lease_rate": lead_to_lease,
            }
        return {
            "leads": 0, "tours": 0, "applications": 0, "lease_signs": 0,
            "lead_to_tour_rate": 0, "tour_to_app_rate": 0, "lead_to_lease_rate": 0,
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
    
    def get_amenities(self, property_id: str, item_type: Optional[str] = None) -> List[dict]:
        """
        Get rentable items (amenities) for a property.
        Reads from unified_amenities in unified.db.
        """
        try:
            conn = sqlite3.connect(str(UNIFIED_DB_PATH))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM unified_amenities WHERE unified_property_id = ?"
            params: list = [property_id]
            if item_type:
                query += " AND LOWER(item_type) LIKE ?"
                params.append(f"%{item_type.lower()}%")
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
        except Exception:
            return []
    
    def get_amenities_summary(self, property_id: str) -> dict:
        """
        Get summary of amenities by type with revenue potential.
        """
        items = self.get_amenities(property_id)
        
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
                    "monthly_rate": item.get("monthly_charge") or item.get("billing_amount") or 0,
                    "potential_revenue": 0,
                    "actual_revenue": 0
                }
            
            by_type[item_type]["total"] += 1
            # Determine rented status: lease_id present, or status='Rented', or unit assigned
            lease_id = item.get("lease_id")
            unit_num = item.get("unit_number")
            status_val = item.get("status", '')
            is_rented = (
                (lease_id and str(lease_id) not in ('', '0', 'None'))
                or status_val == 'Rented'
                or (unit_num and str(unit_num) not in ('', '0', 'None'))
            )
            
            if is_rented:
                by_type[item_type]["rented"] += 1
                by_type[item_type]["actual_revenue"] += item.get("monthly_charge") or item.get("billing_amount") or 0
            else:
                by_type[item_type]["available"] += 1
            
            by_type[item_type]["potential_revenue"] += item.get("monthly_charge") or item.get("billing_amount") or 0
        
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

    def get_lease_expirations(self, property_id: str) -> dict:
        """
        Get lease expiration and renewal metrics for 30/60/90 day periods.
        
        Primary source: unified_lease_expirations (Report 4156) — has
        Decision column: Renewed, Vacating, Unknown, Moved out, MTM.
        Fallback: unified_leases (Current / Current-Future status).
        
        READ-ONLY operation.
        """
        import sqlite3
        from app.db.schema import UNIFIED_DB_PATH
        
        try:
            conn = sqlite3.connect(str(UNIFIED_DB_PATH))
            cursor = conn.cursor()
            
            # Try report 4156 data first (has richer decision statuses)
            use_4156 = False
            try:
                cursor.execute("""
                    SELECT COUNT(*) FROM unified_lease_expirations
                    WHERE unified_property_id = ?
                """, (property_id,))
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
                        FROM unified_lease_expirations
                        WHERE unified_property_id = ?
                          AND lease_end_date IS NOT NULL AND lease_end_date != ''
                          AND {date_expr} BETWEEN date('now') AND date('now', '+{days} days')
                    """, (property_id,))
                    
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
                        FROM unified_lease_expirations
                        WHERE unified_property_id = ?
                          AND lease_end_date IS NOT NULL AND lease_end_date != ''
                          AND {date_expr} BETWEEN ? AND ?
                    """, (property_id, m_start, m_end))
                    
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
                # Fallback: unified_leases (no decision breakdown)
                date_expr = "date(substr(lease_end,7,4)||'-'||substr(lease_end,1,2)||'-'||substr(lease_end,4,2))"
                for days, label in [(30, "30d"), (60, "60d"), (90, "90d")]:
                    cursor.execute(f"""
                        SELECT 
                            COUNT(*) as expirations,
                            SUM(CASE WHEN status = 'Current - Future' THEN 1 ELSE 0 END) as signed_renewals
                        FROM unified_leases 
                        WHERE unified_property_id = ?
                            AND status IN ('Current', 'Current - Future')
                            AND lease_end IS NOT NULL AND lease_end != ''
                            AND {date_expr} BETWEEN date('now') AND date('now', '+{days} days')
                    """, (property_id,))
                    
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
                    cursor.execute(f"""
                        SELECT 
                            COUNT(*) as expirations,
                            SUM(CASE WHEN status = 'Current - Future' THEN 1 ELSE 0 END) as signed_renewals
                        FROM unified_leases 
                        WHERE unified_property_id = ?
                            AND status IN ('Current', 'Current - Future')
                            AND lease_end IS NOT NULL AND lease_end != ''
                            AND {date_expr} BETWEEN ? AND ?
                    """, (property_id, m_start, m_end))
                    
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
            logger.info(f"[OCCUPANCY] Lease expirations for {property_id} (source={'4156' if use_4156 else 'leases'}): {periods}")
            return {"periods": periods}
            
        except Exception as e:
            logger.warning(f"[OCCUPANCY] Failed to get lease expirations: {e}")
            return {"periods": []}
