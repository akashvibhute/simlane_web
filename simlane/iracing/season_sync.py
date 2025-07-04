"""
Season synchronization and schedule processing for iRacing.

This module handles the processing of season schedules from the iRacing API,
creating events, managing recurrence patterns, and handling time slots.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from django.utils import timezone
from django.utils.text import slugify

from simlane.iracing.types import Schedule, SeriesSeasons
from simlane.sim.models import (
    CarClass,
    CarRestriction,
    Event,
    EventClass,
    EventSession,
    EventSource,
    EventStatus,
    Season,
    Series,
    SessionType,
    SimCar,
    SimLayout,
    Simulator,
    TimeSlot,
)

logger = logging.getLogger(__name__)


class ScheduleProcessor:
    """Processes iRacing season schedules and creates events."""
    
    def __init__(self, simulator: Simulator):
        self.simulator = simulator
        self.events_created = 0
        self.events_updated = 0
        self.time_slots_created = 0
        self.errors = []
        self.weather_sync_queued = 0
        self.event_sessions_created = 0
        self.event_sessions_updated = 0
        self.event_classes_created = 0
        self.event_classes_updated = 0
    
    def process_season_schedule(
        self, 
        season: Season, 
        season_data: SeriesSeasons
    ) -> Tuple[int, int, int, int, int, int, int, int, List[str]]:
        """
        Process a season's schedule data and create events.
        
        Args:
            season: Season instance
            schedules: List of schedule data from API
            
        Returns:
            Tuple of (events_created, events_updated, time_slots_created, errors)
        """
        logger.info(f"Processing schedule for season {season.name} with {len(season_data['schedules'])} weeks")
        
        car_class_ids = []
        fixed_setup = season_data.get("fixed_setup", False)
        
        for schedule_data in season_data['schedules']:
            try:
                car_class_ids.extend(schedule_data.get("car_class_ids", []))
                self._process_week_schedule(season, schedule_data, fixed_setup, car_class_ids)
            except Exception as e:
                error_msg = f"Error processing week {schedule_data.get('race_week_num', 'unknown')}: {e}"
                logger.exception(error_msg)
                self.errors.append(error_msg)
        
        return self.events_created, self.events_updated, self.time_slots_created, self.weather_sync_queued, self.event_sessions_created, self.event_sessions_updated, self.event_classes_created, self.event_classes_updated, self.errors
    
    def _process_week_schedule(self, season: Season, schedule_data: Schedule, fixed_setup: bool, car_class_ids: List[int]) -> None:
        """Process a single week's schedule data."""
        round_num = schedule_data.get("race_week_num")
        track_id = schedule_data.get("track", {}).get("track_id")
        track_name = schedule_data.get("track", {}).get("track_name", "")
        layout_name = schedule_data.get("track", {}).get("config_name") or "Default"
        
        if not track_id or round_num is None:
            logger.warning(f"Missing track_id ({track_id}) or round_num ({round_num})")
            return
        
        # Find track layout
        sim_layout = self._find_sim_layout(track_id, track_name, layout_name)
        if not sim_layout:
            return
        
        # Get team event data
        is_team_event = schedule_data.get("driver_changes", False)
        min_team_drivers = schedule_data.get("min_team_drivers", 1)
        max_team_drivers = schedule_data.get("max_team_drivers", 1)
        fair_share_pct = schedule_data.get("fair_share_pct", 25)
        multiclass = schedule_data.get("multiclass", False)
        required_compounds = {
            "must_use_diff_tire_types_in_race": schedule_data.get("must_use_diff_tire_types_in_race", False),
        }
        simulated_start_time = schedule_data.get("weather", {}).get("simulated_start_time", None)
        additional_details = {
            "num_fast_tows": schedule_data.get("num_fast_tows", 0),
            "qualifier_must_start_race": schedule_data.get("qualifier_must_start_race", False),
            "lucky_dog": schedule_data.get("lucky_dog", False),
            "incident_limit": schedule_data.get("incident_limit", 0),
            "incident_warn_mode": schedule_data.get("incident_warn_mode", 0),
            "incident_warn_param1": schedule_data.get("incident_warn_param1", 0),
            "incident_warn_param2": schedule_data.get("incident_warn_param2", 0),
            "grid_by_class": schedule_data.get("grid_by_class", False),
            "drops": schedule_data.get("drops", 0),
            "ignore_license_for_practice": schedule_data.get("ignore_license_for_practice", False),
            "incident_limit": schedule_data.get("incident_limit", 0),
            "license_group_types": schedule_data.get("license_group_types", []),
            "start_type": schedule_data.get("start_type", ""),
        }
        
        # Create or update event
        event = self._create_or_update_event(season, schedule_data, sim_layout, round_num, is_team_event, min_team_drivers, max_team_drivers, fair_share_pct, multiclass, required_compounds, additional_details, simulated_start_time)
        
        # Process car classes
        self._process_car_classes(event, car_class_ids)
        
        # Process car restrictions (BOP)
        self._process_car_restrictions(event, schedule_data.get("car_restrictions", []), fixed_setup)
        
        # Process event sessions
        if simulated_start_time:
            self._process_event_sessions(event, schedule_data, simulated_start_time)
        
        # Process time patterns and create time slots if needed
        self._process_time_patterns(event, schedule_data.get("race_time_descriptors", []))
        
        # Process weather
        if event.weather_forecast_url:
            self._process_weather(event_id=event.id)
        

    def _process_weather(self, event_id: int) -> None:
        """Process weather data for an event."""
        # import here to avoid circular import
        from simlane.iracing.tasks import sync_iracing_weather_task
        
        sync_iracing_weather_task.delay(event_id=event_id, refresh=True) # type: ignore
        self.weather_sync_queued += 1
    
    def _process_event_sessions(self, event: Event, schedule_data: Schedule, simulated_start_time: str) -> None:
        qualify_length = schedule_data.get("qualify_length", 0)
        qual_attached = schedule_data.get("qual_attached", False)
        qualify_laps = schedule_data.get("quailfy_laps", None)
        practice_length = schedule_data.get("practice_length", None)
        warmup_length = schedule_data.get("warmup_length", None)
        race_time_limit = schedule_data.get("race_time_limit", None)
        race_lap_limit = schedule_data.get("race_lap_limit", None)
        race_time_limit = schedule_data.get("race_time_limit", None)
        race_lap_limit = schedule_data.get("race_lap_limit", None)
        simulated_time_multiplier = schedule_data.get("weather", {}).get("simulated_time_multiplier", 1)
        simulated_time_offsets = schedule_data.get("weather", {}).get("simulated_time_offsets", [])
        
        in_game_time = datetime.fromisoformat(simulated_start_time)
        
        # Process event sessions
        if warmup_length:
            _event_session, created = EventSession.objects.update_or_create(
                event=event,
                session_type=SessionType.WARMUP,
                defaults={
                    "duration": warmup_length,
                    "in_game_time": in_game_time,
                }
            )
            if created:
                self.event_sessions_created += 1
            else:
                self.event_sessions_updated += 1
            
        elif practice_length:
            _event_session, created = EventSession.objects.update_or_create(
                event=event,
                session_type=SessionType.PRACTICE,
                defaults={
                    "duration": practice_length,
                    "in_game_time": in_game_time,
                }
            )
            if created:
                self.event_sessions_created += 1
            else:
                self.event_sessions_updated += 1
        
        if qual_attached:
            _event_session, created = EventSession.objects.update_or_create(
                event=event,
                session_type=SessionType.QUALIFYING,
                defaults={
                    "duration": qualify_length,
                    "laps": qualify_laps,
                    "in_game_time": in_game_time + timedelta(minutes=simulated_time_offsets[0] * simulated_time_multiplier),
                }
            )
            if created:
                self.event_sessions_created += 1
            else:
                self.event_sessions_updated += 1
        
        if race_time_limit or race_lap_limit:
            _event_session, created = EventSession.objects.update_or_create(
                event=event,
                session_type=SessionType.RACE,
                defaults={
                    "duration": race_time_limit,
                    "laps": race_lap_limit,
                    "in_game_time": in_game_time + timedelta(minutes=simulated_time_offsets[1] * simulated_time_multiplier if 
                                                             len(simulated_time_offsets) > 1 else simulated_time_offsets[0] * simulated_time_multiplier),
                }
            )
            if created:
                self.event_sessions_created += 1
            else:
                self.event_sessions_updated += 1
        
    def _find_sim_layout(self, track_id: int, track_name: str, layout_name: str) -> Optional[SimLayout]:
        """Find SimLayout by track_id or fallback to name matching."""
        try:
            # Try by layout_code first
            return SimLayout.objects.get(layout_code=track_id)
        except SimLayout.DoesNotExist:
            # Fallback to name matching
            try:
                return SimLayout.objects.get(
                    sim_track__name__icontains=track_name,
                    name__icontains=layout_name,
                )
            except SimLayout.DoesNotExist:
                logger.warning(
                    f"Track layout not found for {track_name} ({track_id}) layout {layout_name}"
                )
                return None
    
    def _create_or_update_event(
        self, 
        season: Season, 
        schedule_data: Schedule, 
        sim_layout: SimLayout,
        round_num: int,
        is_team_event: bool,
        min_team_drivers: int,
        max_team_drivers: int,
        fair_share_pct: int,
        multiclass: bool,
        required_compounds: dict,
        additional_details: dict,
        simulated_start_time: datetime,
    ) -> Event:
        """Create or update an event from schedule data."""
        series = season.series
        series_name = schedule_data.get("series_name") or series.name
        track_name = schedule_data.get("track", {}).get("track_name", "")
        layout_name = schedule_data.get("track", {}).get("config_name") or "Default"
        
        # Generate event name
        event_name = self._generate_event_name(series_name, round_num, track_name, layout_name)
        event_slug = slugify(event_name)[:280]
        
        # Extract weather and timing data
        weather_data = schedule_data.get("weather", {})        
        # Parse weather summary for quick stats
        weather_summary = weather_data.get("weather_summary", {})
        min_temp = weather_summary.get("temp_low")
        max_temp = weather_summary.get("temp_high")
        max_precip = weather_summary.get("precip_chance", 0)
        
        start_date = datetime.fromisoformat(schedule_data.get("start_date"))
        week_end_time = datetime.fromisoformat(schedule_data.get("week_end_time"))
        
        time_pattern = schedule_data.get("race_time_descriptors", [])
        
        # event status if it's in the past, is ongoing, or is in the future
        if week_end_time < timezone.now():
            event_status = EventStatus.COMPLETED
        elif (timezone.make_aware(start_date, timezone.get_default_timezone()) < timezone.now() and week_end_time > timezone.now()):
            event_status = EventStatus.ONGOING
        else:
            event_status = EventStatus.SCHEDULED
        
        # Prepare event data
        event_defaults = {
            "series": series,
            "season": season,
            "simulator": self.simulator,
            "sim_layout": sim_layout,
            "event_source": EventSource.OFFICIAL,
            "status": event_status,
            "start_date": schedule_data.get("start_date"),
            "end_date": schedule_data.get("week_end_time"),
            "name": event_name,
            "slug": event_slug,
            "description": f"{self.simulator.name} {series_name} Week {round_num}",
            "round_number": round_num,
            "category": schedule_data.get("track", {}).get("category", ""),
            
            # Weather configuration
            "weather_config": weather_data,
            "weather_forecast_url": weather_data.get("weather_url", ""),
            "weather_forecast_version": weather_data.get("weather_forecast_version", 1),
            "min_air_temp": min_temp,
            "max_air_temp": max_temp,
            "max_precip_chance": max_precip,
            
            # Time pattern (store for dynamic time slot generation)
            "time_pattern": time_pattern,
            
            # Track-specific settings
            "enable_pitlane_collisions": schedule_data.get("enable_pitlane_collisions", False),
            "full_course_cautions": schedule_data.get("full_course_cautions", True),
            "schedule_name": schedule_data.get("schedule_name", ""),
            "is_team_event": is_team_event,
            "min_drivers_per_entry": min_team_drivers,
            "max_drivers_per_entry": max_team_drivers,
            "fair_share_pct": fair_share_pct,
            "multiclass": multiclass,
            "created_at": schedule_data.get("created_at", timezone.now()),
            "required_compounds": required_compounds,
            "additional_details": additional_details,
            "simulated_start_time": simulated_start_time,
        }
        
        # Create lookup criteria
        lookup_criteria = {
            "series": series,
            "season": season,
            "round_number": round_num,
            "sim_layout": sim_layout,
        }
        
        # Create or update event
        event, created = Event.objects.get_or_create(
            **lookup_criteria,
            defaults=event_defaults,
        )
        
        if not created:
            # Update existing event
            for key, value in event_defaults.items():
                if hasattr(event, key):
                    setattr(event, key, value)
            event.save()
            self.events_updated += 1
            logger.debug(f"Updated event: {event_name}")
        else:
            self.events_created += 1
            logger.debug(f"Created event: {event_name}")
        
        return event
    
    def _generate_event_name(
        self, 
        series_name: str, 
        round_num: int, 
        track_name: str, 
        layout_name: str
    ) -> str:
        """Generate a descriptive event name."""
        week_display = f"Week {round_num}" if round_num is not None else "Event"
        event_name = f"{series_name} - {week_display} - {track_name}"
        
        if layout_name and layout_name.lower() not in ["default", ""]:
            event_name += f" ({layout_name})"
        
        return event_name
    
    def _process_car_restrictions(self, event: Event, car_restrictions: List[Dict[str, Any]], fixed_setup: bool) -> None:
        """Process car restrictions (BOP) for an event."""
        for restriction_data in car_restrictions:
            try:
                car_id = restriction_data.get("car_id")
                if not car_id:
                    continue
                
                # Find the SimCar
                try:
                    sim_car = SimCar.objects.get(
                        sim_api_id=car_id,
                        simulator=self.simulator
                    )
                except SimCar.DoesNotExist:
                    logger.warning(f"SimCar not found for car_id {car_id}")
                    continue
                
                # Create or update car restriction
                CarRestriction.objects.update_or_create(
                    event=event,
                    sim_car=sim_car,
                    defaults={
                        "max_dry_tire_sets": restriction_data.get("max_dry_tire_sets", 0),
                        "max_pct_fuel_fill": restriction_data.get("max_pct_fuel_fill", 100),
                        "power_adjust_pct": restriction_data.get("power_adjust_pct", 0.0),
                        "weight_penalty_kg": restriction_data.get("weight_penalty_kg", 0),
                        "is_fixed_setup": fixed_setup or False,
                    },
                )
                
            except Exception as e:
                logger.warning(f"Error processing car restriction: {e}")
    
    def _process_car_classes(self, event: Event, car_class_ids: List[int]) -> None:
        """Process car classes for an event."""
        for car_class_id in car_class_ids:
            try:
                car_class_order = car_class_ids.index(car_class_id) + 1
                car_class = CarClass.objects.get(sim_api_id=car_class_id, simulator=self.simulator)
                
                # Create event class
                event_class, created = EventClass.objects.update_or_create(
                    event=event,
                    car_class=car_class,
                    defaults={
                        "name": car_class.name,
                        "class_order": car_class_order
                    },
                )
                if created:
                    self.event_classes_created += 1
                else:
                    self.event_classes_updated += 1
                    
            except Exception as e:
                logger.warning(f"Error processing Event Class: {e}")
    
    def _process_time_patterns(self, event: Event, race_time_descriptors: List[Dict[str, Any]]) -> None:
        """
        Process time patterns and create TimeSlot instances for specific times only.
        
        For repeating patterns, we store the pattern in the event and generate
        time slots dynamically when needed.
        """
        if not race_time_descriptors:
            return
        
        for time_descriptor in race_time_descriptors:
            is_repeating = time_descriptor.get("repeating", False)
            
            if is_repeating:
                # For repeating patterns, just store in event.time_pattern
                # Time slots will be generated dynamically
                logger.debug(
                    f"Storing repeating pattern for event {event.name}: "
                    f"every {time_descriptor.get('repeat_minutes', 'unknown')} minutes"
                )
                continue
            else:
                # For specific times, create actual TimeSlot instances
                self._create_specific_time_slots(event, time_descriptor)
    
    def _create_specific_time_slots(self, event: Event, time_descriptor: Dict[str, Any]) -> None:
        """Create TimeSlot instances for specific (non-repeating) time patterns."""
        session_times = time_descriptor.get("session_times", [])
        session_minutes = time_descriptor.get("session_minutes", 60)
        
        if not session_times:
            logger.warning(f"No session_times found in specific time pattern for event {event.name}")
            return
        
        logger.info(
            f"Creating {len(session_times)} specific time slots for event {event.name}"
        )
        
        for session_time_str in session_times:
            try:
                # Parse the session time string (e.g., "2025-06-21T02:00:00Z")
                if isinstance(session_time_str, str):
                    session_time = datetime.fromisoformat(session_time_str.replace('Z', '+00:00'))
                else:
                    session_time = session_time_str
                
                # Make sure it's timezone aware
                if session_time.tzinfo is None:
                    session_time = timezone.make_aware(session_time)
                
                # Calculate end time
                end_time = session_time + timedelta(minutes=session_minutes)
                
                # Create registration times (open 1 hour before, close at start)
                registration_open = session_time - timedelta(hours=1)
                registration_ends = session_time
                
                # Create the time slot
                time_slot, created = TimeSlot.objects.get_or_create(
                    event=event,
                    start_time=session_time,
                    defaults={
                        "end_time": end_time,
                        "registration_open": registration_open,
                        "registration_ends": registration_ends,
                        "is_predicted": True,  # This is from schedule, not actual results
                    }
                )
                
                if created:
                    self.time_slots_created += 1
                    logger.debug(f"Created specific time slot for {event.name} at {session_time}")
                else:
                    logger.debug(f"Time slot already exists for {event.name} at {session_time}")
                    
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing session time '{session_time_str}' for event {event.name}: {e}")
                continue


