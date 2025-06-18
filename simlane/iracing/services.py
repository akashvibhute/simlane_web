"""
iRacing API Service

This module provides a service class for interacting with the iRacing Data API.
It handles authentication, rate limiting, and provides methods for fetching
various types of data from the iRacing platform.
"""

import logging
from typing import Any

from django.conf import settings
from iracingdataapi.client import irDataClient

logger = logging.getLogger(__name__)


class IRacingAPIService:
    """
    Service class for interacting with the iRacing Data API.

    This class provides methods to fetch different types of data from iRacing,
    including driver profiles, race results, series information, and more.
    """

    def __init__(self):
        """Initialize the iRacing API client with credentials from settings."""
        self.client = None
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize the iRacing API client with credentials."""
        try:
            if not settings.IRACING_USERNAME or not settings.IRACING_PASSWORD:
                logger.warning("iRacing credentials not configured in settings")
                return

            self.client = irDataClient(
                username=settings.IRACING_USERNAME,
                password=settings.IRACING_PASSWORD,
            )
            logger.info("iRacing API client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize iRacing API client: {e}")
            self.client = None

    def is_available(self) -> bool:
        """Check if the iRacing API client is available and configured."""
        return self.client is not None

    # Driver Profile Methods
    def get_member_summary(self, cust_id: int | None = None) -> dict[str, Any]:
        """
        Get member summary data.

        Args:
            cust_id: Customer ID. If None, returns data for authenticated user.

        Returns:
            Dict containing member summary data
        """
        if not self.is_available():
            raise Exception("iRacing API client not available")

        try:
            return self.client.stats_member_summary(cust_id=cust_id)
        except Exception as e:
            logger.error(f"Error fetching member summary for {cust_id}: {e}")
            raise

    def get_member_recent_races(self, cust_id: int | None = None) -> dict[str, Any]:
        """
        Get member's recent race results.

        Args:
            cust_id: Customer ID. If None, returns data for authenticated user.

        Returns:
            Dict containing recent race results
        """
        if not self.is_available():
            raise Exception("iRacing API client not available")

        try:
            return self.client.stats_member_recent_races(cust_id=cust_id)
        except Exception as e:
            logger.error(f"Error fetching recent races for {cust_id}: {e}")
            raise

    def get_member_yearly_stats(self, cust_id: int | None = None) -> dict[str, Any]:
        """
        Get member's yearly statistics.

        Args:
            cust_id: Customer ID. If None, returns data for authenticated user.

        Returns:
            Dict containing yearly statistics
        """
        if not self.is_available():
            raise Exception("iRacing API client not available")

        try:
            return self.client.stats_member_yearly(cust_id=cust_id)
        except Exception as e:
            logger.error(f"Error fetching yearly stats for {cust_id}: {e}")
            raise

    # Series and Events Methods
    def get_series(self) -> dict[str, Any]:
        """
        Get all available series.

        Returns:
            Dict containing series data
        """
        if not self.is_available():
            raise Exception("iRacing API client not available")

        try:
            return self.client.get_series()
        except Exception as e:
            logger.error(f"Error fetching series data: {e}")
            raise

    def search_series_results(
        self,
        season_year: int,
        season_quarter: int,
        **kwargs,
    ) -> dict[str, Any]:
        """
        Search for series results.

        Args:
            season_year: Season year
            season_quarter: Season quarter (1-4)
            **kwargs: Additional search parameters

        Returns:
            Dict containing search results
        """
        if not self.is_available():
            raise Exception("iRacing API client not available")

        try:
            return self.client.result_search_series(
                season_year=season_year,
                season_quarter=season_quarter,
                **kwargs,
            )
        except Exception as e:
            logger.error(f"Error searching series results: {e}")
            raise

    # Car and Track Methods
    def get_cars(self) -> dict[str, Any]:
        """
        Get all available cars.

        Returns:
            Dict containing car data
        """
        if not self.is_available():
            raise Exception("iRacing API client not available")

        try:
            return self.client.cars
        except Exception as e:
            logger.error(f"Error fetching cars data: {e}")
            raise

    def get_tracks(self) -> dict[str, Any]:
        """
        Get all available tracks.

        Returns:
            Dict containing track data
        """
        if not self.is_available():
            raise Exception("iRacing API client not available")

        try:
            return self.client.tracks
        except Exception as e:
            logger.error(f"Error fetching tracks data: {e}")
            raise

    # Session Data Methods
    def get_result_lap_data(self, subsession_id: int, cust_id: int) -> dict[str, Any]:
        """
        Get lap data for a specific driver in a race.

        Args:
            subsession_id: Subsession ID
            cust_id: Customer ID

        Returns:
            Dict containing lap data
        """
        if not self.is_available():
            raise Exception("iRacing API client not available")

        try:
            return self.client.result_lap_data(
                subsession_id=subsession_id,
                cust_id=cust_id,
            )
        except Exception as e:
            logger.error(
                f"Error fetching lap data for session {subsession_id}, driver {cust_id}: {e}",
            )
            raise

    def get_subsession_data(self, subsession_id: int) -> dict[str, Any]:
        """
        Get detailed subsession data.

        Args:
            subsession_id: Subsession ID

        Returns:
            Dict containing subsession data
        """
        if not self.is_available():
            raise Exception("iRacing API client not available")

        try:
            return self.client.subsession_data(subsession_id=subsession_id)
        except Exception as e:
            logger.error(f"Error fetching subsession data for {subsession_id}: {e}")
            raise


# Global service instance
iracing_service = IRacingAPIService()
