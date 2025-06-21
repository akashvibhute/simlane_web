# Register your models here.

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Club
from .models import ClubMember
from .models import DriverAvailability
from .models import EventEntry
from .models import PredictedStint
from .models import Team
from .models import TeamMember


@admin.register(Club)
class ClubAdmin(ModelAdmin):
    list_display = ["name", "is_active", "discord_guild_id", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description", "discord_guild_id"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ClubMember)
class ClubMemberAdmin(ModelAdmin):
    list_display = ["user", "club", "role", "created_at"]
    list_filter = ["role", "club", "created_at"]
    search_fields = ["user__username", "user__email", "club__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["user", "club"]

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Show role choices in admin
        if "role" in form.base_fields:
            from .models import ClubRole

            form.base_fields["role"].widget.choices = ClubRole.choices
        return form


@admin.register(Team)
class TeamAdmin(ModelAdmin):
    list_display = ["name", "club", "is_active", "created_at"]
    list_filter = ["club", "is_active", "created_at"]
    search_fields = ["name", "description", "club__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["club"]


@admin.register(TeamMember)
class TeamMemberAdmin(ModelAdmin):
    list_display = ["user", "team", "created_at"]
    list_filter = ["team__club", "created_at"]
    search_fields = ["user__username", "user__email", "team__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["user", "team"]


@admin.register(EventEntry)
class EventEntryAdmin(ModelAdmin):
    list_display = ["user", "event", "sim_car", "team", "event_class", "created_at"]
    list_filter = ["event__simulator", "event__type", "event_class", "created_at"]
    search_fields = ["user__username", "event__name", "team__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["event", "sim_car", "team", "user", "event_class"]


@admin.register(DriverAvailability)
class DriverAvailabilityAdmin(ModelAdmin):
    list_display = ["user", "event_entry", "instance", "available", "created_at"]
    list_filter = ["available", "instance__event", "created_at"]
    search_fields = ["user__username", "event_entry__event__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["event_entry", "user", "instance"]


@admin.register(PredictedStint)
class PredictedStintAdmin(ModelAdmin):
    list_display = ["user", "event_entry", "instance", "stint_order", "created_at"]
    list_filter = ["instance__event", "stint_order", "created_at"]
    search_fields = ["user__username", "event_entry__event__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["event_entry", "user", "instance"]
