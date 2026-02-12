"""
Standalone Google Reviews scraper using Playwright.
Scrapes all reviews + owner replies for PHH properties and saves to cache.
Run manually: python scrape_reviews.py [--headless]

The scraped data is saved to app/db/data/google_reviews_cache.json
and served by the /api/v2/properties/{id}/reviews endpoint.
"""
import asyncio
import json
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

CACHE_PATH = Path(__file__).parent / "app" / "db" / "data" / "google_reviews_cache.json"
PROFILE_DIR = "/tmp/gmaps_scraper_profile"

# PHH properties
PROPERTIES = {
    "parkside": {
        "name": "Parkside at Round Rock",
        "place_id": "ChIJkcLlpSzRRIYRQGZOXRDFlOA",
    },
    "nexus_east": {
        "name": "Nexus East Austin TX",
        "place_id": "ChIJfZfNu3G3RIYRhv4XJwGuYTw",
    },
}

MAX_SCROLL_ITERATIONS = 40


async def scrape_property(page, property_id: str, config: dict) -> dict:
    """Scrape all Google reviews for a single property using an existing page."""
    print(f"\n{'='*60}")
    print(f"Scraping: {config['name']} ({property_id})")
    print(f"{'='*60}")

    search_url = f'https://www.google.com/maps/search/{config["name"].replace(" ", "+")}+apartments'
    print(f"  URL: {search_url}")
    await page.goto(search_url, wait_until='domcontentloaded', timeout=30000)
    await asyncio.sleep(3)

    # Handle consent screen (first property only, cookie persists)
    consent = page.locator('button:has-text("Accept all")')
    if await consent.count() > 0:
        print("  Accepting consent...")
        await consent.first.click()
        await asyncio.sleep(5)

    title = await page.title()
    print(f"  Page: {title}")

    # Click first search result if on results list
    first_result = page.locator('a.hfpxzc')
    if await first_result.count() > 0:
        print("  Clicking search result...")
        await first_result.first.click()
        await asyncio.sleep(3)

    # Wait for Reviews tab (up to 15s)
    review_tab = page.locator('button[role="tab"]:has-text("Reviews")')
    for _ in range(15):
        if await review_tab.count() > 0:
            break
        await asyncio.sleep(1)

    if await review_tab.count() == 0:
        tabs = page.locator('button[role="tab"]')
        names = [await tabs.nth(i).inner_text() for i in range(await tabs.count())]
        print(f"  No Reviews tab! Visible tabs: {names}")
        return {"error": "No Reviews tab", "reviews": []}

    print("  Clicking Reviews tab...")
    await review_tab.click()
    await asyncio.sleep(3)

    # Get rating
    rating = None
    try:
        rating_el = page.locator('div.fontDisplayLarge')
        if await rating_el.count() > 0:
            rating = float(await rating_el.first.inner_text())
    except Exception:
        pass

    # Get total review count from star distribution
    google_review_count = 0
    try:
        star_labels = page.locator('[aria-label*="stars,"][aria-label*="reviews"]')
        for i in range(await star_labels.count()):
            al = await star_labels.nth(i).get_attribute('aria-label') or ''
            parts = al.split(',')
            if len(parts) >= 2:
                num = ''.join(c for c in parts[1] if c.isdigit())
                if num:
                    google_review_count += int(num)
        if google_review_count:
            print(f"  Total on Google: {google_review_count} reviews")
    except Exception:
        pass

    # Scroll to load all reviews
    scrollable = page.locator('div.m6QErb.DxyBCb.kA9KIf.dS8AEf')
    if await scrollable.count() == 0:
        scrollable = page.locator('div.m6QErb.DxyBCb')

    prev_count = 0
    stale_rounds = 0
    for i in range(MAX_SCROLL_ITERATIONS):
        current = await page.locator('div[data-review-id]').count()
        sys.stdout.write(f"\r  Scroll {i+1}: {current} reviews loaded")
        sys.stdout.flush()

        if current == prev_count:
            stale_rounds += 1
            if stale_rounds >= 4:
                break
        else:
            stale_rounds = 0
        prev_count = current

        if await scrollable.count() > 0:
            await scrollable.first.evaluate('el => el.scrollTop = el.scrollHeight')
        await asyncio.sleep(1.2)

    total_els = await page.locator('div[data-review-id]').count()
    print(f"\n  Loaded {total_els} reviews")

    # Expand all "More" buttons via JS (much faster than clicking each one)
    expanded = await page.evaluate('''() => {
        const btns = document.querySelectorAll("button.w8nwRe.kyuRq");
        btns.forEach(b => b.click());
        return btns.length;
    }''')
    if expanded:
        print(f"  Expanded {expanded} truncated reviews")
        await asyncio.sleep(1)

    # Parse ALL reviews in one batch JS call (orders of magnitude faster)
    print("  Parsing reviews via JS...")
    reviews = await page.evaluate('''() => {
        const results = [];
        document.querySelectorAll("div[data-review-id]").forEach(el => {
            const reviewId = el.getAttribute("data-review-id") || "";
            const authorEl = el.querySelector(".d4r55");
            const author = authorEl ? authorEl.innerText.trim() : "";
            const photoEl = el.querySelector("img.NBa7we");
            const authorPhoto = photoEl ? (photoEl.getAttribute("src") || "") : "";
            const ratingEl = el.querySelector('span[role="img"]');
            let rating = 0;
            if (ratingEl) {
                const label = ratingEl.getAttribute("aria-label") || "";
                const m = label.match(/(\\d+)/);
                if (m) rating = parseInt(m[1]);
            }
            const dateEl = el.querySelector(".rsqaWe");
            const dateText = dateEl ? dateEl.innerText.trim() : "";
            const textEl = el.querySelector(".wiI7pd");
            const text = textEl ? textEl.innerText.trim() : "";
            const respEl = el.querySelector(".CDe7pd");
            let hasResponse = false, responseText = null, responseDate = null;
            if (respEl) {
                hasResponse = true;
                responseText = respEl.innerText.trim();
                const rdEl = el.querySelector(".DZSIDd span");
                if (rdEl) responseDate = rdEl.innerText.trim();
            }
            results.push({
                author, author_photo: authorPhoto, author_url: "",
                rating, text, time_desc: dateText,
                publish_time: "", google_maps_uri: "",
                review_id: reviewId, has_response: hasResponse,
                response_text: responseText, response_date: responseDate,
                response_time: null
            });
        });
        return results;
    }''')
    # Deduplicate — Google Maps loads reviews twice during scrolling
    seen = set()
    unique = []
    for r in reviews:
        rid = r["review_id"]
        if rid and rid not in seen:
            seen.add(rid)
            unique.append(r)
    if len(unique) < len(reviews):
        print(f"  Deduped: {len(reviews)} → {len(unique)} (removed {len(reviews)-len(unique)} duplicates)")
    reviews = unique

    # Metrics
    star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    responded = not_responded = 0
    for r in reviews:
        s = r["rating"]
        if s in star_counts:
            star_counts[s] += 1
        if r["has_response"]:
            responded += 1
        else:
            not_responded += 1

    total = len(reviews)
    response_rate = round((responded / total) * 100, 1) if total else 0
    needs_response = sum(1 for r in reviews if not r["has_response"] and r["rating"] <= 3)

    result = {
        "rating": rating,
        "review_count": google_review_count or total,
        "place_id": config.get("place_id", ""),
        "google_maps_url": f"https://www.google.com/maps/place/?q=place_id:{config.get('place_id', '')}",
        "reviews": reviews,
        "star_distribution": star_counts,
        "reviews_fetched": total,
        "responded": responded,
        "not_responded": not_responded,
        "needs_response": needs_response,
        "response_rate": response_rate,
        "avg_response_hours": None,
        "avg_response_label": None,
        "source": "playwright",
    }

    print(f"\n  {config['name']}: {rating}★ | {total} scraped | "
          f"{responded} replied ({response_rate}%) | {needs_response} need attention")
    print(f"  Stars: {star_counts}")
    return result


async def main():
    headless = '--headless' in sys.argv
    mode = "HEADLESS" if headless else "VISIBLE (Chrome will open)"
    print(f"Google Reviews Scraper — {mode}")
    print(f"Properties: {', '.join(PROPERTIES.keys())}\n")

    cache = {}
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text())
        except Exception:
            pass

    async with async_playwright() as p:
        # Persistent context avoids Google's automation detection
        ctx = await p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=headless,
            channel='chrome',
            locale='en-US',
            args=['--disable-blink-features=AutomationControlled'],
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # Stealth: hide webdriver flag
        await page.add_init_script('''
            Object.defineProperty(navigator, "webdriver", {get: () => undefined});
            window.chrome = {runtime: {}};
        ''')

        for pid, config in PROPERTIES.items():
            try:
                result = await scrape_property(page, pid, config)
                if result.get("reviews"):
                    cache[pid] = {"ts": time.time(), "data": result}
                else:
                    print(f"  No reviews for {pid}, keeping old cache")
            except Exception as e:
                print(f"  ERROR scraping {pid}: {e}")
                import traceback
                traceback.print_exc()

        await ctx.close()

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))
    print(f"\nCache saved to {CACHE_PATH}")
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
