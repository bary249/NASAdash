"""
Check ALL units with expected move-in dates on Ridian
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

response = requests.post(URL, data=SOAP_ENVELOPE, headers=headers)
root = ET.fromstring(response.text)
units = root.findall('.//Unit')

today = datetime.now()
print(f"Today: {today.strftime('%Y-%m-%d')}")
print("=" * 100)

# Check ALL units with expected move-in dates
print("\n=== ALL UNITS WITH EXPECTED MOVE-IN DATES ===\n")
print(f"{'Unit':<8} {'Expected Move-In':<20} {'Vacant':<8} {'Avail':<8} {'On Notice Date':<20} {'Status'}")
print("-" * 100)

units_with_movein = []
for unit in units:
    expected_movein = unit.findtext('UnitExpectedMoveinDate', '').strip()
    if expected_movein:
        unit_number = unit.findtext('UnitNumber', '')
        vacant = unit.findtext('Vacant', '')
        available = unit.findtext('Available', '')
        on_notice = unit.findtext('OnNoticeForDate', '').strip()
        
        # Determine status
        try:
            movein_date = datetime.strptime(expected_movein.split()[0], '%Y-%m-%d')
            if movein_date >= today:
                status = "FUTURE"
            else:
                status = "PAST"
        except:
            status = "?"
        
        units_with_movein.append({
            'unit': unit_number,
            'movein': expected_movein,
            'vacant': vacant,
            'available': available,
            'on_notice': on_notice,
            'status': status
        })

units_with_movein.sort(key=lambda x: x['movein'], reverse=True)

for u in units_with_movein:
    print(f"{u['unit']:<8} {u['movein']:<20} {u['vacant']:<8} {u['available']:<8} {u['on_notice']:<20} {u['status']}")

print(f"\nTotal units: {len(units)}")
print(f"Units with any expected move-in: {len(units_with_movein)}")
print(f"Future move-ins: {sum(1 for u in units_with_movein if u['status'] == 'FUTURE')}")

# Also check vacant units
print("\n\n=== VACANT UNITS ===\n")
vacant_units = [u for u in units if u.findtext('Vacant', '') == 'T']
print(f"{'Unit':<8} {'Available':<10} {'Expected Move-In':<20} {'Available Date':<20}")
print("-" * 70)
for unit in vacant_units:
    print(f"{unit.findtext('UnitNumber', ''):<8} {unit.findtext('Available', ''):<10} {unit.findtext('UnitExpectedMoveinDate', '').strip():<20} {unit.findtext('AvailableDate', '').strip():<20}")

print(f"\nTotal vacant: {len(vacant_units)}")
