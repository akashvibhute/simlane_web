from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from .decorators import club_admin_required
from .decorators import club_manager_required
from .decorators import club_member_required
from .forms import ClubCreateForm
from .forms import ClubEventSignupBulkCreateForm
from .forms import ClubEventSignupSheetForm
from .forms import ClubInvitationForm
from .forms import ClubUpdateForm
from .models import Club
from .models import ClubEventSignupSheet
from .models import ClubInvitation
from .models import ClubMember
from .models import ClubRole
from .models import EventParticipation
from .models import Team
from .models import TeamMember

# Import billing decorators for subscription enforcement
from simlane.billing.decorators import race_planning_required
from simlane.billing.decorators import member_limit_enforced
from simlane.billing.decorators import subscription_required
from simlane.billing.decorators import check_member_limit

User = get_user_model()


@login_required
def clubs_dashboard(request):
    """Main clubs dashboard showing user's clubs and teams."""
    # Get user's club memberships
    user_clubs = (
        ClubMember.objects.filter(user=request.user)
        .select_related("club")
        .order_by("club__name")
    )

    # Get user's teams through TeamMember relationships
    team_memberships = TeamMember.objects.filter(user=request.user).select_related(
        "team",
        "team__club",
    )

    user_teams = []
    for team_member in team_memberships:
        # Get club membership role if team is in a club
        club_role = None
        if team_member.team.club:
            try:
                club_member = ClubMember.objects.get(
                    user=request.user,
                    club=team_member.team.club,
                )
                club_role = club_member.role
            except ClubMember.DoesNotExist:
                pass

        user_teams.append(
            {
                "team": team_member.team,
                "club": team_member.team.club,
                "role": club_role,
                "team_role": team_member.role,
            },
        )

    # Get all public clubs for discovery
    all_clubs = Club.objects.filter(is_active=True).order_by("name")

    context = {
        "user_clubs": user_clubs,
        "user_teams": user_teams,
        "total_clubs": user_clubs.count(),
        "total_teams": len(user_teams),
        "all_clubs": all_clubs,
        "show_club_discovery": user_clubs.count() == 0,
    }

    return render(request, "teams/clubs_dashboard.html", context)


@login_required
def browse_clubs(request):
    """Browse all available clubs for joining."""
    # Get all public and active clubs with annotations for efficiency
    all_clubs = (
        Club.objects.filter(is_active=True)
        .annotate(
            member_count=models.Count("members", distinct=True),
            team_count=models.Count(
                "teams", filter=models.Q(teams__is_active=True), distinct=True
            ),
        )
        .order_by("name")
    )

    # Get user's current club memberships to exclude from browsing
    user_club_ids = ClubMember.objects.filter(user=request.user).values_list(
        "club_id", flat=True
    )
    available_clubs = all_clubs.exclude(id__in=user_club_ids)

    context = {
        "available_clubs": available_clubs,
        "total_available_clubs": available_clubs.count(),
    }

    return render(request, "teams/browse_clubs.html", context)


@login_required
def request_join_club(request, club_slug):
    """Request to join a club."""
    try:
        club = Club.objects.get(slug=club_slug, is_active=True)
    except Club.DoesNotExist:
        messages.error(request, "Club not found or is not active.")
        return redirect("teams:browse_clubs")

    # Check if user is already a member
    if ClubMember.objects.filter(user=request.user, club=club).exists():
        messages.info(request, f"You are already a member of {club.name}.")
        return redirect("teams:club_dashboard", club_slug=club.slug)

    # Check if there's already a pending invitation
    existing_invitation = ClubInvitation.objects.filter(
        club=club,
        email=request.user.email,
        accepted_at__isnull=True,
        declined_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).first()

    if existing_invitation:
        messages.info(
            request, f"You already have a pending invitation to join {club.name}."
        )
        return redirect("teams:browse_clubs")

    context = {
        "club": club,
    }

    if request.method == "POST":
        # For now, show a message that request was noted
        # In a full implementation, this could notify club admins
        messages.success(
            request,
            f"Your interest in joining {club.name} has been noted. "
            f"A club administrator may contact you.",
        )
        return redirect("teams:browse_clubs")

    return render(request, "teams/request_join_club.html", context)


