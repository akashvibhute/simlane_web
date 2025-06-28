from django.urls import path

from . import views

app_name = "sim"

# Main sim app URLs (for any remaining sim-specific functionality)
urlpatterns = [
    # Currently empty - profiles and dashboard moved to root level
    path(
        "refresh-iracing-owned/",
        views.refresh_iracing_owned_content,
        name="refresh_iracing_owned",
    ),
]

# Events patterns - to be included at top level
events_patterns = [
    path("", views.events_list, name="events_list"),
    path("upcoming/", views.upcoming_events_list, name="upcoming_events_list"),
    path("<slug:event_slug>/", views.event_detail, name="event_detail"),
]

# Profiles patterns - to be included at top level
profiles_patterns = [
    path("", views.profiles_list, name="profiles_list"),
    path("search/", views.profiles_search, name="profiles_search"),
    path(
        "search-to-link/", views.profile_search_to_link, name="profile_search_to_link"
    ),
    path(
        "<slug:simulator_slug>/",
        views.profiles_by_simulator,
        name="profiles_by_simulator",
    ),
    path(
        "<slug:simulator_slug>/<str:profile_identifier>/",
        views.profile_detail,
        name="profile_detail",
    ),
    path(
        "<slug:simulator_slug>/<str:profile_identifier>/link/",
        views.profile_link,
        name="profile_link",
    ),
    path(
        "<slug:simulator_slug>/<str:profile_identifier>/unlink/",
        views.profile_unlink,
        name="profile_unlink",
    ),
]

# Dashboard patterns - to be included at top level
dashboard_patterns = [
    path("", views.dashboard_home, name="dashboard_home"),
    path(
        "<slug:simulator_slug>/", views.simulator_dashboard, name="simulator_dashboard"
    ),
    path(
        "<slug:simulator_slug>/<str:section>/",
        views.simulator_dashboard_section,
        name="simulator_dashboard_section",
    ),
]

# Cars patterns - to be included at top level
cars_patterns = [
    path("", views.cars_list, name="cars_list"),
    path("<slug:car_slug>/", views.car_detail, name="car_detail"),
]

# Tracks patterns - to be included at top level
tracks_patterns = [
    path("", views.tracks_list, name="tracks_list"),
    path("<slug:track_slug>/", views.track_detail, name="track_detail"),
    path(
        "<slug:track_slug>/<slug:layout_slug>/",
        views.layout_detail,
        name="layout_detail",
    ),
]
