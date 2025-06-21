from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("about/", views.about_view, name="about"),
    path("privacy/", views.privacy_view, name="privacy"),
    path("terms/", views.terms_view, name="terms"),
    path("contact/", views.contact_view, name="contact"),
    path("contact/success/", views.contact_success, name="contact_success"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
]