@login_required
def club_dashboard(request, club_slug):
    """Individual club dashboard - defaults to overview section."""
    return club_dashboard_section(request, club_slug, "overview")


@login_required
def club_dashboard_section(request, club_slug, section="overview"):
    """Club dashboard section view with HTMX support."""
    # Get the club by slug
    try:
        club = Club.objects.get(slug=club_slug)
    except Club.DoesNotExist:
        raise Http404("Club not found")

    # Check if user is a member or if club is public
    user_role = None
    try:
        club_member = ClubMember.objects.get(club=club, user=request.user)
        user_role = club_member.role
    except ClubMember.DoesNotExist:
        if not club.is_public:
            return HttpResponseForbidden(
                "This club is private. You must be a member to view it."
            )

    # Get subscription information for the club
    subscription_info = None
    member_usage_info = None
    subscription_features = []
    
    try:
        from simlane.billing.models import ClubSubscription
        subscription = ClubSubscription.objects.select_related('plan').get(
            club=club, 
            status__in=['active', 'trialing']
        )
        subscription_info = {
            'plan': subscription.plan,
            'status': subscription.status,
            'current_period_end': subscription.current_period_end,
            'seats_used': subscription.seats_used,
        }
        subscription_features = subscription.get_available_features()
        
        # Get member usage information
        current_members = club.members.count()
        max_members = subscription.plan.max_members
        member_usage_info = {
            'current': current_members,
            'limit': max_members if max_members and max_members > 0 else 'Unlimited',
            'percentage': subscription.get_member_usage_percentage() if max_members and max_members > 0 else 0,
            'can_add_members': max_members is None or max_members < 0 or current_members < max_members,
            'approaching_limit': max_members and max_members > 0 and current_members >= (max_members * 0.8),
        }
    except (ImportError, ClubSubscription.DoesNotExist):
        # Billing not available or no subscription - use free plan defaults
        current_members = club.members.count()
        member_usage_info = {
            'current': current_members,
            'limit': 5,  # Free plan default
            'percentage': (current_members / 5) * 100,
            'can_add_members': current_members < 5,
            'approaching_limit': current_members >= 4,
        }

    # Get user's other clubs for navigation
    user_clubs = ClubMember.objects.filter(user=request.user).select_related("club")

    # Get club members
    club_members = (
        ClubMember.objects.filter(club=club)
        .select_related("user")
        .order_by("-role", "user__username")
    )

    # Get teams in this club
    club_teams = Team.objects.filter(club=club, is_active=True).order_by("name")

    # Get user's teams in this club
    user_teams_in_club = []
    if request.user.is_authenticated:
        user_team_memberships = TeamMember.objects.filter(
            user=request.user,
            team__club=club,
        ).select_related("team")
        user_teams_in_club = [tm.team for tm in user_team_memberships]

    # Get recent event participations for this club's teams
    recent_entries = (
        EventParticipation.objects.filter(
            team__club=club,
            status__in=["confirmed", "participated"],
        )
        .select_related("event", "user", "assigned_car", "team")
        .order_by("-created_at")[:10]
    )

    # Get events organized by this club (using Event.organizing_club)
    from simlane.sim.models import Event

    club_events = (
        Event.objects.filter(organizing_club=club)
        .select_related(
            "sim_layout",
            "sim_layout__sim_track",
            "sim_layout__sim_track__track_model",
        )
        .prefetch_related("participations")
        .order_by("-created_at")
    )

    # Get recent signup sheets for the overview
    recent_signup_sheets = []
    if request.user.is_authenticated:
        try:
            club_member = ClubMember.objects.get(club=club, user=request.user)
            can_manage_events = club_member.can_manage_events()
            recent_signup_sheets = club.event_signup_sheets.select_related(
                "event", "created_by"
            ).order_by("-created_at")[:5]
        except ClubMember.DoesNotExist:
            can_manage_events = False
    else:
        can_manage_events = False

    # === Events section specific context ===
    upcoming_signup_sheets = []
    past_signup_sheets = []
    events_tab = request.GET.get("tab", "upcoming")
    if section == "events":
        signup_sheets_all = (
            club.event_signup_sheets.select_related("event")
            .annotate(
                signup_count_annotated=models.Count(
                    "event__participations",
                    filter=models.Q(
                        event__participations__signup_context_club=club,
                    ),
                ),
            )
            .order_by("-created_at")
        )
        now = timezone.now()
        for ss in signup_sheets_all:
            if ss.is_open or ss.signup_closes > now:
                upcoming_signup_sheets.append(ss)
            else:
                past_signup_sheets.append(ss)

        # For HTMX tab swap: if only tab content requested, return full events section
        if request.headers.get("HX-Request") and request.GET.get("tab"):
            # Re-render the entire events section so tabs update correctly
            return render(
                request,
                "teams/club_dashboard_events_section.html",
                {
                    "club": club,
                    "events_tab": events_tab,
                    "upcoming_signup_sheets": upcoming_signup_sheets,
                    "past_signup_sheets": past_signup_sheets,
                    "can_manage_events": can_manage_events,
                },
            )

    context = {
        "club": club,
        "user_role": user_role,
        "user_teams_in_club": user_teams_in_club,
        "club_teams": club_teams,
        "club_members": club_members,
        "recent_entries": recent_entries,
        "club_events": club_events,
        "recent_signup_sheets": recent_signup_sheets,
        "can_manage_events": can_manage_events,
        "active_section": section,
        "total_members": club_members.count(),
        "total_teams": club_teams.count(),
        "total_entries": EventParticipation.objects.filter(
            team__club=club,
            status__in=["confirmed", "participated"],
        ).count(),
        "user_clubs": user_clubs,
        "is_public_view": user_role is None,
        "upcoming_signup_sheets": upcoming_signup_sheets,
        "past_signup_sheets": past_signup_sheets,
        "events_tab": events_tab,
        # Add subscription context
        "subscription_info": subscription_info,
        "member_usage_info": member_usage_info,
        "subscription_features": subscription_features,
        "race_planning_available": 'race_planning' in subscription_features,
    }

    # HTMX requests return partial content
    if request.headers.get("HX-Request"):
        return render(request, "teams/club_dashboard_content_partial.html", context)

    # Regular requests return full page
    return render(request, "teams/club_dashboard.html", context)


