from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID


class TeamAllocationCreate(BaseModel):
    club_event_id: UUID
    team_id: UUID
    assigned_sim_car_id: int
    slug: Optional[str] = None


class TeamAllocationUpdate(BaseModel):
    assigned_sim_car_id: Optional[int] = None
    slug: Optional[str] = None


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

    @validator('role')
    def validate_role(cls, v):
        allowed_roles = ['driver', 'reserve', 'spotter', 'strategist']
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v


class TeamAllocationMemberUpdate(BaseModel):
    role: Optional[str] = Field(None, pattern="^(driver|reserve|spotter|strategist)$")

    @validator('role')
    def validate_role(cls, v):
        if v is not None:
            allowed_roles = ['driver', 'reserve', 'spotter', 'strategist']
            if v not in allowed_roles:
                raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
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
    selected_class_id: Optional[int] = None
    strategy_notes: Optional[str] = ""
    slug: Optional[str] = None


class TeamEventStrategyUpdate(BaseModel):
    selected_car_id: Optional[int] = None
    selected_instance_id: Optional[int] = None
    selected_class_id: Optional[int] = None
    strategy_notes: Optional[str] = None
    calculated_pit_windows: Optional[Dict[str, Any]] = None
    fuel_strategy: Optional[Dict[str, Any]] = None
    tire_strategy: Optional[Dict[str, Any]] = None
    weather_contingencies: Optional[Dict[str, Any]] = None
    is_finalized: Optional[bool] = None


class TeamEventStrategy(BaseModel):
    id: UUID
    team_id: UUID
    club_event_id: UUID
    team_allocation_id: UUID
    slug: str
    selected_car_id: int
    selected_instance_id: int
    selected_class_id: Optional[int] = None
    strategy_notes: str
    calculated_pit_windows: Optional[Dict[str, Any]] = None
    fuel_strategy: Optional[Dict[str, Any]] = None
    tire_strategy: Optional[Dict[str, Any]] = None
    weather_contingencies: Optional[Dict[str, Any]] = None
    is_finalized: bool
    finalized_by_id: Optional[int] = None
    finalized_at: Optional[datetime] = None
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
    role: str = Field(default="primary_driver", pattern="^(primary_driver|secondary_driver|reserve_driver|spotter|strategist|pit_crew)$")
    pit_entry_planned: bool = False
    pit_strategy_notes: Optional[str] = ""
    fuel_load_start: Optional[float] = None
    fuel_load_end: Optional[float] = None
    tire_compound: Optional[str] = ""
    notes: Optional[str] = ""

    @validator('role')
    def validate_role(cls, v):
        allowed_roles = [
            'primary_driver', 'secondary_driver', 'reserve_driver', 
            'spotter', 'strategist', 'pit_crew'
        ]
        if v not in allowed_roles:
            raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v

    @validator('estimated_duration_minutes')
    def validate_duration(cls, v):
        if v <= 0:
            raise ValueError('Duration must be positive')
        return v


class StintAssignmentUpdate(BaseModel):
    estimated_start_time: Optional[datetime] = None
    estimated_end_time: Optional[datetime] = None
    estimated_duration_minutes: Optional[int] = None
    role: Optional[str] = Field(None, pattern="^(primary_driver|secondary_driver|reserve_driver|spotter|strategist|pit_crew)$")
    pit_entry_planned: Optional[bool] = None
    pit_strategy_notes: Optional[str] = None
    fuel_load_start: Optional[float] = None
    fuel_load_end: Optional[float] = None
    tire_compound: Optional[str] = None
    notes: Optional[str] = None

    @validator('role')
    def validate_role(cls, v):
        if v is not None:
            allowed_roles = [
                'primary_driver', 'secondary_driver', 'reserve_driver', 
                'spotter', 'strategist', 'pit_crew'
            ]
            if v not in allowed_roles:
                raise ValueError(f'Role must be one of: {", ".join(allowed_roles)}')
        return v

    @validator('estimated_duration_minutes')
    def validate_duration(cls, v):
        if v is not None and v <= 0:
            raise ValueError('Duration must be positive')
        return v


class StintAssignment(BaseModel):
    id: UUID
    team_strategy_id: UUID
    driver_id: int
    stint_number: int
    estimated_start_time: datetime
    estimated_end_time: datetime
    estimated_duration_minutes: int
    predicted_stint_id: Optional[UUID] = None
    role: str
    pit_entry_planned: bool
    pit_strategy_notes: str
    fuel_load_start: Optional[float] = None
    fuel_load_end: Optional[float] = None
    tire_compound: str
    notes: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True 