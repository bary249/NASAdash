#!/usr/bin/env python3
"""
Automated RealPage token refresh via Playwright headless browser.

Logs in to RealPage (email → password), intercepts the OIDC token exchange,
and saves the JWT to realpage_token.json.

Credentials from .env: REALPAGE_EMAIL, REALPAGE_PASSWORD
Saves token to realpage_token.json (same file used by report downloaders).

Usage:
    python auto_token.py              # Refresh token (headless)
    python auto_token.py --visible    # Refresh with visible browser (debug)
    python auto_token.py --check      # Check if current token is still valid
    python auto_token.py --force      # Force refresh even if token is valid
"""

import base64
import json
import sys
import os
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
TOKEN_FILE = SCRIPT_DIR / "realpage_token.json"
PROFILE_DIR = "/tmp/realpage_token_profile"

# RealPage login entry point — the SPA will trigger the OIDC authorize flow
LOGIN_URL = "https://www.realpage.com/home"


# ── Token check ───────────────────────────────────────────────

def check_token():
    """Check if the current token is still valid."""
    if not TOKEN_FILE.exists():
        print("No token file found.")
        return False

    data = json.loads(TOKEN_FILE.read_text())
    token = data.get("access_token", "")
    if not token:
        print("Token file is empty.")
        return False

    try:
        parts = token.split(".")
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode())
        exp = datetime.fromtimestamp(payload["exp"])
        now = datetime.now()
        remaining = (exp - now).total_seconds()

        print(f"Token info:")
        print(f"  Client:  {payload.get('client_id')}")
        print(f"  User:    {payload.get('loginName')}")
        print(f"  Org:     {payload.get('orgName')}")
        print(f"  Expires: {exp.strftime('%Y-%m-%d %H:%M:%S')}")

        if remaining > 0:
            mins = remaining / 60
            print(f"  Status:  VALID ({mins:.0f} min remaining)")
            return True
        else:
            print(f"  Status:  EXPIRED ({-remaining/60:.0f} min ago)")
            return False
    except Exception as e:
        print(f"Error reading token: {e}")
        return False


# ── Playwright login ──────────────────────────────────────────