# NEW VIEWS FOR CLUB MANAGEMENT

# Club Management Views


@login_required
def club_create(request):
    """Create a new club - any user can create clubs"""
    if request.method == "POST":
        form = ClubCreateForm(request.POST, request.FILES)
        if form.is_valid():
            with transaction.atomic():
                # Create club with the user as creator
                club = form.save(commit=False)
                club.created_by = request.user
                club.save()

                # Create ClubMember instance making the creator an admin
                ClubMember.objects.create(
                    user=request.user,
                    club=club,
                    role=ClubRole.ADMIN,
                )

                # Assign free subscription plan to new club
                try:
                    from simlane.billing.services import SubscriptionService
                    subscription_service = SubscriptionService()
                    subscription_service.assign_free_plan(club)
                except ImportError:
                    # Billing system not available - continue without subscription
                    pass

                messages.success(request, f"Club '{club.name}' created successfully!")
                return redirect("teams:club_dashboard", club_slug=club.slug)
    else:
        form = ClubCreateForm()

    context = {
        "form": form,
        "title": "Create New Club",
    }

    return render(request, "teams/club_create.html", context)


@club_admin_required
def club_update(request, club_slug):
    """Update club details - admin only"""
    club = request.club  # Set by decorator

    if request.method == "POST":
        form = ClubUpdateForm(request.POST, request.FILES, instance=club)
        if form.is_valid():
            form.save()
            messages.success(request, "Club details updated successfully!")

            if request.headers.get("HX-Request"):
                return HttpResponse(status=204, headers={"HX-Refresh": "true"})
            return redirect("teams:club_update", club_slug=club.slug)
    else:
        form = ClubUpdateForm(instance=club)

    context = {
        "form": form,
        "club": club,
        "title": f"Update {club.name}",
    }

    return render(request, "teams/club_update.html", context)


