"""
Auto-creation utilities for bootstrapping iRacing data.

This module handles creating missing models from iRacing API responses,
allowing the system to bootstrap complete data structures from any entry point.
"""

import logging
from datetime import datetime
from datetime import timedelta
from typing import Any

import requests
from django.utils import timezone

from simlane.iracing.services import IRacingAPIService
from simlane.iracing.services import iracing_service
from simlane.sim.models import Event
from simlane.sim.models import Season
from simlane.sim.models import Series
from simlane.sim.models import SimLayout
from simlane.sim.models import SimProfile
from simlane.sim.models import Simulator
from simlane.sim.models import TimeSlot
from simlane.sim.models import WeatherForecast

logger = logging.getLogger(__name__)


def get_or_create_sim_profile_from_iracing_data(
    driver_data: dict,
    simulator: Simulator,
) -> SimProfile | None:
    """Create SimProfile from iRacing driver data if missing."""

    cust_id = driver_data.get("cust_id")
    display_name = driver_data.get("display_name", "")

    if not cust_id:
        logger.warning("No cust_id in driver data: %s", driver_data)
        return None

    sim_profile, created = SimProfile.objects.get_or_create(
        sim_api_id=str(cust_id),
        simulator=simulator,
        defaults={
            "profile_name": display_name,
            "is_verified": False,
            "profile_data": driver_data,  # Store full iRacing data
        },
    )

    if not created and sim_profile.profile_name != display_name:
        # Update name if changed
        sim_profile.profile_name = display_name
        sim_profile.profile_data = driver_data
        sim_profile.save()
        logger.debug("Updated SimProfile: %s", display_name)
    elif created:
        logger.info("Created new SimProfile: %s (cust_id: %s)", display_name, cust_id)

    return sim_profile


def find_or_create_sim_layout_from_track_data(
    track_data: dict, simulator: str
) -> SimLayout | None:
    """Find or create SimLayout from track data."""
    track_id = track_data.get("track_id")
    config_name = track_data.get("config_name", "")
    track_name = track_data.get("track_name", "Unknown Track")

    if not track_id:
        logger.error("No track_id in track data: %s", track_data)
        return None

    try:
        # Get iRacing simulator
        iracing_simulator = Simulator.objects.get(name="iRacing")

        # Find SimLayout directly by layout_code (which contains track_id) and simulator
        # The layout_code field in SimLayout is set to the track_id from iRacing API
        sim_layouts = SimLayout.objects.filter(
            sim_track__simulator=iracing_simulator,
            layout_code=str(track_id),
        )

        # Find specific layout by config_name if provided
        sim_layout = None
        if config_name and config_name != "N/A":
            sim_layout = sim_layouts.filter(
                name__icontains=config_name,
            ).first()

        # Fallback to first available layout for this track
        if not sim_layout:
            sim_layout = sim_layouts.first()

        if not sim_layout:
            logger.error("No layouts found for track %s (ID: %s)", track_name, track_id)
            return None

        logger.info(
            "Found SimLayout: %s for track %s (config: %s)",
            sim_layout, track_name, config_name
        )
        return sim_layout

    except Simulator.DoesNotExist:
        logger.error("iRacing simulator not found in database")
        return None
    except Exception as e:
        logger.error("Error finding SimLayout for track %s: %s", track_name, str(e))
        return None


