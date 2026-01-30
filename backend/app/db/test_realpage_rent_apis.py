"""
Check which RealPage APIs can give us in-place/effective rent
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# Try getRentableItems API - might have rent info
SOAP_RENTABLE = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:getrentableitems>
         <tem:auth>
            <tem:pmcid>{PMCID}</tem:pmcid>
            <tem:siteid>{SITEID}</tem:siteid>
            <tem:licensekey>{LICENSEKEY}</tem:licensekey>
         </tem:auth>
         <tem:getrentableitemsargs>
            <tem:ExtensionData/>
         </tem:getrentableitemsargs>
      </tem:getrentableitems>
   </soapenv:Body>
</soapenv:Envelope>"""

print("=" * 80)
print("CHECKING RENTABLE ITEMS API")
print("=" * 80)

resp = requests.post(URL, data=SOAP_RENTABLE, headers={
    "Content-Type": "text/xml; charset=utf-8", 
    "SOAPAction": "http://tempuri.org/IRPXService/getrentableitems"
})

print(f"Status: {resp.status_code}")
if resp.status_code == 200 and 'Fault' not in resp.text:
    root = ET.fromstring(resp.text)
    items = root.findall('.//*[Rent]') or root.findall('.//rentableitem') or root.findall('.//RentableItem')
    print(f"Found {len(items)} rentable items")
    
    # Show first few items with rent
    for elem in root.iter():
        if 'rent' in elem.tag.lower() or 'charge' in elem.tag.lower():
            print(f"  Found tag: {elem.tag} = {elem.text}")
    
    # Show raw response snippet
    print(f"\nRaw (first 2000 chars):\n{resp.text[:2000]}")
else:
    print(f"Error or no data: {resp.text[:500]}")

# Check getresidentlistinfo which might have more fields
print("\n" + "=" * 80)
print("CHECKING RESIDENTLISTINFO API")
print("=" * 80)

SOAP_RESINFO = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:getresidentlistinfo>
         <tem:auth>
            <tem:pmcid>{PMCID}</tem:pmcid>
            <tem:siteid>{SITEID}</tem:siteid>
            <tem:licensekey>{LICENSEKEY}</tem:licensekey>
         </tem:auth>
         <tem:getresidentlistinfoargs>
            <tem:ExtensionData/>
         </tem:getresidentlistinfoargs>
      </tem:getresidentlistinfo>
   </soapenv:Body>
</soapenv:Envelope>"""

resp2 = requests.post(URL, data=SOAP_RESINFO, headers={
    "Content-Type": "text/xml; charset=utf-8", 
    "SOAPAction": "http://tempuri.org/IRPXService/getresidentlistinfo"
})

print(f"Status: {resp2.status_code}")
if resp2.status_code == 200 and 'Fault' not in resp2.text:
    print(f"Raw (first 2000 chars):\n{resp2.text[:2000]}")
else:
    print(f"Error: {resp2.text[:500]}")