@club_member_required
def club_members(request, club_slug):
    """List and manage club members"""
    club = request.club
    members = club.members.select_related("user").order_by("-role", "user__username")

    # Get pending invitations
    pending_invitations = club.invitations.filter(
        accepted_at__isnull=True,
        declined_at__isnull=True,
        expires_at__gt=timezone.now(),
    ).order_by("-created_at")

    context = {
        "club": club,
        "members": members,
        "pending_invitations": pending_invitations,
        "user_role": request.club_member.role,
        "can_manage": request.club_member.can_manage_club(),
    }

    if request.headers.get("HX-Request"):
        return render(request, "teams/club_members_partial.html", context)

    return render(request, "teams/club_members.html", context)


@club_member_required
def club_members_partial(request, club_slug):
    """HTMX partial for club members list"""
    return club_members(request, club_slug)


@member_limit_enforced
def club_invite_member(request, club_slug):
    """Send invitations to new members"""
    club = request.club

    # Check member limits before showing form
    can_add, limit_message, current_count, max_count = check_member_limit(club, 1)
    
    if not can_add:
        messages.error(request, limit_message)
        if request.headers.get("HX-Request"):
            return redirect("teams:club_members", club_slug=club.slug)
        return redirect("teams:club_members", club_slug=club.slug)

    if request.method == "POST":
        form = ClubInvitationForm(request.POST, club=club, inviter=request.user)
        if form.is_valid():
            try:
                invitation = form.save()
                # TODO: Implement ClubInvitationService.send_invitation
                # For now, just show success message
                messages.success(request, f"Invitation sent to {invitation.email}")

                if request.headers.get("HX-Request"):
                    # Return updated member list for HTMX
                    return redirect("teams:club_members", club_slug=club.slug)

                return redirect("teams:club_members", club_slug=club.slug)
            except (OSError, ValueError) as e:
                messages.error(request, f"Failed to send invitation: {e!s}")
    else:
        form = ClubInvitationForm(club=club, inviter=request.user)

    context = {
        "form": form,
        "club": club,
        "title": f"Invite Member to {club.name}",
        "member_limit_info": getattr(request, 'member_limit_info', None),
    }

    if request.headers.get("HX-Request"):
        return render(request, "teams/club_invite_member_modal.html", context)

    return render(request, "teams/club_invite_member.html", context)


@race_planning_required
def club_event_signup_create(request, club_slug):
    """Create an event signup sheet for the club - requires race planning subscription"""
    club = request.club

    if request.method == "POST":
        form = ClubEventSignupSheetForm(
            request.POST,
            club=club,
            user=request.user,
        )
        if form.is_valid():
            signup_sheet = form.save()
            messages.success(
                request,
                f"Signup sheet '{signup_sheet.title}' created successfully! "
                f"{'It is now open for signups.' if signup_sheet.is_open else 'It will open at the scheduled time.'}",
            )
            return redirect(
                "teams:club_dashboard_section", club_slug=club.slug, section="events"
            )
    else:
        form = ClubEventSignupSheetForm(club=club, user=request.user)

    # Determine selected event for redisplay (if any)
    selected_event = None
    try:
        event_id = form.data.get("event") if hasattr(form, "data") else None
        if event_id:
            from simlane.sim.models import Event

            selected_event = (
                Event.objects.select_related("simulator")
                .prefetch_related("time_slots")
                .filter(id=event_id)
                .first()
            )
    except Exception:
        selected_event = None

    # Import here to avoid circular import
    from simlane.sim.views import get_active_simulators

    context = {
        "form": form,
        "club": club,
        "title": f"Create Event Signup - {club.name}",
        "simulators": get_active_simulators(),
        "selected_event": selected_event,
    }

    if request.headers.get("HX-Request"):
        return render(request, "teams/club_event_signup_create_modal.html", context)

    return render(request, "teams/club_event_signup_create.html", context)


