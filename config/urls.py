"""simlane URL Configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include
from django.urls import path
from django.views import defaults as default_views

from simlane.api.main import api
from simlane.sim.urls import cars_patterns
from simlane.sim.urls import dashboard_patterns
from simlane.sim.urls import events_patterns
from simlane.sim.urls import profiles_patterns
from simlane.sim.urls import tracks_patterns
from simlane.users.views import auth_reset_password_from_key_view
from simlane.users.views import auth_reset_password_view
from simlane.users.views import auth_signup_view
from simlane.users.views import auth_socialaccount_login_error_view
from simlane.users.views import auth_verify_email_view

urlpatterns = [
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("users/", include("simlane.users.urls", namespace="users")),
    path("accounts/", include("allauth.urls")),
    # Social auth providers
    path("accounts/garage61/", include("simlane.garage61_provider.urls")),
    # Auth endpoints for headless/web compatibility
    path(
        "auth/verify-email/<str:key>/", auth_verify_email_view, name="auth_verify_email"
    ),
    path("auth/reset-password/", auth_reset_password_view, name="auth_reset_password"),
    path(
        "auth/reset-password/<str:key>/",
        auth_reset_password_from_key_view,
        name="auth_reset_password_from_key",
    ),
    path("auth/signup/", auth_signup_view, name="auth_signup"),
    path(
        "auth/provider/callback/",
        auth_socialaccount_login_error_view,
        name="auth_socialaccount_login_error",
    ),
    # Your stuff: custom urls includes go here
    path("", include("simlane.core.urls", namespace="core")),
    path("teams/", include("simlane.teams.urls", namespace="teams")),
    path("billing/", include("simlane.billing.urls", namespace="billing")),
    # Top-level drivers and dashboard
    path("drivers/", include((profiles_patterns, "drivers"), namespace="drivers")),
    path(
        "dashboard/", include((dashboard_patterns, "dashboard"), namespace="dashboard")
    ),
    # Top-level cars, tracks, and events pages
    path("cars/", include(cars_patterns)),
    path("tracks/", include(tracks_patterns)),
    path("events/", include((events_patterns, "events"), namespace="events")),
    # Sim app (for any remaining sim-specific functionality)
    path("sim/", include("simlane.sim.urls", namespace="sim")),
    # API endpoints
    path("api/", api.urls),
    path("api/auth/", include("allauth.headless.urls")),
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
    path("discord/", include("simlane.discord.urls")),
    # New club dashboard URLs (revamped CBV structure)
    path("clubs/", include("simlane.teams.dashboard_urls", namespace="clubs")),
]
if settings.DEBUG:
    # Static file serving when using Gunicorn + Uvicorn for local web socket development
    urlpatterns += staticfiles_urlpatterns()

if settings.DEBUG:
    # This allows the error pages to be debugged during development, just visit
    # these url in browser to see how these error pages look like.
    urlpatterns += [
        path(
            "400/",
            default_views.bad_request,
            kwargs={"exception": Exception("Bad Request!")},
        ),
        path(
            "403/",
            default_views.permission_denied,
            kwargs={"exception": Exception("Permission Denied")},
        ),
        path(
            "404/",
            default_views.page_not_found,
            kwargs={"exception": Exception("Page not Found")},
        ),
        path("500/", default_views.server_error),
    ]
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
