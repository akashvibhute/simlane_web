from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel
from pydantic import validator

from .auth import UserProfile


class TrackType(str, Enum):
    ROAD = "ROAD"
    OVAL = "OVAL"
    DIRT_ROAD = "DIRT_ROAD"
    DIRT_OVAL = "DIRT_OVAL"


class SessionType(str, Enum):
    PRACTICE = "PRACTICE"
    QUALIFYING = "QUALIFYING"
    RACE = "RACE"


class SimulatorBase(BaseModel):
    id: int
    name: str
    short_name: str
    is_active: bool

    class Config:
        from_attributes = True


class Simulator(SimulatorBase):
    icon_url: str | None = None
    api_integration: bool = False
    website: str | None = None
    created_at: datetime
    updated_at: datetime


class SimulatorCreate(BaseModel):
    name: str
    short_name: str
    icon_url: str | None = None
    api_integration: bool = False
    website: str | None = None
    is_active: bool = True

    @validator("name")
    def name_validation(cls, v):
        if len(v) < 2:
            raise ValueError("Simulator name must be at least 2 characters long")
        return v

    @validator("short_name")
    def short_name_validation(cls, v):
        if len(v) < 2 or len(v) > 10:
            raise ValueError("Short name must be between 2 and 10 characters")
        return v


class SimulatorUpdate(BaseModel):
    name: str | None = None
    short_name: str | None = None
    icon_url: str | None = None
    api_integration: bool | None = None
    website: str | None = None
    is_active: bool | None = None


class SimProfileBase(BaseModel):
    id: int
    profile_id: str
    display_name: str
    is_verified: bool
    last_updated: datetime

    class Config:
        from_attributes = True


class SimProfile(SimProfileBase):
    user: UserProfile
    simulator: SimulatorBase
    rating: int | None = None
    license_class: str | None = None
    safety_rating: float | None = None
    profile_data: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class SimProfileCreate(BaseModel):
    simulator_id: int
    profile_id: str
    display_name: str
    rating: int | None = None
    license_class: str | None = None
    safety_rating: float | None = None

    @validator("profile_id")
    def profile_id_validation(cls, v):
        if len(v) < 1:
            raise ValueError("Profile ID cannot be empty")
        return v

    @validator("display_name")
    def display_name_validation(cls, v):
        if len(v) < 2:
            raise ValueError("Display name must be at least 2 characters long")
        return v


class SimProfileUpdate(BaseModel):
    display_name: str | None = None
    rating: int | None = None
    license_class: str | None = None
    safety_rating: float | None = None
    profile_data: dict[str, Any] | None = None
    is_verified: bool | None = None


class SimCarBase(BaseModel):
    id: int
    name: str
    category: str
    is_active: bool

    class Config:
        from_attributes = True


class SimCar(SimCarBase):
    simulator: SimulatorBase
    class_name: str | None = None
    power_hp: int | None = None
    weight_kg: int | None = None
    year: int | None = None
    manufacturer: str | None = None
    image_url: str | None = None
    created_at: datetime
    updated_at: datetime


class SimCarCreate(BaseModel):
    simulator_id: int
    name: str
    category: str
    class_name: str | None = None
    power_hp: int | None = None
    weight_kg: int | None = None
    year: int | None = None
    manufacturer: str | None = None
    image_url: str | None = None
    is_active: bool = True

    @validator("name")
    def name_validation(cls, v):
        if len(v) < 2:
            raise ValueError("Car name must be at least 2 characters long")
        return v

    @validator("power_hp")
    def power_validation(cls, v):
        if v is not None and (v < 0 or v > 5000):
            raise ValueError("Power must be between 0 and 5000 HP")
        return v

    @validator("weight_kg")
    def weight_validation(cls, v):
        if v is not None and (v < 0 or v > 10000):
            raise ValueError("Weight must be between 0 and 10000 kg")
        return v

    @validator("year")
    def year_validation(cls, v):
        if v is not None and (v < 1900 or v > 2030):
            raise ValueError("Year must be between 1900 and 2030")
        return v


class SimCarUpdate(BaseModel):
    name: str | None = None
    category: str | None = None
    class_name: str | None = None
    power_hp: int | None = None
    weight_kg: int | None = None
    year: int | None = None
    manufacturer: str | None = None
    image_url: str | None = None
    is_active: bool | None = None


class SimTrackBase(BaseModel):
    id: int
    name: str
    location: str
    country: str
    length_km: float
    turns: int
    type: TrackType
    is_active: bool

    class Config:
        from_attributes = True


class SimTrack(SimTrackBase):
    simulator: SimulatorBase
    image_url: str | None = None
    elevation_change: int | None = None
    surface_type: str | None = None
    created_at: datetime
    updated_at: datetime


class SimTrackCreate(BaseModel):
    simulator_id: int
    name: str
    location: str
    country: str
    length_km: float
    turns: int
    type: TrackType
    image_url: str | None = None
    elevation_change: int | None = None
    surface_type: str | None = None
    is_active: bool = True

    @validator("name")
    def name_validation(cls, v):
        if len(v) < 2:
            raise ValueError("Track name must be at least 2 characters long")
        return v

    @validator("length_km")
    def length_validation(cls, v):
        if v <= 0 or v > 50:
            raise ValueError("Track length must be between 0 and 50 km")
        return v

    @validator("turns")
    def turns_validation(cls, v):
        if v < 0 or v > 100:
            raise ValueError("Number of turns must be between 0 and 100")
        return v


class SimTrackUpdate(BaseModel):
    name: str | None = None
    location: str | None = None
    country: str | None = None
    length_km: float | None = None
    turns: int | None = None
    type: TrackType | None = None
    image_url: str | None = None
    elevation_change: int | None = None
    surface_type: str | None = None
    is_active: bool | None = None


class LapTimeBase(BaseModel):
    id: int
    lap_time: str
    session_type: SessionType
    is_valid: bool
    recorded_at: datetime

    class Config:
        from_attributes = True


class LapTime(LapTimeBase):
    user: UserProfile
    simulator: SimulatorBase
    car: SimCarBase
    track: SimTrackBase
    weather_conditions: str | None = None
    track_temperature: float | None = None
    air_temperature: float | None = None
    created_at: datetime
    updated_at: datetime


class LapTimeCreate(BaseModel):
    simulator_id: int
    car_id: int
    track_id: int
    lap_time: str
    session_type: SessionType
    weather_conditions: str | None = None
    track_temperature: float | None = None
    air_temperature: float | None = None
    recorded_at: datetime | None = None

    @validator("lap_time")
    def lap_time_validation(cls, v):
        # Basic validation for lap time format (mm:ss.sss)
        import re

        if not re.match(r"^\d{1,2}:\d{2}\.\d{3}$", v):
            raise ValueError("Lap time must be in format mm:ss.sss (e.g., 1:23.456)")
        return v


class LapTimeUpdate(BaseModel):
    lap_time: str | None = None
    session_type: SessionType | None = None
    weather_conditions: str | None = None
    track_temperature: float | None = None
    air_temperature: float | None = None
    is_valid: bool | None = None


class DashboardStats(BaseModel):
    total_simulators: int
    total_cars: int
    total_tracks: int
    total_lap_times: int
    best_lap_time: str | None = None
    recent_sessions: int
    user_profiles: int
    verified_profiles: int


class SimDataSummary(BaseModel):
    simulator: SimulatorBase
    car_count: int
    track_count: int
    user_profiles: int
    recent_lap_times: int
    avg_lap_time: str | None = None
    best_lap_time: str | None = None
