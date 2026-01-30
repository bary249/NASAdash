"""
Check lease API for effective rent - Unit 109
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# Get lease info
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
         </tem:getleaseinfoargs>
      </tem:getleaseinfo>
   </soapenv:Body>
</soapenv:Envelope>"""

print("=" * 80)
print("LEASE INFO API - Looking for Rent field")
print("=" * 80)

resp = requests.post(URL, data=SOAP, headers={
    "Content-Type": "text/xml; charset=utf-8", 
    "SOAPAction": "http://tempuri.org/IRPXService/getleaseinfo"
})

print(f"Status: {resp.status_code}")

if resp.status_code == 200 and 'Fault' not in resp.text:
    root = ET.fromstring(resp.text)
    leases = root.findall('.//Lease') or root.findall('.//lease')
    print(f"Found {len(leases)} leases")
    
    # Find lease for unit 109 (UnitID = 1 based on earlier data)
    for lease in leases:
        unit_id = lease.findtext('UnitID', '')
        unit_num = lease.findtext('UnitNumber', '')
        if unit_id == '1' or unit_num == '109':
            print(f"\n=== UNIT 109 LEASE DATA ===")
            for elem in lease:
                if elem.text and elem.text.strip():
                    print(f"  {elem.tag}: {elem.text}")
            break
    
    # Show first lease to see structure
    if leases:
        print(f"\n=== SAMPLE LEASE (first one) ===")
        for elem in leases[0]:
            if elem.text and elem.text.strip():
                print(f"  {elem.tag}: {elem.text}")
else:
    print(f"Error: {resp.text[:1000]}")
