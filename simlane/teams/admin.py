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


# NEW ADMIN CONFIGURATIONS FOR CLUB MANAGEMENT

from .models import (
    ClubInvitation, ClubEvent, EventSignup, EventSignupAvailability,
    TeamAllocation, TeamAllocationMember, TeamEventStrategy, StintAssignment
)


@admin.register(ClubInvitation)
class ClubInvitationAdmin(ModelAdmin):
    list_display = ["email", "club", "role", "invited_by", "status", "created_at", "expires_at"]
    list_filter = ["role", "club", "created_at", "expires_at"]
    search_fields = ["email", "club__name", "invited_by__username"]
    readonly_fields = ["token", "created_at", "updated_at", "accepted_at", "declined_at"]
    
    def status(self, obj):
        if obj.accepted_at:
            return "Accepted"
        elif obj.declined_at:
            return "Declined"
        elif obj.is_expired():
            return "Expired"
        return "Pending"
    status.short_description = "Status"
    
    actions = ["resend_invitation", "mark_as_expired"]
    
    def resend_invitation(self, request, queryset):
        from .services import ClubInvitationService
        count = 0
        for invitation in queryset:
            if not invitation.accepted_at and not invitation.declined_at:
                ClubInvitationService.send_invitation(
                    invitation.club,
                    invitation.invited_by,
                    invitation.email,
                    invitation.role,
                    invitation.personal_message
                )
                count += 1
        self.message_user(request, f"Resent {count} invitations")
    resend_invitation.short_description = "Resend selected invitations"
    
    def mark_as_expired(self, request, queryset):
        from django.utils import timezone
        count = queryset.filter(
            accepted_at__isnull=True,
            declined_at__isnull=True
        ).update(expires_at=timezone.now())
        self.message_user(request, f"Marked {count} invitations as expired")
    mark_as_expired.short_description = "Mark selected invitations as expired"


@admin.register(ClubEvent)
class ClubEventAdmin(ModelAdmin):
    list_display = ["title", "base_event", "club", "status", "signup_deadline", "created_by", "is_active"]
    list_filter = ["status", "club", "is_active", "created_at"]
    search_fields = ["title", "base_event__name", "club__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["club", "base_event", "created_by"]
    
    fieldsets = (
        (None, {
            "fields": ("club", "base_event", "title", "description", "status", "is_active")
        }),
        ("Signup Settings", {
            "fields": ("signup_deadline", "max_participants")
        }),
        ("Team Settings", {
            "fields": ("requires_team_assignment", "auto_assign_teams", "team_size_min", "team_size_max")
        }),
        ("Metadata", {
            "fields": ("created_by", "created_at", "updated_at")
        }),
    )


@admin.register(EventSignup)
class EventSignupAdmin(ModelAdmin):
    list_display = ["user", "club_event", "experience_level", "can_drive", "can_spectate", "assigned_team", "created_at"]
    list_filter = ["experience_level", "can_drive", "can_spectate", "assigned_team", "created_at"]
    search_fields = ["user__username", "club_event__title", "club_event__club__name"]
    readonly_fields = ["created_at", "updated_at", "assigned_at"]
    raw_id_fields = ["club_event", "user", "primary_sim_profile", "assigned_team"]
    filter_horizontal = ["preferred_cars", "backup_cars", "preferred_instances", "preferred_classes"]
    
    fieldsets = (
        (None, {
            "fields": ("club_event", "user", "primary_sim_profile")
        }),
        ("Preferences", {
            "fields": ("can_drive", "can_spectate", "experience_level", "preferred_cars", "backup_cars", 
                      "preferred_instances", "preferred_classes")
        }),
        ("Availability", {
            "fields": ("availability_notes", "max_stint_duration", "min_rest_duration", "notes")
        }),
        ("Team Assignment", {
            "fields": ("assigned_team", "assigned_at", "assignment_locked")
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at")
        }),
    )


@admin.register(EventSignupAvailability)
class EventSignupAvailabilityAdmin(ModelAdmin):
    list_display = ["signup", "event_instance", "available", "preferred_stint_duration", "created_at"]
    list_filter = ["available", "event_instance__event", "created_at"]
    search_fields = ["signup__user__username"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["signup", "event_instance"]


@admin.register(TeamAllocation)
class TeamAllocationAdmin(ModelAdmin):
    list_display = ["team", "club_event", "assigned_sim_car", "created_by", "created_at"]
    list_filter = ["team__club", "assigned_sim_car", "created_at"]
    search_fields = ["team__name", "club_event__title"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["club_event", "team", "assigned_sim_car", "created_by"]
    
    def member_count(self, obj):
        return obj.members.count()
    member_count.short_description = "Members"


@admin.register(TeamAllocationMember)
class TeamAllocationMemberAdmin(ModelAdmin):
    list_display = ["event_signup", "team_allocation", "role", "created_at"]
    list_filter = ["role", "team_allocation__team__club", "created_at"]
    search_fields = ["event_signup__user__username", "team_allocation__team__name"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["team_allocation", "event_signup"]


@admin.register(TeamEventStrategy)
class TeamEventStrategyAdmin(ModelAdmin):
    list_display = ["team", "club_event", "selected_car", "selected_instance", "is_finalized", "created_at"]
    list_filter = ["is_finalized", "club_event__club", "selected_car", "created_at"]
    search_fields = ["team__name", "club_event__title"]
    readonly_fields = ["created_at", "updated_at", "finalized_at", "calculated_pit_windows"]
    raw_id_fields = ["team", "club_event", "team_allocation", "selected_car", "selected_instance", "selected_class", "finalized_by"]
    
    fieldsets = (
        (None, {
            "fields": ("team", "club_event", "team_allocation")
        }),
        ("Event Settings", {
            "fields": ("selected_car", "selected_instance", "selected_class")
        }),
        ("Strategy", {
            "fields": ("strategy_notes", "calculated_pit_windows", "fuel_strategy", "tire_strategy", "weather_contingencies")
        }),
        ("Finalization", {
            "fields": ("is_finalized", "finalized_by", "finalized_at")
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at")
        }),
    )


@admin.register(StintAssignment)
class StintAssignmentAdmin(ModelAdmin):
    list_display = ["driver", "team_strategy", "stint_number", "estimated_start_time", "estimated_duration_minutes", "role", "pit_entry_planned"]
    list_filter = ["role", "pit_entry_planned", "team_strategy__club_event", "created_at"]
    search_fields = ["driver__username", "team_strategy__team__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["team_strategy", "driver", "predicted_stint"]
    ordering = ["team_strategy", "stint_number"]
    
    fieldsets = (
        (None, {
            "fields": ("team_strategy", "driver", "stint_number", "role")
        }),
        ("Timing", {
            "fields": ("estimated_start_time", "estimated_end_time", "estimated_duration_minutes")
        }),
        ("Pit Strategy", {
            "fields": ("pit_entry_planned", "pit_strategy_notes", "fuel_load_start", "fuel_load_end", "tire_compound")
        }),
        ("Links", {
            "fields": ("predicted_stint", "notes")
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at")
        }),
    )
