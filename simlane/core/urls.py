from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("contact/", views.contact_view, name="contact"),
    path("contact/success/", views.contact_success, name="contact_success"),
]
