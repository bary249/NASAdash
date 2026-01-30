"""
Abstract PMS Interface - Unified interface for Property Management Systems.
Implementations: YardiClient, RealPageClient

READ-ONLY OPERATIONS ONLY - No write operations permitted.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from datetime import date
from enum import Enum


class PMSType(str, Enum):
    """Supported PMS types."""
    YARDI = "yardi"
    REALPAGE = "realpage"


class PMSInterface(ABC):
    """
    Abstract interface for PMS data providers.
    
    All implementations must be READ-ONLY.
    No PUT, POST, DELETE operations are permitted.
    """
    
    @property
    @abstractmethod
    def pms_type(self) -> PMSType:
        """Return the PMS type identifier."""
        pass
    
    @abstractmethod
    async def get_properties(self) -> List[dict]:
        """
        Get list of properties/sites.
        
        Returns:
            List of property dicts with at minimum:
            - property_id: str
            - name: str
            - address: Optional[str]
        """
        pass
    
    @abstractmethod
    async def get_units(self, property_id: str) -> List[dict]:
        """
        Get unit information for a property.
        
        Returns:
            List of unit dicts with:
            - unit_id: str
            - unit_number: str
            - floorplan: str
            - bedrooms: int
            - bathrooms: float
            - square_feet: int
            - market_rent: float
            - status: str (occupied, vacant, notice, model, down)
        """
        pass
    
    @abstractmethod
    async def get_residents(
        self, 
        property_id: str, 
        status: Optional[str] = None
    ) -> List[dict]:
        """
        Get residents for a property, optionally filtered by status.
        
        Args:
            property_id: Property identifier
            status: Optional filter (current, future, past, notice, applicant)
        
        Returns:
            List of resident dicts with:
            - resident_id: str
            - unit_id: str
            - first_name: str
            - last_name: str
            - current_rent: float
            - status: str
            - lease_start: Optional[date]
            - lease_end: Optional[date]
            - move_in_date: Optional[date]
            - move_out_date: Optional[date]
        """
        pass
    
    @abstractmethod
    async def get_occupancy_metrics(self, property_id: str) -> dict:
        """
        Get occupancy metrics for a property.
        
        Returns:
            Dict with:
            - total_units: int
            - occupied_units: int
            - vacant_units: int
            - leased_units: int
            - preleased_vacant: int
            - physical_occupancy: float (0-100)
            - leased_percentage: float (0-100)
        """
        pass
    
    @abstractmethod
    async def get_lease_data(self, property_id: str) -> List[dict]:
        """
        Get lease/charge information for a property.
        
        Returns:
            List of lease dicts with:
            - resident_id: str
            - unit_id: str
            - rent_amount: float
            - lease_start: date
            - lease_end: date
            - charges: List[dict] (optional detailed charges)
        """
        pass
    
    async def get_available_units(self, property_id: str) -> List[dict]:
        """
        Get available units with pricing (optional override).
        Default implementation filters units by vacant status.
        
        Returns:
            List of available unit dicts with pricing info.
        """
        units = await self.get_units(property_id)
        return [u for u in units if u.get("status") in ("vacant", "available")]
    
    async def health_check(self) -> dict:
        """
        Verify connectivity to the PMS.
        
        Returns:
            Dict with:
            - status: str (ok, error)
            - message: Optional[str]
            - pms_type: str
        """
        try:
            properties = await self.get_properties()
            return {
                "status": "ok",
                "pms_type": self.pms_type.value,
                "property_count": len(properties)
            }
        except Exception as e:
            return {
                "status": "error",
                "pms_type": self.pms_type.value,
                "message": str(e)
            }
