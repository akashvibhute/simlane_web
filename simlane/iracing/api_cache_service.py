"""
Enhanced iRacing API Service with S3 caching.

This service wraps the existing IRacingAPIService to add intelligent caching
using S3 storage. It checks S3 first before making API calls, reducing load
on the iRacing API and providing better development flexibility.
"""

import logging
from typing import Any, Optional, List
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from simlane.iracing.services import IRacingAPIService
from simlane.iracing.types import Series, SeriesSeasons, PastSeasonsResponse, CarClass, Car, Track
from simlane.iracing.s3_cache_storage import api_response_storage

logger = logging.getLogger(__name__)


class CachedIRacingAPIService:
    """
    Enhanced iRacing API service with S3 caching.
    
    This service provides intelligent caching using S3 storage:
    1. Check S3 for existing data first
    2. Only hit the API if no data exists or refresh=True
    3. Store new API responses in S3 for future use
    4. Respect cache TTL settings for different data types
    """
    
    def __init__(self, base_service: Optional[IRacingAPIService] = None):
        self.base_service = base_service or IRacingAPIService()
        self.cache_ttl = getattr(settings, 'API_RESPONSE_CACHE_TTL', {})
    
    def _is_cache_valid(self, data_type: str, age_seconds: Optional[float], refresh: bool = False) -> bool:
        """
        Determine if cached data is still valid.
        
        Args:
            data_type: Type of data ('series', 'seasons', 'schedules', etc.)
            age_seconds: Age of cached data in seconds (None if no cached data)
            refresh: Whether to force refresh (bypass cache)
            
        Returns:
            True if cache should be used, False if fresh fetch is needed
        """
        if refresh:
            logger.info(f"Refresh flag set - bypassing cache for {data_type}")
            return False
            
        if age_seconds is None:
            logger.info(f"No cached data found for {data_type}")
            return False
            
        # Get TTL for this data type (default to 1 hour if not configured)
        ttl_seconds = self.cache_ttl.get(data_type, 3600)
        
        if age_seconds > ttl_seconds:
            logger.info(f"Cached {data_type} data expired (age: {age_seconds:.0f}s, TTL: {ttl_seconds}s)")
            return False
            
        logger.info(f"Using cached {data_type} data (age: {age_seconds:.0f}s, TTL: {ttl_seconds}s)")
        return True
    
    def get_series(self, refresh: bool = False) -> List[Series]:
        """
        Get series data with S3 caching.
        
        Args:
            refresh: If True, bypass cache and fetch fresh data
            
        Returns:
            List of series data
        """
        logger.info(f"Getting series data (refresh={refresh})")
        
        # Check S3 cache first
        if not refresh:
            cached_data = api_response_storage.retrieve_response('series')
            if cached_data:
                age_seconds = api_response_storage.get_response_age('series')
                if self._is_cache_valid('series', age_seconds, refresh):
                    logger.info("Returning cached series data from S3")
                    return cached_data
        
        # Fetch from API
        logger.info("Fetching fresh series data from iRacing API")
        api_data = self.base_service.get_series()
        
        # Store in S3 cache for future use
        if api_data:
            stored_path = api_response_storage.store_response('series', api_data)
            if stored_path:
                logger.info(f"Stored series data in S3: {stored_path} ({len(api_data)} series)")
        
        return api_data
    
    def get_series_seasons(
        self, 
        series_ids: Optional[List[int]] = None, 
        include_series: bool = True, 
        refresh: bool = False
    ) -> List[SeriesSeasons]:
        """
        Get series seasons data with S3 caching.
        
        Args:
            series_ids: List of series IDs to filter (optional)
            include_series: Whether to include detailed series data
            refresh: If True, bypass cache and fetch fresh data
            
        Returns:
            List of series seasons data
        """
        logger.info(f"Getting series seasons data (refresh={refresh}, include_series={include_series})")
        
        # Create cache key parameters
        cache_params = {}
        if series_ids:
            cache_params['series_ids'] = sorted(series_ids)  # Sort for consistent caching
        if include_series:
            cache_params['include_series'] = True
        
        # Check S3 cache first
        if not refresh:
            cached_data = api_response_storage.retrieve_response('seasons', **cache_params)
            if cached_data:
                age_seconds = api_response_storage.get_response_age('seasons', **cache_params)
                if self._is_cache_valid('seasons', age_seconds, refresh):
                    logger.info("Returning cached seasons data from S3")
                    # Apply client-side filtering if needed (for partial matches)
                    if series_ids and isinstance(cached_data, list):
                        filtered_data = [
                            season for season in cached_data 
                            if season.get("series_id") in series_ids
                        ]
                        return filtered_data
                    return cached_data
        
        # Fetch from API
        logger.info("Fetching fresh series seasons data from iRacing API")
        api_data = self.base_service.get_series_seasons(series_ids, include_series)
        
        # Store in S3 cache for future use
        if api_data:
            stored_path = api_response_storage.store_response('seasons', api_data, **cache_params)
            if stored_path:
                logger.info(f"Stored seasons data in S3: {stored_path} ({len(api_data)} seasons)")
        
        return api_data
    
    def get_series_past_seasons(self, series_id: int, refresh: bool = False) -> PastSeasonsResponse:
        """
        Get past seasons for a specific series with S3 caching.
        
        Args:
            series_id: iRacing series ID
            refresh: If True, bypass cache and fetch fresh data
            
        Returns:
            Past seasons response data
        """
        logger.info(f"Getting past seasons for series {series_id} (refresh={refresh})")
        
        cache_params = {'series_id': series_id}
        
        # Check S3 cache first
        if not refresh:
            cached_data = api_response_storage.retrieve_response('past_seasons', **cache_params)
            if cached_data:
                age_seconds = api_response_storage.get_response_age('past_seasons', **cache_params)
                if self._is_cache_valid('past_seasons', age_seconds, refresh):
                    logger.info(f"Returning cached past seasons data for series {series_id}")
                    return cached_data
        
        # Fetch from API
        logger.info(f"Fetching fresh past seasons data for series {series_id}")
        api_data = self.base_service.get_series_past_seasons(series_id)
        
        # Store in S3 cache
        if api_data:
            stored_path = api_response_storage.store_response('past_seasons', api_data, **cache_params)
            if stored_path:
                logger.info(f"Stored past seasons data in S3: {stored_path}")
        
        return api_data
    
    def get_series_season_schedule(self, season_id: int, refresh: bool = False) -> Any:
        """
        Get season schedule data with S3 caching.
        
        Args:
            season_id: iRacing season ID
            refresh: If True, bypass cache and fetch fresh data
            
        Returns:
            Season schedule data
        """
        logger.info(f"Getting season schedule for season {season_id} (refresh={refresh})")
        
        cache_params = {'season_id': season_id}
        
        # Check S3 cache first
        if not refresh:
            cached_data = api_response_storage.retrieve_response('schedule', **cache_params)
            if cached_data:
                age_seconds = api_response_storage.get_response_age('schedule', **cache_params)
                if self._is_cache_valid('schedule', age_seconds, refresh):
                    logger.info(f"Returning cached schedule data for season {season_id}")
                    return cached_data
        
        # Fetch from API
        logger.info(f"Fetching fresh schedule data for season {season_id}")
        api_data = self.base_service.get_series_season_schedule(season_id)
        
        # Store in S3 cache
        if api_data:
            stored_path = api_response_storage.store_response('schedule', api_data, **cache_params)
            if stored_path:
                logger.info(f"Stored schedule data in S3: {stored_path}")
        
        return api_data
    
    # Delegate other methods to base service (no caching needed for these)
    def get_cars(self) -> List[Car]:
        return self.base_service.get_cars()
    
    def get_tracks(self) -> List[Track]:
        return self.base_service.get_tracks()
    
    def get_car_classes(self) -> List[CarClass]:
        return self.base_service.get_car_classes()
    
    # Add convenience method for clearing cache
    def clear_cache(self, data_type: Optional[str] = None, **params):
        """
        Clear cached data from S3.
        
        Args:
            data_type: Type of data to clear ('series', 'seasons', etc.) or None for all
            **params: Additional parameters to filter cache clearing
        """
        logger.info(f"Clearing S3 cache (data_type={data_type}, params={params})")
        api_response_storage.clear_cache(data_type=data_type, **params)


# Global instance for use throughout the application
cached_iracing_service = CachedIRacingAPIService() 