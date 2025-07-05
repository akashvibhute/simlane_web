# Race Planning API endpoints with subscription gating
#
# These endpoints provide race planning functionality including:
# - EventParticipation team formation
# - RaceStrategy management  
# - StintPlan operations
# - AvailabilityWindow management
#
# All race planning features require appropriate subscription plans.
# See simlane.teams.models for the enhanced model structure.

from typing import List, Optional
from uuid import UUID
from datetime import datetime, timedelta

from django.shortcuts import get_object_or_404
from django.http import Http404
from django.utils import timezone
from ninja import Router, Schema
from ninja.errors import HttpError

from simlane.teams.models import (
    EventParticipation,
    AvailabilityWindow, 
    Team,
    RaceStrategy,
    StintPlan,
    Club,
    ClubMember,
)
from simlane.sim.models import Event, TimeSlot, WeatherForecast, EventSession
from simlane.users.models import User
from simlane.api.schemas.events import EventWeatherDataSchema, WeatherForecastSchema, SessionSchema

router = Router()

# ===== SCHEMAS =====

class EventParticipationSchema(Schema):
    id: UUID
    participation_type: str
    status: str
    user_id: Optional[UUID] = None
    team_id: Optional[UUID] = None
    preferred_car_id: Optional[UUID] = None
    assigned_car_id: Optional[UUID] = None
    experience_level: Optional[str] = None
    max_stint_duration: Optional[int] = None
    min_rest_duration: Optional[int] = None
    notes: Optional[str] = None
    signed_up_at: Optional[datetime] = None
    team_assigned_at: Optional[datetime] = None

class CreateEventParticipationSchema(Schema):
    participation_type: str
    team_id: Optional[UUID] = None
    preferred_car_id: Optional[UUID] = None
    backup_car_id: Optional[UUID] = None
    experience_level: Optional[str] = None
    max_stint_duration: Optional[int] = None
    min_rest_duration: Optional[int] = None
    notes: Optional[str] = None

class AvailabilityWindowSchema(Schema):
    id: UUID
    start_time: datetime
    end_time: datetime
    can_drive: bool
    can_spot: bool
    can_strategize: bool
    preference_level: int
    max_consecutive_stints: int
    preferred_stint_length: Optional[int] = None
    notes: Optional[str] = None

class CreateAvailabilityWindowSchema(Schema):
    start_time: datetime
    end_time: datetime
    can_drive: bool = False
    can_spot: bool = False
    can_strategize: bool = False
    preference_level: int = 3
    max_consecutive_stints: int = 1
    preferred_stint_length: Optional[int] = None
    notes: Optional[str] = None

class RaceStrategySchema(Schema):
    id: UUID
    name: str
    is_active: bool
    target_stint_length: int
    min_driver_rest: int
    pit_stop_time: int
    fuel_per_stint: Optional[float] = None
    fuel_tank_size: Optional[float] = None
    tire_change_frequency: int
    notes: Optional[str] = None
    created_at: datetime

class CreateRaceStrategySchema(Schema):
    name: str = "Primary Strategy"
    target_stint_length: int
    min_driver_rest: int
    pit_stop_time: int = 60
    fuel_per_stint: Optional[float] = None
    fuel_tank_size: Optional[float] = None
    tire_change_frequency: int = 1
    tire_compound_strategy: Optional[dict] = None
    notes: Optional[str] = None

class StintPlanSchema(Schema):
    id: UUID
    stint_number: int
    driver_id: UUID
    planned_start_lap: Optional[int] = None
    planned_end_lap: Optional[int] = None
    planned_start_time: Optional[timedelta] = None
    planned_duration: timedelta
    status: str
    pit_instructions: Optional[dict] = None
    notes: Optional[str] = None

class CreateStintPlanSchema(Schema):
    stint_number: int
    driver_id: UUID
    planned_start_lap: Optional[int] = None
    planned_end_lap: Optional[int] = None
    planned_start_time: Optional[timedelta] = None
    planned_duration: timedelta
    pit_instructions: Optional[dict] = None
    notes: Optional[str] = None

class TeamFormationRecommendationSchema(Schema):
    team_members: List[UUID]
    total_overlap_score: float
    coverage_estimate: float

# ===== HELPER FUNCTIONS =====

