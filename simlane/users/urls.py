from django.urls import path

from .views import sim_profile_add_view
from .views import sim_profile_delete_view
from .views import sim_profile_edit_view
from .views import sim_profile_toggle_active_view
from .views import sim_profiles_view
from .views import user_detail_view
from .views import user_redirect_view
from .views import user_update_view

app_name = "users"
urlpatterns = [
    path("~redirect/", view=user_redirect_view, name="redirect"),
    path("~update/", view=user_update_view, name="update"),
    path("sim-profiles/", view=sim_profiles_view, name="sim_profiles"),
    path("sim-profiles/add/", view=sim_profile_add_view, name="sim_profile_add"),
    path(
        "sim-profiles/<uuid:profile_id>/edit/",
        view=sim_profile_edit_view,
        name="sim_profile_edit",
    ),
    path(
        "sim-profiles/<uuid:profile_id>/delete/",
        view=sim_profile_delete_view,
        name="sim_profile_delete",
    ),
    path(
        "sim-profiles/<uuid:profile_id>/toggle-active/",
        view=sim_profile_toggle_active_view,
        name="sim_profile_toggle_active",
    ),
    path("<str:username>/", view=user_detail_view, name="detail"),
]
