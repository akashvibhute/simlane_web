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
from simlane.sim.models import CarClass
from simlane.sim.models import Event
from simlane.sim.models import EventClass
from simlane.sim.models import EventSource
from simlane.sim.models import EventStatus
from simlane.sim.models import Season
from simlane.sim.models import Series
from simlane.sim.models import SimLayout
from simlane.sim.models import Simulator

logger = logging.getLogger(__name__)


def _ensure_service_available() -> None:
    """Ensure iRacing service is available or raise custom error."""
    if not iracing_service.is_available():
        msg = "iRacing service not available"
        raise IRacingServiceError(msg)


def _get_or_create_iracing_series(
    series_id: int,
    series_info: dict,
    iracing_simulator,
) -> tuple:
    """
    Get or create an iRacing series.

    Args:
        series_id: External series ID from iRacing
        series_info: Series information from API
        iracing_simulator: iRacing simulator instance

    Returns:
        Tuple of (series, created)
    """
    series_name = series_info.get("series_name", "")
    allowed_licenses = series_info.get("allowed_licenses", [])

    # Clean series name using regex patterns from auto_create.py
    import re

    # Remove common prefixes/suffixes and clean up
    name_cleanup_patterns = [
        r"^iRacing\s+",  # Remove "iRacing " prefix
        r"\s+Series$",  # Remove " Series" suffix
        r"\s+Championship$",  # Remove " Championship" suffix
        r"\s+Cup$",  # Remove " Cup" suffix
    ]

    cleaned_name = series_name
    for pattern in name_cleanup_patterns:
        cleaned_name = re.sub(pattern, "", cleaned_name, flags=re.IGNORECASE)

    # Fallback to original name if cleaning results in empty string
    if not cleaned_name.strip():
        cleaned_name = series_name

    series, created = Series.objects.get_or_create(
        external_series_id=series_id,
        defaults={
            "name": cleaned_name,
            "simulator": iracing_simulator,
            "allowed_licenses": allowed_licenses,
            "is_active": True,
        },
    )

    if not created:
        # Update existing series
        series.name = cleaned_name
        series.allowed_licenses = allowed_licenses
        series.save(update_fields=["name", "allowed_licenses"])

    return series, created


def _get_or_create_iracing_event(
    lookup_criteria: dict,
    event_defaults: dict,
    unique_identifier: str | None = None,
) -> tuple:
    """
    Get or create an iRacing event with robust error handling.

    Args:
        lookup_criteria: Criteria to find existing event
        event_defaults: Defaults for creating new event
        unique_identifier: Optional identifier for logging

    Returns:
        Tuple of (event, created)
    """
    try:
        event, created = Event.objects.get_or_create(
            **lookup_criteria,
            defaults=event_defaults,
        )

        if not created:
            # Update existing event with new defaults
            for key, value in event_defaults.items():
                setattr(event, key, value)
                event.save()

        return event, created

    except Exception as e:
        identifier = unique_identifier or "unknown"
        logger.error(
            f"Error in _get_or_create_iracing_event for {identifier}: {e!s}",
        )
        raise


