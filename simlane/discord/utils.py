"""Utility functions for Discord bot operations"""

from typing import Any

from allauth.socialaccount.models import SocialAccount
from django.conf import settings
from django.contrib.auth import get_user_model

from .models import BotSettings
from .models import DiscordGuild

User = get_user_model()


def get_bot_setting(key: str, default: Any = None) -> Any:
    """Get a bot setting from the database"""
    try:
        setting = BotSettings.objects.get(key=key)
        return setting.value
    except BotSettings.DoesNotExist:
        return default


def set_bot_setting(key: str, value: str, description: str = "") -> BotSettings:
    """Set a bot setting in the database"""
    setting, created = BotSettings.objects.update_or_create(
        key=key,
        defaults={
            "value": value,
            "description": description,
        },
    )
    return setting


def link_discord_guild_to_club(guild_id: str, club_id: str) -> DiscordGuild | None:
    """Link a Discord guild to a racing club"""
    try:
        from simlane.teams.models import Club

        guild = DiscordGuild.objects.get(guild_id=guild_id)
        club = Club.objects.get(id=club_id)

        guild.club = club
        guild.save()

        # Also update the club's discord_guild_id field
        club.discord_guild_id = guild_id
        club.save()

        return guild
    except (DiscordGuild.DoesNotExist, Club.DoesNotExist):
        return None


def get_club_for_guild(guild_id: str):
    """Get the racing club associated with a Discord guild"""
    try:
        guild = DiscordGuild.objects.get(guild_id=guild_id)
        return guild.club
    except DiscordGuild.DoesNotExist:
        return None


def get_django_user_from_discord_id(discord_id: str) -> User | None:
    """Get Django user from Discord ID using allauth SocialAccount"""
    try:
        social_account = SocialAccount.objects.get(
            provider="discord",
            uid=discord_id,
        )
        return social_account.user
    except SocialAccount.DoesNotExist:
        return None


def get_discord_social_account(user: User) -> SocialAccount | None:
    """Get Discord social account for a Django user"""
    try:
        return SocialAccount.objects.get(
            user=user,
            provider="discord",
        )
    except SocialAccount.DoesNotExist:
        return None


def is_bot_configured() -> bool:
    """Check if the Discord bot is properly configured"""
    return bool(getattr(settings, "DISCORD_BOT_TOKEN", ""))


def get_bot_status_info() -> dict[str, Any]:
    """Get bot status information"""
    return {
        "configured": is_bot_configured(),
        "token_set": bool(getattr(settings, "DISCORD_BOT_TOKEN", "")),
        "guilds_count": DiscordGuild.objects.filter(is_active=True).count(),
        "total_guilds": DiscordGuild.objects.count(),
        "discord_users_count": SocialAccount.objects.filter(provider="discord").count(),
    }
