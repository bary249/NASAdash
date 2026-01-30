"""
AnyoneHome API Client - GET ONLY MIDDLEWARE
This client enforces read-only operations. No POST, PUT, DELETE allowed.
"""

import requests
from requests.auth import HTTPBasicAuth
from typing import Optional, Dict, Any
import json
import os
from functools import wraps


class GetOnlyMiddleware:
    """
    Middleware that enforces GET-only requests.
    Raises an exception if any non-GET method is attempted.
    """
    
    ALLOWED_METHODS = frozenset(['GET', 'HEAD', 'OPTIONS'])
    
    @classmethod
    def enforce(cls, method: str):
        """Raises exception if method is not GET/HEAD/OPTIONS"""
        if method.upper() not in cls.ALLOWED_METHODS:
            raise PermissionError(
                f"🚫 BLOCKED: HTTP {method.upper()} is not allowed. "
                f"Only {', '.join(cls.ALLOWED_METHODS)} methods are permitted. "
                f"This is a read-only client."
            )
    
    @classmethod
    def wrap_session(cls, session: requests.Session) -> requests.Session:
        """Wraps a session to enforce GET-only requests"""
        original_request = session.request
        
        @wraps(original_request)
        def safe_request(method, url, **kwargs):
            cls.enforce(method)
            return original_request(method, url, **kwargs)
        
        session.request = safe_request
        return session


class AnyoneHomeClient:
    """
    AnyoneHome API Client - READ ONLY
    
    Available endpoints:
    - retrieve_rental_quote: Get quote details
    - retrieve_accounts: List accounts
    - retrieve_property_list: List properties
    """
    
    def __init__(
        self,
        username: str = None,
        password: str = None,
        base_url: str = None
    ):
        self.base_url = base_url or os.getenv(
            'ANYONEHOME_BASE_URL',
            'https://api.anyonehome.com/api/leadmanagement'
        )
        self.username = username or os.getenv('ANYONEHOME_USERNAME')
        self.password = password or os.getenv('ANYONEHOME_PASSWORD')
        
        if not self.username or not self.password:
            raise ValueError("AnyoneHome credentials required")
        
        # Create session with GET-only middleware
        self._session = requests.Session()
        self._session = GetOnlyMiddleware.wrap_session(self._session)
        self._session.auth = HTTPBasicAuth(self.username, self.password)
        self._session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        })
    
    def _get(self, endpoint: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Perform a GET request (the only allowed method)
        """
        url = f"{self.base_url}/{endpoint}"
        
        response = self._session.get(url, params=params, timeout=30)
        
        result = {
            'status_code': response.status_code,
            'success': response.ok,
            'url': response.url
        }
        
        try:
            result['data'] = response.json()
        except json.JSONDecodeError:
            result['data'] = response.text
        
        return result
    
    # =========================================================================
    # GET ENDPOINTS ONLY
    # =========================================================================
    
    def retrieve_rental_quote(
        self,
        account_id: str,
        property_id: str,
        quote_id: str
    ) -> Dict[str, Any]:
        """
        GET /retrieverentalquote
        Retrieves rental quote details
        """
        return self._get('retrieverentalquote', {
            'accountid': account_id,
            'propertyid': property_id,
            'quoteid': quote_id
        })
    
    def retrieve_accounts(self) -> Dict[str, Any]:
        """
        GET /retrieveaccounts
        Retrieves list of accounts
        """
        return self._get('retrieveaccounts')
    
    def retrieve_property_list(
        self,
        management_id: str = None,
        property_id: str = None,
        listing_contact_email: str = None,
        page: int = None,
        include_details: bool = None,
        include_amenities: bool = None
    ) -> Dict[str, Any]:
        """
        GET /retrievepropertylist
        Retrieves list of properties
        """
        params = {}
        if management_id:
            params['managementid'] = management_id
        if property_id:
            params['propertyid'] = property_id
        if listing_contact_email:
            params['listingcontactemail'] = listing_contact_email
        if page is not None:
            params['page'] = str(page)
        if include_details is not None:
            params['includedetails'] = str(include_details).lower()
        if include_amenities is not None:
            params['includeamenities'] = str(include_amenities).lower()
        
        return self._get('retrievepropertylist', params if params else None)
    
    # =========================================================================
    # BLOCKED METHODS - These will raise PermissionError
    # =========================================================================
    
    def _blocked_method(self, *args, **kwargs):
        """Any write operation is blocked"""
        raise PermissionError(
            "🚫 This client is READ-ONLY. No write operations allowed."
        )
    
    # Explicitly block any potential write methods
    post = _blocked_method
    put = _blocked_method
    patch = _blocked_method
    delete = _blocked_method
    create = _blocked_method
    update = _blocked_method
    send = _blocked_method


# Default credentials from Postman environment
DEFAULT_CONFIG = {
    'base_url': 'https://api.anyonehome.com/api/leadmanagement',
    'username': 'Engineering-Suppliers@venn.city/JT*nh#AlH706gqK8aHG+!qWf&OJG+r_a',
    'password': 'faA0!8XS'
}


def get_client() -> AnyoneHomeClient:
    """Factory function to get a configured AnyoneHome client"""
    return AnyoneHomeClient(
        username=os.getenv('ANYONEHOME_USERNAME', DEFAULT_CONFIG['username']),
        password=os.getenv('ANYONEHOME_PASSWORD', DEFAULT_CONFIG['password']),
        base_url=os.getenv('ANYONEHOME_BASE_URL', DEFAULT_CONFIG['base_url'])
    )
