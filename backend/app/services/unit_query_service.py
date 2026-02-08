"""
Unit Query Service - Provides unit-level data for AI insights
Queries unified tables for renewals, delinquencies, and other unit-level details.
READ-ONLY service.
"""
import logging
import sqlite3
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "db" / "unified.db"


class UnitQueryService:
    """Service to query unit-level data for AI insights."""
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn
    
    def get_upcoming_renewals(
        self,
        property_id: str,
        days_ahead: int = 90,
        min_rent: Optional[float] = None
    ) -> List[Dict[str, Any]]:
        """
        Get residents with leases expiring in the next X days.
        
        Args:
            property_id: Unified property ID
            days_ahead: Number of days to look ahead (default 90)
            min_rent: Optional minimum rent filter for high-value leases
            
        Returns:
            List of renewal records with unit, resident, rent, expiration info
        """
        conn = self._get_connection()
        try:
            today = datetime.now().date()
            end_date = today + timedelta(days=days_ahead)
            
            query = """
                SELECT 
                    r.unit_number,
                    r.first_name || ' ' || r.last_name as resident_name,
                    r.current_rent,
                    r.lease_end,
                    r.move_in_date,
                    r.status,
                    r.email,
                    r.phone,
                    u.floorplan_name,
                    u.bedrooms,
                    u.square_feet,
                    u.market_rent
                FROM unified_residents r
                LEFT JOIN unified_units u ON r.unified_property_id = u.unified_property_id 
                    AND r.unit_number = u.unit_number
                WHERE r.unified_property_id = ?
                    AND r.status IN ('current', 'Current', 'CURRENT')
                    AND r.lease_end IS NOT NULL
                    AND date(r.lease_end) BETWEEN date(?) AND date(?)
            """
            params = [property_id, today.isoformat(), end_date.isoformat()]
            
            if min_rent:
                query += " AND r.current_rent >= ?"
                params.append(min_rent)
            
            query += " ORDER BY r.lease_end ASC"
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                # Calculate days until expiration
                lease_end = row['lease_end']
                if lease_end:
                    try:
                        exp_date = datetime.strptime(lease_end[:10], '%Y-%m-%d').date()
                        days_until = (exp_date - today).days
                    except:
                        days_until = None
                else:
                    days_until = None
                
                # Calculate tenure
                move_in = row['move_in_date']
                if move_in:
                    try:
                        mi_date = datetime.strptime(move_in[:10], '%Y-%m-%d').date()
                        tenure_days = (today - mi_date).days
                    except:
                        tenure_days = None
                else:
                    tenure_days = None
                
                # Calculate risk level based on factors
                risk_level = self._calculate_renewal_risk(
                    days_until=days_until,
                    tenure_days=tenure_days,
                    rent=row['current_rent'],
                    market_rent=row['market_rent']
                )
                
                results.append({
                    'unit': row['unit_number'],
                    'resident': row['resident_name'],
                    'monthlyRent': f"US${row['current_rent']:,.0f}" if row['current_rent'] else 'N/A',
                    'rent_amount': row['current_rent'],
                    'expires': f"{days_until} days" if days_until else 'N/A',
                    'expiration_date': lease_end[:10] if lease_end else None,
                    'riskLevel': risk_level,
                    'keyFactors': self._get_risk_factors(days_until, tenure_days, row['current_rent'], row['market_rent']),
                    'offerSent': 'Not yet',  # Would need additional tracking
                    'floorplan': row['floorplan_name'],
                    'bedrooms': row['bedrooms'],
                    'email': row['email'],
                    'phone': row['phone'],
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error querying renewals: {e}")
            return []
        finally:
            conn.close()
    
    def _calculate_renewal_risk(
        self,
        days_until: Optional[int],
        tenure_days: Optional[int],
        rent: Optional[float],
        market_rent: Optional[float]
    ) -> str:
        """Calculate renewal risk level based on multiple factors."""
        risk_score = 0
        
        # Urgency factor - closer expiration = higher risk
        if days_until is not None:
            if days_until <= 30:
                risk_score += 3
            elif days_until <= 60:
                risk_score += 2
            elif days_until <= 90:
                risk_score += 1
        
        # Short tenure = higher risk (less attachment)
        if tenure_days is not None:
            if tenure_days < 365:  # Less than 1 year
                risk_score += 2
            elif tenure_days < 730:  # Less than 2 years
                risk_score += 1
        
        # Below market rent = lower risk (good deal)
        # Above market rent = higher risk
        if rent and market_rent and market_rent > 0:
            rent_ratio = rent / market_rent
            if rent_ratio > 1.05:  # Paying 5%+ above market
                risk_score += 2
            elif rent_ratio > 0.95:
                risk_score += 1
        
        if risk_score >= 4:
            return 'HIGH'
        elif risk_score >= 2:
            return 'MED'
        else:
            return 'LOW'
    
    def _get_risk_factors(
        self,
        days_until: Optional[int],
        tenure_days: Optional[int],
        rent: Optional[float],
        market_rent: Optional[float]
    ) -> str:
        """Generate human-readable risk factors."""
        factors = []
        
        if days_until is not None and days_until <= 30:
            factors.append("Lease expires soon")
        
        if tenure_days is not None and tenure_days < 365:
            factors.append("First-year resident")
        elif tenure_days is not None and tenure_days >= 730:
            factors.append(f"{tenure_days // 365}-year resident")
        
        if rent and market_rent and market_rent > 0:
            rent_ratio = rent / market_rent
            if rent_ratio > 1.05:
                factors.append(f"Paying {(rent_ratio - 1) * 100:.0f}% above market")
            elif rent_ratio < 0.95:
                factors.append(f"Below market rate")
        
        return ", ".join(factors) if factors else "Standard renewal"
    
    def get_delinquent_units(
        self,
        property_id: str,
        min_days_late: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get units with outstanding balances/delinquencies.
        
        Args:
            property_id: Unified property ID
            min_days_late: Minimum days late to include
            
        Returns:
            List of delinquent unit records
        """
        conn = self._get_connection()
        try:
            query = """
                SELECT 
                    r.unit_number,
                    r.first_name || ' ' || r.last_name as resident_name,
                    r.current_rent,
                    r.balance,
                    r.status,
                    r.email,
                    r.phone,
                    r.lease_end
                FROM unified_residents r
                WHERE r.unified_property_id = ?
                    AND r.status IN ('current', 'Current', 'CURRENT')
                    AND r.balance IS NOT NULL
                    AND r.balance > 0
                ORDER BY r.balance DESC
            """
            
            cursor = conn.execute(query, [property_id])
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                balance = row['balance'] or 0
                rent = row['current_rent'] or 1
                
                # Estimate days late based on balance vs rent
                if rent > 0:
                    months_late = balance / rent
                    days_late = int(months_late * 30)
                else:
                    days_late = 30
                
                if days_late >= min_days_late:
                    results.append({
                        'unit': row['unit_number'],
                        'resident': row['resident_name'],
                        'amountDue': f"US${balance:,.0f}",
                        'amount': balance,
                        'daysLate': f"{days_late} days",
                        'days': days_late,
                        'status': self._get_delinquency_status(days_late),
                        'lastContact': 'N/A',  # Would need additional tracking
                        'email': row['email'],
                        'phone': row['phone'],
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error querying delinquencies: {e}")
            return []
        finally:
            conn.close()
    
    def _get_delinquency_status(self, days_late: int) -> str:
        """Get delinquency status based on days late."""
        if days_late <= 5:
            return "Grace period"
        elif days_late <= 15:
            return "Late notice sent"
        elif days_late <= 30:
            return "Payment plan offered"
        elif days_late <= 60:
            return "Final notice"
        else:
            return "Eviction process"
    
    def get_vacant_units(
        self,
        property_id: str,
        aged_only: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Get vacant units with details.
        
        Args:
            property_id: Unified property ID
            aged_only: If True, only return units vacant 90+ days
            
        Returns:
            List of vacant unit records
        """
        conn = self._get_connection()
        try:
            query = """
                SELECT 
                    unit_number,
                    floorplan_name,
                    bedrooms,
                    bathrooms,
                    square_feet,
                    market_rent,
                    status,
                    days_vacant,
                    available_date,
                    made_ready_date
                FROM unified_units
                WHERE unified_property_id = ?
                    AND status IN ('vacant', 'Vacant', 'VACANT')
            """
            params = [property_id]
            
            if aged_only:
                query += " AND days_vacant >= 90"
            
            query += " ORDER BY days_vacant DESC"
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'unit': row['unit_number'],
                    'floorplan': row['floorplan_name'] or 'N/A',
                    'bedrooms': row['bedrooms'],
                    'sqft': row['square_feet'],
                    'marketRent': f"US${row['market_rent']:,.0f}" if row['market_rent'] else 'N/A',
                    'rent': row['market_rent'],
                    'daysVacant': row['days_vacant'] or 0,
                    'status': 'Aged' if (row['days_vacant'] or 0) >= 90 else 'Vacant',
                    'availableDate': row['available_date'],
                    'madeReadyDate': row['made_ready_date'],
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error querying vacant units: {e}")
            return []
        finally:
            conn.close()
    
    def get_move_ins(
        self,
        property_id: str,
        days_back: int = 30
    ) -> List[Dict[str, Any]]:
        """Get recent move-ins."""
        conn = self._get_connection()
        try:
            today = datetime.now().date()
            start_date = today - timedelta(days=days_back)
            
            query = """
                SELECT 
                    r.unit_number,
                    r.first_name || ' ' || r.last_name as resident_name,
                    r.current_rent,
                    r.move_in_date,
                    r.lease_end,
                    u.floorplan_name,
                    u.market_rent
                FROM unified_residents r
                LEFT JOIN unified_units u ON r.unified_property_id = u.unified_property_id 
                    AND r.unit_number = u.unit_number
                WHERE r.unified_property_id = ?
                    AND r.move_in_date IS NOT NULL
                    AND date(r.move_in_date) BETWEEN date(?) AND date(?)
                ORDER BY r.move_in_date DESC
            """
            
            cursor = conn.execute(query, [property_id, start_date.isoformat(), today.isoformat()])
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'unit': row['unit_number'],
                    'resident': row['resident_name'],
                    'rent': f"US${row['current_rent']:,.0f}" if row['current_rent'] else 'N/A',
                    'moveInDate': row['move_in_date'][:10] if row['move_in_date'] else 'N/A',
                    'leaseEnd': row['lease_end'][:10] if row['lease_end'] else 'N/A',
                    'floorplan': row['floorplan_name'] or 'N/A',
                })
            
            return results
            
        except Exception as e:
            logger.error(f"Error querying move-ins: {e}")
            return []
        finally:
            conn.close()


# Singleton instance
unit_query_service = UnitQueryService()
