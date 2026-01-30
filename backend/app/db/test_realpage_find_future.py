"""
Find future residents by leasestatus and specific names
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"  # Ridian
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

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

response = requests.post(URL, data=SOAP_ENVELOPE, headers=headers)
root = ET.fromstring(response.text)
residents = root.findall('.//resident')

print(f"Total residents: {len(residents)}")

# Look for Future status
print("\n=== RESIDENTS WITH 'FUTURE' LEASE STATUS ===")
future_count = 0
for res in residents:
    status = res.findtext('leasestatus', '').lower()
    if 'future' in status:
        future_count += 1
        print(f"  {res.findtext('firstname', '')} {res.findtext('lastname', '')} - Unit {res.findtext('unitnumber', '')} - Status: {res.findtext('leasestatus', '')}")

print(f"Found: {future_count}")

# Search for specific names from screenshot
target_names = ['yoshida', 'heyde', 'lippert', 'bahrami']
print("\n=== SEARCHING FOR SPECIFIC NAMES ===")
for res in residents:
    first = res.findtext('firstname', '').lower()
    last = res.findtext('lastname', '').lower()
    if any(name in last for name in target_names):
        print(f"  {res.findtext('firstname', '')} {res.findtext('lastname', '')} - Unit {res.findtext('unitnumber', '')} - Status: {res.findtext('leasestatus', '')}")

# Show all unique lease statuses
print("\n=== ALL UNIQUE LEASE STATUSES ===")
statuses = set()
for res in residents:
    statuses.add(res.findtext('leasestatus', ''))
for s in sorted(statuses):
    print(f"  - {s}")

# Search for units 149, 211, 219, 327
print("\n=== RESIDENTS IN UNITS 149, 211, 219, 327 ===")
target_units = ['149', '211', '219', '327']
for res in residents:
    unit = res.findtext('unitnumber', '')
    if unit in target_units:
        print(f"  Unit {unit}: {res.findtext('firstname', '')} {res.findtext('lastname', '')} - Status: {res.findtext('leasestatus', '')}")
