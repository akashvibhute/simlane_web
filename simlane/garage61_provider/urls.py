"""URL patterns for Garage61 OAuth2 provider"""

from django.urls import path

from . import views

app_name = "garage61"

urlpatterns = [
    path("login/", views.oauth2_login, name="garage61_login"),
    path("login/callback/", views.oauth2_callback, name="garage61_callback"),
]
