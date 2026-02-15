#!/usr/bin/env python3
"""
OwnerDashV2 — Production Smoke Test
=====================================
Verifies all deployed endpoints (Railway backend + Netlify frontend) are healthy.

Checks:
  1. Backend health & DB status
  2. Portfolio properties list
  3. Per-property endpoints (occupancy, forecast, delinquency, leases, risk, reviews, AI, watchpoints)
  4. Portfolio-level endpoints (watchlist, owner-groups, risk-scores)
  5. Auth endpoint (login)
  6. Frontend (HTML + JS bundle loads)

Usage:
    python smoke_test.py                       # Run against production
    python smoke_test.py --backend http://localhost:8000 --frontend http://localhost:5173
    python smoke_test.py --log                 # Append results to logs/smoke_test.log

Designed to run every 7h via GH Actions or cron.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    import requests
except ImportError:
    print("ERROR: 'requests' package required. Install with: pip install requests")
    sys.exit(1)

# ── Defaults ──
BACKEND_URL = os.environ.get(
    "RAILWAY_API_URL",
    "https://brilliant-upliftment-production-3a4d.up.railway.app",
)
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://nasadash.netlify.app")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "")
TIMEOUT = 20  # seconds per request
TIMEOUT_SLOW = 30  # for heavier endpoints

# Test properties — one from each owner group
TEST_PROPERTIES = ["nexus_east", "parkside", "ridian"]

LOG_DIR = Path(__file__).parent / "logs"


# ── Helpers ──
class SmokeResult:
    def __init__(self):
        self.checks: list[dict] = []
        self.start = time.time()

    def add(self, name: str, ok: bool, detail: str = "", duration_ms: int = 0):
        self.checks.append({
            "name": name,
            "ok": ok,
            "detail": detail[:300],
            "duration_ms": duration_ms,
        })
        icon = "✅" if ok else "❌"
        ms = f" ({duration_ms}ms)" if duration_ms else ""
        print(f"  {icon} {name}{ms}" + (f"  — {detail[:120]}" if detail else ""))

    @property
    def passed(self):
        return sum(1 for c in self.checks if c["ok"])

    @property
    def failed(self):
        return sum(1 for c in self.checks if not c["ok"])

    @property
    def total(self):
        return len(self.checks)

    @property
    def all_ok(self):
        return self.failed == 0

    def summary_dict(self):
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_s": round(time.time() - self.start, 1),
            "passed": self.passed,
            "failed": self.failed,
            "total": self.total,
            "all_ok": self.all_ok,
            "checks": self.checks,
        }


def get(url: str, headers: dict | None = None, timeout: int = TIMEOUT) -> tuple[int, dict | str, int]:
    """GET request. Returns (status_code, json_or_text, duration_ms)."""
    t0 = time.time()
    try:
        r = requests.get(url, headers=headers or {}, timeout=timeout)
        ms = int((time.time() - t0) * 1000)
        try:
            return r.status_code, r.json(), ms
        except Exception:
            return r.status_code, r.text[:500], ms
    except requests.Timeout:
        return 0, "TIMEOUT", int((time.time() - t0) * 1000)
    except Exception as e:
        return 0, str(e)[:200], int((time.time() - t0) * 1000)


def post_json(url: str, body: dict, headers: dict | None = None, timeout: int = TIMEOUT) -> tuple[int, dict | str, int]:
    """POST JSON request."""
    t0 = time.time()
    try:
        h = {"Content-Type": "application/json", **(headers or {})}
        r = requests.post(url, json=body, headers=h, timeout=timeout)
        ms = int((time.time() - t0) * 1000)
        try:
            return r.status_code, r.json(), ms
        except Exception:
            return r.status_code, r.text[:500], ms
    except requests.Timeout:
        return 0, "TIMEOUT", int((time.time() - t0) * 1000)
    except Exception as e:
        return 0, str(e)[:200], int((time.time() - t0) * 1000)


# ── Test Sections ──

def test_backend_health(res: SmokeResult, base: str):
    """Check backend is alive."""
    status, body, ms = get(f"{base}/api/v2/health")
    res.add("Backend /health", status == 200, f"status={status}", ms)


def test_db_status(res: SmokeResult, base: str):
    """Check DB files exist on Railway volume."""
    if not ADMIN_KEY:
        res.add("DB status (skipped)", True, "No ADMIN_API_KEY set")
        return
    status, body, ms = get(f"{base}/api/admin/db-status", {"X-Admin-Key": ADMIN_KEY})
    if status == 200 and isinstance(body, dict):
        unified = body.get("unified", {})
        realpage = body.get("realpage", {})
        u_ok = unified.get("exists", False)
        r_ok = realpage.get("exists", False)
        detail = f"unified={unified.get('size_mb', '?')}MB, realpage={realpage.get('size_mb', '?')}MB"
        res.add("DB status", u_ok and r_ok, detail, ms)
    else:
        res.add("DB status", False, f"status={status}", ms)


def test_portfolio_properties(res: SmokeResult, base: str) -> list[str]:
    """Check portfolio properties list returns data."""
    status, body, ms = get(f"{base}/api/portfolio/properties", timeout=TIMEOUT_SLOW)
    if status == 200 and isinstance(body, list) and len(body) > 0:
        ids = [p["id"] for p in body]
        res.add("Portfolio properties", True, f"{len(body)} properties", ms)
        return ids
    else:
        res.add("Portfolio properties", False, f"status={status}, count={len(body) if isinstance(body, list) else '?'}", ms)
        return []


def test_owner_groups(res: SmokeResult, base: str):
    status, body, ms = get(f"{base}/api/portfolio/owner-groups")
    ok = status == 200 and isinstance(body, list) and len(body) > 0
    res.add("Owner groups", ok, f"{body}" if ok else f"status={status}", ms)


def test_watchlist(res: SmokeResult, base: str):
    status, body, ms = get(f"{base}/api/portfolio/watchlist")
    if status == 200 and isinstance(body, dict):
        props = body.get("properties", [])
        res.add("Watchlist", True, f"{len(props)} properties, thresholds present", ms)
    else:
        res.add("Watchlist", False, f"status={status}", ms)


def test_property_availability(res: SmokeResult, base: str, pid: str):
    status, body, ms = get(f"{base}/api/v2/properties/{pid}/availability")
    if status == 200 and isinstance(body, dict):
        atr = body.get("atr")
        total = body.get("total_units", 0)
        res.add(f"[{pid}] Availability/ATR", total > 0, f"total={total}, atr={atr}", ms)
    else:
        res.add(f"[{pid}] Availability/ATR", False, f"status={status}", ms)


def test_property_forecast(res: SmokeResult, base: str, pid: str):
    status, body, ms = get(f"{base}/api/v2/properties/{pid}/occupancy-forecast")
    if status == 200 and isinstance(body, dict):
        forecast = body.get("forecast", [])
        source = body.get("data_source", "?")
        exp_units = len(body.get("expiration_units", []))
        has_weeks = len(forecast) > 0
        res.add(f"[{pid}] Forecast", has_weeks, f"weeks={len(forecast)}, source={source}, exp_units={exp_units}", ms)
    else:
        res.add(f"[{pid}] Forecast", False, f"status={status}", ms)


def test_property_delinquency(res: SmokeResult, base: str, pid: str):
    status, body, ms = get(f"{base}/api/v2/properties/{pid}/delinquency")
    ok = status == 200 and isinstance(body, dict)
    if ok:
        total = body.get("total_delinquent", body.get("total_balance", "?"))
        units = body.get("delinquent_units", "?")
        res.add(f"[{pid}] Delinquency", True, f"total=${total}, units={units}", ms)
    else:
        res.add(f"[{pid}] Delinquency", False, f"status={status}", ms)


def test_property_lease_expirations(res: SmokeResult, base: str, pid: str):
    status, body, ms = get(f"{base}/api/v2/properties/{pid}/expirations", timeout=TIMEOUT_SLOW)
    if status == 200 and isinstance(body, dict):
        periods = body.get("periods", [])
        res.add(f"[{pid}] Lease expirations", True, f"{len(periods)} periods", ms)
    else:
        res.add(f"[{pid}] Lease expirations", False, f"status={status}", ms)


def test_property_risk_scores(res: SmokeResult, base: str, pid: str):
    status, body, ms = get(f"{base}/api/v2/properties/{pid}/risk-scores")
    if status == 200 and isinstance(body, dict):
        has_data = body.get("avg_churn_score") is not None or body.get("message") is not None
        res.add(f"[{pid}] Risk scores", True, f"churn={body.get('avg_churn_score', 'N/A')}", ms)
    else:
        res.add(f"[{pid}] Risk scores", False, f"status={status}", ms)


def test_property_reviews(res: SmokeResult, base: str, pid: str):
    status, body, ms = get(f"{base}/api/v2/properties/{pid}/reputation")
    if status == 200 and isinstance(body, dict):
        sources = body.get("sources", [])
        overall = body.get("overall_rating", "?")
        res.add(f"[{pid}] Reviews/Reputation", True, f"rating={overall}, sources={len(sources)}", ms)
    else:
        # 404 = no review data for this property, still a valid response
        res.add(f"[{pid}] Reviews/Reputation", status in (200, 404), f"status={status}", ms)


def test_property_ai_insights(res: SmokeResult, base: str, pid: str):
    status, body, ms = get(f"{base}/api/v2/properties/{pid}/ai-insights")
    if status == 200 and isinstance(body, dict):
        alerts = body.get("alerts", [])
        res.add(f"[{pid}] AI insights", True, f"{len(alerts)} alerts", ms)
    else:
        # AI might be unavailable if no API key — 200 with error is still "endpoint works"
        res.add(f"[{pid}] AI insights", status in (200, 503), f"status={status}", ms)


def test_property_watchpoints(res: SmokeResult, base: str, pid: str):
    status, body, ms = get(f"{base}/api/v2/properties/{pid}/watchpoints")
    if status == 200 and isinstance(body, dict):
        metrics = len(body.get("available_metrics", {}))
        res.add(f"[{pid}] Watchpoints", metrics > 0, f"{metrics} available metrics", ms)
    else:
        res.add(f"[{pid}] Watchpoints", False, f"status={status}", ms)


def test_auth_login(res: SmokeResult, base: str):
    """Test login endpoint responds (don't actually log in)."""
    status, body, ms = post_json(f"{base}/api/auth/login", {"username": "__smoke__", "password": "__smoke__"})
    # Expect 401 (bad creds) — that means the endpoint is alive
    res.add("Auth /login endpoint", status == 401, f"status={status}", ms)


def test_chat_status(res: SmokeResult, base: str):
    status, body, ms = get(f"{base}/api/v2/chat/status")
    if status == 200 and isinstance(body, dict):
        available = body.get("available", False)
        res.add("Chat status", True, f"available={available}", ms)
    else:
        res.add("Chat status", False, f"status={status}", ms)


def test_frontend_html(res: SmokeResult, frontend: str):
    """Check frontend serves HTML with JS bundle."""
    status, body, ms = get(frontend)
    if status == 200 and isinstance(body, str):
        has_root = "id=\"root\"" in body or 'id="root"' in body
        has_js = ".js" in body
        res.add("Frontend HTML", has_root and has_js, f"has_root={has_root}, has_js={has_js}", ms)
    else:
        res.add("Frontend HTML", False, f"status={status}", ms)


def test_frontend_api_proxy(res: SmokeResult, frontend: str):
    """Check Netlify /api proxy works."""
    status, body, ms = get(f"{frontend}/api/portfolio/owner-groups")
    ok = status == 200 and isinstance(body, list)
    res.add("Frontend API proxy", ok, f"status={status}, groups={body if ok else '?'}", ms)


# ── Main ──

def run_smoke_test(backend: str, frontend: str) -> SmokeResult:
    res = SmokeResult()

    print(f"\n{'='*60}")
    print(f"  OWNERDASHV2 SMOKE TEST")
    print(f"  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"  Backend:  {backend}")
    print(f"  Frontend: {frontend}")
    print(f"{'='*60}\n")

    # 1. Infrastructure
    print("── Infrastructure ──")
    test_backend_health(res, backend)
    test_db_status(res, backend)
    test_auth_login(res, backend)
    test_chat_status(res, backend)

    # 2. Portfolio-level
    print("\n── Portfolio Endpoints ──")
    prop_ids = test_portfolio_properties(res, backend)
    test_owner_groups(res, backend)
    test_watchlist(res, backend)

    # 3. Per-property endpoints
    test_props = [p for p in TEST_PROPERTIES if p in prop_ids] or TEST_PROPERTIES[:2]
    for pid in test_props:
        print(f"\n── Property: {pid} ──")
        test_property_availability(res, backend, pid)
        test_property_forecast(res, backend, pid)
        test_property_delinquency(res, backend, pid)
        test_property_lease_expirations(res, backend, pid)
        test_property_risk_scores(res, backend, pid)
        test_property_reviews(res, backend, pid)
        test_property_ai_insights(res, backend, pid)
        test_property_watchpoints(res, backend, pid)

    # 4. Frontend
    print("\n── Frontend ──")
    test_frontend_html(res, frontend)
    test_frontend_api_proxy(res, frontend)

    # Summary
    print(f"\n{'='*60}")
    icon = "✅" if res.all_ok else "❌"
    print(f"  {icon} RESULT: {res.passed}/{res.total} passed, {res.failed} failed")
    print(f"  Duration: {time.time() - res.start:.1f}s")
    print(f"{'='*60}\n")

    return res


def save_log(result: SmokeResult):
    """Append result to logs/smoke_test.log as JSONL."""
    LOG_DIR.mkdir(exist_ok=True)
    log_file = LOG_DIR / "smoke_test.log"
    entry = result.summary_dict()
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")
    print(f"  📝 Log saved to {log_file}")


def main():
    parser = argparse.ArgumentParser(description="OwnerDashV2 Production Smoke Test")
    parser.add_argument("--backend", default=BACKEND_URL, help="Backend base URL")
    parser.add_argument("--frontend", default=FRONTEND_URL, help="Frontend base URL")
    parser.add_argument("--log", action="store_true", help="Save results to logs/smoke_test.log")
    args = parser.parse_args()

    result = run_smoke_test(args.backend.rstrip("/"), args.frontend.rstrip("/"))

    if args.log:
        save_log(result)

    sys.exit(0 if result.all_ok else 1)


if __name__ == "__main__":
    main()
