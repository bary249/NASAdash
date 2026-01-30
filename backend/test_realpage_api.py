"""
Test script to explore RealPage RPX API data.
Uses existing credentials from the Postman environment.
READ-ONLY operations only.
"""

import httpx
import xml.etree.ElementTree as ET
from xml.dom import minidom
import json


# RealPage RPX credentials (from Postman environment)
# Using VennPro endpoint and licensekey to test all modules
CONFIG = {
    "url": "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc",  # VennPro endpoint
    "url_venn": "https://gateway.rpx.realpage.com/rpxgateway/partner/Venn/Venn.svc",   # Original Venn
    "url_pro": "https://gateway.rpx.realpage.com/rpxgateway/partner/VennPro/VennPro.svc",
    # CrossFire Prospect Management API endpoint (separate from RPX)
    "url_crossfire": "https://onesite.realpage.com/WebServices/CrossFire/prospectmanagement/service.asmx",
    # RPX Gateway credentials
    "pmcid": "5230170",
    "siteid": "5230176",
    "licensekey": "402b831f-a045-40ce-9ee8-cc2aa6c3ab72",  # VennPro licensekey
    "licensekey_venn": "fdc09c52-4f28-46d6-aca1-8bcc2b135587",  # Original Venn
    "licensekey_pro": "402b831f-a045-40ce-9ee8-cc2aa6c3ab72",
    # CrossFire credentials (DIFFERENT IDs than RPX!)
    "crossfire_pmcid": "4248314",    # Company ID from OneSite
    "crossfire_siteid": "5480255",   # Property ID from OneSite
    "crossfire_username": "Engineering-suppliers@venn.city",
    "crossfire_password": "Venn2023!",
}


def build_soap_envelope(body_content: str, namespace: str = "tem") -> str:
    """Build a SOAP envelope with the given body content."""
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:{namespace}="http://tempuri.org/">
    <soapenv:Header/>
    <soapenv:Body>
        {body_content}
    </soapenv:Body>
