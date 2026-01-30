"""
Test Script: PostSingleCharge API (FOR PREPARATION ONLY - DO NOT EXECUTE)
This script prepares the PostSingleCharge API call but should NOT be run
as it would modify data in the production system.

Prepared with dummy data from API example using Pro license key.
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.clients.realpage_client import RealPageClient


async def prepare_postsinglecharge():
    """
    PREPARATION ONLY - DO NOT EXECUTE
    This would post a charge to RealPage, which is not allowed.
    """
    
    print("⚠️  WARNING: This script is for PREPARATION ONLY")
    print("⚠️  DO NOT EXECUTE - This would modify production data")
    print("⚠️  PostSingleCharge is a write operation")
    
    client = RealPageClient(
        url='https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc',
        pmcid='4248314',  # Kairoi Management LLC
        siteid='5375283',  # The Northern
        licensekey='402b831f-a045-40ce-9ee8-cc2aa6c3ab72'  # Pro license key
    )
    
    # Using dummy data from API example
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
    
    print("\n📤 Prepared SOAP Request (DO NOT SEND):")
    print("=" * 60)
    print(soap_body)
    print("=" * 60)
    
    print("\n🔍 Request Analysis:")
    print(f"   PMC ID: {client.pmcid}")
    print(f"   Site ID: {client.siteid}")
    print(f"   License Key: {client.licensekey}")
    print(f"   Resident ID: 4452 (dummy)")
    print(f"   Transaction Date: 2014-06-30")
    print(f"   Amount: $201.00")
    print(f"   Transaction Name: UTILITY")
    print(f"   Description: TestBatch 1/3/2011")
    print(f"   Document Number: 123456")
    print(f"   Batch ID: X1234X12ABZX")
    
    print("\n❌ THIS WOULD:")
    print("   - Create a $201 UTILITY charge for resident 4452")
    print("   - Modify the resident's ledger")
    print("   - Create a permanent financial record")
    print("   - Potentially trigger billing notifications")
    
    print("\n✅ To safely test this:")
    print("   1. Use a test/sandbox environment")
    print("   2. Get explicit approval from RealPage")
    print("   3. Have a reversal plan ready")
    print("   4. Use a test resident ID, not real ones")

    print("🚫 POSTSINGLECHARGE TEST PREPARATION")
    print("🚫 READ-ONLY MODE - NO EXECUTION")
    print("=" * 60)
    
    # This will prepare the requests but not send them
    asyncio.run(prepare_postsinglecharge())
    asyncio.run(prepare_real_amenity_charge())
    
    print("\n" + "=" * 60)
    print("📝 SUMMARY:")
    print("✅ Both requests prepared successfully")
    print("❌ DO NOT EXECUTE - These would modify production data")
    print("🔧 Use only in approved test environment")
    print("=" * 60)
