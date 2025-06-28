"""
Celery tasks for iRacing data fetching.

This module contains background tasks for fetching various types of data
from the iRacing API using Celery for asynchronous processing.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from celery import shared_task
from django.utils import timezone
from django.db import transaction
from channels.layers import get_channel_layer
import json
from asgiref.sync import async_to_sync
import requests

from simlane.iracing.services import IRacingServiceError, iracing_service
from simlane.sim.models import (
    CarModel, Event, EventInstance, EventStatus, Series, EventSource, SimCar, SimLayout, 
    SimProfile, SimProfileCarOwnership, SimProfileTrackOwnership, SimTrack, Simulator, TrackModel,
    EventResult, TeamResult, ParticipantResult, Season, RaceWeek, CarRestriction, CarClass, EventClass
)
from simlane.teams.models import Team
from simlane.sim.utils import create_event_result_from_api, create_team_and_participant_results

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


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_season_list(
    self,
    season_year: int,
    season_quarter: int,
) -> dict[str, Any]:
    """
    Fetch official seasons for a specific year and quarter.

    Args:
        season_year: Season year (e.g., 2024)
        season_quarter: Season quarter (1-4)

    Returns:
        Dict containing season list data or error information.
    """
    try:
        logger.info("Fetching season list for %s Q%s", season_year, season_quarter)

        _ensure_service_available()

        data = iracing_service.get_season_list(
            season_year=season_year,
            season_quarter=season_quarter,
        )

        logger.info(
            "Successfully fetched season list for %s Q%s",
            season_year,
            season_quarter,
        )
        return {
            "success": True,
            "data": data,
            "timestamp": timezone.now().isoformat(),
            "season_year": season_year,
            "season_quarter": season_quarter,
        }

    except Exception as exc:
        logger.exception(
            "Error fetching season list for %s Q%s",
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
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_season_race_guide(
    self,
    start_from: str | None = None,
    include_end_after_from: bool | None = None,
) -> dict[str, Any]:
    """
    Fetch the season schedule race guide with upcoming events.

    Args:
        start_from: ISO-8601 offset format timestamp
        include_end_after_from: Include sessions that start before 'from' but end after

    Returns:
        Dict containing race guide data or error information.
    """
    try:
        logger.info("Fetching season race guide")

        _ensure_service_available()

        data = iracing_service.get_season_race_guide(
            start_from=start_from,
            include_end_after_from=include_end_after_from,
        )

        logger.info("Successfully fetched season race guide")
        return {
            "success": True,
            "data": data,
            "timestamp": timezone.now().isoformat(),
            "start_from": start_from,
            "include_end_after_from": include_end_after_from,
        }

    except Exception as exc:
        logger.exception("Error fetching season race guide")

        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "start_from": start_from,
            "include_end_after_from": include_end_after_from,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_series_seasons(self, include_series: bool = False) -> dict[str, Any]:
    """
    Fetch all series and seasons data.

    Args:
        include_series: Whether to include series information

    Returns:
        Dict containing series seasons data or error information.
    """
    try:
        logger.info("Fetching series seasons data")

        _ensure_service_available()

        data = iracing_service.get_series_seasons(include_series=include_series)

        logger.info("Successfully fetched series seasons data")
        return {
            "success": True,
            "data": data,
            "timestamp": timezone.now().isoformat(),
            "include_series": include_series,
        }

    except Exception as exc:
        logger.exception("Error fetching series seasons data")

        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "include_series": include_series,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_and_sync_events(
    self,
    season_year: int | None = None,
    season_quarter: int | None = None,
    sync_to_database: bool = True,
) -> dict[str, Any]:
    """
    Fetch events from iRacing API and optionally sync them to the database.

    Args:
        season_year: Season year to fetch (defaults to current year)
        season_quarter: Season quarter to fetch (defaults to current quarter)
        sync_to_database: Whether to save events to database

    Returns:
        Dict containing sync results or error information.
    """
    try:
        # Default to current date if not specified
        if season_year is None or season_quarter is None:
            current_date = timezone.now()
            if season_year is None:
                season_year = current_date.year
            if season_quarter is None:
                # Calculate quarter based on month
                season_quarter = ((current_date.month - 1) // 3) + 1

        logger.info(
            "Fetching and syncing events for %s Q%s, sync_to_database=%s",
            season_year,
            season_quarter,
            sync_to_database,
        )

        _ensure_service_available()

        events_created = 0
        events_updated = 0
        errors = []

        # Fetch race guide for upcoming events
        try:
            race_guide_data = iracing_service.get_season_race_guide()
            logger.info("Fetched race guide with %d sessions", len(race_guide_data.get("sessions", [])))
            
            if sync_to_database:
                # Process race guide sessions
                created, updated, guide_errors = _process_race_guide_events(race_guide_data)
                events_created += created
                events_updated += updated
                errors.extend(guide_errors)
                
        except Exception as e:
            error_msg = f"Error processing race guide: {str(e)}"
            logger.exception(error_msg)
            errors.append(error_msg)

        # Fetch series seasons for more comprehensive data
        try:
            series_seasons_data = iracing_service.get_series_seasons(include_series=True)
            logger.info("Fetched %d series seasons", len(series_seasons_data))
            
            if sync_to_database:
                # Process series seasons
                created, updated, season_errors = _process_series_seasons(series_seasons_data)
                events_created += created
                events_updated += updated
                errors.extend(season_errors)
                
        except Exception as e:
            error_msg = f"Error processing series seasons: {str(e)}"
            logger.exception(error_msg)
            errors.append(error_msg)

        logger.info(
            "Event sync completed: %d created, %d updated, %d errors",
            events_created,
            events_updated,
            len(errors),
        )

        return {
            "success": True,
            "events_created": events_created,
            "events_updated": events_updated,
            "errors": errors,
            "timestamp": timezone.now().isoformat(),
            "season_year": season_year,
            "season_quarter": season_quarter,
            "sync_to_database": sync_to_database,
        }

    except Exception as exc:
        logger.exception(
            "Error in fetch_and_sync_events for %s Q%s",
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
            "sync_to_database": sync_to_database,
        }


def _get_or_create_iracing_series(series_id: int, series_info: dict, iracing_simulator) -> tuple:
    """
    Robust iRacing-specific Series get_or_create with proper lookup and update logic.
    
    Args:
        series_id: iRacing series ID
        series_info: Series data from iRacing API
        iracing_simulator: iRacing Simulator instance
    
    Returns:
        Tuple of (Series instance, created boolean)
    """
    from simlane.sim.models import Series
    
    # Extract data with fallbacks
    series_name = series_info.get("series_name", "")
    
    # Clean up series name (remove common patterns)
    if series_name:
        import re
        # Remove season/year patterns
        series_name = re.sub(r'\s*-\s*\d{4}\s*Season.*$', '', series_name)
        series_name = re.sub(r'\s*-\s*(Fixed|Open)(\s*-.*)?$', '', series_name)
        series_name = series_name.strip()
    
    if not series_name:
        raise ValueError(f"No valid series name found for series_id {series_id}")
    
    # Prepare defaults
    defaults = {
        "name": series_name,
        "description": f"iRacing {series_name} series",
        "simulator": iracing_simulator,
        "multiclass": series_info.get("multiclass", False),
        "fixed_setup": series_info.get("fixed_setup", False),
        "category": series_info.get("category", ""),
        "license_group": series_info.get("license_group"),
        "is_official": series_info.get("official", True),
        "car_switching": series_info.get("car_switching", False),
        "incident_limit": series_info.get("incident_limit"),
        "max_team_drivers": series_info.get("max_team_drivers", 1),
        "region_competition": series_info.get("region_competition", True),
        "allowed_car_class_ids": [str(class_id) for class_id in series_info.get("car_class_ids", [])],
    }
    
    # Get or create with robust lookup
    series, created = Series.objects.get_or_create(
        external_series_id=series_id,
        defaults=defaults
    )
    
    # Update existing series if not created
    if not created:
        updated = False
        for field, value in defaults.items():
            if field != "simulator" and getattr(series, field) != value:
                setattr(series, field, value)
                updated = True
        
        if updated:
            series.save()
    
    return series, created


def _resolve_track_layout_for_race_guide(track_name: str, iracing_simulator):
    """
    Try to resolve a track name from race guide to a SimLayout.
    Race guide events often have limited track info, so we do best-effort matching.
    
    Args:
        track_name: Track name from race guide
        iracing_simulator: iRacing Simulator instance
    
    Returns:
        SimLayout instance or None if not resolvable
    """
    from simlane.sim.models import SimLayout
    
    if not track_name:
        return None
    
    try:
        # Try exact track name match first
        layouts = SimLayout.objects.filter(
            sim_track__track_model__name__iexact=track_name,
            sim_track__simulator=iracing_simulator
        ).select_related('sim_track')
        
        if layouts.exists():
            # Prefer "Grand Prix" or "Road Course" layouts for race guide
            preferred_layout = layouts.filter(
                name__icontains="Grand Prix"
            ).first() or layouts.filter(
                name__icontains="Road Course"
            ).first() or layouts.first()
            
            return preferred_layout
        
        # Try partial match
        layouts = SimLayout.objects.filter(
            sim_track__track_model__name__icontains=track_name,
            sim_track__simulator=iracing_simulator
        ).select_related('sim_track')
        
        if layouts.exists():
            return layouts.first()
        
        return None
        
    except Exception as e:
        logger.warning(f"Error resolving track layout for '{track_name}': {str(e)}")
        return None


def _get_or_create_iracing_event(lookup_criteria: dict, event_defaults: dict, unique_identifier: str = None) -> tuple:
    """
    Robust iRacing-specific Event get_or_create with proper lookup and update logic.
    
    Args:
        lookup_criteria: Dictionary of fields to use for lookup
        event_defaults: Default values for event creation
        unique_identifier: Optional unique identifier for logging
    
    Returns:
        Tuple of (Event instance, created boolean)
    """
    from simlane.sim.models import Event
    
    try:
        # Try to find existing event using business logic
        event = Event.objects.filter(**lookup_criteria).first()
        
        if event:
            # Update existing event with latest data
            updated = False
            for field, value in event_defaults.items():
                if field not in lookup_criteria and getattr(event, field) != value:
                    setattr(event, field, value)
                    updated = True
            
            if updated:
                event.save()
            
            return event, False
        else:
            # Create new event
            event_data = {**lookup_criteria, **event_defaults}
            event = Event.objects.create(**event_data)
            return event, True
            
    except Exception as e:
        error_msg = f"Error in _get_or_create_iracing_event for {unique_identifier}: {str(e)}"
        logger.error(error_msg)
        raise


def _process_race_guide_events(race_guide_data: dict) -> tuple[int, int, list[str]]:
    """
    Process race guide data and create/update Event records.
    
    Returns:
        Tuple of (events_created, events_updated, errors)
    """
    from simlane.sim.models import Event, EventSource, EventStatus, Simulator
    
    events_created = 0
    events_updated = 0
    errors = []
    
    sessions = race_guide_data.get("sessions", [])
    
    # Get or create iRacing simulator
    try:
        iracing_simulator = Simulator.objects.get(name="iRacing")
    except Simulator.DoesNotExist:
        error_msg = "iRacing simulator not found in database"
        logger.error(error_msg)
        errors.append(error_msg)
        return events_created, events_updated, errors
    
    for session in sessions:
        try:
            # Extract session data
            session_id = session.get("session_id")
            session_name = session.get("session_name", "")
            start_time = session.get("start_time")
            series_name = session.get("series_name", "")
            series_id = session.get("series_id")  # May be None
            track_name = session.get("track", {}).get("track_name", "")
            
            if not session_id or not start_time:
                continue
                
            # Parse start time
            try:
                event_date = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                event_date = timezone.make_aware(event_date) if timezone.is_naive(event_date) else event_date
            except (ValueError, AttributeError):
                logger.warning("Could not parse start_time: %s", start_time)
                continue
            
            # Try to resolve track layout for race guide events
            sim_layout = _resolve_track_layout_for_race_guide(track_name, iracing_simulator)
            
            if not sim_layout:
                # Skip race guide events without resolvable track info
                # These are often generic/summary events anyway
                logger.debug(f"Skipping race guide session {session_id} - no resolvable track layout for '{track_name}'")
                continue
            
            # Create a unique name for the event
            event_name = f"{series_name} - {track_name}" if series_name and track_name else session_name
            if not event_name:
                event_name = f"iRacing Event {session_id}"
            
            # Prepare event defaults
            event_defaults = {
                "simulator": iracing_simulator,
                "sim_layout": sim_layout,  # Now we have a resolved layout
                "event_source": EventSource.SERIES,
                "event_date": event_date,
                "status": EventStatus.SCHEDULED,
                "description": f"iRacing {series_name} session" if series_name else "iRacing session",
                "entry_requirements": {
                    "session_id": session_id,
                    "series_id": series_id,
                    "series_name": series_name,
                    "track_name": track_name,
                },
            }
            
            # Create lookup criteria - handle case where series might be None
            lookup_criteria = {
                "simulator": iracing_simulator,
                "name": event_name,
                "event_date": event_date,
            }
            
            # Add series to lookup if we have a series_id
            if series_id:
                try:
                    series = Series.objects.get(external_series_id=series_id)
                    lookup_criteria["series"] = series
                    event_defaults["series"] = series
                except Series.DoesNotExist:
                    logger.warning(f"Series {series_id} not found for session {session_id}")
            
            # Use robust get_or_create
            event, created = _get_or_create_iracing_event(
                lookup_criteria, 
                event_defaults, 
                f"race_guide_session_{session_id}"
            )
            
            if created:
                events_created += 1
                logger.debug("Created race guide event: %s", event_name)
            else:
                events_updated += 1
                logger.debug("Updated race guide event: %s", event_name)
                
        except Exception as e:
            error_msg = f"Error processing session {session.get('session_id', 'unknown')}: {str(e)}"
            logger.exception(error_msg)
            errors.append(error_msg)
    
    return events_created, events_updated, errors


def _process_series_seasons(series_seasons_data: list) -> tuple[int, int, list[str]]:
    """
    Process series seasons data and create/update Series and Event records.
    
    Returns:
        Tuple of (events_created, events_updated, errors)
    """
    
    events_created = 0
    events_updated = 0
    errors = []
    
    # Get or create iRacing simulator
    try:
        iracing_simulator = Simulator.objects.get(name="iRacing")
    except Simulator.DoesNotExist:
        error_msg = "iRacing simulator not found in database"
        logger.error(error_msg)
        errors.append(error_msg)
        return events_created, events_updated, errors
    
    # Fetch all series data to get proper series names
    try:
        from simlane.iracing.services import iracing_service
        series_data = iracing_service.get_series()
        # Create a lookup map of series_id -> series info
        series_lookup = {}
        if isinstance(series_data, dict) and 'data' in series_data:
            series_list = series_data['data']
        elif isinstance(series_data, list):
            series_list = series_data
        else:
            series_list = []
            
        for series_info in series_list:
            series_id = series_info.get('series_id')
            if series_id:
                series_lookup[series_id] = series_info
        
        logger.info(f"Loaded {len(series_lookup)} series for lookup")
    except Exception as e:
        error_msg = f"Failed to fetch series data for lookup: {str(e)}"
        logger.error(error_msg)
        errors.append(error_msg)
        # Continue processing without series lookup
        series_lookup = {}
    
    for season_data in series_seasons_data:
        try:
            series_id = season_data.get("series_id")
            season_name = season_data.get("season_name", "")
            
            if not series_id:
                continue
            
            # Get series name from the series lookup
            series_info = series_lookup.get(series_id, {})
            series_name = series_info.get("series_name", "")
            
            # Fallback to extracting from season name if no series info found
            if not series_name and season_name:
                series_name = season_name
                # Common patterns to clean up: " - 2025 Season", " - Fixed", " - Open", etc.
                import re
                series_name = re.sub(r'\s*-\s*\d{4}\s*Season.*$', '', series_name)
                series_name = re.sub(r'\s*-\s*(Fixed|Open)(\s*-.*)?$', '', series_name)
                series_name = series_name.strip()
            
            if not series_name:
                logger.warning(f"No series name found for series_id {series_id}, skipping")
                continue
            
            # Extract car class and series-level data
            car_class_ids = season_data.get("car_class_ids", [])
            multiclass = season_data.get("multiclass", False)
            fixed_setup = season_data.get("fixed_setup", False)
            
            # Convert car_class_ids to strings for consistency
            allowed_car_class_ids = [str(class_id) for class_id in car_class_ids] if car_class_ids else []
            
            # Use robust Series get_or_create
            series, series_created = _get_or_create_iracing_series(
                series_id, 
                {**series_info, **season_data},  # Merge series info with season data
                iracing_simulator
            )
            
            # Process race schedules to create specific events
            schedules = season_data.get("schedules", [])
            
            if not schedules:
                # If no schedules, create a general season event (fallback)
                if season_data.get("active", False):
                    event_name = f"{series_name} - {season_name}" if season_name else series_name
                    
                    # Skip events without track/layout info in this case
                    logger.warning("No schedules found for series %s, skipping detailed event creation", series_name)
                    continue
            
            # Process each race week schedule
            for schedule in schedules:
                try:
                    track_info = schedule.get("track", {})
                    track_id = track_info.get("track_id")
                    track_name = track_info.get("track_name", "")
                    config_name = track_info.get("config_name", "")
                    
                    if not track_id or not track_name:
                        logger.warning("Missing track info in schedule for series %s", series_name)
                        continue
                    
                    # Find the corresponding SimLayout
                    try:
                        # Direct lookup by layout_code which contains the track_id from iRacing API
                        sim_layout = SimLayout.objects.select_related('sim_track').get(
                            layout_code=str(track_id),
                            sim_track__simulator=iracing_simulator
                        )
                        
                    except SimLayout.DoesNotExist:
                        # Fallback: try to find SimTrack and then match by config_name
                        try:
                            # Find all layouts for tracks with this name
                            sim_layouts = SimLayout.objects.filter(
                                sim_track__track_model__name=track_name,
                                sim_track__simulator=iracing_simulator
                            ).select_related('sim_track')
                            
                            # Try to match by config_name
                            sim_layout = None
                            if config_name and sim_layouts.exists():
                                # Try exact match first
                                sim_layout = sim_layouts.filter(name=config_name).first()
                                
                                # Try partial match if exact match fails
                                if not sim_layout:
                                    sim_layout = sim_layouts.filter(name__icontains=config_name).first()
                            
                            # Fallback to first layout if no match
                            if not sim_layout and sim_layouts.exists():
                                sim_layout = sim_layouts.first()
                                logger.warning(
                                    f"Could not find exact layout match for {config_name} at {track_name}, "
                                    f"using {sim_layout.name}"
                                )
                            
                            if not sim_layout:
                                error_msg = f"SimLayout not found for track {track_name} (ID: {track_id}). Track data may need to be synced first."
                                logger.warning(error_msg)
                                errors.append(error_msg)
                                continue
                                
                        except Exception as e:
                            error_msg = f"Error finding SimLayout for track {track_name} (ID: {track_id}): {str(e)}"
                            logger.warning(error_msg)
                            errors.append(error_msg)
                            continue
                    
                    # Create event name with track and layout info
                    race_week_num = schedule.get("race_week_num", "")
                    week_suffix = f" - Week {race_week_num}" if race_week_num is not None else ""
                    layout_suffix = f" ({config_name})" if config_name and config_name != track_name else ""
                    
                    event_name = f"{series_name} - {track_name}{layout_suffix}{week_suffix}"
                    
                    # Create unique identifier for this specific race week
                    unique_key = f"{series_id}_{season_data.get('season_id', '')}_{race_week_num}_{track_id}"
                    
                    # Get start and end dates for the race week
                    start_date = schedule.get("start_date")
                    week_end_time = schedule.get("week_end_time")
                    
                    event_date = None
                    if start_date:
                        try:
                            event_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
                            event_date = timezone.make_aware(event_date) if timezone.is_naive(event_date) else event_date
                        except (ValueError, AttributeError):
                            logger.warning("Could not parse start_date: %s", start_date)
                    
                    # Store additional metadata in entry_requirements JSON field
                    schedule_metadata = {
                        "external_series_id": series_id,
                        "external_season_id": season_data.get("season_id"),
                        "external_track_id": track_id,
                        "race_week_num": race_week_num,
                        "config_name": config_name,
                        "schedule_description": season_data.get("schedule_description", ""),
                        "category": track_info.get("category", ""),
                        "race_lap_limit": schedule.get("race_lap_limit"),
                        "race_time_limit": schedule.get("race_time_limit"),
                        "practice_length": schedule.get("practice_length"),
                        "qualify_length": schedule.get("qualify_length"),
                        "unique_key": unique_key,
                    }
                    
                    # Prepare event defaults
                    event_defaults = {
                        "name": event_name,
                        "series": series,
                        "simulator": iracing_simulator,
                        "sim_layout": sim_layout,
                        "event_source": EventSource.SERIES,
                        "event_date": event_date,
                        "status": EventStatus.SCHEDULED,
                        "description": f"iRacing {series_name} - Week {race_week_num} at {track_name} ({config_name})",
                        "entry_requirements": schedule_metadata,
                        "max_entries": schedule.get("max_entries"),
                        "weather": schedule.get("weather") if schedule.get("weather") else None,
                        "track_state": schedule.get('track_state', {}),
                    }
                    
                    # Create lookup criteria using business logic fields
                    lookup_criteria = {
                        "series": series,
                        "simulator": iracing_simulator,
                        "name": event_name,
                        "event_date": event_date,
                    }
                    
                    # Use robust get_or_create
                    event, created = _get_or_create_iracing_event(
                        lookup_criteria,
                        event_defaults,
                        f"series_season_{series_id}_week_{race_week_num}"
                    )
                    
                    if created:
                        events_created += 1
                        logger.debug("Created race week event: %s", event_name)
                    else:
                        events_updated += 1
                        logger.debug("Updated race week event: %s", event_name)
                    
                    # NEW: Create EventClass instances based on car class IDs
                    try:
                        # Get car class IDs (from event or fall back to series)
                        car_class_ids = event.allowed_car_class_ids or series.allowed_car_class_ids
                        
                        if car_class_ids:
                            # Clear existing event classes if updating
                            if not created:
                                event.classes.all().delete()
                            
                            # Create EventClass for each car class
                            for i, class_id in enumerate(car_class_ids):
                                try:
                                    car_class = CarClass.objects.get(
                                        simulator=iracing_simulator,
                                        sim_api_id=str(class_id)
                                    )
                                    
                                    # Determine class name
                                    if len(car_class_ids) == 1:
                                        # Single class - use car class name or "Main Class"
                                        class_name = car_class.name if car_class.name else "Main Class"
                                    else:
                                        # Multi-class - use car class name with fallback
                                        class_name = car_class.name if car_class.name else f"Class {i+1}"
                                    
                                    event_class, ec_created = EventClass.objects.get_or_create(
                                        event=event,
                                        car_class=car_class,
                                        defaults={
                                            'name': class_name,
                                            'class_order': i,  # 0=fastest, 1=second fastest, etc.
                                            'inherit_series_restrictions': True,
                                        }
                                    )
                                    
                                    if ec_created:
                                        logger.debug(f"Created EventClass: {class_name} for {event_name}")
                                    else:
                                        # Update existing EventClass
                                        event_class.name = class_name
                                        event_class.class_order = i
                                        event_class.save()
                                        logger.debug(f"Updated EventClass: {class_name} for {event_name}")
                                        
                                except CarClass.DoesNotExist:
                                    logger.warning(f"CarClass with sim_api_id {class_id} not found for event {event_name}")
                                    continue
                        else:
                            logger.debug(f"No car class IDs found for event {event_name}")
                            
                    except Exception as e:
                        logger.error(f"Error creating EventClass instances for {event_name}: {str(e)}")
                    
                    # --- Ensure Season & RaceWeek exist for every schedule ---
                    season, _ = Season.objects.get_or_create(
                        external_season_id=season_data.get("season_id"),
                        series=series,
                        defaults={
                            "name": season_name,
                            "active": season_data.get("active", True),
                            "complete": season_data.get("complete", False),
                        },
                    )

                    # Build defaults for RaceWeek
                    rw_defaults = {
                        "sim_layout": sim_layout,
                        "start_date": event_date.date() if event_date else timezone.now().date(),
                        "end_date": datetime.fromisoformat(schedule.get("week_end_time", "").replace('Z', '+00:00')) if schedule.get("week_end_time") else (event_date.date() + timedelta(days=7) if event_date else timezone.now().date() + timedelta(days=7)),
                        "category": track_info.get("category", ""),
                        "enable_pitlane_collisions": schedule.get("enable_pitlane_collisions", False),
                        "full_course_cautions": schedule.get("full_course_cautions", False),
                        "weather_config": schedule.get('weather'),
                        "weather_forecast_url": (schedule.get('weather') or {}).get('weather_url', ''),
                        "weather_forecast_version": (schedule.get('weather') or {}).get('version'),
                        "track_state": schedule.get('track_state', {}),
                    }

                    race_week, _ = RaceWeek.objects.update_or_create(
                        season=season,
                        week_number=race_week_num,
                        defaults=rw_defaults,
                    )

                    # Queue background forecast fetch if needed
                    if race_week.weather_forecast_url and (not race_week.weather_forecast_data):
                        update_weather_forecast_task.delay(str(race_week.id))

                    # --- Car Restrictions ---
                    car_restrictions = schedule.get("car_restrictions", [])
                    for restriction_data in car_restrictions:
                        car_api_id = restriction_data.get("car_id")
                        if not car_api_id:
                            continue
                        try:
                            sim_car = SimCar.objects.get(simulator=iracing_simulator, sim_api_id=str(car_api_id))
                        except SimCar.DoesNotExist:
                            logger.warning("SimCar not found for car_id %s, skipping restriction", car_api_id)
                            continue
                        CarRestriction.objects.update_or_create(
                            race_week=race_week,
                            sim_car=sim_car,
                            defaults={
                                "max_dry_tire_sets": restriction_data.get("max_dry_tire_sets", 0),
                                "max_pct_fuel_fill": restriction_data.get("max_pct_fuel_fill", 100),
                                "power_adjust_pct": float(restriction_data.get("power_adjust_pct", 0)),
                                "weight_penalty_kg": restriction_data.get("weight_penalty_kg", 0),
                            },
                        )
                        logger.debug("Created/updated car restriction for %s in week %s", sim_car.display_name, race_week_num)
                    
                except Exception as e:
                    error_msg = f"Error processing schedule for series {series_name}: {str(e)}"
                    logger.exception(error_msg)
                    errors.append(error_msg)
                    
        except Exception as e:
            error_msg = f"Error processing series {season_data.get('series_id', 'unknown')}: {str(e)}"
            logger.exception(error_msg)
            errors.append(error_msg)
    
    return events_created, events_updated, errors


@shared_task
def sync_iracing_owned_content(sim_profile_id):
    """
    Fetch owned cars and tracks for a SimProfile from the iRacing API and update ownership tables.
    Sends a websocket event to the user group when done.
    """
    try:
        profile = SimProfile.objects.get(id=sim_profile_id)
        member_info = iracing_service.get_member_info()
        logger.info(f"[SYNC] iRacing member_info: cust_id={member_info.get('cust_id')}, name={member_info.get('display_name')}, car_packages={member_info.get('car_packages')}, track_packages={member_info.get('track_packages')}")
        # Use package_id for ownership mapping
        owned_car_ids = set(pkg['package_id'] for pkg in member_info.get('car_packages', []))
        owned_track_ids = set(pkg['package_id'] for pkg in member_info.get('track_packages', []))
        logger.info(f"[SYNC] owned_car_ids (package_id): {owned_car_ids}")
        logger.info(f"[SYNC] owned_track_ids (package_id): {owned_track_ids}")
        sim_cars = SimCar.objects.filter(sim_api_id__in=owned_car_ids, simulator=profile.simulator)
        sim_tracks = SimTrack.objects.filter(sim_api_id__in=owned_track_ids, simulator=profile.simulator)
        car_map = {car.sim_api_id: car for car in sim_cars}
        track_map = {track.sim_api_id: track for track in sim_tracks}
        logger.info(f"[SYNC] SimCars found: {len(sim_cars)}; SimTracks found: {len(sim_tracks)}")
        with transaction.atomic():
            SimProfileCarOwnership.objects.filter(sim_profile=profile).delete()
            SimProfileTrackOwnership.objects.filter(sim_profile=profile).delete()
            car_ownerships = [
                SimProfileCarOwnership(sim_profile=profile, sim_car=car_map[api_id])
                for api_id in owned_car_ids if api_id in car_map
            ]
            track_ownerships = [
                SimProfileTrackOwnership(sim_profile=profile, sim_track=track_map[api_id])
                for api_id in owned_track_ids if api_id in track_map
            ]
            SimProfileCarOwnership.objects.bulk_create(car_ownerships)
            SimProfileTrackOwnership.objects.bulk_create(track_ownerships)
        logger.info(f"[SYNC] Car ownerships created: {len(car_ownerships)}; Track ownerships created: {len(track_ownerships)}")
        # Notify user via websocket
        channel_layer = get_channel_layer()
        group = f"user_{profile.linked_user.id}" if profile.linked_user else None
        if channel_layer and group:
            async_to_sync(channel_layer.group_send)(
                group,
                {
                    "type": "sync_status",
                    "status": "done",
                    "profile_id": str(profile.id),
                }
            )
        logger.info(f"Synced iRacing owned content for SimProfile {profile.id}")
    except Exception as e:
        logger.error(f"Failed to sync iRacing owned content for SimProfile {sim_profile_id}: {e}")
        raise


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_member_recent_races_task(self, cust_id: int) -> dict[str, Any]:
    """
    Celery task to fetch member recent races and auto-create missing data.
    
    Args:
        cust_id: iRacing customer ID
        
    Returns:
        Dict containing processing results and created counts.
    """
    try:
        from simlane.iracing.auto_create import process_member_recent_races
        
        logger.info("Processing recent races for member %s", cust_id)
        result = process_member_recent_races(cust_id)
        
        logger.info(
            "Completed processing for member %s: %s races processed, created %s", 
            cust_id, 
            result.get('processed_races', 0),
            result.get('created_counts', {})
        )
        
        return {
            "success": True,
            "result": result,
            "timestamp": timezone.now().isoformat(),
            "cust_id": cust_id,
        }
        
    except Exception as exc:
        logger.exception("Error processing member recent races for %s", cust_id)
        
        # Retry on network/API errors
        if self.request.retries < self.max_retries:
            logger.info("Retrying member recent races processing for %s", cust_id)
            raise self.retry(countdown=60, exc=exc)
        
        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "cust_id": cust_id,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_subsession_results_task(self, subsession_id: int) -> dict[str, Any]:
    """
    Celery task to fetch and sync a specific subsession's results.
    
    Args:
        subsession_id: iRacing subsession ID
        
    Returns:
        Dict containing sync results.
    """
    try:
        from simlane.iracing.auto_create import auto_create_event_chain_from_results, process_results_participants
        from simlane.sim.models import Simulator
        
        logger.info("Syncing subsession results for %s", subsession_id)
        
        # Get iRacing simulator
        try:
            iracing_simulator = Simulator.objects.get(name="iRacing")
        except Simulator.DoesNotExist:
            raise ValueError("iRacing simulator not found in database")
        
        # Fetch detailed results
        detailed_results = iracing_service.results_get(
            subsession_id=subsession_id,
            include_licenses=True
        )
        
        # Auto-create event chain
        event_instance, event_counts = auto_create_event_chain_from_results(
            detailed_results, iracing_simulator
        )
        
        # Process participants
        participant_counts = process_results_participants(
            detailed_results, iracing_simulator
        )
        
        total_counts = {**event_counts, **participant_counts}
        
        logger.info(
            "Completed subsession sync for %s: created %s", 
            subsession_id, 
            total_counts
        )
        
        return {
            "success": True,
            "event_instance_id": str(event_instance.id),
            "created_counts": total_counts,
            "timestamp": timezone.now().isoformat(),
            "subsession_id": subsession_id,
        }
        
    except Exception as exc:
        logger.exception("Error syncing subsession results for %s", subsession_id)
        
        # Retry on network/API errors
        if self.request.retries < self.max_retries:
            logger.info("Retrying subsession sync for %s", subsession_id)
            raise self.retry(countdown=60, exc=exc)
        
        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "subsession_id": subsession_id,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def match_season_results_to_instances_task(self, season_id: int) -> dict[str, Any]:
    """
    Celery task to match actual season results to predicted EventInstance records.
    
    Args:
        season_id: iRacing season ID
        
    Returns:
        Dict containing matching results.
    """
    try:
        from simlane.sim.models import EventInstance, Simulator
        
        logger.info("Matching season results to instances for season %s", season_id)
        
        # Get iRacing simulator
        try:
            iracing_simulator = Simulator.objects.get(name="iRacing")
        except Simulator.DoesNotExist:
            raise ValueError("iRacing simulator not found in database")
        
        # Get season results
        season_results = iracing_service.season_results(season_id=season_id)
        
        matched_count = 0
        created_count = 0
        errors = []
        
        for result in season_results.get('results_list', []):
            try:
                subsession_id = result['subsession_id']
                session_id = result.get('session_id')
                start_time = datetime.fromisoformat(result['start_time'].replace('Z', '+00:00'))
                start_time = timezone.make_aware(start_time) if timezone.is_naive(start_time) else start_time
                track_id = result['track']['track_id']
                race_week_num = result.get('race_week_num')
                
                # Try to find matching predicted instance
                time_window = timedelta(minutes=30)
                matching_instance = EventInstance.objects.filter(
                    event__entry_requirements__external_track_id=track_id,
                    event__entry_requirements__race_week_num=race_week_num,
                    start_time__range=[
                        start_time - time_window,
                        start_time + time_window
                    ],
                                            is_predicted=True,
                        external_subsession_id__isnull=True
                ).first()
                
                if matching_instance:
                    # Match found - update with actual data
                    matching_instance.predicted_start_time = matching_instance.start_time
                    matching_instance.external_subsession_id = subsession_id
                    matching_instance.external_session_id = session_id
                    matching_instance.start_time = start_time
                    matching_instance.is_matched = True
                    matching_instance.save()
                    matched_count += 1
                    logger.debug("Matched subsession %s to existing instance", subsession_id)
                
                else:
                    # No match - trigger creation of new EventInstance
                    sync_subsession_results_task.delay(subsession_id)
                    created_count += 1
                    logger.debug("Queued creation for unmatched subsession %s", subsession_id)
                    
            except Exception as e:
                error_msg = f"Error processing result for subsession {result.get('subsession_id')}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        return {
            "success": True,
            "matched_instances": matched_count,
            "queued_creations": created_count,
            "errors": errors,
            "timestamp": timezone.now().isoformat(),
            "season_id": season_id,
        }
        
    except Exception as exc:
        logger.exception("Error matching season results for season %s", season_id)
        
        # Retry on network/API errors
        if self.request.retries < self.max_retries:
            logger.info("Retrying season results matching for %s", season_id)
            raise self.retry(countdown=60, exc=exc)
        
        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "season_id": season_id,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_completed_events_task(self) -> dict[str, Any]:
    """
    Celery task to check for completed events and queue them for result fetching.
    
    This task runs periodically to find EventInstances that have finished
    (past end_time + 15 minutes buffer) and queues them for result processing.
    
    Returns:
        Dict containing task results and statistics.
    """
    logger.info("Starting check for completed events...")
    
    # Calculate the cutoff time (15 minutes buffer after event end)
    cutoff_time = timezone.now() - timedelta(minutes=15)
    
    # Find completed events that haven't been processed yet
    completed_events = EventInstance.objects.filter(
        end_time__lt=cutoff_time,  # Event has finished
        external_subsession_id__isnull=False,  # Has iRacing subsession ID
        # TODO: Add a field to track if results have been fetched
        # results_fetched__isnull=True,  # Results not yet fetched
    ).select_related('event', 'event__simulator')
    
    logger.info(f"Found {completed_events.count()} completed events to process")
    
    queued_count = 0
    errors = []
    
    for event_instance in completed_events:
        try:
            # Queue the result fetching task
            fetch_results_task.delay(event_instance.id)
            queued_count += 1
            logger.info(f"Queued result fetching for EventInstance {event_instance.id} (subsession: {event_instance.external_subsession_id})")
            
        except Exception as e:
            error_msg = f"Failed to queue result fetching for EventInstance {event_instance.id}: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)
    
    result = {
        "success": True,
        "completed_events_found": completed_events.count(),
        "queued_for_processing": queued_count,
        "errors": errors,
        "timestamp": timezone.now().isoformat(),
    }
    
    logger.info(f"Completed event check: {queued_count} events queued for result processing")
    return result


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def fetch_results_task(self, event_instance_id: str) -> dict[str, Any]:
    """
    Celery task to fetch and process results for a specific EventInstance.
    """
    from simlane.sim.models import EventInstance, Simulator
    from simlane.iracing.services import iracing_service

    logger.info(f"Starting result fetch for EventInstance {event_instance_id}")

    try:
        # Get the EventInstance
        event_instance = EventInstance.objects.get(id=event_instance_id)

        if not event_instance.external_subsession_id:
            raise ValueError(f"EventInstance {event_instance_id} has no external_subsession_id")

        # Get the simulator
        simulator = event_instance.event.simulator

        # Fetch results from iRacing API
        logger.info(f"Fetching results for subsession {event_instance.external_subsession_id}")
        results_data = iracing_service.results_get(
            subsession_id=event_instance.external_subsession_id,
            include_licenses=True
        )

        # --- NEW: Create EventResult and process participants ---
        event_result = create_event_result_from_api(event_instance, results_data)
        participants_processed = 0
        if 'results' in results_data:
            # Team event
            create_team_and_participant_results(event_result, results_data['results'])
            participants_processed = sum(len(team.get('driver_results', [])) for team in results_data['results'])
        elif 'session_results' in results_data and results_data['session_results']:
            # Solo event (legacy/solo structure)
            # TODO: Implement solo participant creation utility if needed
            pass

        result = {
            "success": True,
            "event_instance_id": str(event_instance.id),
            "subsession_id": event_instance.external_subsession_id,
            "results_fetched": True,
            "participants_processed": participants_processed,
            "timestamp": timezone.now().isoformat(),
        }

        logger.info(f"Successfully processed results for EventInstance {event_instance_id}")
        return result

    except EventInstance.DoesNotExist:
        error_msg = f"EventInstance {event_instance_id} not found"
        logger.error(error_msg)
        raise ValueError(error_msg)
    except Exception as e:
        error_msg = f"Failed to fetch results for EventInstance {event_instance_id}: {str(e)}"
        logger.error(error_msg)
        raise ValueError(error_msg)


def process_event_results(event_instance, results_data, simulator):
    """
    Process results data for an EventInstance (legacy, now handled in fetch_results_task).
    """
    logger.info(f"Processing results for EventInstance {event_instance.id} (legacy stub)")
    return {
        "participants_processed": 0,
        "results_data_keys": list(results_data.keys()),
    }

# Periodic task configuration
# This will be picked up by django-celery-beat

# Check for completed events every 5 minutes
check_completed_events_schedule = {
    'name': 'Check Completed Events',
    'task': 'simlane.iracing.tasks.check_completed_events_task',
    'schedule': 300.0,  # 5 minutes in seconds
    'enabled': True,
    'description': 'Periodically check for completed events and queue them for result fetching',
}

# --- Weather forecast helper ---

def _update_weather_forecast(race_week, http_session: Optional[requests.Session] = None):
    """Download and cache weather forecast JSON for a RaceWeek.

    Saves full JSON in race_week.weather_forecast_data and summary stats
    (min/max air temp in °C, max precip chance).
    """
    if not race_week.weather_forecast_url:
        return  # nothing to do

    # Skip if we already cached and have summary stats
    if race_week.weather_forecast_data and race_week.min_air_temp is not None:
        return

    sess = http_session or requests.Session()
    try:
        resp = sess.get(race_week.weather_forecast_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        logger.warning("Failed to fetch weather forecast for RaceWeek %s: %s", race_week.id, exc)
        return

    if not isinstance(data, list):
        logger.warning("Unexpected weather forecast format for RaceWeek %s", race_week.id)
        return

    # Compute summary stats – iRacing temps are hundredths of °C, convert.
    temps = [(pt.get('air_temp') or 0) / 100.0 for pt in data if 'air_temp' in pt]
    precip_chances = [pt.get('precip_chance', 0) for pt in data]

    if temps:
        race_week.min_air_temp = min(temps)
        race_week.max_air_temp = max(temps)
    if precip_chances:
        race_week.max_precip_chance = max(precip_chances)

    race_week.weather_forecast_data = data
    # version may be included in first point
    race_week.weather_forecast_version = data[0].get('version') if isinstance(data[0], dict) else race_week.weather_forecast_version
    race_week.save(update_fields=[
        'weather_forecast_data',
        'min_air_temp',
        'max_air_temp',
        'max_precip_chance',
        'weather_forecast_version',
        'updated_at',
    ])

# -- Celery wrapper so forecast fetch runs in background --

@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def update_weather_forecast_task(self, race_week_id: str) -> dict[str, Any]:
    """Background task to fetch and cache weather forecast for a RaceWeek."""
    from simlane.sim.models import RaceWeek  # Local import to avoid circularities

    try:
        race_week = RaceWeek.objects.get(id=race_week_id)
    except RaceWeek.DoesNotExist:
        return {
            'success': False,
            'error': 'RaceWeek not found',
            'race_week_id': race_week_id,
        }

    try:
        _update_weather_forecast(race_week)
        return {
            'success': True,
            'updated': True,
            'race_week_id': race_week_id,
        }
    except Exception as exc:
        # Retry on network errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc)
        return {
            'success': False,
            'error': str(exc),
            'race_week_id': race_week_id,
        }
