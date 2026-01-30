"""
Yardi PMS SOAP Client - READ-ONLY OPERATIONS ONLY
Implements PMSInterface for Yardi Voyager.

This client only implements GET operations. No PUT, POST, or DELETE.
"""
import httpx
from typing import List, Optional
from xml.etree import ElementTree as ET
from app.config import get_settings
from app.clients.pms_interface import PMSInterface, PMSType


class YardiClient(PMSInterface):
    """
    SOAP client for Yardi PMS APIs.
    Implements PMSInterface for unified PMS access.
    
    IMPORTANT: This client only implements READ operations (Get*).
    No write operations are permitted.
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.headers = {
            "Content-Type": "text/xml; charset=utf-8",
        }
    
    @property
    def pms_type(self) -> PMSType:
        return PMSType.YARDI
    
    def _build_auth_xml(self, use_ils: bool = False) -> str:
        """Build the common authentication XML block."""
        entity = self.settings.yardi_ils_interface_entity if use_ils else self.settings.yardi_interface_entity
        license = self.settings.yardi_ils_interface_license if use_ils else self.settings.yardi_interface_license
        return f"""<UserName>{self.settings.yardi_username}</UserName>
            <Password>{self.settings.yardi_password}</Password>
            <ServerName>{self.settings.yardi_server_name}</ServerName>
            <Database>{self.settings.yardi_database}</Database>
            <Platform>{self.settings.yardi_platform}</Platform>
            <InterfaceEntity>{entity}</InterfaceEntity>
            <InterfaceLicense>{license}</InterfaceLicense>"""
    
    async def get_property_configurations(self) -> dict:
        """
        GET operation: Retrieve property configurations.
        Returns list of properties with their codes and names.
        """
        soap_action = "http://tempuri.org/YSI.Interfaces.WebServices/ItfResidentData/GetPropertyConfigurations"
        
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <GetPropertyConfigurations xmlns="http://tempuri.org/YSI.Interfaces.WebServices/ItfResidentData">
            {self._build_auth_xml()}
        </GetPropertyConfigurations>
    </soap:Body>
</soap:Envelope>"""
        
        return await self._send_request(
            self.settings.yardi_resident_url, 
            soap_action, 
            body
        )
    
    async def get_unit_information(self, property_id: str) -> dict:
        """
        GET operation: Retrieve unit information for a property.
        Used for: Occupancy, Vacancy, Unit Types, Square Footage.
        """
        soap_action = "http://tempuri.org/YSI.Interfaces.WebServices/ItfResidentData/GetUnitInformation"
        
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <GetUnitInformation xmlns="http://tempuri.org/YSI.Interfaces.WebServices/ItfResidentData">
            {self._build_auth_xml()}
            <YardiPropertyId>{property_id}</YardiPropertyId>
        </GetUnitInformation>
    </soap:Body>
</soap:Envelope>"""
        
        return await self._send_request(
            self.settings.yardi_resident_url, 
            soap_action, 
            body
        )
    
    async def get_residents_by_status(
        self, 
        property_id: str, 
        status: str = "Current^Applicant^Future^Notice"
    ) -> dict:
        """
        GET operation: Retrieve residents filtered by status.
        Status options: Current, Future, Past, Notice, Applicant, Eviction, Denied, Canceled
        Use ^ to separate multiple statuses.
        Used for: Move-ins, Move-outs, Exposure, Renewals.
        """
        soap_action = "http://tempuri.org/YSI.Interfaces.WebServices/ItfResidentData/GetResidentsByStatus"
        
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <GetResidentsByStatus xmlns="http://tempuri.org/YSI.Interfaces.WebServices/ItfResidentData">
            {self._build_auth_xml()}
            <YardiPropertyId>{property_id}</YardiPropertyId>
            <Status>{status}</Status>
            <DateFrom>01/01/1900</DateFrom>
        </GetResidentsByStatus>
    </soap:Body>
</soap:Envelope>"""
        
        return await self._send_request(
            self.settings.yardi_resident_url, 
            soap_action, 
            body
        )
    
    async def get_resident_lease_charges(self, property_id: str) -> dict:
        """
        GET operation: Retrieve lease charges for residents.
        Used for: In-Place Effective Rent, Lease Charges.
        """
        soap_action = "http://tempuri.org/YSI.Interfaces.WebServices/ItfResidentData/GetResidentLeaseCharges_Login"
        
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <GetResidentLeaseCharges_Login xmlns="http://tempuri.org/YSI.Interfaces.WebServices/ItfResidentData">
            {self._build_auth_xml()}
            <YardiPropertyId>{property_id}</YardiPropertyId>
        </GetResidentLeaseCharges_Login>
    </soap:Body>
