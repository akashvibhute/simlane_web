from django.urls import path

from . import views

app_name = "teams"

urlpatterns = [
    # Clubs Root Dashboard
    path("", views.clubs_dashboard, name="clubs_dashboard"),
    # Club Management URLs (using club slug)
    path("create/", views.club_create, name="club_create"),
    path("browse/", views.browse_clubs, name="browse_clubs"),
    path("<slug:club_slug>/", views.club_dashboard, name="club_dashboard"),
    path(
        "<slug:club_slug>/<str:section>/",
        views.club_dashboard_section,
        name="club_dashboard_section",
    ),
    path("<slug:club_slug>/update/", views.club_update, name="club_update"),
    path("<slug:club_slug>/members/", views.club_members, name="club_members"),
    path(
        "<slug:club_slug>/invite/",
        views.club_invite_member,
        name="club_invite_member",
    ),
    # Club Events Management
    path("<slug:club_slug>/events/add/", views.club_add_events, name="club_add_events"),
    path(
        "<slug:club_slug>/events/<uuid:event_id>/",
        views.club_event_detail,
        name="club_event_detail",
    ),
    path(
        "<slug:club_slug>/events/<slug:event_slug>/remove/",
        views.club_remove_event,
        name="club_remove_event",
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
    # Team URLs within clubs (using club slug and team slug) - TODO: Implement team views
    # path("<slug:club_slug>/teams/<slug:team_slug>/", views.team_dashboard, name="team_dashboard"),
    # path("<slug:club_slug>/teams/<slug:team_slug>/<str:section>/", views.team_dashboard_section, name="team_dashboard_section"),
    # Legacy team planning URLs - redirects to enhanced system
    path(
        "<slug:club_slug>/allocations/<slug:allocation_slug>/planning/",
        views.clubs_dashboard,  # Redirect to main dashboard
        name="team_planning_dashboard_legacy",
    ),
    path(
        "<slug:club_slug>/allocations/<slug:allocation_slug>/stints/",
        views.clubs_dashboard,  # Redirect to main dashboard
        name="stint_planning_legacy",
    ),
    path(
        "<slug:club_slug>/allocations/<slug:allocation_slug>/stints/update/",
        views.stint_plan_update_legacy,
        name="stint_plan_update",
    ),
    path(
        "<slug:club_slug>/allocations/<slug:allocation_slug>/stints/export/",
        views.stint_plan_export_legacy,
        name="stint_plan_export",
    ),
    # HTMX Partial URLs (within club context)
    path(
        "<slug:club_slug>/members/partial/",
        views.club_members_partial,
        name="club_members_partial",
    ),
    # Legacy signup/allocation partials removed - replaced by enhanced system
    path(
        "<slug:club_slug>/allocations/<slug:allocation_slug>/stints/partial/",
        views.stint_plan_partial_legacy,
        name="stint_plan_partial",
    ),
    
    # === UNIFIED EVENT PARTICIPATION SYSTEM ===
    # Event Signup (replaces old signup system)  
    path('events/<uuid:event_id>/signup/', 
         views.enhanced_event_signup_create, 
         name='event_signup_enhanced'),
    
    # Team Formation Dashboard (replaces old allocation wizard)
    path('events/<uuid:club_event_id>/formation/', 
         views.enhanced_team_formation_dashboard, 
         name='team_formation_dashboard'),
    
    # HTMX API Endpoints for team formation
    path('events/<uuid:club_event_id>/data/', 
         views.formation_dashboard_data, 
         name='formation_dashboard_data'),
    
    path('events/<uuid:club_event_id>/close-signup/', 
         views.close_signup_phase, 
         name='close_signup_phase'),
    
    path('events/<uuid:club_event_id>/generate-suggestions/', 
         views.generate_team_suggestions, 
         name='generate_team_suggestions'),
    
    path('events/<uuid:club_event_id>/create-teams/', 
         views.create_teams_from_suggestions, 
         name='create_teams_from_suggestions'),
    
    path('events/<uuid:club_event_id>/finalize/', 
         views.finalize_teams, 
         name='finalize_teams'),
    
    # Availability & Analytics
    path('events/<uuid:event_id>/availability-heatmap/', 
         views.availability_coverage_heatmap, 
         name='availability_heatmap'),
    
    path('events/<uuid:event_id>/workflow-status/', 
         views.workflow_status, 
         name='workflow_status'),
    
    # Individual Team Formation (for non-club users)
    path('events/<uuid:event_id>/invite/', 
         views.send_signup_invitation, 
         name='send_signup_invitation'),
    
    path('invitations/<str:token>/', 
         views.process_invitation, 
         name='process_invitation'),
    
    # HTMX Partials for dynamic updates
    path('events/<uuid:club_event_id>/partials/participants/', 
         views.participant_list_partial, 
         name='participant_list_partial'),
    
    path('events/<uuid:club_event_id>/partials/suggestions/', 
         views.team_suggestions_partial, 
         name='team_suggestions_partial'),
    
    # Real-time Updates (WebSocket helpers)
    path('events/<uuid:event_id>/notify-signup/', 
         views.notify_signup_update, 
         name='notify_signup_update'),

    path("request-join/<slug:club_slug>/", views.request_join_club, name="request_join_club"),
]
