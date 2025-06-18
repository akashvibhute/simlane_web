"""
Celery tasks for iRacing data fetching.

This module contains background tasks for fetching various types of data
from the iRacing API using Celery for asynchronous processing.
"""

import logging
from typing import Any

from celery import shared_task
from django.utils import timezone

from simlane.iracing.services import IRacingServiceError
from simlane.iracing.services import iracing_service

logger = logging.getLogger(__name__)


def _ensure_service_available() -> None:
    """Ensure iRacing service is available or raise custom error."""
    if not iracing_service.is_available():
        msg = "iRacing service not available"
        raise IRacingServiceError(msg)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_member_summary(self, cust_id: int | None = None) -> dict[str, Any]:
    """
    Fetch member summary data from iRacing API.

    Args:
        cust_id: Customer ID. If None, fetches data for authenticated user.

    Returns:
        Dict containing member summary data or error information.
    """
    try:
        logger.info("Fetching member summary for customer ID: %s", cust_id)

        _ensure_service_available()

        data = iracing_service.get_member_summary(cust_id=cust_id)

        logger.info("Successfully fetched member summary for customer ID: %s", cust_id)
        return {
            "success": True,
            "data": data,
            "timestamp": timezone.now().isoformat(),
            "cust_id": cust_id,
        }

    except Exception as exc:
        logger.exception("Error fetching member summary for %s", cust_id)

        # Retry on certain exceptions
        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "cust_id": cust_id,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_member_recent_races(self, cust_id: int | None = None) -> dict[str, Any]:
    """
    Fetch member's recent race results from iRacing API.

    Args:
        cust_id: Customer ID. If None, fetches data for authenticated user.

    Returns:
        Dict containing recent race results or error information.
    """
    try:
        logger.info("Fetching recent races for customer ID: %s", cust_id)

        _ensure_service_available()

        data = iracing_service.get_member_recent_races(cust_id=cust_id)

        logger.info("Successfully fetched recent races for customer ID: %s", cust_id)
        return {
            "success": True,
            "data": data,
            "timestamp": timezone.now().isoformat(),
            "cust_id": cust_id,
        }

    except Exception as exc:
        logger.exception("Error fetching recent races for %s", cust_id)

        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "cust_id": cust_id,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_series_data(self) -> dict[str, Any]:
    """
    Fetch all series data from iRacing API.

    Returns:
        Dict containing series data or error information.
    """
    try:
        logger.info("Fetching series data")

        _ensure_service_available()

        data = iracing_service.get_series()

        logger.info("Successfully fetched series data")
        return {
            "success": True,
            "data": data,
            "timestamp": timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.exception("Error fetching series data")

        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_cars_data(self) -> dict[str, Any]:
    """
    Fetch all cars data from iRacing API.

    Returns:
        Dict containing cars data or error information.
    """
    try:
        logger.info("Fetching cars data")

        _ensure_service_available()

        data = iracing_service.get_cars()

        logger.info("Successfully fetched cars data")
        return {
            "success": True,
            "data": data,
            "timestamp": timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.exception("Error fetching cars data")

        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_tracks_data(self) -> dict[str, Any]:
    """
    Fetch all tracks data from iRacing API.

    Returns:
        Dict containing tracks data or error information.
    """
    try:
        logger.info("Fetching tracks data")

        _ensure_service_available()

        data = iracing_service.get_tracks()

        logger.info("Successfully fetched tracks data")
        return {
            "success": True,
            "data": data,
            "timestamp": timezone.now().isoformat(),
        }

    except Exception as exc:
        logger.exception("Error fetching tracks data")

        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_subsession_data(self, subsession_id: int) -> dict[str, Any]:
    """
    Fetch detailed subsession data from iRacing API.

    Args:
        subsession_id: The subsession ID to fetch data for.

    Returns:
        Dict containing subsession data or error information.
    """
    try:
        logger.info("Fetching subsession data for ID: %s", subsession_id)

        _ensure_service_available()

        data = iracing_service.get_subsession_data(subsession_id=subsession_id)

        logger.info("Successfully fetched subsession data for ID: %s", subsession_id)
        return {
            "success": True,
            "data": data,
            "timestamp": timezone.now().isoformat(),
            "subsession_id": subsession_id,
        }

    except Exception as exc:
        logger.exception("Error fetching subsession data for %s", subsession_id)

        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "subsession_id": subsession_id,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_series_search_results(
    self,
    season_year: int,
    season_quarter: int,
    **kwargs,
) -> dict[str, Any]:
    """
    Search for series results from iRacing API.

    Args:
        season_year: Season year to search
        season_quarter: Season quarter (1-4)
        **kwargs: Additional search parameters

    Returns:
        Dict containing search results or error information.
    """
    try:
        logger.info("Searching series results for %s Q%s", season_year, season_quarter)

        _ensure_service_available()

        data = iracing_service.search_series_results(
            season_year=season_year,
            season_quarter=season_quarter,
            **kwargs,
        )

        logger.info(
            "Successfully fetched series search results for %s Q%s",
            season_year,
            season_quarter,
        )
        return {
            "success": True,
            "data": data,
            "timestamp": timezone.now().isoformat(),
            "season_year": season_year,
            "season_quarter": season_quarter,
            "search_params": kwargs,
        }

    except Exception as exc:
        logger.exception(
            "Error searching series results for %s Q%s",
            season_year,
            season_quarter,
        )

        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "season_year": season_year,
            "season_quarter": season_quarter,
            "search_params": kwargs,
        }