class RecurrenceHandler:
    """Handles dynamic generation of time slots from recurrence patterns."""
    
    @staticmethod
    def generate_time_slots_for_period(
        event: Event, 
        start_date: datetime, 
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        Generate time slots for an event within a specific period.
        
        This is used for displaying upcoming races without creating
        database records for every possible time slot.
        
        Args:
            event: Event with time_pattern data
            start_date: Start of period to generate slots for
            end_date: End of period to generate slots for
            
        Returns:
            List of time slot data dictionaries
        """
        if not event.time_pattern or "race_time_descriptors" not in event.time_pattern:
            return []
        
        time_slots = []
        race_time_descriptors = event.time_pattern["race_time_descriptors"]
        
        for descriptor in race_time_descriptors:
            if not descriptor.get("repeating", False):
                continue
            
            slots = RecurrenceHandler._generate_repeating_slots(
                descriptor, start_date, end_date, event
            )
            time_slots.extend(slots)
        
        return sorted(time_slots, key=lambda x: x["start_time"])
    
    @staticmethod
    def _generate_repeating_slots(
        descriptor: Dict[str, Any], 
        start_date: datetime, 
        end_date: datetime,
        event: Event
    ) -> List[Dict[str, Any]]:
        """Generate time slots for a repeating pattern."""
        time_slots = []
        
        # Parse pattern data
        first_session_time = descriptor.get("first_session_time", "00:00:00")
        repeat_minutes = descriptor.get("repeat_minutes", 60)
        session_minutes = descriptor.get("session_minutes", 60)
        day_offsets = descriptor.get("day_offset", [0, 1, 2, 3, 4, 5, 6])
        pattern_start_date = descriptor.get("start_date")
        
        if not pattern_start_date:
            logger.warning("No start_date in repeating pattern descriptor")
            return time_slots
        
        # Parse start date and first session time
        try:
            if isinstance(pattern_start_date, str):
                # Handle both date strings and datetime strings
                if 'T' in pattern_start_date or 'Z' in pattern_start_date:
                    base_date = datetime.fromisoformat(pattern_start_date.replace('Z', '+00:00'))
                else:
                    # Just a date string like "2025-02-11"
                    base_date = datetime.strptime(pattern_start_date, "%Y-%m-%d")
            else:
                base_date = pattern_start_date
            
            # Make sure base_date is timezone aware
            if base_date.tzinfo is None:
                base_date = timezone.make_aware(base_date)
            
            # Parse first session time
            time_parts = first_session_time.split(":")
            session_hour = int(time_parts[0])
            session_minute = int(time_parts[1])
            session_second = int(time_parts[2]) if len(time_parts) > 2 else 0
            
        except (ValueError, AttributeError) as e:
            logger.warning(f"Error parsing time pattern: {e}")
            return time_slots
        
        # Generate slots
        current_date = max(start_date.date(), base_date.date())
        end_date_only = end_date.date()
        
        logger.debug(f"Generating repeating slots from {current_date} to {end_date_only} for event {event.name}")
        logger.debug(f"Pattern: every {repeat_minutes}min starting at {first_session_time} on days {day_offsets}")
        
        while current_date <= end_date_only:
            # Calculate day offset from the pattern start date
            # iRacing weeks typically start on Tuesday, but we use the pattern's start_date as reference
            days_from_start = (current_date - base_date.date()).days
            day_offset = days_from_start % 7
            
            if day_offset in day_offsets:
                # Generate slots for this day
                current_datetime = timezone.make_aware(
                    datetime.combine(current_date, datetime.min.time())
                )
                
                # Start from first session time
                slot_time = current_datetime.replace(
                    hour=session_hour, 
                    minute=session_minute, 
                    second=session_second, 
                    microsecond=0
                )
                
                # Generate slots throughout the day (24 hour period from first session)
                day_end = slot_time + timedelta(hours=24)
                
                slot_count = 0
                while slot_time < day_end and slot_time.date() == current_date:
                    if start_date <= slot_time <= end_date:
                        end_time = slot_time + timedelta(minutes=session_minutes)
                        
                        time_slots.append({
                            "start_time": slot_time,
                            "end_time": end_time,
                            "registration_open": slot_time - timedelta(hours=1),
                            "registration_ends": slot_time,
                            "is_predicted": True,
                            "event": event,
                        })
                        slot_count += 1
                    
                    slot_time += timedelta(minutes=repeat_minutes)
                
                logger.debug(f"Generated {slot_count} slots for {current_date} (day_offset {day_offset})")
            
            current_date += timedelta(days=1)
        
        logger.debug(f"Total slots generated: {len(time_slots)}")
        return time_slots


def create_season_from_schedule_data(
    series: Series, 
    season_data: Union[Dict[str, Any], Any]
) -> Season:
    """
    Create or update a Season from API schedule data.
    
    Args:
        series: Series instance
        season_data: Season data from API
        
    Returns:
        Season instance
    """
    season_id = season_data.get("season_id")
    season_name = season_data.get("season_name", "")
    schedule_description = season_data.get("schedule_description", "")
    
    if not season_id:
        raise ValueError("Season data missing season_id")
    
    # Calculate season dates from schedules
    schedules = season_data.get("schedules", [])
    season_start_date = None
    season_end_date = None
    
    if schedules:
        start_dates = []
        end_dates = []
        
        for schedule in schedules:
            start_str = schedule.get("start_date")
            end_str = schedule.get("week_end_time")
            
            try:
                if start_str:
                    if isinstance(start_str, str):
                        start_date = datetime.fromisoformat(start_str.replace('Z', '+00:00')).date()
                    else:
                        start_date = start_str.date() if hasattr(start_str, 'date') else start_str
                    start_dates.append(start_date)
            except (ValueError, AttributeError):
                pass
            
            try:
                if end_str:
                    if isinstance(end_str, str):
                        end_date = datetime.fromisoformat(end_str.replace('Z', '+00:00')).date()
                    else:
                        end_date = end_str.date() if hasattr(end_str, 'date') else end_str
                    end_dates.append(end_date)
            except (ValueError, AttributeError):
                pass
        
        if start_dates:
            season_start_date = min(start_dates)
        if end_dates:
            season_end_date = max(end_dates)
    
    # Determine season status
    from datetime import date
    today = date.today()
    
    if season_end_date and season_end_date < today:
        is_active = False
        is_complete = True
    elif season_start_date and season_start_date > today:
        is_active = False
        is_complete = False
    else:
        is_active = True
        is_complete = False
    
    # Create or update season
    season, created = Season.objects.get_or_create(
        external_season_id=season_id,
        defaults={
            "name": season_name,
            "series": series,
            "active": is_active,
            "complete": is_complete,
            "start_date": season_start_date,
            "end_date": season_end_date,
            "schedule_description": schedule_description,
        },
    )
    
    if not created:
        # Update existing season
        season.name = season_name
        season.active = is_active
        season.complete = is_complete
        season.start_date = season_start_date
        season.end_date = season_end_date
        season.schedule_description = schedule_description
        season.save(update_fields=["name", "active", "complete", "start_date", "end_date", "schedule_description"])
    
    return season 