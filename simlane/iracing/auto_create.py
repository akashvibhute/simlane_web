"""
Auto-creation utilities for bootstrapping iRacing data.

This module handles creating missing models from iRacing API responses,
allowing the system to bootstrap complete data structures from any entry point.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple, List

import requests
from django.utils import timezone
from django.utils.text import slugify

from simlane.sim.models import (
    CarRestriction,
    Event,
    EventInstance,
    EventSource,
    EventStatus,
    RaceWeek,
    Season,
    Series,
    SimCar,
    SimLayout,
    SimProfile,
    SimTrack,
    Simulator,
    WeatherForecast,
)
from simlane.iracing.services import iracing_service, IRacingAPIService

logger = logging.getLogger(__name__)


def get_or_create_sim_profile_from_iracing_data(
    driver_data: dict, 
    simulator: Simulator
) -> Optional[SimProfile]:
    """Create SimProfile from iRacing driver data if missing."""
    
    cust_id = driver_data.get('cust_id')
    display_name = driver_data.get('display_name', '')
    
    if not cust_id:
        logger.warning("No cust_id in driver data: %s", driver_data)
        return None
    
    sim_profile, created = SimProfile.objects.get_or_create(
        sim_api_id=str(cust_id),
        simulator=simulator,
        defaults={
            'profile_name': display_name,
            'is_verified': False,
            'profile_data': driver_data,  # Store full iRacing data
        }
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


def find_or_create_sim_layout_from_track_data(track_data: dict, simulator: str) -> Optional[SimLayout]:
    """Find or create SimLayout from track data."""
    track_id = track_data.get('track_id')
    config_name = track_data.get('config_name', '')
    track_name = track_data.get('track_name', 'Unknown Track')
    
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
            layout_code=str(track_id)
        )
        
        # Find specific layout by config_name if provided
        sim_layout = None
        if config_name and config_name != 'N/A':
            sim_layout = sim_layouts.filter(
                name__icontains=config_name
            ).first()
        
        # Fallback to first available layout for this track
        if not sim_layout:
            sim_layout = sim_layouts.first()
            
        if not sim_layout:
            logger.error("No layouts found for track %s (ID: %s)", track_name, track_id)
            return None
            
        logger.info(f"Found SimLayout: {sim_layout} for track {track_name} (config: {config_name})")
        return sim_layout
        
    except Simulator.DoesNotExist:
        logger.error("iRacing simulator not found in database")
        return None
    except Exception as e:
        logger.error("Error finding SimLayout for track %s: %s", track_name, str(e))
        return None


def create_weather_forecasts_from_iracing_data(
    weather_forecast_data: list, 
    event_instance: EventInstance,
    forecast_version: int = 1
) -> int:
    """
    Create WeatherForecast records from iRacing weather forecast data.
    
    Args:
        weather_forecast_data: List of weather forecast dictionaries from iRacing API
        event_instance: EventInstance to create forecasts for
        forecast_version: Weather forecast version (1=Forecast/hourly, 3=Timeline/15min)
    
    Returns:
        Number of weather forecast records created
    """
    if not weather_forecast_data:
        return 0
    
    created_count = 0
    
    # Define unit conversion factors for reference
    units_info = {
        "air_temperature": {"unit": "celsius", "conversion": "divide by 100", "api_field": "air_temp"},
        "pressure": {"unit": "hectopascals", "conversion": "divide by 10", "api_field": "pressure"},
        "wind_speed": {"unit": "m/s", "conversion": "divide by 100", "api_field": "wind_speed"},
        "wind_direction": {"unit": "degrees", "conversion": "as-is", "api_field": "wind_dir"},
        "precipitation_chance": {"unit": "percent", "conversion": "divide by 100", "api_field": "precip_chance"},
        "precipitation_amount": {"unit": "mm/hour", "conversion": "divide by 10", "api_field": "precip_amount"},
        "cloud_cover": {"unit": "percent", "conversion": "divide by 10", "api_field": "cloud_cover"},
        "relative_humidity": {"unit": "percent", "conversion": "divide by 100", "api_field": "rel_humidity"},
    }
    
    for forecast_item in weather_forecast_data:
        try:
            # Parse timestamp
            timestamp_str = forecast_item.get('timestamp')
            if timestamp_str:
                timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                timestamp = timezone.make_aware(timestamp) if timezone.is_naive(timestamp) else timestamp
            else:
                # Fallback: calculate from time_offset
                time_offset_minutes = forecast_item.get('time_offset', 0)
                timestamp = event_instance.start_time + timedelta(minutes=time_offset_minutes)
            
            # Convert iRacing units to standard units using official conversion factors
            # Air temperature: divide by 100 (Celsius)
            air_temp_celsius = forecast_item.get('air_temp', 2000) / 100.0
            
            # Pressure: divide by 10 (hectopascals/hPa)
            pressure_hpa = forecast_item.get('pressure', 10132) / 10.0
            
            # Wind speed: divide by 100 (meters per second)
            wind_speed_ms = forecast_item.get('wind_speed', 0) / 100.0
            
            # Relative humidity: divide by 100 (percent)
            humidity_percent = min(100, forecast_item.get('rel_humidity', 5000) / 100.0)
            
            # Cloud cover: divide by 10 (percent)
            cloud_cover_percent = min(100, max(0, forecast_item.get('cloud_cover', 0) / 10.0))
            
            # Precipitation chance: divide by 100 (percent)
            precip_chance_percent = min(100, forecast_item.get('precip_chance', 0) / 100.0)
            
            # Precipitation amount: divide by 10 (mm/hour)
            precip_amount = forecast_item.get('precip_amount', 0) / 10.0
            
            WeatherForecast.objects.create(
                event_instance=event_instance,
                time_offset=forecast_item.get('time_offset', 0),
                timestamp=timestamp,
                is_sun_up=forecast_item.get('is_sun_up', True),
                affects_session=forecast_item.get('affects_session', True),
                
                # Temperature and Pressure (converted)
                air_temperature=air_temp_celsius,
                pressure=pressure_hpa,
                
                # Wind (converted)
                wind_speed=wind_speed_ms,
                wind_direction=forecast_item.get('wind_dir', 0),
                
                # Precipitation (converted)
                precipitation_chance=int(precip_chance_percent),
                precipitation_amount=precip_amount,
                allow_precipitation=forecast_item.get('allow_precip', False),
                
                # Cloud and Humidity (converted)
                cloud_cover=int(cloud_cover_percent),
                relative_humidity=int(humidity_percent),
                
                # Metadata
                forecast_version=forecast_version,
                valid_stats=forecast_item.get('valid_stats', True),
                units_info=units_info,  # Store unit conversion reference
                raw_data=forecast_item,  # Store complete raw data for reference
            )
            created_count += 1
            
        except Exception as e:
            logger.error("Failed to create WeatherForecast from data %s: %s", 
                        forecast_item, str(e))
            continue
    
    logger.info("Created %d weather forecast records for EventInstance %s (version %d)", 
               created_count, event_instance.id, forecast_version)
    return created_count


def fetch_and_cache_weather_forecast(race_week: 'RaceWeek') -> bool:
    """
    Fetch weather forecast data from iRacing URL and cache it in RaceWeek.
    
    Args:
        race_week: RaceWeek instance with weather_forecast_url
    
    Returns:
        True if successful, False otherwise
    """
    if not race_week.weather_forecast_url:
        return False
    
    try:
        response = requests.get(race_week.weather_forecast_url, timeout=10)
        response.raise_for_status()
        weather_data = response.json()
        
        if not isinstance(weather_data, list):
            logger.warning("Weather forecast data is not a list: %s", race_week.weather_forecast_url)
            return False
        
        # Cache the data in the RaceWeek
        race_week.weather_forecast_data = weather_data
        race_week.save(update_fields=['weather_forecast_data'])
        
        logger.info("Cached weather forecast data for RaceWeek %s (%d records)", 
                   race_week, len(weather_data))
        return True
        
    except Exception as e:
        logger.error("Failed to fetch weather forecast from %s: %s", 
                    race_week.weather_forecast_url, str(e))
        return False


def create_weather_forecasts_from_url(weather_url: str, event_instance: EventInstance) -> int:
    """Create weather forecasts from URL."""
    # For now, return 0 to avoid the complex weather fetching logic
    # This can be implemented later when weather data is properly handled
    logger.warning(f"Weather forecast creation from URL not implemented yet: {weather_url}")
    return 0


def auto_create_event_chain_from_results(results_data: dict[str, Any], iracing_service: IRacingAPIService) -> tuple[Series, Season, RaceWeek, Event, EventInstance]:
    """
    Auto-create the full event chain from results data.
    """
    logger.info(f"Starting auto-creation with results data: series_id={results_data.get('series_id')}, season_id={results_data.get('season_id')}, subsession_id={results_data.get('subsession_id')}")
    
    # Extract data from results
    series_data = results_data.get('series', {})
    season_data = results_data.get('season', {})
    
    series_id = series_data.get('series_id') or results_data.get('series_id')
    series_name = series_data.get('series_name') or results_data.get('series_name', 'Unknown Series')
    season_id = season_data.get('season_id') or results_data.get('season_id')
    season_name = season_data.get('season_name', f'{series_name} Season')
    race_week_num = results_data.get('race_week_num', 0)

    logger.info(f"Extracted data: series_id={series_id}, series_name={series_name}, season_id={season_id}, season_name={season_name}")

    # If season_id is missing, try to fetch it using the utility
    if not season_id and series_id:
        season_year = results_data.get('season_year')
        season_quarter = results_data.get('season_quarter')
        logger.info(f"Attempting to fetch season data for series_id={series_id}, year={season_year}, quarter={season_quarter}")
        if season_year and season_quarter:
            fetched_season = iracing_service.get_season_by_series_year_quarter(
                series_id=series_id,
                season_year=season_year,
                season_quarter=season_quarter
            )
            if fetched_season:
                logger.info(f"Found season data: {fetched_season}")
                season_id = fetched_season.get('season_id')
                season_name = fetched_season.get('season_name', season_name)
            else:
                logger.error(f"Could not fetch season for series_id={series_id}, year={season_year}, quarter={season_quarter}")
        else:
            logger.error(f"Missing year/quarter info to fetch season. year={season_year}, quarter={season_quarter}")

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
            'name': series_name,
            'simulator': iracing_simulator,
        }
    )[0]
    logger.info(f"Created/found Series: {series}")

    # Create Season
    season = Season.objects.get_or_create(
        external_season_id=season_id,
        series=series,
        defaults={
            'name': season_name,
        }
    )[0]
    logger.info(f"Created/found Season: {season}")

    # 3. Find SimLayout for track
    track_data = results_data.get('track', {})
    sim_layout = find_or_create_sim_layout_from_track_data(track_data, str('iracing'))
    if not sim_layout:
        raise ValueError(f"Could not find/create SimLayout for track {track_data}")
    
    # Parse start_time string to datetime object
    start_time_str = results_data.get('start_time')
    if not start_time_str:
        raise ValueError("No start_time in results_data")
    
    # Parse the datetime string (assuming ISO format like '2025-06-07T12:00:00Z')
    try:
        start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
        start_time = timezone.make_aware(start_time) if timezone.is_naive(start_time) else start_time
    except ValueError as e:
        logger.error(f"Failed to parse start_time '{start_time_str}': {e}")
        raise ValueError(f"Invalid start_time format: {start_time_str}")
    
    # 4. Get or create RaceWeek
    race_week, created = RaceWeek.objects.get_or_create(
        season=season,
        week_number=race_week_num,
        defaults={
            'sim_layout': sim_layout,
            'start_date': start_time.date(),
            'end_date': start_time.date() + timedelta(days=7),
            'category': track_data.get('category', ''),
            'weather_config': results_data.get('weather', {}),
        }
    )
    if created:
        logger.info("Created RaceWeek: %s - Week %s", season_name, race_week_num)
        
        # Weather forecasts will be created when EventInstance is created
    
    # 5. Get or create Event
    event_name = f"{series_name} - {track_data.get('track_name', 'Unknown')} - Week {race_week_num}"
    
    event, created = Event.objects.get_or_create(
        series=series,
        sim_layout=sim_layout,
        name=event_name,
        defaults={
            'simulator': iracing_simulator,
            'event_source': EventSource.SERIES,
            'status': EventStatus.COMPLETED,  # If we have results, it's completed
            'description': f'iRacing {series_name} event',
            'entry_requirements': {
                'external_series_id': series_id,
                'external_season_id': season_id,
                'race_week_num': race_week_num,
                'external_track_id': track_data.get('track_id'),
                'config_name': track_data.get('config_name', ''),
                'unique_key': f"{series_id}_{season_id}_{race_week_num}_{track_data.get('track_id')}",
            },
            'is_team_event': results_data.get('driver_changes', False),
            'fixed_setup': results_data.get('fixed_setup', False),
        }
    )
    if created:
        logger.info("Created Event: %s", event_name)
    
    # Ensure linkage to RaceWeek
    if race_week and event.race_week_id != race_week.id:
        event.race_week = race_week
        event.save(update_fields=["race_week"])
    
    # 6. Create EventInstance
    event_instance, created = EventInstance.objects.get_or_create(
        external_subsession_id=results_data['subsession_id'],
        defaults={
            'event': event,
            'external_session_id': results_data.get('session_id'),
            'start_time': start_time,
            'end_time': start_time + timedelta(hours=2),  # Estimate
            'registration_open': start_time - timedelta(minutes=30),
            'registration_ends': start_time + timedelta(minutes=5),
            'is_predicted': False,
            'is_matched': True,
        }
    )
    if created:
        logger.info("Created EventInstance: subsession %s", results_data['subsession_id'])
        
        # Create weather forecasts if URL available in weather data
        weather_url = None
        if results_data.get('weather', {}) and isinstance(results_data['weather'], dict):
            weather_url = results_data['weather'].get('weather_url')
        if weather_url:
            weather_forecasts_created = create_weather_forecasts_from_url(weather_url, event_instance)
            logger.info("Created %d weather forecast records for EventInstance %s", 
                       weather_forecasts_created, event_instance.id)
    
    return series, season, race_week, event, event_instance


def process_results_participants(
    results_data: dict, 
    simulator: Simulator
) -> dict:
    """
    Create SimProfile records for all drivers/teams in results.
    """
    
    logger.info("=== STARTING process_results_participants ===")
    created_counts = {'sim_profiles': 0}
    
    # Debug: Log the structure of results_data
    logger.info(f"Processing participants from results_data keys: {list(results_data.keys())}")
    
    # Process individual drivers
    if 'session_results' in results_data:
        logger.info(f"Found session_results with {len(results_data['session_results'])} entries")
        for result in results_data['session_results']:
            if 'cust_id' in result:
                # Individual driver
                sim_profile = get_or_create_sim_profile_from_iracing_data(
                    result, simulator
                )
                if sim_profile and sim_profile._state.adding:  # Was just created
                    created_counts['sim_profiles'] += 1
                    
            elif 'team_id' in result:
                # Team event - process all team drivers
                for driver in result.get('drivers', []):
                    sim_profile = get_or_create_sim_profile_from_iracing_data(
                        driver, simulator
                    )
                    if sim_profile and sim_profile._state.adding:
                        created_counts['sim_profiles'] += 1
    else:
        logger.warning("No 'session_results' found in results_data. Available keys: %s", list(results_data.keys()))
        # Try alternative structures
        if 'drivers' in results_data:
            logger.info(f"Found 'drivers' with {len(results_data['drivers'])} entries")
            for driver in results_data['drivers']:
                if 'cust_id' in driver:
                    sim_profile = get_or_create_sim_profile_from_iracing_data(
                        driver, simulator
                    )
                    if sim_profile and sim_profile._state.adding:
                        created_counts['sim_profiles'] += 1
        elif 'results' in results_data:
            logger.info(f"Found 'results' with {len(results_data['results'])} entries")
            for result in results_data['results']:
                if 'cust_id' in result:
                    sim_profile = get_or_create_sim_profile_from_iracing_data(
                        result, simulator
                    )
                    if sim_profile and sim_profile._state.adding:
                        created_counts['sim_profiles'] += 1
    
    logger.info(f"Created {created_counts['sim_profiles']} SimProfiles from results data")
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
        return {'error': 'iRacing simulator not found'}
    
    # 1. Get the member's recent races
    try:
        recent_races = iracing_service.member_recent_races(cust_id=cust_id)
    except Exception as e:
        logger.error("Failed to fetch recent races for cust_id %s: %s", cust_id, str(e))
        return {'error': f'Failed to fetch recent races: {str(e)}'}
    
    created_counts = {
        'sim_profiles': 0,
        'series': 0,
        'seasons': 0,
        'race_weeks': 0,
        'events': 0,
        'event_instances': 0,
    }
    
    processed_races = 0
    errors = []
    
    # 2. Iterate over races in the correct structure
    for race_summary in recent_races.get('races', []):
        subsession_id = race_summary.get('subsession_id')
        
        if not subsession_id:
            continue
        
        # 2. Check if we already have this EventInstance
        try:
            event_instance = EventInstance.objects.get(
                external_subsession_id=subsession_id
            )
            logger.debug("EventInstance exists for subsession %s", subsession_id)
            processed_races += 1
            continue
        except EventInstance.DoesNotExist:
            # 3. Fetch detailed results and create missing data
            logger.info("Creating missing data for subsession %s", subsession_id)
            try:
                detailed_results = iracing_service.results_get(
                    subsession_id=subsession_id,
                    include_licenses=True
                )
                # 4. Auto-create Series/Season/Event chain if missing
                series, season, race_week, event, event_instance = auto_create_event_chain_from_results(
                    detailed_results, iracing_service
                )
                # 5. Process all drivers/teams in the results
                logger.info(f"Calling process_results_participants for subsession {subsession_id}")
                driver_counts = process_results_participants(
                    detailed_results, iracing_simulator
                )
                logger.info(f"process_results_participants returned: {driver_counts}")
                # Update counts
                for key, value in {**driver_counts}.items():
                    created_counts[key] += value
                processed_races += 1
            except Exception as e:
                error_msg = f"Failed to process subsession {subsession_id}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
    
    return {
        'processed_races': processed_races,
        'created_counts': created_counts,
        'errors': errors,
    }


def create_or_update_race_week_from_schedule(
    schedule_data: dict,
    season: Season,
    simulator: Simulator
) -> Tuple[Optional['RaceWeek'], bool, List[str]]:
    """
    Create or update a RaceWeek from iRacing schedule data.
    
    Args:
        schedule_data: Schedule data from series_seasons API
        season: Season this race week belongs to
        simulator: iRacing simulator
    
    Returns:
        Tuple of (RaceWeek instance or None, created bool, list of errors)
    """
    errors = []
    
    # Extract track information
    track_info = schedule_data.get('track', {})
    track_id = track_info.get('track_id')
    config_name = track_info.get('config_name', '')
    
    if not track_id:
        errors.append("No track_id in schedule data")
        return None, False, errors
    
    # Find SimLayout
    sim_layout = find_or_create_sim_layout_from_track_data(track_info, str('iracing'))
    if not sim_layout:
        errors.append(f"Could not find/create SimLayout for track {track_info}")
        return None, False, errors
    
    # Extract timing
    # API returns 0-based week numbers; SimLane stores 1-based
    race_week_num = schedule_data.get('race_week_num', 0) + 1
    start_date_str = schedule_data.get('start_date')
    week_end_time_str = schedule_data.get('week_end_time')
    
    if not start_date_str:
        errors.append("No start_date in schedule data")
        return None, False, errors
    
    try:
        start_date = datetime.fromisoformat(start_date_str).date()
        if week_end_time_str:
            end_datetime = datetime.fromisoformat(week_end_time_str.replace('Z', '+00:00'))
            end_datetime = timezone.make_aware(end_datetime) if timezone.is_naive(end_datetime) else end_datetime
        else:
            # Default to 7 days from start
            end_datetime = timezone.make_aware(datetime.combine(start_date + timedelta(days=7), datetime.min.time()))
    except (ValueError, AttributeError) as e:
        errors.append(f"Failed to parse dates: {str(e)}")
        return None, False, errors
    
    # Extract weather data
    weather_data = schedule_data.get('weather', {})
    weather_url = weather_data.get('weather_url', '')
    weather_version = weather_data.get('version', 1)
    
    # Extract time pattern from race_time_descriptors
    time_descriptors = schedule_data.get('race_time_descriptors', [])
    time_pattern = None
    if time_descriptors:
        # Take the first descriptor as the pattern
        time_pattern = {
            'first_session_time': time_descriptors[0].get('first_session_time'),
            'repeat_minutes': time_descriptors[0].get('repeat_minutes'),
            'session_minutes': time_descriptors[0].get('session_minutes'),
            'day_offset': time_descriptors[0].get('day_offset'),
            'repeating': time_descriptors[0].get('repeating', True)
        }
    
    # Create or update RaceWeek
    race_week, created = RaceWeek.objects.update_or_create(
        season=season,
        week_number=race_week_num,
        defaults={
            'sim_layout': sim_layout,
            'schedule_name': schedule_data.get('schedule_name', ''),
            'start_date': start_date,
            'end_date': end_datetime,
            'category': track_info.get('category', ''),
            'enable_pitlane_collisions': schedule_data.get('enable_pitlane_collisions', False),
            'full_course_cautions': schedule_data.get('full_course_cautions', True),
            'time_pattern': time_pattern,
            'weather_config': weather_data,  # Store entire weather object
            'weather_forecast_url': weather_url,
            'weather_forecast_version': weather_version,
            'track_state': schedule_data.get('track_state', {}),
        }
    )
    
    if created:
        logger.info("Created RaceWeek: %s - Week %s", season.name, race_week_num)
    else:
        logger.info("Updated RaceWeek: %s - Week %s", season.name, race_week_num)
    
    # Handle car restrictions if present
    car_restrictions = schedule_data.get('car_restrictions', [])
    if car_restrictions and created:  # Only create on new race weeks
        for restriction_data in car_restrictions:
            car_api_id = restriction_data.get('car_id')
            if car_api_id:
                try:
                    sim_car = SimCar.objects.get(
                        simulator=simulator,
                        sim_api_id=str(car_api_id)
                    )
                    CarRestriction.objects.create(
                        race_week=race_week,
                        sim_car=sim_car,
                        max_dry_tire_sets=restriction_data.get('max_dry_tire_sets', 0),
                        max_pct_fuel_fill=restriction_data.get('max_pct_fuel_fill', 100),
                        power_adjust_pct=restriction_data.get('power_adjust_pct', 0),
                        weight_penalty_kg=restriction_data.get('weight_penalty_kg', 0),
                    )
                except SimCar.DoesNotExist:
                    logger.warning("SimCar not found for car_id %s, skipping restriction", car_api_id)
    
    # Fetch and cache weather forecast if URL is available
    if weather_url and not race_week.weather_forecast_data:
        fetch_and_cache_weather_forecast(race_week)
    
    return race_week, created, errors 