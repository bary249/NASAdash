"""
Apartments.com Reviews Service — reads from Zembra API cache.
Cache is populated by running: python3 fetch_apartments_reviews.py
"""
import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

from app.db.schema import DB_DIR
CACHE_PATH = DB_DIR / "apartments_reviews_cache.json"

# Map unified property_id → apartments cache key
PROPERTY_MAP = {
    "parkside": "parkside",
    "5536211": "parkside",
    "nexus_east": "nexus_east",
    "5472172": "nexus_east",
}


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except Exception:
            return {}
    return {}


def get_apartments_reviews(property_id: str) -> Optional[dict]:
    """Get Apartments.com reviews for a property from the Zembra cache."""
    cache = _load_cache()
    
    # Try direct match first, then mapped key
    cache_key = PROPERTY_MAP.get(property_id, property_id)
    entry = cache.get(cache_key)
    
    if not entry:
        # Try case-insensitive / partial match
        pid_lower = property_id.lower()
        for key in cache:
            if key.lower() == pid_lower or pid_lower in key.lower():
                entry = cache[key]
                break
    
    if not entry:
        return None
    
    data = entry.get("data", {})
    if not data:
        return None
    
    return data
