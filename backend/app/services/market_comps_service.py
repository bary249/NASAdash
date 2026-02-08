"""
Market Comps Service - Retrieves market comparison data from ALN API.
READ-ONLY: Only retrieves and transforms data, no modifications.
"""
from typing import List, Optional
from app.clients.aln_client import ALNClient
from app.models import MarketComp, MarketCompsResponse


class MarketCompsService:
    """Service for retrieving market comps from ALN Data."""
    
    def __init__(self):
        self.aln = ALNClient()
    
    async def get_market_comps(
        self, 
        submarket: str,
        subject_property: Optional[str] = None,
        limit: int = 20,
        min_units: Optional[int] = None,
        max_units: Optional[int] = None,
        min_year_built: Optional[int] = None,
        max_year_built: Optional[int] = None,
        amenities: Optional[List[str]] = None
    ) -> MarketCompsResponse:
        """
        Get comparable properties in a submarket with optional filters.
        Falls back to placeholder data if ALN API is unavailable.
        """
        try:
            apartments_data = await self.aln.get_apartments_by_submarket(
                submarket=submarket,
                top=limit,
                min_units=min_units,
                max_units=max_units,
                min_year_built=min_year_built,
                max_year_built=max_year_built,
                amenities=amenities
            )
            comps = self._extract_comps(apartments_data)
            print(f"[ALN] Got {len(comps)} comps from ALN API")
            # Fall back to placeholder if ALN returns empty
            if not comps:
                print(f"[ALN] No comps found, using placeholder data")
                comps = self._get_placeholder_comps(submarket)
        except Exception as e:
            print(f"[ALN] Error fetching from ALN: {type(e).__name__}: {e}")
            comps = self._get_placeholder_comps(submarket)
        
        if subject_property:
            comps = [c for c in comps if c.property_name.lower() != subject_property.lower()]
        
        avg_rent = sum(c.average_rent or 0 for c in comps) / len(comps) if comps else 0
        avg_occ = sum(c.occupancy or 0 for c in comps) / len(comps) if comps else 0
        
        return MarketCompsResponse(
            submarket=submarket,
            subject_property=subject_property,
            comps=comps,
            avg_market_rent=round(avg_rent, 2),
            avg_occupancy=round(avg_occ, 1)
        )
    
    async def search_comps(
        self,
        city: Optional[str] = None,
        state: Optional[str] = None,
        min_units: Optional[int] = None,
        max_units: Optional[int] = None,
        limit: int = 20
    ) -> List[MarketComp]:
        """Search for comparable properties by criteria."""
        try:
            apartments_data = await self.aln.search_apartments(
                city=city,
                state=state,
                min_units=min_units,
                max_units=max_units,
                top=limit
            )
            return self._extract_comps(apartments_data)
        except Exception:
            return self._get_placeholder_comps("Search Results")
    
    def _extract_comps(self, data: dict) -> List[MarketComp]:
        """Extract market comp list from ALN response."""
        comps = []
        
        apartments = data.get("value", [])
        if isinstance(apartments, dict):
            apartments = [apartments]
        
        for apt in apartments:
            # ALN nests property data under "Property" key
            prop = apt.get("Property", apt)
            floorplans = apt.get("FloorPlans", [])
            rents_by_bed = self._aggregate_rents_by_bedroom(floorplans)
            
            # Handle occupancy - can be string or number
            occupancy = prop.get("Occupancy")
            if occupancy and isinstance(occupancy, str):
                try:
                    occupancy = float(occupancy)
                except ValueError:
                    occupancy = None
            elif occupancy is not None:
                try:
                    occupancy = float(occupancy)
                except (ValueError, TypeError):
                    occupancy = None
            
            # Handle year built - can be string like "2015"
            year_built = prop.get("YearBuilt")
            if year_built and isinstance(year_built, str):
                try:
                    year_built = int(year_built)
                except ValueError:
                    year_built = None
            
            # Handle average rent
            avg_rent = prop.get("AverageRent")
            if avg_rent is not None:
                try:
                    avg_rent = float(avg_rent)
                except (ValueError, TypeError):
                    avg_rent = None
            
            # Handle num units
            num_units = prop.get("NumUnits", 0)
            if isinstance(num_units, str):
                try:
                    num_units = int(num_units)
                except ValueError:
                    num_units = 0
            
            # Get address from Addresses array if available
            addresses = apt.get("Addresses", [])
            address = ""
            city = ""
            state = ""
            if addresses and len(addresses) > 0:
                addr = addresses[0] if isinstance(addresses, list) else addresses
                address = addr.get("Address1", "") or addr.get("Address", "")
                city = addr.get("City", "")
                state = addr.get("State", "")
            
            comps.append(MarketComp(
                aln_id=prop.get("ALNId", 0),
                property_name=prop.get("AptName", ""),
                address=address,
                city=city,
                state=state,
                num_units=num_units,
                year_built=year_built,
                occupancy=occupancy,
                average_rent=avg_rent,
                studio_rent=rents_by_bed.get(0),
                one_bed_rent=rents_by_bed.get(1),
                two_bed_rent=rents_by_bed.get(2),
                three_bed_rent=rents_by_bed.get(3)
            ))
        
        return comps
    
    def _aggregate_rents_by_bedroom(self, floorplans: list) -> dict:
        """Aggregate average rents by bedroom count."""
        rents = {}
        counts = {}
        
        for fp in floorplans if isinstance(floorplans, list) else []:
            bedrooms = fp.get("Bedrooms", 0)
            rent = fp.get("Rent", 0)
            
            if rent and rent > 0:
                if bedrooms not in rents:
                    rents[bedrooms] = 0
                    counts[bedrooms] = 0
                rents[bedrooms] += rent
                counts[bedrooms] += 1
        
        return {
            bed: round(rents[bed] / counts[bed], 2) 
            for bed in rents if counts.get(bed, 0) > 0
        }
    
    def _get_placeholder_comps(self, submarket: str) -> List[MarketComp]:
        """Return placeholder data when ALN API is unavailable."""
        return [
            MarketComp(
                aln_id=1,
                property_name="Sample Property A",
                address="123 Main St",
                city="Santa Monica",
                state="CA",
                num_units=150,
                year_built=2018,
                occupancy=94.5,
                average_rent=2150,
                one_bed_rent=1850,
                two_bed_rent=2450
            ),
            MarketComp(
                aln_id=2,
                property_name="Sample Property B",
                address="456 Ocean Ave",
                city="Santa Monica",
                state="CA",
                num_units=200,
                year_built=2020,
                occupancy=96.0,
                average_rent=2350,
                one_bed_rent=2050,
                two_bed_rent=2650
            ),
            MarketComp(
                aln_id=3,
                property_name="Sample Property C",
                address="789 Beach Blvd",
                city="Santa Monica",
                state="CA",
                num_units=120,
                year_built=2015,
                occupancy=92.0,
                average_rent=1950,
                one_bed_rent=1650,
                two_bed_rent=2250
            )
        ]
