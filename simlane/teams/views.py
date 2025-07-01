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

from .decorators import club_admin_required, club_manager_required
from .decorators import club_member_required
from .forms import ClubCreateForm
from .forms import ClubEventSignupBulkCreateForm
from .forms import ClubEventSignupSheetForm
from .forms import ClubInvitationForm
from .forms import ClubJoinRequestForm
from .forms import ClubJoinRequestResponseForm
from .forms import ClubUpdateForm
from .models import Club
from .models import ClubEventSignupSheet
from .models import ClubInvitation
from .models import ClubJoinRequest
from .models import ClubMember
from .models import ClubRole
from .models import EventParticipation
from .models import Team
from .models import TeamMember

# Discord integration imports
from simlane.discord.models import DiscordGuild, ClubDiscordSettings, EventDiscordChannel
from simlane.discord.tasks import sync_discord_members
from simlane.discord.services import DiscordBotService

# Import billing decorators for subscription enforcement
from simlane.billing.decorators import race_planning_required
from simlane.billing.decorators import member_limit_enforced
from simlane.billing.decorators import subscription_required
from simlane.billing.decorators import check_member_limit

# Standard library imports
import asyncio
import logging

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

    # Get user's current club memberships
    user_club_ids = set(
        ClubMember.objects.filter(user=request.user).values_list("club_id", flat=True)
    )

    # We'll present *all* clubs; membership status will influence the action button
    available_clubs = all_clubs  # no exclusion

    # Get user's join requests (pending / historical) to show appropriate button states
    user_join_requests = {}
    if request.user.is_authenticated:
        join_requests = (
            ClubJoinRequest.objects.filter(
                user=request.user,
                club__in=available_clubs,
                status__in=["pending", "approved", "rejected"],
            ).select_related("club")
        )
        user_join_requests = {req.club.id: req for req in join_requests}

    # Add join request status to each club
    clubs_with_status = []
    for club in available_clubs:
        join_request = user_join_requests.get(club.id)
        is_member = club.id in user_club_ids

        clubs_with_status.append(
            {
                "club": club,
                "join_request": join_request,
                "is_member": is_member,
                # Only allow new request if not already member and either no prior request or previous rejected
                "can_request": not is_member
                and (join_request is None or join_request.status == "rejected"),
                "request_status": join_request.status if join_request else None,
            }
        )

    context = {
        "clubs_with_status": clubs_with_status,
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

    # Check if there's already a pending join request
    existing_request = ClubJoinRequest.objects.filter(
        club=club,
        user=request.user,
        status='pending'
    ).first()

    if existing_request:
        messages.info(
            request, f"You already have a pending request to join {club.name}."
        )
        return redirect("teams:browse_clubs")

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

    if request.method == "POST":
        form = ClubJoinRequestForm(request.POST)
        if form.is_valid():
            join_request = form.save(commit=False)
            join_request.club = club
            join_request.user = request.user
            join_request.save()
            
            # Send Discord notification if configured
            if hasattr(club, 'discord_settings') and club.discord_settings.enable_join_request_notifications:
                from simlane.discord.tasks import send_join_request_notification
                send_join_request_notification.delay(join_request.id)
            
            messages.success(
                request,
                f"Your request to join {club.name} has been submitted. "
                f"Club administrators will review it and get back to you."
            )
            return redirect("teams:browse_clubs")
    else:
        form = ClubJoinRequestForm()

    context = {
        "club": club,
        "form": form,
        "existing_request": existing_request,
    }

    return render(request, "teams/request_join_club.html", context)


@login_required
def club_dashboard(request, club_slug):
    """Legacy endpoint – redirect to new CBV dashboard root (/clubs/)."""
    return redirect("clubs:dashboard_root", club_slug=club_slug)


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

    # === Requests section specific context ===
    join_requests = []
    pending_requests_count = 0
    total_requests_count = 0
    status_filter = 'all'
    if section == "requests":
        if user_role not in ['admin', 'teams_manager']:
            return HttpResponseForbidden("Only club admins can view join requests.")
        
        join_requests = ClubJoinRequest.objects.filter(club=club).select_related('user', 'reviewed_by').order_by('-created_at')
        pending_requests_count = ClubJoinRequest.objects.filter(club=club, status='pending').count()
        total_requests_count = ClubJoinRequest.objects.filter(club=club).count()
        
        status_filter = request.GET.get('status', 'all')
        if status_filter != 'all':
            join_requests = join_requests.filter(status=status_filter)
        
        # For HTMX status filter: if this is an HTMX request for requests section, 
        # return only the requests section to update properly
        if request.headers.get("HX-Request") and section == "requests":
            # Check if this is a status filter request by looking at the referer
            referer = request.META.get('HTTP_REFERER', '')
            if 'requests' in referer or request.GET.get("status") is not None:
                # Re-render the entire requests section so status tabs update correctly
                return render(
                    request,
                    "teams/club_dashboard_requests_section.html",
                    {
                        "club": club,
                        "join_requests": join_requests,
                        "pending_requests_count": pending_requests_count,
                        "total_requests_count": total_requests_count,
                        "status_filter": status_filter,
                        "user_role": user_role,
                    },
                )

    # === Discord section specific context ===
    discord_settings = None
    if section == "discord":
        if user_role not in ['admin', 'teams_manager']:
            return HttpResponseForbidden("Only club admins can manage Discord settings.")
        
        # Get or create Discord settings for this club
        from simlane.discord.models import ClubDiscordSettings
        discord_settings, created = ClubDiscordSettings.objects.get_or_create(club=club)

    # === Update section specific context ===
    form = None
    if section == "update":
        # Check if user is admin
        if user_role != 'admin':
            return HttpResponseForbidden("Only club admins can update club settings.")
        
        # Import here to avoid circular imports
        from .forms import ClubUpdateForm
        form = ClubUpdateForm(instance=club)

    # Fetch available text channels from the connected Discord guild for dropdowns
    available_channels = []
    if hasattr(club, 'discord_guild') and club.discord_guild is not None:
        bot_service = DiscordBotService()
        try:
            channels_data = asyncio.run(
                bot_service.list_channels(club.discord_guild.guild_id)
            )
            # Keep only text channels and sort alphabetically by name
            available_channels = sorted(
                (
                    c for c in channels_data
                    if 'text' in c.get('type', '')  # ChannelType.text or guild_text
                ),
                key=lambda c: c['name']
            )
        except Exception as fetch_err:
            logging.getLogger(__name__).warning(
                "Unable to fetch Discord channels for guild %s: %s",
                club.discord_guild.guild_id if hasattr(club, 'discord_guild') else 'unknown',
                fetch_err,
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
        "form": form,
        "join_requests": join_requests,
        "pending_requests_count": pending_requests_count,
        "total_requests_count": total_requests_count,
        "status_filter": status_filter,
        "discord_settings": discord_settings,
        "available_channels": available_channels,
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
                # Check if this came from the dashboard
                if request.headers.get("HX-Target") == "#club-dashboard-content":
                    # Redirect to settings section in dashboard
                    response = HttpResponse(status=204)
                    response["HX-Redirect"] = f"/teams/{club.slug}/dashboard/settings/"
                    return response
                else:
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


# Discord Integration Views

@club_admin_required  
def club_discord_settings(request, club_slug):
    """Discord settings configuration for club"""
    club = get_object_or_404(Club, slug=club_slug)
    
    # Get or create discord settings
    discord_settings, created = ClubDiscordSettings.objects.get_or_create(
        club=club,
        defaults={
            'auto_create_channels': True,
            'enable_voice_channels': True,
            'enable_stint_alerts': True,
        }
    )
    
    # Get discord connection status
    discord_status = {
        'connected': hasattr(club, 'discord_guild') and club.discord_guild is not None,
        'guild_name': club.discord_guild.name if hasattr(club, 'discord_guild') and club.discord_guild else None,
        'member_count': club.discord_guild.member_count if hasattr(club, 'discord_guild') and club.discord_guild else 0,
    }
    
    # Fetch available text channels from the connected Discord guild for dropdowns
    available_channels = []
    if discord_status['connected']:
        bot_service = DiscordBotService()
        try:
            channels_data = asyncio.run(
                bot_service.list_channels(club.discord_guild.guild_id)
            )
            # Keep only text channels and sort alphabetically by name
            available_channels = sorted(
                (
                    c for c in channels_data
                    if 'text' in c.get('type', '')  # ChannelType.text or guild_text
                ),
                key=lambda c: c['name']
            )
        except Exception as fetch_err:
            logging.getLogger(__name__).warning(
                "Unable to fetch Discord channels for guild %s: %s",
                club.discord_guild.guild_id if hasattr(club, 'discord_guild') else 'unknown',
                fetch_err,
            )

    if request.method == 'POST':
        # Handle form submission
        discord_settings.auto_create_channels = request.POST.get('auto_create_channels') == 'on'
        discord_settings.enable_voice_channels = request.POST.get('enable_voice_channels') == 'on'
        discord_settings.enable_practice_voice = request.POST.get('enable_practice_voice') == 'on'
        discord_settings.enable_stint_alerts = request.POST.get('enable_stint_alerts') == 'on'
        discord_settings.auto_sync_members = request.POST.get('auto_sync_members') == 'on'
        discord_settings.enable_join_request_notifications = request.POST.get('enable_join_request_notifications') == 'on'
        
        # Channel settings
        if request.POST.get('join_requests_channel_id'):
            discord_settings.join_requests_channel_id = request.POST.get('join_requests_channel_id')
        
        discord_settings.save()
        
        messages.success(request, "Discord settings updated successfully.")
        
        if request.headers.get('HX-Request'):
            return render(request, 'teams/discord/discord_settings_partial.html', {
                'club': club,
                'discord_settings': discord_settings,
                'discord_status': discord_status,
                'available_channels': available_channels,
            })
    
    context = {
        'club': club,
        'discord_settings': discord_settings,
        'discord_status': discord_status,
        'available_channels': available_channels,
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'teams/discord/discord_settings_partial.html', context)
    
    return render(request, 'teams/discord/discord_settings.html', context)


@club_manager_required
def club_discord_invite_bot(request, club_slug):
    """Generate Discord bot invitation URL for club"""
    club = request.club
    
    if request.method == "POST":
        permissions = 34630287424  # Combined permissions as int
        from django.conf import settings
        redirect_uri = request.build_absolute_uri("/discord/bot/callback/")
        invite_url = DiscordBotService().get_invite_url(
            scopes=["bot", "applications.commands"],
            permissions=permissions,
            state=club.id,
            redirect_uri=redirect_uri,
            response_type="code",
        )
        context = {
            'club': club,
            'invite_url': invite_url,
            'permissions_list': [
                "Manage Channels",
                "Manage Roles", 
                "Send Messages",
                "Create Threads",
                "Connect Voice",
                "View Channel History",
                "Use External Emojis"
            ]
        }
        return render(request, "teams/discord/bot_invite_modal.html", context)
    
    return redirect("teams:club_discord_settings", club_slug=club.slug)


@club_admin_required
def club_discord_sync_members(request, club_slug):
    """Trigger Discord member sync for club"""
    club = request.club
    
    # Check if club has Discord integration
    if not hasattr(club, 'discord_guild'):
        messages.error(request, "Discord integration not set up for this club.")
        return redirect("teams:club_discord_settings", club_slug=club.slug)
    
    if request.method == "POST":
        # Trigger member sync task
        task = sync_discord_members.delay(
            club.discord_guild.guild_id,
            sync_type='manual'
        )
        
        messages.success(
            request, 
            "Discord member sync has been started. This may take a few minutes to complete."
        )
        
        if request.headers.get("HX-Request"):
            return render(request, "teams/discord/member_sync_status.html", {
                'club': club,
                'task_id': task.id,
                'sync_status': 'started'
            })
    
    return redirect("teams:club_discord_settings", club_slug=club.slug)


@club_member_required
def club_discord_status(request, club_slug):
    """Display Discord integration status for club"""
    club = request.club
    
    # Get Discord guild info
    discord_guild = getattr(club, 'discord_guild', None)
    
    # Get Discord settings
    settings = None
    if hasattr(club, 'discord_settings'):
        settings = club.discord_settings
    
    # Get recent sync history
    sync_history = []
    if discord_guild:
        sync_history = discord_guild.discordmembersync_set.order_by('-sync_timestamp')[:10]
    
    # Get active channels
    active_channels = []
    if discord_guild:
        active_channels = EventDiscordChannel.objects.filter(
            guild=discord_guild,
            status='active'
        ).select_related('event_signup_sheet__event')
    
    context = {
        'club': club,
        'discord_guild': discord_guild,
        'discord_settings': settings,
        'sync_history': sync_history,
        'active_channels': active_channels,
        'is_connected': bool(discord_guild),
        'can_manage': request.club_member.can_manage_club()
    }
    
    if request.headers.get("HX-Request"):
        return render(request, "teams/discord/member_sync_status.html", context)
    
    return render(request, "teams/discord/member_sync_status.html", context)


@club_admin_required
def club_join_requests(request, club_slug):
    """View and manage join requests for the club"""
    club = get_object_or_404(Club, slug=club_slug)
    
    # Get all join requests for this club
    join_requests = ClubJoinRequest.objects.filter(club=club).select_related('user', 'reviewed_by').order_by('-created_at')
    
    # Filter by status if requested
    status_filter = request.GET.get('status', 'all')
    if status_filter != 'all':
        join_requests = join_requests.filter(status=status_filter)
    
    context = {
        'club': club,
        'join_requests': join_requests,
        'status_filter': status_filter,
        'pending_count': ClubJoinRequest.objects.filter(club=club, status='pending').count(),
    }
    
    if request.headers.get('HX-Request'):
        return render(request, 'teams/club_dashboard_requests_partial.html', context)
    
    return render(request, 'teams/club_dashboard_requests_section.html', context)


@club_admin_required
def handle_join_request(request, club_slug, request_id):
    """Handle approval/rejection of a join request"""
    club = get_object_or_404(Club, slug=club_slug)
    join_request = get_object_or_404(ClubJoinRequest, id=request_id, club=club)
    
    if request.method == 'POST':
        form = ClubJoinRequestResponseForm(request.POST)
        if form.is_valid():
            action = form.cleaned_data['action']
            message = form.cleaned_data['message']
            role = form.cleaned_data['role']
            
            if action == 'approve':
                club_member = join_request.approve(request.user, message, role)
                
                # Send Discord notification if configured
                if hasattr(club, 'discord_settings') and club.discord_settings.enable_join_request_notifications:
                    from simlane.discord.tasks import send_join_request_approved_notification
                    send_join_request_approved_notification.delay(join_request.id, club_member.id)
                
                messages.success(request, f"Approved {join_request.user.username}'s request to join the club.")
                
            elif action == 'reject':
                join_request.reject(request.user, message)
                
                # Send Discord notification if configured  
                if hasattr(club, 'discord_settings') and club.discord_settings.enable_join_request_notifications:
                    from simlane.discord.tasks import send_join_request_rejected_notification
                    send_join_request_rejected_notification.delay(join_request.id)
                
                messages.info(request, f"Rejected {join_request.user.username}'s request to join the club.")
            
            if request.headers.get('HX-Request'):
                # Return updated requests list
                join_requests = ClubJoinRequest.objects.filter(club=club).select_related('user', 'reviewed_by').order_by('-created_at')
                return render(request, 'teams/club_dashboard_requests_partial.html', {
                    'club': club,
                    'join_requests': join_requests,
                    'status_filter': 'all',
                    'pending_count': ClubJoinRequest.objects.filter(club=club, status='pending').count(),
                })
            
            return redirect('teams:club_join_requests', club_slug=club.slug)
    else:
        form = ClubJoinRequestResponseForm()
    
    context = {
        'club': club,
        'join_request': join_request,
        'form': form,
    }
    
    return render(request, 'teams/handle_join_request.html', context)
