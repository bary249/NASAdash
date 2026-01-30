#!/usr/bin/env python3
"""
Run All Database Operations.

This script:
1. Initializes all databases (Yardi, RealPage, Unified)
2. Pulls data from both PMS APIs
3. Populates the unified data layer
4. Calculates all metrics

Usage:
    python run_all.py              # Run full extraction
    python run_all.py --init       # Initialize databases only
    python run_all.py --unified    # Populate unified layer only (from existing raw data)
    python run_all.py --summary    # Show all database summaries
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.db.schema import init_all_databases, YARDI_DB_PATH, REALPAGE_DB_PATH, UNIFIED_DB_PATH
from app.db.populate_yardi import populate_yardi_database, show_yardi_summary
from app.db.populate_realpage import populate_realpage_database, show_realpage_summary
from app.db.populate_unified import populate_unified_database, show_unified_summary


async def run_full_extraction():
    """Run complete extraction from both PMS systems."""
    print("\n" + "=" * 70)
    print("  OWNERDASHV2 - FULL DATA EXTRACTION")
    print("=" * 70)
    
    # 1. Initialize databases
    print("\n[1/4] Initializing databases...")
    init_all_databases()
    
    # 2. Extract from RealPage
    print("\n[2/4] Extracting from RealPage...")
    try:
        await populate_realpage_database()
    except Exception as e:
        print(f"   ⚠️  RealPage extraction failed: {e}")
    
    # 3. Extract from Yardi  
    print("\n[3/4] Extracting from Yardi...")
    try:
        await populate_yardi_database()
    except Exception as e:
        print(f"   ⚠️  Yardi extraction failed: {e}")
    
    # 4. Populate unified layer
    print("\n[4/4] Populating unified data layer...")
    populate_unified_database()
    
    # Final summary
    print("\n" + "=" * 70)
    print("  EXTRACTION COMPLETE")
    print("=" * 70)
    print("\nDatabase files created:")
    print(f"   📁 Yardi:    {YARDI_DB_PATH}")
    print(f"   📁 RealPage: {REALPAGE_DB_PATH}")
    print(f"   📁 Unified:  {UNIFIED_DB_PATH}")
    print("\nUse --summary to view database contents.")


def show_all_summaries():
    """Show summaries of all databases."""
    print("\n" + "=" * 70)
    print("  DATABASE SUMMARIES")
    print("=" * 70)
    
    show_realpage_summary()
    show_yardi_summary()
    show_unified_summary()


def main():
    parser = argparse.ArgumentParser(
        description="OwnerDashV2 Database Management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_all.py              # Full extraction from both PMS systems
    python run_all.py --init       # Just initialize empty databases
    python run_all.py --unified    # Rebuild unified layer from existing raw data
    python run_all.py --summary    # View all database contents
        """
    )
    parser.add_argument("--init", action="store_true", 
                        help="Initialize databases only (no extraction)")
    parser.add_argument("--unified", action="store_true",
                        help="Populate unified layer only (from existing raw data)")
    parser.add_argument("--summary", action="store_true",
                        help="Show all database summaries")
    
    args = parser.parse_args()
    
    if args.summary:
        show_all_summaries()
    elif args.init:
        init_all_databases()
    elif args.unified:
        populate_unified_database()
    else:
        asyncio.run(run_full_extraction())


if __name__ == "__main__":
    main()
