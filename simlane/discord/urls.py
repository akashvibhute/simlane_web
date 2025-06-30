from django.urls import path
from . import views

urlpatterns = [
    path("bot/callback/", views.bot_oauth_callback, name="discord_bot_oauth_callback"),
] 