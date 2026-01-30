"""
Test Script: Execute PostSingleCharge with dummy data
WARNING: This will attempt to post a charge to RealPage
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.clients.realpage_client import RealPageClient


async def execute_dummy_charge():
    """
    Execute PostSingleCharge with dummy resident ID 44529999
    This will attempt to post a charge to RealPage
    """
    
    print("⚠️  WARNING: This will EXECUTE PostSingleCharge")
    print("⚠️  This will attempt to modify data in RealPage")
    print("⚠️  Using dummy resident ID to minimize impact")
    
    client = RealPageClient(
        url='https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc',
        pmcid='4248314123',  # Kairoi Management LLC
        siteid='53752831233',  # The Northern
        licensekey='402b831f-a045-40ce-9ee8-cc2aa6c3ab72'  # Pro license key
    )
    
    # Using dummy resident ID 44529999 (non-existent)
    body_content = f'''<tem:postsinglecharge>
            {client._build_auth_block()}
            <tem:postsinglecharge>
                <tem:residentid>44529999</tem:residentid>
                <tem:transdate>2014-06-30</tem:transdate>
                <tem:transamt>201</tem:transamt>
                <tem:transname>UTILITY</tem:transname>
                <tem:transdesc>TestBatch 1/3/2011</tem:transdesc>
                <tem:docno>123456</tem:docno>
                <tem:transactionbatchid>X1234X12ABZX</tem:transactionbatchid>
                <tem:batchnumber></tem:batchnumber>
                <tem:ExtensionData/>
            </tem:postsinglecharge>
        </tem:postsinglecharge>'''
    
    soap_body = client._build_soap_envelope(body_content)
    
    print("\n📤 Sending SOAP Request:")
    print("=" * 60)
    print(soap_body)
    print("=" * 60)
    
    print("\n🔍 Request Details:")
    print(f"   PMC ID: {client.pmcid}")
    print(f"   Site ID: {client.siteid}")
    print(f"   Resident ID: 44529999 (dummy - should not exist)")
    print(f"   Amount: $201.00")
    print(f"   Transaction: UTILITY")
    print(f"   Date: 2014-06-30")
    
    try:
        print("\n🚀 Executing PostSingleCharge...")
        result = await client._send_request(
            "http://tempuri.org/IRPXService/postsinglecharge",
            soap_body
        )
        
        print("\n✅ Response received:")
        print("-" * 40)
        
        if isinstance(result, dict):
            print(f"Response keys: {list(result.keys())}")
            
            # Look for common response patterns
            if 'postsinglechargeResult' in result:
                charge_result = result['postsinglechargeResult']
                print(f"Charge Result: {charge_result}")
                
                # Check for success indicators
                if isinstance(charge_result, dict):
                    for key, value in charge_result.items():
                        print(f"  {key}: {value}")
            else:
                # Print full response
                def explore(obj, indent=0):
                    prefix = "  " * indent
                    if isinstance(obj, dict):
                        for key, value in obj.items():
                            if isinstance(value, list):
                                print(f"{prefix}{key}: LIST[{len(value)}]")
                                if len(value) <= 5:
                                    for i, item in enumerate(value):
                                        print(f"{prefix}  [{i}]:")
                                        explore(item, indent + 2)
                            elif isinstance(value, dict):
                                print(f"{prefix}{key}:")
                                explore(value, indent + 1)
                            else:
                                print(f"{prefix}{key}: {value}")
                    else:
                        print(f"{prefix}{obj}")
                explore(result)
        else:
            print(f"Raw response: {str(result)[:1000]}")
            
        return result
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("🚫 POSTSINGLECHARGE EXECUTION")
    print("⚠️  THIS WILL ATTEMPT TO POST A CHARGE")
    print("=" * 60)
    
    print("\n📋 CONFIRMATION REQUIRED:")
    print("   - This will send a PostSingleCharge request")
    print("   - Using dummy resident ID 44529999")
    print("   - Amount: $201.00")
    print("   - Transaction: UTILITY")
    print("   - Date: 2014-06-30")
    
    print("\n⚠️  RISKS:")
    print("   - May create a charge record")
    print("   - May modify system state")
    print("   - May trigger notifications")
    print("   - May require manual reversal")
    
    print("\n🚀 Proceeding in 3 seconds...")
    print("   (Press Ctrl+C to cancel)")
    
    import time
    try:
        time.sleep(3)
        asyncio.run(execute_dummy_charge())
    except KeyboardInterrupt:
        print("\n❌ CANCELLED by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
