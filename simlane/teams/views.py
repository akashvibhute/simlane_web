# Create your views here.

from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render

from .models import Club
from .models import ClubMember


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
            "team", "team__club"
        )
        user_teams = []
        for team_member in team_memberships:
            # Get club membership role
            try:
                club_member = ClubMember.objects.get(
                    user=request.user, club=team_member.team.club
                )
                club_role = club_member.role
            except ClubMember.DoesNotExist:
                club_role = "member"

            user_teams.append(
                {
                    "team": team_member.team,
                    "club": team_member.team.club,
                    "role": club_role,
                }
            )

        # If user has teams, redirect to first team's dashboard
        if user_teams:
            from django.shortcuts import redirect

            first_team = user_teams[0]["team"]
            return redirect("teams_dashboard:club_dashboard", team_name=first_team.name)

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
def club_dashboard(request, team_name):
    """Individual club dashboard - defaults to overview section."""
    return club_dashboard_section(request, team_name, "overview")


@login_required
def club_dashboard_section(request, team_name, section="overview"):
    """Club dashboard section view with HTMX support."""
    # Get the team by name, ensuring user has access through TeamMember
    from .models import EventEntry
    from .models import TeamMember

    try:
        team_membership = TeamMember.objects.select_related("team", "team__club").get(
            team__name__iexact=team_name,
            user=request.user,
        )
        team = team_membership.team
    except TeamMember.DoesNotExist:
        raise Http404("Team not found or you don't have access to it")

    # Get user's role in the club
    try:
        club_member = ClubMember.objects.get(user=request.user, club=team.club)
        user_role = club_member.role
    except ClubMember.DoesNotExist:
        user_role = "member"  # fallback

    # Get all user's clubs for the dropdown
    user_clubs = (
        ClubMember.objects.filter(user=request.user)
        .select_related("club")
        .order_by("club__name")
    )

    # Get all user's teams for club switching
    all_team_memberships = TeamMember.objects.filter(user=request.user).select_related(
        "team", "team__club"
    )
    user_clubs_with_teams = []
    for tm in all_team_memberships:
        # Get club membership role
        try:
            cm = ClubMember.objects.get(user=request.user, club=tm.team.club)
            club_role = cm.role
        except ClubMember.DoesNotExist:
            club_role = "member"

        # Check if this club is already in our list
        existing_club = next(
            (c for c in user_clubs_with_teams if c["club"].id == tm.team.club.id), None
        )
        if not existing_club:
            user_clubs_with_teams.append(
                {
                    "club": tm.team.club,
                    "role": club_role,
                    "teams": [tm.team],
                }
            )
        else:
            existing_club["teams"].append(tm.team)

    # Get team members
    team_members = (
        TeamMember.objects.filter(team=team)
        .select_related("user")
        .order_by("user__username")
    )

    # Get recent events/entries for this team
    recent_entries = (
        EventEntry.objects.filter(team=team)
        .select_related("event", "user", "sim_car")
        .order_by("-created_at")[:10]
    )

    context = {
        "team": team,
        "club": team.club,
        "user_role": user_role,
        "team_members": team_members,
        "recent_entries": recent_entries,
        "active_section": section,
        "total_members": team_members.count(),
        "total_entries": EventEntry.objects.filter(team=team).count(),
        "user_clubs_with_teams": user_clubs_with_teams,
    }

    # HTMX requests return partial content
    if request.headers.get("HX-Request"):
        return render(request, "teams/club_dashboard_content_partial.html", context)

    # Regular requests return full page
    return render(request, "teams/club_dashboard.html", context)