def check_race_planning_subscription(club: Club):
    """Check if club has subscription that allows race planning features"""
    # This will be implemented when billing models are available
    # For now, return True to allow development
    # TODO: Implement actual subscription check
    # from simlane.billing.models import ClubSubscription
    # subscription = ClubSubscription.objects.filter(club=club, status='active').first()
    # if not subscription or not subscription.plan.features.get('race_planning', False):
    #     raise HttpError(402, "Race planning features require a paid subscription")
    return True

def get_club_from_context(request, event_id: UUID) -> Club:
    """Get club context from request or event participation"""
    # Try to get club from request context (set by auth middleware)
    if hasattr(request, 'club'):
        return request.club
    
    # Fallback: get club from user's participation in the event
    if hasattr(request, 'user') and request.user.is_authenticated:
        participation = EventParticipation.objects.filter(
            event_id=event_id,
            user=request.user
        ).first()
        
        if participation and participation.signup_context_club:
            return participation.signup_context_club
    
    raise HttpError(403, "No club context found for race planning")

def check_team_management_permission(user: User, team: Team) -> bool:
    """Check if user can manage the specified team"""
    return team.can_user_manage(user)

# ===== EVENT PARTICIPATION ENDPOINTS =====

@router.get("/events/{event_id}/participations", response=List[EventParticipationSchema])
def list_event_participations(request, event_id: UUID):
    """List all participations for an event (club context)"""
    event = get_object_or_404(Event, id=event_id)
    club = get_club_from_context(request, event_id)
    check_race_planning_subscription(club)
    
    participations = EventParticipation.objects.filter(
        event=event,
        signup_context_club=club
    ).select_related('user', 'team')
    
    return participations

@router.post("/events/{event_id}/participations", response=EventParticipationSchema)
def create_event_participation(request, event_id: UUID, data: CreateEventParticipationSchema):
    """Create a new event participation"""
    event = get_object_or_404(Event, id=event_id)
    club = get_club_from_context(request, event_id)
    check_race_planning_subscription(club)
    
    # Verify user is club member
    if not ClubMember.objects.filter(club=club, user=request.user).exists():
        raise HttpError(403, "You must be a club member to participate")
    
    # Check if user already has participation for this event
    existing = EventParticipation.objects.filter(
        event=event,
        user=request.user
    ).exists()
    
    if existing:
        raise HttpError(400, "You already have a participation for this event")
    
    participation = EventParticipation.objects.create(
        event=event,
        user=request.user,
        signup_context_club=club,
        participation_type=data.participation_type,
        status="signed_up",
        signed_up_at=timezone.now(),
        **data.dict(exclude={'participation_type'})
    )
    
    return participation

@router.get("/events/{event_id}/participations/{participation_id}", response=EventParticipationSchema)
def get_event_participation(request, event_id: UUID, participation_id: UUID):
    """Get specific event participation"""
    event = get_object_or_404(Event, id=event_id)
    club = get_club_from_context(request, event_id)
    check_race_planning_subscription(club)
    
    participation = get_object_or_404(
        EventParticipation,
        id=participation_id,
        event=event,
        signup_context_club=club
    )
    
    return participation

@router.put("/events/{event_id}/participations/{participation_id}/assign-team")
def assign_participation_to_team(request, event_id: UUID, participation_id: UUID, team_id: UUID):
    """Assign a participation to a team"""
    event = get_object_or_404(Event, id=event_id)
    club = get_club_from_context(request, event_id)
    check_race_planning_subscription(club)
    
    participation = get_object_or_404(
        EventParticipation,
        id=participation_id,
        event=event,
        signup_context_club=club
    )
    
    team = get_object_or_404(Team, id=team_id, club=club)
    
    # Check permission to manage team
    if not check_team_management_permission(request.user, team):
        raise HttpError(403, "You don't have permission to manage this team")
    
    try:
        participation.assign_to_team(team, assigned_by=request.user)
        return {"success": True, "message": "Participation assigned to team"}
    except ValueError as e:
        raise HttpError(400, str(e))

# ===== AVAILABILITY WINDOW ENDPOINTS =====