@race_planning_required
def club_event_signup_bulk_create(request, club_slug):
    """Create multiple event signup sheets at once - requires race planning subscription"""
    club = request.club

    if request.method == "POST":
        form = ClubEventSignupBulkCreateForm(
            request.POST,
            club=club,
            user=request.user,
        )
        if form.is_valid():
            created_sheets = form.create_signup_sheets()

            # Success message with count
            count = len(created_sheets)
            if count == 1:
                messages.success(
                    request,
                    "Created 1 signup sheet successfully!",
                )
            else:
                messages.success(
                    request,
                    f"Created {count} signup sheets successfully!",
                )

            # Show breakdown of what was created
            for sheet in created_sheets:
                messages.info(
                    request,
                    (
                        f"📝 {sheet.title} - "
                        f"{'Open now' if sheet.is_open else 'Opens ' + sheet.signup_opens.strftime('%b %d, %Y')}"
                    ),
                )

            return redirect("teams:club_event_signups", club_slug=club.slug)
    else:
        form = ClubEventSignupBulkCreateForm(club=club, user=request.user)

    context = {
        "form": form,
        "club": club,
        "title": f"Bulk Create Event Signups - {club.name}",
    }

    if request.headers.get("HX-Request"):
        return render(
            request, "teams/club_event_signup_bulk_create_modal.html", context
        )

    return render(request, "teams/club_event_signup_bulk_create.html", context)


@club_member_required
def club_event_signups(request, club_slug):
    """View all event signup sheets for the club"""
    club = request.club

    # Get all signup sheets for this club
    signup_sheets = (
        club.event_signup_sheets.select_related("event", "created_by")
        .annotate(
            signup_count_annotated=models.Count(
                "event__participations",
                filter=models.Q(
                    event__participations__signup_context_club=club,
                    event__participations__status__in=[
                        "signed_up",
                        "team_formation",
                        "team_assigned",
                        "entered",
                        "confirmed",
                    ],
                ),
            ),
        )
        .order_by("-created_at")
    )

    # Separate open and closed signups
    open_signups = []
    closed_signups = []

    for sheet in signup_sheets:
        if sheet.is_open:
            open_signups.append(sheet)
        else:
            closed_signups.append(sheet)

    context = {
        "club": club,
        "open_signups": open_signups,
        "closed_signups": closed_signups,
        "user_role": request.club_member.role
        if hasattr(request, "club_member")
        else None,
        "can_manage": request.club_member.can_manage_events()
        if hasattr(request, "club_member")
        else False,
    }

    if request.headers.get("HX-Request"):
        return render(request, "teams/club_event_signups_partial.html", context)

    return render(request, "teams/club_event_signups.html", context)


def club_invitation_accept(request, token):
    """Process invitation acceptance - no login required initially"""
    try:
        invitation = ClubInvitation.objects.get(token=token)

        if not request.user.is_authenticated:
            # Store token in session and redirect to login
            request.session["invitation_token"] = token
            messages.info(request, "Please log in or sign up to accept the invitation.")
            return redirect(f"{reverse('account_login')}?next={request.path}")

        # Accept the invitation
        if invitation.is_expired():
            messages.error(request, "This invitation has expired.")
            return redirect("teams:clubs_dashboard")

        # Check member limits before accepting
        can_add, limit_message, current_count, max_count = check_member_limit(invitation.club, 1)
        
        if not can_add:
            messages.error(
                request, 
                f"Cannot accept invitation: {limit_message}. "
                "Please contact the club administrator about upgrading their subscription."
            )
            return redirect("teams:clubs_dashboard")

        club_member = invitation.accept(request.user)
        messages.success(request, f"Welcome to {invitation.club.name}!")

        # Clear token from session if exists
        request.session.pop("invitation_token", None)

        return redirect("teams:club_dashboard", club_slug=invitation.club.slug)

    except ClubInvitation.DoesNotExist:
        messages.error(request, "Invalid invitation link.")
        return redirect("teams:clubs_dashboard")
    except ValueError as e:
        messages.error(request, str(e))
        return redirect("teams:clubs_dashboard")


