"""
Debug Ridian: Get residents with Applicant status and show 3 units with market rent
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# Get residents
SOAP_RES = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
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

# Get units
SOAP_UNITS = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
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

print("=" * 80)
print("RIDIAN DEBUG: Future Residents (Applicant - Lease Signed)")
print("=" * 80)

resp = requests.post(URL, data=SOAP_RES, headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "http://tempuri.org/IRPXService/getresidentlist"})
root = ET.fromstring(resp.text)
residents = root.findall('.//resident')

print(f"\nTotal residents: {len(residents)}")
print("\nResidents with 'Applicant' in leasestatus:")
print("-" * 80)

applicants = []
for res in residents:
    status = res.findtext('leasestatus', '')
    if 'applicant' in status.lower():
        applicants.append({
            'name': f"{res.findtext('firstname', '')} {res.findtext('lastname', '')}",
            'unit': res.findtext('unitnumber', ''),
            'status': status,
            'balance': res.findtext('balance', '')
        })
        print(f"  {applicants[-1]['name']:<25} Unit {applicants[-1]['unit']:<6} Status: {applicants[-1]['status']}")

print(f"\nTotal applicants (future move-ins): {len(applicants)}")

print("\n" + "=" * 80)
print("3 SAMPLE UNITS WITH MARKET RENT")
print("=" * 80)

resp2 = requests.post(URL, data=SOAP_UNITS, headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "http://tempuri.org/IRPXService/unitlist"})
root2 = ET.fromstring(resp2.text)
units = root2.findall('.//Unit')

print(f"\nTotal units: {len(units)}")
print("\n3 Sample Units:")
print("-" * 80)

for i, unit in enumerate(units[:3]):
    print(f"\nUnit {i+1}:")
    print(f"  UnitNumber:    {unit.findtext('UnitNumber', '')}")
    print(f"  FloorplanName: {unit.findtext('FloorplanName', '')}")
    print(f"  Bedrooms:      {unit.findtext('Bedrooms', '')}")
    print(f"  Bathrooms:     {unit.findtext('Bathrooms', '')}")
    print(f"  RentableSqft:  {unit.findtext('RentableSqft', '')}")
    print(f"  MarketRent:    ${unit.findtext('MarketRent', '0')}")
    print(f"  Vacant:        {unit.findtext('Vacant', '')}")
    print(f"  Available:     {unit.findtext('Available', '')}")

# Show all unique lease statuses
print("\n" + "=" * 80)
print("ALL UNIQUE LEASE STATUSES IN RESIDENTS")
print("=" * 80)
statuses = {}
for res in residents:
    status = res.findtext('leasestatus', 'Unknown')
    statuses[status] = statuses.get(status, 0) + 1

for status, count in sorted(statuses.items()):
    print(f"  {status}: {count}")
