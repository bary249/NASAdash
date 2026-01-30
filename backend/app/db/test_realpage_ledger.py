"""
Test RealPage getresidentledger SOAP API - READ ONLY
"""
import requests

# RealPage credentials from .env
REALPAGE_URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5472172"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# SOAP envelope for getresidentledger (READ-ONLY operation)
soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:getresidentledger>
         <tem:auth>
            <tem:pmcid>{PMCID}</tem:pmcid>
            <tem:siteid>{SITEID}</tem:siteid>
            <tem:licensekey>{LICENSEKEY}</tem:licensekey>
         </tem:auth>
         <tem:getresidentledger>
            <tem:reshid>10</tem:reshid>
            <tem:startdate>2022-12-31</tem:startdate>
            <tem:enddate>2025-02-16</tem:enddate>
            <tem:allopen>false</tem:allopen>
            <tem:ExtensionData/>
         </tem:getresidentledger>
      </tem:getresidentledger>
   </soapenv:Body>
</soapenv:Envelope>"""

headers = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "http://tempuri.org/IRPXService/getresidentledger"
}

print("=" * 60)
print("Testing RealPage getresidentledger API (READ-ONLY)")
print("=" * 60)
print(f"URL: {REALPAGE_URL}")
print(f"PMCID: {PMCID}")
print(f"SITEID: {SITEID}")
print(f"reshid: 750")
print("=" * 60)

try:
    response = requests.post(REALPAGE_URL, data=soap_envelope, headers=headers, timeout=30)
    print(f"\nStatus Code: {response.status_code}")
    print(f"\nResponse Headers:")
    for k, v in response.headers.items():
        print(f"  {k}: {v}")
    print(f"\nResponse Body:\n{response.text}")
except Exception as e:
    print(f"Error: {e}")
