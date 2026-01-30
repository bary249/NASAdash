"""
Search Ridian units for future expected move-in dates
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

# SOAP envelope for unitlist
SOAP_ENVELOPE = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:unitlist>
         <tem:auth>
            <tem:pmcid>{PMCID}</tem:pmcid>
            <tem:siteid>{SITEID}</tem:siteid>
            <tem:licensekey>{LICENSEKEY}</tem:licensekey>
         </tem:auth>
         <tem:getunitlist>
            <tem:ExtensionData/>
         </tem:getunitlist>
      </tem:unitlist>
   </soapenv:Body>
</soapenv:Envelope>"""

headers = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "http://tempuri.org/IRPXService/unitlist"
}

print(f"Searching for units with FUTURE expected move-in dates on Ridian (Site ID: {SITEID})")
print("=" * 80)

response = requests.post(URL, data=SOAP_ENVELOPE, headers=headers)

if response.status_code != 200:
    print(f"Error: {response.status_code}")
    exit()

# Parse XML response
root = ET.fromstring(response.text)

# Find all Unit elements (handle namespaces)
units = root.findall('.//{http://tempuri.org/}unitlistResult//Unit') or root.findall('.//Unit')

today = datetime.now()
future_moveins = []

for unit in units:
    unit_number = unit.findtext('UnitNumber', '')
    expected_movein = unit.findtext('UnitExpectedMoveinDate', '')
    vacant = unit.findtext('Vacant', '')
    available = unit.findtext('Available', '')
    market_rent = unit.findtext('MarketRent', '')
    floorplan = unit.findtext('FloorplanName', '')
    sqft = unit.findtext('RentableSqft', '')
    on_notice_date = unit.findtext('OnNoticeForDate', '')
    available_date = unit.findtext('AvailableDate', '')
    
    # Check if has future move-in date
    if expected_movein and expected_movein.strip():
        try:
            movein_date = datetime.strptime(expected_movein.split()[0], '%Y-%m-%d')
            if movein_date >= today:
                future_moveins.append({
                    'unit': unit_number,
                    'expected_movein': expected_movein.split()[0],
                    'vacant': vacant,
                    'available': available,
                    'market_rent': market_rent,
                    'floorplan': floorplan,
                    'sqft': sqft,
                    'on_notice': on_notice_date,
                    'available_date': available_date.split()[0] if available_date else ''
                })
        except:
            pass

# Sort by move-in date
future_moveins.sort(key=lambda x: x['expected_movein'])

print(f"\nFound {len(future_moveins)} units with FUTURE expected move-in dates:\n")
print(f"{'Unit':<8} {'Move-In Date':<14} {'Vacant':<8} {'Avail':<8} {'Floorplan':<10} {'SqFt':<8} {'Rent':<10}")
print("-" * 80)

for u in future_moveins:
    print(f"{u['unit']:<8} {u['expected_movein']:<14} {u['vacant']:<8} {u['available']:<8} {u['floorplan']:<10} {u['sqft']:<8} ${u['market_rent']:<10}")

print(f"\nTotal units in property: {len(units)}")
print(f"Units with future move-ins: {len(future_moveins)}")
