# Create your views here.

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import Http404
from django.http import HttpResponse
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from simlane.sim.models import Event

from .decorators import club_admin_required
from .decorators import club_manager_required
from .decorators import club_member_required
from .decorators import event_signup_access
from .decorators import team_allocation_access
from .forms import ClubCreateForm
from .forms import ClubInvitationForm
from .forms import ClubUpdateForm
from .forms import EventSignupForm
from .models import Club
from .models import ClubEvent
from .models import ClubInvitation
from .models import ClubMember
from .models import EventSignup
from .models import Team
from .models import TeamEventStrategy
from .services import EventParticipationService
from .utils import export_signup_data
from .utils import generate_stint_plan_pdf

# Enhanced views imports
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json


@login_required
def clubs_dashboard(request):
    """Main clubs dashboard showing user's clubs and teams."""
    # Get user's club memberships
    user_clubs = (
        ClubMember.objects.filter(user=request.user)
        .select_related("club")
        .order_by("club__name")
    )

    # If user has clubs, redirect to first club dashboard if they have teams
    if user_clubs.exists():
        # Get user's teams through TeamMember relationships
        from .models import TeamMember

        team_memberships = TeamMember.objects.filter(user=request.user).select_related(
            "team",
            "team__club",
        )
        user_teams = []
        for team_member in team_memberships:
            # Get club membership role
            try:
                club_member = ClubMember.objects.get(
                    user=request.user,
                    club=team_member.team.club,
                )
                club_role = club_member.role
            except ClubMember.DoesNotExist:
                club_role = "member"

            user_teams.append(
                {
                    "team": team_member.team,
                    "club": team_member.team.club,
                    "role": club_role,
                },
            )

        # If user has teams, redirect to first team's dashboard
        if user_teams:
            from django.shortcuts import redirect

            first_team = user_teams[0]["team"]
            return redirect("teams:club_dashboard", team_name=first_team.name)

        context = {
            "user_clubs": user_clubs,
            "user_teams": user_teams,
            "total_clubs": user_clubs.count(),
            "total_teams": len(user_teams),
        }

        return render(request, "teams/clubs_dashboard.html", context)

    # If user has no clubs, show club discovery/creation page
    # Get all public clubs for joining
    all_clubs = Club.objects.filter(is_active=True).order_by("name")

    context = {
        "user_clubs": user_clubs,
        "user_teams": [],
        "total_clubs": 0,
        "total_teams": 0,
        "all_clubs": all_clubs,
        "show_club_discovery": True,
    }

    return render(request, "teams/clubs_dashboard.html", context)


@login_required
def club_dashboard(request, club_slug):
    """Individual club dashboard - defaults to overview section."""
    return club_dashboard_section(request, club_slug, "overview")


