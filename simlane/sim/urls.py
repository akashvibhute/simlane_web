from django.urls import path, include

from . import views

app_name = "sim"

urlpatterns = [
    # Public sim profile discovery
    path("profiles/", include([
        path("", views.profiles_list, name="profiles_list"),
        path("search/", views.profiles_search, name="profiles_search"),
        path("<slug:simulator_slug>/", views.profiles_by_simulator, name="profiles_by_simulator"),
        path("<slug:simulator_slug>/<str:profile_identifier>/", views.profile_detail, name="profile_detail"),
    ])),
    
    # Dashboard views (per-simulator dashboards)
    path("dashboard/", include([
        path("", views.dashboard_home, name="dashboard_home"),
        path("<slug:simulator_slug>/", views.simulator_dashboard, name="simulator_dashboard"),
        path("<slug:simulator_slug>/<str:section>/", views.simulator_dashboard_section, name="simulator_dashboard_section"),
    ])),
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
    path("<slug:track_slug>/<slug:layout_slug>/", views.layout_detail, name="layout_detail"),
]