</soapenv:Envelope>"""


def build_auth_block(use_pro: bool = False) -> str:
    """Build the authentication block."""
    key = CONFIG["licensekey_pro"] if use_pro else CONFIG["licensekey"]
    return f"""<tem:auth>
                <tem:pmcid>{CONFIG["pmcid"]}</tem:pmcid>
                <tem:siteid>{CONFIG["siteid"]}</tem:siteid>
                <tem:licensekey>{key}</tem:licensekey>
                <tem:system>Onesite</tem:system>
            </tem:auth>"""


def prettify_xml(xml_string: str) -> str:
    """Pretty print XML."""
    try:
        dom = minidom.parseString(xml_string)
        return dom.toprettyxml(indent="  ")
    except:
        return xml_string


def xml_to_dict(element):
    """Convert XML element to dictionary."""
    result = {}
    
    # Handle attributes
    if element.attrib:
        result["@attributes"] = element.attrib
    
    # Handle children
    children = list(element)
    if children:
        child_dict = {}
        for child in children:
            child_result = xml_to_dict(child)
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            
            if tag in child_dict:
                if not isinstance(child_dict[tag], list):
                    child_dict[tag] = [child_dict[tag]]
                child_dict[tag].append(child_result)
            else:
                child_dict[tag] = child_result
        
        result.update(child_dict)
    
    # Handle text
    if element.text and element.text.strip():
        if result:
            result["#text"] = element.text.strip()
        else:
            return element.text.strip()
    
    return result if result else None


async def call_realpage_api(url: str, soap_action: str, body: str) -> dict:
    """Make a SOAP call to RealPage API."""
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": soap_action,
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, content=body, headers=headers)
        
        print(f"\n{'='*60}")
        print(f"API: {soap_action.split('/')[-1]}")
        print(f"Status: {response.status_code}")
        print(f"{'='*60}")
        
        if response.status_code == 200:
            try:
                root = ET.fromstring(response.text)
                # Find the Body element
                body_elem = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Body")
                if body_elem is not None and len(body_elem) > 0:
                    result = xml_to_dict(body_elem[0])
                    return {"status": "success", "data": result}
            except ET.ParseError as e:
                return {"status": "error", "message": f"XML parse error: {e}", "raw": response.text[:1000]}
        
        return {"status": "error", "code": response.status_code, "raw": response.text[:1000]}


async def test_get_buildings():
    """Test getBuildings endpoint."""
    body = build_soap_envelope(f"""
        <tem:getbuildings>
            {build_auth_block()}
        </tem:getbuildings>
    """)
    
    return await call_realpage_api(
        CONFIG["url"],
        "http://tempuri.org/IRPXService/getbuildings",
        body
    )


async def test_get_site_list():
    """Test getSiteList endpoint."""
    body = build_soap_envelope(f"""
        <tem:getsitelist>
            {build_auth_block(use_pro=True)}
        </tem:getsitelist>
    """)
    
    return await call_realpage_api(
        CONFIG["url_pro"],
        "http://tempuri.org/IRPXService/getsitelist",
        body
    )


async def test_get_unit_list():
    """Test getUnitList endpoint."""
    body = build_soap_envelope(f"""
        <tem:unitlist>
            {build_auth_block()}
        </tem:unitlist>
    """)
    
    return await call_realpage_api(
        CONFIG["url"],
        "http://tempuri.org/IRPXService/unitlist",
        body
    )


async def test_get_resident_list_info():
    """Test getResidentListInfo endpoint - gets residents with status."""
    body = build_soap_envelope(f"""
        <tem:getresidentlistinfo>
            {build_auth_block()}
            <tem:getresidentlistinfo>
                <tem:status>ALL</tem:status>
                <tem:headofhousehold>0</tem:headofhousehold>
            </tem:getresidentlistinfo>
        </tem:getresidentlistinfo>
    """)
    
    return await call_realpage_api(
        CONFIG["url"],
        "http://tempuri.org/IRPXService/getresidentlistinfo",
        body
    )


async def test_get_resident():
    """Test getResident endpoint - gets current residents."""
    body = build_soap_envelope(f"""
        <tem:getresident>
            {build_auth_block()}
            <tem:getresident>
                <tem:residentstatus>C</tem:residentstatus>
                <tem:residentheldthestatus>30</tem:residentheldthestatus>
                <tem:residentwillhavethestatus>30</tem:residentwillhavethestatus>
            </tem:getresident>
        </tem:getresident>
    """)
    
    return await call_realpage_api(
        CONFIG["url"],
        "http://tempuri.org/IRPXService/getresident",
        body
    )


async def test_get_lease_info():
    """Test getLeaseInfo endpoint."""
    body = build_soap_envelope(f"""
        <tem:getleaseinfo>
            {build_auth_block(use_pro=True)}
            <tem:getleaseinfo>
                <tem:residentstatus>ALL</tem:residentstatus>
                <tem:residentheldthestatus>30</tem:residentheldthestatus>
            </tem:getleaseinfo>
        </tem:getleaseinfo>
    """)
    
    return await call_realpage_api(
        CONFIG["url_pro"],
        "http://tempuri.org/IRPXService/getleaseinfo",
        body
    )


# =============================================================================
# PROSPECT MANAGEMENT API (CrossFire) - READ-ONLY OPERATIONS ONLY
# These are GET-equivalent operations for lead-to-lease data
# Uses DIFFERENT endpoint and auth structure than RPX
# =============================================================================

# SAFETY: Explicit allowlist of read-only methods - NOTHING ELSE IS PERMITTED
CROSSFIRE_READONLY_METHODS = frozenset([
    "GetActivityLossReasons",
    "GetActivityResultCodes",
    "GetActivityTypes",
    "GetAgentAppointmentDetails",
    "GetAgentsAppointmentTimes",
    "GetAllContactTypes",
    "GetAppointmentCounts",
    "GetCustomFieldSeedDataBulk",
    "GetFloorPlanGroupsByProperty",
    "GetFloorPlanIDAndName",
    "GetGuestCardNotesByDateRange",
    "GetLeasingAgentsByProperty",
    "GetMarketingSourcesByProperty",
    "GetPetPolicy",
    "GetPetTypes",
    "GetPetWeight",
    "GetPicklistProspect",
    "GetPriceRangesByProperty",
    "GetReasonsDidRentByProperty",
    "GetReasonsForMoving",
    "GetScheduledAppointments",
    "GetUnitsByProperty",
    "GetWorkLocationData",
    "ProspectSearch",        # Read-only search
    "RetrieveLeaseTerms",    # Read-only retrieval
])

# DANGER: These methods MUST NEVER be called - they modify data
CROSSFIRE_WRITE_METHODS_BLOCKED = frozenset([
    "AddNewCustomerToGuestCard",  # WRITE
    "ConfirmAppointment",          # WRITE
    "DeleteContact",               # DELETE
    "DeleteTask",                  # DELETE
    "InsertActivity",              # WRITE
    "InsertFollowUp",              # WRITE
    "InsertProspect",              # WRITE
    "InsertUnitShown",             # WRITE
    "UpdateProspect",              # WRITE
])


def validate_readonly_method(method_name: str) -> bool:
    """
    SAFETY CHECK: Validate that the method is read-only.
    Raises exception if method could modify data.
    """
    if method_name in CROSSFIRE_WRITE_METHODS_BLOCKED:
        raise PermissionError(f"🚫 BLOCKED: '{method_name}' is a WRITE operation - not permitted!")
    
    if method_name not in CROSSFIRE_READONLY_METHODS:
        raise PermissionError(f"🚫 BLOCKED: '{method_name}' is not in the approved read-only allowlist!")
    
    return True


def build_crossfire_soap_envelope(body_content: str) -> str:
    """
    Build a SOAP envelope for Prospect Management API.
    Uses RPX credentials (pmcid, siteid, licensekey) as per documentation.
    """
    # Use RPX-style auth with licensekey (required params per docs)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
    <soapenv:Header/>
    <soapenv:Body>
        <tem:auth>
            <tem:pmcid>{CONFIG["pmcid"]}</tem:pmcid>
            <tem:siteid>{CONFIG["siteid"]}</tem:siteid>
            <tem:licensekey>{CONFIG["licensekey"]}</tem:licensekey>
            <tem:system>Onesite</tem:system>
        </tem:auth>
        {body_content}
    </soapenv:Body>
</soapenv:Envelope>"""


