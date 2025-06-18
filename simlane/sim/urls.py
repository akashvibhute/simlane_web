from django.urls import path

from . import views

app_name = "sim"

urlpatterns = [
    path("fov-calculator/", views.fov_calculator, name="fov_calculator"),
]
