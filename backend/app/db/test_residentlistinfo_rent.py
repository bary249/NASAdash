"""
Check residentlistinfo API for rent - requires status param
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

SOAP = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
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
            <tem:status>C</tem:status>
         </tem:getresidentlistinfoargs>
      </tem:getresidentlistinfo>
   </soapenv:Body>
</soapenv:Envelope>"""

print("=" * 80)
print("RESIDENTLISTINFO API (status=C) - Looking for Rent")
print("=" * 80)

resp = requests.post(URL, data=SOAP, headers={
    "Content-Type": "text/xml; charset=utf-8", 
    "SOAPAction": "http://tempuri.org/IRPXService/getresidentlistinfo"
})

print(f"Status: {resp.status_code}")

if resp.status_code == 200 and 'Fault' not in resp.text and 'Error' not in resp.text:
    root = ET.fromstring(resp.text)
    residents = root.findall('.//resident') or root.findall('.//Resident')
    print(f"Found {len(residents)} residents")
    
    # Find unit 109
    for res in residents:
        unit = res.findtext('unitnumber', '') or res.findtext('UnitNumber', '')
        if unit == '109':
            print(f"\n=== UNIT 109 RESIDENT (residentlistinfo) ===")
            for elem in res:
                if elem.text and elem.text.strip():
                    print(f"  {elem.tag}: {elem.text}")
            break
    
    # Show first resident to see all fields
    if residents:
        print(f"\n=== ALL FIELDS FROM FIRST RESIDENT ===")
        for elem in residents[0]:
            print(f"  {elem.tag}: {elem.text if elem.text else '(empty)'}")
else:
    print(f"Response: {resp.text[:1500]}")
