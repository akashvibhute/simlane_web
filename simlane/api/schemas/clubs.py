from datetime import datetime
from enum import Enum

from pydantic import BaseModel
from pydantic import validator

from .sim import SimCarBase
from .sim import SimTrackBase
from .sim import SimulatorBase


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
    avatar_url: str | None = None

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
    logo_url: str | None = None
    website: str | None = None
    discord_server: str | None = None


class ClubCreate(BaseModel):
    name: str
    description: str
    is_public: bool = True
    max_members: int = 50
    website: str | None = None
    discord_server: str | None = None
    timezone: str = "UTC"

    @validator("name")
    def name_validation(cls, v):
        if len(v) < 3:
            raise ValueError("Club name must be at least 3 characters long")
        return v

    @validator("max_members")
    def max_members_validation(cls, v):
        if v < 1 or v > 1000:
            raise ValueError("Max members must be between 1 and 1000")
        return v


class ClubUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_public: bool | None = None
    max_members: int | None = None
    website: str | None = None
    discord_server: str | None = None
    timezone: str | None = None


class ClubMemberBase(BaseModel):
    id: int
    role: ClubRole
    date_joined: datetime
    is_active: bool
    nickname: str | None = None
    notes: str | None = None

    class Config:
        from_attributes = True


class ClubMember(ClubMemberBase):
    user: UserBase
    club: ClubBase


class ClubMemberUpdate(BaseModel):
    role: ClubRole | None = None
    nickname: str | None = None
    notes: str | None = None
    is_active: bool | None = None


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
    logo_url: str | None = None
    captain: UserBase | None = None
    members: list[UserBase] = []


class TeamCreate(BaseModel):
    name: str
    description: str
    max_members: int = 4
    color: str = "#FF2300"
    captain_id: int | None = None

    @validator("name")
    def name_validation(cls, v):
        if len(v) < 2:
            raise ValueError("Team name must be at least 2 characters long")
        return v

    @validator("max_members")
    def max_members_validation(cls, v):
        if v < 1 or v > 20:
            raise ValueError("Max members must be between 1 and 20")
        return v

    @validator("color")
    def color_validation(cls, v):
        if not v.startswith("#") or len(v) != 7:
            raise ValueError("Color must be a valid hex color (e.g., #FF2300)")
        return v


class TeamUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    max_members: int | None = None
    color: str | None = None
    captain_id: int | None = None
    is_active: bool | None = None


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

    @validator("expires_in_days")
    def expires_validation(cls, v):
        if v < 1 or v > 30:
            raise ValueError("Expiration must be between 1 and 30 days")
        return v
