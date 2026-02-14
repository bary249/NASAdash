"""
Apartments.com Reviews scraper using Playwright.
Scrapes ratings + reviews for PHH properties and saves to cache.
Run manually: python scrape_apartments_reviews.py [--headless]

The scraped data is saved to app/db/data/apartments_reviews_cache.json
and served by the /api/v2/properties/{id}/reviews endpoint (source=apartments).
"""
import asyncio
import json
import random
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

CACHE_PATH = Path(__file__).parent / "app" / "db" / "data" / "apartments_reviews_cache.json"
PROFILE_DIR = "/tmp/apartments_scraper_profile_v2"

# PHH properties — slug is from the apartments.com URL
PROPERTIES = {
    "parkside": {
        "name": "Parkside at Round Rock",
        "url": "https://www.apartments.com/parkside-at-round-rock-round-rock-tx/xe8kehq/",
    },
    "nexus_east": {
        "name": "Nexus East",
        "url": "https://www.apartments.com/nexus-east-austin-tx/nbnfysp/",
    },
}

MAX_SCROLL_ITERATIONS = 15


async def human_delay(min_s=1.0, max_s=3.0):
    """Random delay to simulate human browsing."""
    await asyncio.sleep(random.uniform(min_s, max_s))


async def scrape_property(page, property_id: str, config: dict) -> dict:
    """Scrape all Apartments.com reviews for a single property."""
    print(f"\n{'='*60}")
    print(f"Scraping: {config['name']} ({property_id})")
    print(f"{'='*60}")

    url = config["url"]
    print(f"  URL: {url}")
    await page.goto(url, wait_until='domcontentloaded', timeout=60000)
    await human_delay(3, 5)

    # Check if we got blocked
    title = await page.title()
    if 'access denied' in title.lower() or 'blocked' in title.lower():
        print(f"  BLOCKED by WAF: {title}")
        return {"error": "Blocked by WAF", "reviews": []}

    # ----- Overall rating -----
    rating = None
    review_count = 0
    try:
        rating_data = await page.evaluate('''() => {
            // Look for structured data first (most reliable)
            const scripts = document.querySelectorAll('script[type="application/ld+json"]');
            for (const s of scripts) {
                try {
                    const d = JSON.parse(s.textContent);
                    if (d.aggregateRating) return { rating: parseFloat(d.aggregateRating.ratingValue), count: parseInt(d.aggregateRating.reviewCount) || 0 };
                    if (d['@graph']) { for (const item of d['@graph']) { if (item.aggregateRating) return { rating: parseFloat(item.aggregateRating.ratingValue), count: parseInt(item.aggregateRating.reviewCount) || 0 }; } }
                } catch(e) {}
            }
            // Fallback: DOM
            const ratingEl = document.querySelector('.reviewRating .rating');
            const countEl = document.querySelector('.reviewCount');
            let rating = null, count = 0;
            if (ratingEl) rating = parseFloat(ratingEl.innerText.trim());
            if (countEl) { const m = countEl.innerText.match(/(\\d+)/); if (m) count = parseInt(m[1]); }
            return { rating, count };
        }''')
        rating = rating_data.get('rating')
        review_count = rating_data.get('count', 0)
        print(f"  Rating: {rating}★, Review count: {review_count}")
    except Exception as e:
        print(f"  Rating extraction error: {e}")

    # ----- Scroll down to reviews section naturally -----
    await page.evaluate('''() => {
        const el = document.querySelector('#reviews, .reviewsSection, [class*="reviewsSection"]');
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
    }''')
    await human_delay(1, 2)

    # Don't click "See all reviews" — it triggers Akamai WAF redirect.
    # Parse the initial reviews visible on the main property page instead.

    # ----- Parse reviews -----
    # propertyReviewRow is a SINGLE container; individual reviews are .reviewContainer inside it
    print("  Parsing reviews...")
    reviews = await page.evaluate('''() => {
        const results = [];
        // Individual review cards are .reviewContainer inside the review section
        let rows = document.querySelectorAll('.reviewContainer');
        
        // Fallback selectors
        if (rows.length === 0) rows = document.querySelectorAll('[class*="propertyReview"] > div > div');
        if (rows.length === 0) rows = document.querySelectorAll('.propertyReviewRow > div');
        
        for (const row of rows) {
            const fullText = row.innerText?.trim() || '';
            // Skip very short or tooltip-like elements
            if (fullText.length < 30 || fullText.includes('How Is This Rating')) continue;
            
            // ----- Rating -----
            let rating = 0;
            // Count filled/active star SVGs or spans
            const starContainer = row.querySelector('[class*="star"], [class*="Star"]');
            if (starContainer) {
                // Look at aria-label first
                const ariaLabel = starContainer.getAttribute('aria-label') || '';
                const m = ariaLabel.match(/(\\d)/);
                if (m) rating = parseInt(m[1]);
            }
            // Method 2: count individual star elements that are "filled"
            if (!rating) {
                const allStarEls = row.querySelectorAll('svg, [class*="star"]');
                let filled = 0;
                for (const s of allStarEls) {
                    const cls = (s.getAttribute('class') || '') + ' ' + (s.getAttribute('fill') || '');
                    if (cls.includes('fill') || cls.includes('active') || cls.includes('colored') || cls.includes('#')) filled++;
                }
                if (filled > 0 && filled <= 5) rating = filled;
            }
            // Method 3: look for a numeric rating
            if (!rating) {
                const spans = row.querySelectorAll('span');
                for (const s of spans) {
                    const t = s.innerText?.trim();
                    if (t && /^[1-5]$/.test(t)) {
                        const cls = s.className || s.parentElement?.className || '';
                        if (cls.toLowerCase().includes('rating') || cls.toLowerCase().includes('star')) {
                            rating = parseInt(t);
                            break;
                        }
                    }
                }
            }
            
            // ----- Date -----
            let dateText = '';
            // Look for date-like text in spans
            const allSpans = row.querySelectorAll('span, time, div');
            for (const s of allSpans) {
                const t = s.innerText?.trim() || '';
                // Match "Month Day, Year" pattern
                if (/^(January|February|March|April|May|June|July|August|September|October|November|December)\\s+\\d{1,2},\\s+\\d{4}$/.test(t)) {
                    dateText = t;
                    break;
                }
            }
            
            // ----- Review text -----
            // Get the actual comment text (skip metadata)
            let reviewText = '';
            // Look for paragraph elements with actual review content
            const paras = row.querySelectorAll('p');
            for (const p of paras) {
                const t = p.innerText?.trim() || '';
                if (t.length > 20 && !t.includes('Submitted by') && !t.includes('How Is This')) {
                    if (t.length > reviewText.length) reviewText = t;
                }
            }
            // Fallback: get longest text block from divs
            if (!reviewText) {
                const divs = row.querySelectorAll('div');
                for (const d of divs) {
                    // Only direct text, not nested
                    if (d.children.length > 3) continue;
                    const t = d.innerText?.trim() || '';
                    if (t.length > 30 && t.length < 2000 && !t.includes('How Is This') && !t.includes('Submitted by')) {
                        if (t.length > reviewText.length) reviewText = t;
                    }
                }
            }
            
            if (!reviewText || reviewText.length < 20) continue;
            
            // ----- Management response -----
            let hasResponse = false, responseText = null;
            const respEl = row.querySelector('[class*="response"], [class*="Response"], [class*="reply"], [class*="Reply"], [class*="manager"]');
            if (respEl) {
                const rText = respEl.innerText?.trim();
                if (rText && rText.length > 10) {
                    hasResponse = true;
                    responseText = rText;
                    // Remove response text from reviewText if it got included
                    reviewText = reviewText.replace(rText, '').trim();
                }
            }
            
            results.push({
                author: '',  // Apartments.com anonymizes most reviewers
                rating,
                text: reviewText,
                time_desc: dateText,
                has_response: hasResponse,
                response_text: responseText,
            });
        }
        
        return results;
    }''')

    print(f"  Found {len(reviews)} reviews")

    if len(reviews) == 0:
        # Dump debug info
        debug = await page.evaluate('''() => {
            const info = {};
            const selectors = ['.reviewContainer', '.propertyReviewRow', '.renterReviewsWrapper', '#reviews'];
            for (const s of selectors) info[s] = document.querySelectorAll(s).length;
            // Get child elements of the review section
            const section = document.querySelector('.propertyReviewRow, #reviews, .renterReviewsWrapper');
            if (section) {
                info.children = section.children.length;
                info.childClasses = [...section.children].slice(0, 10).map(c => c.className).filter(Boolean);
                info.sampleChild = section.children[0]?.outerHTML?.substring(0, 500) || 'none';
            }
            return info;
        }''')
        print(f"  Debug: {json.dumps(debug, indent=2)}")
        screenshot_path = Path(__file__).parent / "apartments_debug.png"
        await page.screenshot(path=str(screenshot_path), full_page=False)
        print(f"  Debug screenshot saved to {screenshot_path}")

    # ----- Compute metrics -----
    star_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
    responded = not_responded = 0
    for r in reviews:
        s = r.get("rating", 0)
        if s in star_counts:
            star_counts[s] += 1
        if r.get("has_response"):
            responded += 1
        else:
            not_responded += 1

    total = len(reviews)
    response_rate = round((responded / total) * 100, 1) if total else 0
    needs_response = sum(1 for r in reviews if not r.get("has_response") and r.get("rating", 5) <= 3)

    result = {
        "rating": rating,
        "review_count": review_count or total,
        "reviews": reviews,
        "star_distribution": star_counts,
        "reviews_fetched": total,
        "responded": responded,
        "not_responded": not_responded,
        "needs_response": needs_response,
        "response_rate": response_rate,
        "source": "apartments.com",
        "url": url,
    }

    print(f"\n  {config['name']}: {rating}★ | {total} scraped | "
          f"{responded} replied ({response_rate}%) | {needs_response} need attention")
    print(f"  Stars: {star_counts}")
    return result


