"""
RealPage PMS SOAP Client - READ-ONLY OPERATIONS ONLY
Implements PMSInterface for RealPage RPX Gateway.

This client only implements GET operations. No PUT, POST, or DELETE.
"""
import httpx
from typing import List, Optional
from xml.etree import ElementTree as ET
from app.config import get_settings
from app.clients.pms_interface import PMSInterface, PMSType


class RealPageClient(PMSInterface):
    """
    SOAP client for RealPage RPX Gateway APIs.
    
    IMPORTANT: This client only implements READ operations (Get*).
    No write operations are permitted.
    
    Available Methods:
    - getBuildings: Property structures
    - getSiteList: Site/property list  
    - getUnitList: Unit details
    - getResident: Resident information
    - getResidentListInfo: Resident list
    - getLeaseInfo: Lease data
    
    NOT Available (needs RealPage authorization):
    - Guest Cards / Prospects
    - Marketing Sources
    - Activity Types
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        pmcid: Optional[str] = None,
        siteid: Optional[str] = None,
        licensekey: Optional[str] = None
    ):
        """
        Initialize RealPage client.
        
        Args:
            url: RealPage RPX Gateway URL (defaults to settings)
            pmcid: PMC ID (defaults to settings)
            siteid: Site ID (defaults to settings)
            licensekey: License key (defaults to settings)
        """
        settings = get_settings()
        self.url = url or getattr(settings, 'realpage_url', None)
        self.pmcid = pmcid or getattr(settings, 'realpage_pmcid', None)
        self.siteid = siteid or getattr(settings, 'realpage_siteid', None)
        self.licensekey = licensekey or getattr(settings, 'realpage_licensekey', None)
        
        self.headers = {
            "Content-Type": "text/xml; charset=utf-8",
        }
    
    @property
    def pms_type(self) -> PMSType:
        return PMSType.REALPAGE
    
    def _build_soap_envelope(self, body_content: str) -> str:
        """Build a SOAP envelope with the given body content."""
        return f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
    <soapenv:Header/>
    <soapenv:Body>
        {body_content}
    </soapenv:Body>
</soapenv:Envelope>"""
    
    def _build_auth_block(self) -> str:
        """Build the authentication block."""
        return f"""<tem:auth>
                <tem:pmcid>{self.pmcid}</tem:pmcid>
                <tem:siteid>{self.siteid}</tem:siteid>
                <tem:licensekey>{self.licensekey}</tem:licensekey>
                <tem:system>Onesite</tem:system>
            </tem:auth>"""
    
    async def _send_request(self, soap_action: str, body: str) -> dict:
        """Send SOAP request and parse response."""
        headers = {
            **self.headers,
            "SOAPAction": soap_action
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(self.url, headers=headers, content=body)
            response.raise_for_status()
            return self._parse_xml_response(response.text)
    
    def _parse_xml_response(self, xml_text: str) -> dict:
        """Parse SOAP XML response into a dictionary."""
        try:
            root = ET.fromstring(xml_text)
            body = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Body')
            
            if body is not None and len(body) > 0:
                return self._element_to_dict(body[0])
            
            return {"raw": xml_text}
        except ET.ParseError:
            return {"raw": xml_text, "error": "XML parse error"}
    
    def _element_to_dict(self, element: ET.Element) -> dict:
        """Recursively convert XML element to dictionary."""
        result = {}
        
        if element.attrib:
            result["@attributes"] = dict(element.attrib)
        
        for child in element:
            tag = child.tag.split('}')[-1] if '}' in child.tag else child.tag
            child_data = self._element_to_dict(child) if len(child) > 0 else child.text
            
            if tag in result:
                if not isinstance(result[tag], list):
                    result[tag] = [result[tag]]
                result[tag].append(child_data)
            else:
                result[tag] = child_data
        
        if element.text and element.text.strip() and not result:
            return element.text.strip()
        
        return result
    
    async def get_properties(self) -> List[dict]:
        """
        GET operation: Retrieve list of properties/sites.
        Maps to getSiteList API.
        """
        soap_action = "http://tempuri.org/IRPXService/getsitelist"
        
        body = self._build_soap_envelope(f"""
            <tem:getsitelist>
                {self._build_auth_block()}
            </tem:getsitelist>
        """)
        
        result = await self._send_request(soap_action, body)
        
        # Transform to unified format
        properties = []
        site_list = result.get("SiteList", {})
        sites = site_list.get("Site", [])
        if not isinstance(sites, list):
            sites = [sites] if sites else []
        
        for site in sites:
            properties.append({
                "property_id": site.get("SiteID", ""),
                "name": site.get("SiteName", ""),
                "address": site.get("Address", ""),
                "city": site.get("City", ""),
                "state": site.get("State", ""),
                "zip": site.get("Zip", ""),
            })
        
        return properties
    
    async def get_units_raw(self, property_id: str) -> List[dict]:
        """
        GET operation: Retrieve raw unit data from RealPage API.
        Returns the raw unit dictionaries without transformation.
        """
        soap_action = "http://tempuri.org/IRPXService/unitlist"
        
        body = self._build_soap_envelope(f"""
            <tem:unitlist>
                {self._build_auth_block()}
            </tem:unitlist>
        """)
        
        result = await self._send_request(soap_action, body)
        
        unit_result = result.get("unitlistResult", result)
        unit_list = unit_result.get("UnitList", {}) if isinstance(unit_result, dict) else {}
        unit_data = unit_list.get("Unit", []) if isinstance(unit_list, dict) else []
        if not isinstance(unit_data, list):
            unit_data = [unit_data] if unit_data else []
        
        return [u for u in unit_data if isinstance(u, dict)]
    
    async def get_units(self, property_id: str) -> List[dict]:
        """
        GET operation: Retrieve unit information for a property.
        Maps to getUnitList API (uses unitlist action).
        """
        soap_action = "http://tempuri.org/IRPXService/unitlist"
        
        body = self._build_soap_envelope(f"""
            <tem:unitlist>
                {self._build_auth_block()}
            </tem:unitlist>
        """)
        
        result = await self._send_request(soap_action, body)
        
        # Transform to unified format
        # Response structure: unitlistResponse > unitlistResult > UnitList > Unit
        units = []
        unit_result = result.get("unitlistResult", result)
        unit_list = unit_result.get("UnitList", {}) if isinstance(unit_result, dict) else {}
        unit_data = unit_list.get("Unit", []) if isinstance(unit_list, dict) else []
        if not isinstance(unit_data, list):
            unit_data = [unit_data] if unit_data else []
        
        for unit in unit_data:
            if not isinstance(unit, dict):
                continue
            # Map Vacant field to status: F=occupied, T=vacant
            vacant_flag = unit.get("Vacant", "F")
            status = "vacant" if vacant_flag == "T" else "occupied"
            
            # RealPage Available flag - units available for rent (vacant ready OR occupied on notice)
            available_flag = unit.get("Available", "F") == "T"
            
            # Calculate days vacant from AvailableDate
            available_date = unit.get("AvailableDate")
            days_vacant = None
            if available_date and status == "vacant":
                days_vacant = self._calculate_days_since(available_date)
            
            # On notice date for exposure calculation
            on_notice_date = unit.get("OnNoticeForDate")
            
            units.append({
                "unit_id": unit.get("UnitID", ""),
                "unit_number": unit.get("UnitNumber", ""),
                "floorplan": unit.get("FloorplanID", ""),
                "floorplan_name": unit.get("FloorplanName", ""),
                "bedrooms": self._safe_int(unit.get("Bedrooms", 0)),
                "bathrooms": self._safe_float(unit.get("Bathrooms", 0)),
                "square_feet": self._safe_int(unit.get("RentableSqft", unit.get("GrossSqft", 0))),
                "market_rent": self._safe_float(unit.get("MarketRent", 0)),
                "status": status,
                "occupancy_status": status,  # Alias for compatibility
                "available": available_flag,  # RealPage Available flag
                "building": unit.get("BuildingName", ""),
                "floor": unit.get("Floor", ""),
                "available_date": available_date,
                "days_vacant": days_vacant,
                "on_notice_date": on_notice_date,
                "made_ready_date": unit.get("UnitMadeReadyDate"),
            })
        
        return units
    
    async def get_residents(
        self, 
        property_id: str, 
        status: Optional[str] = None
    ) -> List[dict]:
        """
        GET operation: Retrieve residents for a property.
        Uses getresidentlistinfo API for complete resident data with move-in/move-out dates.
        
        Args:
            property_id: Property identifier (uses configured siteid)
            status: Filter by status (current, future, past, notice)
        """
        soap_action = "http://tempuri.org/IRPXService/getresidentlistinfo"
        
        # Map status filter to RealPage format: P=Pending, C=Current, F=Former, ALL=all
        rp_status = "ALL"  # Default to all residents
        if status:
            status_map = {
                "current": "C",
                "future": "P",  # Pending = Future move-ins
                "past": "F",    # Former
                "notice": "C",  # Notice residents are still current
            }
            rp_status = status_map.get(status.lower(), "ALL")
        
        body = self._build_soap_envelope(f"""
            <tem:getresidentlistinfo>
                {self._build_auth_block()}
                <tem:getresidentlistinfo>
                    <tem:status>{rp_status}</tem:status>
                    <tem:headofhousehold>0</tem:headofhousehold>
                </tem:getresidentlistinfo>
            </tem:getresidentlistinfo>
        """)
        
        result = await self._send_request(soap_action, body)
        
        # Transform to unified format
        # Response structure varies - need to find the resident data
        residents = []
        
        # Response structure: getresidentlistinfoResult > residentlist > resident (lowercase)
        res_result = result.get("getresidentlistinfoResult", result)
        res_list = res_result.get("residentlist", res_result.get("ResidentList", {})) if isinstance(res_result, dict) else {}
        
        resident_data = res_list.get("resident", res_list.get("Resident", [])) if isinstance(res_list, dict) else []
        if not isinstance(resident_data, list):
            resident_data = [resident_data] if resident_data else []
        
        for res in resident_data:
            if not isinstance(res, dict):
                continue
            
            # Skip placeholder entries without unit info
            unit_id = res.get("unitid")
            if not unit_id:
                continue
            
            # Map leasestatus to our status format
            lease_status = res.get("leasestatus", "")
            mapped_status = self._map_lease_status_to_resident_status(lease_status)
            
            # Filter by status if provided (after mapping, not before)
            if status:
                status_map = {
                    "current": "C",
                    "future": "P",
                    "past": "F",
                    "notice": "C",
                }
                # Don't filter here since we already filtered in the API call
            
            residents.append({
                "resident_id": res.get("residentmemberid") or res.get("residentid") or "",
                "unit_id": str(unit_id),
                "unit_number": res.get("unitnumber") or "",
                "first_name": res.get("firstname") or "",
                "last_name": res.get("lastname") or "",
                "current_rent": self._safe_float(res.get("rent", 0)),
                "status": mapped_status,
                "lease_start": res.get("begindate") or res.get("leasestartdate"),
                "lease_end": res.get("enddate") or res.get("leaseenddate"),
                "move_in_date": res.get("moveindate"),
                "move_out_date": res.get("moveoutdate"),
                "notice_date": res.get("noticegivendate") or res.get("noticefordate"),
            })
        
        return residents
    
    def _map_lease_status_to_resident_status(self, lease_status: str) -> str:
        """Map RealPage leasestatus to unified resident status."""
        status_lower = lease_status.lower() if lease_status else ""
        if "current" in status_lower:
            return "Current"
        elif "former" in status_lower or "past" in status_lower:
            return "Past"
        elif "notice" in status_lower:
            return "Notice"
        elif "applicant" in status_lower and "former" not in status_lower:
            # "Applicant" or "Applicant - Lease Signed" = Future move-in (new residents)
            return "Future"
        elif "future lease" in status_lower:
            # "Future Lease" = renewals, treat as Current (not new move-ins)
            return "Current"
        return "Current"
    
    async def get_occupancy_metrics(self, property_id: str) -> dict:
        """
        GET operation: Calculate occupancy metrics from unit data.
        Derives metrics from getUnitList response.
        """
        units = await self.get_units(property_id)
        
        total_units = len(units)
        occupied_units = len([u for u in units if u["status"] == "occupied"])
        vacant_units = len([u for u in units if u["status"] == "vacant"])
        notice_units = len([u for u in units if u["status"] == "notice"])
        available_units = len([u for u in units if u.get("available", False)])
        
        # Leased = occupied + notice (still under lease)
        leased_units = occupied_units + notice_units
        
        physical_occupancy = (occupied_units / total_units * 100) if total_units > 0 else 0
        leased_percentage = (leased_units / total_units * 100) if total_units > 0 else 0
        
        return {
            "total_units": total_units,
            "occupied_units": occupied_units,
            "vacant_units": vacant_units,
            "leased_units": leased_units,
            "preleased_vacant": 0,  # Would need additional data
            "available_units": available_units,  # RealPage Available flag
            "physical_occupancy": round(physical_occupancy, 2),
            "leased_percentage": round(leased_percentage, 2),
        }
    
    async def get_lease_data(self, property_id: str) -> List[dict]:
        """
        GET operation: Retrieve lease information.
        Maps to getLeaseInfo API.
        """
        soap_action = "http://tempuri.org/IRPXService/getleaseinfo"
        
        body = self._build_soap_envelope(f"""
            <tem:getleaseinfo>
                {self._build_auth_block()}
            </tem:getleaseinfo>
        """)
        
        result = await self._send_request(soap_action, body)
        
        # Transform to unified format - try both uppercase and lowercase keys
        leases = []
        
        # Try different response structures (getleaseinfo may not be available for all sites)
        lease_info = result.get("getleaseinfoResult", result.get("GetLeaseInfo", result))
        
        lease_list = lease_info.get("leaselist", lease_info.get("Lease", lease_info.get("lease", []))) if isinstance(lease_info, dict) else []
        if isinstance(lease_list, dict):
            lease_list = lease_list.get("lease", lease_list.get("Lease", []))
        if not isinstance(lease_list, list):
            lease_list = [lease_list] if lease_list else []
        
        for lease in lease_list:
            leases.append({
                "resident_id": lease.get("ResidentID", ""),
                "unit_id": lease.get("UnitID", ""),
                "rent_amount": self._safe_float(lease.get("RentAmount", 0)),
                "lease_start": lease.get("LeaseStartDate"),
                "lease_end": lease.get("LeaseEndDate"),
                "lease_term": lease.get("LeaseTerm"),
            })
        
        return leases
    
    async def get_buildings(self) -> List[dict]:
        """
        GET operation: Retrieve building information.
        Maps to getBuildings API.
        """
        soap_action = "http://tempuri.org/IRPXService/getbuildings"
        
        body = self._build_soap_envelope(f"""
            <tem:getbuildings>
                {self._build_auth_block()}
            </tem:getbuildings>
        """)
        
        result = await self._send_request(soap_action, body)
        
        # Transform to unified format
        buildings = []
        building_list = result.get("BuildingList", {})
        building_data = building_list.get("Building", [])
        if not isinstance(building_data, list):
            building_data = [building_data] if building_data else []
        
        for bldg in building_data:
            buildings.append({
                "building_id": bldg.get("BuildingID", ""),
                "name": bldg.get("BuildingName", ""),
                "address": bldg.get("Address", ""),
            })
        
        return buildings
    
    async def get_rentable_items(self, property_id: str, date_needed: str = None) -> List[dict]:
        """
        GET operation: Retrieve rentable items (amenities, parking, storage).
        Maps to getRentableItems API.
        
        Args:
            property_id: Site ID
            date_needed: Optional date for availability check (YYYY-MM-DD format)
        
        Returns:
            List of rentable items with pricing and availability
        """
        from datetime import datetime
        
        if not date_needed:
            # Default to 30 days from now
            date_needed = (datetime.now().replace(day=1) + 
                          __import__('datetime').timedelta(days=32)).strftime("%Y-%m-%d")
        
        soap_action = "http://tempuri.org/IRPXService/getrentableitems"
        
        body = self._build_soap_envelope(f"""
            <tem:getrentableitems>
                {self._build_auth_block()}
                <tem:getrentableitemRequest>
                    <tem:unitid>0</tem:unitid>
                    <tem:dateneeded>{date_needed}</tem:dateneeded>
                    <tem:leaseid>0</tem:leaseid>
                </tem:getrentableitemRequest>
            </tem:getrentableitems>
        """)
        
        result = await self._send_request(soap_action, body)
        
        # Navigate response structure
        items = []
        try:
            response = result.get("getrentableitemsResult", {})
            response = response.get("GetRentableItemsResponse", {})
            response = response.get("Response", {})
            item_list = response.get("RentableItem", [])
            
            if not isinstance(item_list, list):
                item_list = [item_list] if item_list else []
            
            for item in item_list:
                items.append({
                    "rid_id": item.get("RidID"),
                    "item_name": item.get("ItemName"),
                    "item_type": item.get("ItemType"),
                    "description": item.get("Description"),
                    "billing_amount": self._safe_float(item.get("BillingAmount", 0)),
                    "frequency": item.get("Frequency"),  # M=Monthly, O=One-time
                    "transaction_code_id": item.get("TransactionCodeID"),
                    "in_service": item.get("InService"),
                    "serial_number": item.get("SerialNumber"),
                    "status": item.get("Status"),
                    "date_available": item.get("DateAvailable"),
                    "unit_id": item.get("UnitID"),
                    "lease_id": item.get("LeaseID"),
                    "resh_id": item.get("ReshID"),
                    "resident_member_id": item.get("ResidentMemberID"),
                    "start_date": item.get("StartDate"),
                    "end_date": item.get("EndDate"),
                })
        except Exception as e:
            print(f"Error parsing rentable items: {e}")
        
        return items
    
    async def get_leases_raw(self, property_id: str) -> List[dict]:
        """
        GET operation: Retrieve raw lease data with all fields.
        Maps to getLeaseInfo API.
        """
        soap_action = "http://tempuri.org/IRPXService/getleaseinfo"
        
        body = self._build_soap_envelope(f"""
            <tem:getleaseinfo>
                {self._build_auth_block()}
                <tem:getleaseinfo>
                    <tem:residentstatus>ALL</tem:residentstatus>
                    <tem:residentheldthestatus>365</tem:residentheldthestatus>
                </tem:getleaseinfo>
            </tem:getleaseinfo>
        """)
        
        result = await self._send_request(soap_action, body)
        
        # Navigate response structure: getleaseinfoResult -> GetLeaseInfo -> Leases -> Lease
        leases = []
        try:
            lease_result = result.get("getleaseinfoResult", {})
            get_lease_info = lease_result.get("GetLeaseInfo", {})
            leases_container = get_lease_info.get("Leases", {})
            lease_list = leases_container.get("Lease", [])
            
            if not isinstance(lease_list, list):
                lease_list = [lease_list] if lease_list else []
            
            for lease in lease_list:
                leases.append({
                    "lease_id": lease.get("LeaseID"),
                    "resh_id": lease.get("ReshID"),
                    "site_id": lease.get("SiteID"),
                    "unit_id": lease.get("UnitID"),
                    "unit_designation": lease.get("UnitDesignation"),
                    "lease_start_date": lease.get("LeaseBeginDate"),
                    "lease_end_date": lease.get("LeaseEndDate"),
                    "lease_term": self._safe_int(lease.get("LeaseTerm")),
                    "lease_term_desc": lease.get("LeaseTermDesc"),
                    "rent_amount": self._safe_float(lease.get("Rent", 0)),
                    "next_lease_id": lease.get("NextLeaseID"),
                    "prior_lease_id": lease.get("PriorLeaseID"),
                    "status": lease.get("LeaseStatus"),
                    "status_text": lease.get("LeaseStatusText"),
                    "type_code": lease.get("Typecode"),
                    "type_text": lease.get("TypeText"),
                    "move_in_date": lease.get("MoveInDate"),
                    "sched_move_in_date": lease.get("SchedMoveInDate"),
                    "applied_date": lease.get("AppliedDate"),
                    "active_date": lease.get("ActiveDate"),
                    "inactive_date": lease.get("InactiveDate"),
                    "last_renewal_date": lease.get("LastRenewalDate"),
                    "initial_lease_date": lease.get("InitialLeaseDate"),
                    "bill_date": lease.get("BillDate"),
                    "payment_due_date": lease.get("PaymentDueDate"),
                    "current_balance": self._safe_float(lease.get("CurBal", 0)),
                    "total_paid": self._safe_float(lease.get("TotPaid", 0)),
                    "late_day_of_month": self._safe_int(lease.get("LateDOM")),
                    "late_charge_pct": self._safe_float(lease.get("LCPct", 0)),
                    "evict": lease.get("Evict"),
                    "head_of_household_name": lease.get("HeadofHouseholdName"),
                })
        except Exception as e:
            print(f"Error parsing leases: {e}")
        
        return leases
    
    def _map_unit_status(self, rp_status: str) -> str:
        """Map RealPage unit status to unified status."""
        status_map = {
            "Occupied": "occupied",
            "Vacant": "vacant",
            "Notice": "notice",
            "Model": "model",
            "Down": "down",
            "Admin": "down",
        }
        return status_map.get(rp_status, rp_status.lower() if rp_status else "unknown")
    
    def _map_resident_status(self, rp_status: str) -> str:
        """Map RealPage resident status to unified status."""
        status_map = {
            "Current": "current",
            "Future": "future",
            "Past": "past",
            "Notice": "notice",
        }
        return status_map.get(rp_status, rp_status.lower() if rp_status else "unknown")
    
    def _map_resident_status_filter(self, status: Optional[str]) -> str:
        """Map unified status filter to RealPage resident type."""
        if not status:
            return "Current"
        
        filter_map = {
            "current": "Current",
            "future": "Future",
            "past": "Past",
            "notice": "Notice",
            "applicant": "Applicant",
            "all": "All",
        }
        return filter_map.get(status.lower(), "Current")
    
    def _safe_int(self, value) -> int:
        """Safely convert value to int."""
        try:
            return int(value) if value else 0
        except (ValueError, TypeError):
            return 0
    
    def _calculate_days_since(self, date_str: str) -> Optional[int]:
        """Calculate days since a date string."""
        if not date_str:
            return None
        try:
            from datetime import datetime
            date = datetime.strptime(date_str[:10], "%Y-%m-%d")
            return (datetime.now() - date).days
        except (ValueError, TypeError):
            return None
    
    def _safe_float(self, value) -> float:
        """Safely convert value to float."""
        try:
            return float(value) if value else 0.0
        except (ValueError, TypeError):
            return 0.0
