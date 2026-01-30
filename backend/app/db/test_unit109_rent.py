"""
Check Unit 109 rent data from RealPage APIs
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# Get units
SOAP_UNITS = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
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

# Get residents
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

print("=" * 80)
print("UNIT 109 - RENT DATA VERIFICATION")
print("=" * 80)

# Get unit data
resp = requests.post(URL, data=SOAP_UNITS, headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "http://tempuri.org/IRPXService/unitlist"})
root = ET.fromstring(resp.text)
units = root.findall('.//Unit')

print("\n--- FROM UNITLIST API ---")
for unit in units:
    if unit.findtext('UnitNumber', '') == '109':
        print(f"UnitNumber:     {unit.findtext('UnitNumber', '')}")
        print(f"FloorplanName:  {unit.findtext('FloorplanName', '')}")
        print(f"RentableSqft:   {unit.findtext('RentableSqft', '')}")
        print(f"MarketRent:     ${unit.findtext('MarketRent', '')}")
        print(f"Vacant:         {unit.findtext('Vacant', '')}")
        # Show all fields to find effective rent
        print("\nAll fields for unit 109:")
        for elem in unit:
            if elem.text and elem.text.strip():
                print(f"  {elem.tag}: {elem.text}")
        break

# Get resident data for unit 109
resp2 = requests.post(URL, data=SOAP_RES, headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "http://tempuri.org/IRPXService/getresidentlist"})
root2 = ET.fromstring(resp2.text)
residents = root2.findall('.//resident')

print("\n--- FROM RESIDENTLIST API (Madison Coffey in Unit 109) ---")
for res in residents:
    if res.findtext('unitnumber', '') == '109':
        print(f"Name:           {res.findtext('firstname', '')} {res.findtext('lastname', '')}")
        print(f"Unit:           {res.findtext('unitnumber', '')}")
        print(f"Status:         {res.findtext('leasestatus', '')}")
        print(f"Balance:        {res.findtext('balance', '')}")
        # Show all fields to find rent
        print("\nAll fields for this resident:")
        for elem in res:
            if elem.text and elem.text.strip():
                print(f"  {elem.tag}: {elem.text}")
        break

print("\n" + "=" * 80)
print("EXPECTED (from RealPage UI):")
print("  Market Rent:    $1,890.00")
print("  Effective Rent: $1,630.00")
print("  Rent Growth:    15.95% = (1890/1630 - 1) * 100")
print("=" * 80)
