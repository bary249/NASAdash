"""
Test Script: Call missing RealPage APIs to see if they return data.

Tests:
1. getRentableItems - amenity fees, charges, concessions
2. getRoommate - roommates for a lease
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.clients.realpage_client import RealPageClient


async def test_get_rentable_items(client: RealPageClient):
    """Test getRentableItems endpoint."""
    print("\n" + "=" * 60)
    print("Testing getRentableItems")
    print("=" * 60)
    
    # Build the SOAP request based on Postman collection
    body_content = f"""<tem:getrentableitems>
            {client._build_auth_block()}
            <tem:getrentableitemRequest>
                <tem:unitid>0</tem:unitid>
                <tem:dateneeded>2025-02-01</tem:dateneeded>
                <tem:leaseid>0</tem:leaseid>
            </tem:getrentableitemRequest>
        </tem:getrentableitems>"""
    
    soap_body = client._build_soap_envelope(body_content)
    
    try:
        result = await client._send_request(
            "http://tempuri.org/IRPXService/getrentableitems",
            soap_body
        )
        print(f"\n✅ SUCCESS! Got response:")
        print(f"   Type: {type(result)}")
        
        if isinstance(result, dict):
            print(f"   Keys: {list(result.keys())[:10]}")
            # Recursively explore the response
            def explore(obj, indent=3):
                prefix = "   " * indent
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if isinstance(value, list):
                            print(f"{prefix}{key}: LIST[{len(value)}]")
                            if value and len(value) <= 20:
                                for i, item in enumerate(value[:5]):
                                    print(f"{prefix}  [{i}]:")
                                    explore(item, indent + 2)
                            elif value:
                                print(f"{prefix}  (showing first 3 of {len(value)})")
                                for i, item in enumerate(value[:3]):
                                    print(f"{prefix}  [{i}]:")
                                    explore(item, indent + 2)
                        elif isinstance(value, dict):
                            print(f"{prefix}{key}: DICT")
                            explore(value, indent + 1)
                        else:
                            print(f"{prefix}{key}: {value}")
                else:
                    print(f"{prefix}{obj}")
            explore(result)
        else:
            print(f"   Raw: {str(result)[:500]}")
            
        return result
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return None


async def test_get_roommate(client: RealPageClient, lease_id: str = "984"):
    """Test getRoommate endpoint."""
    print("\n" + "=" * 60)
    print(f"Testing getRoommate (lease_id={lease_id})")
    print("=" * 60)
    
    # Build the SOAP request based on Postman collection
    body_content = f"""<tem:GetRoomates>
            {client._build_auth_block()}
            <tem:parameter>
                <tem:LeaseID>{lease_id}</tem:LeaseID>
            </tem:parameter>
        </tem:GetRoomates>"""
    
    soap_body = client._build_soap_envelope(body_content)
    
    try:
        result = await client._send_request(
            "http://tempuri.org/IRPXService/getroomates",
            soap_body
        )
        print(f"\n✅ SUCCESS! Got response:")
        print(f"   Type: {type(result)}")
        
        if isinstance(result, dict):
            print(f"   Keys: {list(result.keys())[:10]}")
            for key, value in result.items():
                if isinstance(value, list):
                    print(f"\n   Found list '{key}' with {len(value)} items")
                    if value and isinstance(value[0], dict):
                        print(f"   First item keys: {list(value[0].keys())}")
                        print(f"   Sample: {value[0]}")
        else:
            print(f"   Raw: {str(result)[:500]}")
            
        return result
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return None


async def main():
    print("=" * 60)
    print("RealPage Missing API Test")
    print("=" * 60)
    
    client = RealPageClient()
    
    if not client.url or not client.pmcid or not client.siteid:
        print("❌ RealPage credentials not configured")
        return
    
    print(f"\nUsing credentials:")
    print(f"  URL: {client.url}")
    print(f"  PMC ID: {client.pmcid}")
    print(f"  Site ID: {client.siteid}")
    
    # Test getRentableItems
    rentable_result = await test_get_rentable_items(client)
    
    # Get lease IDs directly from getleaseinfo API
    print("\n" + "=" * 60)
    print("Getting raw lease data to find lease IDs...")
    print("=" * 60)
    
    try:
        # Call getleaseinfo directly to see the raw response
        body_content = f"""<tem:getleaseinfo>
            {client._build_auth_block()}
            <tem:getleaseinfo>
                <tem:residentstatus>C</tem:residentstatus>
                <tem:residentheldthestatus>30</tem:residentheldthestatus>
            </tem:getleaseinfo>
        </tem:getleaseinfo>"""
        
        soap_body = client._build_soap_envelope(body_content)
        result = await client._send_request(
            "http://tempuri.org/IRPXService/getleaseinfo",
            soap_body
        )
        
        print("  Raw lease response structure:")
        print(f"  Top-level keys: {list(result.keys())}")
        # Find leases in response
        if 'getleaseinfoResult' in result:
            lease_result = result['getleaseinfoResult']
            print(f"  getleaseinfoResult keys: {list(lease_result.keys()) if isinstance(lease_result, dict) else lease_result}")
            
            # Navigate to leases - structure is GetLeaseInfo -> Leases
            if 'GetLeaseInfo' in lease_result:
                get_lease_info = lease_result['GetLeaseInfo']
                print(f"  GetLeaseInfo keys: {list(get_lease_info.keys()) if isinstance(get_lease_info, dict) else get_lease_info}")
                
                # Leases are directly under GetLeaseInfo.Leases
                leases_container = get_lease_info.get('Leases', {})
                print(f"  Leases container: {list(leases_container.keys()) if isinstance(leases_container, dict) else type(leases_container)}")
                
                leases = leases_container.get('Lease', []) if isinstance(leases_container, dict) else []
                if not isinstance(leases, list):
                    leases = [leases] if leases else []
                print(f"  Found {len(leases)} leases")
                if leases:
                    print(f"  First lease keys: {list(leases[0].keys())}")
                    print(f"  First lease sample: {leases[0]}")
                    
                    # Try getRoommate with first lease
                    lease_id = leases[0].get('LeaseID')
                    if lease_id:
                        print(f"\n  Testing getRoommate with LeaseID: {lease_id}")
                        await test_get_roommate(client, str(lease_id))
    except Exception as e:
        print(f"  Error: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n" + "=" * 60)
    print("Test Complete")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
