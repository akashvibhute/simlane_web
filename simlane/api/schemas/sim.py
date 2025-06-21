from pydantic import BaseModel, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

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
    icon_url: Optional[str] = None
    api_integration: bool = False
    website: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SimulatorCreate(BaseModel):
    name: str
    short_name: str
    icon_url: Optional[str] = None
    api_integration: bool = False
    website: Optional[str] = None
    is_active: bool = True

    @validator('name')
    def name_validation(cls, v):
        if len(v) < 2:
            raise ValueError('Simulator name must be at least 2 characters long')
        return v

    @validator('short_name')
    def short_name_validation(cls, v):
        if len(v) < 2 or len(v) > 10:
            raise ValueError('Short name must be between 2 and 10 characters')
        return v


class SimulatorUpdate(BaseModel):
    name: Optional[str] = None
    short_name: Optional[str] = None
    icon_url: Optional[str] = None
    api_integration: Optional[bool] = None
    website: Optional[str] = None
    is_active: Optional[bool] = None


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
    rating: Optional[int] = None
    license_class: Optional[str] = None
    safety_rating: Optional[float] = None
    profile_data: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime


class SimProfileCreate(BaseModel):
    simulator_id: int
    profile_id: str
    display_name: str
    rating: Optional[int] = None
    license_class: Optional[str] = None
    safety_rating: Optional[float] = None

    @validator('profile_id')
    def profile_id_validation(cls, v):
        if len(v) < 1:
            raise ValueError('Profile ID cannot be empty')
        return v

    @validator('display_name')
    def display_name_validation(cls, v):
        if len(v) < 2:
            raise ValueError('Display name must be at least 2 characters long')
        return v


class SimProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    rating: Optional[int] = None
    license_class: Optional[str] = None
    safety_rating: Optional[float] = None
    profile_data: Optional[Dict[str, Any]] = None
    is_verified: Optional[bool] = None


class SimCarBase(BaseModel):
    id: int
    name: str
    category: str
    is_active: bool

    class Config:
        from_attributes = True


class SimCar(SimCarBase):
    simulator: SimulatorBase
    class_name: Optional[str] = None
    power_hp: Optional[int] = None
    weight_kg: Optional[int] = None
    year: Optional[int] = None
    manufacturer: Optional[str] = None
    image_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class SimCarCreate(BaseModel):
    simulator_id: int
    name: str
    category: str
    class_name: Optional[str] = None
    power_hp: Optional[int] = None
    weight_kg: Optional[int] = None
    year: Optional[int] = None
    manufacturer: Optional[str] = None
    image_url: Optional[str] = None
    is_active: bool = True

    @validator('name')
    def name_validation(cls, v):
        if len(v) < 2:
            raise ValueError('Car name must be at least 2 characters long')
        return v

    @validator('power_hp')
    def power_validation(cls, v):
        if v is not None and (v < 0 or v > 5000):
            raise ValueError('Power must be between 0 and 5000 HP')
        return v

    @validator('weight_kg')
    def weight_validation(cls, v):
        if v is not None and (v < 0 or v > 10000):
            raise ValueError('Weight must be between 0 and 10000 kg')
        return v

    @validator('year')
    def year_validation(cls, v):
        if v is not None and (v < 1900 or v > 2030):
            raise ValueError('Year must be between 1900 and 2030')
        return v


class SimCarUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    class_name: Optional[str] = None
    power_hp: Optional[int] = None
    weight_kg: Optional[int] = None
    year: Optional[int] = None
    manufacturer: Optional[str] = None
    image_url: Optional[str] = None
    is_active: Optional[bool] = None


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
    image_url: Optional[str] = None
    elevation_change: Optional[int] = None
    surface_type: Optional[str] = None
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
    image_url: Optional[str] = None
    elevation_change: Optional[int] = None
    surface_type: Optional[str] = None
    is_active: bool = True

    @validator('name')
    def name_validation(cls, v):
        if len(v) < 2:
            raise ValueError('Track name must be at least 2 characters long')
        return v

    @validator('length_km')
    def length_validation(cls, v):
        if v <= 0 or v > 50:
            raise ValueError('Track length must be between 0 and 50 km')
        return v

    @validator('turns')
    def turns_validation(cls, v):
        if v < 0 or v > 100:
            raise ValueError('Number of turns must be between 0 and 100')
        return v


class SimTrackUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    country: Optional[str] = None
    length_km: Optional[float] = None
    turns: Optional[int] = None
    type: Optional[TrackType] = None
    image_url: Optional[str] = None
    elevation_change: Optional[int] = None
    surface_type: Optional[str] = None
    is_active: Optional[bool] = None


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
    weather_conditions: Optional[str] = None
    track_temperature: Optional[float] = None
    air_temperature: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class LapTimeCreate(BaseModel):
    simulator_id: int
    car_id: int
    track_id: int
    lap_time: str
    session_type: SessionType
    weather_conditions: Optional[str] = None
    track_temperature: Optional[float] = None
    air_temperature: Optional[float] = None
    recorded_at: Optional[datetime] = None

    @validator('lap_time')
    def lap_time_validation(cls, v):
        # Basic validation for lap time format (mm:ss.sss)
        import re
        if not re.match(r'^\d{1,2}:\d{2}\.\d{3}$', v):
            raise ValueError('Lap time must be in format mm:ss.sss (e.g., 1:23.456)')
        return v


class LapTimeUpdate(BaseModel):
    lap_time: Optional[str] = None
    session_type: Optional[SessionType] = None
    weather_conditions: Optional[str] = None
    track_temperature: Optional[float] = None
    air_temperature: Optional[float] = None
    is_valid: Optional[bool] = None


class DashboardStats(BaseModel):
    total_simulators: int
    total_cars: int
    total_tracks: int
    total_lap_times: int
    best_lap_time: Optional[str] = None
    recent_sessions: int
    user_profiles: int
    verified_profiles: int


class SimDataSummary(BaseModel):
    simulator: SimulatorBase
    car_count: int
    track_count: int
    user_profiles: int
    recent_lap_times: int
    avg_lap_time: Optional[str] = None
    best_lap_time: Optional[str] = None 