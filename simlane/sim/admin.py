# Register your models here.

from django.contrib import admin
from django.db.models import Count
from unfold.admin import ModelAdmin, TabularInline

from .models import CarClass
from .models import CarModel
from .models import CarRestriction
from .models import Event
from .models import EventClass
from .models import EventResult
from .models import EventSession
from .models import LapTime
from .models import ParticipantResult
from .models import PitData
from .models import ProfileRating
from .models import RatingSystem
from .models import Season
from .models import Series
from .models import SimCar
from .models import SimLayout
from .models import SimProfile
from .models import SimProfileCarOwnership
from .models import SimProfileTrackOwnership
from .models import SimTrack
from .models import Simulator
from .models import TeamResult
from .models import TimeSlot
from .models import TrackModel
from .models import WeatherForecast


# Inline classes for tabular displays
class SeasonInline(TabularInline):
    model = Season
    extra = 0
    readonly_fields = ["external_season_id", "created_at", "updated_at"]
    fields = [
        "name", "external_season_id", "start_date", "end_date", 
        "active", "complete", "created_at"
    ]
    show_change_link = True
    ordering = ["-start_date"]


class EventInline(TabularInline):
    model = Event
    extra = 0
    readonly_fields = ["created_at", "updated_at"]
    fields = [
        "name", "simulator", "type", "status",
        "start_date", "end_date", "round_number"
    ]
    show_change_link = True
    raw_id_fields = ["simulator", "sim_layout"]
    ordering = ["start_date", "round_number"]


@admin.register(Simulator)
class SimulatorAdmin(ModelAdmin):
    list_display = ["name", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SimProfile)
class SimProfileAdmin(ModelAdmin):
    list_display = [
        "profile_name",
        "linked_user",
        "simulator",
        "is_verified",
        "is_public",
        "last_active",
    ]
    list_filter = ["simulator", "is_verified", "is_public", "created_at"]
    search_fields = [
        "profile_name",
        "linked_user__username",
        "linked_user__email",
        "sim_api_id",
    ]
    readonly_fields = ["created_at", "updated_at", "linked_at"]
    raw_id_fields = ["linked_user", "simulator"]

    def get_queryset(self, request):
        """Optimize queryset for admin"""
        return super().get_queryset(request).select_related("linked_user", "simulator")