def club_invitation_decline(request, token):
    """Process invitation decline"""
    try:
        invitation = ClubInvitation.objects.get(token=token)

        if invitation.is_expired():
            messages.error(request, "This invitation has expired.")
            return redirect("teams:clubs_dashboard")

        invitation.decline()
        messages.info(
            request, f"You have declined the invitation to join {invitation.club.name}."
        )

        return redirect("teams:clubs_dashboard")

    except ClubInvitation.DoesNotExist:
        messages.error(request, "Invalid invitation link.")
        return redirect("teams:clubs_dashboard")


# Legacy views - redirect to main dashboard
@login_required
def stint_plan_update_legacy(request, allocation_id):
    """Legacy view - replaced by enhanced team formation system"""
    messages.warning(
        request, "Stint planning has been moved to the enhanced team formation system"
    )
    return redirect("teams:clubs_dashboard")


@login_required
def stint_plan_export_legacy(request, allocation_id):
    """Legacy view - replaced by enhanced team formation system"""
    messages.warning(
        request,
        "Export functionality has been moved to the enhanced team formation system",
    )
    return redirect("teams:clubs_dashboard")


@login_required
def stint_plan_partial_legacy(request, allocation_id):
    """Legacy view - replaced by enhanced team formation system"""
    messages.warning(
        request, "Stint planning has been moved to the enhanced team formation system"
    )
    return redirect("teams:clubs_dashboard")


# === RACE PLANNING AND TEAM FORMATION VIEWS ===
# These views handle advanced race planning functionality that requires subscription

@race_planning_required
def event_team_formation(request, club_slug, sheet_id):
    """Form teams for an event - requires race planning subscription."""
    club = request.club
    signup_sheet = get_object_or_404(ClubEventSignupSheet, id=sheet_id, club=club)
    
    # Get all signups ready for team formation
    signups = EventParticipation.get_team_formation_candidates(signup_sheet.event)
    
    # Get team formation recommendations if we have enough participants
    recommendations = []
    if signups.count() >= signup_sheet.min_drivers_per_team:
        from simlane.teams.models import AvailabilityWindow
        recommendations = AvailabilityWindow.get_team_formation_recommendations(
            signup_sheet.event,
            team_size=signup_sheet.target_team_size
        )
    
    context = {
        "club": club,
        "signup_sheet": signup_sheet,
        "signups": signups,
        "recommendations": recommendations,
        "title": f"Team Formation - {signup_sheet.title}",
    }
    
    return render(request, "teams/event_team_formation.html", context)


@race_planning_required
def event_race_strategy_create(request, club_slug, team_id, event_id):
    """Create race strategy for a team - requires race planning subscription."""
    club = request.club
    team = get_object_or_404(Team, id=team_id, club=club)
    
    from simlane.sim.models import Event
    event = get_object_or_404(Event, id=event_id)
    
    # Check if user can manage this team
    if not team.can_user_manage(request.user):
        return HttpResponseForbidden("You don't have permission to manage this team's strategy")
    
    if request.method == "POST":
        # Handle race strategy creation
        # This would involve forms for RaceStrategy and StintPlan models
        messages.success(request, "Race strategy created successfully!")
        return redirect("teams:club_dashboard", club_slug=club.slug)
    
    context = {
        "club": club,
        "team": team,
        "event": event,
        "title": f"Create Race Strategy - {team.name}",
    }
    
    return render(request, "teams/race_strategy_create.html", context)


@race_planning_required
def stint_plan_management(request, club_slug, strategy_id):
    """Manage stint plans for a race strategy - requires race planning subscription."""
    club = request.club
    
    from simlane.teams.models import RaceStrategy
    strategy = get_object_or_404(RaceStrategy, id=strategy_id, team__club=club)
    
    # Check permissions
    if not strategy.team.can_user_manage(request.user):
        return HttpResponseForbidden("You don't have permission to manage this strategy")
    
    stint_plans = strategy.stint_plans.all().order_by('stint_number')
    
    context = {
        "club": club,
        "strategy": strategy,
        "stint_plans": stint_plans,
        "title": f"Stint Planning - {strategy.name}",
    }
    
    return render(request, "teams/stint_plan_management.html", context)