</soap:Envelope>"""
        
        return await self._send_request(
            self.settings.yardi_resident_url, 
            soap_action, 
            body
        )
    
    async def get_available_units(self, property_id: str) -> dict:
        """
        GET operation: Retrieve available units with pricing.
        Used for: Asking Rents, Market Rent, Effective Rent by floorplan.
        """
        soap_action = "http://tempuri.org/YSI.Interfaces.WebServices/ItfILSGuestCard/AvailableUnits_Login"
        
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <AvailableUnits_Login xmlns="http://tempuri.org/YSI.Interfaces.WebServices/ItfILSGuestCard">
            {self._build_auth_xml()}
            <YardiPropertyId>{property_id}</YardiPropertyId>
        </AvailableUnits_Login>
    </soap:Body>
</soap:Envelope>"""
        
        return await self._send_request(
            self.settings.yardi_ils_url, 
            soap_action, 
            body
        )
    
    async def get_guest_activity(
        self, 
        property_id: str,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None
    ) -> dict:
        """
        GET operation: Retrieve guest/prospect activity.
        Used for: Leads, Tours, Applications, Lease Signs, Conversion metrics.
        EventTypes: Email, CallFromProspect, Show, Appointment, Application, LeaseSign, ApplicationDenied
        """
        soap_action = "http://tempuri.org/YSI.Interfaces.WebServices/ItfILSGuestCard/GetYardiGuestActivity_Login"
        
        date_filter = ""
        if from_date:
            date_filter += f"<FromDate>{from_date}</FromDate>"
        if to_date:
            date_filter += f"<ToDate>{to_date}</ToDate>"
        
        body = f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
    <soap:Body>
        <GetYardiGuestActivity_Login xmlns="http://tempuri.org/YSI.Interfaces.WebServices/ItfILSGuestCard">
            {self._build_auth_xml(use_ils=True)}
            <YardiPropertyId>{property_id}</YardiPropertyId>
            {date_filter}
        </GetYardiGuestActivity_Login>
    </soap:Body>
