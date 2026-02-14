"""
Google Reviews Service - Fetch and cache Google Place reviews for properties.
Uses SerpAPI (preferred, full reviews + owner replies) or Google Places API (fallback, 5 reviews only).
READ-ONLY.
"""
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)

CACHE_PATH = Path(__file__).parent.parent / "db" / "data" / "google_places_cache.json"
REVIEWS_CACHE_PATH = Path(__file__).parent.parent / "db" / "data" / "google_reviews_cache.json"
REVIEWS_CACHE_TTL = 43200  # 12 hours
MAX_SERPAPI_PAGES = 5  # Up to ~40 reviews (8 first page + 10-20 per page after)


def _load_reviews_cache() -> dict:
    if REVIEWS_CACHE_PATH.exists():
        try:
            return json.loads(REVIEWS_CACHE_PATH.read_text())
        except Exception:
            return {}
    return {}


def _save_reviews_cache(cache: dict):
    try:
        REVIEWS_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        REVIEWS_CACHE_PATH.write_text(json.dumps(cache, indent=2))
    except Exception as e:
        logger.warning(f"[REVIEWS] Failed to save cache: {e}")


def _get_place_id(property_id: str) -> Optional[str]:
    """Get cached place_id for a property from the places cache."""
    if not CACHE_PATH.exists():
        return None
    try:
        cache = json.loads(CACHE_PATH.read_text())
        from app.property_config.properties import ALL_PROPERTIES
        prop = ALL_PROPERTIES.get(property_id)
        if not prop:
            return None
        for key, entry in cache.items():
            data = entry.get("data")
            if not data:
                continue
            if prop.name.lower() in key.lower():
                return data.get("place_id")
        return None
    except Exception:
        return None


async def get_property_reviews(property_id: str) -> dict:
    """
    Fetch reviews. Data sources (in priority order):
    1. Playwright cache (populated by scrape_reviews.py — full data, owner replies)
    2. SerpAPI (if configured + paid plan)
    3. Google Places API fallback (5 reviews, no replies)
    
    Playwright data is authoritative — never overwrite it with degraded API data.
    Expired Playwright data is still returned (stale > empty).
    """
    cache = _load_reviews_cache()
    existing_entry = cache.get(property_id)
    existing_data = existing_entry.get("data", {}) if existing_entry else {}
    existing_source = existing_data.get("source", "")
    existing_review_count = existing_data.get("review_count", 0)
    is_expired = existing_entry and (time.time() - existing_entry.get("ts", 0) >= REVIEWS_CACHE_TTL)

    # Valid (non-expired) cache → return immediately
    if existing_entry and not is_expired:
        return existing_data

    # Expired Playwright data → still return it (stale > empty).
    # Don't try API fallbacks that will return degraded data.
    if existing_entry and existing_source == "playwright" and existing_review_count > 10:
        logger.info(f"[REVIEWS] Returning stale Playwright data for {property_id} ({existing_review_count} reviews). Re-run scrape_reviews.py to refresh.")
        return existing_data

    place_id = _get_place_id(property_id)
    if not place_id:
        if existing_entry:
            return existing_data  # Return whatever we have
        return {"error": "Property not found in Google Places", "reviews": [], "source": "none"}

    settings = get_settings()

    # Try SerpAPI (full reviews + owner replies) — requires paid plan
    if settings.serpapi_api_key:
        result = await _fetch_serpapi(property_id, place_id, settings.serpapi_api_key)
        if result and not result.get("error"):
            new_count = result.get("review_count", 0)
            # Only save if it has more data than existing cache
            if new_count >= existing_review_count:
                cache[property_id] = {"ts": time.time(), "data": result}
                _save_reviews_cache(cache)
            return result

    # Fallback: Google Places API (5 reviews, no replies)
    if settings.google_places_api_key:
        result = await _fetch_google_places(property_id, place_id, settings.google_places_api_key)
        if result:
            new_count = result.get("review_count", 0)
            if new_count >= existing_review_count:
                cache[property_id] = {"ts": time.time(), "data": result}
                _save_reviews_cache(cache)
            return result

    # Nothing worked — return stale cache if available
    if existing_entry:
        return existing_data

    return {"error": "No review data. Run scrape_reviews.py or configure API keys.", "reviews": []}