def refresh_token(headless: bool = True):
    """Login via Playwright and capture the JWT from the OIDC token exchange."""
    load_dotenv(SCRIPT_DIR / ".env")

    email = os.environ.get("REALPAGE_EMAIL")
    password = os.environ.get("REALPAGE_PASSWORD")

    if not email or not password:
        print("ERROR: Set REALPAGE_EMAIL and REALPAGE_PASSWORD in .env")
        sys.exit(1)

    from playwright.sync_api import sync_playwright

    all_tokens = []  # collect all captured tokens

    print(f"Starting {'headless' if headless else 'visible'} browser...")

    with sync_playwright() as p:
        # Use persistent context (keeps cookies for faster re-auth)
        browser = p.chromium.launch_persistent_context(
            PROFILE_DIR,
            headless=headless,
            channel="chrome",
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = browser.pages[0] if browser.pages else browser.new_page()

        # Intercept ALL token exchange responses
        def handle_response(response):
            if "/connect/token" in response.url and response.status == 200:
                try:
                    body = response.json()
                    if "access_token" in body:
                        token = body["access_token"]
                        parts = token.split(".")
                        payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode())
                        cid = payload.get("client_id", "unknown")
                        scopes = payload.get("scope", [])
                        all_tokens.append({"token": token, "client_id": cid, "scopes": scopes})
                        print(f"  Captured token: client={cid}, scopes={len(scopes)}")
                except Exception:
                    pass

        page.on("response", handle_response)

        # Navigate to RealPage home (triggers OIDC flow if not logged in)
        print(f"Step 1: Navigating to {LOGIN_URL}...")
        page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(2000)

        current_url = page.url
        print(f"  Current URL: {current_url[:80]}")

        # Check if we're already on the dashboard (persistent session)
        if "/home" in current_url and "Account" not in current_url and "authorize" not in current_url:
            # Might already be logged in from persistent profile
            # Check if we captured a token during page load
            if captured_token["access_token"]:
                print("  Already logged in (token captured during load)")
            else:
                # Try to get token from localStorage
                try:
                    storage = page.evaluate("""() => {
                        for (let i = 0; i < localStorage.length; i++) {
                            const key = localStorage.key(i);
                            const val = localStorage.getItem(key);
                            if (val && val.includes('access_token')) {
                                return val;
                            }
                        }
                        return null;
                    }""")
                    if storage:
                        data = json.loads(storage)
                        if "access_token" in data:
                            captured_token["access_token"] = data["access_token"]
                            print("  Got token from localStorage")
                except Exception:
                    pass

        # If on login page, fill in credentials
        if "Account/SignIn" in page.url or "Account/EntryPoint" in page.url:
            print("Step 2: Filling email...")
            # Wait for email input
            page.wait_for_selector('input[name="Username"]', timeout=10000)
            page.fill('input[name="Username"]', email)

            # Click continue/submit
            submit_btn = page.query_selector('button[type="submit"], input[type="submit"]')
            if submit_btn:
                submit_btn.click()
            else:
                page.keyboard.press("Enter")

            page.wait_for_timeout(2000)
            print(f"  After email: {page.url[:80]}")

        # Password page
        if "Account/Local" in page.url:
            print("Step 3: Filling password...")
            page.wait_for_selector('input[name="Password"]', timeout=10000)
            page.fill('input[name="Password"]', password)

            submit_btn = page.query_selector('button[type="submit"], input[type="submit"]')
            if submit_btn:
                submit_btn.click()
            else:
                page.keyboard.press("Enter")

            # Wait for redirect to complete and token to be captured
            print("  Waiting for login to complete...")
            page.wait_for_timeout(5000)

        # If no tokens captured yet, wait a bit more
        if not all_tokens:
            print("  Waiting for token exchange...")
            for i in range(10):
                page.wait_for_timeout(1000)
                if all_tokens:
                    break

        # Check if we already have a reportinguipkce or unifiedreportingapi token
        def pick_best_token(tokens):
            # Prefer reportinguipkce
            for t in tokens:
                if t["client_id"] == "reportinguipkce":
                    return t["token"]
            # Then any token with unifiedreportingapi scope
            for t in tokens:
                if "unifiedreportingapi" in t.get("scopes", []):
                    return t["token"]
            # Fallback: first token
            return tokens[0]["token"] if tokens else None

        best = pick_best_token(all_tokens)
        if best:
            parts = best.split(".")
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode())
            cid = payload.get("client_id", "")
            has_reporting = "unifiedreportingapi" in payload.get("scope", [])
            print(f"  Best token so far: client={cid}, has_reporting_scope={has_reporting}")

        # Navigate to Unified Reporting to get the reportinguipkce token
        need_reporting = not any(t["client_id"] == "reportinguipkce" for t in all_tokens)
        if need_reporting:
            print("Step 4: Navigating to Unified Reporting for reportinguipkce token...")
            page.goto("https://www.realpage.com/unified-reporting/", wait_until="domcontentloaded", timeout=30000)

            # Wait up to 15s for the reporting token
            for i in range(15):
                page.wait_for_timeout(1000)
                if any(t["client_id"] == "reportinguipkce" for t in all_tokens):
                    print(f"  Got reportinguipkce token!")
                    break

            # Also try localStorage on the reporting page
            if not any(t["client_id"] == "reportinguipkce" for t in all_tokens):
                try:
                    ls_tokens = page.evaluate("""() => {
                        const results = [];
                        for (let i = 0; i < localStorage.length; i++) {
                            const key = localStorage.key(i);
                            const val = localStorage.getItem(key);
                            if (val && val.includes('access_token')) {
                                results.push({key, val});
                            }
                        }
                        return results;
                    }""")
                    for item in (ls_tokens or []):
                        try:
                            data = json.loads(item["val"])
                            if "access_token" in data:
                                token = data["access_token"]
                                parts = token.split(".")
                                payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode())
                                cid = payload.get("client_id", "unknown")
                                scopes = payload.get("scope", [])
                                all_tokens.append({"token": token, "client_id": cid, "scopes": scopes})
                                print(f"  localStorage token: client={cid}")
                        except Exception:
                            pass
                except Exception:
                    pass

        # Print summary of all captured tokens
        print(f"\n  Total tokens captured: {len(all_tokens)}")
        for t in all_tokens:
            print(f"    - {t['client_id']}: {len(t.get('scopes',[]))} scopes")

        browser.close()

    # Pick best token and save
    access_token = pick_best_token(all_tokens) if all_tokens else None
    if not access_token:
        print("\nERROR: Could not capture access token. Try with --visible flag to debug.")
        sys.exit(1)

    # Save token
    TOKEN_FILE.write_text(json.dumps({"access_token": access_token}, indent=2))

    # Decode and show info
    parts = access_token.split(".")
    payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode())
    exp = datetime.fromtimestamp(payload["exp"])
    remaining_min = (exp - datetime.now()).total_seconds() / 60

    print(f"\n{'='*50}")
    print(f"  Token saved to {TOKEN_FILE.name}")
    print(f"  Client:    {payload.get('client_id')}")
    print(f"  User:      {payload.get('loginName')}")
    print(f"  Org:       {payload.get('orgName')}")
    print(f"  Expires:   {exp.strftime('%Y-%m-%d %H:%M:%S')} ({remaining_min:.0f} min)")
    print(f"{'='*50}")


def main():
    if "--check" in sys.argv:
        valid = check_token()
        sys.exit(0 if valid else 1)

    # Check if current token is still valid (skip refresh if so)
    if "--force" not in sys.argv and TOKEN_FILE.exists():
        try:
            data = json.loads(TOKEN_FILE.read_text())
            token = data.get("access_token", "")
            parts = token.split(".")
            payload = json.loads(base64.urlsafe_b64decode(parts[1] + "==").decode())
            remaining = datetime.fromtimestamp(payload["exp"]) - datetime.now()
            remaining_min = remaining.total_seconds() / 60
            if remaining_min > 10:
                print(f"Current token still valid ({remaining_min:.0f} min remaining). Use --force to refresh anyway.")
                sys.exit(0)
            else:
                print(f"Token expires in {remaining_min:.0f} min, refreshing...")
        except Exception:
            pass

    headless = "--visible" not in sys.argv
    refresh_token(headless=headless)


if __name__ == "__main__":
    main()
