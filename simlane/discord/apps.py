from django.apps import AppConfig


class DiscordConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "simlane.discord"
    label = "discord_bot"
    
    def ready(self):
        """Import signal handlers when app is ready"""
        import simlane.discord.signals  # noqa: F401