async def main():
    headless = '--headless' in sys.argv
    mode = "HEADLESS" if headless else "VISIBLE (Chrome will open)"
    print(f"Apartments.com Reviews Scraper — {mode}")
    print(f"Properties: {', '.join(PROPERTIES.keys())}\n")

    # Clean profile to avoid WAF fingerprint accumulation
    import shutil
    if Path(PROFILE_DIR).exists():
        shutil.rmtree(PROFILE_DIR)

    cache = {}
    if CACHE_PATH.exists():
        try:
            cache = json.loads(CACHE_PATH.read_text())
        except Exception:
            pass

    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=headless,
            channel='chrome',
            locale='en-US',
            viewport={'width': 1440, 'height': 900},
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
            ],
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()

        # Stealth: hide webdriver flag and add chrome runtime
        await page.add_init_script('''
            Object.defineProperty(navigator, "webdriver", {get: () => undefined});
            window.chrome = { runtime: {}, csi: function(){}, loadTimes: function(){} };
            Object.defineProperty(navigator, "plugins", {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, "languages", {get: () => ["en-US", "en"]});
        ''')

        # Warm up with a normal site visit to establish browsing pattern
        print("Warming up browser...")
        await page.goto('https://www.google.com', wait_until='domcontentloaded', timeout=15000)
        await human_delay(2, 3)

        for pid, config in PROPERTIES.items():
            try:
                result = await scrape_property(page, pid, config)
                if result.get("reviews") or result.get("rating"):
                    cache[pid] = {"ts": time.time(), "data": result}
                else:
                    print(f"  No data for {pid}, keeping old cache")
            except Exception as e:
                print(f"  ERROR scraping {pid}: {e}")
                import traceback
                traceback.print_exc()

            # Longer human-like delay between properties
            await human_delay(8, 15)

        await ctx.close()

    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False))
    print(f"\nCache saved to {CACHE_PATH}")
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
