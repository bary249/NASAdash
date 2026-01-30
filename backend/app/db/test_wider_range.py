"""
Test Script: Try wider date range for Andricia Rodriguez ledger
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.clients.realpage_client import RealPageClient


async def try_wider_range():
    client = RealPageClient(
        url='https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc',
        pmcid='4248314',
        siteid='5375283',
        licensekey='402b831f-a045-40ce-9ee8-cc2aa6c3ab72'
    )
    
    print('📅 Trying wider date range for Andricia Rodriguez (resident 379)...')
    
    # Try with allopen=true and wider range
    body = client._build_soap_envelope(f'''
        <tem:getresidentledger>
            {client._build_auth_block()}
            <tem:getresidentledger>
                <tem:reshid>379</tem:reshid>
                <tem:startdate>2024-01-01</tem:startdate>
                <tem:enddate>2025-02-16</tem:enddate>
                <tem:allopen>true</tem:allopen>
                <tem:ExtensionData/>
            </tem:getresidentledger>
        </tem:getresidentledger>
    ''')
    
    result = await client._send_request('http://tempuri.org/IRPXService/getresidentledger', body)
    
    # Check if we have diffgram data
    result_path = result.get('getresidentledgerResult', {}).get('GetResidentLedger', {}).get('GetResidentLedgerResult', {})
    
    if 'diffgram' in result_path:
        diffgram = result_path['diffgram']
        print('✅ Found diffgram data!')
        
        resident_data = diffgram.get('ResidentDataSet', {})
        
        # Check ResidentInfo
        resident_info = resident_data.get('ResidentInfo')
        if resident_info:
            print(f'👤 Found resident info')
            if isinstance(resident_info, dict):
                print(f'   Name: {resident_info.get("resmFirstName", "N/A")} {resident_info.get("resmLastName", "N/A")}')
                print(f'   Balance: {resident_info.get("ReshBal", "N/A")}')
            elif isinstance(resident_info, list):
                print(f'   Found {len(resident_info)} resident records')
        
        # Check ResidentLedgerDetails
        ledger_details = resident_data.get('ResidentLedgerDetails')
        if ledger_details:
            print(f'📊 Found ledger details')
            if isinstance(ledger_details, list):
                print(f'   Found {len(ledger_details)} transactions')
                # Show recent ones
                for i, trans in enumerate(ledger_details[:5]):
                    trans_date = trans.get("TransDate", "N/A")[:10] if trans.get("TransDate") else "N/A"
                    trans_name = trans.get("TrancName", "N/A")
                    trans_desc = trans.get("TrancDesc", "N/A")
                    amt = trans.get("Amt", "N/A")
                    print(f'   {i+1}. {trans_date} - {trans_name} - ${amt} - {trans_desc}')
            elif isinstance(ledger_details, dict):
                print(f'   Found 1 transaction')
                trans_date = ledger_details.get("TransDate", "N/A")[:10] if ledger_details.get("TransDate") else "N/A"
                print(f'   {trans_date} - {ledger_details.get("TrancName", "N/A")} - ${ledger_details.get("Amt", "N/A")} - {ledger_details.get("TrancDesc", "N/A")}')
        else:
            print('❌ No ledger details found')
    else:
        print('❌ No diffgram data found')
        print('Available keys:', list(result_path.keys()))


if __name__ == "__main__":
    asyncio.run(try_wider_range())
