"""
Pydantic models for Owner Dashboard V2 API responses.
Implements spec from Owners Dashboard Specification.
"""
from pydantic import BaseModel
from typing import List, Optional
from enum import Enum


class Timeframe(str, Enum):
    """
    Timeframe options per spec Section 2.
    - CM: Current Month (1st of current month to now)
    - PM: Previous Month (1st to last day of previous month)
    - YTD: Year-to-Date (Jan 1st to now, with averaging for occupancy)
    - L30: Last 30 days
    - L7: Last 7 days
    """
    CM = "cm"
    PM = "pm"
    YTD = "ytd"
    L30 = "l30"
    L7 = "l7"


class OccupancyMetrics(BaseModel):
    """Module 1: Occupancy metrics (Vital Signs)."""
    property_id: str
    property_name: str
    timeframe: str
    period_start: str
    period_end: str
    
    # Core occupancy
    total_units: int
    occupied_units: int
    vacant_units: int
    leased_units: int
    preleased_vacant: int  # Vacant units with signed future lease
    
    # Percentages
    physical_occupancy: float  # Total Occupied / Total Units
    leased_percentage: float   # (Occupied + Preleased Vacant) / Total Units
    
    # Notice breakdown
    notice_break_units: int = 0  # NTV units breaking lease early (available_date << lease_end)
    
    # Vacancy breakdown
    vacant_ready: int          # Move-in ready vacant units
    vacant_not_ready: int      # Not move-in ready vacant units
    available_units: int       # Available for rent (subset of vacant)
    aged_vacancy_90_plus: int  # Units vacant > 90 days


class ExposureMetrics(BaseModel):
    """Module 1: Exposure metrics (Risk indicators)."""
    property_id: str
    timeframe: str
    period_start: str
    period_end: str
    
    # Exposure = (Vacant + Pending Move-outs) - Pending Move-ins
    exposure_30_days: int  # Exposure within 30 days
    exposure_60_days: int  # Exposure within 60 days
    
    # Notices (NTVs) - pending move-outs
    notices_total: int
    notices_30_days: int   # Notices with move-out in next 30 days
    notices_60_days: int   # Notices with move-out in next 60 days
    
    # Pending move-ins (scheduled/future leases)
    pending_moveins_30_days: int = 0  # Scheduled move-ins within 30 days
    pending_moveins_60_days: int = 0  # Scheduled move-ins within 60 days
    
    # Move-ins/outs for the period (historical)
    move_ins: int
    move_outs: int
    net_absorption: int  # Move-ins - Move-outs


class LeasingFunnelMetrics(BaseModel):
    """Module 2: Marketing Funnel (Pipeline)."""
    property_id: str
    timeframe: str
    period_start: str
    period_end: str
    
    # Raw counts
    leads: int          # Unique contacts/inquiries (Guest Cards)
    tours: int          # Verified visits (Show events)
    applications: int   # Submitted applications
    lease_signs: int    # Signed leases (countersigned)
    denials: int        # Denied applications
    sight_unseen: int = 0    # Leased without any tour/visit
    tour_to_app: int = 0     # Prospects who toured AND applied
    
    # Conversion rates
    lead_to_tour_rate: float     # Tours / Leads %
    tour_to_app_rate: float      # Applications / Tours %
    app_to_lease_rate: float     # Lease Signs / Applications %
    lead_to_lease_rate: float    # Lease Signs / Leads %
    
    # Marketing cross-reference
    marketing_net_leases: Optional[int] = None   # Net leases from Advertising Source report (leases - cancelled/denied)
    
    # Derived marketing metrics (Step 1.2)
    avg_days_to_lease: Optional[float] = None   # Avg days from first contact to lease sign
    app_completion_rate: Optional[float] = None  # % of pre-qualifies that reach agreement
    app_approval_rate: Optional[float] = None    # % of agreements that reach leased status


class FloorplanPricing(BaseModel):
    """Unit pricing by floorplan/unit type."""
    floorplan_id: str
    name: str           # Unit Type (e.g., SA, SB, 1+1A)
    unit_count: int
    bedrooms: int
    bathrooms: float
    square_feet: int    # Average SF for this type
    
    # In-Place (current residents)
    in_place_rent: float        # Weighted average rent paid
    in_place_rent_per_sf: float
    
    # Asking (market)
    asking_rent: float          # Weighted average asking price
    asking_rent_per_sf: float
    
    # Growth
    rent_growth: float  # (Asking / In-Place) - 1


class UnitPricingMetrics(BaseModel):
    """Module: Unit Data / Pricing."""
    property_id: str
    property_name: str
    
    # Per-floorplan breakdown
    floorplans: List[FloorplanPricing]
    
    # Portfolio totals (weighted averages)
    total_in_place_rent: float
    total_in_place_per_sf: float
    total_asking_rent: float
    total_asking_per_sf: float
    total_rent_growth: float


class UnitRaw(BaseModel):
    """Raw unit data for drill-through."""
    unit_id: str
    floorplan: str
    unit_type: str
    bedrooms: int
    bathrooms: float
    square_feet: int
    market_rent: float
    status: str
    occupancy_status: str
    days_vacant: Optional[int] = None
    available_date: Optional[str] = None


class ResidentRaw(BaseModel):
    """Raw resident data for drill-through."""
    resident_id: str
    first_name: str
    last_name: str
    unit: str
    rent: float
    status: str
    move_in_date: Optional[str] = None
    move_out_date: Optional[str] = None
    lease_start: Optional[str] = None
    lease_end: Optional[str] = None
    notice_date: Optional[str] = None


class ProspectRaw(BaseModel):
    """Raw prospect data for drill-through."""
    first_name: str
    last_name: str
    email: str
    phone: Optional[str] = None
    desired_floorplan: Optional[str] = None
    target_move_in: Optional[str] = None
    last_event: str
    event_date: Optional[str] = None
    event_count: int


class PropertyInfo(BaseModel):
    """Basic property information."""
    id: str
    name: str
    city: Optional[str] = None
    state: Optional[str] = None
    address: Optional[str] = None
    floor_count: Optional[int] = None
    google_rating: Optional[float] = None
    google_review_count: Optional[int] = None


class DashboardSummary(BaseModel):
    """Complete dashboard summary for a property."""
    property_info: PropertyInfo
    timeframe: str
    occupancy: OccupancyMetrics
    exposure: ExposureMetrics
    leasing_funnel: LeasingFunnelMetrics
    pricing: Optional[UnitPricingMetrics] = None


class MarketComp(BaseModel):
    """Market comparable property from ALN."""
    aln_id: int
    property_name: str
    address: str
    city: str
    state: str
    num_units: int
    year_built: Optional[int] = None
    property_class: Optional[str] = None  # A, B, C, D
    occupancy: Optional[float] = None
    average_rent: Optional[float] = None
    studio_rent: Optional[float] = None
    one_bed_rent: Optional[float] = None
    two_bed_rent: Optional[float] = None
    three_bed_rent: Optional[float] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_miles: Optional[float] = None  # Distance from subject property


class MarketCompsResponse(BaseModel):
    """Market comps response with averages."""
    submarket: str
    subject_property: Optional[str] = None
    comps: List[MarketComp]
    avg_market_rent: float
    avg_occupancy: float