@router.get("/events/{event_id}/participations/{participation_id}/availability", response=List[AvailabilityWindowSchema])
def list_availability_windows(request, event_id: UUID, participation_id: UUID):
    """List availability windows for a participation"""
    event = get_object_or_404(Event, id=event_id)
    club = get_club_from_context(request, event_id)
    check_race_planning_subscription(club)
    
    participation = get_object_or_404(
        EventParticipation,
        id=participation_id,
        event=event,
        signup_context_club=club
    )
    
    # Users can only view their own availability or team managers can view team member availability
    if participation.user != request.user:
        if not participation.team or not check_team_management_permission(request.user, participation.team):
            raise HttpError(403, "You don't have permission to view this availability")
    
    windows = AvailabilityWindow.objects.filter(participation=participation).order_by('start_time')
    return windows

@router.post("/events/{event_id}/participations/{participation_id}/availability", response=AvailabilityWindowSchema)
def create_availability_window(request, event_id: UUID, participation_id: UUID, data: CreateAvailabilityWindowSchema):
    """Create availability window for a participation"""
    event = get_object_or_404(Event, id=event_id)
    club = get_club_from_context(request, event_id)
    check_race_planning_subscription(club)
    
    participation = get_object_or_404(
        EventParticipation,
        id=participation_id,
        event=event,
        signup_context_club=club
    )
    
    # Users can only create their own availability
    if participation.user != request.user:
        raise HttpError(403, "You can only manage your own availability")
    
    try:
        window = AvailabilityWindow.objects.create(
            participation=participation,
            **data.dict()
        )
        return window
    except Exception as e:
        raise HttpError(400, f"Error creating availability window: {str(e)}")

@router.delete("/events/{event_id}/participations/{participation_id}/availability/{window_id}")
def delete_availability_window(request, event_id: UUID, participation_id: UUID, window_id: UUID):
    """Delete an availability window"""
    event = get_object_or_404(Event, id=event_id)
    club = get_club_from_context(request, event_id)
    check_race_planning_subscription(club)
    
    participation = get_object_or_404(
        EventParticipation,
        id=participation_id,
        event=event,
        signup_context_club=club
    )
    
    window = get_object_or_404(
        AvailabilityWindow,
        id=window_id,
        participation=participation
    )
    
    # Users can only delete their own availability
    if participation.user != request.user:
        raise HttpError(403, "You can only manage your own availability")
    
    window.delete()
    return {"success": True, "message": "Availability window deleted"}

# ===== TEAM FORMATION ENDPOINTS =====

@router.get("/events/{event_id}/team-formation/candidates", response=List[EventParticipationSchema])
def get_team_formation_candidates(request, event_id: UUID):
    """Get participants ready for team formation"""
    event = get_object_or_404(Event, id=event_id)
    club = get_club_from_context(request, event_id)
    check_race_planning_subscription(club)
    
    # Check if user can manage teams for this club
    club_member = get_object_or_404(ClubMember, club=club, user=request.user)
    if not club_member.can_manage_events():
        raise HttpError(403, "You don't have permission to manage team formation")
    
    candidates = EventParticipation.get_team_formation_candidates(event).filter(
        signup_context_club=club
    )
    
    return candidates

@router.get("/events/{event_id}/team-formation/recommendations", response=List[TeamFormationRecommendationSchema])
def get_team_formation_recommendations(request, event_id: UUID, team_size: int = 3, min_coverage_hours: int = 6):
    """Get AI-powered team formation recommendations"""
    event = get_object_or_404(Event, id=event_id)
    club = get_club_from_context(request, event_id)
    check_race_planning_subscription(club)
    
    # Check if user can manage teams for this club
    club_member = get_object_or_404(ClubMember, club=club, user=request.user)
    if not club_member.can_manage_events():
        raise HttpError(403, "You don't have permission to manage team formation")
    
    recommendations = AvailabilityWindow.get_team_formation_recommendations(
        event, team_size=team_size, min_coverage_hours=min_coverage_hours
    )
    
    return recommendations

# ===== RACE STRATEGY ENDPOINTS =====

@router.get("/teams/{team_id}/events/{event_id}/strategies", response=List[RaceStrategySchema])
def list_race_strategies(request, team_id: UUID, event_id: UUID):
    """List race strategies for a team in an event"""
    team = get_object_or_404(Team, id=team_id)
    event = get_object_or_404(Event, id=event_id)
    
    if team.club:
        check_race_planning_subscription(team.club)
    
    # Check permission to view team strategies
    if not check_team_management_permission(request.user, team):
        raise HttpError(403, "You don't have permission to view this team's strategies")
    
    strategies = RaceStrategy.objects.filter(
        team=team,
        event=event
    ).order_by('-is_active', '-created_at')
    
    return strategies

