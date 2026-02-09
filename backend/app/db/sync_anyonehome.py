"""
AnyoneHome Data Sync Script - GET ONLY (Read-Only Operations)
Syncs AnyoneHome leasing CRM data for Kairoi properties to the unified database.

This script:
1. Fetches accounts from AnyoneHome
2. Fetches all Kairoi properties with RealPage mappings
3. Stores data in unified.db for dashboard integration
"""

import sys
import sqlite3
import re
from datetime import datetime
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.api.anyonehome_client import get_client, GetOnlyMiddleware
from app.db.schema import UNIFIED_DB_PATH, UNIFIED_SCHEMA

# Kairoi account ID
KAIROI_ACCOUNT_ID = "0010H00002QznrGQAR"
KAIROI_ACCOUNT_NAME = "Kairoi Residential"

# Known Kairoi properties from OwnerDashV2 (RealPage Site IDs)
KAIROI_REALPAGE_SITES = {
    "5472172": "nexus_east",
    "5536211": "parkside",
    "5446271": "ridian",
    "5375283": "the_northern",
}


def init_anyonehome_tables():
    """Initialize AnyoneHome tables in unified.db"""
    conn = sqlite3.connect(UNIFIED_DB_PATH)
    try:
        # Execute only the AnyoneHome portion of the schema
        conn.executescript(UNIFIED_SCHEMA)
        conn.commit()
        print("✅ AnyoneHome tables initialized in unified.db")
    finally:
        conn.close()


def parse_properties_xml(xml_data: str) -> list:
    """Parse property list XML response into list of dicts"""
    properties = []
    
    # Find all properties
    prop_matches = re.findall(r'<Property>(.*?)</Property>', xml_data, re.DOTALL)
    
    # Track current management company
    current_account_id = None
    current_account_name = None
    
    # Split by management company to get account context
    mgmt_parts = re.split(r'<ManagementCompany', xml_data)
    
    for part in mgmt_parts[1:]:  # Skip first empty part
        # Extract management company info
        mgmt_match = re.search(r'name="([^"]+)" id="([^"]+)"', part)
        if mgmt_match:
            current_account_name = mgmt_match.group(1)
            current_account_id = mgmt_match.group(2)
        
        # Find properties in this management company section
        props = re.findall(r'<Property>(.*?)</Property>', part, re.DOTALL)
        
        for prop_xml in props:
            prop = {
                'account_id': current_account_id,
                'account_name': current_account_name,
            }
            
            # Extract fields
            id_match = re.search(r'<ID>(.*?)</ID>', prop_xml)
            name_match = re.search(r'<PropertyName>(.*?)</PropertyName>', prop_xml)
            pref_match = re.search(r'<PreferredID>(.*?)</PreferredID>', prop_xml)
            realpage_match = re.search(r'ExternalID id="(\d+)" vendor="RealPage"', prop_xml)
            email_match = re.search(r'<ListingContactEmail>(.*?)</ListingContactEmail>', prop_xml)
            
            prop['ah_property_id'] = id_match.group(1) if id_match else None
            prop['property_name'] = name_match.group(1) if name_match else None
            prop['preferred_id'] = pref_match.group(1) if pref_match and pref_match.group(1) else None
            prop['realpage_site_id'] = realpage_match.group(1) if realpage_match else None
            prop['listing_contact_email'] = email_match.group(1) if email_match and email_match.group(1) else None
            
            if prop['ah_property_id']:
                properties.append(prop)
    
    return properties


def sync_accounts(client, conn):
    """Sync AnyoneHome accounts (GET only)"""
    print("\n📋 Syncing AnyoneHome Accounts...")
    
    result = client.retrieve_accounts()
    
    if not result['success']:
        print(f"❌ Failed to retrieve accounts: {result['data']}")
        return 0
    
    data = result['data']
    accounts = data.get('Messages', {}).get('Message', {}).get('RetrieveAccountsResponse', {}).get('Accounts', {}).get('Account', [])
    
    cursor = conn.cursor()
    count = 0
    
    for acc in accounts:
        account_id = acc.get('@id')
        account_name = acc.get('@name')
        
        cursor.execute("""
            INSERT OR REPLACE INTO anyonehome_accounts 
            (account_id, account_name, synced_at)
            VALUES (?, ?, ?)
        """, (account_id, account_name, datetime.now().isoformat()))
        count += 1
    
    conn.commit()
    print(f"✅ Synced {count} accounts")
    return count


