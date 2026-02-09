"""
Property Configuration - Maps properties to their PMS systems.
READ-ONLY: This configuration is for data retrieval only.
"""
from app.models.unified import PMSSource, PMSConfig, PropertyMapping, PortfolioConfig
from app.config import get_settings

settings = get_settings()

# =============================================================================
# Kairoi Properties (RealPage) - All share PMC ID 4248314
# =============================================================================

_KAIROI_PMC = "4248314"

def _kairoi_prop(unified_id: str, name: str, siteid: str) -> PropertyMapping:
    return PropertyMapping(
        unified_id=unified_id,
        name=name,
        pms_config=PMSConfig(
            pms_type=PMSSource.REALPAGE,
            property_id=unified_id,
            realpage_pmcid=_KAIROI_PMC,
            realpage_siteid=siteid,
            realpage_licensekey=settings.realpage_licensekey,
        )
    )

KAIROI_7_EAST = _kairoi_prop("7_east", "7 East", "5481703")
KAIROI_ASPIRE = _kairoi_prop("aspire_7th_grant", "Aspire 7th and Grant", "4779341")
KAIROI_BLOCK_44 = _kairoi_prop("block_44", "Block 44", "5473254")
KAIROI_DISCOVERY = _kairoi_prop("discovery_kingwood", "Discovery at Kingwood", "5618425")
KAIROI_EDEN = _kairoi_prop("eden_keller_ranch", "Eden Keller Ranch", "5536209")
KAIROI_EDISON = _kairoi_prop("edison_rino", "Edison at RiNo", "4248319")
KAIROI_HARVEST = _kairoi_prop("harvest", "Harvest", "5507303")
KAIROI_IZZY = _kairoi_prop("izzy", "Izzy", "5618432")
KAIROI_KALACO = _kairoi_prop("kalaco", "Kalaco", "5339721")
KAIROI_LUNA = _kairoi_prop("luna", "Luna", "5590740")
KAIROI_NEXUS_EAST = _kairoi_prop("nexus_east", "Nexus East", "5472172")
KAIROI_PARKSIDE = _kairoi_prop("parkside", "Parkside at Round Rock", "5536211")
KAIROI_RIDIAN = _kairoi_prop("ridian", "Ridian", "5446271")
KAIROI_THE_ALCOTT = _kairoi_prop("the_alcott", "The Alcott", "4996967")
KAIROI_THE_AVANT = _kairoi_prop("the_avant", "The Avant", "5480255")
KAIROI_THE_HUNTER = _kairoi_prop("the_hunter", "The Hunter", "5558217")
KAIROI_THE_NORTHERN = _kairoi_prop("the_northern", "The Northern", "5375283")
KAIROI_STATION = _kairoi_prop("station_riverfront", "The Station at Riverfront Park", "4976258")
KAIROI_CURATE = _kairoi_prop("curate", "Curate at Orchard Town Center", "4682517")
KAIROI_HEIGHTS = _kairoi_prop("heights_interlocken", "Heights at Interlocken", "5558216")
KAIROI_PARK17 = _kairoi_prop("park_17", "Park 17", "4481243")
KAIROI_PEARL_LANTANA = _kairoi_prop("pearl_lantana", "Pearl Lantana", "5481704")
KAIROI_SLATE = _kairoi_prop("slate", "Slate", "5486880")
KAIROI_SLOANE = _kairoi_prop("sloane", "Sloane", "5486881")
KAIROI_STONEWOOD = _kairoi_prop("stonewood", "Stonewood", "5481705")
KAIROI_TEN50 = _kairoi_prop("ten50", "Ten50", "5581218")
KAIROI_BROADLEAF = _kairoi_prop("broadleaf", "The Broadleaf", "5286092")
KAIROI_CONFLUENCE = _kairoi_prop("confluence", "The Confluence", "4832865")
KAIROI_LINKS = _kairoi_prop("links_plum_creek", "The Links at Plum Creek", "5558220")
KAIROI_THEPEARL = _kairoi_prop("thepearl", "thePearl", "5114464")
KAIROI_THEQUINCI = _kairoi_prop("thequinci", "theQuinci", "5286878")

# =============================================================================
# All Properties Registry
# =============================================================================

ALL_PROPERTIES = {
    "7_east": KAIROI_7_EAST,
    "aspire_7th_grant": KAIROI_ASPIRE,
    "block_44": KAIROI_BLOCK_44,
    "broadleaf": KAIROI_BROADLEAF,
    "confluence": KAIROI_CONFLUENCE,
    "curate": KAIROI_CURATE,
    "discovery_kingwood": KAIROI_DISCOVERY,
    "eden_keller_ranch": KAIROI_EDEN,
    "edison_rino": KAIROI_EDISON,
    "harvest": KAIROI_HARVEST,
    "heights_interlocken": KAIROI_HEIGHTS,
    "izzy": KAIROI_IZZY,
    "kalaco": KAIROI_KALACO,
    "links_plum_creek": KAIROI_LINKS,
    "luna": KAIROI_LUNA,
    "nexus_east": KAIROI_NEXUS_EAST,
    "park_17": KAIROI_PARK17,
    "parkside": KAIROI_PARKSIDE,
    "pearl_lantana": KAIROI_PEARL_LANTANA,
    "ridian": KAIROI_RIDIAN,
    "slate": KAIROI_SLATE,
    "sloane": KAIROI_SLOANE,
    "station_riverfront": KAIROI_STATION,
    "stonewood": KAIROI_STONEWOOD,
    "ten50": KAIROI_TEN50,
    "the_alcott": KAIROI_THE_ALCOTT,
    "the_avant": KAIROI_THE_AVANT,
    "the_hunter": KAIROI_THE_HUNTER,
    "the_northern": KAIROI_THE_NORTHERN,
    "thepearl": KAIROI_THEPEARL,
    "thequinci": KAIROI_THEQUINCI,
}

# By PMS type
REALPAGE_PROPERTIES = {
    k: v for k, v in ALL_PROPERTIES.items() 
    if v.pms_config.pms_type == PMSSource.REALPAGE
}

YARDI_PROPERTIES = {
    k: v for k, v in ALL_PROPERTIES.items() 
    if v.pms_config.pms_type == PMSSource.YARDI
}

# Portfolio definitions
KAIROI_PORTFOLIO = PortfolioConfig(
    portfolio_id="kairoi",
    name="Kairoi Properties",
    properties=list(ALL_PROPERTIES.values())
)


def get_property(property_id: str) -> PropertyMapping:
    """Get property configuration by ID."""
    if property_id not in ALL_PROPERTIES:
        raise ValueError(f"Unknown property: {property_id}")
    return ALL_PROPERTIES[property_id]


def get_pms_config(property_id: str) -> PMSConfig:
    """Get PMS config for a property."""
    return get_property(property_id).pms_config


def list_all_properties() -> list[PropertyMapping]:
    """List all configured properties."""
    return list(ALL_PROPERTIES.values())


def list_realpage_properties() -> list[PropertyMapping]:
    """List RealPage properties only."""
    return list(REALPAGE_PROPERTIES.values())


def list_yardi_properties() -> list[PropertyMapping]:
    """List Yardi properties only."""
    return list(YARDI_PROPERTIES.values())