@router.post("/teams/{team_id}/events/{event_id}/strategies", response=RaceStrategySchema)
def create_race_strategy(request, team_id: UUID, event_id: UUID, time_slot_id: UUID, data: CreateRaceStrategySchema):
    """Create a new race strategy"""
    team = get_object_or_404(Team, id=team_id)
    event = get_object_or_404(Event, id=event_id)
    time_slot = get_object_or_404(TimeSlot, id=time_slot_id)
    
    if team.club:
        check_race_planning_subscription(team.club)
    
    # Check permission to manage team
    if not check_team_management_permission(request.user, team):
        raise HttpError(403, "You don't have permission to manage this team")
    
    strategy = RaceStrategy.objects.create(
        team=team,
        event=event,
        time_slot=time_slot,
        created_by=request.user,
        **data.dict()
    )
    
    return strategy

@router.get("/teams/{team_id}/events/{event_id}/strategies/{strategy_id}", response=RaceStrategySchema)
def get_race_strategy(request, team_id: UUID, event_id: UUID, strategy_id: UUID):
    """Get specific race strategy"""
    team = get_object_or_404(Team, id=team_id)
    
    if team.club:
        check_race_planning_subscription(team.club)
    
    strategy = get_object_or_404(
        RaceStrategy,
        id=strategy_id,
        team=team,
        event_id=event_id
    )
    
    # Check permission to view team strategies
    if not check_team_management_permission(request.user, team):
        raise HttpError(403, "You don't have permission to view this team's strategies")
    
    return strategy

@router.put("/teams/{team_id}/events/{event_id}/strategies/{strategy_id}/activate")
def activate_race_strategy(request, team_id: UUID, event_id: UUID, strategy_id: UUID):
    """Activate a race strategy (deactivate others)"""
    team = get_object_or_404(Team, id=team_id)
    
    if team.club:
        check_race_planning_subscription(team.club)
    
    strategy = get_object_or_404(
        RaceStrategy,
        id=strategy_id,
        team=team,
        event_id=event_id
    )
    
    # Check permission to manage team
    if not check_team_management_permission(request.user, team):
        raise HttpError(403, "You don't have permission to manage this team")
    
    # Deactivate other strategies for this team/event
    RaceStrategy.objects.filter(
        team=team,
        event_id=event_id
    ).update(is_active=False)
    
    # Activate this strategy
    strategy.is_active = True
    strategy.save()
    
    return {"success": True, "message": "Strategy activated"}

# ===== STINT PLAN ENDPOINTS =====

@router.get("/strategies/{strategy_id}/stints", response=List[StintPlanSchema])
def list_stint_plans(request, strategy_id: UUID):
    """List stint plans for a strategy"""
    strategy = get_object_or_404(RaceStrategy, id=strategy_id)
    
    if strategy.team.club:
        check_race_planning_subscription(strategy.team.club)
    
    # Check permission to view team strategies
    if not check_team_management_permission(request.user, strategy.team):
        raise HttpError(403, "You don't have permission to view this team's stint plans")
    
    stints = StintPlan.objects.filter(strategy=strategy).order_by('stint_number')
    return stints

@router.post("/strategies/{strategy_id}/stints", response=StintPlanSchema)
def create_stint_plan(request, strategy_id: UUID, data: CreateStintPlanSchema):
    """Create a new stint plan"""
    strategy = get_object_or_404(RaceStrategy, id=strategy_id)
    
    if strategy.team.club:
        check_race_planning_subscription(strategy.team.club)
    
    # Check permission to manage team
    if not check_team_management_permission(request.user, strategy.team):
        raise HttpError(403, "You don't have permission to manage this team")
    
    # Verify driver is part of the team
    driver = get_object_or_404(User, id=data.driver_id)
    if not strategy.team.members.filter(user=driver).exists():
        raise HttpError(400, "Driver must be a member of the team")
    
    stint = StintPlan.objects.create(
        strategy=strategy,
        driver=driver,
        **data.dict(exclude={'driver_id'})
    )
    
    return stint

