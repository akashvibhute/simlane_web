"""
iRacing Data API Client

A client for the iRacing Data API with error handling, rate limiting, and integration.
"""

import base64
import hashlib
import json
import logging
import pickle
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union

from .types import (
    Car, CarAsset, CarClass, MemberInfo, PastSeasonsResponse,
    SeasonScheduleResponse, Series, SeriesAsset, SeriesSeasons,
    Track, TrackAsset
)

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class IRacingAPIError(Exception):
    """Custom exception for iRacing API errors with detailed information."""
    
    def __init__(
        self, 
        message: str, 
        status_code: Optional[int] = None, 
        response_data: Optional[Dict] = None, 
        endpoint: Optional[str] = None,
        response_headers: Optional[Dict] = None
    ):
        self.status_code = status_code
        self.response_data = response_data
        self.endpoint = endpoint
        self.response_headers = response_headers
        super().__init__(message)

    def __str__(self):
        base_msg = super().__str__()
        if self.status_code:
            base_msg += f" (Status: {self.status_code})"
        if self.endpoint:
            base_msg += f" (Endpoint: {self.endpoint})"
        return base_msg


class IRacingMaintenanceError(IRacingAPIError):
    """Exception raised when the iRacing API is unavailable due to maintenance (HTTP 503)."""

    pass


