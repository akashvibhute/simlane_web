from django.db import models


class DiscordGuild(models.Model):
    """Discord Guild (Server) information"""

    guild_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    club = models.OneToOneField(
        "teams.Club",
        on_delete=models.CASCADE,
        related_name="discord_guild",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Discord Guild"
        verbose_name_plural = "Discord Guilds"

    def __str__(self):
        return f"{self.name} ({self.guild_id})"


class BotCommand(models.Model):
    """Log of bot commands executed"""

    command_name = models.CharField(max_length=100)
    discord_user_id = models.CharField(max_length=50)  # Discord user ID
    username = models.CharField(max_length=100)  # Discord username at time of command
    guild = models.ForeignKey(DiscordGuild, on_delete=models.CASCADE)
    channel_id = models.CharField(max_length=50)
    arguments = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bot Command"
        verbose_name_plural = "Bot Commands"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.command_name} by {self.username} in {self.guild.name}"

    @property
    def django_user(self):
        """Get the Django user if they've linked their Discord account"""
        from allauth.socialaccount.models import SocialAccount

        try:
            social_account = SocialAccount.objects.get(
                provider="discord",
                uid=self.discord_user_id,
            )
            return social_account.user
        except SocialAccount.DoesNotExist:
            return None


class BotSettings(models.Model):
    """Global bot settings"""

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bot Setting"
        verbose_name_plural = "Bot Settings"

    def __str__(self):
        return self.key
