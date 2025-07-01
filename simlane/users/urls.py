from django.urls import path
from django.views.generic import RedirectView

from .views import profile_emails_view
from .views import profile_general_view
from .views import profile_password_view
from .views import profile_sessions_view
from .views import profile_sim_profiles_view
from .views import profile_social_accounts_view
from .views import profile_view
from .views import sim_profile_add_view
from .views import sim_profile_disconnect_view
from .views import sim_profile_edit_view
from .views import user_detail_view
from .views import user_redirect_view
from .views import user_update_view

app_name = "users"
urlpatterns = [
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("~update/", view=user_update_view, name="update"),
    # New unified profile section
    path("profile/", view=profile_view, name="profile"),
    path("profile/general/", view=profile_general_view, name="profile_general"),
    path(
        "profile/sim-profiles/",
        view=profile_sim_profiles_view,
        name="profile_sim_profiles",
    ),
    # Moved sim profile management routes under profile section
    path("profile/sim-profiles/add/", view=sim_profile_add_view, name="sim_profile_add"),
    path(
        "profile/sim-profiles/<uuid:profile_id>/edit/",
        view=sim_profile_edit_view,
        name="sim_profile_edit",
    ),
    path(
        "profile/sim-profiles/<uuid:profile_id>/disconnect/",
        view=sim_profile_disconnect_view,
        name="sim_profile_disconnect",
    ),
    path("profile/emails/", view=profile_emails_view, name="profile_emails"),
    path(
        "profile/social-accounts/",
        view=profile_social_accounts_view,
        name="profile_social_accounts",
    ),
    path("profile/password/", view=profile_password_view, name="profile_password"),
    path("profile/sessions/", view=profile_sessions_view, name="profile_sessions"),
    # Legacy routes - redirect to new profile section for backward compatibility
    path(
        "sim-profiles/",
        RedirectView.as_view(url="/users/profile/sim-profiles/", permanent=True),
        name="sim_profiles",
    ),
    path(
        "sim-profiles/add/",
        RedirectView.as_view(url="/users/profile/sim-profiles/add/", permanent=True),
        name="legacy_sim_profile_add",
    ),
    path(
        "sim-profiles/<uuid:profile_id>/edit/",
        RedirectView.as_view(url="/users/profile/sim-profiles/%(profile_id)s/edit/", permanent=True),
        name="legacy_sim_profile_edit",
    ),
    path(
        "sim-profiles/<uuid:profile_id>/disconnect/",
        RedirectView.as_view(url="/users/profile/sim-profiles/%(profile_id)s/disconnect/", permanent=True),
        name="legacy_sim_profile_disconnect",
    ),
    path("<str:username>/", view=user_detail_view, name="detail"),
]
