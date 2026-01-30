"""
Test Script: Get residents and ledger for unit 934 at site 5375283
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.clients.realpage_client import RealPageClient


async def get_unit_residents():
    client = RealPageClient(
        url='https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc',
        pmcid='5230170',
        siteid='5375283',
        licensekey='402b831f-a045-40ce-9ee8-cc2aa6c3ab72'
    )
    
    print('🔍 Finding residents for unit 934 at site 5375283...')
    
    # Get all residents for the site
    residents = await client.get_residents('5375283', status='current')
    
    # Find unit 934
    unit_934_residents = [r for r in residents if r.get('unit_number') == '934']
    
    print(f'Found {len(unit_934_residents)} residents in unit 934:')
    for r in unit_934_residents:
        print(f'  Resident ID: {r.get("resident_id")}')
        print(f'  Name: {r.get("first_name")} {r.get("last_name")}')
        print(f'  Unit: {r.get("unit_number")}')
        print(f'  Status: {r.get("status")}')
        print()
    
    if unit_934_residents:
        # Get ledger for first resident
        resident = unit_934_residents[0]
        res_id = resident.get('resident_id')
        print(f'📋 Getting ledger for resident {res_id}...')
        
        body = client._build_soap_envelope(f'''
            <tem:getresidentledger>
                {client._build_auth_block()}
                <tem:getresidentledger>
                    <tem:reshid>{res_id}</tem:reshid>
                    <tem:startdate>2024-01-01</tem:startdate>
                    <tem:enddate>2025-02-16</tem:enddate>
                    <tem:allopen>false</tem:allopen>
                    <tem:ExtensionData/>
                </tem:getresidentledger>
            </tem:getresidentledger>
        ''')
        
        result = await client._send_request('http://tempuri.org/IRPXService/getresidentledger', body)
        
        # Extract key info
        try:
            resident_info = result.get('getresidentledgerResult', {}).get('GetResidentLedger', {}).get('GetResidentLedgerResult', {}).get('diffgram', {}).get('ResidentDataSet', {}).get('ResidentInfo', {})
            if isinstance(resident_info, dict):
                print(f'Resident Balance: {resident_info.get("ReshBal", "N/A")}')
                print(f'Current Due: {resident_info.get("CurrentDue", "N/A")}')
                print(f'Past Due: {resident_info.get("PastDue", "N/A")}')
            
            # Show recent transactions
            ledger_details = result.get('getresidentledgerResult', {}).get('GetResidentLedger', {}).get('GetResidentLedgerResult', {}).get('diffgram', {}).get('ResidentDataSet', {}).get('ResidentLedgerDetails', [])
            if isinstance(ledger_details, list):
                print(f'Recent transactions (showing first 5):')
                for i, trans in enumerate(ledger_details[:5]):
                    print(f'  {i+1}. {trans.get("TransDate", "N/A")} - {trans.get("TrancName", "N/A")} - ${trans.get("Amt", "N/A")} - {trans.get("TrancDesc", "N/A")}')
            elif isinstance(ledger_details, dict):
                print(f'Recent transaction: {ledger_details.get("TransDate", "N/A")} - {ledger_details.get("TrancName", "N/A")} - ${ledger_details.get("Amt", "N/A")} - {ledger_details.get("TrancDesc", "N/A")}')
                
        except Exception as e:
            print(f'Error parsing ledger: {e}')
    else:
        print('No residents found in unit 934')


if __name__ == "__main__":
    asyncio.run(get_unit_residents())
