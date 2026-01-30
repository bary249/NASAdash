"""
Test Script: Call RealPage transactioncodes API (GET/READ-ONLY)
Tests the transactioncodes endpoint with catcode=P, cashtype=A
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.clients.realpage_client import RealPageClient


async def test_transaction_codes(client: RealPageClient):
    """Test transactioncodes endpoint."""
    print("\n" + "=" * 60)
    print("Testing transactioncodes (catcode=P, cashtype=A)")
    print("=" * 60)
    
    # Build the SOAP request based on user's template
    body_content = f"""<tem:transactioncodes>
            {client._build_auth_block()}
            <tem:transactioncodes>
                <tem:catcode>P</tem:catcode>
                <tem:cashtype>A</tem:cashtype>
                <tem:ExtensionData/>
            </tem:transactioncodes>
        </tem:transactioncodes>"""
    
    soap_body = client._build_soap_envelope(body_content)
    
    print("\n📤 SOAP Request:")
    print("-" * 40)
    print(soap_body)
    
    try:
        result = await client._send_request(
            "http://tempuri.org/IRPXService/transactioncodes",
            soap_body
        )
        print(f"\n✅ SUCCESS! Got response:")
        print("-" * 40)
        
        if isinstance(result, dict):
            print(f"Keys: {list(result.keys())}")
            # Recursively explore the response
            def explore(obj, indent=0):
                prefix = "  " * indent
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if isinstance(value, list):
                            print(f"{prefix}{key}: LIST[{len(value)}]")
                            if value and len(value) <= 30:
                                for i, item in enumerate(value):
                                    print(f"{prefix}  [{i}]:")
                                    explore(item, indent + 2)
                            elif value:
                                print(f"{prefix}  (showing first 5 of {len(value)})")
                                for i, item in enumerate(value[:5]):
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
            print(f"Raw: {str(result)[:1000]}")
            
        return result
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None


async def main():
    """Run the test."""
    print("🔌 Initializing RealPage client...")
    
    # Using Venn (RealPage) environment credentials
    client = RealPageClient(
        url="https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc",
        pmcid="5230170",
        siteid="5230176",
        licensekey="402b831f-a045-40ce-9ee8-cc2aa6c3ab72"
    )
    
    print(f"   URL: {client.url}")
    print(f"   PMC ID: {client.pmcid}")
    print(f"   Site ID: {client.siteid}")
    
    await test_transaction_codes(client)


if __name__ == "__main__":
    asyncio.run(main())