@admin.register(PitData)
class PitDataAdmin(ModelAdmin):
    list_display = ["id", "fuel_unit", "drive_through_loss_sec", "refuel_flow_rate"]
    list_filter = ["fuel_unit", "tire_then_refuel", "simultaneous_actions"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(CarClass)
class CarClassAdmin(ModelAdmin):
    list_display = ["name", "category"]
    search_fields = ["name", "category"]


@admin.register(CarModel)
class CarModelAdmin(ModelAdmin):
    list_display = ["name", "manufacturer", "category", "release_year"]
    list_filter = ["category", "release_year"]
    search_fields = ["name", "manufacturer"]


@admin.register(SimCar)
class SimCarAdmin(ModelAdmin):
    list_display = ["car_model", "simulator", "sim_api_id", "is_active"]
    list_filter = ["simulator", "is_active", "created_at"]
    search_fields = ["car_model__name", "car_model__manufacturer", "sim_api_id"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["simulator", "car_model", "pit_data"]


@admin.register(TrackModel)
class TrackModelAdmin(ModelAdmin):
    list_display = ["name", "country", "location"]
    list_filter = ["country"]
    search_fields = ["name", "country", "location"]


@admin.register(SimTrack)
class SimTrackAdmin(ModelAdmin):
    list_display = [
        "display_name",
        "track_model",
        "simulator",
        "is_laser_scanned",
        "is_active",
    ]
    list_filter = ["simulator", "is_laser_scanned", "is_active", "created_at"]
    search_fields = ["display_name", "track_model__name", "sim_api_id"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["simulator", "track_model"]


@admin.register(SimLayout)
class SimLayoutAdmin(ModelAdmin):
    list_display = ["name", "sim_track", "layout_code", "type", "length_km"]
    list_filter = ["type", "created_at"]
    search_fields = ["name", "layout_code", "sim_track__display_name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["sim_track", "pit_data"]


@admin.register(Series)
class SeriesAdmin(ModelAdmin):
    list_display = [
        "name",
        "seasons_count",
    ]
    list_filter = ["created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [SeasonInline]

    def get_queryset(self, request):
        """Optimize queryset for admin with season count"""
        return super().get_queryset(request).annotate(
            seasons_count=Count('seasons')
        )

    def seasons_count(self, obj):
        """Display season count for each series"""
        return obj.seasons_count
    seasons_count.short_description = "Seasons"
    seasons_count.admin_order_field = "seasons_count"


@admin.register(Event)
class EventAdmin(ModelAdmin):
    list_display = ["name", "series", "simulator", "type", "status", "start_date"]
    list_filter = ["type", "status", "simulator", "is_team_event", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["series", "simulator", "sim_layout"]
    date_hierarchy = "start_date"


@admin.register(EventSession)
class EventSessionAdmin(ModelAdmin):
    list_display = ["event", "session_type", "duration", "in_game_time"]
    list_filter = ["session_type", "created_at"]
    search_fields = ["event__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["event"]


@admin.register(EventClass)
class EventClassAdmin(ModelAdmin):
    list_display = [
        "name",
        "event",
        "car_class",
        "class_order",
        "min_entries",
        "max_entries",
        "inherit_series_restrictions",
    ]
    list_filter = ["event", "car_class", "inherit_series_restrictions"]
    search_fields = ["name", "event__name", "car_class__name"]
    raw_id_fields = ["event", "car_class"]
    ordering = ["event", "class_order"]


@admin.register(TimeSlot)
class TimeSlotAdmin(ModelAdmin):
    list_display = [
        "event",
        "start_time",
        "end_time",
        "registration_open",
        "registration_ends",
    ]
    list_filter = ["created_at"]
    search_fields = ["event__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["event"]
    date_hierarchy = "start_time"


@admin.register(LapTime)
class LapTimeAdmin(ModelAdmin):
    list_display = [
        "sim_profile",
        "sim_layout",
        "lap_time_ms",
        "rating_at_time",
        "is_valid",
        "recorded_at",
    ]
    list_filter = ["is_valid", "sim_layout__sim_track__simulator", "recorded_at"]
    search_fields = ["sim_profile__profile_name", "sim_profile__linked_user__username"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["sim_profile", "sim_layout"]
    date_hierarchy = "recorded_at"


@admin.register(RatingSystem)
class RatingSystemAdmin(ModelAdmin):
    list_display = ["name", "simulator", "code", "category", "min_value", "max_value"]
    list_filter = ["simulator", "category"]
    search_fields = ["name", "code", "description"]
    raw_id_fields = ["simulator"]


@admin.register(ProfileRating)
class ProfileRatingAdmin(ModelAdmin):
    list_display = [
        "sim_profile",
        "rating_system",
        "discipline",
        "value",
        "recorded_at",
    ]
    list_filter = ["rating_system", "discipline", "recorded_at"]
    search_fields = ["sim_profile__profile_name", "sim_profile__linked_user__username"]
    readonly_fields = ["recorded_at"]
    raw_id_fields = ["sim_profile", "rating_system"]
    date_hierarchy = "recorded_at"


@admin.register(WeatherForecast)
class WeatherForecastAdmin(ModelAdmin):
    list_display = [
        "event",
        "timestamp",
        "air_temperature",
        "precipitation_chance",
        "wind_speed",
    ]
    list_filter = [
        "is_sun_up",
        "affects_session",
        "allow_precipitation",
        "forecast_version",
    ]
    search_fields = ["event__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["event"]
    date_hierarchy = "timestamp"


@admin.register(SimProfileCarOwnership)
class SimProfileCarOwnershipAdmin(admin.ModelAdmin):
    list_display = ("sim_profile", "sim_car", "is_favorite", "acquired_at")
    search_fields = (
        "sim_profile__sim_api_id",
        "sim_profile__profile_name",
        "sim_car__car_model__name",
        "sim_car__simulator__name",
    )
    list_filter = ("is_favorite", "sim_car__simulator")
    autocomplete_fields = ["sim_profile", "sim_car"]


@admin.register(SimProfileTrackOwnership)
class SimProfileTrackOwnershipAdmin(admin.ModelAdmin):
    list_display = ("sim_profile", "sim_track", "is_favorite", "acquired_at")
    search_fields = (
        "sim_profile__sim_api_id",
        "sim_profile__profile_name",
        "sim_track__track_model__name",
        "sim_track__simulator__name",
    )
    list_filter = ("is_favorite", "sim_track__simulator")
    autocomplete_fields = ["sim_profile", "sim_track"]


@admin.register(EventResult)
class EventResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "time_slot",
        "subsession_id",
        "num_drivers",
        "start_time",
        "end_time",
        "is_processed",
    )
    search_fields = ("subsession_id", "time_slot__id")
    list_filter = ("is_processed", "start_time")
    readonly_fields = ("results_fetched_at",)


@admin.register(TeamResult)
class TeamResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event_result",
        "team",
        "finish_position",
        "car_class_name",
        "champ_points",
        "is_dnf",
    )
    search_fields = ("team__name", "event_result__subsession_id")
    list_filter = ("car_class_name", "finish_position")


@admin.register(ParticipantResult)
class ParticipantResultAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "sim_profile",
        "event_result",
        "team_result",
        "finish_position",
        "car_class_name",
        "champ_points",
        "is_dnf",
    )
    search_fields = (
        "sim_profile__user__username",
        "event_result__subsession_id",
        "team_result__team__name",
    )
    list_filter = ("car_class_name", "finish_position")


@admin.register(Season)
class SeasonAdmin(ModelAdmin):
    list_display = [
        "series",
        "name",
        "events_count",
        "external_season_id",
        "start_date",
        "end_date",
        "active",
        "complete",
    ]
    list_filter = ["series", "active", "complete", "start_date"]
    search_fields = ["name", "series__name", "external_season_id"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["series"]
    date_hierarchy = "start_date"
    inlines = [EventInline]

    def get_queryset(self, request):
        """Optimize queryset for admin with event count"""
        return super().get_queryset(request).annotate(
            events_count=Count('events')
        )

    def events_count(self, obj):
        """Display event count for each season"""
        return obj.events_count
    events_count.short_description = "Events"
    events_count.admin_order_field = "events_count"


@admin.register(CarRestriction)
class CarRestrictionAdmin(ModelAdmin):
    list_display = [
        "event",
        "sim_car",
        "max_pct_fuel_fill",
        "power_adjust_pct",
        "weight_penalty_kg",
        "is_fixed_setup",
    ]
    list_filter = [
        "event__series",
        "sim_car__simulator",
        "is_fixed_setup",
    ]
    search_fields = [
        "event__series__name",
        "sim_car__car_model__name",
        "sim_car__sim_api_id",
    ]
    raw_id_fields = ["event", "sim_car"]
