from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import BotCommand
from .models import BotSettings
from .models import DiscordGuild


@admin.register(DiscordGuild)
class DiscordGuildAdmin(ModelAdmin):
    list_display = ["guild_id", "name", "club", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["guild_id", "name", "club__name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(BotCommand)
class BotCommandAdmin(ModelAdmin):
    list_display = [
        "command_name",
        "username",
        "linked_user",
        "guild",
        "success",
        "timestamp",
    ]
    list_filter = ["command_name", "success", "timestamp", "guild"]
    search_fields = ["command_name", "username", "guild__name", "discord_user_id"]
    readonly_fields = ["timestamp", "linked_user"]
    date_hierarchy = "timestamp"

    @admin.display(
        description="Django User",
    )
    def linked_user(self, obj):
        """Show if Discord user is linked to a Django user"""
        django_user = obj.django_user
        if django_user:
            return format_html(
                '<a href="/admin/users/user/{}/change/">{}</a>',
                django_user.id,
                django_user.username,
            )
        return "Not linked"

    def has_add_permission(self, request):
        return False  # These are created automatically by the bot


@admin.register(BotSettings)
class BotSettingsAdmin(ModelAdmin):
    list_display = ["key", "value", "description", "updated_at"]
    search_fields = ["key", "description"]
    readonly_fields = ["created_at", "updated_at"]
