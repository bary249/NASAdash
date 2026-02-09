"""
Unified Data Models for Multi-PMS Dashboard.
These models normalize data from Yardi and RealPage into a common format.
"""
from pydantic import BaseModel
from typing import List, Optional
from datetime import date
from enum import Enum


class PMSSource(str, Enum):
    """Source PMS system."""
    YARDI = "yardi"
    REALPAGE = "realpage"


class AggregationMode(str, Enum):
    """Aggregation mode for portfolio metrics."""
    WEIGHTED_AVERAGE = "weighted_avg"  # Calculate per-property, then average
    ROW_METRICS = "row_metrics"        # Combine all raw data, then calculate


class UnifiedUnit(BaseModel):
    """Normalized unit data from any PMS."""
    unit_id: str
    property_id: str
    pms_source: PMSSource
    unit_number: str
    floorplan: str = ""
    floorplan_name: Optional[str] = None
    bedrooms: int = 0
    bathrooms: float = 0
    square_feet: int = 0
    market_rent: float = 0
    status: str  # "occupied" | "vacant" | "notice" | "model" | "down"
    building: Optional[str] = None
    floor: Optional[str] = None
    ready_status: Optional[str] = None  # "ready" | "not_ready"
    available: Optional[bool] = None  # True if vacant AND ready
    days_vacant: Optional[int] = None
    available_date: Optional[date] = None
    on_notice_date: Optional[str] = None  # Date when tenant gave notice


class UnifiedResident(BaseModel):
    """Normalized resident data from any PMS."""
    resident_id: str
    property_id: str
    pms_source: PMSSource
    unit_id: str
    unit_number: Optional[str] = None
    first_name: str
    last_name: str
    current_rent: float
    status: str  # "current" | "future" | "past" | "notice" | "applicant"
    lease_start: Optional[str] = None
    lease_end: Optional[str] = None
    move_in_date: Optional[str] = None
    move_out_date: Optional[str] = None
    notice_date: Optional[str] = None  # Date when tenant gave notice


class UnifiedLease(BaseModel):
    """Normalized lease data from any PMS."""
    resident_id: str
    property_id: str
    pms_source: PMSSource
    unit_id: str
    rent_amount: float
    lease_start: Optional[str] = None
    lease_end: Optional[str] = None
    lease_term: Optional[str] = None


class UnifiedOccupancy(BaseModel):
    """Normalized occupancy metrics."""
    property_id: str
    property_name: Optional[str] = None
    pms_source: PMSSource
    total_units: int
    occupied_units: int
    vacant_units: int
    leased_units: int
    preleased_vacant: int = 0
    available_units: int = 0
    vacant_ready: int = 0
    vacant_not_ready: int = 0
    physical_occupancy: float  # Percentage 0-100
    leased_percentage: float   # Percentage 0-100


class UnifiedProperty(BaseModel):
    """Normalized property data from any PMS."""
    property_id: str
    pms_source: PMSSource
    name: str
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None


class UnifiedPricing(BaseModel):
    """Normalized pricing metrics by floorplan."""
    property_id: str
    pms_source: PMSSource
    floorplan: str
    floorplan_name: Optional[str] = None
    unit_count: int
    bedrooms: int
    bathrooms: float
    avg_square_feet: int
    in_place_rent: float      # Average rent being paid
    in_place_per_sf: float    # In-place rent per SF
    asking_rent: float        # Average asking/market rent
    asking_per_sf: float      # Asking rent per SF
    rent_growth: float        # (Asking / In-Place) - 1


# =========================================================================
# Portfolio/Aggregated Models
# =========================================================================

class PortfolioOccupancy(BaseModel):
    """Aggregated occupancy metrics across multiple properties."""
    property_ids: List[str]
    aggregation_mode: AggregationMode
    total_units: int
    occupied_units: int
    vacant_units: int
    leased_units: int
    preleased_vacant: int = 0
    available_units: int = 0
    vacant_ready: int = 0
    vacant_not_ready: int = 0
    physical_occupancy: float
    leased_percentage: float
    # Per-property breakdown for drill-through
    property_breakdown: Optional[List[UnifiedOccupancy]] = None


class PortfolioPricing(BaseModel):
    """Aggregated pricing metrics across multiple properties."""
    property_ids: List[str]
    aggregation_mode: AggregationMode
    total_in_place_rent: float
    total_in_place_per_sf: float
    total_asking_rent: float
    total_asking_per_sf: float
    total_rent_growth: float
    # Per-floorplan breakdown (combined)
    floorplan_breakdown: Optional[List[UnifiedPricing]] = None


class PortfolioSummary(BaseModel):
    """Complete portfolio summary combining all metrics."""
    property_ids: List[str]
    property_names: List[str]
    aggregation_mode: AggregationMode
    occupancy: PortfolioOccupancy
    pricing: Optional[PortfolioPricing] = None
    # Combined raw data for drill-through
    total_unit_count: int
    total_resident_count: int


# =========================================================================
# Property Configuration Models
# =========================================================================

class PMSConfig(BaseModel):
    """Configuration for a single PMS connection."""
    pms_type: PMSSource
    property_id: str
    # Yardi-specific
    yardi_property_id: Optional[str] = None
    # RealPage-specific
    realpage_pmcid: Optional[str] = None
    realpage_siteid: Optional[str] = None
    realpage_licensekey: Optional[str] = None


class PropertyMapping(BaseModel):
    """Maps a unified property ID to its PMS configuration."""
    unified_id: str
    name: str
    pms_config: PMSConfig


class PortfolioConfig(BaseModel):
    """Configuration for a portfolio of properties."""
    portfolio_id: str
    name: str
    properties: List[PropertyMapping]
