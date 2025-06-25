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


class IRacingServiceError(Exception):
    """Custom exception for iRacing service errors."""


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
        except Exception:
            logger.exception("Failed to initialize iRacing API client")
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
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            return self.client.stats_member_summary(cust_id=cust_id)
        except Exception as e:
            logger.exception("Error fetching member summary for %s", cust_id)
            msg = f"Failed to fetch member summary for {cust_id}"
            raise IRacingServiceError(msg) from e

    def get_member_recent_races(self, cust_id: int | None = None) -> dict[str, Any]:
        """
        Get member's recent race results.

        Args:
            cust_id: Customer ID. If None, returns data for authenticated user.

        Returns:
            Dict containing recent race results
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            return self.client.stats_member_recent_races(cust_id=cust_id)
        except Exception as e:
            logger.exception("Error fetching recent races for %s", cust_id)
            msg = f"Failed to fetch recent races for {cust_id}"
            raise IRacingServiceError(msg) from e

    def get_member_yearly_stats(self, cust_id: int | None = None) -> dict[str, Any]:
        """
        Get member's yearly statistics.

        Args:
            cust_id: Customer ID. If None, returns data for authenticated user.

        Returns:
            Dict containing yearly statistics
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            return self.client.stats_member_yearly(cust_id=cust_id)
        except Exception as e:
            logger.exception("Error fetching yearly stats for %s", cust_id)
            msg = f"Failed to fetch yearly stats for {cust_id}"
            raise IRacingServiceError(msg) from e

    # Series and Events Methods
    def get_series(self) -> dict[str, Any]:
        """
        Get all available series.

        Returns:
            Dict containing series data
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            return self.client.get_series()
        except Exception as e:
            logger.exception("Error fetching series data")
            msg = "Failed to fetch series data"
            raise IRacingServiceError(msg) from e

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
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            return self.client.result_search_series(
                season_year=season_year,
                season_quarter=season_quarter,
                **kwargs,
            )
        except Exception as e:
            logger.exception("Error searching series results")
            msg = "Failed to search series results"
            raise IRacingServiceError(msg) from e

    # Car and Track Methods
    def get_cars(self) -> dict[str, Any]:
        """
        Get all available cars.

        Returns:
            Dict containing car data
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            return self.client.cars
        except Exception as e:
            logger.exception("Error fetching cars data")
            msg = "Failed to fetch cars data"
            raise IRacingServiceError(msg) from e

    def get_tracks(self) -> dict[str, Any]:
        """
        Get all available tracks.

        Returns:
            Dict containing track data
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            return self.client.tracks
        except Exception as e:
            logger.exception("Error fetching tracks data")
            msg = "Failed to fetch tracks data"
            raise IRacingServiceError(msg) from e

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
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            return self.client.result_lap_data(
                subsession_id=subsession_id,
                cust_id=cust_id,
            )
        except Exception as e:
            logger.exception(
                "Error fetching lap data for session %s, driver %s",
                subsession_id,
                cust_id,
            )
            msg = (
                f"Failed to fetch lap data for session {subsession_id}, "
                f"driver {cust_id}"
            )
            raise IRacingServiceError(msg) from e

    def get_subsession_data(self, subsession_id: int) -> dict[str, Any]:
        """
        Get detailed subsession data.

        Args:
            subsession_id: Subsession ID

        Returns:
            Dict containing subsession data
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            return self.client.subsession_data(subsession_id=subsession_id)
        except Exception as e:
            logger.exception("Error fetching subsession data for %s", subsession_id)
            msg = f"Failed to fetch subsession data for {subsession_id}"
            raise IRacingServiceError(msg) from e

    def get_member_info(self) -> dict[str, Any]:
        """
        Get full member info for the authenticated user (including owned cars/tracks).
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)
        try:
            return self.client.member_info()
        except Exception as e:
            logger.exception("Error fetching member info")
            msg = "Failed to fetch member info"
            raise IRacingServiceError(msg) from e


# Global service instance
iracing_service = IRacingAPIService()
