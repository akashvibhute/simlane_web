"""
iRacing app configuration.
"""

from django.apps import AppConfig


class IracingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "simlane.iracing"
