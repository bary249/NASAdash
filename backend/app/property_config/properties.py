"""
Property Configuration - Maps properties to their PMS systems.
READ-ONLY: This configuration is for data retrieval only.
"""
from app.models.unified import PMSSource, PMSConfig, PropertyMapping, PortfolioConfig
from app.config import get_settings

settings = get_settings()

# =============================================================================
# Kairoi Properties (RealPage)
# =============================================================================

KAIROI_NEXUS_EAST = PropertyMapping(
    unified_id="kairoi-nexus-east",
    name="Nexus East",
    pms_config=PMSConfig(
        pms_type=PMSSource.REALPAGE,
        property_id="kairoi-nexus-east",
        realpage_pmcid="4248314",
        realpage_siteid="5472172",
        realpage_licensekey=settings.realpage_licensekey,
    )
)

KAIROI_PARKSIDE = PropertyMapping(
    unified_id="kairoi-parkside",
    name="Parkside at Round Rock",
    pms_config=PMSConfig(
        pms_type=PMSSource.REALPAGE,
        property_id="kairoi-parkside",
        realpage_pmcid="4248314",
        realpage_siteid="5536211",
        realpage_licensekey=settings.realpage_licensekey,
    )
)

KAIROI_RIDIAN = PropertyMapping(
    unified_id="kairoi-ridian",
    name="Ridian",
    pms_config=PMSConfig(
        pms_type=PMSSource.REALPAGE,
        property_id="kairoi-ridian",
        realpage_pmcid="4248314",
        realpage_siteid="5446271",
        realpage_licensekey=settings.realpage_licensekey,
    )
)

KAIROI_THE_NORTHERN = PropertyMapping(
    unified_id="kairoi-the-northern",
    name="The Northern",
    pms_config=PMSConfig(
        pms_type=PMSSource.REALPAGE,
        property_id="kairoi-the-northern",
        realpage_pmcid="4248314",
        realpage_siteid="5375283",
        realpage_licensekey=settings.realpage_licensekey,
    )
)

# =============================================================================
# Yardi Properties (existing)
# =============================================================================

YARDI_DEFAULT = PropertyMapping(
    unified_id="venn00",
    name="Venn Default Property",
    pms_config=PMSConfig(
        pms_type=PMSSource.YARDI,
        property_id="venn00",
        yardi_property_id="venn00",
    )
)

# =============================================================================
# All Properties Registry
# =============================================================================

ALL_PROPERTIES = {
    "kairoi-nexus-east": KAIROI_NEXUS_EAST,
    "kairoi-parkside": KAIROI_PARKSIDE,
    "kairoi-ridian": KAIROI_RIDIAN,
    "kairoi-the-northern": KAIROI_THE_NORTHERN,
    "venn00": YARDI_DEFAULT,
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
    properties=[KAIROI_NEXUS_EAST, KAIROI_PARKSIDE, KAIROI_RIDIAN, KAIROI_THE_NORTHERN]
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
