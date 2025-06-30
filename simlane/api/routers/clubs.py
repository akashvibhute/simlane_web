from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja import Router
from ninja.errors import HttpError

from simlane.api.schemas.clubs import Club as ClubSchema
from simlane.api.schemas.clubs import ClubCreate
from simlane.api.schemas.clubs import ClubMember as ClubMemberSchema
from simlane.api.schemas.clubs import ClubMemberUpdate
from simlane.api.schemas.clubs import ClubUpdate
from simlane.api.schemas.clubs import Team as TeamSchema
from simlane.api.schemas.clubs import TeamCreate
from simlane.teams.models import Club
from simlane.teams.models import ClubMember
from simlane.teams.models import Team
from simlane.billing.services import SubscriptionService, SubscriptionServiceError
from simlane.billing.models import SubscriptionPlan

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


def check_subscription_limits(club, action="general"):
    """Check subscription limits for various actions."""
    try:
        status = SubscriptionService.check_subscription_status(club)
        
        if action == "add_member":
            can_add, reason = SubscriptionService.can_add_member(club)
            if not can_add:
                raise HttpError(402, {
                    "error": "subscription_limit_exceeded",
                    "message": reason,
                    "current_plan": status["plan_name"],
                    "seats_used": status["seats_used"],
                    "max_members": status["max_members"],
                    "upgrade_required": True
                })
        
        elif action == "race_planning":
            can_use, reason = SubscriptionService.can_use_feature(club, "race_planning")
            if not can_use:
                raise HttpError(402, {
                    "error": "feature_not_available",
                    "message": reason,
                    "current_plan": status["plan_name"],
                    "required_feature": "race_planning",
                    "upgrade_required": True
                })
        
        return status
        
    except SubscriptionServiceError as e:
        raise HttpError(402, {
            "error": "subscription_error",
            "message": str(e),
            "upgrade_required": True
        })


def add_subscription_info_to_response(club_data, club):
    """Add subscription information to club API response."""
    try:
        status = SubscriptionService.check_subscription_status(club)
        club_data.update({
            "subscription": {
                "plan_name": status["plan_name"],
                "status": status["status"],
                "max_members": status["max_members"],
                "seats_used": status["seats_used"],
                "seats_available": status["seats_available"],
                "can_add_members": status["can_add_members"],
                "has_race_planning": status["has_race_planning"],
                "features": status["features"],
                "is_trial": status["is_trial"],
                "trial_ends_at": status["trial_ends_at"].isoformat() if status["trial_ends_at"] else None,
                "current_period_end": status["current_period_end"].isoformat() if status["current_period_end"] else None,
            }
        })
    except Exception:
        # Fallback to basic info if subscription service fails
        club_data.update({
            "subscription": {
                "plan_name": "Free",
                "status": "active",
                "max_members": 5,
                "seats_used": ClubMember.objects.filter(club=club, is_active=True).count(),
                "seats_available": max(0, 5 - ClubMember.objects.filter(club=club, is_active=True).count()),
                "can_add_members": ClubMember.objects.filter(club=club, is_active=True).count() < 5,
                "has_race_planning": False,
                "features": ["basic_club_management"],
                "is_trial": False,
                "trial_ends_at": None,
                "current_period_end": None,
            }
        })
    
    return club_data


# Club endpoints
@router.get("/", response=list[ClubSchema])
def list_clubs(request: HttpRequest):
    """List user's clubs with subscription information."""
    user_clubs = Club.objects.filter(
        clubmember__user=request.auth,
        clubmember__is_active=True,
    ).distinct()

    clubs_with_subscription = []
    for club in user_clubs:
        club_data = ClubSchema.from_orm(club).dict()
        club_data = add_subscription_info_to_response(club_data, club)
        clubs_with_subscription.append(club_data)

    return clubs_with_subscription


@router.post("/", response=ClubSchema)
def create_club(request: HttpRequest, club_data: ClubCreate):
    """Create a new club with Free plan subscription."""
    from django.db import transaction
    
    try:
        with transaction.atomic():
            # Create club
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

            # Assign Free plan subscription
            try:
                free_plan = SubscriptionPlan.get_default_plan()
                if free_plan:
                    from simlane.billing.models import ClubSubscription
                    ClubSubscription.objects.create(
                        club=club,
                        plan=free_plan,
                        status='active',
                        seats_used=1,  # Owner counts as 1 seat
                    )
            except Exception as e:
                # Log error but don't fail club creation
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Failed to create subscription for new club {club.id}: {e}")

            # Return club data with subscription info
            club_data = ClubSchema.from_orm(club).dict()
            club_data = add_subscription_info_to_response(club_data, club)
            return club_data
            
    except Exception as e:
        raise HttpError(400, f"Failed to create club: {str(e)}")


