from django.urls import path

from .dashboard_views import (
    OverviewView,
    MembersView,
    TeamsView,
    EventsView,
    RequestsView,
    DiscordSettingsView,
    ClubSettingsView,
)

app_name = "clubs"

urlpatterns = [
    # Root -> overview
    path(
        "<slug:club_slug>/",
        OverviewView.as_view(),
        name="dashboard_root",
    ),
    path("<slug:club_slug>/overview/", OverviewView.as_view(), name="overview"),
    path("<slug:club_slug>/members/", MembersView.as_view(), name="members"),
    path("<slug:club_slug>/teams/", TeamsView.as_view(), name="teams"),
    path("<slug:club_slug>/events/", EventsView.as_view(), name="events"),
    path("<slug:club_slug>/requests/", RequestsView.as_view(), name="requests"),
    path("<slug:club_slug>/discord/", DiscordSettingsView.as_view(), name="discord"),
    path("<slug:club_slug>/settings/", ClubSettingsView.as_view(), name="settings"),
] 