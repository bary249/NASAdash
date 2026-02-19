"""
ALN OData API Client - READ-ONLY OPERATIONS ONLY
This client only implements GET operations for market comps data.
"""
import httpx
from typing import Optional
from app.config import get_settings


class ALNClient:
    """
    REST client for ALN OData API.
    IMPORTANT: This client only implements READ operations (GET).
    No write operations are permitted.
    """
    
    def __init__(self):
        self.settings = get_settings()
        # Use config URL, fallback to odata4.alndata.com if not set
        self.base_url = self.settings.aln_base_url or "https://odata4.alndata.com"
        self.api_key = self.settings.aln_api_key
        self.headers = {
            "Accept": "application/json"
        }
    
    async def get_apartments_by_submarket(
        self, 
        submarket: str,
        top: int = 20,
        min_units: Optional[int] = None,
        max_units: Optional[int] = None,
        min_year_built: Optional[int] = None,
        max_year_built: Optional[int] = None,
        property_class: Optional[str] = None,
        amenities: Optional[list] = None
    ) -> dict:
        """
        GET operation: Retrieve apartment properties in a submarket with filters.
        Used for: Market Comps - comparable properties.
        """
        url = f"{self.base_url}/Apartments"
        
        filters = []
        if submarket:
            filters.append(f"Property/SubmarketDescription eq '{submarket}'")
        if min_units:
            filters.append(f"Property/NumUnits ge {min_units}")
        if max_units:
            filters.append(f"Property/NumUnits le {max_units}")
        if min_year_built:
            filters.append(f"Property/YearBuilt ge {min_year_built}")
        if max_year_built:
            filters.append(f"Property/YearBuilt le {max_year_built}")
        if property_class:
            filters.append(f"Property/Class eq '{property_class}'")
        
        # Amenity filters - ALN uses specific boolean fields
        if amenities:
            amenity_map = {
                "pool": "Property/Pool eq true",
                "fitness": "Property/FitnessCenter eq true",
                "clubhouse": "Property/Clubhouse eq true",
                "gated": "Property/GatedAccess eq true",
                "parking": "Property/CoveredParking eq true",
                "washer_dryer": "Property/WasherDryerConnections eq true",
                "pet_friendly": "Property/PetsAllowed eq true",
            }
            for amenity in amenities:
                if amenity.lower() in amenity_map:
                    filters.append(amenity_map[amenity.lower()])
        
        params = {
            "apikey": self.api_key,
            "$top": top,
            "$expand": "PhoneNumbers,Addresses,FloorPlans($select=Bedrooms,Rent)"
        }
        
        if filters:
            params["$filter"] = " and ".join(filters)
        
        return await self._send_get_request(url, params)
    
    async def get_apartment_details(self, aln_id: int) -> dict:
        """
        GET operation: Retrieve detailed information for a specific property.
        Used for: Property details, floorplan pricing.
        """
        url = f"{self.base_url}/Apartments({aln_id})"
        params = {
            "apikey": self.api_key,
            "$expand": "FloorPlans,Owner"
        }
        
        return await self._send_get_request(url, params)
    
    async def search_apartments(
        self,
        city: Optional[str] = None,
        state: Optional[str] = None,
        min_units: Optional[int] = None,
        max_units: Optional[int] = None,
        top: int = 20
    ) -> dict:
        """
        GET operation: Search apartments by criteria.
        Used for: Finding comp properties.
        """
        url = f"{self.base_url}/Apartments"
        
        filters = []
        if city:
            filters.append(f"City eq '{city}'")
        if state:
            filters.append(f"State eq '{state}'")
        if min_units:
            filters.append(f"NumUnits ge {min_units}")
        if max_units:
            filters.append(f"NumUnits le {max_units}")
        
        params = {
            "apikey": self.api_key,
            "$top": top,
            "$select": "ALNId,AptName,NumUnits,Address,City,State,Submarket,Occupancy,AverageRent",
            "$expand": "FloorPlans($select=Bedrooms,Rent)"
        }
        
        if filters:
            params["$filter"] = " and ".join(filters)
        
        return await self._send_get_request(url, params)
    
    async def get_all_submarkets(self) -> dict:
        """
        GET operation: Retrieve all submarkets from ALN.
        Used for: Market Comps submarket dropdown.
        """
        url = f"{self.base_url}/Submarkets"
        params = {
            "apikey": self.api_key,
            "$select": "SubmarketId,SubMarketDescription,Market",
            "$orderby": "SubMarketDescription"
        }
        
        return await self._send_get_request(url, params)
    
    async def _send_get_request(self, url: str, params: dict) -> dict:
        """Send GET request and return JSON response."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