def create_weather_forecasts_from_iracing_data(
    weather_forecast_data: list,
    time_slot: TimeSlot,
    forecast_version: int = 1,
) -> int:
    """
    Create WeatherForecast records from iRacing weather forecast data.

    Args:
        weather_forecast_data: List of weather forecast dictionaries from iRacing API
        time_slot: TimeSlot to create forecasts for
        forecast_version: Weather forecast version (1=Forecast/hourly, 3=Timeline/15min)

    Returns:
        Number of weather forecast records created
    """
    if not weather_forecast_data:
        return 0

    created_count = 0

    # Define unit conversion factors for reference
    units_info = {
        "air_temperature": {
            "unit": "celsius",
            "conversion": "divide by 100",
            "api_field": "air_temp",
        },
        "pressure": {
            "unit": "hectopascals",
            "conversion": "divide by 10",
            "api_field": "pressure",
        },
        "wind_speed": {
            "unit": "m/s",
            "conversion": "divide by 100",
            "api_field": "wind_speed",
        },
        "wind_direction": {
            "unit": "degrees",
            "conversion": "as-is",
            "api_field": "wind_dir",
        },
        "precipitation_chance": {
            "unit": "percent",
            "conversion": "divide by 100",
            "api_field": "precip_chance",
        },
        "precipitation_amount": {
            "unit": "mm/hour",
            "conversion": "divide by 10",
            "api_field": "precip_amount",
        },
        "cloud_cover": {
            "unit": "percent",
            "conversion": "divide by 10",
            "api_field": "cloud_cover",
        },
        "relative_humidity": {
            "unit": "percent",
            "conversion": "divide by 100",
            "api_field": "rel_humidity",
        },
    }

    for forecast_item in weather_forecast_data:
        try:
            # Parse timestamp
            timestamp_str = forecast_item.get("timestamp")
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                timestamp = (
                    timezone.make_aware(timestamp)
                    if timezone.is_naive(timestamp)
                    else timestamp
                )
            else:
                # Fallback: calculate from time_offset
                time_offset_minutes = forecast_item.get("time_offset", 0)
                timestamp = time_slot.start_time + timedelta(
                    minutes=time_offset_minutes
                )

            # Convert iRacing units to standard units using official conversion factors
            # Air temperature: divide by 100 (Celsius)
            air_temp_celsius = forecast_item.get("air_temp", 2000) / 100.0

            # Pressure: divide by 10 (hectopascals/hPa)
            pressure_hpa = forecast_item.get("pressure", 10132) / 10.0

            # Wind speed: divide by 100 (meters per second)
            wind_speed_ms = forecast_item.get("wind_speed", 0) / 100.0

            # Relative humidity: divide by 100 (percent)
            humidity_percent = min(100, forecast_item.get("rel_humidity", 5000) / 100.0)

            # Cloud cover: divide by 10 (percent)
            cloud_cover_percent = min(
                100, max(0, forecast_item.get("cloud_cover", 0) / 10.0)
            )

            # Precipitation chance: divide by 100 (percent)
            precip_chance_percent = min(
                100, forecast_item.get("precip_chance", 0) / 100.0
            )

            # Precipitation amount: divide by 10 (mm/hour)
            precip_amount = forecast_item.get("precip_amount", 0) / 10.0

            WeatherForecast.objects.create(
                time_slot=time_slot,
                time_offset=forecast_item.get("time_offset", 0),
                timestamp=timestamp,
                is_sun_up=forecast_item.get("is_sun_up", True),
                affects_session=forecast_item.get("affects_session", True),
                # Temperature and Pressure (converted)
                air_temperature=air_temp_celsius,
                pressure=pressure_hpa,
                # Wind (converted)
                wind_speed=wind_speed_ms,
                wind_direction=forecast_item.get("wind_dir", 0),
                # Precipitation (converted)
                precipitation_chance=int(precip_chance_percent),
                precipitation_amount=precip_amount,
                allow_precipitation=forecast_item.get("allow_precip", False),
                # Cloud and Humidity (converted)
                cloud_cover=int(cloud_cover_percent),
                relative_humidity=int(humidity_percent),
                # Metadata
                forecast_version=forecast_version,
                valid_stats=forecast_item.get("valid_stats", True),
                units_info=units_info,  # Store unit conversion reference
                raw_data=forecast_item,  # Store complete raw data for reference
            )
            created_count += 1

        except Exception as e:
            logger.error(
                "Failed to create WeatherForecast from data %s: %s",
                forecast_item,
                str(e),
            )
            continue

    logger.info(
        "Created %d weather forecast records for TimeSlot %s (version %d)",
        created_count,
        time_slot.id,
        forecast_version,
    )
    return created_count


def fetch_and_cache_weather_forecast(event: "Event") -> bool:
    """
    Fetch weather forecast data from iRacing URL and cache it in the Event.

    Args:
        event: Event instance with weather_forecast_url

    Returns:
        True if successful, False otherwise
    """
    if not event.weather_forecast_url:
        return False

    try:
        response = requests.get(event.weather_forecast_url, timeout=10)
        response.raise_for_status()
        weather_data = response.json()

        if not isinstance(weather_data, list):
            logger.warning(
                "Weather forecast data is not a list: %s", event.weather_forecast_url
            )
            return False

        # Cache the data in the Event
        event.weather_forecast_data = weather_data
        event.save(update_fields=["weather_forecast_data"])

        logger.info(
            "Cached weather forecast data for Event %s (%d records)",
            event,
            len(weather_data),
        )
        return True

    except Exception as e:
        logger.error(
            "Failed to fetch weather forecast from %s: %s",
            event.weather_forecast_url,
            str(e),
        )
        return False


