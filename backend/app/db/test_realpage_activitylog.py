"""
Get resident activity log - might contain move-in dates
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# Lease IDs for lease-signed residents
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
        <tem:getresidentactivitylog>
            <tem:auth>
                <tem:pmcid>{PMCID}</tem:pmcid>
                <tem:siteid>{SITEID}</tem:siteid>
                <tem:licensekey>{LICENSEKEY}</tem:licensekey>
            </tem:auth>
            <tem:getresidentactivitylogparams>
                <tem:residentlist>
                    <tem:residentactivity>
                        <tem:leaseid>{lease_id}</tem:leaseid>
                    </tem:residentactivity>
                </tem:residentlist>
            </tem:getresidentactivitylogparams>
        </tem:getresidentactivitylog>
    </soapenv:Body>
</soapenv:Envelope>"""

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "http://tempuri.org/IRPXService/getresidentactivitylog"
    }

    print(f"\n=== {name} (Unit {unit}) - Lease ID {lease_id} ===")
    response = requests.post(URL, data=SOAP, headers=headers)
    
    if response.status_code == 200 and 'Fault' not in response.text:
        # Parse and look for date fields
        root = ET.fromstring(response.text)
        for elem in root.iter():
            tag = elem.tag.lower()
            if elem.text and elem.text.strip():
                # Show all fields with date/move in name
                if 'date' in tag or 'move' in tag or 'start' in tag or 'begin' in tag:
                    print(f"  {elem.tag}: {elem.text}")
        # Also show raw response snippet
        print(f"\n  Raw (500 chars): {response.text[400:900]}")
    else:
        print(f"  Status: {response.status_code}")
        print(f"  Preview: {response.text[:800]}")