class IRacingClient:
    """
    Custom iRacing Data API client with Django integration.
    
    Features:
    - Session caching with Django cache framework
    - Comprehensive error handling and logging
    - Built-in rate limiting and retry logic
    - Only implements endpoints we actually use
    """
    
    BASE_URL = "https://members-ng.iracing.com"
    AUTH_URL = "https://members-ng.iracing.com/auth"
    
    # Cache settings
    SESSION_CACHE_KEY = "iracing_session_system"
    SESSION_CACHE_TIMEOUT = 86400  # 24 hours
    DATA_CACHE_TIMEOUT = 300  # 5 minutes for data caching
    
    # Rate limiting settings
    DEFAULT_RATE_LIMIT_DELAY = 1.0  # 1 second between requests
    MAX_RETRIES = 3
    RETRY_DELAY = 2.0  # 2 seconds between retries
    
    def __init__(self, username: Optional[str] = None, password: Optional[str] = None):
        """
        Initialize the iRacing client.
        
        Args:
            username: iRacing username (defaults to settings.IRACING_USERNAME)
            password: iRacing password (defaults to settings.IRACING_PASSWORD)
        """
        self.username = username or settings.IRACING_USERNAME
        self.password = password or settings.IRACING_PASSWORD
        self.session = requests.Session()
        self.authenticated = False
        self.last_request_time = 0
        
        if not self.username or not self.password:
            raise IRacingAPIError("iRacing credentials not configured")
    
    @classmethod
    def from_settings(cls) -> 'IRacingClient':
        """Create client instance using Django settings."""
        return cls()
    
    def _encode_password(self, username: str, password: str) -> str:
        """Encode password using iRacing's method."""
        initial_hash = hashlib.sha256(
            (password + username.lower()).encode("utf-8")
        ).digest()
        return base64.b64encode(initial_hash).decode("utf-8")
    
    def _rate_limit(self):
        """Implement rate limiting between requests."""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.DEFAULT_RATE_LIMIT_DELAY:
            sleep_time = self.DEFAULT_RATE_LIMIT_DELAY - elapsed
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _load_session_from_cache(self) -> bool:
        """Load session cookies from Django cache."""
        try:
            session_data = cache.get(self.SESSION_CACHE_KEY)
            if session_data:
                self.session.cookies.update(pickle.loads(session_data))
                self.authenticated = True
                logger.debug("Loaded iRacing session from cache")
                return True
        except Exception as e:
            logger.warning(f"Failed to load session from cache: {e}")
            cache.delete(self.SESSION_CACHE_KEY)
        return False
    
    def _save_session_to_cache(self):
        """Save session cookies to Django cache."""
        try:
            cache.set(
                self.SESSION_CACHE_KEY,
                pickle.dumps(self.session.cookies),
                self.SESSION_CACHE_TIMEOUT
            )
            logger.debug("Saved iRacing session to cache")
        except Exception as e:
            logger.warning(f"Failed to save session to cache: {e}")
    
    def _login(self) -> bool:
        """Authenticate with iRacing API."""
        logger.info("Authenticating with iRacing API")
        
        headers = {"Content-Type": "application/json"}
        data = {
            "email": self.username,
            "password": self._encode_password(self.username or "", self.password or "")
        }
        
        try:
            response = self.session.post(
                self.AUTH_URL,
                headers=headers,
                json=data,
                timeout=10.0
            )
            
            if response.status_code == 429:
                self._handle_rate_limit(response)
                return self._login()  # Retry after rate limit
            
            if response.status_code == 200:
                response_data = response.json()
                if response_data.get("authcode"):
                    self.authenticated = True
                    self._save_session_to_cache()
                    logger.info("Successfully authenticated with iRacing")
                    return True
                else:
                    raise IRacingAPIError(
                        f"Authentication failed: {response_data}",
                        status_code=response.status_code,
                        response_data=response_data,
                        endpoint="/auth"
                    )
            else:
                self._handle_error_response(response, "/auth")
                
        except requests.Timeout:
            raise IRacingAPIError("Authentication timed out", endpoint="/auth")
        except requests.ConnectionError as e:
            raise IRacingAPIError(f"Connection error during authentication: {e}", endpoint="/auth")
        
        return False
    
    def _handle_rate_limit(self, response):
        """Handle rate limiting response."""
        reset_header = response.headers.get("x-ratelimit-reset")
        if reset_header:
            try:
                reset_time = datetime.fromtimestamp(int(reset_header))
                wait_time = (reset_time - datetime.now()).total_seconds() + 0.5
                if wait_time > 0:
                    logger.warning(f"Rate limited by iRacing API, waiting {wait_time:.1f} seconds")
                    time.sleep(wait_time)
                    return
            except (ValueError, TypeError):
                pass
        
        # Fallback: wait 60 seconds
        logger.warning("Rate limited by iRacing API, waiting 60 seconds")
        time.sleep(60)
    
    def _handle_error_response(self, response, endpoint: str):
        """Handle non-200 HTTP responses."""
        try:
            response_data = response.json()
        except Exception:
            response_data = {"raw_content": response.text[:1000]}
        
        # Log detailed error information
        logger.error(
            "iRacing API request failed",
            extra={
                "status_code": response.status_code,
                "endpoint": endpoint,
                "response_headers": dict(response.headers),
                "response_data": response_data,
                "request_url": str(response.url),
                "request_method": response.request.method if response.request else None,
            }
        )
        
        # Create meaningful error messages
        error_messages = {
            400: "Bad Request: Invalid parameters or request format",
            401: "Unauthorized: Authentication failed or expired",
            403: "Forbidden: Access denied to resource",
            404: "Not Found: Endpoint or resource not found",
            429: "Rate Limited: Too many requests",
            500: "Internal Server Error: iRacing server error",
            502: "Bad Gateway: iRacing server temporarily unavailable",
            503: "Service Unavailable: iRacing server temporarily unavailable",
        }
        
        message = error_messages.get(
            response.status_code,
            f"HTTP Error ({response.status_code}): Request failed"
        )
        
        # Include response error details if available
        if isinstance(response_data, dict):
            if "error" in response_data:
                message += f" - {response_data['error']}"
            elif "message" in response_data:
                message += f" - {response_data['message']}"
        
        if response.status_code == 503:
            # Detect maintenance mode specifically
            is_maintenance = False
            if isinstance(response_data, dict):
                error_val = str(response_data.get("error", "")).lower()
                # Typical maintenance payload example: {"error": "Site Maintenance", ...}
                if "maintenance" in error_val:
                    is_maintenance = True
            if is_maintenance:
                message = "Service Unavailable: iRacing API is undergoing maintenance. Please try again later."
                raise IRacingMaintenanceError(
                    message=message,
                    status_code=response.status_code,
                    response_data=response_data,
                    endpoint=endpoint,
                    response_headers=dict(response.headers),
                )
        
        raise IRacingAPIError(
            message=message,
            status_code=response.status_code,
            response_data=response_data,
            endpoint=endpoint,
            response_headers=dict(response.headers)
        )
    
    def _ensure_authenticated(self):
        """Ensure we have a valid authentication session."""
        if self.authenticated:
            return
        
        # Try to load session from cache first
        if self._load_session_from_cache():
            # Validate session with a simple API call
            try:
                self._make_request("/data/member/info")
                logger.info("Restored and validated iRacing session from cache")
                return
            except IRacingAPIError:
                logger.warning("Cached session invalid, re-authenticating")
                self.authenticated = False
                cache.delete(self.SESSION_CACHE_KEY)
        
        # Authenticate if no valid cached session
        if not self._login():
            raise IRacingAPIError("Failed to authenticate with iRacing API")
    
    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
        use_cache: bool = True,
        cache_timeout: Optional[int] = None
    ) -> Union[Dict, List]:
        """
        Make an authenticated request to the iRacing API.
        
        Args:
            endpoint: API endpoint path
            params: Query parameters
            use_cache: Whether to use caching for this request
            cache_timeout: Cache timeout override
            
        Returns:
            API response data
        """
        # Check cache first if enabled
        cache_key = None
        if use_cache:
            cache_key = f"iracing_api:{endpoint}:{hash(str(sorted((params or {}).items())))}"
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                logger.debug(f"Cache hit for endpoint: {endpoint}")
                return cached_data
        
        self._ensure_authenticated()
        self._rate_limit()
        
        url = f"{self.BASE_URL}{endpoint}"
        
        for attempt in range(self.MAX_RETRIES + 1):
            try:
                response = self.session.get(url, params=params, timeout=30.0)
                
                # Handle authentication issues
                if response.status_code == 401:
                    logger.warning("Received 401, re-authenticating")
                    self.authenticated = False
                    cache.delete(self.SESSION_CACHE_KEY)
                    if attempt < self.MAX_RETRIES:
                        self._ensure_authenticated()
                        continue
                
                # Handle rate limiting
                if response.status_code == 429:
                    if attempt < self.MAX_RETRIES:
                        self._handle_rate_limit(response)
                        continue
                
                # Handle successful response
                if response.status_code == 200:
                    try:
                        data = response.json()
                        
                        # Handle link-style responses (chunked data)
                        if isinstance(data, dict) and "link" in data:
                            data = self._fetch_linked_data(data["link"])
                        
                        # Cache successful response
                        if use_cache and cache_key:
                            timeout = cache_timeout or self.DATA_CACHE_TIMEOUT
                            cache.set(cache_key, data, timeout)
                            logger.debug(f"Cached response for endpoint: {endpoint}")
                        
                        return data
                        
                    except json.JSONDecodeError as e:
                        raise IRacingAPIError(
                            f"Invalid JSON response: {e}",
                            status_code=response.status_code,
                            endpoint=endpoint
                        )
                
                # Handle error response
                self._handle_error_response(response, endpoint)
                
            except requests.Timeout:
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"Request timeout, retrying ({attempt + 1}/{self.MAX_RETRIES})")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise IRacingAPIError(f"Request timeout after {self.MAX_RETRIES} retries", endpoint=endpoint)
            
            except requests.ConnectionError as e:
                if attempt < self.MAX_RETRIES:
                    logger.warning(f"Connection error, retrying ({attempt + 1}/{self.MAX_RETRIES}): {e}")
                    time.sleep(self.RETRY_DELAY * (attempt + 1))
                    continue
                raise IRacingAPIError(f"Connection error after {self.MAX_RETRIES} retries: {e}", endpoint=endpoint)
        
        raise IRacingAPIError(f"Request failed after {self.MAX_RETRIES} retries", endpoint=endpoint)
    
    def _fetch_linked_data(self, link_url: str) -> Union[Dict, List]:
        """Fetch data from a chunked/linked response."""
        try:
            response = self.session.get(link_url, timeout=30.0)
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to fetch linked data: {response.status_code}")
                return {}
        except Exception as e:
            logger.warning(f"Error fetching linked data: {e}")
            return {}
    
    # API Methods - Only implement what we need
    
    def get_member_info(self) -> MemberInfo:
        """Get member information for the authenticated user."""
        result = self._make_request("/data/member/info")
        if not isinstance(result, dict):
            raise IRacingAPIError("Invalid response format for member info", endpoint="/data/member/info")
        return result  # type: ignore
    
    def get_series(self) -> List[Series]:
        """Get all available series."""
        result = self._make_request("/data/series/get")
        if not isinstance(result, list):
            raise IRacingAPIError("Invalid response format for series", endpoint="/data/series/get")
        return result  # type: ignore
    
    def get_series_assets(self) -> Dict[str, SeriesAsset]:
        """Get series assets (logos, descriptions, etc.)."""
        result = self._make_request("/data/series/assets")
        if not isinstance(result, dict):
            raise IRacingAPIError("Invalid response format for series assets", endpoint="/data/series/assets")
        return result  # type: ignore
    
    def get_series_seasons(self, include_series: bool = False) -> List[SeriesSeasons]:
        """Get all current series seasons."""
        params = {"include_series": include_series}
        result = self._make_request("/data/series/seasons", params=params)
        if not isinstance(result, list):
            raise IRacingAPIError("Invalid response format for series seasons", endpoint="/data/series/seasons")
        return result  # type: ignore
    
    def get_series_past_seasons(self, series_id: int) -> PastSeasonsResponse:
        """Get past seasons for a specific series."""
        params = {"series_id": series_id}
        result = self._make_request("/data/series/past_seasons", params=params)
        if not isinstance(result, dict):
            raise IRacingAPIError("Invalid response format for past seasons", endpoint="/data/series/past_seasons")
        return result  # type: ignore
    
    def get_series_season_schedule(self, season_id: int) -> SeasonScheduleResponse:
        """Get the detailed schedule for a specific season."""
        params = {"season_id": season_id}
        result = self._make_request("/data/series/season_schedule", params=params)
        if not isinstance(result, dict):
            raise IRacingAPIError("Invalid response format for season schedule", endpoint="/data/series/season_schedule")
        return result  # type: ignore
    
    def get_cars(self) -> List[Car]:
        """Get all available cars."""
        result = self._make_request("/data/car/get")
        if not isinstance(result, list):
            raise IRacingAPIError("Invalid response format for cars", endpoint="/data/car/get")
        return result  # type: ignore
    
    def get_car_assets(self) -> Dict[str, CarAsset]:
        """Get car assets (images, etc.)."""
        result = self._make_request("/data/car/assets")
        if not isinstance(result, dict):
            raise IRacingAPIError("Invalid response format for car assets", endpoint="/data/car/assets")
        return result  # type: ignore
        
    def get_tracks(self) -> List[Track]:
        """Get all available tracks."""
        result = self._make_request("/data/track/get")
        if not isinstance(result, list):
            raise IRacingAPIError("Invalid response format for tracks", endpoint="/data/track/get")
        return result  # type: ignore
    
    def get_track_assets(self) -> Dict[str, TrackAsset]:
        """Get track assets (images, etc.)."""
        result = self._make_request("/data/track/assets")
        if not isinstance(result, dict):
            raise IRacingAPIError("Invalid response format for track assets", endpoint="/data/track/assets")
        return result  # type: ignore
    
    def get_car_classes(self) -> List[CarClass]:
        """Get all car classes."""
        result = self._make_request("/data/carclass/get")
        if not isinstance(result, list):
            raise IRacingAPIError("Invalid response format for car classes", endpoint="/data/carclass/get")
        return result  # type: ignore

    # Stats API Methods
    def stats_member_summary(self, cust_id: int = None) -> Dict[str, Any]:
        """Get member summary statistics."""
        params = {}
        if cust_id is not None:
            params["cust_id"] = cust_id
        result = self._make_request("/data/stats/member_summary", params=params)
        if not isinstance(result, dict):
            raise IRacingAPIError("Invalid response format for member summary", endpoint="/data/stats/member_summary")
        return result

    def stats_member_recent_races(self, cust_id: int = None) -> Dict[str, Any]:
        """Get member's recent race results."""
        params = {}
        if cust_id is not None:
            params["cust_id"] = cust_id
        result = self._make_request("/data/stats/member_recent_races", params=params)
        if not isinstance(result, dict):
            raise IRacingAPIError("Invalid response format for member recent races", endpoint="/data/stats/member_recent_races")
        return result

    def stats_member_yearly(self, cust_id: int = None) -> Dict[str, Any]:
        """Get member's yearly statistics."""
        params = {}
        if cust_id is not None:
            params["cust_id"] = cust_id
        result = self._make_request("/data/stats/member_yearly", params=params)
        if not isinstance(result, dict):
            raise IRacingAPIError("Invalid response format for member yearly stats", endpoint="/data/stats/member_yearly")
        return result

    def member_profile(self, cust_id: int = None) -> Dict[str, Any]:
        """Get member profile information."""
        params = {}
        if cust_id is not None:
            params["cust_id"] = cust_id
        result = self._make_request("/data/member/profile", params=params)
        if not isinstance(result, dict):
            raise IRacingAPIError("Invalid response format for member profile", endpoint="/data/member/profile")
        return result


# Global instance for easy access
iracing_client = None


def get_iracing_client() -> IRacingClient:
    """Get or create the global iRacing client instance."""
    global iracing_client
    if iracing_client is None:
        iracing_client = IRacingClient.from_settings()
    return iracing_client 