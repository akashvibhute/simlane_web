import logging
import pickle
from typing import Any, Dict, Optional

from django.conf import settings
from django.core.cache import cache
from iracingdataapi.client import irDataClient

logger = logging.getLogger(__name__)


class IRacingAPIError(Exception):
    """Custom exception for iRacing API errors with detailed information."""
    
    def __init__(self, message: str, status_code: Optional[int] = None, response_data: Optional[Dict] = None, endpoint: Optional[str] = None):
        self.status_code = status_code
        self.response_data = response_data
        self.endpoint = endpoint
        super().__init__(message)


class IRacingAPIClient(irDataClient):
    """
    iRacing API client with persistent system session caching and enhanced error handling.
    Subclasses irDataClient to add cache-based session restoration, validation, and comprehensive error handling.
    """

    CACHE_KEY = "iracing_session_system"
    CACHE_TIMEOUT = 86400  # 24 hours

    @classmethod
    def from_system_cache(cls):
        """
        Returns an IRacingAPIClient with a persistent session for the system account.
        Restores session cookies from cache if available and valid, otherwise authenticates and caches.
        """
        if not settings.IRACING_USERNAME or not settings.IRACING_PASSWORD:
            logger.warning("iRacing credentials not configured in settings")
            return None

        session_data = cache.get(cls.CACHE_KEY)
        client = cls(
            username=settings.IRACING_USERNAME,
            password=settings.IRACING_PASSWORD,
        )
        restored = False
        if session_data:
            try:
                client.session.cookies.update(pickle.loads(session_data))
                client.authenticated = True
                # Validate session
                try:
                    client.member_info()
                    logger.info(
                        "iRacing session restored and validated from cache",
                        extra={
                            "auth_type": "system",
                            "cache_hit": True,
                        },
                    )
                    restored = True
                except Exception:
                    logger.warning("Cached session invalid, re-authenticating")
                    cache.delete(cls.CACHE_KEY)
            except Exception:
                logger.exception(
                    "Failed to restore iRacing session from cache; re-authenticating",
                )
                cache.delete(cls.CACHE_KEY)

        if not restored:
            # Authenticate (will login on first API call)
            try:
                client.member_info()
                logger.info("iRacing system account authenticated and session cached")
            except Exception:
                logger.exception("Failed to authenticate iRacing system account")
                return None

        # Always cache the latest cookies after login or restore
        cache.set(
            cls.CACHE_KEY,
            pickle.dumps(client.session.cookies),
            cls.CACHE_TIMEOUT,
        )
        return client

    def save_to_cache(self):
        """
        Saves the current session cookies to cache. For future extensibility.
        """
        cache.set(
            self.CACHE_KEY,
            pickle.dumps(self.session.cookies),
            self.CACHE_TIMEOUT,
        )
        logger.info("Saved iRacing session cookies to cache")

    def _handle_response_error(self, response, endpoint: Optional[str] = None):
        """
        Handle and log HTTP response errors with detailed information.
        
        Args:
            response: The HTTP response object
            endpoint: The API endpoint that was called
            
        Raises:
            IRacingAPIError: With detailed error information
        """
        try:
            # Try to get response body as JSON
            response_data = response.json()
        except Exception:
            # If JSON parsing fails, get text content
            response_data = {"raw_content": response.text[:1000]}  # Limit to 1000 chars
        
        # Log detailed error information
        logger.error(
            "iRacing API request failed",
            extra={
                "status_code": response.status_code,
                "endpoint": endpoint,
                "response_headers": dict(response.headers),
                "response_data": response_data,
                "request_url": response.url,
                "request_method": response.request.method if response.request else None,
            }
        )
        
        # Create meaningful error messages based on status code
        if response.status_code == 400:
            message = f"Bad Request to iRacing API (400): Invalid parameters or request format"
        elif response.status_code == 401:
            message = f"Unauthorized access to iRacing API (401): Authentication failed"
        elif response.status_code == 403:
            message = f"Forbidden access to iRacing API (403): Access denied to resource"
        elif response.status_code == 404:
            message = f"Not Found (404): iRacing API endpoint or resource not found"
        elif response.status_code == 429:
            message = f"Rate Limited (429): Too many requests to iRacing API"
        elif response.status_code >= 500:
            message = f"Server Error ({response.status_code}): iRacing API server encountered an error"
        else:
            message = f"HTTP Error ({response.status_code}): iRacing API request failed"
        
        if endpoint:
            message += f" for endpoint: {endpoint}"
        
        # Include response data in message if it contains useful information
        if isinstance(response_data, dict):
            if "error" in response_data:
                message += f" - Error: {response_data['error']}"
            elif "message" in response_data:
                message += f" - Message: {response_data['message']}"
        
        raise IRacingAPIError(
            message=message,
            status_code=response.status_code,
            response_data=response_data,
            endpoint=endpoint
        )

    def _get_resource(self, endpoint: str, payload: Optional[dict] = None) -> Optional[Any]:
        """
        Override the parent _get_resource method to add enhanced error handling.
        
        Args:
            endpoint: The API endpoint to call
            payload: Optional parameters for the request
            
        Returns:
            The API response data
            
        Raises:
            IRacingAPIError: For non-200 responses with detailed error information
        """
        try:
            # Call the parent method which handles authentication, rate limiting, etc.
            return super()._get_resource(endpoint, payload)
        except RuntimeError as e:
            # Check if this is the "Unhandled Non-200 response" error from the parent class
            if len(e.args) >= 2 and "Unhandled Non-200 response" in str(e.args[0]):
                # Extract the response object from the error
                response = e.args[1]
                self._handle_response_error(response, endpoint)
            else:
                # Re-raise other RuntimeErrors as-is
                raise

    def series_season_schedule(self, season_id: int) -> Dict[str, Any]:
        """
        Get the detailed schedule for a specific season.

        Args:
            season_id (int): The iRacing season ID

        Returns:
            dict: A dict containing the season schedule with race weeks, tracks, and weather
        """
        payload = {"season_id": season_id}
        result = self._get_resource("/data/series/season_schedule", payload=payload)
        return result if isinstance(result, dict) else {}
