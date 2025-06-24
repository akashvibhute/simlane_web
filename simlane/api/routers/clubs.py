from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from simlane.api.schemas.clubs import Club as ClubSchema
from simlane.api.schemas.clubs import ClubCreate
from simlane.api.schemas.clubs import ClubEvent as ClubEventSchema
from simlane.api.schemas.clubs import ClubEventCreate
from simlane.api.schemas.clubs import ClubMember as ClubMemberSchema
from simlane.api.schemas.clubs import ClubMemberUpdate
from simlane.api.schemas.clubs import ClubUpdate
# Legacy EventSignup schemas removed
from simlane.api.schemas.clubs import Team as TeamSchema
from simlane.api.schemas.clubs import TeamCreate
from simlane.teams.models import Club
from simlane.teams.models import ClubEvent
from simlane.teams.models import ClubMember
# Legacy EventSignup model removed
from simlane.teams.models import Team

router = Router()


# Helper functions for permission checking
def check_club_access(user, club, required_roles=None):
    """Check if user has access to club with required roles."""
    if required_roles is None:
        required_roles = ["OWNER", "ADMIN", "MANAGER", "MEMBER"]

    try:
        membership = ClubMember.objects.get(user=user, club=club, is_active=True)
        if membership.role not in required_roles:
            raise HttpError(403, "Insufficient permissions")
        return membership
    except ClubMember.DoesNotExist:
        raise HttpError(403, "Not a member of this club")


def check_club_admin(user, club):
    """Check if user is admin or owner of club."""
    return check_club_access(user, club, ["OWNER", "ADMIN"])


def check_club_manager(user, club):
    """Check if user has manager+ permissions."""
    return check_club_access(user, club, ["OWNER", "ADMIN", "MANAGER"])


# Club endpoints
@router.get("/", response=list[ClubSchema])
def list_clubs(request: HttpRequest):
    """List user's clubs."""
    user_clubs = Club.objects.filter(
        clubmember__user=request.auth,
        clubmember__is_active=True,
    ).distinct()

    return [ClubSchema.from_orm(club) for club in user_clubs]


@router.post("/", response=ClubSchema)
def create_club(request: HttpRequest, club_data: ClubCreate):
    """Create a new club."""
    club = Club.objects.create(
        name=club_data.name,
        description=club_data.description,
        is_public=club_data.is_public,
        max_members=club_data.max_members,
        website=club_data.website,
        discord_server=club_data.discord_server,
        timezone=club_data.timezone,
        owner=request.auth,
    )

    # Create owner membership
    ClubMember.objects.create(
        user=request.auth,
        club=club,
        role="OWNER",
        is_active=True,
    )

    return ClubSchema.from_orm(club)


@router.get("/{club_id}", response=ClubSchema)
def get_club(request: HttpRequest, club_id: int):
    """Get club details."""
    club = get_object_or_404(Club, id=club_id)
    check_club_access(request.auth, club)

    return ClubSchema.from_orm(club)


@router.patch("/{club_id}", response=ClubSchema)
def update_club(request: HttpRequest, club_id: int, updates: ClubUpdate):
    """Update club details."""
    club = get_object_or_404(Club, id=club_id)
    check_club_admin(request.auth, club)

    # Update club fields
    for field, value in updates.dict(exclude_unset=True).items():
        if hasattr(club, field):
            setattr(club, field, value)

    club.save()
    return ClubSchema.from_orm(club)


@router.delete("/{club_id}")
def delete_club(request: HttpRequest, club_id: int):
    """Delete club (owner only)."""
    club = get_object_or_404(Club, id=club_id)

    # Only owner can delete club
    if club.owner != request.auth:
        raise HttpError(403, "Only club owner can delete the club")

    club.delete()
    return {"message": "Club deleted successfully"}


# Club member endpoints
@router.get("/{club_id}/members", response=list[ClubMemberSchema])
def list_club_members(request: HttpRequest, club_id: int):
    """List club members."""
    club = get_object_or_404(Club, id=club_id)
    check_club_access(request.auth, club)

    members = ClubMember.objects.filter(club=club, is_active=True)
    return [ClubMemberSchema.from_orm(member) for member in members]


