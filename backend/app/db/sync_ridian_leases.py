"""
Sync Ridian lease data to database
READ-ONLY from API, writes to local DB
"""
import requests
import xml.etree.ElementTree as ET
import sqlite3
from datetime import datetime
from pathlib import Path

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"  # Ridian
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

DB_PATH = Path(__file__).parent / "data" / "realpage_raw.db"

# Get leases via getleaseinfo - need lease IDs first from residents
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

print("=" * 60)
print("Syncing Ridian Lease Data")
print("=" * 60)

# Get residents with lease IDs
resp = requests.post(URL, data=SOAP_RES, headers={
    "Content-Type": "text/xml; charset=utf-8", 
    "SOAPAction": "http://tempuri.org/IRPXService/getresidentlist"
})

root = ET.fromstring(resp.text)
residents = root.findall('.//resident')
print(f"Found {len(residents)} residents")

# Connect to DB
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Insert lease data from residents (they have leaseid, balance info)
inserted = 0
for res in residents:
    lease_id = res.findtext('leaseid', '')
    unit_id = res.findtext('unitid', '')
    unit_number = res.findtext('unitnumber', '')
    status = res.findtext('leasestatus', '')
    balance = res.findtext('balance', '0').replace(',', '')
    
    # We don't have rent in residentlist - need to estimate or get from another source
    # For now, skip - the API doesn't give us the rent amount directly
    
print(f"\nNote: getresidentlist API doesn't include rent_amount field")
print("Need to check if getleaseinfo works with specific lease IDs")

# Try getleaseinfo for a specific lease
lease_ids = [res.findtext('leaseid', '') for res in residents[:3]]
print(f"\nTrying getleaseinfo for lease IDs: {lease_ids}")

for lid in lease_ids:
    if not lid:
        continue
    SOAP_LEASE = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
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
                <tem:leaseid>{lid}</tem:leaseid>
             </tem:getleaseinfoargs>
          </tem:getleaseinfo>
       </soapenv:Body>
    </soapenv:Envelope>"""
    
    resp2 = requests.post(URL, data=SOAP_LEASE, headers={
        "Content-Type": "text/xml; charset=utf-8", 
        "SOAPAction": "http://tempuri.org/IRPXService/getleaseinfo"
    })
    
    if 'Fault' not in resp2.text and 'Error' not in resp2.text:
        print(f"\nLease {lid} response (first 500 chars):")
        print(resp2.text[:500])
        # Parse for rent
        root2 = ET.fromstring(resp2.text)
        for elem in root2.iter():
            if 'rent' in elem.tag.lower():
                print(f"  Found: {elem.tag} = {elem.text}")
    else:
        print(f"  Lease {lid}: API error")

conn.close()
