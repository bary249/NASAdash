"""
Test RealPage unitlist API on Ridian property (Site ID: 5446271)
READ-ONLY: This only fetches data, no modifications.
"""
import requests

# RealPage credentials
URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"  # Ridian property
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# SOAP envelope for unitlist
SOAP_ENVELOPE = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:unitlist>
         <tem:auth>
            <tem:pmcid>{PMCID}</tem:pmcid>
            <tem:siteid>{SITEID}</tem:siteid>
            <tem:licensekey>{LICENSEKEY}</tem:licensekey>
         </tem:auth>
         <tem:getunitlist>
            <tem:ExtensionData/>
         </tem:getunitlist>
      </tem:unitlist>
   </soapenv:Body>
</soapenv:Envelope>"""

headers = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "http://tempuri.org/IRPXService/unitlist"
}

print(f"Testing unitlist API on Ridian (Site ID: {SITEID})")
print("=" * 60)

response = requests.post(URL, data=SOAP_ENVELOPE, headers=headers)

print(f"Status: {response.status_code}")
print(f"\nResponse:\n{response.text[:3000]}")

if len(response.text) > 3000:
    print(f"\n... (truncated, total length: {len(response.text)} chars)")
