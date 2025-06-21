from django.urls import path

from . import views

app_name = "teams"

urlpatterns = [
    # Clubs Root Dashboard
    path("", views.clubs_dashboard, name="clubs_dashboard"),
    
    # Club Management URLs (using club slug)
    path("create/", views.club_create, name="club_create"),
    path("<slug:club_slug>/", views.club_dashboard, name="club_dashboard"),
    path("<slug:club_slug>/<str:section>/", views.club_dashboard_section, name="club_dashboard_section"),
    path("<slug:club_slug>/update/", views.club_update, name="club_update"),
    path("<slug:club_slug>/members/", views.club_members, name="club_members"),
    path("<slug:club_slug>/invite/", views.club_invite_member, name="club_invite_member"),
    
    # Club Events Management
    path("<slug:club_slug>/events/add/", views.club_add_events, name="club_add_events"),
    path("<slug:club_slug>/events/<uuid:event_id>/remove/", views.club_remove_event, name="club_remove_event"),
    
    # Club Invitation URLs (token-based, no club needed in URL)
    path("invite/<str:token>/accept/", views.club_invitation_accept, name="club_invitation_accept"),
    path("invite/<str:token>/decline/", views.club_invitation_decline, name="club_invitation_decline"),
    
    # Team URLs within clubs (using club slug and team slug) - TODO: Implement team views
    # path("<slug:club_slug>/teams/<slug:team_slug>/", views.team_dashboard, name="team_dashboard"),
    # path("<slug:club_slug>/teams/<slug:team_slug>/<str:section>/", views.team_dashboard_section, name="team_dashboard_section"),
    
    # Event Signup URLs (within clubs)
    path("<slug:club_slug>/signups/create/", views.event_signup_create, name="event_signup_create"),
    path("<slug:club_slug>/signups/<uuid:signup_id>/", views.event_signup_detail, name="event_signup_detail"),
    path("<slug:club_slug>/signups/<uuid:signup_id>/join/", views.event_signup_join, name="event_signup_join"),
    path("<slug:club_slug>/signups/<uuid:signup_id>/entries/<uuid:entry_id>/update/", views.event_signup_update, name="event_signup_update"),
    path("<slug:club_slug>/signups/<uuid:signup_id>/close/", views.event_signup_close, name="event_signup_close"),
    
    # Team Allocation URLs (within club context)
    path("<slug:club_slug>/signups/<uuid:signup_id>/allocate/", views.team_allocation_wizard, name="team_allocation_wizard"),
    path("<slug:club_slug>/signups/<uuid:signup_id>/allocate/preview/", views.team_allocation_preview, name="team_allocation_preview"),
    path("<slug:club_slug>/signups/<uuid:signup_id>/allocate/create/", views.team_allocation_create, name="team_allocation_create"),
    path("<slug:club_slug>/allocations/<uuid:allocation_id>/update/", views.team_allocation_update, name="team_allocation_update"),
    
    # Team Planning URLs (within club context)
    path("<slug:club_slug>/allocations/<uuid:allocation_id>/planning/", views.team_planning_dashboard, name="team_planning_dashboard"),
    path("<slug:club_slug>/allocations/<uuid:allocation_id>/stints/", views.stint_planning, name="stint_planning"),
    path("<slug:club_slug>/allocations/<uuid:allocation_id>/stints/update/", views.stint_plan_update, name="stint_plan_update"),
    path("<slug:club_slug>/allocations/<uuid:allocation_id>/stints/export/", views.stint_plan_export, name="stint_plan_export"),
    
    # HTMX Partial URLs (within club context)
    path("<slug:club_slug>/members/partial/", views.club_members_partial, name="club_members_partial"),
    path("<slug:club_slug>/signups/<uuid:signup_id>/entries/partial/", views.signup_entries_partial, name="signup_entries_partial"),
    path("<slug:club_slug>/signups/<uuid:signup_id>/allocate/partial/", views.team_allocation_partial, name="team_allocation_partial"),
    path("<slug:club_slug>/allocations/<uuid:allocation_id>/stints/partial/", views.stint_plan_partial, name="stint_plan_partial"),
]
