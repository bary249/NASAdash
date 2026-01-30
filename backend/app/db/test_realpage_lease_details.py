"""
Get lease details for 'Applicant - Lease Signed' residents using getresident API
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"  # Ridian
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# First get resident IDs from getresidentlist
SOAP_LIST = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
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

headers_list = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "http://tempuri.org/IRPXService/getresidentlist"
}

response = requests.post(URL, data=SOAP_LIST, headers=headers_list)
root = ET.fromstring(response.text)
residents = root.findall('.//resident')

# Find lease signed residents
lease_signed = []
for res in residents:
    status = res.findtext('leasestatus', '')
    if 'Applicant - Lease Signed' in status:
        lease_signed.append({
            'resid': res.findtext('residentmemberid', ''),
            'leaseid': res.findtext('leaseid', ''),
            'name': f"{res.findtext('firstname', '')} {res.findtext('lastname', '')}",
            'unit': res.findtext('unitnumber', '')
        })

print(f"Found {len(lease_signed)} 'Applicant - Lease Signed' residents")

# Get detailed info for each using getresident
for r in lease_signed:
    print(f"\n=== {r['name']} (Unit {r['unit']}) - ResID: {r['resid']}, LeaseID: {r['leaseid']} ===")
    
    SOAP_DETAIL = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
       <soapenv:Header/>
       <soapenv:Body>
          <tem:getresident>
             <tem:auth>
                <tem:pmcid>{PMCID}</tem:pmcid>
                <tem:siteid>{SITEID}</tem:siteid>
                <tem:licensekey>{LICENSEKEY}</tem:licensekey>
             </tem:auth>
             <tem:getresidentargs>
                <tem:ExtensionData/>
                <tem:resid>{r['resid']}</tem:resid>
             </tem:getresidentargs>
          </tem:getresident>
       </soapenv:Body>
    </soapenv:Envelope>"""
    
    headers_detail = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "http://tempuri.org/IRPXService/getresident"
    }
    
    resp = requests.post(URL, data=SOAP_DETAIL, headers=headers_detail)
    if resp.status_code == 200:
        # Look for move-in date in response
        text = resp.text
        if 'movein' in text.lower() or 'move' in text.lower():
            # Parse and find relevant fields
            detail_root = ET.fromstring(text)
            for elem in detail_root.iter():
                tag = elem.tag.lower()
                if 'move' in tag or 'lease' in tag or 'start' in tag or 'date' in tag:
                    if elem.text and elem.text.strip():
                        print(f"  {elem.tag}: {elem.text}")
        else:
            print(f"  Response length: {len(text)} chars")
            # Show first part to see structure
            print(f"  Preview: {text[500:1500]}")
    else:
        print(f"  Error: {resp.status_code}")
