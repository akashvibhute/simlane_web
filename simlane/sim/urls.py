from django.urls import path

from . import views

app_name = "sim"

urlpatterns = [
    # iRacing Dashboard
    path("", views.iracing_dashboard, name="iracing_dashboard"),
    path(
        "<str:section>/",
        views.iracing_dashboard_section,
        name="iracing_dashboard_section",
    ),
]