def sync_kairoi_properties(client, conn):
    """Sync all Kairoi properties from AnyoneHome (GET only)"""
    print("\n🏢 Syncing Kairoi Properties...")
    
    result = client.retrieve_property_list()
    
    if not result['success']:
        print(f"❌ Failed to retrieve properties: {result['data']}")
        return 0
    
    # Parse XML response
    properties = parse_properties_xml(str(result['data']))
    
    # Filter for Kairoi Residential only
    kairoi_props = [p for p in properties if p.get('account_id') == KAIROI_ACCOUNT_ID]
    
    cursor = conn.cursor()
    count = 0
    
    for prop in kairoi_props:
        cursor.execute("""
            INSERT OR REPLACE INTO anyonehome_properties 
            (ah_property_id, account_id, property_name, preferred_id, 
             realpage_site_id, listing_contact_email, synced_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            prop['ah_property_id'],
            prop['account_id'],
            prop['property_name'],
            prop['preferred_id'],
            prop['realpage_site_id'],
            prop['listing_contact_email'],
            datetime.now().isoformat()
        ))
        count += 1
        
        # Mark if it's one of our known properties
        if prop['realpage_site_id'] in KAIROI_REALPAGE_SITES:
            print(f"  ⭐ {prop['property_name']} (RealPage: {prop['realpage_site_id']}) - TRACKED")
        else:
            print(f"  📍 {prop['property_name']} (RealPage: {prop['realpage_site_id'] or 'N/A'})")
    
    conn.commit()
    print(f"\n✅ Synced {count} Kairoi properties")
    return count


def get_sync_summary(conn):
    """Get summary of synced data"""
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("📊 SYNC SUMMARY")
    print("=" * 60)
    
    # Accounts
    cursor.execute("SELECT COUNT(*) FROM anyonehome_accounts")
    acc_count = cursor.fetchone()[0]
    print(f"\nAccounts: {acc_count}")
    
    # Properties
    cursor.execute("SELECT COUNT(*) FROM anyonehome_properties")
    prop_count = cursor.fetchone()[0]
    print(f"Properties: {prop_count}")
    
    # Properties with RealPage mapping
    cursor.execute("SELECT COUNT(*) FROM anyonehome_properties WHERE realpage_site_id IS NOT NULL")
    mapped_count = cursor.fetchone()[0]
    print(f"Properties with RealPage ID: {mapped_count}")
    
    # Known tracked properties
    cursor.execute("""
        SELECT property_name, ah_property_id, realpage_site_id 
        FROM anyonehome_properties 
        WHERE realpage_site_id IN (?, ?, ?)
    """, tuple(KAIROI_REALPAGE_SITES.keys()))
    
    tracked = cursor.fetchall()
    print(f"\n🎯 Tracked Properties (in OwnerDashV2):")
    for name, ah_id, rp_id in tracked:
        unified_id = KAIROI_REALPAGE_SITES.get(rp_id, 'unknown')
        print(f"  - {name}")
        print(f"    AnyoneHome ID: {ah_id}")
        print(f"    RealPage ID: {rp_id}")
        print(f"    Unified ID: {unified_id}")
    
    return {
        'accounts': acc_count,
        'properties': prop_count,
        'mapped_properties': mapped_count,
        'tracked_properties': len(tracked)
    }


def main():
    print("=" * 60)
    print("🏠 AnyoneHome Data Sync - GET ONLY")
    print(f"Started: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Verify middleware is active
    print("\n🛡️  Verifying GET-only middleware...")
    try:
        GetOnlyMiddleware.enforce('POST')
        print("❌ ERROR: Middleware not blocking POST!")
        return
    except PermissionError:
        print("✅ Middleware active - write operations blocked")
    
    # Initialize tables
    init_anyonehome_tables()
    
    # Get client and connect to DB
    client = get_client()
    conn = sqlite3.connect(UNIFIED_DB_PATH)
    
    try:
        # Sync accounts
        sync_accounts(client, conn)
        
        # Sync Kairoi properties
        sync_kairoi_properties(client, conn)
        
        # Get summary
        summary = get_sync_summary(conn)
        
        print("\n" + "=" * 60)
        print("✅ Sync completed successfully!")
        print("=" * 60)
        
    finally:
        conn.close()


if __name__ == "__main__":
    main()
