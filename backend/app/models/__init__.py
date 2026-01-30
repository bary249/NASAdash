# Models package - re-export from original models.py for backwards compatibility
# Also exports new unified models

# Import all from original models.py (one directory up, use relative import workaround)
import sys
from pathlib import Path

# Add parent to allow importing the original models module
_parent = Path(__file__).parent.parent
_models_file = _parent / "models.py"

# Import original models using importlib
import importlib.util
spec = importlib.util.spec_from_file_location("_original_models", _models_file)
_original_models = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_original_models)

# Re-export everything from original models
Timeframe = _original_models.Timeframe
OccupancyMetrics = _original_models.OccupancyMetrics
ExposureMetrics = _original_models.ExposureMetrics
LeasingFunnelMetrics = _original_models.LeasingFunnelMetrics
FloorplanPricing = _original_models.FloorplanPricing
UnitPricingMetrics = _original_models.UnitPricingMetrics
UnitRaw = _original_models.UnitRaw
ResidentRaw = _original_models.ResidentRaw
ProspectRaw = _original_models.ProspectRaw
PropertyInfo = _original_models.PropertyInfo
DashboardSummary = _original_models.DashboardSummary
MarketComp = _original_models.MarketComp
MarketCompsResponse = _original_models.MarketCompsResponse

# Export new unified models
from .unified import (
    PMSSource,
    AggregationMode,
    UnifiedUnit,
    UnifiedResident,
    UnifiedLease,
    UnifiedOccupancy,
    UnifiedProperty,
    UnifiedPricing,
    PortfolioOccupancy,
    PortfolioPricing,
    PortfolioSummary,
    PMSConfig,
    PropertyMapping,
    PortfolioConfig,
)
