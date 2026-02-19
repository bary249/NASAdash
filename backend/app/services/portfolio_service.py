"""
Portfolio Service - Aggregates metrics across multiple properties.
Supports two aggregation modes: weighted average and row metrics.

READ-ONLY OPERATIONS ONLY.
"""
import sqlite3
from typing import List, Dict, Optional
from app.db.schema import UNIFIED_DB_PATH
from app.models.unified import (
    AggregationMode,
    PMSSource,
    PMSConfig,
    UnifiedUnit,
    UnifiedResident,
    UnifiedOccupancy,
    UnifiedPricing,
    PortfolioOccupancy,
    PortfolioPricing,
    PortfolioSummary,
)


class PortfolioService:
    """
    Aggregates metrics across multiple properties. Reads from unified.db ONLY.
    
    Supports two aggregation modes:
    - WEIGHTED_AVERAGE: Calculate metrics per property, then weighted average
    - ROW_METRICS: Combine all raw data, calculate metrics from combined dataset
    """
    
    def __init__(self):
        pass
    
    def _get_units_from_db(self, property_id: str) -> Optional[List[Dict]]:
        """Get units from unified.db for a property."""
        try:
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT unit_number, floorplan, square_feet, market_rent, status,
                       occupancy_status, available_date, on_notice_date, days_vacant,
                       made_ready_date, excluded_from_occupancy, floorplan_name,
                       bedrooms, bathrooms, building, floor
                FROM unified_units
                WHERE unified_property_id = ?
            """, (property_id,))
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                return [dict(row) for row in rows]
        except Exception:
            pass
        return None
    
    def _get_residents_from_db(self, property_id: str) -> Optional[List[Dict]]:
        """Get residents from unified.db for a property."""
        try:
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT pms_resident_id, unit_number, first_name, last_name, full_name,
                       status, lease_start, lease_end, move_in_date, move_out_date,
                       current_rent, balance
                FROM unified_residents
                WHERE unified_property_id = ?
            """, (property_id,))
            rows = cursor.fetchall()
            conn.close()
            
            if rows:
                return [dict(row) for row in rows]
        except Exception:
            pass
        return None
    
    def _get_occupancy_from_db(self, property_id: str) -> Optional[Dict]:
        """Get occupancy from unified.db for a property."""
        try:
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT total_units, occupied_units, vacant_units, leased_units,
                       preleased_vacant, physical_occupancy, leased_percentage,
                       exposure_30_days, exposure_60_days,
                       COALESCE(vacant_ready, 0), COALESCE(vacant_not_ready, 0),
                       COALESCE(notice_break_units, 0), COALESCE(notice_units, 0)
                FROM unified_occupancy_metrics
                WHERE unified_property_id = ?
                ORDER BY snapshot_date DESC
                LIMIT 1
            """, (property_id,))
            row = cursor.fetchone()
            conn.close()
            
            if row:
                vacant_units = row[2] or 0
                vacant_ready = row[9] or 0
                vacant_not_ready = row[10] or 0
                notice_break = row[11] or 0
                notice_units = row[12] or 0
                
                # Override vacant from unified_units for consistency with
                # ATR, bedroom table, and KPI card (all read from unified_units)
                try:
                    conn2 = sqlite3.connect(UNIFIED_DB_PATH)
                    c2 = conn2.cursor()
                    c2.execute("""
                        SELECT COUNT(*) FROM unified_units
                        WHERE unified_property_id = ?
                          AND occupancy_status IN ('vacant', 'vacant_ready', 'vacant_not_ready')
                    """, (property_id,))
                    uu_row = c2.fetchone()
                    conn2.close()
                    if uu_row and uu_row[0] > 0:
                        vacant_units = uu_row[0]
                except Exception:
                    pass
                
                # Fallback: if no vacant_ready data, use total vacant
                if vacant_ready == 0 and vacant_not_ready == 0 and vacant_units > 0:
                    vacant_ready = vacant_units
                return {
                    "total_units": row[0] or 0,
                    "occupied_units": row[1] or 0,
                    "vacant_units": vacant_units,
                    "leased_units": row[3] or 0,
                    "preleased_vacant": row[4] or 0,
                    "available_units": vacant_ready if vacant_ready > 0 else vacant_units,
                    "vacant_ready": vacant_ready,
                    "vacant_not_ready": vacant_not_ready,
                    "notice_units": notice_units,
                    "notice_break_units": notice_break,
                    "physical_occupancy": row[5] or 0,
                    "leased_percentage": row[6] or 0,
                    "exposure_30_days": row[7] or 0,
                    "exposure_60_days": row[8] or 0,
                }
        except Exception:
            pass
        return None
    
    def get_portfolio_occupancy(
        self,
        configs: List[PMSConfig],
        mode: AggregationMode = AggregationMode.WEIGHTED_AVERAGE
    ) -> PortfolioOccupancy:
        """
        Aggregate occupancy metrics across multiple properties.
        
        Args:
            configs: List of PMS configurations for each property
            mode: Aggregation mode (weighted_avg or row_metrics)
        
        Returns:
            PortfolioOccupancy with aggregated metrics
        """
        property_ids = [c.property_id for c in configs]
        
        if mode == AggregationMode.ROW_METRICS:
            return self._occupancy_row_metrics(configs)
        else:
            return self._occupancy_weighted_average(configs)
    
    def _occupancy_weighted_average(
        self, 
        configs: List[PMSConfig]
    ) -> PortfolioOccupancy:
        """Calculate occupancy using weighted average of per-property metrics."""
        property_metrics: List[UnifiedOccupancy] = []
        
        for config in configs:
            metrics = self._get_occupancy_from_db(config.property_id)
            if not metrics:
                continue
            
            property_metrics.append(UnifiedOccupancy(
                property_id=config.property_id,
                pms_source=PMSSource(config.pms_type),
                total_units=metrics["total_units"],
                occupied_units=metrics["occupied_units"],
                vacant_units=metrics["vacant_units"],
                leased_units=metrics["leased_units"],
                preleased_vacant=metrics.get("preleased_vacant", 0),
                available_units=metrics.get("available_units", 0),
                vacant_ready=metrics.get("vacant_ready", 0),
                vacant_not_ready=metrics.get("vacant_not_ready", 0),
                physical_occupancy=metrics["physical_occupancy"],
                leased_percentage=metrics["leased_percentage"],
            ))
        
        # Calculate weighted averages
        total_units = sum(m.total_units for m in property_metrics)
        total_occupied = sum(m.occupied_units for m in property_metrics)
        total_vacant = sum(m.vacant_units for m in property_metrics)
        total_leased = sum(m.leased_units for m in property_metrics)
        total_preleased = sum(m.preleased_vacant for m in property_metrics)
        total_available = sum(m.available_units for m in property_metrics)
        total_vacant_ready = sum(m.vacant_ready for m in property_metrics)
        total_vacant_not_ready = sum(m.vacant_not_ready for m in property_metrics)
        
        # Weighted average for percentages
        if total_units > 0:
            weighted_occupancy = sum(
                m.physical_occupancy * m.total_units for m in property_metrics
            ) / total_units
            weighted_leased = sum(
                m.leased_percentage * m.total_units for m in property_metrics
            ) / total_units
        else:
            weighted_occupancy = 0
            weighted_leased = 0
        
        return PortfolioOccupancy(
            property_ids=[c.property_id for c in configs],
            aggregation_mode=AggregationMode.WEIGHTED_AVERAGE,
            total_units=total_units,
            occupied_units=total_occupied,
            vacant_units=total_vacant,
            leased_units=total_leased,
            preleased_vacant=total_preleased,
            available_units=total_available,
            vacant_ready=total_vacant_ready,
            vacant_not_ready=total_vacant_not_ready,
            physical_occupancy=round(weighted_occupancy, 2),
            leased_percentage=round(weighted_leased, 2),
            property_breakdown=property_metrics,
        )
    
    def _occupancy_row_metrics(
        self, 
        configs: List[PMSConfig]
    ) -> PortfolioOccupancy:
        """Calculate occupancy from combined raw unit data."""
        all_units: List[dict] = []
        property_metrics: List[UnifiedOccupancy] = []
        
        for config in configs:
            db_metrics = self._get_occupancy_from_db(config.property_id)
            if not db_metrics:
                continue
            
            property_metrics.append(UnifiedOccupancy(
                property_id=config.property_id,
                pms_source=PMSSource(config.pms_type),
                total_units=db_metrics["total_units"],
                occupied_units=db_metrics["occupied_units"],
                vacant_units=db_metrics["vacant_units"],
                leased_units=db_metrics["leased_units"],
                preleased_vacant=db_metrics.get("preleased_vacant", 0),
                available_units=db_metrics.get("available_units", 0),
                vacant_ready=db_metrics.get("vacant_ready", 0),
                vacant_not_ready=db_metrics.get("vacant_not_ready", 0),
                physical_occupancy=db_metrics["physical_occupancy"],
                leased_percentage=db_metrics["leased_percentage"],
            ))
            for _ in range(db_metrics["occupied_units"]):
                all_units.append({"status": "occupied", "_property_id": config.property_id})
            for _ in range(db_metrics["vacant_units"]):
                all_units.append({"status": "vacant", "_property_id": config.property_id})
        
        # Calculate from combined raw data
        total_units = len(all_units)
        occupied_units = len([u for u in all_units if u.get("status") == "occupied"])
        vacant_units = len([u for u in all_units if u.get("status") == "vacant"])
        notice_units = len([u for u in all_units if u.get("status") == "notice"])
        available_units = len([u for u in all_units if u.get("available", False)])
        leased_units = occupied_units + notice_units
        
        # Vacant ready/not ready breakdown
        vacant_ready = len([u for u in all_units 
                          if u.get("status") == "vacant" 
                          and u.get("ready_status") == "ready"])
        vacant_not_ready = vacant_units - vacant_ready
        
        physical_occupancy = (occupied_units / total_units * 100) if total_units > 0 else 0
        leased_percentage = (leased_units / total_units * 100) if total_units > 0 else 0
        
        return PortfolioOccupancy(
            property_ids=[c.property_id for c in configs],
            aggregation_mode=AggregationMode.ROW_METRICS,
            total_units=total_units,
            occupied_units=occupied_units,
            vacant_units=vacant_units,
            leased_units=leased_units,
            preleased_vacant=0,
            available_units=available_units,
            vacant_ready=vacant_ready,
            vacant_not_ready=vacant_not_ready,
            physical_occupancy=round(physical_occupancy, 2),
            leased_percentage=round(leased_percentage, 2),
            property_breakdown=property_metrics,
        )
    
    def get_portfolio_pricing(
        self,
        configs: List[PMSConfig],
        mode: AggregationMode = AggregationMode.WEIGHTED_AVERAGE
    ) -> PortfolioPricing:
        """
        Aggregate pricing metrics across multiple properties.
        
        Args:
            configs: List of PMS configurations for each property
            mode: Aggregation mode (weighted_avg or row_metrics)
        
        Returns:
            PortfolioPricing with aggregated metrics
        """
        if mode == AggregationMode.ROW_METRICS:
            return self._pricing_row_metrics(configs)
        else:
            return self._pricing_weighted_average(configs)
    
    def _get_pricing_from_db(self, property_id: str) -> Optional[Dict]:
        """Get pricing from unified.db for a property."""
        try:
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                SELECT floorplan, unit_count, avg_square_feet,
                       in_place_rent, asking_rent
                FROM unified_pricing_metrics
                WHERE unified_property_id = ?
                AND snapshot_date = (
                    SELECT MAX(snapshot_date) FROM unified_pricing_metrics
                    WHERE unified_property_id = ?
                )
            """, (property_id, property_id))
            rows = cursor.fetchall()
            conn.close()
            
            if not rows:
                return None
            
            total_units = sum(r[1] or 0 for r in rows)
            total_sf = sum((r[1] or 0) * (r[2] or 0) for r in rows)
            total_ip = sum((r[1] or 0) * (r[3] or 0) for r in rows)
            total_ask = sum((r[1] or 0) * (r[4] or 0) for r in rows)
            
            if total_units > 0:
                avg_sf = total_sf / total_units
                avg_ip = total_ip / total_units
                avg_ask = total_ask / total_units
            else:
                avg_sf = avg_ip = avg_ask = 0
            
            return {
                "in_place_rent": avg_ip,
                "asking_rent": avg_ask,
                "in_place_per_sf": avg_ip / avg_sf if avg_sf > 0 else 0,
                "asking_per_sf": avg_ask / avg_sf if avg_sf > 0 else 0,
                "rent_growth": ((avg_ask / avg_ip) - 1) * 100 if avg_ip > 0 else 0,
                "total_units": total_units,
            }
        except Exception:
            return None
    
    def _pricing_weighted_average(
        self, 
        configs: List[PMSConfig]
    ) -> PortfolioPricing:
        """Calculate pricing using weighted average from unified.db."""
        property_ids = [c.property_id for c in configs]
        total_units = 0
        weighted_ip = 0
        weighted_ask = 0
        weighted_ip_sf = 0
        weighted_ask_sf = 0
        
        for config in configs:
            pricing = self._get_pricing_from_db(config.property_id)
            if not pricing or pricing["total_units"] == 0:
                continue
            n = pricing["total_units"]
            total_units += n
            weighted_ip += pricing["in_place_rent"] * n
            weighted_ask += pricing["asking_rent"] * n
            weighted_ip_sf += pricing["in_place_per_sf"] * n
            weighted_ask_sf += pricing["asking_per_sf"] * n
        
        if total_units > 0:
            avg_ip = weighted_ip / total_units
            avg_ask = weighted_ask / total_units
            avg_ip_sf = weighted_ip_sf / total_units
            avg_ask_sf = weighted_ask_sf / total_units
            growth = ((avg_ask / avg_ip) - 1) * 100 if avg_ip > 0 else 0
        else:
            avg_ip = avg_ask = avg_ip_sf = avg_ask_sf = growth = 0
        
        return PortfolioPricing(
            property_ids=property_ids,
            aggregation_mode=AggregationMode.WEIGHTED_AVERAGE,
            total_in_place_rent=round(avg_ip, 2),
            total_in_place_per_sf=round(avg_ip_sf, 2),
            total_asking_rent=round(avg_ask, 2),
            total_asking_per_sf=round(avg_ask_sf, 2),
            total_rent_growth=round(growth, 2),
        )
    
    def _pricing_row_metrics(
        self, 
        configs: List[PMSConfig]
    ) -> PortfolioPricing:
        """Calculate pricing from combined unified.db data (same as weighted avg for DB source)."""
        return self._pricing_weighted_average(configs)
    
    def get_all_units(
        self,
        configs: List[PMSConfig]
    ) -> List[UnifiedUnit]:
        """
        Get combined unit list from all properties (for drill-through).
        """
        all_units: List[UnifiedUnit] = []
        
        for config in configs:
            units = self._get_units_from_db(config.property_id)
            if not units:
                continue
            
            for unit in units:
                # Determine ready_status and available from unit data
                status = unit.get("status", "unknown")
                occ_status = unit.get("occupancy_status")
                is_vacant = occ_status == "vacant" or status == "vacant" or occ_status in ("vacant_ready", "vacant_not_ready")
                ready_status = unit.get("ready_status")
                if not ready_status:
                    # Use occupancy_status from enriched unified_units data
                    if occ_status == "vacant_ready":
                        ready_status = "ready"
                    elif occ_status == "vacant_not_ready":
                        ready_status = "not_ready"
                    elif is_vacant:
                        ready_status = "not_ready"
                is_available = unit.get("available", is_vacant and ready_status == "ready")
                
                all_units.append(UnifiedUnit(
                    unit_id=unit.get("unit_id") or unit.get("unit_number") or "",
                    property_id=config.property_id,
                    pms_source=PMSSource(config.pms_type),
                    unit_number=unit.get("unit_number") or "",
                    floorplan=unit.get("floorplan") or "",
                    floorplan_name=unit.get("floorplan_name"),
                    bedrooms=unit.get("bedrooms") or 0,
                    bathrooms=unit.get("bathrooms") or 0,
                    square_feet=unit.get("square_feet") or 0,
                    market_rent=unit.get("market_rent") or 0,
                    status=status if status in ("occupied", "vacant", "down", "notice", "model") else (
                        "vacant" if occ_status in ("vacant_ready", "vacant_not_ready") else (occ_status or status)
                    ),
                    building=unit.get("building"),
                    floor=unit.get("floor"),
                    ready_status=ready_status,
                    available=is_available,
                    days_vacant=unit.get("days_vacant"),
                    available_date=unit.get("available_date"),
                    on_notice_date=unit.get("on_notice_date"),
                ))
        
        return all_units
    
    def get_all_residents(
        self,
        configs: List[PMSConfig],
        status: Optional[str] = None
    ) -> List[UnifiedResident]:
        """
        Get combined resident list from all properties (for drill-through).
        """
        all_residents: List[UnifiedResident] = []
        
        for config in configs:
            residents = self._get_residents_from_db(config.property_id)
            if not residents:
                continue
            
            for res in residents:
                # Re-categorize Current residents with notice_date to "Notice" status
                # (RealPage doesn't have Notice status - they're still Current with notice_date)
                notice_date = res.get("notice_date")
                res_status = res.get("status", "unknown")
                if res_status == "Current" and notice_date:
                    res_status = "Notice"
                
                all_residents.append(UnifiedResident(
                    resident_id=res.get("resident_id", ""),
                    property_id=config.property_id,
                    pms_source=PMSSource(config.pms_type),
                    unit_id=res.get("unit_id", ""),
                    unit_number=res.get("unit_number"),
                    first_name=res.get("first_name", ""),
                    last_name=res.get("last_name", ""),
                    current_rent=res.get("current_rent", 0),
                    status=res_status,
                    lease_start=res.get("lease_start"),
                    lease_end=res.get("lease_end"),
                    move_in_date=res.get("move_in_date"),
                    move_out_date=res.get("move_out_date"),
                    notice_date=notice_date,
                ))
        
        return all_residents
    
    def get_portfolio_summary(
        self,
        configs: List[PMSConfig],
        mode: AggregationMode = AggregationMode.WEIGHTED_AVERAGE
    ) -> PortfolioSummary:
        """
        Get complete portfolio summary with all metrics.
        """
        occupancy = self.get_portfolio_occupancy(configs, mode)
        pricing = self.get_portfolio_pricing(configs, mode)
        
        # Get counts
        all_units = self.get_all_units(configs)
        all_residents = self.get_all_residents(configs, status="current")
        
        # Get property names from unified.db
        property_names = []
        try:
            conn = sqlite3.connect(UNIFIED_DB_PATH)
            cursor = conn.cursor()
            for config in configs:
                cursor.execute("SELECT name FROM unified_properties WHERE unified_property_id = ?", (config.property_id,))
                row = cursor.fetchone()
                property_names.append(row[0] if row else config.property_id)
            conn.close()
        except Exception:
            property_names = [c.property_id for c in configs]
        
        return PortfolioSummary(
            property_ids=[c.property_id for c in configs],
            property_names=property_names,
            aggregation_mode=mode,
            occupancy=occupancy,
            pricing=pricing,
            total_unit_count=len(all_units),
            total_resident_count=len(all_residents),
        )