def auto_create_event_chain_from_results(
    results_data: dict[str, Any], iracing_service: IRacingAPIService
) -> tuple[Series, Season, Event, TimeSlot]:
    """
    Auto-create the full event chain from results data.
    """
    logger.info(
        f"Starting auto-creation with results data: series_id={results_data.get('series_id')}, season_id={results_data.get('season_id')}, subsession_id={results_data.get('subsession_id')}"
    )

    # Extract data from results
    series_data = results_data.get("series", {})
    season_data = results_data.get("season", {})

    series_id = series_data.get("series_id") or results_data.get("series_id")
    series_name = series_data.get("series_name") or results_data.get(
        "series_name", "Unknown Series"
    )
    season_id = season_data.get("season_id") or results_data.get("season_id")
    season_name = season_data.get("season_name", f"{series_name} Season")
    race_week_num = results_data.get("race_week_num", 0)

    logger.info(
        f"Extracted data: series_id={series_id}, series_name={series_name}, season_id={season_id}, season_name={season_name}"
    )

    # If season_id is missing, try to fetch it using the utility
    if not season_id and series_id:
        season_year = results_data.get("season_year")
        season_quarter = results_data.get("season_quarter")
        logger.info(
            f"Attempting to fetch season data for series_id={series_id}, year={season_year}, quarter={season_quarter}"
        )
        if season_year and season_quarter:
            fetched_season = iracing_service.get_season_by_series_year_quarter(
                series_id=series_id,
                season_year=season_year,
                season_quarter=season_quarter,
            )
            if fetched_season:
                logger.info(f"Found season data: {fetched_season}")
                season_id = fetched_season.get("season_id")
                season_name = fetched_season.get("season_name", season_name)
            else:
                logger.error(
                    f"Could not fetch season for series_id={series_id}, year={season_year}, quarter={season_quarter}"
                )
        else:
            logger.error(
                f"Missing year/quarter info to fetch season. year={season_year}, quarter={season_quarter}"
            )

    if not season_id:
        msg = f"No season_id found or fetched for series_id={series_id} in results_data: {results_data}"
        logger.error(msg)
        raise ValueError(msg)

    # Create Series
    # Get iRacing simulator instance
    iracing_simulator = Simulator.objects.get(name="iRacing")

    series = Series.objects.get_or_create(
        external_series_id=series_id,
        defaults={
            "name": series_name,
            "simulator": iracing_simulator,
        },
    )[0]
    logger.info("Created/found Series: %s", series)

    # Create Season
    season = Season.objects.get_or_create(
        external_season_id=season_id,
        series=series,
        defaults={
            "name": season_name,
        },
    )[0]
    logger.info("Created/found Season: %s", season)

    # 3. Find SimLayout for track
    track_data = results_data.get("track", {})
    sim_layout = find_or_create_sim_layout_from_track_data(track_data, "iracing")
    if not sim_layout:
        raise ValueError(f"Could not find/create SimLayout for track {track_data}")

    # Parse start_time string to datetime object
    start_time_str = results_data.get("start_time")
    if not start_time_str:
        raise ValueError("No start_time in results_data")

    # Parse the datetime string (assuming ISO format like '2025-06-07T12:00:00Z')
    try:
        start_time = datetime.fromisoformat(start_time_str.replace("Z", "+00:00"))
        start_time = (
            timezone.make_aware(start_time)
            if timezone.is_naive(start_time)
            else start_time
        )
    except ValueError as e:
        logger.error(f"Failed to parse start_time '{start_time_str}': {e}")
        raise ValueError(f"Invalid start_time format: {start_time_str}")

    # 4. Get or create Event for this round
    event, created = Event.objects.get_or_create(
        season=season,
        round_number=race_week_num,
        defaults={
            "sim_layout": sim_layout,
            "start_date": start_time.date(),
            "end_date": start_time.date() + timedelta(days=7),
            "category": track_data.get("category", ""),
            "weather_config": results_data.get("weather", {}),
        },
    )
    if created:
        logger.info("Created Event for round %s: %s", race_week_num, event)

    # 5. Update Event details if needed (already created above)

    # 6. Create TimeSlot
    time_slot, created = TimeSlot.objects.get_or_create(
        external_subsession_id=results_data["subsession_id"],
        defaults={
            "event": event,
            "external_session_id": results_data.get("session_id"),
            "start_time": start_time,
            "end_time": start_time + timedelta(hours=2),  # Estimate
            "registration_open": start_time - timedelta(minutes=30),
            "registration_ends": start_time + timedelta(minutes=5),
            "is_predicted": False,
            "is_matched": True,
        },
    )
    if created:
        logger.info("Created TimeSlot: subsession %s", results_data["subsession_id"])
        # Create weather forecasts if URL available in weather data
        weather_url = None
        if results_data.get("weather", {}) and isinstance(
            results_data["weather"], dict
        ):
            weather_url = results_data["weather"].get("weather_url")
        if weather_url:
            weather_forecasts_created = create_weather_forecasts_from_url(
                weather_url, time_slot
            )
            logger.info(
                "Created %d weather forecast records for TimeSlot %s",
                weather_forecasts_created,
                time_slot.id,
            )

    return series, season, event, time_slot


