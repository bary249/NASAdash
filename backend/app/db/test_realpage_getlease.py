"""
Get lease details including move-in dates
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# Try getlease for lease ID 80 (Jordan Lippert)
SOAP = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:getlease>
         <tem:auth>
            <tem:pmcid>{PMCID}</tem:pmcid>
            <tem:siteid>{SITEID}</tem:siteid>
            <tem:licensekey>{LICENSEKEY}</tem:licensekey>
         </tem:auth>
         <tem:getleaseargs>
            <tem:ExtensionData/>
            <tem:leaseid>80</tem:leaseid>
         </tem:getleaseargs>
      </tem:getlease>
   </soapenv:Body>
</soapenv:Envelope>"""

headers = {"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "http://tempuri.org/IRPXService/getlease"}

print("Testing getlease API for lease ID 80 (Jordan Lippert - Unit 211)")
response = requests.post(URL, data=SOAP, headers=headers)
print(f"Status: {response.status_code}")
print(f"\nResponse:\n{response.text[:3000]}")
