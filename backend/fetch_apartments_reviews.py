"""
Fetch Apartments.com reviews via Zembra API and cache locally.
Run: python3 fetch_apartments_reviews.py

Flow:
1. POST /reviews — creates a review job (or reuses existing)
2. GET /reviews?jobId=... — fetches all reviews for the job
3. Saves to apartments_reviews_cache.json

Costs ~63-113 credits per property on first call, free on subsequent fetches.
"""
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests

CACHE_PATH = Path(__file__).parent / "app" / "db" / "data" / "apartments_reviews_cache.json"
API_BASE = "https://api.zembra.io"
API_KEY = os.environ.get("ZEMBRA_API_KEY", "")
if not API_KEY:
    # Try loading from .env file
    env_path = Path(__file__).parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith("ZEMBRA_API_KEY="):
                API_KEY = line.split("=", 1)[1].strip()
                break
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

# PHH properties — network=apartments, slug from URL
PROPERTIES = {
    "parkside": {
        "name": "Parkside at Round Rock",
        "network": "apartments",
        "slug": "parkside-at-round-rock-round-rock-tx/xe8kehq",
    },
    "nexus_east": {
        "name": "Nexus East",
        "network": "apartments",
        "slug": "nexus-east-austin-tx/nbnfysp",
    },
}


def create_review_job(network: str, slug: str) -> dict:
    """Create a review job. Returns job info + target metadata."""
    resp = SESSION.post(f"{API_BASE}/reviews", json={
        "network": network,
        "slug": slug,
    }, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") != "SUCCESS":
        raise RuntimeError(f"Zembra error: {data.get('message')}")
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
    has_payload = data.get("review_count", 0) > 0 or len(data.get("reviews", [])) > 0
    return has_payload and (time.time() - ts) < ttl_seconds


def process_reviews(reviews: list) -> dict:
    """Compute metrics from raw Zembra reviews."""
    star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    responded = 0
    processed = []

    for r in reviews:
        rating = r.get("rating", 0)
        if rating in star_counts:
            star_counts[rating] += 1

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
        "source": "zembra/apartments.com",
    }


def main():
    print("Apartments.com Reviews Fetcher (via Zembra API)")
    print(f"Properties: {', '.join(PROPERTIES.keys())}\n")

    cache = {}
    force_refresh = "--force" in sys.argv
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text())
        except Exception:
            pass

    for pid, config in PROPERTIES.items():
        existing = cache.get(pid)
        if not force_refresh and _is_fresh_cache_entry(existing):
            age_mins = int((time.time() - existing.get("ts", 0)) / 60)
            print(f"{'='*50}")
            print(f"  {config['name']} ({pid})")
            print(f"{'='*50}")
            print(f"  cache: fresh ({age_mins}m old) -> skipping Zembra calls")
            continue

        print(f"{'='*50}")
        print(f"  {config['name']} ({pid})")
        print(f"{'='*50}")

        try:
            # Step 1: Create job
            result = create_review_job(config["network"], config["slug"])
            job = result["data"]["job"]
            target = result["data"]["target"]
            job_id = job["jobId"]
            rating = target.get("globalRating")
            review_count = target.get("reviewCount", {}).get("native", {}).get("total", 0)
            print(f"  Job: {job_id}")
            print(f"  Rating: {rating}★, Total reviews: {review_count}")
            print(f"  Cost: {result.get('cost')} credits, Balance: {result.get('balance')}")

            # Step 2: Fetch reviews
            time.sleep(2)
            reviews = get_reviews(job_id)
            print(f"  Fetched: {len(reviews)} reviews")

            # Step 3: Process
            metrics = process_reviews(reviews)
            metrics["rating"] = rating
            metrics["review_count"] = review_count
            metrics["url"] = f"https://www.apartments.com/{config['slug'].split('/')[0]}/{config['slug'].split('/')[-1]}/"
            metrics["zembra_job_id"] = job_id

            cache[pid] = {"ts": time.time(), "data": metrics}

            print(f"  Stars: {metrics['star_distribution']}")
            print(f"  Responded: {metrics['responded']}/{metrics['reviews_fetched']} ({metrics['response_rate']}%)")
            print(f"  Needs attention: {metrics['needs_response']}")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))
    print(f"\nCache saved to {CACHE_PATH}")
    print("Done!")


if __name__ == "__main__":
    main()
