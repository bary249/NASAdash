#!/usr/bin/env python3
"""
OwnerDashV2 — Complete Data Refresh Pipeline
=============================================
Single command to refresh ALL data sources end-to-end:

  1. SOAP API pull  → realpage_raw.db  (units, residents, leases, rentable items)
  2. Report download → realpage_raw.db  (box_score, rent_roll, delinquency, etc.)
  3. Unified sync    → unified.db       (occupancy, pricing, units, residents)
  4. Risk scores     → unified.db       (churn & delinquency predictions)
  5. Google reviews  → cache JSON       (PHH properties: Parkside, Nexus East)

Usage:
    python refresh_all.py                    # Run everything
    python refresh_all.py --skip api         # Skip SOAP API pull
    python refresh_all.py --skip reports     # Skip report downloads
    python refresh_all.py --skip risk        # Skip risk score sync
    python refresh_all.py --skip reviews     # Skip Google Reviews scrape
    python refresh_all.py --only reviews     # Only run reviews scrape
    python refresh_all.py --only sync        # Only run unified sync
"""

import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PYTHON = sys.executable

# Step registry: (key, label, description)
STEPS = [
    ("api",     "SOAP API Pull",        "Units, residents, leases, rentable items → realpage_raw.db"),
    ("reports", "Report Downloads",      "Box score, rent roll, delinquency, etc. → realpage_raw.db"),
    ("sync",    "Unified DB Sync",       "realpage_raw.db → unified.db"),
    ("risk",    "Risk Score Sync",       "Snowflake risk scores → unified.db"),
    ("reviews", "Google Reviews Scrape", "PHH property reviews + owner replies → cache"),
]


def banner(text: str, char: str = "=", width: int = 70):
    print(f"\n{char * width}")
    print(f"  {text}")
    print(f"{char * width}")


def run_step(label: str, cmd: list, cwd: str = None, timeout: int = 600) -> dict:
    """Run a subprocess step with live output. Returns {success, duration, output}."""
    start = time.time()
    cwd = cwd or str(SCRIPT_DIR)

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

        lines = []
        for line in proc.stdout:
            line = line.rstrip()
            lines.append(line)
            print(f"  {line}", flush=True)

        proc.wait(timeout=timeout)
        output = "\n".join(lines)
        success = proc.returncode == 0
        duration = time.time() - start

        return {"success": success, "duration": duration, "output": output}

    except subprocess.TimeoutExpired:
        proc.kill()
        return {"success": False, "duration": time.time() - start, "output": f"TIMEOUT after {timeout}s"}
    except Exception as e:
        return {"success": False, "duration": time.time() - start, "output": str(e)}


def step_api() -> dict:
    """Step 1: Pull SOAP API data for all properties."""
    banner("STEP 1/5: SOAP API PULL")
    print("  Pulling units, residents, leases for all Kairoi properties...")
    return run_step("API Pull", [PYTHON, "-u", "pull_all_api_data.py"], timeout=900)


def step_reports() -> dict:
    """Step 2: Download RealPage reports for all properties."""
    banner("STEP 2/5: REPORT DOWNLOADS")
    print("  Downloading box_score, rent_roll, delinquency, lease_exp, projected_occ, activity...")
    return run_step("Reports", [PYTHON, "-u", "download_reports_v2.py"], timeout=1200)


def step_sync() -> dict:
    """Step 3: Sync realpage_raw.db → unified.db."""
    banner("STEP 3/5: UNIFIED DB SYNC")
    print("  Syncing properties, occupancy, pricing, units, residents, delinquency...")
    return run_step("Sync", [PYTHON, "-u", "-m", "app.db.sync_realpage_to_unified"], timeout=120)


def step_risk() -> dict:
    """Step 4: Sync risk scores from Snowflake CSV → unified.db."""
    banner("STEP 4/5: RISK SCORE SYNC")
    print("  Loading Snowflake risk scores and writing to unified.db...")
    return run_step("Risk Scores", [PYTHON, "-u", "-m", "app.db.sync_risk_scores"], timeout=120)


def step_reviews() -> dict:
    """Step 5: Scrape Google reviews for PHH properties."""
    banner("STEP 5/5: GOOGLE REVIEWS SCRAPE")
    print("  Scraping reviews + owner replies for Parkside & Nexus East...")
    return run_step("Reviews", [PYTHON, "-u", "scrape_reviews.py"], timeout=300)


# Map step keys to functions
STEP_FNS = {
    "api":     step_api,
    "reports": step_reports,
    "sync":    step_sync,
    "risk":    step_risk,
    "reviews": step_reviews,
}


def main():
    parser = argparse.ArgumentParser(
        description="OwnerDashV2 — Complete Data Refresh Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Steps:
  api      SOAP API pull (units, residents, leases)
  reports  RealPage report downloads (box_score, rent_roll, etc.)
  sync     Sync realpage_raw.db → unified.db
  risk     Risk score sync (Snowflake → unified.db)
  reviews  Google Reviews scrape (PHH properties)
"""
    )
    parser.add_argument(
        "--skip", nargs="+", choices=list(STEP_FNS.keys()),
        help="Steps to skip"
    )
    parser.add_argument(
        "--only", nargs="+", choices=list(STEP_FNS.keys()),
        help="Only run these steps"
    )
    args = parser.parse_args()

    skip_set = set(args.skip or [])
    only_set = set(args.only or [])

    # Determine which steps to run
    steps_to_run = []
    for key, label, desc in STEPS:
        if only_set and key not in only_set:
            continue
        if key in skip_set:
            continue
        steps_to_run.append((key, label, desc))

    # Header
    start_time = datetime.now()
    banner("OWNERDASHV2 — COMPLETE DATA REFRESH", "█")
    print(f"  Started:  {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Steps:    {len(steps_to_run)} of {len(STEPS)}")
    for key, label, desc in steps_to_run:
        print(f"    • {label} — {desc}")

    # Run steps
    results = {}
    for key, label, desc in steps_to_run:
        fn = STEP_FNS[key]
        result = fn()
        results[key] = result

        status = "✅" if result["success"] else "❌"
        print(f"\n  {status} {label}: {'done' if result['success'] else 'FAILED'} ({result['duration']:.1f}s)")

    # Skipped steps
    skipped = [label for key, label, _ in STEPS if key not in results]

    # Final summary
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    banner("REFRESH COMPLETE", "█")
    print(f"  Duration: {duration:.0f}s ({duration/60:.1f} min)")
    print()

    for key, label, _ in STEPS:
        if key in results:
            r = results[key]
            icon = "✅" if r["success"] else "❌"
            print(f"  {icon} {label:<25s} {r['duration']:>6.1f}s")
        else:
            print(f"  ⏭️  {label:<25s} skipped")

    failed = [label for key, label, _ in STEPS if key in results and not results[key]["success"]]
    if failed:
        print(f"\n  ⚠️  Failed steps: {', '.join(failed)}")
        print(f"  Check output above for details.")

    print(f"\n  Data is now live in the dashboard. 🚀")
    print("█" * 70)

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