@router.put("/strategies/{strategy_id}/stints/{stint_id}", response=StintPlanSchema)
def update_stint_plan(request, strategy_id: UUID, stint_id: UUID, data: CreateStintPlanSchema):
    """Update a stint plan"""
    strategy = get_object_or_404(RaceStrategy, id=strategy_id)
    
    if strategy.team.club:
        check_race_planning_subscription(strategy.team.club)
    
    stint = get_object_or_404(
        StintPlan,
        id=stint_id,
        strategy=strategy
    )
    
    # Check permission to manage team
    if not check_team_management_permission(request.user, strategy.team):
        raise HttpError(403, "You don't have permission to manage this team")
    
    # Update stint plan
    for field, value in data.dict(exclude_unset=True).items():
        if field == 'driver_id':
            driver = get_object_or_404(User, id=value)
            if not strategy.team.members.filter(user=driver).exists():
                raise HttpError(400, "Driver must be a member of the team")
            stint.driver = driver
        else:
            setattr(stint, field, value)
    
    stint.save()
    return stint

@router.delete("/strategies/{strategy_id}/stints/{stint_id}")
def delete_stint_plan(request, strategy_id: UUID, stint_id: UUID):
    """Delete a stint plan"""
    strategy = get_object_or_404(RaceStrategy, id=strategy_id)
    
    if strategy.team.club:
        check_race_planning_subscription(strategy.team.club)
    
    stint = get_object_or_404(
        StintPlan,
        id=stint_id,
        strategy=strategy
    )
    
    # Check permission to manage team
    if not check_team_management_permission(request.user, strategy.team):
        raise HttpError(403, "You don't have permission to manage this team")
    
    stint.delete()
    return {"success": True, "message": "Stint plan deleted"}

@router.put("/strategies/{strategy_id}/stints/{stint_id}/start")
def start_stint(request, strategy_id: UUID, stint_id: UUID):
    """Start a stint (mark as in progress)"""
    strategy = get_object_or_404(RaceStrategy, id=strategy_id)
    
    if strategy.team.club:
        check_race_planning_subscription(strategy.team.club)
    
    stint = get_object_or_404(
        StintPlan,
        id=stint_id,
        strategy=strategy
    )
    
    # Check permission to manage team
    if not check_team_management_permission(request.user, strategy.team):
        raise HttpError(403, "You don't have permission to manage this team")
    
    if not stint.can_start():
        raise HttpError(400, "Stint cannot be started at this time")
    
    stint.status = "in_progress"
    stint.actual_start_time = timezone.now()
    stint.save()
    
    return {"success": True, "message": "Stint started"}

@router.put("/strategies/{strategy_id}/stints/{stint_id}/complete")
def complete_stint(request, strategy_id: UUID, stint_id: UUID):
    """Complete a stint"""
    strategy = get_object_or_404(RaceStrategy, id=strategy_id)
    
    if strategy.team.club:
        check_race_planning_subscription(strategy.team.club)
    
    stint = get_object_or_404(
        StintPlan,
        id=stint_id,
        strategy=strategy
    )
    
    # Check permission to manage team
    if not check_team_management_permission(request.user, strategy.team):
        raise HttpError(403, "You don't have permission to manage this team")
    
    if stint.status != "in_progress":
        raise HttpError(400, "Only in-progress stints can be completed")
    
    stint.status = "completed"
    stint.actual_end_time = timezone.now()
    stint.save()
    
    return {"success": True, "message": "Stint completed"}

# ===== WEATHER ENDPOINTS =====

@router.get("/events/{event_id}/weather", response=EventWeatherDataSchema, auth=None)
def get_event_weather_data(request, event_id: UUID, time_slot_id: Optional[UUID] = None):
    """Get weather data and session information for an event"""
    event = get_object_or_404(Event, id=event_id)
    
    # Get weather forecasts
    weather_qs = WeatherForecast.objects.filter(event=event)
    if time_slot_id:
        weather_qs = weather_qs.filter(time_slot_id=time_slot_id)
    
    weather_forecasts = weather_qs.order_by('timestamp')
    
    # Get sessions
    sessions = EventSession.objects.filter(event=event).order_by('in_game_time')
    
    return {
        "event_id": event_id,
        "time_slot_id": time_slot_id,
        "weather_forecasts": weather_forecasts,
        "sessions": sessions,
    }
