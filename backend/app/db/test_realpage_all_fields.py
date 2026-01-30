"""
Show ALL fields for lease-signed residents
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

headers = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "http://tempuri.org/IRPXService/getresidentlist"}
response = requests.post(URL, data=SOAP, headers=headers)
root = ET.fromstring(response.text)

# Find one lease-signed resident and show ALL fields
for res in root.findall('.//resident'):
    if 'Lease Signed' in res.findtext('leasestatus', ''):
        print(f"=== ALL FIELDS FOR: {res.findtext('firstname', '')} {res.findtext('lastname', '')} ===\n")
        for elem in res:
            print(f"  {elem.tag}: {elem.text}")
        break
