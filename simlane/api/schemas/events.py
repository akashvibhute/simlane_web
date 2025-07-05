# Legacy event schemas removed (TeamAllocation, TeamEventStrategy, StintAssignment)
# These have been replaced by the enhanced EventParticipation and AvailabilityWindow system
# Located in simlane/teams/models.py

# If new event-related API schemas are needed, they should be based on:
# - EventParticipation model for unified event participation
# - AvailabilityWindow model for granular availability tracking
# - Team model for team management (preserved)
# - ClubEvent model for event organization (preserved)

# Example future schemas (not implemented):
#
# from pydantic import BaseModel
# from datetime import datetime
# from uuid import UUID
#
# class EventParticipationCreate(BaseModel):
#     event_id: UUID
#     participation_type: str
#     preferred_car_id: int | None = None
#     experience_level: str | None = None
#     max_stint_duration: int | None = None
#     notes: str = ""
#
# class AvailabilityWindowCreate(BaseModel):
#     participation_id: UUID
#     start_time: datetime
#     end_time: datetime
#     can_drive: bool = False
#     can_spot: bool = False
#     can_strategize: bool = False
#     preference_level: int = 3

from datetime import datetime
from typing import List, Optional
from uuid import UUID
from ninja import Schema

class WeatherForecastSchema(Schema):
    id: UUID
    time_offset: int
    timestamp: datetime
    is_sun_up: bool
    affects_session: bool
    air_temperature: float
    pressure: float
    wind_speed: float
    wind_direction: int
    precipitation_chance: int
    precipitation_amount: float
    allow_precipitation: bool
    cloud_cover: int
    relative_humidity: int
    forecast_version: int
    valid_stats: bool

class SessionSchema(Schema):
    id: UUID
    session_type: str
    in_game_time: Optional[datetime] = None
    duration: Optional[int] = None
    laps: Optional[int] = None

class EventWeatherDataSchema(Schema):
    event_id: UUID
    time_slot_id: Optional[UUID] = None
    weather_forecasts: List[WeatherForecastSchema]
    sessions: List[SessionSchema]

# All legacy event schemas have been removed
# This file is kept as a placeholder for future event API schemas
