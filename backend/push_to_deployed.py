#!/usr/bin/env python3
"""
Push local SQLite DBs to the deployed Railway backend.

Uploads unified.db and realpage_raw.db via the admin upload endpoint.
Used by GitHub Actions (or manual runs) to sync data after report refresh.

Usage:
    python push_to_deployed.py                    # Push both DBs
    python push_to_deployed.py --only unified     # Push only unified.db
    python push_to_deployed.py --only realpage    # Push only realpage_raw.db
    python push_to_deployed.py --dry-run          # Check status only

Env vars:
    RAILWAY_API_URL   - Railway backend URL (e.g. https://ownerdash-production.up.railway.app)
    ADMIN_API_KEY     - Shared secret for admin endpoints
"""

import os
import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).parent
load_dotenv(SCRIPT_DIR / ".env")

# Config
RAILWAY_URL = os.environ.get("RAILWAY_API_URL", "").rstrip("/")
ADMIN_KEY = os.environ.get("ADMIN_API_KEY", "")

# Local DB paths
DB_DIR = SCRIPT_DIR / "app" / "db" / "data"
DB_FILES = {
    "unified": DB_DIR / "unified.db",
    "realpage": DB_DIR / "realpage_raw.db",
}


def check_status():
    """Check deployed DB status."""
    print(f"Checking deployed DB status at {RAILWAY_URL}...")
    r = httpx.get(
        f"{RAILWAY_URL}/api/admin/db-status",
        headers={"X-Admin-Key": ADMIN_KEY},
        timeout=15,
    )
    if r.status_code != 200:
        print(f"  ERROR: {r.status_code} {r.text[:200]}")
        return None
    data = r.json()
    print(f"  DB dir: {data.get('db_dir')}")
    for name in ["unified", "realpage", "yardi"]:
        info = data.get(name, {})
        if info.get("exists"):
            print(f"  {name}: {info['size_mb']} MB")
        else:
            print(f"  {name}: NOT FOUND")
    return data


def upload_db(db_type: str) -> bool:
    """Upload a single DB file to Railway."""
    local_path = DB_FILES.get(db_type)
    if not local_path or not local_path.exists():
        print(f"  ERROR: Local {db_type} DB not found at {local_path}")
        return False

    size_mb = local_path.stat().st_size / (1024 * 1024)
    print(f"  Uploading {db_type} ({size_mb:.1f} MB)...")

    start = time.time()
    with open(local_path, "rb") as f:
        r = httpx.post(
            f"{RAILWAY_URL}/api/admin/upload-db?db_type={db_type}",
            headers={"X-Admin-Key": ADMIN_KEY},
            files={"file": (local_path.name, f, "application/octet-stream")},
            timeout=120,
        )

    elapsed = time.time() - start

    if r.status_code == 200:
        data = r.json()
        print(f"  OK: {data.get('size_mb')} MB uploaded in {elapsed:.1f}s")
        return True
    else:
        print(f"  ERROR: {r.status_code} {r.text[:300]}")
        return False


def main():
    if not RAILWAY_URL:
        print("ERROR: Set RAILWAY_API_URL in .env")
        sys.exit(1)
    if not ADMIN_KEY:
        print("ERROR: Set ADMIN_API_KEY in .env")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    only = None
    if "--only" in sys.argv:
        idx = sys.argv.index("--only")
        if idx + 1 < len(sys.argv):
            only = sys.argv[idx + 1]

    print(f"Railway URL: {RAILWAY_URL}")
    print(f"{'='*50}")

    # Check current status
    check_status()

    if dry_run:
        print("\n(dry-run mode — no uploads)")
        return

    # Upload
    print(f"\n{'='*50}")
    print("UPLOADING")
    print(f"{'='*50}")

    targets = [only] if only else list(DB_FILES.keys())
    results = {}

    for db_type in targets:
        results[db_type] = upload_db(db_type)

    # Summary
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    for db_type, ok in results.items():
        status = "OK" if ok else "FAILED"
        print(f"  {db_type}: {status}")

    # Verify
    print()
    check_status()

    if not all(results.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