def process_results_participants(
    results_data: dict,
    simulator: Simulator,
) -> dict:
    """
    Create SimProfile records for all drivers/teams in results.
    """

    logger.info("=== STARTING process_results_participants ===")
    created_counts = {"sim_profiles": 0}

    # Debug: Log the structure of results_data
    logger.info(
        f"Processing participants from results_data keys: {list(results_data.keys())}"
    )

    # Process individual drivers
    if "session_results" in results_data:
        logger.info(
            f"Found session_results with {len(results_data['session_results'])} entries"
        )
        for result in results_data["session_results"]:
            if "cust_id" in result:
                # Individual driver
                sim_profile = get_or_create_sim_profile_from_iracing_data(
                    result,
                    simulator,
                )
                if sim_profile and sim_profile._state.adding:  # Was just created
                    created_counts["sim_profiles"] += 1

            elif "team_id" in result:
                # Team event - process all team drivers
                for driver in result.get("drivers", []):
                    sim_profile = get_or_create_sim_profile_from_iracing_data(
                        driver,
                        simulator,
                    )
                    if sim_profile and sim_profile._state.adding:
                        created_counts["sim_profiles"] += 1
    else:
        logger.warning(
            "No 'session_results' found in results_data. Available keys: %s",
            list(results_data.keys()),
        )
        # Try alternative structures
        if "drivers" in results_data:
            logger.info(f"Found 'drivers' with {len(results_data['drivers'])} entries")
            for driver in results_data["drivers"]:
                if "cust_id" in driver:
                    sim_profile = get_or_create_sim_profile_from_iracing_data(
                        driver,
                        simulator,
                    )
                    if sim_profile and sim_profile._state.adding:
                        created_counts["sim_profiles"] += 1
        elif "results" in results_data:
            logger.info(f"Found 'results' with {len(results_data['results'])} entries")
            for result in results_data["results"]:
                if "cust_id" in result:
                    sim_profile = get_or_create_sim_profile_from_iracing_data(
                        result,
                        simulator,
                    )
                    if sim_profile and sim_profile._state.adding:
                        created_counts["sim_profiles"] += 1

    logger.info(
        "Created %d SimProfiles from results data",
        created_counts["sim_profiles"]
    )
    logger.info("=== FINISHED process_results_participants ===")
    return created_counts


def process_member_recent_races(cust_id: int) -> dict:
    """
    Fetch member recent races and auto-create all missing data.
    Entry point that bootstraps the entire system if needed.
    """

    try:
        iracing_simulator = Simulator.objects.get(name="iRacing")
    except Simulator.DoesNotExist:
        logger.error("iRacing simulator not found in database")
        return {"error": "iRacing simulator not found"}

    # 1. Get the member's recent races
    try:
        recent_races = iracing_service.member_recent_races(cust_id=cust_id)
    except Exception as e:
        logger.error("Failed to fetch recent races for cust_id %s: %s", cust_id, str(e))
        return {"error": f"Failed to fetch recent races: {e!s}"}

    created_counts = {
        "sim_profiles": 0,
        "series": 0,
        "seasons": 0,
        "events": 0,
        "time_slots": 0,
    }

    processed_races = 0
    errors = []

    # 2. Iterate over races in the correct structure
    for race_summary in recent_races.get("races", []):
        subsession_id = race_summary.get("subsession_id")

        if not subsession_id:
            continue

        # 2. Check if we already have this TimeSlot
        try:
            time_slot = TimeSlot.objects.get(
                external_subsession_id=subsession_id,
            )
            logger.debug("TimeSlot exists for subsession %s", subsession_id)
            processed_races += 1
            continue
        except TimeSlot.DoesNotExist:
            # 3. Fetch detailed results and create missing data
            logger.info("Creating missing data for subsession %s", subsession_id)
            try:
                detailed_results = iracing_service.results_get(
                    subsession_id=subsession_id,
                    include_licenses=True,
                )
                # 4. Auto-create Series/Season/Event chain if missing
                series, season, event, time_slot = auto_create_event_chain_from_results(
                    detailed_results,
                    iracing_service,
                )
                # 5. Process all drivers/teams in the results
                logger.info(
                    f"Calling process_results_participants for subsession {subsession_id}"
                )
                driver_counts = process_results_participants(
                    detailed_results,
                    iracing_simulator,
                )
                logger.info(f"process_results_participants returned: {driver_counts}")
                # Update counts
                for key, value in {**driver_counts}.items():
                    created_counts[key] += value
                processed_races += 1
            except Exception as e:
                error_msg = f"Failed to process subsession {subsession_id}: {e!s}"
                logger.error(error_msg)
                errors.append(error_msg)

    return {
        "processed_races": processed_races,
        "created_counts": created_counts,
        "errors": errors,
    }