@login_required
def club_dashboard_section(request, club_slug, section="overview"):
    """Club dashboard section view with HTMX support."""
    from .models import EventEntry
    from .models import TeamMember

    # Get the club by slug, ensuring user has access through ClubMember
    try:
        club_member = ClubMember.objects.select_related("club").get(
            club__slug=club_slug,
            user=request.user,
        )
        club = club_member.club
        user_role = club_member.role
    except ClubMember.DoesNotExist:
        # Check if club is public for read-only access
        try:
            club = Club.objects.get(slug=club_slug, is_public=True)
            user_role = None  # No role for public access
        except Club.DoesNotExist:
            raise Http404("Club not found or you don't have access to it")

    # Get all user's clubs for the dropdown
    user_clubs = (
        ClubMember.objects.filter(user=request.user)
        .select_related("club")
        .order_by("club__name")
    )

    # Get all user's teams in this club
    user_teams_in_club = []
    if user_role:  # Only if user is a member
        user_teams_in_club = TeamMember.objects.filter(
            user=request.user,
            team__club=club,
        ).select_related("team")

    # Get club teams (for display)
    club_teams = club.teams.filter(is_active=True).order_by("name")

    # Get club members
    club_members = (
        ClubMember.objects.filter(club=club)
        .select_related("user")
        .order_by("-role", "user__username")
    )

    # Get recent events/entries for this club
    recent_entries = (
        EventEntry.objects.filter(team__club=club)
        .select_related("event", "user", "sim_car", "team")
        .order_by("-created_at")[:10]
    )

    # Get club events
    club_events = (
        ClubEvent.objects.filter(club=club)
        .select_related(
            "base_event",
            "base_event__sim_layout",
            "base_event__sim_layout__sim_track",
            "base_event__sim_layout__sim_track__track_model",
        )
        .prefetch_related("signups")
        .order_by("-created_at")
    )

    context = {
        "club": club,
        "user_role": user_role,
        "user_teams_in_club": user_teams_in_club,
        "club_teams": club_teams,
        "club_members": club_members,
        "recent_entries": recent_entries,
        "club_events": club_events,
        "active_section": section,
        "total_members": club_members.count(),
        "total_teams": club_teams.count(),
        "total_entries": EventEntry.objects.filter(team__club=club).count(),
        "user_clubs": user_clubs,
        "is_public_view": user_role is None,
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
        form = ClubCreateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                # Create club with the user as creator
                club = form.save(commit=False)
                club.created_by = request.user
                club.save()

                # The save method will automatically create the user as admin

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
        form = ClubUpdateForm(request.POST, instance=club)
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


@club_manager_required
def club_invite_member(request, club_slug):
    """Send invitations to new members"""
    club = request.club

    if request.method == "POST":
        form = ClubInvitationForm(request.POST, club=club, inviter=request.user)
        if form.is_valid():
            try:
                invitation = form.save()
                # Send invitation email
                ClubInvitationService.send_invitation(
                    club=club,
                    inviter=request.user,
                    email=invitation.email,
                    role=invitation.role,
                    message=invitation.personal_message,
                )
                messages.success(request, f"Invitation sent to {invitation.email}")

                if request.headers.get("HX-Request"):
                    # Return updated member list for HTMX
                    return redirect("teams:club_members", club_id=club.id)

                return redirect("teams:club_members", club_id=club.id)
            except (OSError, ValueError) as e:
                messages.error(request, f"Failed to send invitation: {e!s}")
    else:
        form = ClubInvitationForm(club=club, inviter=request.user)

    context = {
        "form": form,
        "club": club,
        "title": f"Invite Member to {club.name}",
    }

    if request.headers.get("HX-Request"):
        return render(request, "teams/club_invite_member_modal.html", context)

    return render(request, "teams/club_invite_member.html", context)


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
        ClubInvitationService.accept_invitation(token, request.user)
        messages.success(request, f"Welcome to {invitation.club.name}!")

        # Clear token from session if exists
        request.session.pop("invitation_token", None)

        return redirect("teams:club_dashboard", club_id=invitation.club.id)

    except ValueError as e:
        messages.error(request, str(e))
        return redirect("teams:clubs_dashboard")
    except (OSError, ValueError, ClubInvitation.DoesNotExist):
        messages.error(request, "An error occurred processing your invitation.")
        return redirect("teams:clubs_dashboard")


def club_invitation_decline(request, token):
    """Process invitation decline"""
    try:
        ClubInvitationService.decline_invitation(token)
        messages.info(request, "Invitation declined.")
    except ValueError as e:
        messages.error(request, str(e))

    if request.user.is_authenticated:
        return redirect("teams:clubs_dashboard")
    return redirect("account_login")


# Event Signup Views


@club_manager_required
def event_signup_create(request, club_slug):
    """Open signup for existing club events"""
    from simlane.sim.models import Simulator

    club = request.club

    # DEBUG: Let's see what's available
    total_sim_events = Event.objects.count()
    total_club_events = ClubEvent.objects.filter(club=club).count()
    draft_club_events_count = ClubEvent.objects.filter(
        club=club,
        status="draft",
    ).count()

    # Get club events that don't have signups open yet (status is draft)
    available_club_events = (
        ClubEvent.objects.filter(club=club, status="draft")
        .select_related(
            "base_event",
            "base_event__sim_layout",
            "base_event__sim_layout__sim_track",
            "base_event__sim_layout__sim_track__track_model",
            "base_event__series",
            "base_event__simulator",
        )
        .prefetch_related("base_event__sessions", "base_event__instances")
        .order_by("-created_at")
    )

    # Convert to base events for template compatibility
    available_events = [club_event.base_event for club_event in available_club_events]

    # Get all simulators for filtering
    simulators = Simulator.objects.filter(is_active=True).order_by("name")

    # DEBUG: Add debug information to messages if no events found
    if not available_events:
        messages.info(
            request,
            f"Debug Info: Total Sim Events: {total_sim_events}, "
            f"Club Events: {total_club_events}, "
            f"Draft Club Events: {draft_club_events_count}. "
            f"{'No events added to club yet - use Add Events button.' if total_club_events == 0 else 'Club events exist but none are in draft status.'}",
        )

    if request.method == "POST":
        selected_event_id = request.POST.get("base_event")
        if selected_event_id:
            try:
                # Find the club event for this base event
                club_event = ClubEvent.objects.get(
                    club=club,
                    base_event_id=selected_event_id,
                    status="draft",
                )

                # Update signup details
                club_event.signup_deadline = timezone.now() + timedelta(
                    days=7,
                )  # Default 7 days
                club_event.status = "signup_open"
                club_event.save()

                messages.success(request, f"Signup opened for: {club_event.title}")
                return redirect(
                    "teams:event_signup_detail",
                    club_slug=club.slug,
                    signup_id=club_event.id,
                )
            except ClubEvent.DoesNotExist:
                messages.error(
                    request,
                    "Selected event not found or already has signup open.",
                )
        else:
            messages.error(request, "Please select an event.")

    context = {
        "club": club,
        "available_events": available_events,
        "simulators": simulators,
        "title": f"Open Event Signup - {club.name}",
        # DEBUG: Add debug context
        "debug_info": {
            "total_sim_events": total_sim_events,
            "total_club_events": total_club_events,
            "draft_club_events_count": draft_club_events_count,
        },
    }

    return render(request, "teams/event_signup_create.html", context)


@event_signup_access
def event_signup_detail(request, club_slug, signup_id):
    """View signup sheet details and entries"""
    club_event = request.club_event  # Set by decorator

    # Get signups with related data
    signups = (
        club_event.signups.select_related(
            "user",
            "primary_sim_profile",
            "assigned_team",
        )
        .prefetch_related(
            "preferred_cars",
            "backup_cars",
            "availabilities",
        )
        .order_by("-created_at")
    )

    # Calculate statistics
    stats = EventSignupService.get_signup_summary(club_event.id)

    # Check if user has signed up
    user_signup = None
    if request.user.is_authenticated:
        user_signup = signups.filter(user=request.user).first()

    context = {
        "club_event": club_event,
        "club": club_event.club,
        "signups": signups,
        "stats": stats,
        "user_signup": user_signup,
        "can_manage": request.club_member.can_manage_club(),
        "is_signup_open": club_event.is_signup_open,
    }

    if request.headers.get("HX-Request"):
        return render(request, "teams/event_signup_detail_partial.html", context)

    return render(request, "teams/event_signup_detail.html", context)


@event_signup_access
@require_http_methods(["GET", "POST"])
def event_signup_join(request, club_slug, signup_id):
    """Member signup form"""
    club_event = request.club_event

    # Check if already signed up
    existing_signup = EventSignup.objects.filter(
        club_event=club_event,
        user=request.user,
    ).first()

    if existing_signup:
        messages.info(request, "You have already signed up for this event.")
        return redirect(
            "teams:event_signup_update",
            signup_id=signup_id,
            entry_id=existing_signup.id,
        )

    if request.method == "POST":
        form = EventSignupForm(
            request.POST,
            club_event=club_event,
            user=request.user,
        )

        if form.is_valid():
            with transaction.atomic():
                signup = form.save(commit=False)
                signup.club_event = club_event
                signup.user = request.user
                signup.save()

                # Save many-to-many relationships
                form.save_m2m()

                # Handle availability formset
                # This would be handled with additional forms

                # Send confirmation
                NotificationService.send_signup_confirmation(signup)

                messages.success(request, "Successfully signed up for the event!")
                return redirect("teams:event_signup_detail", signup_id=club_event.id)
    else:
        form = EventSignupForm(club_event=club_event, user=request.user)

    context = {
        "form": form,
        "club_event": club_event,
        "club": club_event.club,
        "title": f"Sign Up - {club_event.title}",
    }

    return render(request, "teams/event_signup_join.html", context)


@event_signup_access
def event_signup_update(request, club_slug, signup_id, entry_id):
    """Update existing signup"""
    club_event = request.club_event
    signup = get_object_or_404(
        EventSignup,
        id=entry_id,
        club_event=club_event,
        user=request.user,
    )

    if request.method == "POST":
        form = EventSignupForm(
            request.POST,
            instance=signup,
            club_event=club_event,
            user=request.user,
        )

        if form.is_valid():
            form.save()
            messages.success(request, "Signup updated successfully!")

            if request.headers.get("HX-Request"):
                return HttpResponse(status=204, headers={"HX-Refresh": "true"})

            return redirect("teams:event_signup_detail", signup_id=club_event.id)
    else:
        form = EventSignupForm(
            instance=signup,
            club_event=club_event,
            user=request.user,
        )

    context = {
        "form": form,
        "club_event": club_event,
        "signup": signup,
        "title": f"Update Signup - {club_event.title}",
    }

    return render(request, "teams/event_signup_update.html", context)


@club_manager_required
def event_signup_close(request, club_slug, signup_id):
    """Close signup for team allocation"""
    club_event = get_object_or_404(ClubEvent, id=signup_id, club=request.club)

    if request.method == "POST":
        EventSignupService.close_signup(club_event.id)
        messages.success(request, "Signup closed. You can now allocate teams.")
        return redirect("teams:team_allocation_wizard", signup_id=club_event.id)

    context = {
        "club_event": club_event,
        "signups_count": club_event.signups.count(),
    }

    return render(request, "teams/event_signup_close_confirm.html", context)


# Team Allocation Views


@club_manager_required
def team_allocation_wizard(request, club_slug, signup_id):
    """Multi-step team allocation interface"""
    club_event = get_object_or_404(ClubEvent, id=signup_id, club=request.club)

    # Get all signups
    signups = club_event.signups.filter(can_drive=True).select_related("user")

    if request.method == "POST":
        # Handle different wizard steps
        step = request.POST.get("step", "1")

        if step == "auto_suggest":
            # Get AI suggestions
            criteria = {
                "prioritize_skill": request.POST.get("prioritize_skill", True),
                "prioritize_availability": request.POST.get(
                    "prioritize_availability",
                    False,
                ),
                "team_count": int(request.POST.get("team_count", 2)),
            }

            suggestions = TeamAllocationService.suggest_team_allocations(
                club_event.id,
                criteria,
            )

            context = {
                "club_event": club_event,
                "suggestions": suggestions,
                "step": "review",
            }

            if request.headers.get("HX-Request"):
                return render(
                    request,
                    "teams/team_allocation_suggestions_partial.html",
                    context,
                )

    context = {
        "club_event": club_event,
        "signups": signups,
        "available_teams": Team.objects.filter(club=request.club, is_active=True),
        "step": request.GET.get("step", "1"),
    }

    return render(request, "teams/team_allocation_wizard.html", context)


@club_manager_required
def team_allocation_preview(request, club_slug, signup_id):
    """Preview suggested allocations"""
    club_event = get_object_or_404(ClubEvent, id=signup_id, club=request.club)

    # This would show the preview of allocations before finalizing

    context = {
        "club_event": club_event,
    }

    return render(request, "teams/team_allocation_preview.html", context)


@club_manager_required
@require_http_methods(["POST"])
def team_allocation_create(request, club_slug, signup_id):
    """Finalize team allocations"""
    club_event = get_object_or_404(ClubEvent, id=signup_id, club=request.club)

    try:
        # Parse allocation data from request
        allocations = []
        # This would parse the form data to create allocations

        # Create allocations
        created = TeamAllocationService.create_team_allocation(
            club_event.id,
            allocations,
        )

        messages.success(
            request,
            f"Successfully created {len(created)} team allocations!",
        )
        return redirect("teams:event_signup_detail", signup_id=club_event.id)

    except (OSError, ValueError) as e:
        messages.error(request, f"Failed to create allocations: {e!s}")
        return redirect("teams:team_allocation_wizard", signup_id=club_event.id)


@team_allocation_access
def team_allocation_update(request, allocation_id):
    """Modify existing allocations"""
    allocation = request.allocation  # Set by decorator

    # Handle updates to team allocations

    context = {
        "allocation": allocation,
    }

    return render(request, "teams/team_allocation_update.html", context)


# Team Planning Views


@team_allocation_access
def team_planning_dashboard(request, allocation_id):
    """Team-specific planning interface"""
    allocation = request.allocation

    # Get or create team strategy
    strategy, created = TeamEventStrategy.objects.get_or_create(
        team=allocation.team,
        club_event=allocation.club_event,
        team_allocation=allocation,
        defaults={
            "selected_car": allocation.assigned_sim_car,
            "selected_instance": allocation.club_event.base_event.instances.first(),
        },
    )

    # Get team members
    team_members = allocation.members.select_related("event_signup__user")

    # Get stint assignments
    stints = strategy.stint_assignments.order_by("stint_number")

    context = {
        "allocation": allocation,
        "strategy": strategy,
        "team_members": team_members,
        "stints": stints,
        "club": allocation.club_event.club,
        "event": allocation.club_event,
    }

    return render(request, "teams/team_planning_dashboard.html", context)


@team_allocation_access
def stint_planning(request, allocation_id):
    """Stint planning and pit strategy"""
    allocation = request.allocation

    # Get strategy through the relationship
    try:
        strategy = allocation.strategy
    except TeamEventStrategy.DoesNotExist:
        # Create strategy if it doesn't exist
        strategy = TeamEventStrategy.objects.create(
            team=allocation.team,
            club_event=allocation.club_event,
            team_allocation=allocation,
            selected_car=allocation.assigned_sim_car,
            selected_instance=allocation.club_event.base_event.instances.first(),
        )

    if request.method == "POST":
        # Handle stint planning updates
        pass

    # Calculate pit windows
    pit_windows = StintPlanningService.calculate_pit_windows(
        strategy.selected_instance,
        strategy.selected_car,
    )

    context = {
        "allocation": allocation,
        "strategy": strategy,
        "pit_windows": pit_windows,
    }

    if request.headers.get("HX-Request"):
        return render(request, "teams/stint_planning_partial.html", context)

    return render(request, "teams/stint_planning.html", context)


@team_allocation_access
@require_http_methods(["POST"])
def stint_plan_update(request, allocation_id):
    """Update stint assignments"""
    allocation = request.allocation

    # Handle stint updates

    messages.success(request, "Stint plan updated successfully!")

    if request.headers.get("HX-Request"):
        return HttpResponse(status=204, headers={"HX-Refresh": "true"})

    return redirect("teams:stint_planning", allocation_id=allocation.id)


@team_allocation_access
def stint_plan_export(request, allocation_id):
    """Export stint plan as PDF/CSV"""
    allocation = request.allocation
    export_format = request.GET.get("format", "pdf")

    if export_format == "pdf":
        pdf_file = generate_stint_plan_pdf(allocation)
        response = HttpResponse(pdf_file, content_type="application/pdf")
        response["Content-Disposition"] = (
            f'attachment; filename="stint_plan_{allocation.team.name}.pdf"'
        )
        return response

    if export_format == "csv":
        csv_file = export_signup_data(allocation.club_event, format="csv")
        response = HttpResponse(csv_file, content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="signups_{allocation.club_event.title}.csv"'
        )
        return response

    return HttpResponse("Invalid format", status=400)


# HTMX Partial Views


@club_member_required
def club_members_partial(request, club_slug):
    """Dynamic member list updates"""
    return club_members(request, club_slug)


@event_signup_access
def signup_entries_partial(request, club_slug, signup_id):
    """Dynamic signup list"""
    club_event = request.club_event
    signups = club_event.signups.select_related("user").order_by("-created_at")

    context = {
        "signups": signups,
        "club_event": club_event,
    }

    return render(request, "teams/signup_entries_partial.html", context)


@club_manager_required
def team_allocation_partial(request, club_slug, signup_id):
    """Dynamic team allocation interface"""
    club_event = get_object_or_404(ClubEvent, id=signup_id, club=request.club)

    context = {
        "club_event": club_event,
    }

    return render(request, "teams/team_allocation_partial.html", context)


@team_allocation_access
def stint_plan_partial(request, allocation_id):
    """Dynamic stint plan updates"""
    return stint_planning(request, allocation_id)


@club_manager_required
def club_add_events(request, club_slug):
    """HTMX modal for adding events from sim app to club"""
    from simlane.sim.models import Event

    club = get_object_or_404(Club, slug=club_slug)

    # Get available events that aren't already in this club
    existing_event_ids = ClubEvent.objects.filter(club=club).values_list(
        "base_event_id",
        flat=True,
    )
    available_events = (
        Event.objects.exclude(id__in=existing_event_ids)
        .select_related(
            "sim_layout",
            "sim_layout__sim_track",
            "sim_layout__sim_track__track_model",
            "series",
        )
        .filter(status__in=["SCHEDULED", "DRAFT"])
        .order_by("-created_at")[:50]  # Limit to recent events
    )

    if request.method == "POST":
        selected_event_ids = request.POST.getlist("events")
        if selected_event_ids:
            with transaction.atomic():
                for event_id in selected_event_ids:
                    try:
                        base_event = Event.objects.get(id=event_id)
                        # Create club event with reasonable defaults
                        ClubEvent.objects.create(
                            club=club,
                            base_event=base_event,
                            title=base_event.name,
                            description=base_event.description or "",
                            signup_deadline=timezone.now()
                            + timedelta(days=7),  # Default 7 days from now
                            max_participants=None,  # No limit by default
                            created_by=request.user,
                            status="draft",
                        )
                    except Event.DoesNotExist:
                        continue

            messages.success(
                request,
                f"Successfully added {len(selected_event_ids)} event(s) to {club.name}",
            )

            # Return updated events section
            return HttpResponse(
                status=200,
                headers={
                    "HX-Trigger": "closeModal",
                    "HX-Refresh": "true",
                },
            )

    context = {
        "club": club,
        "available_events": available_events,
    }

    return render(request, "teams/club_add_events_modal.html", context)


@club_manager_required
@require_http_methods(["DELETE"])
def club_remove_event(request, club_slug, event_id):
    """Remove an event from the club"""
    club = get_object_or_404(Club, slug=club_slug)
    club_event = get_object_or_404(ClubEvent, id=event_id, club=club)

    # Check if event has signups - if so, require confirmation
    if club_event.signups.exists():
        return JsonResponse(
            {
                "error": "Cannot remove event with existing signups. Please close signups first.",
            },
            status=400,
        )

    event_title = club_event.title
    club_event.delete()

    messages.success(request, f"Removed event '{event_title}' from {club.name}")

    # Return empty response to remove the element
    return HttpResponse(status=200)


@club_member_required
def club_event_detail(request, club_slug, event_id):
    """View club event details"""
    club_event = get_object_or_404(ClubEvent, id=event_id, club=request.club)

    # Check if user has signed up (if signup is open)
    user_signup = None
    if request.user.is_authenticated and club_event.status == "signup_open":
        user_signup = club_event.signups.filter(user=request.user).first()

    # Get signups count if needed
    signups_count = 0
    if club_event.status in ["signup_open", "signup_closed", "teams_assigned"]:
        signups_count = club_event.signups.count()

    context = {
        "club_event": club_event,
        "club": club_event.club,
        "signups_count": signups_count,
        "user_signup": user_signup,
        "can_manage": request.club_member.can_manage_club(),
        "is_signup_open": club_event.status == "signup_open",
        "can_signup": (
            club_event.status == "signup_open"
            and club_event.signup_deadline > timezone.now()
            and not user_signup
        ),
    }

    return render(request, "teams/club_event_detail.html", context)


# ===== UNIFIED EVENT PARTICIPATION SYSTEM =====
# These views implement the enhanced event participation workflow
# They work alongside the existing views and will eventually replace some of them

@login_required
def enhanced_event_signup_create(request, event_id):
    """Enhanced event signup with availability collection"""
    try:
        from simlane.sim.models import Event
        from .models import EventParticipation, ClubEvent
        from .forms_enhanced import EnhancedEventSignupForm
        from .services import EventParticipationService
        
        event = get_object_or_404(Event, id=event_id)
        
        # Check if this is a club event
        club_event = None
        try:
            club_event = ClubEvent.objects.get(event=event)
        except ClubEvent.DoesNotExist:
            pass
        
        # Check if user already has a participation
        existing_participation = EventParticipation.objects.filter(
            event=event, user=request.user
        ).first()
        
        if existing_participation:
            messages.info(request, "You are already signed up for this event.")
            return redirect('teams:team_formation_dashboard', club_event_id=club_event.id if club_event else event.id)
        
        if request.method == 'POST':
            form = EnhancedEventSignupForm(request.POST, event=event, user=request.user)
            if form.is_valid():
                participation = form.save()
                messages.success(request, "Successfully signed up for the event!")
                
                if request.headers.get('HX-Request'):
                    return JsonResponse({'status': 'success', 'redirect': True})
                
                return redirect('teams:team_formation_dashboard', club_event_id=club_event.id if club_event else event.id)
        else:
            form = EnhancedEventSignupForm(event=event, user=request.user)
        
        context = {
            'form': form,
            'event': event,
            'club_event': club_event,
            'existing_participation': existing_participation,
        }
        
        return render(request, 'teams/event_signup_create_enhanced.html', context)
        
    except ImportError:
        messages.error(request, "Enhanced signup system not available yet.")
        return redirect('teams:clubs_dashboard')


@login_required  
def enhanced_team_formation_dashboard(request, club_event_id):
    """Enhanced team formation dashboard with analytics"""
    try:
        from .models import ClubEvent, EventParticipation
        from .services import EventParticipationService, WorkflowService, AvailabilityService
        
        club_event = get_object_or_404(ClubEvent, id=club_event_id)
        event = club_event.event
        
        # Check permissions
        if not request.user.clubmember_set.filter(club=club_event.club).exists():
            raise Http404("Access denied")
        
        # Get participation data
        participations = EventParticipation.objects.filter(
            event=event
        ).select_related('user', 'preferred_car', 'backup_car', 'team').prefetch_related(
            'availability_windows'
        )
        
        # Get analytics
        summary = EventParticipationService.get_participation_summary(event)
        workflow = WorkflowService.get_workflow_status(event)
        coverage = AvailabilityService.generate_coverage_report(event)
        
        context = {
            'club_event': club_event,
            'event': event,
            'participations': participations,
            'summary': summary,
            'workflow': workflow,
            'coverage': coverage,
        }
        
        return render(request, 'teams/team_formation_dashboard.html', context)
        
    except ImportError:
        messages.error(request, "Enhanced team formation not available yet.")
        return redirect('teams:clubs_dashboard')


@login_required
@require_POST
def generate_team_suggestions(request, club_event_id):
    """Generate team suggestions based on availability overlap"""
    try:
        from .models import ClubEvent
        from .services import TeamFormationService
        
        club_event = get_object_or_404(ClubEvent, id=club_event_id)
        
        # Check permissions
        if not request.user.clubmember_set.filter(club=club_event.club).exists():
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Generate suggestions
        suggestions = TeamFormationService.generate_team_suggestions(
            event=club_event.event,
            team_size=int(request.POST.get('team_size', 3)),
            algorithm=request.POST.get('algorithm', 'availability_overlap')
        )
        
        # Store suggestions in session for later use
        request.session[f'team_suggestions_{club_event_id}'] = suggestions
        
        if request.headers.get('HX-Request'):
            context = {'suggestions': suggestions}
            return render(request, 'teams/partials/team_suggestions.html', context)
        
        return JsonResponse({'status': 'success', 'suggestions_count': len(suggestions)})
        
    except ImportError:
        return JsonResponse({'error': 'Team formation service not available'}, status=500)


@login_required
@require_POST  
def create_teams_from_suggestions(request, club_event_id):
    """Create teams from selected suggestions"""
    try:
        from .models import ClubEvent
        from .services import TeamFormationService
        
        club_event = get_object_or_404(ClubEvent, id=club_event_id)
        
        # Check permissions
        if not request.user.clubmember_set.filter(club=club_event.club).exists():
            return JsonResponse({'error': 'Access denied'}, status=403)
        
        # Get suggestions from session
        suggestions = request.session.get(f'team_suggestions_{club_event_id}', [])
        if not suggestions:
            return JsonResponse({'error': 'No suggestions found'}, status=400)
        
        # Get selected suggestion indices
        selected_indices = json.loads(request.POST.get('selected_teams', '[]'))
        
        # Create teams from selected suggestions
        created_teams = TeamFormationService.create_teams_from_suggestions(
            club_event=club_event,
            suggestions=suggestions,
            selected_indices=selected_indices,
            creator=request.user
        )
        
        messages.success(request, f"Created {len(created_teams)} teams successfully!")
        
        if request.headers.get('HX-Request'):
            return JsonResponse({'status': 'success', 'teams_created': len(created_teams)})
        
        return redirect('teams:team_formation_dashboard', club_event_id=club_event_id)
        
    except ImportError:
        return JsonResponse({'error': 'Team formation service not available'}, status=500)


@login_required
def participant_list_partial(request, club_event_id):
    """HTMX partial for participant list"""
    try:
        from .models import ClubEvent, EventParticipation
        
        club_event = get_object_or_404(ClubEvent, id=club_event_id)
        
        participations = EventParticipation.objects.filter(
            event=club_event.event
        ).select_related('user', 'preferred_car', 'team').prefetch_related(
            'availability_windows'
        )
        
        context = {'participants': participations}
        return render(request, 'teams/partials/participant_list.html', context)
        
    except ImportError:
        return HttpResponse("Service not available", status=500)


@login_required
def team_suggestions_partial(request, club_event_id):
    """HTMX partial for team suggestions"""
    try:
        suggestions = request.session.get(f'team_suggestions_{club_event_id}', [])
        context = {'suggestions': suggestions}
        return render(request, 'teams/partials/team_suggestions.html', context)
        
    except Exception:
        return HttpResponse("Error loading suggestions", status=500)


# Placeholder views for other enhanced endpoints
@login_required
def formation_dashboard_data(request, club_event_id):
    """API endpoint for dashboard data"""
    return JsonResponse({'status': 'not_implemented'})

@login_required  
def close_signup_phase(request, club_event_id):
    """Close signup phase and move to team formation"""
    return JsonResponse({'status': 'not_implemented'})

@login_required
def finalize_teams(request, club_event_id):
    """Finalize team allocations"""
    return JsonResponse({'status': 'not_implemented'})

@login_required
def availability_coverage_heatmap(request, event_id):
    """Generate availability coverage heatmap"""
    return JsonResponse({'status': 'not_implemented'})

@login_required
def workflow_status(request, event_id):
    """Get current workflow status"""
    return JsonResponse({'status': 'not_implemented'})

@login_required
def send_signup_invitation(request, event_id):
    """Send signup invitation for individual team formation"""
    return JsonResponse({'status': 'not_implemented'})

def process_invitation(request, token):
    """Process signup invitation response"""
    return render(request, 'teams/invitation_response.html', {'token': token})

@login_required
def notify_signup_update(request, event_id):
    """WebSocket helper for real-time updates"""
    return JsonResponse({'status': 'not_implemented'})