@router.patch("/{club_id}/members/{member_id}", response=ClubMemberSchema)
def update_club_member(
    request: HttpRequest,
    club_id: int,
    member_id: int,
    updates: ClubMemberUpdate,
):
    """Update club member."""
    club = get_object_or_404(Club, id=club_id)
    check_club_manager(request.auth, club)

    member = get_object_or_404(ClubMember, id=member_id, club=club)

    # Update member fields
    for field, value in updates.dict(exclude_unset=True).items():
        if hasattr(member, field):
            setattr(member, field, value)

    member.save()
    return ClubMemberSchema.from_orm(member)


@router.delete("/{club_id}/members/{member_id}")
def remove_club_member(request: HttpRequest, club_id: int, member_id: int):
    """Remove club member."""
    club = get_object_or_404(Club, id=club_id)
    check_club_manager(request.auth, club)

    member = get_object_or_404(ClubMember, id=member_id, club=club)

    # Can't remove club owner
    if member.role == "OWNER":
        raise HttpError(400, "Cannot remove club owner")

    member.delete()
    return {"message": "Member removed successfully"}


# Team endpoints
@router.get("/{club_id}/teams", response=list[TeamSchema])
def list_club_teams(request: HttpRequest, club_id: int):
    """List club teams."""
    club = get_object_or_404(Club, id=club_id)
    check_club_access(request.auth, club)

    teams = Team.objects.filter(club=club, is_active=True)
    return [TeamSchema.from_orm(team) for team in teams]


@router.post("/{club_id}/teams", response=TeamSchema)
def create_club_team(request: HttpRequest, club_id: int, team_data: TeamCreate):
    """Create a new team."""
    club = get_object_or_404(Club, id=club_id)
    check_club_manager(request.auth, club)

    team = Team.objects.create(
        name=team_data.name,
        description=team_data.description,
        club=club,
        max_members=team_data.max_members,
        color=team_data.color,
    )

    # Set captain if provided
    if team_data.captain_id:
        try:
            captain = ClubMember.objects.get(
                id=team_data.captain_id,
                club=club,
                is_active=True,
            )
            team.captain = captain.user
            team.save()
        except ClubMember.DoesNotExist:
            pass

    return TeamSchema.from_orm(team)


# Event endpoints
@router.get("/{club_id}/events", response=list[ClubEventSchema])
def list_club_events(request: HttpRequest, club_id: int):
    """List club events."""
    club = get_object_or_404(Club, id=club_id)
    check_club_access(request.auth, club)

    events = ClubEvent.objects.filter(club=club).order_by("-start_date")
    return [ClubEventSchema.from_orm(event) for event in events]


@router.post("/{club_id}/events", response=ClubEventSchema)
def create_club_event(request: HttpRequest, club_id: int, event_data: ClubEventCreate):
    """Create a new event."""
    club = get_object_or_404(Club, id=club_id)
    check_club_manager(request.auth, club)

    # TODO: Get simulator, car, track objects
    # For now, we'll need to import and get these from the sim app
    from simlane.sim.models import SimCar
    from simlane.sim.models import SimTrack
    from simlane.sim.models import Simulator

    simulator = get_object_or_404(Simulator, id=event_data.simulator_id)
    car = get_object_or_404(SimCar, id=event_data.car_id)
    track = get_object_or_404(SimTrack, id=event_data.track_id)

    event = ClubEvent.objects.create(
        name=event_data.name,
        description=event_data.description,
        club=club,
        simulator=simulator,
        car=car,
        track=track,
        start_date=event_data.start_date,
        duration_minutes=event_data.duration_minutes,
        max_signups=event_data.max_signups,
        signup_deadline=event_data.signup_deadline,
        is_team_event=event_data.is_team_event,
        max_teams=event_data.max_teams,
        points_system=event_data.points_system,
        event_format=event_data.event_format,
        weather_conditions=event_data.weather_conditions,
        track_conditions=event_data.track_conditions,
    )

    return ClubEventSchema.from_orm(event)


# Legacy event signup endpoints removed - replaced by enhanced participation system
