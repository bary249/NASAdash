"""
Configuration settings for Owner Dashboard V2.
"""
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Yardi PMS Credentials
    yardi_username: str = ""
    yardi_password: str = ""
    yardi_server_name: str = ""
    yardi_database: str = ""
    yardi_platform: str = "SQL Server"
    
    # Resident Data Interface (for unit info, residents)
    yardi_interface_entity: str = ""
    yardi_interface_license: str = ""
    
    # ILS/Guest Card Interface (for leasing funnel, prospects)
    yardi_ils_interface_entity: str = ""
    yardi_ils_interface_license: str = ""
    
    # Yardi API URLs
    yardi_resident_url: str = ""
    yardi_ils_url: str = ""
    yardi_common_url: str = ""
    
    # Default Property
    yardi_default_property_id: str = ""
    
    # ALN API
    aln_api_key: str = ""
    aln_base_url: str = "https://odata4.alndata.com"
    
    # RealPage RPX Gateway
    realpage_url: str = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
    realpage_pmcid: str = ""
    realpage_siteid: str = ""
    realpage_licensekey: str = ""
    
    # Google Places API
    google_places_api_key: str = ""
    
    # SerpAPI (for Google Reviews scraping)
    serpapi_api_key: str = ""
    
    # Claude AI API
    anthropic_api_key: str = ""
    
    # Zembra API (Apartments.com reviews)
    zembra_api_key: str = ""
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
