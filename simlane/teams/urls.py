from django.urls import path

from . import views

app_name = "teams"

urlpatterns = [
    # Clubs Dashboard
    path("", views.clubs_dashboard, name="clubs_dashboard"),
    path("<str:team_name>/", views.club_dashboard, name="club_dashboard"),
    path(
        "<str:team_name>/<str:section>/",
        views.club_dashboard_section,
        name="club_dashboard_section",
    ),
]
