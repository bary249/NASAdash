"""
Google Places API service for property ratings and reviews.
Uses Places API (New) Text Search to find properties and cache results.
READ-ONLY: Only fetches public data from Google.
"""
import json
import logging
import time
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

# Cache file — ratings don't change often, cache for 24h
from app.db.schema import DB_DIR
CACHE_PATH = DB_DIR / "google_places_cache.json"
CACHE_TTL_SECONDS = 86400  # 24 hours


def _load_cache() -> dict:
    if CACHE_PATH.exists():
        try:
            return json.loads(CACHE_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_cache(cache: dict):
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        CACHE_PATH.write_text(json.dumps(cache, indent=2))
    except Exception as e:
        logger.warning(f"[GOOGLE] Failed to save cache: {e}")


async def lookup_property_rating(
    property_name: str,
    city: str = "",
    state: str = "",
) -> Optional[dict]:
    """
    Look up a property on Google Places and return rating info.
    Returns: {"rating": float, "review_count": int, "place_id": str} or None.
    """
    settings = get_settings()
    api_key = settings.google_places_api_key
    if not api_key:
        return None

    # Build search query
    query = f"{property_name} apartments"
    if city:
        query += f" {city}"
    if state:
        query += f" {state}"

    # Check cache
    cache = _load_cache()
    cache_key = query.lower().strip()
    if cache_key in cache:
        entry = cache[cache_key]
        if time.time() - entry.get("cached_at", 0) < CACHE_TTL_SECONDS:
            logger.debug(f"[GOOGLE] Cache hit for '{property_name}'")
            return entry.get("data")

    # Call Google Places API (New) — Text Search
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount,places.id,places.formattedAddress",
    }
    body = {
        "textQuery": query,
        "maxResultCount": 1,
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json=body, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        places = data.get("places", [])
        if not places:
            logger.info(f"[GOOGLE] No results for '{query}'")
            # Cache the miss too
            cache[cache_key] = {"cached_at": time.time(), "data": None}
            _save_cache(cache)
            return None

        place = places[0]
        result = {
            "rating": place.get("rating"),
            "review_count": place.get("userRatingCount", 0),
            "place_id": place.get("id", ""),
            "address": place.get("formattedAddress", ""),
        }

        # Cache it
        cache[cache_key] = {"cached_at": time.time(), "data": result}
        _save_cache(cache)

        logger.info(f"[GOOGLE] Found '{property_name}': rating={result['rating']}, reviews={result['review_count']}")
        return result

    except Exception as e:
        logger.warning(f"[GOOGLE] API error for '{query}': {e}")
        return None


async def get_all_property_ratings() -> dict[str, dict]:
    """
    Look up ratings for all configured properties.
    Returns: {property_id: {"rating": float, "review_count": int, ...}}
    """
    from app.property_config.properties import ALL_PROPERTIES
    import sqlite3

    # Get city/state from unified.db for better search accuracy
    prop_locations = {}
    try:
        db_path = Path(__file__).parent.parent / "db" / "data" / "unified.db"
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT unified_property_id, city, state FROM unified_properties")
        for row in cursor.fetchall():
            prop_locations[row[0]] = {"city": row[1] or "", "state": row[2] or ""}
        conn.close()
    except Exception:
        pass

    results = {}
    for prop_id, prop in ALL_PROPERTIES.items():
        loc = prop_locations.get(prop_id, {})
        data = await lookup_property_rating(
            prop.name,
            city=loc.get("city", ""),
            state=loc.get("state", ""),
        )
        if data and data.get("rating"):
            results[prop_id] = data

    return results
