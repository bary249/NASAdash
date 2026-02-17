#!/usr/bin/env python3
"""
Unified review fetcher — Google + Apartments.com via Zembra API.
No browser needed. Runs in GH Actions.

Usage:
    python fetch_all_reviews.py                # Fetch all
    python fetch_all_reviews.py --only google  # Google only
    python fetch_all_reviews.py --only apartments  # Apartments.com only
    python fetch_all_reviews.py --check        # Check Zembra balance only

Env: ZEMBRA_API_KEY
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
load_dotenv(SCRIPT_DIR / ".env")

from app.db.schema import DB_DIR
GOOGLE_CACHE = DB_DIR / "google_reviews_cache.json"
APARTMENTS_CACHE = DB_DIR / "apartments_reviews_cache.json"

API_BASE = "https://api.zembra.io"
API_KEY = os.environ.get("ZEMBRA_API_KEY", "")
if not API_KEY:
    print("ERROR: Set ZEMBRA_API_KEY in .env or environment")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

# Skip external calls when cache is still fresh (default: 12h)
REVIEWS_CACHE_TTL = int(os.environ.get("ZEMBRA_REVIEWS_CACHE_TTL_SECONDS", "43200"))

# ─── Property registry ───────────────────────────────────────────────────────
# Google: network="google", slug = Google Maps CID (from place URL)
# Apartments: network="apartments", slug = URL path
PROPERTIES = {
    "parkside": {
        "name": "Parkside at Round Rock",
        "google_slug": "ChIJkcLlpSzRRIYRQGZOXRDFlOA",
        "apartments_slug": "parkside-at-round-rock-round-rock-tx/xe8kehq",
    },
    "nexus_east": {
        "name": "Nexus East",
        "google_slug": "ChIJfZfNu3G3RIYRhv4XJwGuYTw",
        "apartments_slug": "nexus-east-austin-tx/nbnfysp",
    },
}


def check_balance():
    """Check Zembra account balance."""
    resp = SESSION.get(f"{API_BASE}/account", timeout=20)
    if resp.status_code == 200:
        data = resp.json()
        balance = data.get("data", {}).get("balance", "?")
        print(f"  Zembra balance: {balance} credits")
        return balance
    else:
        print(f"  ERROR checking balance: {resp.status_code}")
        return None


def create_review_job(network: str, slug: str) -> dict:
    """Create a review job. Returns job info + target metadata."""
    resp = SESSION.post(f"{API_BASE}/reviews", json={
        "network": network,
        "slug": slug,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "SUCCESS":
        raise RuntimeError(f"Zembra error: {data.get('message', data)}")
    return data


def get_reviews(job_id: str, max_attempts: int = 6) -> list:
    """Fetch all reviews for a job. Polls until ready with backoff."""
    for attempt in range(max_attempts):
        resp = SESSION.get(f"{API_BASE}/reviews", params={"jobId": job_id}, timeout=30)
        if resp.status_code not in (200, 206):
            resp.raise_for_status()
        data = resp.json()
        reviews = data.get("data", {}).get("reviews", [])
        if reviews:
            return reviews

        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                sleep_s = float(retry_after)
            except ValueError:
                sleep_s = 0.0
        else:
            # Exponential backoff to reduce polling pressure
            sleep_s = min(2 * (2 ** attempt), 20)

        print(f"  Waiting for reviews (attempt {attempt + 1}/{max_attempts}, sleep {sleep_s:.1f}s)...")
        time.sleep(sleep_s)
    return []


def _is_fresh_cache_entry(entry: Optional[dict], ttl_seconds: int = REVIEWS_CACHE_TTL) -> bool:
    if not entry:
        return False
    ts = entry.get("ts", 0)
    data = entry.get("data", {})
    if not ts or not isinstance(data, dict):
        return False
    # Fresh only if payload is present and has at least summary fields
    has_payload = data.get("review_count", 0) > 0 or len(data.get("reviews", [])) > 0
    return has_payload and (time.time() - ts) < ttl_seconds


def process_reviews(reviews: list, source: str) -> dict:
    """Compute metrics from raw Zembra reviews."""
    star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    responded = 0
    processed = []

    for r in reviews:
        rating = r.get("rating", 0)
        if isinstance(rating, (int, float)) and int(rating) in star_counts:
            star_counts[int(rating)] += 1

        replies = r.get("replies", [])
        has_response = len(replies) > 0
        if has_response:
            responded += 1

        processed.append({
            "review_id": r.get("id", ""),
            "author": r.get("author", {}).get("name", "Anonymous"),
            "rating": rating,
            "text": r.get("text", ""),
            "time_desc": r.get("timestamp", ""),
            "has_response": has_response,
            "response_text": replies[0].get("text", "") if replies else None,
            "response_date": replies[0].get("timestamp", "") if replies else None,
        })

    total = len(processed)
    response_rate = round((responded / total) * 100, 1) if total else 0
    needs_response = sum(1 for r in processed if not r["has_response"] and r["rating"] <= 3)

    return {
        "reviews": processed,
        "star_distribution": star_counts,
        "reviews_fetched": total,
        "responded": responded,
        "not_responded": total - responded,
        "needs_response": needs_response,
        "response_rate": response_rate,
        "source": f"zembra/{source}",
    }


def fetch_for_network(network: str, slug_key: str, cache_path: Path, force_refresh: bool = False):
    """Fetch reviews for all properties on a given network."""
    print(f"\n{'='*60}")
    print(f"  FETCHING: {network.upper()} REVIEWS")
    print(f"{'='*60}")

    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text())
        except Exception:
            pass

    for pid, config in PROPERTIES.items():
        slug = config.get(slug_key)
        if not slug:
            print(f"  {pid}: No {slug_key} configured, skipping")
            continue

        existing = cache.get(pid)
        if not force_refresh and _is_fresh_cache_entry(existing):
            age_mins = int((time.time() - existing.get("ts", 0)) / 60)
            print(f"\n  {config['name']} ({pid})")
            print(f"  cache: fresh ({age_mins}m old) -> skipping Zembra calls")
            continue

        print(f"\n  {config['name']} ({pid})")
        print(f"  slug: {slug}")

        try:
            result = create_review_job(network, slug)
            job = result["data"]["job"]
            target = result["data"]["target"]
            job_id = job["jobId"]
            rating = target.get("globalRating")
            review_count = target.get("reviewCount", {}).get("native", {}).get("total", 0)
            cost = result.get("cost", 0)
            balance = result.get("balance", "?")
            print(f"  Rating: {rating}★, Total: {review_count}, Cost: {cost} credits, Balance: {balance}")

            time.sleep(2)
            reviews = get_reviews(job_id)
            print(f"  Fetched: {len(reviews)} reviews")

            metrics = process_reviews(reviews, network)
            metrics["rating"] = rating
            metrics["review_count"] = review_count
            metrics["zembra_job_id"] = job_id

            # Capture property image from target metadata (Google has profileImage)
            profile_image = target.get("profileImage")
            if profile_image:
                metrics["profile_image"] = profile_image
                print(f"  Profile image: {profile_image[:80]}...")

            if network == "apartments":
                slug_parts = slug.split("/")
                metrics["url"] = f"https://www.apartments.com/{slug_parts[0]}/{slug_parts[-1]}/"

            cache[pid] = {"ts": time.time(), "data": metrics}

            print(f"  Stars: {metrics['star_distribution']}")
            print(f"  Responded: {metrics['responded']}/{metrics['reviews_fetched']} ({metrics['response_rate']}%)")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(cache, indent=2, ensure_ascii=False))
    print(f"\n  Cache saved to {cache_path}")


def main():
    print("Unified Review Fetcher (Zembra API)")
    print(f"Properties: {', '.join(PROPERTIES.keys())}")

    only = None
    force_refresh = "--force" in sys.argv
    if "--only" in sys.argv:
        idx = sys.argv.index("--only")
        if idx + 1 < len(sys.argv):
            only = sys.argv[idx + 1]

    if "--check" in sys.argv:
        check_balance()
        return

    check_balance()

    if only is None or only == "google":
        fetch_for_network("google", "google_slug", GOOGLE_CACHE, force_refresh=force_refresh)

    if only is None or only == "apartments":
        fetch_for_network("apartments", "apartments_slug", APARTMENTS_CACHE, force_refresh=force_refresh)

    print(f"\n{'='*60}")
    print("  DONE")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
