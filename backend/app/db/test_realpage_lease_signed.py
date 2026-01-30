"""
Get full details for 'Applicant - Lease Signed' residents
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"  # Ridian
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# Try getresidentlistinfo for more details
SOAP_ENVELOPE = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
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

headers = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "http://tempuri.org/IRPXService/getresidentlistinfo"
}

response = requests.post(URL, data=SOAP_ENVELOPE, headers=headers)
print(f"Status: {response.status_code}")

if response.status_code == 200:
    root = ET.fromstring(response.text)
    residents = root.findall('.//resident') or root.findall('.//Resident')
    print(f"Total residents: {len(residents)}")
    
    # Find lease signed residents and show all fields
    target_names = ['yoshida', 'heyde', 'lippert', 'bahrami']
    for res in residents:
        last = ''
        for elem in res:
            if 'lastname' in elem.tag.lower():
                last = elem.text or ''
        
        if any(name in last.lower() for name in target_names):
            print(f"\n=== {last} ===")
            for elem in res:
                if elem.text and elem.text.strip():
                    print(f"  {elem.tag}: {elem.text}")
else:
    print(f"Error: {response.text[:1000]}")
