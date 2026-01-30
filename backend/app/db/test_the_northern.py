"""
Test Script: Get residents and ledger for unit 934 at The Northern (site 5375283)
PMC: 4248314 (Kairoi Management LLC)
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from app.clients.realpage_client import RealPageClient


async def check_site_5375283():
    client = RealPageClient(
        url='https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc',
        pmcid='4248314',  # Kairoi Management LLC
        siteid='5375283',  # The Northern
        licensekey='402b831f-a045-40ce-9ee8-cc2aa6c3ab72'
    )
    
    print('🔍 Checking site 5375283 (The Northern) with PMC 4248314 (Kairoi Management)...')
    
    try:
        # Get all residents
        residents = await client.get_residents('5375283', status='current')
        print(f'Total residents: {len(residents)}')
        
        # Get units
        units = await client.get_units('5375283')
        print(f'Total units: {len(units)}')
        
        # Look for unit 934
        unit_934 = [u for u in units if u.get('unit_number') == '934']
        if unit_934:
            print(f'✅ Unit 934 found: {unit_934[0].get("status")} - {unit_934[0].get("floorplan_name")}')
            
            # Find residents in unit 934
            unit_934_residents = [r for r in residents if r.get('unit_number') == '934']
            print(f'Residents in unit 934: {len(unit_934_residents)}')
            
            for r in unit_934_residents:
                print(f'  Resident ID: {r.get("resident_id")} - {r.get("first_name")} {r.get("last_name")}')
                
                # Get ledger for this resident
                res_id = r.get('resident_id')
                print(f'  📋 Getting ledger for resident {res_id}...')
                
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
                        print(f'    Balance: {resident_info.get("ReshBal", "N/A")}')
                        print(f'    Current Due: {resident_info.get("CurrentDue", "N/A")}')
                        print(f'    Past Due: {resident_info.get("PastDue", "N/A")}')
                    
                    # Show recent transactions
                    ledger_details = result.get('getresidentledgerResult', {}).get('GetResidentLedger', {}).get('GetResidentLedgerResult', {}).get('diffgram', {}).get('ResidentDataSet', {}).get('ResidentLedgerDetails', [])
                    if isinstance(ledger_details, list):
                        print(f'    Recent transactions (showing first 3):')
                        for i, trans in enumerate(ledger_details[:3]):
                            print(f'      {i+1}. {trans.get("TransDate", "N/A")} - {trans.get("TrancName", "N/A")} - ${trans.get("Amt", "N/A")} - {trans.get("TrancDesc", "N/A")}')
                    elif isinstance(ledger_details, dict):
                        print(f'    Recent transaction: {ledger_details.get("TransDate", "N/A")} - {ledger_details.get("TrancName", "N/A")} - ${ledger_details.get("Amt", "N/A")} - {ledger_details.get("TrancDesc", "N/A")}')
                        
                except Exception as e:
                    print(f'    Error parsing ledger: {e}')
        else:
            print(f'❌ Unit 934 not found')
            # Show sample units
            print(f'\nSample units at The Northern:')
            for i, unit in enumerate(units[:10]):
                print(f'  {unit.get("unit_number")} - {unit.get("status")} - {unit.get("floorplan_name")}')
                
    except Exception as e:
        print(f'Error accessing site: {e}')


if __name__ == "__main__":
    asyncio.run(check_site_5375283())