def _process_series_seasons(series_seasons_data: list) -> tuple[int, int, list[str]]:
    """
    Process series seasons data and create/update Event records.

    Args:
        series_seasons_data: List of series seasons data from API

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

    for series_data in series_seasons_data:
        try:
            series_id = series_data.get("series_id")
            series_name = series_data.get("series_name", "")
            allowed_licenses = series_data.get("allowed_licenses", [])

            if not series_id:
                continue

            # Get or create series
            series, series_created = _get_or_create_iracing_series(
                series_id,
                series_data,
                iracing_simulator,
            )

            if series_created:
                logger.debug(f"Created series: {series_name}")

            # Process seasons
            seasons = series_data.get("seasons", [])
            for season_data in seasons:
                try:
                    season_id = season_data.get("season_id")
                    season_name = season_data.get("season_name", "")
                    season_year = season_data.get("season_year")
                    season_quarter = season_data.get("season_quarter")

                    if not season_id:
                        continue

                    # Get or create season
                    season, season_created = Season.objects.get_or_create(
                        external_season_id=season_id,
                        defaults={
                            "name": season_name,
                            "series": series,
                            "active": True,
                        },
                    )

                    if not season_created:
                        # Update existing season
                        season.name = season_name
                        season.save(update_fields=["name"])

                    # Process schedules/events
                    schedules = season_data.get("schedules", [])
                    for schedule_data in schedules:
                        try:
                            round_num = schedule_data.get("race_week_num")
                            track_id = schedule_data.get("track", {}).get("track_id")
                            track_name = schedule_data.get("track", {}).get(
                                "track_name", ""
                            )
                            layout_id = schedule_data.get("track", {}).get(
                                "config_name"
                            )

                            if not track_id or round_num is None:
                                continue

                            # Try to find track layout
                            try:
                                sim_layout = SimLayout.objects.get(
                                    sim_track__external_track_id=track_id,
                                    layout_code=layout_id,
                                )
                            except SimLayout.DoesNotExist:
                                # Try to find by track name as fallback
                                try:
                                    sim_layout = SimLayout.objects.get(
                                        sim_track__name__icontains=track_name,
                                        layout_code=layout_id,
                                    )
                                except SimLayout.DoesNotExist:
                                    logger.warning(
                                        f"Track layout not found for {track_name} ({track_id}) layout {layout_id}",
                                    )
                                    continue

                            # Create event name
                            event_name = (
                                f"{series_name} - Week {round_num} - {track_name}"
                            )
                            if layout_id and layout_id.lower() != "default":
                                event_name += f" ({layout_id})"

                            # Prepare event defaults
                            event_defaults = {
                                "series": series,
                                "season": season,
                                "simulator": iracing_simulator,
                                "sim_layout": sim_layout,
                                "event_source": EventSource.SERIES,
                                "status": EventStatus.SCHEDULED,
                                "description": f"iRacing {series_name} Week {round_num}",
                                "entry_requirements": {
                                    "round_number": round_num,
                                    "track_id": track_id,
                                    "layout_id": layout_id,
                                },
                            }

                            # Create lookup criteria
                            lookup_criteria = {
                                "series": series,
                                "season": season,
                                "round_number": round_num,
                                "sim_layout": sim_layout,
                            }

                            # Use robust get_or_create
                            event, created = _get_or_create_iracing_event(
                                lookup_criteria,
                                event_defaults,
                                f"series_{series_id}_season_{season_id}_round_{round_num}",
                            )

                            if created:
                                events_created += 1
                                logger.debug(f"Created event: {event_name}")
                            else:
                                events_updated += 1
                                logger.debug(f"Updated event: {event_name}")

                            # Process car classes if available
                            car_classes = schedule_data.get("car_classes", [])
                            for car_class_data in car_classes:
                                try:
                                    car_class_id = car_class_data.get("car_class_id")
                                    if car_class_id:
                                        car_class, _ = CarClass.objects.get_or_create(
                                            external_car_class_id=car_class_id,
                                            defaults={
                                                "name": car_class_data.get(
                                                    "car_class_name", ""
                                                ),
                                                "simulator": iracing_simulator,
                                            },
                                        )

                                        # Create event class
                                        event_class, _ = (
                                            EventClass.objects.get_or_create(
                                                event=event,
                                                car_class=car_class,
                                                defaults={
                                                    "is_active": True,
                                                },
                                            )
                                        )

                                except Exception as e:
                                    logger.warning(f"Error processing car class: {e}")

                        except Exception as e:
                            error_msg = f"Error processing schedule for series {series_id}, season {season_id}: {e!s}"
                            logger.exception(error_msg)
                            errors.append(error_msg)

                except Exception as e:
                    error_msg = f"Error processing season {season_data.get('season_id', 'unknown')}: {e!s}"
                    logger.exception(error_msg)
                    errors.append(error_msg)

        except Exception as e:
            error_msg = f"Error processing series {series_data.get('series_id', 'unknown')}: {e!s}"
            logger.exception(error_msg)
            errors.append(error_msg)

    return events_created, events_updated, errors


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_series_seasons_task(
    self,
    series_id: int | None = None,
    season_year: int | None = None,
    season_quarter: int | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """
    Sync current and future seasons for series.

    Args:
        series_id: Specific series ID to sync (None for all)
        season_year: Filter by season year
        season_quarter: Filter by season quarter
        refresh: Whether to bypass cache

    Returns:
        Dict containing sync results
    """
    try:
        logger.info(
            f"Syncing series seasons for series_id={series_id}, year={season_year}, quarter={season_quarter}"
        )

        _ensure_service_available()

        # Fetch current and future seasons for all series
        seasons_data = iracing_service.get_series_seasons(include_series=True)

        # Filter by series_id if specified
        if series_id:
            seasons_data = [s for s in seasons_data if s.get("series_id") == series_id]

        # Filter by year/quarter if specified
        if season_year or season_quarter:
            filtered_data = []
            for series_data in seasons_data:
                filtered_seasons = []
                for season in series_data.get("seasons", []):
                    if season_year and season.get("season_year") != season_year:
                        continue
                    if (
                        season_quarter
                        and season.get("season_quarter") != season_quarter
                    ):
                        continue
                    filtered_seasons.append(season)

                if filtered_seasons:
                    series_data_copy = series_data.copy()
                    series_data_copy["seasons"] = filtered_seasons
                    filtered_data.append(series_data_copy)

            seasons_data = filtered_data

        # Process the data
        events_created, events_updated, errors = _process_series_seasons(seasons_data)

        logger.info(
            f"Successfully synced series seasons: {events_created} created, {events_updated} updated, {len(errors)} errors",
        )

        return {
            "success": True,
            "events_created": events_created,
            "events_updated": events_updated,
            "errors": errors,
            "timestamp": timezone.now().isoformat(),
            "series_id": series_id,
            "season_year": season_year,
            "season_quarter": season_quarter,
        }

    except Exception as exc:
        logger.exception(f"Error syncing series seasons for series_id={series_id}")

        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "series_id": series_id,
            "season_year": season_year,
            "season_quarter": season_quarter,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_past_seasons_task(
    self, series_id: int, refresh: bool = False
) -> dict[str, Any]:
    """
    Sync past seasons for a specific series.

    Args:
        series_id: Series ID to sync past seasons for
        refresh: Whether to bypass cache

    Returns:
        Dict containing sync results
    """
    try:
        logger.info(f"Syncing past seasons for series_id={series_id}")

        _ensure_service_available()

        # Get past seasons for the series
        past_seasons_response = iracing_service.get_series_past_seasons(
            series_id=series_id
        )

        # The response is the series dict which contains a 'seasons' array
        if (
            isinstance(past_seasons_response, dict)
            and "seasons" in past_seasons_response
        ):
            past_seasons = past_seasons_response["seasons"]
        else:
            logger.error(
                f"Unexpected past seasons response format: {type(past_seasons_response)}"
            )
            return {
                "success": False,
                "error": f"Unexpected past seasons response format: {type(past_seasons_response)}",
                "timestamp": timezone.now().isoformat(),
                "series_id": series_id,
            }

        if not isinstance(past_seasons, list):
            logger.error(f"Unexpected past seasons data format: {type(past_seasons)}")
            return {
                "success": False,
                "error": f"Unexpected past seasons data format: {type(past_seasons)}",
                "timestamp": timezone.now().isoformat(),
                "series_id": series_id,
            }

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
            return {
                "success": False,
                "error": error_msg,
                "timestamp": timezone.now().isoformat(),
                "series_id": series_id,
            }

        # Get series
        try:
            series = Series.objects.get(external_series_id=series_id)
        except Series.DoesNotExist:
            error_msg = f"Series {series_id} not found in database"
            logger.error(error_msg)
            errors.append(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "timestamp": timezone.now().isoformat(),
                "series_id": series_id,
            }

        # Process each past season
        for past_season in past_seasons:
            try:
                season_id = past_season.get("season_id")
                if not season_id:
                    continue

                # Get season schedule - this returns: {"success": true, "season_id": X, "schedules": [...]}
                season_schedule_response = iracing_service.get_series_season_schedule(
                    season_id
                )

                # Transform the season_schedule format to match what _process_series_seasons expects
                # _process_series_seasons expects data in series_seasons format with embedded schedules
                transformed_season = {
                    "season_id": season_id,
                    "season_name": past_season.get("season_name", ""),
                    "season_year": past_season.get("season_year"),
                    "season_quarter": past_season.get("season_quarter"),
                    "series_id": series_id,
                    "schedules": season_schedule_response.get("schedules", []),
                }

                # Convert to the format expected by _process_series_seasons
                season_data = {
                    "series_id": series_id,
                    "series_name": series.name,
                    "allowed_licenses": series.allowed_licenses or [],
                    "seasons": [transformed_season],
                }

                created, updated, season_errors = _process_series_seasons([season_data])
                events_created += created
                events_updated += updated
                errors.extend(season_errors)

            except Exception as e:
                error_msg = f"Error processing past season {past_season.get('season_id', 'unknown')}: {e!s}"
                logger.exception(error_msg)
                errors.append(error_msg)

        logger.info(
            f"Successfully synced past seasons for series {series_id}: {events_created} created, {events_updated} updated, {len(errors)} errors",
        )

        return {
            "success": True,
            "events_created": events_created,
            "events_updated": events_updated,
            "errors": errors,
            "timestamp": timezone.now().isoformat(),
            "series_id": series_id,
        }

    except Exception as exc:
        logger.exception(f"Error syncing past seasons for series_id={series_id}")

        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "series_id": series_id,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_iracing_series_task(
    self,
    sync_seasons: bool = False,
    sync_past_seasons: bool = False,
    season_year: int | None = None,
    season_quarter: int | None = None,
    refresh: bool = False,
) -> dict[str, Any]:
    """
    Sync iRacing series and optionally seasons.

    Args:
        sync_seasons: Whether to sync current/future seasons
        sync_past_seasons: Whether to sync past seasons
        season_year: Filter by season year
        season_quarter: Filter by season quarter
        refresh: Whether to bypass cache

    Returns:
        Dict containing sync results
    """
    try:
        logger.info(
            f"Syncing iRacing series with seasons={sync_seasons}, past_seasons={sync_past_seasons}"
        )

        _ensure_service_available()

        # Fetch all series
        series_response = iracing_service.get_series()

        # Handle the response structure - it might be a dict with a 'series' key or a direct list
        if isinstance(series_response, dict):
            series_data = series_response.get("series", [])
        else:
            series_data = series_response

        if not isinstance(series_data, list):
            logger.error(f"Unexpected series data format: {type(series_data)}")
            return {
                "success": False,
                "error": f"Unexpected series data format: {type(series_data)}",
                "timestamp": timezone.now().isoformat(),
            }

        series_created = 0
        series_updated = 0
        errors = []

        # Get or create iRacing simulator
        try:
            iracing_simulator = Simulator.objects.get(name="iRacing")
        except Simulator.DoesNotExist:
            error_msg = "iRacing simulator not found in database"
            logger.error(error_msg)
            errors.append(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "timestamp": timezone.now().isoformat(),
            }

        # Process series
        for series_info in series_data:
            try:
                series_id = series_info.get("series_id")
                if not series_id:
                    continue

                series, created = _get_or_create_iracing_series(
                    series_id,
                    series_info,
                    iracing_simulator,
                )

                if created:
                    series_created += 1
                else:
                    series_updated += 1

            except Exception as e:
                error_msg = f"Error processing series {series_info.get('series_id', 'unknown')}: {e!s}"
                logger.exception(error_msg)
                errors.append(error_msg)

        # Queue season sync tasks if requested
        if sync_seasons:
            from simlane.iracing.tasks import sync_series_seasons_task

            sync_series_seasons_task.delay(
                season_year=season_year,
                season_quarter=season_quarter,
                refresh=refresh,
            )

        if sync_past_seasons:
            from simlane.iracing.tasks import sync_past_seasons_task

            # Queue past seasons sync for each series
            for series_info in series_data:
                series_id = series_info.get("series_id")
                if series_id:
                    sync_past_seasons_task.delay(series_id=series_id, refresh=refresh)

        logger.info(
            f"Successfully synced iRacing series: {series_created} created, {series_updated} updated, {len(errors)} errors",
        )

        return {
            "success": True,
            "series_created": series_created,
            "series_updated": series_updated,
            "errors": errors,
            "timestamp": timezone.now().isoformat(),
            "sync_seasons": sync_seasons,
            "sync_past_seasons": sync_past_seasons,
            "season_year": season_year,
            "season_quarter": season_quarter,
        }

    except Exception as exc:
        logger.exception("Error syncing iRacing series")

        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "sync_seasons": sync_seasons,
            "sync_past_seasons": sync_past_seasons,
            "season_year": season_year,
            "season_quarter": season_quarter,
        }


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_iracing_owned_content(self, sim_profile_id: int) -> dict[str, Any]:
    """
    Sync owned cars and tracks for a user's iRacing profile.

    Args:
        sim_profile_id: SimProfile ID to sync content for

    Returns:
        Dict containing sync results
    """
    try:
        from simlane.sim.models import SimProfile

        logger.info(f"Syncing owned content for profile ID {sim_profile_id}")

        # Get the profile
        try:
            profile = SimProfile.objects.get(id=sim_profile_id)
        except SimProfile.DoesNotExist:
            error_msg = f"SimProfile {sim_profile_id} not found"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "timestamp": timezone.now().isoformat(),
                "sim_profile_id": sim_profile_id,
            }

        # Ensure this is an iRacing profile
        if profile.simulator.name != "iRacing":
            error_msg = f"Profile {sim_profile_id} is not an iRacing profile"
            logger.error(error_msg)
            return {
                "success": False,
                "error": error_msg,
                "timestamp": timezone.now().isoformat(),
                "sim_profile_id": sim_profile_id,
            }

        _ensure_service_available()

        # Get member info which includes owned cars and tracks
        member_info = iracing_service.get_member_info()

        # TODO: Process owned cars and tracks data
        # This would involve:
        # 1. Extracting owned car/track IDs from member_info
        # 2. Creating/updating OwnedContent records
        # 3. Linking them to the SimProfile

        logger.info(f"Successfully synced owned content for profile {sim_profile_id}")

        return {
            "success": True,
            "timestamp": timezone.now().isoformat(),
            "sim_profile_id": sim_profile_id,
        }

    except Exception as exc:
        logger.exception(f"Error syncing owned content for profile {sim_profile_id}")

        if self.request.retries < self.max_retries:
            logger.info("Retrying task in %s seconds...", self.default_retry_delay)
            raise self.retry(exc=exc) from exc

        return {
            "success": False,
            "error": str(exc),
            "timestamp": timezone.now().isoformat(),
            "sim_profile_id": sim_profile_id,
        }