async def _fetch_serpapi(property_id: str, place_id: str, api_key: str) -> Optional[dict]:
    """Fetch reviews from SerpAPI with pagination. Returns all reviews + owner replies."""
    all_reviews = []
    place_info = {}
    next_page_token = None

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            for page in range(MAX_SERPAPI_PAGES):
                params = {
                    "engine": "google_maps_reviews",
                    "place_id": place_id,
                    "api_key": api_key,
                    "hl": "en",
                    "sort_by": "newestFirst",
                }
                if next_page_token:
                    params["next_page_token"] = next_page_token

                resp = await client.get("https://serpapi.com/search.json", params=params)
                resp.raise_for_status()
                data = resp.json()

                if page == 0:
                    place_info = data.get("place_info", {})

                for r in data.get("reviews", []):
                    response_data = r.get("response")
                    all_reviews.append({
                        "author": r.get("user", {}).get("name", "Anonymous"),
                        "author_photo": r.get("user", {}).get("thumbnail", ""),
                        "author_url": r.get("user", {}).get("link", ""),
                        "rating": r.get("rating", 0),
                        "text": r.get("snippet", ""),
                        "time_desc": r.get("date", ""),
                        "publish_time": r.get("iso_date", ""),
                        "google_maps_uri": r.get("link", ""),
                        "review_id": r.get("review_id", ""),
                        "has_response": response_data is not None,
                        "response_text": response_data.get("snippet", "") if response_data else None,
                        "response_date": response_data.get("date", "") if response_data else None,
                        "response_time": response_data.get("iso_date", "") if response_data else None,
                    })

                # Check for next page
                pagination = data.get("serpapi_pagination", {})
                next_page_token = pagination.get("next_page_token")
                if not next_page_token:
                    break

        # Calculate metrics
        star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        responded = 0
        not_responded = 0
        response_times_hours = []

        for r in all_reviews:
            star = int(r["rating"])
            star_counts[star] = star_counts.get(star, 0) + 1

            if r["has_response"]:
                responded += 1
                # Calculate response time if we have both dates
                if r.get("publish_time") and r.get("response_time"):
                    try:
                        pub = datetime.fromisoformat(r["publish_time"].replace("Z", "+00:00"))
                        res = datetime.fromisoformat(r["response_time"].replace("Z", "+00:00"))
                        diff_hours = (res - pub).total_seconds() / 3600
                        if diff_hours > 0:
                            response_times_hours.append(diff_hours)
                    except Exception:
                        pass
            else:
                not_responded += 1

        total = len(all_reviews)
        response_rate = round((responded / total) * 100, 1) if total > 0 else 0
        avg_response_hours = round(sum(response_times_hours) / len(response_times_hours), 1) if response_times_hours else None

        # Format avg response time as human-readable
        avg_response_label = None
        if avg_response_hours is not None:
            if avg_response_hours < 24:
                avg_response_label = f"{int(avg_response_hours)}h"
            else:
                avg_response_label = f"{round(avg_response_hours / 24, 1)}d"

        result = {
            "rating": place_info.get("rating"),
            "review_count": place_info.get("reviews", 0),
            "place_id": place_id,
            "google_maps_url": f"https://www.google.com/maps/place/?q=place_id:{place_id}",
            "reviews": all_reviews,
            "star_distribution": star_counts,
            "reviews_fetched": total,
            "responded": responded,
            "not_responded": not_responded,
            "needs_response": sum(1 for r in all_reviews if not r["has_response"] and r["rating"] <= 3),
            "response_rate": response_rate,
            "avg_response_hours": avg_response_hours,
            "avg_response_label": avg_response_label,
            "source": "serpapi",
        }

        logger.info(f"[REVIEWS] SerpAPI: {total} reviews for {property_id} "
                     f"(rating={place_info.get('rating')}, responded={responded}/{total}={response_rate}%)")
        return result

    except Exception as e:
        logger.error(f"[REVIEWS] SerpAPI error for {property_id}: {e}")
        return None


async def _fetch_google_places(property_id: str, place_id: str, api_key: str) -> Optional[dict]:
    """Fallback: fetch 5 reviews from Google Places API (no owner replies)."""
    url = f"https://places.googleapis.com/v1/places/{place_id}"
    headers = {
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "rating,userRatingCount,reviews,googleMapsUri",
    }

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        reviews = []
        star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

        for r in data.get("reviews", []):
            star = r.get("rating", 0)
            star_counts[star] = star_counts.get(star, 0) + 1
            author = r.get("authorAttribution", {})
            reviews.append({
                "author": author.get("displayName", "Anonymous"),
                "author_photo": author.get("photoUri", ""),
                "author_url": author.get("uri", ""),
                "rating": star,
                "text": r.get("text", {}).get("text", ""),
                "time_desc": r.get("relativePublishTimeDescription", ""),
                "publish_time": r.get("publishTime", ""),
                "google_maps_uri": r.get("googleMapsUri", ""),
                "has_response": False,
                "response_text": None,
                "response_date": None,
                "response_time": None,
            })

        return {
            "rating": data.get("rating"),
            "review_count": data.get("userRatingCount", 0),
            "place_id": place_id,
            "google_maps_url": data.get("googleMapsUri", ""),
            "reviews": reviews,
            "star_distribution": star_counts,
            "reviews_fetched": len(reviews),
            "responded": 0,
            "not_responded": len(reviews),
            "needs_response": sum(1 for r in reviews if r["rating"] <= 3),
            "response_rate": 0,
            "avg_response_hours": None,
            "avg_response_label": None,
            "source": "google_places",
        }

    except Exception as e:
        logger.error(f"[REVIEWS] Google Places error for {property_id}: {e}")
        return None
