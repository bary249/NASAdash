"""
Sync lease data for all Kairoi properties
"""
import asyncio
import sqlite3
from datetime import datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.clients.realpage_client import RealPageClient
from app.db.schema import REALPAGE_DB_PATH

PMCID = "4248314"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

PROPERTIES = [
    ("5472172", "Nexus East"),
    ("5536211", "Parkside"),
    ("5446271", "Ridian"),
]

async def sync_leases(site_id: str, name: str):
    print(f"\n{'='*60}")
    print(f"Syncing {name} (Site ID: {site_id})")
    print('='*60)
    
    client = RealPageClient(pmcid=PMCID, siteid=site_id, licensekey=LICENSEKEY)
    conn = sqlite3.connect(REALPAGE_DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Clear old data for this site
        cursor.execute("DELETE FROM realpage_leases WHERE site_id = ?", (site_id,))
        
        # Get leases
        print(f"📋 Fetching leases via get_leases_raw...")
        leases = await client.get_leases_raw(site_id)
        print(f"   Got {len(leases)} leases")
        
        # Insert
        for lease in leases:
            cursor.execute("""
                INSERT INTO realpage_leases
                (pmc_id, site_id, lease_id, resh_id, unit_id,
                 lease_start_date, lease_end_date, lease_term, lease_term_desc,
                 rent_amount, next_lease_id, prior_lease_id, status, status_text,
                 type_code, type_text, move_in_date, sched_move_in_date,
                 applied_date, active_date, inactive_date, last_renewal_date,
                 initial_lease_date, bill_date, payment_due_date,
                 current_balance, total_paid, late_day_of_month, late_charge_pct,
                 evict, head_of_household_name, extracted_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                PMCID,
                site_id,
                lease.get('lease_id'),
                lease.get('resh_id'),
                lease.get('unit_id'),
                lease.get('lease_start_date'),
                lease.get('lease_end_date'),
                lease.get('lease_term'),
                lease.get('lease_term_desc'),
                lease.get('rent_amount', 0),
                lease.get('next_lease_id'),
                lease.get('prior_lease_id'),
                lease.get('status'),
                lease.get('status_text'),
                lease.get('type_code'),
                lease.get('type_text'),
                lease.get('move_in_date'),
                lease.get('sched_move_in_date'),
                lease.get('applied_date'),
                lease.get('active_date'),
                lease.get('inactive_date'),
                lease.get('last_renewal_date'),
                lease.get('initial_lease_date'),
                lease.get('bill_date'),
                lease.get('payment_due_date'),
                lease.get('current_balance', 0),
                lease.get('total_paid', 0),
                lease.get('late_day_of_month'),
                lease.get('late_charge_pct', 0),
                lease.get('evict'),
                lease.get('head_of_household_name'),
                datetime.now().isoformat()
            ))
        
        conn.commit()
        
        # Show sample with rent
        cursor.execute("""
            SELECT unit_id, rent_amount FROM realpage_leases 
            WHERE site_id = ? AND rent_amount > 0 LIMIT 5
        """, (site_id,))
        samples = cursor.fetchall()
        print(f"   Sample rents: {samples}")
        
        # Count
        cursor.execute("SELECT COUNT(*) FROM realpage_leases WHERE site_id = ? AND rent_amount > 0", (site_id,))
        cnt = cursor.fetchone()[0]
        print(f"   ✅ {cnt} leases with rent_amount > 0")
        
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

async def main():
    for site_id, name in PROPERTIES:
        await sync_leases(site_id, name)
    
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    conn = sqlite3.connect(REALPAGE_DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT site_id, COUNT(*), SUM(CASE WHEN rent_amount > 0 THEN 1 ELSE 0 END) as with_rent
        FROM realpage_leases GROUP BY site_id
    """)
    for row in cursor.fetchall():
        print(f"  Site {row[0]}: {row[1]} leases, {row[2]} with rent")
    conn.close()

if __name__ == "__main__":
    asyncio.run(main())
