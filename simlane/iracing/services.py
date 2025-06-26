"""
iRacing API Service

This module provides a service class for interacting with the iRacing Data API.
It handles authentication, rate limiting, and provides methods for fetching
various types of data from the iRacing platform.
"""

import logging
from typing import Any

from django.conf import settings
from .iracing_api_client import IRacingAPIClient

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

            self.client = IRacingAPIClient.from_system_cache()
            logger.info("iRacing API client initialized successfully (via session manager)")
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

    # Events and Season Methods
    def get_season_list(self, season_year: int, season_quarter: int) -> dict[str, Any]:
        """
        Get official seasons for a specific year and quarter.

        Args:
            season_year: Season year (e.g., 2024)
            season_quarter: Season quarter (1-4)

        Returns:
            Dict containing official seasons data
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            return self.client.season_list(
                season_year=season_year,
                season_quarter=season_quarter,
            )
        except Exception as e:
            logger.exception(
                "Error fetching season list for %s Q%s",
                season_year,
                season_quarter,
            )
            msg = f"Failed to fetch season list for {season_year} Q{season_quarter}"
            raise IRacingServiceError(msg) from e

    def get_season_race_guide(
        self,
        start_from: str | None = None,
        include_end_after_from: bool | None = None,
    ) -> dict[str, Any]:
        """
        Get the season schedule race guide with upcoming events.

        Args:
            start_from: ISO-8601 offset format timestamp. Defaults to current time.
            include_end_after_from: Include sessions that start before 'from' but end after.

        Returns:
            Dict containing race guide data with upcoming events
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            kwargs = {}
            if start_from is not None:
                kwargs["start_from"] = start_from
            if include_end_after_from is not None:
                kwargs["include_end_after_from"] = include_end_after_from

            return self.client.season_race_guide(**kwargs)
        except Exception as e:
            logger.exception("Error fetching season race guide")
            msg = "Failed to fetch season race guide"
            raise IRacingServiceError(msg) from e

    def get_spectator_subsession_ids(
        self,
        event_types: list[int] | None = None,
    ) -> list[int]:
        """
        Get current list of subsession IDs for given event types.

        Args:
            event_types: List of event type IDs (2: Practice, 3: Qualify, 4: Time Trial, 5: Race)

        Returns:
            List of subsession IDs
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            if event_types is None:
                event_types = [2, 3, 4, 5]  # Default: all event types

            return self.client.season_spectator_subsessionids(event_types=event_types)
        except Exception as e:
            logger.exception("Error fetching spectator subsession IDs")
            msg = "Failed to fetch spectator subsession IDs"
            raise IRacingServiceError(msg) from e

    def get_series_seasons(
        self,
        series_ids: list[int] | None = None,
        include_series: bool = True
    ) -> dict[str, Any]:
        """
        Get series seasons data with optional series filtering.
        
        Args:
            series_ids: List of series IDs to filter (optional)
            include_series: Whether to include detailed series data (schedules, tracks, etc.)
        
        Returns:
            Dict containing series seasons data with track/layout information.
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)
        try:
            return self.client.series_seasons(
                series_ids=series_ids,
                include_series=include_series
            )
        except Exception as e:
            logger.exception("Error fetching series seasons")
            msg = f"Failed to fetch series seasons: {str(e)}"
            raise IRacingServiceError(msg) from e

    def get_series_past_seasons(self, series_id: int) -> dict[str, Any]:
        """
        Get all past seasons for a specific series.

        Args:
            series_id: iRacing series ID

        Returns:
            Dict containing series information and list of seasons
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            return self.client.series_past_seasons(series_id=series_id)
        except Exception as e:
            logger.exception("Error fetching past seasons for series %s", series_id)
            msg = f"Failed to fetch past seasons for series {series_id}"
            raise IRacingServiceError(msg) from e

    def get_constants_event_types(self) -> list[dict[str, Any]]:
        """
        Get list of event types (Practice, Qualify, Time Trial, Race).

        Returns:
            List of event types with IDs and descriptions
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)

        try:
            return self.client.constants_event_types()
        except Exception as e:
            logger.exception("Error fetching event types")
            msg = "Failed to fetch event types"
            raise IRacingServiceError(msg) from e

    def member_recent_races(self, cust_id: int, category_id: int | None = None) -> dict[str, Any]:
        """
        Get recent races for a member.
        
        Args:
            cust_id: Customer ID of the member
            category_id: Optional category filter
        
        Returns:
            Dict containing recent races data.
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)
        try:
            return self.client.stats_member_recent_races(cust_id=cust_id)
        except Exception as e:
            logger.exception("Error fetching member recent races for cust_id %s", cust_id)
            msg = f"Failed to fetch member recent races: {str(e)}"
            raise IRacingServiceError(msg) from e

    def results_get(self, subsession_id: int, include_licenses: bool = False) -> dict[str, Any]:
        """
        Get detailed results for a specific subsession.
        
        Args:
            subsession_id: Subsession ID to get results for
            include_licenses: Whether to include license information
        
        Returns:
            Dict containing detailed subsession results.
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)
        try:
            return self.client.result(subsession_id=subsession_id, include_licenses=include_licenses)
        except Exception as e:
            logger.exception("Error fetching results for subsession %s", subsession_id)
            msg = f"Failed to fetch results for subsession {subsession_id}: {str(e)}"
            raise IRacingServiceError(msg) from e

    def season_results(
        self, 
        season_id: int, 
        event_type: int | None = None, 
        race_week_num: int | None = None
    ) -> dict[str, Any]:
        """
        Get season results.
        
        Args:
            season_id: Season ID to get results for
            event_type: Optional event type filter
            race_week_num: Optional race week filter
        
        Returns:
            Dict containing season results.
        """
        if not self.is_available():
            msg = "iRacing API client not available"
            raise IRacingServiceError(msg)
        try:
            return self.client.season_results(
                season_id=season_id,
                event_type=event_type,
                race_week_num=race_week_num
            )
        except Exception as e:
            logger.exception("Error fetching season results for season %s", season_id)
            msg = f"Failed to fetch season results: {str(e)}"
            raise IRacingServiceError(msg) from e

    def get_season_by_series_year_quarter(self, series_id: int, season_year: int, season_quarter: int) -> dict[str, Any] | None:
        """
        Fetch a season for a given series_id, year, and quarter using the series_seasons API.
        Returns the season dict if found, else None.
        """
        try:
            data = self.get_series_seasons(series_ids=[series_id], include_series=True)
            # The structure is typically { 'seasons': [ ... ] }
            seasons = data.get('seasons', [])
            for season in seasons:
                if (
                    season.get('series_id') == series_id and
                    season.get('season_year') == season_year and
                    season.get('season_quarter') == season_quarter
                ):
                    return season
            return None
        except Exception as e:
            logger.error(
                "Failed to fetch season for series_id=%s, year=%s, quarter=%s: %s",
                series_id, season_year, season_quarter, str(e)
            )
            return None


# Global service instance
iracing_service = IRacingAPIService()
