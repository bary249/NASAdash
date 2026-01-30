"""
Get lease info including move-in dates using getleaseinfo API
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# Lease IDs for future residents: 80, 85, 87, 91
lease_ids = [
    (80, "Jordan Lippert", "211"),
    (85, "Brent Heyde", "149"),
    (87, "Naseam Bahrami", "219"),
    (91, "Lindy Yoshida", "327"),
]

for lease_id, name, unit in lease_ids:
    SOAP = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
       <soapenv:Header/>
       <soapenv:Body>
          <tem:getleaseinfo>
             <tem:auth>
                <tem:pmcid>{PMCID}</tem:pmcid>
                <tem:siteid>{SITEID}</tem:siteid>
                <tem:licensekey>{LICENSEKEY}</tem:licensekey>
             </tem:auth>
             <tem:getleaseinfoargs>
                <tem:ExtensionData/>
                <tem:leaseid>{lease_id}</tem:leaseid>
             </tem:getleaseinfoargs>
          </tem:getleaseinfo>
       </soapenv:Body>
    </soapenv:Envelope>"""

    headers = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "http://tempuri.org/IRPXService/getleaseinfo"}
    response = requests.post(URL, data=SOAP, headers=headers)
    
    print(f"\n=== {name} (Unit {unit}) - Lease ID {lease_id} ===")
    
    if response.status_code == 200 and 'Fault' not in response.text:
        root = ET.fromstring(response.text)
        # Find all elements with date or move in tag
        for elem in root.iter():
            tag = elem.tag.lower()
            if elem.text and elem.text.strip():
                if 'move' in tag or 'date' in tag or 'start' in tag or 'begin' in tag:
                    print(f"  {elem.tag}: {elem.text}")
    else:
        print(f"  Status: {response.status_code}")
        if 'Fault' in response.text:
            print("  Error: API call failed")
        print(f"  Preview: {response.text[:500]}")
