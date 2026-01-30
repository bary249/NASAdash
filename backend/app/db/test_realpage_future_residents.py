"""
Search for future residents (scheduled move-ins) on Ridian
READ-ONLY: This only fetches data, no modifications.
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

# RealPage credentials
URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"  # Ridian property
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# SOAP envelope for getresidentlist
SOAP_ENVELOPE = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:getresidentlist>
         <tem:auth>
            <tem:pmcid>{PMCID}</tem:pmcid>
            <tem:siteid>{SITEID}</tem:siteid>
            <tem:licensekey>{LICENSEKEY}</tem:licensekey>
         </tem:auth>
         <tem:getresidentlistargs>
            <tem:ExtensionData/>
         </tem:getresidentlistargs>
      </tem:getresidentlist>
   </soapenv:Body>
</soapenv:Envelope>"""

headers = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "http://tempuri.org/IRPXService/getresidentlist"
}

print(f"Searching for FUTURE residents on Ridian (Site ID: {SITEID})")
print("=" * 100)

response = requests.post(URL, data=SOAP_ENVELOPE, headers=headers)

if response.status_code != 200:
    print(f"Error: {response.status_code}")
    print(response.text[:2000])
    exit()

root = ET.fromstring(response.text)
residents = root.findall('.//Resident')

today = datetime.now()
print(f"Today: {today.strftime('%Y-%m-%d')}")
print(f"Total residents found: {len(residents)}")

# Look for future move-ins
print("\n=== FUTURE MOVE-INS (status=Future or move-in date > today) ===\n")
print(f"{'Name':<25} {'Unit':<8} {'Move-In':<15} {'Status':<15} {'Lease Start':<15}")
print("-" * 100)

future_residents = []
for res in residents:
    first = res.findtext('FirstName', '')
    last = res.findtext('LastName', '')
    unit = res.findtext('UnitNumber', '')
    status = res.findtext('ResidentStatus', '')
    move_in = res.findtext('MoveInDate', '').strip()
    lease_start = res.findtext('LeaseStartDate', '').strip()
    
    # Check for future status or future move-in date
    is_future = False
    if status and 'future' in status.lower():
        is_future = True
    if move_in:
        try:
            movein_date = datetime.strptime(move_in.split()[0], '%Y-%m-%d')
            if movein_date >= today:
                is_future = True
        except:
            pass
    
    if is_future:
        future_residents.append({
            'name': f"{first} {last}",
            'unit': unit,
            'move_in': move_in.split()[0] if move_in else '',
            'status': status,
            'lease_start': lease_start.split()[0] if lease_start else ''
        })

# Sort by move-in date
future_residents.sort(key=lambda x: x['move_in'] if x['move_in'] else '9999')

for r in future_residents:
    print(f"{r['name']:<25} {r['unit']:<8} {r['move_in']:<15} {r['status']:<15} {r['lease_start']:<15}")

print(f"\nTotal future move-ins: {len(future_residents)}")

# Also show units 149, 211, 219, 327 specifically
print("\n\n=== CHECKING SPECIFIC UNITS (149, 211, 219, 327) ===\n")
target_units = ['149', '211', '219', '327']
for res in residents:
    unit = res.findtext('UnitNumber', '')
    if unit in target_units:
        print(f"Unit {unit}:")
        print(f"  Name: {res.findtext('FirstName', '')} {res.findtext('LastName', '')}")
        print(f"  Status: {res.findtext('ResidentStatus', '')}")
        print(f"  Move-In: {res.findtext('MoveInDate', '')}")
        print(f"  Lease Start: {res.findtext('LeaseStartDate', '')}")
        print()
