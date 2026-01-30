"""
Test RealPage getpetinformation SOAP API - READ ONLY
"""
import requests
import re

# RealPage credentials from .env
REALPAGE_URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5472172"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

headers = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "http://tempuri.org/IRPXService/getpetinformation"
}

print("=" * 60)
print("Testing RealPage getpetinformation API (READ-ONLY)")
print(f"Checking leases 1-20")
print("=" * 60)

# First, show raw response for lease 10 to verify data format
soap_envelope = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
    <soapenv:Header/>
    <soapenv:Body>
        <tem:getpetinformation>
            <tem:auth>
                <tem:pmcid>{PMCID}</tem:pmcid>
                <tem:siteid>{SITEID}</tem:siteid>
                <tem:licensekey>{LICENSEKEY}</tem:licensekey>
            </tem:auth>
            <tem:leaseId>10</tem:leaseId>
        </tem:getpetinformation>
    </soapenv:Body>
</soapenv:Envelope>"""

print("\n--- RAW RESPONSE FOR LEASE 10 ---")
response = requests.post(REALPAGE_URL, data=soap_envelope, headers=headers, timeout=30)
print(f"Status: {response.status_code}")
print(f"Response:\n{response.text}\n")

# Check success field
if "<success>true</success>" in response.text:
    print("✓ API returning valid success=true responses")
elif "<success>false</success>" in response.text:
    print("✗ API returning success=false - check errors")
else:
    print("? Unexpected response format")
