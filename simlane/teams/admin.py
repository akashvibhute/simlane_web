# Register your models here.

from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import AvailabilityWindow
from .models import Club
from .models import ClubEvent
from .models import ClubInvitation
from .models import ClubMember
from .models import EventParticipation
from .models import EventSignupInvitation
from .models import RaceStrategy
from .models import StintPlan
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
    list_display = ["name", "club", "owner_user", "owner_sim_profile", "is_active", "is_temporary", "created_at"]
    list_filter = ["club", "is_active", "is_temporary", "is_public", "created_at"]
    search_fields = ["name", "description", "club__name", "owner_user__username"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["club", "owner_user", "owner_sim_profile"]


@admin.register(TeamMember)
class TeamMemberAdmin(ModelAdmin):
    list_display = ["user", "team", "role", "status", "created_at"]
    list_filter = ["role", "status", "team__club", "created_at"]
    search_fields = ["user__username", "user__email", "team__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["user", "team"]


# NEW UNIFIED EVENT PARTICIPATION ADMIN

@admin.register(EventParticipation)
class EventParticipationAdmin(ModelAdmin):
    list_display = [
        "get_participant_display",
        "event",
        "participation_type",
        "status",
        "assigned_car",
        "team",
        "created_at"
    ]
    list_filter = [
        "participation_type",
        "status",
        "event__simulator",
        "event__type",
        "created_at"
    ]
    search_fields = [
        "user__username",
        "user__email",
        "team__name",
        "event__name"
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
        "signed_up_at",
        "team_assigned_at",
        "entered_at",
        "confirmed_at",
        "withdrawn_at"
    ]
    raw_id_fields = [
        "event",
        "user",
        "team",
        "preferred_car",
        "backup_car",
        "assigned_car",
        "assigned_class",
        "club_event",
        "signup_invitation"
    ]
    
    @admin.display(description="Participant")
    def get_participant_display(self, obj):
        if obj.user:
            return f"User: {obj.user.username}"
        elif obj.team:
            return f"Team: {obj.team.name}"
        return "No participant"
    
    fieldsets = (
        ("Participant Information", {
            "fields": (
                "event",
                "user",
                "team",
                "participation_type",
                "status",
            )
        }),
        ("Car Selection", {
            "fields": (
                "preferred_car",
                "backup_car",
                "assigned_car",
                "assigned_class",
                "car_number",
                "starting_position",
            )
        }),
        ("Preferences", {
            "fields": (
                "experience_level",
                "max_stint_duration",
                "min_rest_duration",
                "participant_timezone",
            )
        }),
        ("Relationships", {
            "fields": (
                "club_event",
                "signup_invitation",
            )
        }),
        ("Additional Data", {
            "fields": (
                "notes",
                "registration_data",
            ),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": (
                "signed_up_at",
                "team_assigned_at",
                "entered_at",
                "confirmed_at",
                "withdrawn_at",
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",)
        }),
    )


@admin.register(AvailabilityWindow)
class AvailabilityWindowAdmin(ModelAdmin):
    list_display = [
        "participation",
        "start_time",
        "end_time",
        "can_drive",
        "can_spot",
        "preference_level",
        "created_at"
    ]
    list_filter = [
        "can_drive",
        "can_spot",
        "can_strategize",
        "preference_level",
        "created_at"
    ]
    search_fields = [
        "participation__user__username",
        "participation__event__name",
        "notes"
    ]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["participation"]


# RACE STRATEGY AND PLANNING ADMIN

@admin.register(RaceStrategy)
class RaceStrategyAdmin(ModelAdmin):
    list_display = [
        "name",
        "team",
        "event",
        "event_instance",
        "is_active",
        "target_stint_length",
        "created_at"
    ]
    list_filter = ["is_active", "team", "event", "created_at"]
    search_fields = ["name", "team__name", "event__name", "notes"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["team", "event", "event_instance", "created_by"]
    
    fieldsets = (
        ("Strategy Information", {
            "fields": (
                "team",
                "event",
                "event_instance",
                "name",
                "is_active",
            )
        }),
        ("Timing Parameters", {
            "fields": (
                "target_stint_length",
                "min_driver_rest",
                "pit_stop_time",
            )
        }),
        ("Fuel & Tire Strategy", {
            "fields": (
                "fuel_per_stint",
                "fuel_tank_size",
                "tire_change_frequency",
                "tire_compound_strategy",
            )
        }),
        ("Additional Information", {
            "fields": (
                "notes",
                "strategy_data",
            ),
            "classes": ("collapse",)
        }),
        ("Metadata", {
            "fields": (
                "created_by",
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",)
        }),
    )


@admin.register(StintPlan)
class StintPlanAdmin(ModelAdmin):
    list_display = [
        "stint_number",
        "driver",
        "strategy",
        "status",
        "planned_duration",
        "actual_start_time",
        "actual_end_time",
    ]
    list_filter = ["status", "strategy__team", "strategy__event", "created_at"]
    search_fields = ["driver__username", "strategy__team__name", "notes"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["strategy", "driver"]
    
    fieldsets = (
        ("Stint Information", {
            "fields": (
                "strategy",
                "driver",
                "stint_number",
                "status",
            )
        }),
        ("Planned Timing", {
            "fields": (
                "planned_start_lap",
                "planned_end_lap",
                "planned_start_time",
                "planned_duration",
            )
        }),
        ("Actual Timing", {
            "fields": (
                "actual_start_lap",
                "actual_end_lap",
                "actual_start_time",
                "actual_end_time",
            )
        }),
        ("Performance", {
            "fields": (
                "avg_lap_time",
                "fastest_lap_time",
                "incidents_count",
            ),
            "classes": ("collapse",)
        }),
        ("Pit Instructions", {
            "fields": (
                "pit_instructions",
                "notes",
            ),
            "classes": ("collapse",)
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            ),
            "classes": ("collapse",)
        }),
    )


@admin.register(EventSignupInvitation)
class EventSignupInvitationAdmin(ModelAdmin):
    list_display = [
        "team_name",
        "event",
        "organizer_user",
        "invitee_email",
        "status",
        "created_at",
        "expires_at"
    ]
    list_filter = ["status", "event", "created_at", "expires_at"]
    search_fields = ["team_name", "invitee_email", "organizer_user__username", "event__name"]
    readonly_fields = ["token", "created_at", "responded_at"]
    raw_id_fields = ["event", "organizer_user", "invitee_user"]


@admin.register(ClubInvitation)
class ClubInvitationAdmin(ModelAdmin):
    list_display = [
        "email",
        "club",
        "role",
        "invited_by",
        "status",
        "created_at",
        "expires_at",
    ]
    list_filter = ["role", "club", "created_at", "expires_at"]
    search_fields = ["email", "club__name", "invited_by__username"]
    readonly_fields = [
        "token",
        "created_at",
        "updated_at",
        "accepted_at",
        "declined_at",
    ]

    @admin.display(
        description="Status",
    )
    def status(self, obj):
        if obj.accepted_at:
            return "Accepted"
        if obj.declined_at:
            return "Declined"
        if obj.is_expired():
            return "Expired"
        return "Pending"

    actions = ["resend_invitation", "mark_as_expired"]

    @admin.action(
        description="Resend selected invitations",
    )
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
                    invitation.personal_message,
                )
                count += 1
        self.message_user(request, f"Resent {count} invitations")

    @admin.action(
        description="Mark selected invitations as expired",
    )
    def mark_as_expired(self, request, queryset):
        from django.utils import timezone

        count = queryset.filter(
            accepted_at__isnull=True,
            declined_at__isnull=True,
        ).update(expires_at=timezone.now())
        self.message_user(request, f"Marked {count} invitations as expired")


@admin.register(ClubEvent)
class ClubEventAdmin(ModelAdmin):
    list_display = [
        "title",
        "base_event",
        "club",
        "status",
        "signup_deadline",
        "created_by",
        "is_active",
    ]
    list_filter = ["status", "club", "is_active", "created_at"]
    search_fields = ["title", "base_event__name", "club__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["club", "base_event", "created_by"]

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "club",
                    "base_event",
                    "title",
                    "description",
                    "status",
                    "is_active",
                ),
            },
        ),
        (
            "Signup Settings",
            {
                "fields": ("signup_deadline", "max_participants"),
            },
        ),
        (
            "Team Settings",
            {
                "fields": (
                    "requires_team_assignment",
                    "auto_assign_teams",
                    "team_size_min",
                    "team_size_max",
                ),
            },
        ),
        (
            "Metadata",
            {
                "fields": ("created_by", "created_at", "updated_at"),
            },
        ),
    )



