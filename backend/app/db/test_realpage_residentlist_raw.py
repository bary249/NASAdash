"""
Get raw resident list response to see structure
READ-ONLY
"""
import requests

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"  # Ridian
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

SOAP_ENVELOPE = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
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

headers = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "http://tempuri.org/IRPXService/getresidentlist"
}

response = requests.post(URL, data=SOAP_ENVELOPE, headers=headers)
print(f"Status: {response.status_code}")
print(f"\nRaw response (first 5000 chars):\n{response.text[:5000]}")