</soap:Envelope>"""
        
        return await self._send_request(
            self.settings.yardi_ils_url, 
            soap_action, 
            body
        )
    
    async def _send_request(self, url: str, soap_action: str, body: str) -> dict:
        """Send SOAP request and parse response."""
        headers = {
            **self.headers,
            "SOAPAction": soap_action
        }
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, headers=headers, content=body)
            response.raise_for_status()
            
            return self._parse_xml_response(response.text)
    
    def _parse_xml_response(self, xml_text: str) -> dict:
        """Parse SOAP XML response into a dictionary."""
        try:
            root = ET.fromstring(xml_text)
            namespaces = {
                'soap': 'http://schemas.xmlsoap.org/soap/envelope/'
            }
            
            body = root.find('.//soap:Body', namespaces)
            if body is None:
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
    
    # =========================================================================
    # PMSInterface Implementation Methods
    # =========================================================================
    
    async def get_properties(self) -> List[dict]:
        """
        GET operation: Retrieve list of properties.
        Maps to GetPropertyConfigurations API.
        """
        result = await self.get_property_configurations()
        
        properties = []
        prop_list = result.get("PropertyConfigurations", {}).get("Property", [])
        if not isinstance(prop_list, list):
            prop_list = [prop_list] if prop_list else []
        
        for prop in prop_list:
            properties.append({
                "property_id": prop.get("Code", ""),
                "name": prop.get("MarketingName", prop.get("Code", "")),
                "address": prop.get("Address", ""),
            })
        
        return properties
    
    async def get_units(self, property_id: str) -> List[dict]:
        """
        GET operation: Retrieve unit information for a property.
        Maps to GetUnitInformation API.
        """
        result = await self.get_unit_information(property_id)
        
        units = []
        unit_list = result.get("UnitInformation", {}).get("Unit", [])
        if not isinstance(unit_list, list):
            unit_list = [unit_list] if unit_list else []
        
        for unit in unit_list:
            status = self._map_unit_status(unit.get("UnitStatus", ""))
            units.append({
                "unit_id": unit.get("UnitCode", ""),
                "unit_number": unit.get("UnitCode", ""),
                "floorplan": unit.get("UnitType", ""),
                "floorplan_name": unit.get("UnitType", ""),
                "bedrooms": self._safe_int(unit.get("Bedrooms", 0)),
                "bathrooms": self._safe_float(unit.get("Bathrooms", 0)),
                "square_feet": self._safe_int(unit.get("SQFT", 0)),
                "market_rent": self._safe_float(unit.get("MarketRent", 0)),
                "status": status,
                "building": unit.get("Building", ""),
            })
        
        return units
    
    async def get_residents(
        self, 
        property_id: str, 
        status: Optional[str] = None
    ) -> List[dict]:
        """
        GET operation: Retrieve residents for a property.
        Maps to GetResidentsByStatus API.
        """
        # Map unified status to Yardi status filter
        yardi_status = self._map_resident_status_filter(status)
        result = await self.get_residents_by_status(property_id, yardi_status)
        
        residents = []
        res_list = result.get("Residents", {}).get("Resident", [])
        if not isinstance(res_list, list):
            res_list = [res_list] if res_list else []
        
        for res in res_list:
            residents.append({
                "resident_id": res.get("ResidentCode", ""),
                "unit_id": res.get("UnitCode", ""),
                "unit_number": res.get("UnitCode", ""),
                "first_name": res.get("FirstName", ""),
                "last_name": res.get("LastName", ""),
                "current_rent": self._safe_float(res.get("Rent", 0)),
                "status": self._map_resident_status(res.get("Status", "")),
                "lease_start": res.get("LeaseFromDate"),
                "lease_end": res.get("LeaseToDate"),
                "move_in_date": res.get("MoveInDate"),
                "move_out_date": res.get("MoveOutDate"),
            })
        
        return residents
    
    async def get_occupancy_metrics(self, property_id: str) -> dict:
        """
        GET operation: Calculate occupancy metrics from unit data.
        """
        units = await self.get_units(property_id)
        
        total_units = len(units)
        occupied_units = len([u for u in units if u["status"] == "occupied"])
        vacant_units = len([u for u in units if u["status"] == "vacant"])
        notice_units = len([u for u in units if u["status"] == "notice"])
        
        leased_units = occupied_units + notice_units
        
        physical_occupancy = (occupied_units / total_units * 100) if total_units > 0 else 0
        leased_percentage = (leased_units / total_units * 100) if total_units > 0 else 0
        
        return {
            "total_units": total_units,
            "occupied_units": occupied_units,
            "vacant_units": vacant_units,
            "leased_units": leased_units,
            "preleased_vacant": 0,
            "physical_occupancy": round(physical_occupancy, 2),
            "leased_percentage": round(leased_percentage, 2),
        }
    
    async def get_lease_data(self, property_id: str) -> List[dict]:
        """
        GET operation: Retrieve lease/charge information.
        Maps to GetResidentLeaseCharges_Login API.
        """
        result = await self.get_resident_lease_charges(property_id)
        
        leases = []
        lease_list = result.get("LeaseCharges", {}).get("Resident", [])
        if not isinstance(lease_list, list):
            lease_list = [lease_list] if lease_list else []
        
        for lease in lease_list:
            leases.append({
                "resident_id": lease.get("ResidentCode", ""),
                "unit_id": lease.get("UnitCode", ""),
                "rent_amount": self._safe_float(lease.get("TotalCharges", 0)),
                "lease_start": lease.get("LeaseFromDate"),
                "lease_end": lease.get("LeaseToDate"),
            })
        
        return leases
    
    def _map_unit_status(self, yardi_status: str) -> str:
        """Map Yardi unit status to unified status."""
        status_map = {
            "Occupied": "occupied",
            "Vacant": "vacant",
            "VacantReady": "vacant",
            "VacantNotReady": "vacant",
            "Notice": "notice",
            "Model": "model",
            "Down": "down",
            "Admin": "down",
        }
        return status_map.get(yardi_status, yardi_status.lower() if yardi_status else "unknown")
    
    def _map_resident_status(self, yardi_status: str) -> str:
        """Map Yardi resident status to unified status."""
        status_map = {
            "Current": "current",
            "Future": "future",
            "Past": "past",
            "Notice": "notice",
            "Applicant": "applicant",
        }
        return status_map.get(yardi_status, yardi_status.lower() if yardi_status else "unknown")
    
    def _map_resident_status_filter(self, status: Optional[str]) -> str:
        """Map unified status filter to Yardi status filter."""
        if not status:
            return "Current"
        
        filter_map = {
            "current": "Current",
            "future": "Future",
            "past": "Past",
            "notice": "Notice",
            "applicant": "Applicant",
            "all": "Current^Applicant^Future^Notice^Past",
        }
        return filter_map.get(status.lower(), "Current")
    
    def _safe_int(self, value) -> int:
        """Safely convert value to int."""
        try:
            return int(value) if value else 0
        except (ValueError, TypeError):
            return 0
    
    def _safe_float(self, value) -> float:
        """Safely convert value to float."""
        try:
            return float(value) if value else 0.0
        except (ValueError, TypeError):
            return 0.0
