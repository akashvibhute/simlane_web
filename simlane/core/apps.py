from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "simlane.core"

    def ready(self):
        """Import signals when app is ready"""
        import simlane.core.signals  # noqa: F401
