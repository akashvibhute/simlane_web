from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from simlane.api.schemas.events import StintAssignment as StintAssignmentSchema
from simlane.api.schemas.events import StintAssignmentCreate
from simlane.api.schemas.events import TeamAllocation as TeamAllocationSchema
from simlane.api.schemas.events import TeamAllocationCreate
from simlane.api.schemas.events import (
    TeamAllocationMember as TeamAllocationMemberSchema,
)
from simlane.api.schemas.events import TeamAllocationUpdate
from simlane.api.schemas.events import TeamEventStrategy as TeamEventStrategySchema
from simlane.api.schemas.events import TeamEventStrategyCreate
from simlane.teams.models import StintAssignment
from simlane.teams.models import TeamAllocation
from simlane.teams.models import TeamAllocationMember
from simlane.teams.models import TeamEventStrategy

router = Router()


# Team allocation endpoints
@router.get("/", response=list[TeamAllocationSchema])
def list_team_allocations(request: HttpRequest):
    """List team allocations user has access to."""
    # Get allocations for events in clubs where user is a member
    allocations = TeamAllocation.objects.filter(
        event__club__clubmember__user=request.auth,
        event__club__clubmember__is_active=True,
    ).distinct()

    return [TeamAllocationSchema.from_orm(allocation) for allocation in allocations]


@router.post("/", response=TeamAllocationSchema)
def create_team_allocation(request: HttpRequest, allocation_data: TeamAllocationCreate):
    """Create a new team allocation."""
    from simlane.teams.models import ClubEvent
    from simlane.teams.models import ClubMember

    event = get_object_or_404(ClubEvent, id=allocation_data.event_id)

    # Check if user has manager+ permissions for the club
    try:
        membership = ClubMember.objects.get(
            user=request.auth,
            club=event.club,
            is_active=True,
            role__in=["OWNER", "ADMIN", "MANAGER"],
        )
    except ClubMember.DoesNotExist:
        raise HttpError(403, "Insufficient permissions")

    allocation = TeamAllocation.objects.create(
        event=event,
        name=allocation_data.name,
        description=allocation_data.description,
        allocation_strategy=allocation_data.allocation_strategy,
        created_by=request.auth,
        team_count=allocation_data.team_count,
        members_per_team=allocation_data.members_per_team,
    )

    return TeamAllocationSchema.from_orm(allocation)


@router.get("/{allocation_id}", response=TeamAllocationSchema)
def get_team_allocation(request: HttpRequest, allocation_id: int):
    """Get team allocation details."""
    allocation = get_object_or_404(TeamAllocation, id=allocation_id)

    # Check access to the event's club
    try:
        ClubMember.objects.get(
            user=request.auth,
            club=allocation.event.club,
            is_active=True,
        )
    except ClubMember.DoesNotExist:
        raise HttpError(403, "Not a member of this club")

    return TeamAllocationSchema.from_orm(allocation)


@router.patch("/{allocation_id}", response=TeamAllocationSchema)
def update_team_allocation(
    request: HttpRequest,
    allocation_id: int,
    updates: TeamAllocationUpdate,
):
    """Update team allocation."""
    allocation = get_object_or_404(TeamAllocation, id=allocation_id)

    # Check if user is the creator or has manager+ permissions
    if allocation.created_by != request.auth:
        try:
            ClubMember.objects.get(
                user=request.auth,
                club=allocation.event.club,
                is_active=True,
                role__in=["OWNER", "ADMIN", "MANAGER"],
            )
        except ClubMember.DoesNotExist:
            raise HttpError(403, "Insufficient permissions")

    # Update allocation fields
    for field, value in updates.dict(exclude_unset=True).items():
        if hasattr(allocation, field):
            setattr(allocation, field, value)

    allocation.save()
    return TeamAllocationSchema.from_orm(allocation)


@router.post("/{allocation_id}/finalize")
def finalize_team_allocation(request: HttpRequest, allocation_id: int):
    """Finalize team allocation."""
    allocation = get_object_or_404(TeamAllocation, id=allocation_id)

    # Check permissions
    if allocation.created_by != request.auth:
        try:
            ClubMember.objects.get(
                user=request.auth,
                club=allocation.event.club,
                is_active=True,
                role__in=["OWNER", "ADMIN", "MANAGER"],
            )
        except ClubMember.DoesNotExist:
            raise HttpError(403, "Insufficient permissions")

    allocation.is_finalized = True
    allocation.save()

    return {"message": "Team allocation finalized"}


# Team allocation member endpoints
@router.get("/{allocation_id}/members", response=list[TeamAllocationMemberSchema])
def list_allocation_members(request: HttpRequest, allocation_id: int):
    """List team allocation members."""
    allocation = get_object_or_404(TeamAllocation, id=allocation_id)

    # Check access
    try:
        ClubMember.objects.get(
            user=request.auth,
            club=allocation.event.club,
            is_active=True,
        )
    except ClubMember.DoesNotExist:
        raise HttpError(403, "Not a member of this club")

    members = TeamAllocationMember.objects.filter(allocation=allocation)
    return [TeamAllocationMemberSchema.from_orm(member) for member in members]


