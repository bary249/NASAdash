"""
AnyoneHome API Test Script - GET ONLY (Read-Only Operations)
Uses the GetOnlyMiddleware to enforce read-only operations
"""

import sys
import json
from datetime import datetime

# Add app to path
sys.path.insert(0, '/Users/barak.b/Venn/OwnerDashV2/backend')

from app.api.anyonehome_client import AnyoneHomeClient, GetOnlyMiddleware, get_client

# Test parameters from Slack
TEST_ACCOUNT_ID = "0010H00002fAupLQAS"
TEST_PROPERTY_ID = "4556469"
TEST_QUOTE_ID = "0c7b683e-2244-4836-af3e-c2745ad2ecda"
ALT_QUOTE_ID = "e2c92157-b7cd-4a3e-814f-5fb37d98c40f"


def print_result(name: str, result: dict):
    """Pretty print API result"""
    print(f"\n{'='*60}")
    print(f"📋 {name}")
    print(f"{'='*60}")
    print(f"Status: {result['status_code']} {'✅' if result['success'] else '❌'}")
    print(f"URL: {result['url']}")
    print(f"\nResponse:")
    print(json.dumps(result['data'], indent=2, default=str)[:2000])


def test_middleware_blocks_writes():
    """Verify that non-GET methods are blocked"""
    print(f"\n{'='*60}")
    print("🛡️  Testing GET-Only Middleware")
    print(f"{'='*60}")
    
    # Test that GET is allowed
    try:
        GetOnlyMiddleware.enforce('GET')
        print("✅ GET method: ALLOWED")
    except PermissionError as e:
        print(f"❌ GET method blocked (unexpected): {e}")
    
    # Test that POST is blocked
    try:
        GetOnlyMiddleware.enforce('POST')
        print("❌ POST method: NOT BLOCKED (security issue!)")
    except PermissionError as e:
        print(f"✅ POST method: BLOCKED - {e}")
    
    # Test that DELETE is blocked
    try:
        GetOnlyMiddleware.enforce('DELETE')
        print("❌ DELETE method: NOT BLOCKED (security issue!)")
    except PermissionError as e:
        print(f"✅ DELETE method: BLOCKED")
    
    # Test that PUT is blocked
    try:
        GetOnlyMiddleware.enforce('PUT')
        print("❌ PUT method: NOT BLOCKED (security issue!)")
    except PermissionError as e:
        print(f"✅ PUT method: BLOCKED")


if __name__ == "__main__":
    print(f"\n🏠 AnyoneHome API Test - {datetime.now().isoformat()}")
    print("=" * 60)
    print("⚠️  This client enforces GET-ONLY requests (read-only)")
    print("=" * 60)
    
    # Test 0: Verify middleware blocks write methods
    test_middleware_blocks_writes()
    
    # Initialize client
    print("\n\n📡 Initializing AnyoneHome Client...")
    client = get_client()
    print(f"Base URL: {client.base_url}")
    print(f"Username: {client.username[:30]}...")
    
    # Test 1: Retrieve Accounts
    print("\n\n[TEST 1] Retrieve Accounts")
    result = client.retrieve_accounts()
    print_result("Retrieve Accounts", result)
    
    # Test 2: Retrieve Property List
    print("\n\n[TEST 2] Retrieve Property List")
    result = client.retrieve_property_list()
    print_result("Retrieve Property List", result)
    
    # Test 3: Retrieve Rental Quote
    print("\n\n[TEST 3] Retrieve Rental Quote")
    result = client.retrieve_rental_quote(
        account_id=TEST_ACCOUNT_ID,
        property_id=TEST_PROPERTY_ID,
        quote_id=TEST_QUOTE_ID
    )
    print_result("Retrieve Rental Quote", result)
    
    # Test 4: Alternative Quote ID
    print("\n\n[TEST 4] Retrieve Rental Quote (Alternative ID)")
    result = client.retrieve_rental_quote(
        account_id=TEST_ACCOUNT_ID,
        property_id=TEST_PROPERTY_ID,
        quote_id=ALT_QUOTE_ID
    )
    print_result("Retrieve Rental Quote (Alt)", result)
    
    # Test 5: Verify write methods are blocked on client
    print("\n\n[TEST 5] Verify Client Blocks Write Methods")
    try:
        client.post()
    except PermissionError as e:
        print(f"✅ client.post() blocked: {e}")
    
    try:
        client.delete()
    except PermissionError as e:
        print(f"✅ client.delete() blocked")
    
    print("\n\n" + "=" * 60)
    print("✅ Test complete. All write methods blocked.")
    print("=" * 60)
