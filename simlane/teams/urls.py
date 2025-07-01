from django.urls import path

from . import views

app_name = "teams"

urlpatterns = [
    # === CLUB MANAGEMENT ===
    # Clubs Root Dashboard
    path("", views.clubs_dashboard, name="clubs_dashboard"),
    # Club Discovery & Creation
    path("create/", views.club_create, name="club_create"),
    path("browse/", views.browse_clubs, name="browse_clubs"),
    path(
        "request-join/<slug:club_slug>/",
        views.request_join_club,
        name="request_join_club",
    ),
    # Club Dashboard & Management (using club slug)
    path("<slug:club_slug>/", views.club_dashboard, name="club_dashboard"),
    path(
        "<slug:club_slug>/<str:section>/",
        views.club_dashboard_section,
        name="club_dashboard_section",
    ),
    path("<slug:club_slug>/update/", views.club_update, name="club_update"),
    # Club Members Management
    path("<slug:club_slug>/members/", views.club_members, name="club_members"),
    path(
        "<slug:club_slug>/invite/", views.club_invite_member, name="club_invite_member"
    ),
    # Club Join Requests Management
    path(
        "<slug:club_slug>/requests/", views.club_join_requests, name="club_join_requests"
    ),
    path(
        "<slug:club_slug>/requests/<uuid:request_id>/handle/",
        views.handle_join_request,
        name="handle_join_request",
    ),
    # Club Event Signups
    path(
        "<slug:club_slug>/signups/", views.club_event_signups, name="club_event_signups"
    ),
    path(
        "<slug:club_slug>/signups/create/",
        views.club_event_signup_create,
        name="club_event_signup_create",
    ),
    path(
        "<slug:club_slug>/signups/bulk-create/",
        views.club_event_signup_bulk_create,
        name="club_event_signup_bulk_create",
    ),
    # Signup Sheet Detail
    path(
        "<slug:club_slug>/signups/<uuid:sheet_id>/",
        views.club_event_signup_detail,
        name="club_event_signup_detail",
    ),
    path(
        "<slug:club_slug>/signups/<uuid:sheet_id>/edit/",
        views.club_event_signup_edit,
        name="club_event_signup_edit",
    ),
    # Club Invitation URLs (token-based, no club needed in URL)
    path(
        "invite/<str:token>/accept/",
        views.club_invitation_accept,
        name="club_invitation_accept",
    ),
    path(
        "invite/<str:token>/decline/",
        views.club_invitation_decline,
        name="club_invitation_decline",
    ),
    
    # === DISCORD INTEGRATION ===
    path(
        "<slug:club_slug>/discord/settings/",
        views.club_discord_settings,
        name="club_discord_settings",
    ),
    path(
        "<slug:club_slug>/discord/invite-bot/",
        views.club_discord_invite_bot,
        name="club_discord_invite_bot",
    ),
    path(
        "<slug:club_slug>/discord/sync-members/",
        views.club_discord_sync_members,
        name="club_discord_sync_members",
    ),
    path(
        "<slug:club_slug>/discord/status/",
        views.club_discord_status,
        name="club_discord_status",
    ),
    # === FUTURE FEATURES ===
    # These will be implemented as we build out the functionality
    # Event Organization (using Event.organizing_club)
    # path("<slug:club_slug>/organize-event/", views.club_organize_event, name="club_organize_event"),
    # path("<slug:club_slug>/events/", views.club_events_list, name="club_events_list"),
    # Team Management within Clubs
    # path("<slug:club_slug>/teams/", views.club_teams_list, name="club_teams_list"),
    # path("<slug:club_slug>/teams/create/", views.club_team_create, name="club_team_create"),
    # path("<slug:club_slug>/teams/<slug:team_slug>/", views.club_team_detail, name="club_team_detail"),
    # Race Planning & Strategy (direct Event integration)
    # path("events/<uuid:event_id>/plan/", views.event_race_plan, name="event_race_plan"),
    # path("events/<uuid:event_id>/signup/", views.event_signup, name="event_signup"),
    # path("events/<uuid:event_id>/teams/", views.event_team_formation, name="event_team_formation"),
]