@router.get("/{club_id}", response=ClubSchema)
def get_club(request: HttpRequest, club_id: int):
    """Get club details with subscription information."""
    club = get_object_or_404(Club, id=club_id)
    check_club_access(request.auth, club)

    club_data = ClubSchema.from_orm(club).dict()
    club_data = add_subscription_info_to_response(club_data, club)
    return club_data


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
    
    # Return club data with subscription info
    club_data = ClubSchema.from_orm(club).dict()
    club_data = add_subscription_info_to_response(club_data, club)
    return club_data


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
    """List club members with subscription context."""
    club = get_object_or_404(Club, id=club_id)
    check_club_access(request.auth, club)

    # Check subscription status for context
    subscription_status = check_subscription_limits(club)

    members = ClubMember.objects.filter(club=club, is_active=True)
    members_data = []
    
    for member in members:
        member_data = ClubMemberSchema.from_orm(member).dict()
        # Add subscription context to response
        member_data["subscription_context"] = {
            "can_add_more_members": subscription_status["can_add_members"],
            "seats_used": subscription_status["seats_used"],
            "max_members": subscription_status["max_members"],
        }
        members_data.append(member_data)
    
    return members_data


@router.patch("/{club_id}/members/{member_id}", response=ClubMemberSchema)
def update_club_member(
    request: HttpRequest,
    club_id: int,
    member_id: int,
    updates: ClubMemberUpdate,
):
    """Update club member with subscription validation."""
    club = get_object_or_404(Club, id=club_id)
    check_club_manager(request.auth, club)

    member = get_object_or_404(ClubMember, id=member_id, club=club)

    # Check if reactivating a member would exceed limits
    if hasattr(updates, 'is_active') and updates.is_active and not member.is_active:
        check_subscription_limits(club, "add_member")

    # Update member fields
    for field, value in updates.dict(exclude_unset=True).items():
        if hasattr(member, field):
            setattr(member, field, value)

    member.save()
    
    # Update subscription seat count
    try:
        subscription = SubscriptionService.get_club_subscription(club)
        if subscription:
            subscription.update_seats_used()
    except Exception:
        pass  # Don't fail the update if subscription sync fails
    
    return ClubMemberSchema.from_orm(member)


@router.delete("/{club_id}/members/{member_id}")
def remove_club_member(request: HttpRequest, club_id: int, member_id: int):
    """Remove club member and update subscription seat count."""
    club = get_object_or_404(Club, id=club_id)
    check_club_manager(request.auth, club)

    member = get_object_or_404(ClubMember, id=member_id, club=club)

    # Can't remove club owner
    if member.role == "OWNER":
        raise HttpError(400, "Cannot remove club owner")

    member.delete()
    
    # Update subscription seat count
    try:
        subscription = SubscriptionService.get_club_subscription(club)
        if subscription:
            subscription.update_seats_used()
    except Exception:
        pass  # Don't fail the removal if subscription sync fails
    
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
    """Create a new team with subscription validation."""
    club = get_object_or_404(Club, id=club_id)
    check_club_manager(request.auth, club)

    # Check if race planning features are available for team creation
    # (teams might be considered part of race planning functionality)
    subscription_status = check_subscription_limits(club)
    
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


# Add new subscription management endpoints
@router.get("/{club_id}/subscription")
def get_club_subscription_status(request: HttpRequest, club_id: int):
    """Get detailed subscription status for a club."""
    club = get_object_or_404(Club, id=club_id)
    check_club_access(request.auth, club)
    
    try:
        status = SubscriptionService.check_subscription_status(club)
        
        # Add upgrade recommendations if needed
        if not status["can_add_members"] or not status["has_race_planning"]:
            recommendations = SubscriptionService.get_upgrade_recommendations(club)
            status["upgrade_recommendations"] = [
                {
                    "plan_name": rec["plan"].name,
                    "monthly_price": float(rec["plan"].monthly_price),
                    "max_members": rec["plan"].max_members,
                    "benefits": rec["benefits"],
                    "stripe_price_id": rec["plan"].stripe_price_id,
                }
                for rec in recommendations[:3]  # Limit to top 3 recommendations
            ]
        
        return status
        
    except Exception as e:
        raise HttpError(500, f"Failed to get subscription status: {str(e)}")


@router.post("/{club_id}/subscription/validate-member-addition")
def validate_member_addition(request: HttpRequest, club_id: int):
    """Validate if club can add new members before invitation."""
    club = get_object_or_404(Club, id=club_id)
    check_club_manager(request.auth, club)
    
    try:
        can_add, reason = SubscriptionService.can_add_member(club)
        
        if not can_add:
            return {
                "can_add": False,
                "reason": reason,
                "subscription_status": SubscriptionService.check_subscription_status(club),
                "upgrade_required": True
            }
        
        return {
            "can_add": True,
            "reason": "Member can be added",
            "subscription_status": SubscriptionService.check_subscription_status(club),
            "upgrade_required": False
        }
        
    except Exception as e:
        raise HttpError(500, f"Failed to validate member addition: {str(e)}")


# Event endpoints removed - using sim.Event.organizing_club instead
# Clubs can organize events by setting organizing_club field on sim.Event


# Legacy event signup endpoints removed - replaced by enhanced participation system
