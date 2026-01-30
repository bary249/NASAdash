"""
Compare UnitExpectedMoveinDate from unitlist with lease-signed residents
READ-ONLY
"""
import requests
import xml.etree.ElementTree as ET
from datetime import datetime

URL = "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc"
PMCID = "4248314"
SITEID = "5446271"
LICENSEKEY = "402b831f-a045-40ce-9ee8-cc2aa6c3ab72"

# Get unit list
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

# Get resident list
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

# Fetch units
resp_units = requests.post(URL, data=SOAP_UNITS, headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "http://tempuri.org/IRPXService/unitlist"})
root_units = ET.fromstring(resp_units.text)
units = root_units.findall('.//Unit')

# Fetch residents
resp_res = requests.post(URL, data=SOAP_RES, headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": "http://tempuri.org/IRPXService/getresidentlist"})
root_res = ET.fromstring(resp_res.text)
residents = root_res.findall('.//resident')

# Get lease-signed residents
lease_signed = {}
for res in residents:
    if 'Lease Signed' in res.findtext('leasestatus', ''):
        unit = res.findtext('unitnumber', '')
        lease_signed[unit] = f"{res.findtext('firstname', '')} {res.findtext('lastname', '')}"

print("=== COMPARING UNIT EXPECTED MOVE-IN DATES WITH LEASE-SIGNED RESIDENTS ===\n")
print(f"{'Unit':<8} {'Resident':<25} {'UnitExpectedMoveinDate':<25} {'Vacant':<8} {'Available':<10}")
print("-" * 90)

today = datetime.now()

# Check units for the lease-signed residents
target_units = ['149', '211', '219', '327', '128']  # Including 128 which showed future date
for unit in units:
    unit_num = unit.findtext('UnitNumber', '')
    if unit_num in target_units or unit_num in lease_signed:
        expected = unit.findtext('UnitExpectedMoveinDate', '').strip()
        vacant = unit.findtext('Vacant', '')
        available = unit.findtext('Available', '')
        resident = lease_signed.get(unit_num, '(none)')
        
        # Highlight if future date
        is_future = ""
        if expected:
            try:
                dt = datetime.strptime(expected.split()[0], '%Y-%m-%d')
                if dt >= today:
                    is_future = " ← FUTURE"
            except:
                pass
        
        print(f"{unit_num:<8} {resident:<25} {expected:<25} {vacant:<8} {available:<10}{is_future}")

print("\n\n=== ALL UNITS WITH FUTURE EXPECTED MOVE-IN DATES ===\n")
for unit in units:
    expected = unit.findtext('UnitExpectedMoveinDate', '').strip()
    if expected:
        try:
            dt = datetime.strptime(expected.split()[0], '%Y-%m-%d')
            if dt >= today:
                unit_num = unit.findtext('UnitNumber', '')
                resident = lease_signed.get(unit_num, '(no lease-signed resident)')
                print(f"Unit {unit_num}: {expected} - {resident}")
        except:
            pass
