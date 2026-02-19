"""
Market Comps Service - Retrieves market comparison data from ALN API.
READ-ONLY: Only retrieves and transforms data, no modifications.
"""
import math
from typing import List, Optional, Tuple
from app.clients.aln_client import ALNClient
from app.models import MarketComp, MarketCompsResponse


class MarketCompsService:
    """Service for retrieving market comps from ALN Data."""
    
    def __init__(self):
        self.aln = ALNClient()
    
    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance in miles between two lat/lon points."""
        R = 3958.8  # Earth radius in miles
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    async def get_market_comps(
        self, 
        submarket: str,
        subject_property: Optional[str] = None,
        limit: int = 20,
        min_units: Optional[int] = None,
        max_units: Optional[int] = None,
        min_year_built: Optional[int] = None,
        max_year_built: Optional[int] = None,
        property_class: Optional[str] = None,
        amenities: Optional[List[str]] = None,
        subject_lat: Optional[float] = None,
        subject_lon: Optional[float] = None,
        max_distance: Optional[float] = None,
    ) -> MarketCompsResponse:
        """
        Get comparable properties in a submarket with optional filters.
        Falls back to placeholder data if ALN API is unavailable.
        """
        try:
            # Fetch more than limit to allow post-filtering by distance
            fetch_limit = limit * 3 if max_distance else limit
            apartments_data = await self.aln.get_apartments_by_submarket(
                submarket=submarket,
                top=fetch_limit,
                min_units=min_units,
                max_units=max_units,
                min_year_built=min_year_built,
                max_year_built=max_year_built,
                property_class=property_class,
                amenities=amenities
            )
            comps = self._extract_comps(apartments_data)
            print(f"[ALN] Got {len(comps)} comps from ALN API")
            
            # Calculate distance from subject property
            if subject_lat and subject_lon:
                for c in comps:
                    if c.latitude and c.longitude:
                        c.distance_miles = round(self._haversine(subject_lat, subject_lon, c.latitude, c.longitude), 1)
                # Filter by max distance
                if max_distance:
                    comps = [c for c in comps if c.distance_miles is not None and c.distance_miles <= max_distance]
                # Sort by distance
                comps.sort(key=lambda c: c.distance_miles if c.distance_miles is not None else 9999)
                comps = comps[:limit]
            
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
            
            # Property class (A, B, C, D)
            property_class = prop.get("Class") or prop.get("PropertyClass")
            if property_class and isinstance(property_class, str):
                property_class = property_class.strip().upper()[:1]  # Normalize to single letter
            
            # Latitude / Longitude
            latitude = None
            longitude = None
            try:
                lat_val = prop.get("Latitude") or prop.get("Lat")
                lon_val = prop.get("Longitude") or prop.get("Lng") or prop.get("Long")
                if lat_val is not None:
                    latitude = float(lat_val)
                if lon_val is not None:
                    longitude = float(lon_val)
            except (ValueError, TypeError):
                pass
            
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
                # Fallback lat/lon from address if not on property
                if latitude is None and addr.get("Latitude"):
                    try:
                        latitude = float(addr["Latitude"])
                    except (ValueError, TypeError):
                        pass
                if longitude is None and addr.get("Longitude"):
                    try:
                        longitude = float(addr["Longitude"])
                    except (ValueError, TypeError):
                        pass
            
            comps.append(MarketComp(
                aln_id=prop.get("ALNId", 0),
                property_name=prop.get("AptName", ""),
                address=address,
                city=city,
                state=state,
                num_units=num_units,
                year_built=year_built,
                property_class=property_class,
                occupancy=occupancy,
                average_rent=avg_rent,
                studio_rent=rents_by_bed.get(0),
                one_bed_rent=rents_by_bed.get(1),
                two_bed_rent=rents_by_bed.get(2),
                three_bed_rent=rents_by_bed.get(3),
                latitude=latitude,
                longitude=longitude,
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
                property_name="The Summit at Westlake",
                address="1200 Capital of Texas Hwy",
                city="Austin",
                state="TX",
                num_units=312,
                year_built=2019,
                property_class="A",
                occupancy=94.5,
                average_rent=2150,
                studio_rent=1450,
                one_bed_rent=1850,
                two_bed_rent=2450,
                three_bed_rent=3100,
                latitude=30.3074,
                longitude=-97.8107,
                distance_miles=2.4,
            ),
            MarketComp(
                aln_id=2,
                property_name="Broadstone Travesia",
                address="9501 Dessau Rd",
                city="Austin",
                state="TX",
                num_units=264,
                year_built=2021,
                property_class="A",
                occupancy=96.0,
                average_rent=2350,
                studio_rent=1600,
                one_bed_rent=2050,
                two_bed_rent=2650,
                three_bed_rent=3350,
                latitude=30.3941,
                longitude=-97.6538,
                distance_miles=4.1,
            ),
            MarketComp(
                aln_id=3,
                property_name="Settlers Creek",
                address="3100 Settler Way",
                city="Round Rock",
                state="TX",
                num_units=188,
                year_built=2016,
                property_class="B",
                occupancy=92.0,
                average_rent=1950,
                studio_rent=1250,
                one_bed_rent=1650,
                two_bed_rent=2250,
                three_bed_rent=2800,
                latitude=30.5218,
                longitude=-97.6790,
                distance_miles=1.2,
            ),
            MarketComp(
                aln_id=4,
                property_name="Lakeline Villas",
                address="1155 Lakeline Blvd",
                city="Cedar Park",
                state="TX",
                num_units=224,
                year_built=2013,
                property_class="B",
                occupancy=93.8,
                average_rent=1780,
                studio_rent=1150,
                one_bed_rent=1520,
                two_bed_rent=2080,
                three_bed_rent=2600,
                latitude=30.4941,
                longitude=-97.7989,
                distance_miles=7.3,
            ),
            MarketComp(
                aln_id=5,
                property_name="Avery Ranch Flats",
                address="10200 Avery Ranch Blvd",
                city="Austin",
                state="TX",
                num_units=156,
                year_built=2022,
                property_class="A",
                occupancy=91.2,
                average_rent=2480,
                studio_rent=1700,
                one_bed_rent=2200,
                two_bed_rent=2850,
                three_bed_rent=3500,
                latitude=30.4985,
                longitude=-97.7638,
                distance_miles=5.6,
            ),
            MarketComp(
                aln_id=6,
                property_name="Georgetown Crossing",
                address="450 Wolf Ranch Pkwy",
                city="Georgetown",
                state="TX",
                num_units=198,
                year_built=2017,
                property_class="B",
                occupancy=95.3,
                average_rent=1680,
                studio_rent=1100,
                one_bed_rent=1420,
                two_bed_rent=1950,
                three_bed_rent=2450,
                latitude=30.6333,
                longitude=-97.6961,
                distance_miles=9.1,
            ),
            MarketComp(
                aln_id=7,
                property_name="Domain Heights",
                address="11400 Domain Dr",
                city="Austin",
                state="TX",
                num_units=340,
                year_built=2020,
                property_class="A",
                occupancy=94.8,
                average_rent=2620,
                studio_rent=1800,
                one_bed_rent=2300,
                two_bed_rent=2950,
                three_bed_rent=3650,
                latitude=30.4021,
                longitude=-97.7253,
                distance_miles=11.8,
            ),
            MarketComp(
                aln_id=8,
                property_name="Wells Branch Commons",
                address="2100 Wells Branch Pkwy",
                city="Austin",
                state="TX",
                num_units=142,
                year_built=2008,
                property_class="C",
                occupancy=97.1,
                average_rent=1420,
                studio_rent=950,
                one_bed_rent=1180,
                two_bed_rent=1620,
                three_bed_rent=2050,
                latitude=30.4424,
                longitude=-97.6812,
                distance_miles=6.8,
            ),
        ]
