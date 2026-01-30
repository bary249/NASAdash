"""
Check future residents (Applicant - Lease Signed) count from live API
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

PROPERTIES = [
    ("5472172", "Nexus East"),
    ("5536211", "Parkside"),
    ("5446271", "Ridian"),
]

for site_id, name in PROPERTIES:
    SOAP = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
       <soapenv:Header/>
       <soapenv:Body>
          <tem:getresidentlist>
             <tem:auth>
                <tem:pmcid>{PMCID}</tem:pmcid>
                <tem:siteid>{site_id}</tem:siteid>
                <tem:licensekey>{LICENSEKEY}</tem:licensekey>
             </tem:auth>
             <tem:getresidentlistargs>
                <tem:ExtensionData/>
             </tem:getresidentlistargs>
          </tem:getresidentlist>
       </soapenv:Body>
    </soapenv:Envelope>"""
    
    resp = requests.post(URL, data=SOAP, headers={
        "Content-Type": "text/xml; charset=utf-8", 
        "SOAPAction": "http://tempuri.org/IRPXService/getresidentlist"
    })
    
    root = ET.fromstring(resp.text)
    residents = root.findall('.//resident')
    
    # Count by lease status
    statuses = {}
    future_count = 0
    for res in residents:
        status = res.findtext('leasestatus', 'Unknown')
        statuses[status] = statuses.get(status, 0) + 1
        # Count future move-ins (Applicant - Lease Signed, NOT Former)
        if 'applicant' in status.lower() and 'former' not in status.lower():
            future_count += 1
    
    print(f"\n{name} (Site {site_id}):")
    print(f"  Total residents: {len(residents)}")
    print(f"  Future move-ins (Applicant - Lease Signed): {future_count}")
    print(f"  All statuses: {statuses}")