async def call_crossfire_api(soap_action: str, body: str) -> dict:
    """
    Make a SOAP call to CrossFire Prospect Management API.
    
    ⚠️  SAFETY: This function validates that ONLY read-only methods are called.
    Any attempt to call a write method will raise PermissionError.
    """
    # SAFETY CHECK: Extract method name and validate it's read-only
    method_name = soap_action.split("/")[-1]
    validate_readonly_method(method_name)  # Raises if not allowed
    
    print(f"  ✅ Safety check passed: '{method_name}' is a read-only method")
    
    # RealPage requires SOAPAction with quotes around the value
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{soap_action}"',
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            CONFIG["url_crossfire"], 
            content=body, 
            headers=headers
        )
        
        print(f"\n{'='*60}")
        print(f"API: {soap_action.split('/')[-1]} (CrossFire)")
        print(f"Status: {response.status_code}")
        print(f"{'='*60}")
        
        if response.status_code == 200:
            try:
                root = ET.fromstring(response.text)
                body_elem = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Body")
                if body_elem is not None and len(body_elem) > 0:
                    result = xml_to_dict(body_elem[0])
                    return {"status": "success", "data": result}
            except ET.ParseError as e:
                return {"status": "error", "message": f"XML parse error: {e}", "raw": response.text[:1000]}
        
        return {"status": "error", "code": response.status_code, "raw": response.text[:2000]}


async def test_get_guest_card_list():
    """
    READ-ONLY: Get list of guest cards (prospects).
    Uses RPX-style auth with licensekey.
    """
    body = build_soap_envelope(f"""
        <tem:getguestcardlist>
            {build_auth_block()}
            <tem:getguestcardlist>
                <tem:status>ALL</tem:status>
            </tem:getguestcardlist>
        </tem:getguestcardlist>
    """)
    
    return await call_realpage_api(
        CONFIG["url"],
        "http://tempuri.org/IRPXService/getguestcardlist",
        body
    )


async def test_get_marketing_sources():
    """
    READ-ONLY: Get marketing sources for lead attribution.
    Uses RPX-style auth with licensekey.
    """
    body = build_soap_envelope(f"""
        <tem:getmarketingsources>
            {build_auth_block()}
        </tem:getmarketingsources>
    """)
    
    return await call_realpage_api(
        CONFIG["url"],
        "http://tempuri.org/IRPXService/getmarketingsources",
        body
    )


async def test_get_activity_types_prospect():
    """
    READ-ONLY: Get activity type definitions.
    Uses RPX-style auth with licensekey.
    """
    body = build_soap_envelope(f"""
        <tem:getactivitytypes>
            {build_auth_block()}
        </tem:getactivitytypes>
    """)
    
    return await call_realpage_api(
        CONFIG["url"],
        "http://tempuri.org/IRPXService/getactivitytypes",
        body
    )


async def test_get_guest_card_notes():
    """
    READ-ONLY: Get guest card notes by date range.
    Uses RPX-style auth with licensekey.
    """
    from datetime import datetime, timedelta
    start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    end = datetime.now().strftime("%Y-%m-%d")
    
    body = build_soap_envelope(f"""
        <tem:getguestcardnotesbydaterange>
            {build_auth_block()}
            <tem:getguestcardnotesbydaterange>
                <tem:startdate>{start}</tem:startdate>
                <tem:enddate>{end}</tem:enddate>
            </tem:getguestcardnotesbydaterange>
        </tem:getguestcardnotesbydaterange>
    """)
    
    return await call_realpage_api(
        CONFIG["url"],
        "http://tempuri.org/IRPXService/getguestcardnotesbydaterange",
        body
    )


