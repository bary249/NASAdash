"""
Test Script: Get detailed ledger for Andricia Rodriguez (resident 379) in unit 934
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.clients.realpage_client import RealPageClient


async def get_andricia_ledger():
    client = RealPageClient(
        url='https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc',
        pmcid='4248314',  # Kairoi Management LLC
        siteid='5375283',  # The Northern
        licensekey='402b831f-a045-40ce-9ee8-cc2aa6c3ab72'
    )
    
    print('📋 Getting detailed ledger for Andricia Rodriguez (resident 379) in unit 934...')
    
    # Get ledger for resident 379
    body = client._build_soap_envelope(f'''
        <tem:getresidentledger>
            {client._build_auth_block()}
            <tem:getresidentledger>
                <tem:reshid>379</tem:reshid>
                <tem:startdate>2025-01-01</tem:startdate>
                <tem:enddate>2025-02-16</tem:enddate>
                <tem:allopen>false</tem:allopen>
                <tem:ExtensionData/>
            </tem:getresidentledger>
        </tem:getresidentledger>
    ''')
    
    result = await client._send_request('http://tempuri.org/IRPXService/getresidentledger', body)
    
    # Extract and display resident info
    try:
        diffgram = result.get('getresidentledgerResult', {}).get('GetResidentLedger', {}).get('GetResidentLedgerResult', {}).get('diffgram', {})
        resident_data = diffgram.get('ResidentDataSet', {})
        
        # Resident info
        resident_info = resident_data.get('ResidentInfo', {})
        if isinstance(resident_info, dict):
            print(f'\n👤 Resident Info:')
            print(f'  Name: {resident_info.get("resmFirstName", "N/A")} {resident_info.get("resmLastName", "N/A")}')
            print(f'  Unit: {resident_info.get("UnitNumber", "N/A")}')
            print(f'  Balance: ${resident_info.get("ReshBal", "N/A")}')
            print(f'  Current Due: ${resident_info.get("CurrentDue", "N/A")}')
            print(f'  Past Due: ${resident_info.get("PastDue", "N/A")}')
        
        # Ledger details
        ledger_details = resident_data.get('ResidentLedgerDetails', [])
        if isinstance(ledger_details, list):
            print(f'\n📊 Recent Transactions ({len(ledger_details)} total):')
            for i, trans in enumerate(ledger_details[:10]):
                trans_date = trans.get("TransDate", "N/A")[:10] if trans.get("TransDate") else "N/A"
                trans_name = trans.get("TrancName", "N/A")
                trans_desc = trans.get("TrancDesc", "N/A")
                amt = trans.get("Amt", "N/A")
                print(f'  {i+1}. {trans_date} - {trans_name} - ${amt} - {trans_desc}')
                
                # Look for the amenity charge from your data
                if "amenity" in str(trans_desc).lower() and "sky lounge" in str(trans_desc).lower():
                    print(f'      ⭐ MATCH: This looks like your amenity charge!')
        elif isinstance(ledger_details, dict):
            print(f'\n📊 Recent Transaction:')
            trans_date = ledger_details.get("TransDate", "N/A")[:10] if ledger_details.get("TransDate") else "N/A"
            print(f'  {trans_date} - {ledger_details.get("TrancName", "N/A")} - ${ledger_details.get("Amt", "N/A")} - {ledger_details.get("TrancDesc", "N/A")}')
        else:
            print(f'\n📊 No ledger details found')
            
    except Exception as e:
        print(f'Error parsing ledger: {e}')
        print(f'Raw result keys: {list(result.keys()) if isinstance(result, dict) else "Not a dict"}')


if __name__ == "__main__":
    asyncio.run(get_andricia_ledger())
