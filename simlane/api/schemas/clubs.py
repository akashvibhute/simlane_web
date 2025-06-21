from pydantic import BaseModel, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

from .auth import UserProfile
from .sim import SimulatorBase, SimCarBase, SimTrackBase


class ClubRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MANAGER = "MANAGER"
    MEMBER = "MEMBER"


class EventFormat(str, Enum):
    RACE = "RACE"
    QUALIFYING = "QUALIFYING"
    PRACTICE = "PRACTICE"
    ENDURANCE = "ENDURANCE"


class UserBase(BaseModel):
    id: int
    username: str
    first_name: str
    last_name: str
    avatar_url: Optional[str] = None

    class Config:
        from_attributes = True


class ClubBase(BaseModel):
    id: int
    name: str
    description: str
    is_public: bool
    timezone: str
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Club(ClubBase):
    max_members: int
    member_count: int
    owner: UserBase
    logo_url: Optional[str] = None
    website: Optional[str] = None
    discord_server: Optional[str] = None


class ClubCreate(BaseModel):
    name: str
    description: str
    is_public: bool = True
    max_members: int = 50
    website: Optional[str] = None
    discord_server: Optional[str] = None
    timezone: str = "UTC"

    @validator('name')
    def name_validation(cls, v):
        if len(v) < 3:
            raise ValueError('Club name must be at least 3 characters long')
        return v

    @validator('max_members')
    def max_members_validation(cls, v):
        if v < 1 or v > 1000:
            raise ValueError('Max members must be between 1 and 1000')
        return v


class ClubUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_public: Optional[bool] = None
    max_members: Optional[int] = None
    website: Optional[str] = None
    discord_server: Optional[str] = None
    timezone: Optional[str] = None


class ClubMemberBase(BaseModel):
    id: int
    role: ClubRole
    date_joined: datetime
    is_active: bool
    nickname: Optional[str] = None
    notes: Optional[str] = None

    class Config:
        from_attributes = True


class ClubMember(ClubMemberBase):
    user: UserBase
    club: ClubBase


class ClubMemberUpdate(BaseModel):
    role: Optional[ClubRole] = None
    nickname: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class TeamBase(BaseModel):
    id: int
    name: str
    description: str
    max_members: int
    is_active: bool
    color: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class Team(TeamBase):
    club: ClubBase
    logo_url: Optional[str] = None
    captain: Optional[UserBase] = None
    members: List[UserBase] = []


class TeamCreate(BaseModel):
    name: str
    description: str
    max_members: int = 4
    color: str = "#FF2300"
    captain_id: Optional[int] = None

    @validator('name')
    def name_validation(cls, v):
        if len(v) < 2:
            raise ValueError('Team name must be at least 2 characters long')
        return v

    @validator('max_members')
    def max_members_validation(cls, v):
        if v < 1 or v > 20:
            raise ValueError('Max members must be between 1 and 20')
        return v

    @validator('color')
    def color_validation(cls, v):
        if not v.startswith('#') or len(v) != 7:
            raise ValueError('Color must be a valid hex color (e.g., #FF2300)')
        return v


class TeamUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    max_members: Optional[int] = None
    color: Optional[str] = None
    captain_id: Optional[int] = None
    is_active: Optional[bool] = None


class ClubEventBase(BaseModel):
    id: int
    name: str
    description: str
    start_date: datetime
    duration_minutes: int
    max_signups: int
    signup_deadline: datetime
    is_team_event: bool
    event_format: EventFormat
    signup_count: int
    is_signup_open: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ClubEvent(ClubEventBase):
    club: ClubBase
    simulator: SimulatorBase
    car: SimCarBase
    track: SimTrackBase
    max_teams: Optional[int] = None
    points_system: Optional[str] = None
    weather_conditions: Optional[str] = None
    track_conditions: Optional[str] = None


class ClubEventCreate(BaseModel):
    name: str
    description: str
    simulator_id: int
    car_id: int
    track_id: int
    start_date: datetime
    duration_minutes: int = 60
    max_signups: int = 30
    signup_deadline: datetime
    is_team_event: bool = False
    max_teams: Optional[int] = None
    points_system: Optional[str] = None
    event_format: EventFormat = EventFormat.RACE
    weather_conditions: Optional[str] = None
    track_conditions: Optional[str] = None

    @validator('name')
    def name_validation(cls, v):
        if len(v) < 3:
            raise ValueError('Event name must be at least 3 characters long')
        return v

    @validator('duration_minutes')
    def duration_validation(cls, v):
        if v < 5 or v > 1440:  # 5 minutes to 24 hours
            raise ValueError('Duration must be between 5 minutes and 24 hours')
        return v

    @validator('max_signups')
    def max_signups_validation(cls, v):
        if v < 1 or v > 100:
            raise ValueError('Max signups must be between 1 and 100')
        return v


class ClubEventUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    simulator_id: Optional[int] = None
    car_id: Optional[int] = None
    track_id: Optional[int] = None
    start_date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    max_signups: Optional[int] = None
    signup_deadline: Optional[datetime] = None
    is_team_event: Optional[bool] = None
    max_teams: Optional[int] = None
    points_system: Optional[str] = None
    event_format: Optional[EventFormat] = None
    weather_conditions: Optional[str] = None
    track_conditions: Optional[str] = None


class EventSignupBase(BaseModel):
    id: int
    signup_time: datetime
    notes: Optional[str] = None
    car_number: Optional[int] = None
    livery_url: Optional[str] = None
    is_confirmed: bool
    is_reserve: bool
    expected_lap_time: Optional[str] = None

    class Config:
        from_attributes = True


class EventSignup(EventSignupBase):
    event: ClubEventBase
    user: UserBase
    team: Optional[TeamBase] = None


class EventSignupCreate(BaseModel):
    notes: Optional[str] = None
    car_number: Optional[int] = None
    livery_url: Optional[str] = None
    expected_lap_time: Optional[str] = None
    team_id: Optional[int] = None

    @validator('car_number')
    def car_number_validation(cls, v):
        if v is not None and (v < 1 or v > 999):
            raise ValueError('Car number must be between 1 and 999')
        return v


class EventSignupUpdate(BaseModel):
    notes: Optional[str] = None
    car_number: Optional[int] = None
    livery_url: Optional[str] = None
    expected_lap_time: Optional[str] = None
    is_confirmed: Optional[bool] = None
    is_reserve: Optional[bool] = None


class ClubInvitation(BaseModel):
    id: int
    email: str
    role: ClubRole
    invited_by: UserBase
    created_at: datetime
    expires_at: datetime
    is_accepted: bool

    class Config:
        from_attributes = True


class ClubInvitationCreate(BaseModel):
    email: str
    role: ClubRole = ClubRole.MEMBER
    expires_in_days: int = 7

    @validator('expires_in_days')
    def expires_validation(cls, v):
        if v < 1 or v > 30:
            raise ValueError('Expiration must be between 1 and 30 days')
        return v 