async def test_get_leasing_agents():
    """
    READ-ONLY: Get leasing agents for the property.
    Uses RPX-style auth with licensekey.
    """
    body = build_soap_envelope(f"""
        <tem:getleasingagents>
            {build_auth_block()}
        </tem:getleasingagents>
    """)
    
    return await call_realpage_api(
        CONFIG["url"],
        "http://tempuri.org/IRPXService/getleasingagents",
        body
    )


def summarize_data(name: str, result: dict):
    """Print a summary of the API response."""
    print(f"\n📊 {name} Summary:")
    print("-" * 40)
    
    if result.get("status") == "error":
        print(f"  ❌ Error: {result.get('message', result.get('code', 'Unknown'))}")
        if "raw" in result:
            print(f"  Raw (truncated): {result['raw'][:200]}...")
        return
    
    data = result.get("data", {})
    
    # Try to find the main result
    for key, value in data.items():
        if "Result" in key or "Response" in key:
            if isinstance(value, dict):
                for k, v in value.items():
                    if isinstance(v, list):
                        print(f"  ✅ {k}: {len(v)} items")
                        if v and isinstance(v[0], dict):
                            print(f"     Fields: {list(v[0].keys())[:8]}...")
                    elif isinstance(v, dict):
                        print(f"  ✅ {k}: {len(v)} fields")
                    else:
                        print(f"  ✅ {k}: {v}")
            elif isinstance(value, list):
                print(f"  ✅ {key}: {len(value)} items")
            else:
                print(f"  ✅ {key}: {value}")


async def main():
    """Run all API tests."""
    print("\n" + "=" * 60)
    print("🔍 RealPage RPX API Data Explorer")
    print("=" * 60)
    print(f"PMC ID: {CONFIG['pmcid']}")
    print(f"Site ID: {CONFIG['siteid']}")
    print("=" * 60)
    
    results = {}
    
    # Test each endpoint
    print("\n\n🏢 Testing getBuildings...")
    results["buildings"] = await test_get_buildings()
    summarize_data("Buildings", results["buildings"])
    
    print("\n\n📍 Testing getSiteList...")
    results["sites"] = await test_get_site_list()
    summarize_data("Sites", results["sites"])
    
    print("\n\n🏠 Testing getUnitList...")
    results["units"] = await test_get_unit_list()
    summarize_data("Units", results["units"])
    
    print("\n\n👥 Testing getResidentListInfo...")
    results["residents_info"] = await test_get_resident_list_info()
    summarize_data("Residents Info", results["residents_info"])
    
    print("\n\n👤 Testing getResident (Current)...")
    results["residents"] = await test_get_resident()
    summarize_data("Current Residents", results["residents"])
    
    print("\n\n📄 Testing getLeaseInfo...")
    results["leases"] = await test_get_lease_info()
    summarize_data("Lease Info", results["leases"])
    
    # =========================================================================
    # PROSPECT MANAGEMENT API - Using RPX credentials (licensekey)
    # Same endpoint as RPX, same auth - as per documentation
    # =========================================================================
    print("\n\n" + "=" * 60)
    print("🎯 PROSPECT MANAGEMENT API (Lead-to-Lease Data)")
    print("    ⚠️  READ-ONLY: All operations are get* methods only")
    print("    🔑 Using RPX credentials (pmcid, siteid, licensekey)")
    print(f"    Endpoint: {CONFIG['url']}")
    print("=" * 60)
    
    print("\n\n📋 Testing getGuestCardList (READ-ONLY)...")
    results["guest_cards"] = await test_get_guest_card_list()
    summarize_data("Guest Cards (Prospects)", results["guest_cards"])
    
    print("\n\n📢 Testing getMarketingSources (READ-ONLY)...")
    results["marketing_sources"] = await test_get_marketing_sources()
    summarize_data("Marketing Sources", results["marketing_sources"])
    
    print("\n\n📝 Testing getActivityTypes (READ-ONLY)...")
    results["activity_types"] = await test_get_activity_types_prospect()
    summarize_data("Activity Types", results["activity_types"])
    
    print("\n\n📓 Testing getGuestCardNotesByDateRange (READ-ONLY)...")
    results["guest_card_notes"] = await test_get_guest_card_notes()
    summarize_data("Guest Card Notes", results["guest_card_notes"])
    
    print("\n\n👤 Testing getLeasingAgents (READ-ONLY)...")
    results["leasing_agents"] = await test_get_leasing_agents()
    summarize_data("Leasing Agents", results["leasing_agents"])
    
    # Save full results to JSON for analysis
    output_file = "realpage_api_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n\n💾 Full results saved to: {output_file}")
    print("\n" + "=" * 60)
    print("✅ API exploration complete!")
    print("=" * 60)
    
    return results


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
