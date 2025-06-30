from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin

from .models import BotCommand
from .models import BotSettings
from .models import DiscordGuild
from .models import EventDiscordChannel
from .models import DiscordMemberSync
from .models import ClubDiscordSettings
from .tasks import sync_discord_members, cleanup_expired_channels
from .services import DiscordBotService


@admin.register(DiscordGuild)
class DiscordGuildAdmin(ModelAdmin):
    list_display = [
        "guild_id",
        "name",
        "club",
        "is_active",
        "member_count",
        "last_sync_timestamp",
        "created_at",
    ]
    list_filter = ["is_active", "created_at", "member_count"]
    search_fields = ["guild_id", "name", "club__name"]
    readonly_fields = [
        "created_at",
        "updated_at",
        "member_count",
        "last_sync_timestamp",
        "bot_permissions",
    ]
    actions = ["trigger_member_sync", "cleanup_guild_channels", "reset_guild_connection"]

    @admin.action(description="Trigger manual member sync")
    def trigger_member_sync(self, request, queryset):
        for guild in queryset:
            sync_discord_members.apply_async(args=[guild.guild_id, "manual"])
        self.message_user(request, "Manual member sync triggered for selected guild(s).")

    @admin.action(description="Cleanup expired event channels for selected guild(s)")
    def cleanup_guild_channels(self, request, queryset):
        for guild in queryset:
            cleanup_expired_channels.apply_async(args=[guild.guild_id])
        self.message_user(request, "Cleanup tasks scheduled for selected guild(s).")

    @admin.action(description="Reset guild connection (re-fetch guild info)")
    def reset_guild_connection(self, request, queryset):
        for guild in queryset:
            try:
                service = DiscordBotService()
                service.reset_guild_connection(guild)
                self.message_user(request, f"Guild connection reset for {guild.name}.")
            except Exception as e:
                self.message_user(
                    request,
                    f"Error resetting guild {guild.name}: {e}",
                    level=admin.messages.ERROR,
                )


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

    @admin.display(description="Django User")
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


@admin.register(EventDiscordChannel)
class EventDiscordChannelAdmin(ModelAdmin):
    list_display = [
        "event_name",
        "club_name",
        "text_channel_id",
        "status",
        "created_at",
    ]
    list_filter = ["status", "created_at", "guild"]
    search_fields = [
        "event_signup_sheet__event__name",
        "event_signup_sheet__club__name",
        "text_channel_id",
    ]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["archive_selected_channels", "reset_error_state"]

    @admin.display(description="Event Name")
    def event_name(self, obj):
        return obj.event_signup_sheet.event.name

    @admin.display(description="Club Name")
    def club_name(self, obj):
        return obj.event_signup_sheet.club.name

    @admin.action(description="Archive selected event channels")
    def archive_selected_channels(self, request, queryset):
        for channel in queryset:
            channel.archive_channels()
        self.message_user(request, "Selected event channels have been archived.")

    @admin.action(description="Reset error state for selected channels")
    def reset_error_state(self, request, queryset):
        for channel in queryset:
            channel.status = "creating"
            channel.last_error = ""
            channel.error_count = 0
            channel.save(
                update_fields=["status", "last_error", "error_count", "updated_at"]
            )
        self.message_user(request, "Error state reset for selected channels.")

    def has_add_permission(self, request):
        return False  # These are created automatically


@admin.register(DiscordMemberSync)
class DiscordMemberSyncAdmin(ModelAdmin):
    list_display = [
        "guild",
        "sync_type",
        "matched_members",
        "new_club_members",
        "success",
        "sync_timestamp",
    ]
    list_filter = ["sync_type", "success", "sync_timestamp"]
    search_fields = ["guild__name", "guild__guild_id"]
    readonly_fields = ["sync_timestamp", "results"]
    date_hierarchy = "sync_timestamp"
    actions = ["rerun_selected_syncs"]

    @admin.action(description="Re-run selected member sync operations")
    def rerun_selected_syncs(self, request, queryset):
        for sync_record in queryset:
            sync_discord_members.apply_async(
                args=[sync_record.guild.guild_id, sync_record.sync_type]
            )
        self.message_user(request, "Re-run of selected sync operations scheduled.")

    def has_add_permission(self, request):
        return False  # These are created automatically


@admin.register(ClubDiscordSettings)
class ClubDiscordSettingsAdmin(ModelAdmin):
    list_display = [
        "club",
        "auto_create_channels",
        "enable_voice_channels",
        "enable_stint_alerts",
        "updated_at",
    ]
    list_filter = [
        "auto_create_channels",
        "enable_voice_channels",
        "enable_stint_alerts",
    ]
    search_fields = ["club__name"]
    readonly_fields = ["created_at", "updated_at"]
    actions = ["generate_bot_invite_url", "reset_to_defaults"]

    @admin.action(description="Generate bot invite URL for selected club(s)")
    def generate_bot_invite_url(self, request, queryset):
        for settings in queryset:
            try:
                service = DiscordBotService()
                url = service.get_bot_invite_url(settings.club)
                self.message_user(
                    request,
                    f"Invite URL for {settings.club.name}: {url}"
                )
            except Exception as e:
                self.message_user(
                    request,
                    f"Error generating invite URL for {settings.club.name}: {e}",
                    level=admin.messages.ERROR,
                )

    @admin.action(description="Reset Discord settings to defaults for selected club(s)")
    def reset_to_defaults(self, request, queryset):
        for settings in queryset:
            defaults = settings.get_default_notification_preferences()
            settings.notification_preferences = defaults
            settings.auto_create_channels = True
            settings.enable_voice_channels = True
            settings.enable_practice_voice = True
            settings.enable_team_formation_channels = True
            settings.auto_assign_roles = True
            settings.save()
        self.message_user(
            request,
            "Discord settings reset to defaults for selected club(s)."
        )