# === SUBSCRIPTION UPGRADE VIEWS ===

@club_member_required
def subscription_upgrade_prompt(request, club_slug):
    """Show upgrade prompt when subscription limits are reached."""
    club = request.club
    
    # Get current subscription info
    try:
        from simlane.billing.models import ClubSubscription
        subscription = ClubSubscription.objects.select_related('plan').get(
            club=club, 
            status__in=['active', 'trialing']
        )
    except (ImportError, ClubSubscription.DoesNotExist):
        subscription = None
    
    # Get available plans for upgrade
    available_plans = []
    try:
        from simlane.billing.models import SubscriptionPlan
        available_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('monthly_price')
    except ImportError:
        pass
    
    context = {
        "club": club,
        "current_subscription": subscription,
        "available_plans": available_plans,
        "title": f"Upgrade Subscription - {club.name}",
    }
    
    return render(request, "teams/subscription_upgrade_prompt.html", context)


# === FUTURE VIEWS ===
# These will be implemented as we build out the functionality:
#
# Event Organization (using Event.organizing_club):
# - club_organize_event: Create/organize events as a club
# - club_events_list: List events organized by the club
#
# Team Management:
# - club_teams_list: List teams in the club
# - club_team_create: Create a new team within the club
# - club_team_detail: View team details


# === EVENT SIGNUP SHEET DETAIL ===
@subscription_required(features=['race_planning'])
def club_event_signup_detail(request, club_slug, sheet_id):
    """Detailed view of a club's event signup sheet - requires race planning subscription."""
    club = request.club
    signup_sheet = get_object_or_404(
        ClubEventSignupSheet.objects.select_related(
            "event",
            "event__simulator",
            "event__sim_layout",
            "event__sim_layout__sim_track",
            "event__sim_layout__sim_track__track_model",
            "created_by",
        ).prefetch_related(
            "event__time_slots",
        ),
        id=sheet_id,
        club=club,
    )

    # Fetch signups (participations) for this sheet
    signups_qs = EventParticipation.objects.filter(
        event=signup_sheet.event,
        signup_context_club=club,
    ).select_related("user", "team", "assigned_car")

    can_manage = (
        request.club_member.can_manage_events()
        if hasattr(request, "club_member")
        else False
    )

    # Check if team formation features are available
    team_formation_available = hasattr(request, 'club_subscription') and request.club_subscription.has_feature('race_planning')

    context = {
        "club": club,
        "signup_sheet": signup_sheet,
        "signups": signups_qs,
        "can_manage": can_manage,
        "title": signup_sheet.title,
        "team_formation_available": team_formation_available,
        "subscription_info": getattr(request, 'club_subscription', None),
    }

    if request.headers.get("HX-Request"):
        return render(request, "teams/club_event_signup_detail_partial.html", context)

    return render(request, "teams/club_event_signup_detail.html", context)


@race_planning_required
def club_event_signup_edit(request, club_slug, sheet_id):
    """Edit an existing signup sheet (event is immutable) - requires race planning subscription."""
    club = request.club
    signup_sheet = get_object_or_404(ClubEventSignupSheet, id=sheet_id, club=club)

    if request.method == "POST":
        form = ClubEventSignupSheetForm(
            request.POST,
            instance=signup_sheet,
            club=club,
            user=request.user,
        )
        # Prevent event from being changed
        form.fields.pop("event_search", None)
        if form.is_valid():
            form.save()
            messages.success(request, "Signup sheet updated successfully.")
            return redirect(
                "teams:club_event_signup_detail", club_slug=club.slug, sheet_id=sheet_id
            )
    else:
        form = ClubEventSignupSheetForm(
            instance=signup_sheet, club=club, user=request.user
        )
        form.fields.pop("event_search", None)

    context = {
        "club": club,
        "form": form,
        "signup_sheet": signup_sheet,
        "edit_mode": True,
        "title": f"Edit Signup - {signup_sheet.title}",
    }
    return render(request, "teams/club_event_signup_edit.html", context)
