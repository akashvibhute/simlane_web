"""simlane URL Configuration."""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
from django.urls import include, path
from django.views import defaults as default_views
from django.views.generic import TemplateView

from simlane.api.main import api

urlpatterns = [
    path("", TemplateView.as_view(template_name="core/home.html"), name="home"),
    path("about/", TemplateView.as_view(template_name="core/about.html"), name="about"),
    # Django Admin, use {% url 'admin:index' %}
    path(settings.ADMIN_URL, admin.site.urls),
    # User management
    path("users/", include("simlane.users.urls", namespace="users")),
    path("accounts/", include("allauth.urls")),
    # Social auth providers
    path("accounts/garage61/", include("simlane.garage61_provider.urls")),
    # Your stuff: custom urls includes go here
    path("", include("simlane.core.urls", namespace="core")),
    path("sim/", include("simlane.sim.urls", namespace="sim")),
    path("teams/", include("simlane.teams.urls", namespace="teams")),
    # API endpoints
    path("api/", api.urls),
    path("api/auth/", include("allauth.headless.urls")),
    # Dashboard routes
    path("dashboard/iracing/", include("simlane.sim.urls", namespace="sim_dashboard")),
    # Media files
    *static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT),
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
