from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic import Field
from pydantic import validator


class TeamAllocationCreate(BaseModel):
    club_event_id: UUID
    team_id: UUID
    assigned_sim_car_id: int
    slug: str | None = None


class TeamAllocationUpdate(BaseModel):
    assigned_sim_car_id: int | None = None
    slug: str | None = None


class TeamAllocation(BaseModel):
    id: UUID
    club_event_id: UUID
    team_id: UUID
    slug: str
    assigned_sim_car_id: int
    created_by_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TeamAllocationMemberCreate(BaseModel):
    team_allocation_id: UUID
    event_signup_id: UUID
    role: str = Field(default="driver", pattern="^(driver|reserve|spotter|strategist)$")

    @validator("role")
    def validate_role(cls, v):
        allowed_roles = ["driver", "reserve", "spotter", "strategist"]
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v


class TeamAllocationMemberUpdate(BaseModel):
    role: str | None = Field(None, pattern="^(driver|reserve|spotter|strategist)$")

    @validator("role")
    def validate_role(cls, v):
        if v is not None:
            allowed_roles = ["driver", "reserve", "spotter", "strategist"]
            if v not in allowed_roles:
                raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v


class TeamAllocationMember(BaseModel):
    id: UUID
    team_allocation_id: UUID
    event_signup_id: UUID
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class TeamEventStrategyCreate(BaseModel):
    team_id: UUID
    club_event_id: UUID
    team_allocation_id: UUID
    selected_car_id: int
    selected_instance_id: int
    selected_class_id: int | None = None
    strategy_notes: str | None = ""
    slug: str | None = None


class TeamEventStrategyUpdate(BaseModel):
    selected_car_id: int | None = None
    selected_instance_id: int | None = None
    selected_class_id: int | None = None
    strategy_notes: str | None = None
    calculated_pit_windows: dict[str, Any] | None = None
    fuel_strategy: dict[str, Any] | None = None
    tire_strategy: dict[str, Any] | None = None
    weather_contingencies: dict[str, Any] | None = None
    is_finalized: bool | None = None


class TeamEventStrategy(BaseModel):
    id: UUID
    team_id: UUID
    club_event_id: UUID
    team_allocation_id: UUID
    slug: str
    selected_car_id: int
    selected_instance_id: int
    selected_class_id: int | None = None
    strategy_notes: str
    calculated_pit_windows: dict[str, Any] | None = None
    fuel_strategy: dict[str, Any] | None = None
    tire_strategy: dict[str, Any] | None = None
    weather_contingencies: dict[str, Any] | None = None
    is_finalized: bool
    finalized_by_id: int | None = None
    finalized_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StintAssignmentCreate(BaseModel):
    team_strategy_id: UUID
    driver_id: int
    stint_number: int
    estimated_start_time: datetime
    estimated_end_time: datetime
    estimated_duration_minutes: int
    role: str = Field(
        default="primary_driver",
        pattern="^(primary_driver|secondary_driver|reserve_driver|spotter|strategist|pit_crew)$",
    )
    pit_entry_planned: bool = False
    pit_strategy_notes: str | None = ""
    fuel_load_start: float | None = None
    fuel_load_end: float | None = None
    tire_compound: str | None = ""
    notes: str | None = ""

    @validator("role")
    def validate_role(cls, v):
        allowed_roles = [
            "primary_driver",
            "secondary_driver",
            "reserve_driver",
            "spotter",
            "strategist",
            "pit_crew",
        ]
        if v not in allowed_roles:
            raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v

    @validator("estimated_duration_minutes")
    def validate_duration(cls, v):
        if v <= 0:
            raise ValueError("Duration must be positive")
        return v


class StintAssignmentUpdate(BaseModel):
    estimated_start_time: datetime | None = None
    estimated_end_time: datetime | None = None
    estimated_duration_minutes: int | None = None
    role: str | None = Field(
        None,
        pattern="^(primary_driver|secondary_driver|reserve_driver|spotter|strategist|pit_crew)$",
    )
    pit_entry_planned: bool | None = None
    pit_strategy_notes: str | None = None
    fuel_load_start: float | None = None
    fuel_load_end: float | None = None
    tire_compound: str | None = None
    notes: str | None = None

    @validator("role")
    def validate_role(cls, v):
        if v is not None:
            allowed_roles = [
                "primary_driver",
                "secondary_driver",
                "reserve_driver",
                "spotter",
                "strategist",
                "pit_crew",
            ]
            if v not in allowed_roles:
                raise ValueError(f"Role must be one of: {', '.join(allowed_roles)}")
        return v

    @validator("estimated_duration_minutes")
    def validate_duration(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Duration must be positive")
        return v


class StintAssignment(BaseModel):
    id: UUID
    team_strategy_id: UUID
    driver_id: int
    stint_number: int
    estimated_start_time: datetime
    estimated_end_time: datetime
    estimated_duration_minutes: int
    predicted_stint_id: UUID | None = None
    role: str
    pit_entry_planned: bool
    pit_strategy_notes: str
    fuel_load_start: float | None = None
    fuel_load_end: float | None = None
    tire_compound: str
    notes: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