@router.post("/{allocation_id}/auto-assign")
def auto_assign_teams(request: HttpRequest, allocation_id: int):
    """Auto-assign teams based on allocation strategy."""
    allocation = get_object_or_404(TeamAllocation, id=allocation_id)

    # Check permissions
    if allocation.created_by != request.auth:
        try:
            ClubMember.objects.get(
                user=request.auth,
                club=allocation.event.club,
                is_active=True,
                role__in=["OWNER", "ADMIN", "MANAGER"],
            )
        except ClubMember.DoesNotExist:
            raise HttpError(403, "Insufficient permissions")

    # TODO: Implement team assignment logic based on strategy
    # This would use the existing TeamAllocationService logic

    return {"message": "Teams auto-assigned successfully"}


# Strategy endpoints
@router.get("/{allocation_id}/strategies", response=list[TeamEventStrategySchema])
def list_team_strategies(request: HttpRequest, allocation_id: int):
    """List team strategies for allocation."""
    allocation = get_object_or_404(TeamAllocation, id=allocation_id)

    # Check access
    try:
        ClubMember.objects.get(
            user=request.auth,
            club=allocation.event.club,
            is_active=True,
        )
    except ClubMember.DoesNotExist:
        raise HttpError(403, "Not a member of this club")

    strategies = TeamEventStrategy.objects.filter(allocation=allocation)
    return [TeamEventStrategySchema.from_orm(strategy) for strategy in strategies]


@router.post("/{allocation_id}/strategies", response=TeamEventStrategySchema)
def create_team_strategy(
    request: HttpRequest,
    allocation_id: int,
    strategy_data: TeamEventStrategyCreate,
):
    """Create a team strategy."""
    allocation = get_object_or_404(TeamAllocation, id=allocation_id)

    # Check if user is member of the team or has manager+ permissions
    try:
        member = TeamAllocationMember.objects.get(
            allocation=allocation,
            user=request.auth,
            team_number=strategy_data.team_number,
        )
    except TeamAllocationMember.DoesNotExist:
        # Check if user has manager+ permissions
        try:
            ClubMember.objects.get(
                user=request.auth,
                club=allocation.event.club,
                is_active=True,
                role__in=["OWNER", "ADMIN", "MANAGER"],
            )
        except ClubMember.DoesNotExist:
            raise HttpError(403, "Not a member of this team")

    strategy = TeamEventStrategy.objects.create(
        allocation=allocation,
        team_number=strategy_data.team_number,
        strategy_name=strategy_data.strategy_name,
        total_stint_time=strategy_data.total_stint_time,
        pit_stop_count=strategy_data.pit_stop_count,
        fuel_strategy=strategy_data.fuel_strategy,
        tire_strategy=strategy_data.tire_strategy,
        weather_considerations=strategy_data.weather_considerations,
        notes=strategy_data.notes,
    )

    return TeamEventStrategySchema.from_orm(strategy)


# Stint assignment endpoints
@router.get(
    "/{allocation_id}/strategies/{strategy_id}/stints",
    response=list[StintAssignmentSchema],
)
def list_stint_assignments(request: HttpRequest, allocation_id: int, strategy_id: int):
    """List stint assignments for a strategy."""
    allocation = get_object_or_404(TeamAllocation, id=allocation_id)
    strategy = get_object_or_404(
        TeamEventStrategy,
        id=strategy_id,
        allocation=allocation,
    )

    # Check access
    try:
        ClubMember.objects.get(
            user=request.auth,
            club=allocation.event.club,
            is_active=True,
        )
    except ClubMember.DoesNotExist:
        raise HttpError(403, "Not a member of this club")

    stints = StintAssignment.objects.filter(strategy=strategy).order_by("stint_number")
    return [StintAssignmentSchema.from_orm(stint) for stint in stints]


@router.post(
    "/{allocation_id}/strategies/{strategy_id}/stints",
    response=StintAssignmentSchema,
)
def create_stint_assignment(
    request: HttpRequest,
    allocation_id: int,
    strategy_id: int,
    stint_data: StintAssignmentCreate,
):
    """Create a stint assignment."""
    allocation = get_object_or_404(TeamAllocation, id=allocation_id)
    strategy = get_object_or_404(
        TeamEventStrategy,
        id=strategy_id,
        allocation=allocation,
    )

    # Check if user is member of the team
    try:
        TeamAllocationMember.objects.get(
            allocation=allocation,
            user=request.auth,
            team_number=strategy.team_number,
        )
    except TeamAllocationMember.DoesNotExist:
        raise HttpError(403, "Not a member of this team")

    # Get the assigned user
    assigned_user = get_object_or_404(User, id=stint_data.user_id)

    # Verify assigned user is on the team
    try:
        TeamAllocationMember.objects.get(
            allocation=allocation,
            user=assigned_user,
            team_number=strategy.team_number,
        )
    except TeamAllocationMember.DoesNotExist:
        raise HttpError(400, "Assigned user is not on this team")

    stint = StintAssignment.objects.create(
        strategy=strategy,
        user=assigned_user,
        stint_number=stint_data.stint_number,
        start_time=stint_data.start_time,
        duration_minutes=stint_data.duration_minutes,
        expected_lap_time=stint_data.expected_lap_time,
        fuel_load=stint_data.fuel_load,
        tire_compound=stint_data.tire_compound,
        notes=stint_data.notes,
    )

    return StintAssignmentSchema.from_orm(stint)
