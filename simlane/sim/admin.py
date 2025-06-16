# Register your models here.

from django.contrib import admin

from .models import CarClass
from .models import CarModel
from .models import Event
from .models import EventClass
from .models import EventInstance
from .models import EventSession
from .models import LapTime
from .models import PitData
from .models import ProfileRating
from .models import RatingSystem
from .models import Series
from .models import SimCar
from .models import SimLayout
from .models import SimProfile
from .models import SimTrack
from .models import Simulator
from .models import TrackModel
from .models import WeatherForecast


@admin.register(Simulator)
class SimulatorAdmin(admin.ModelAdmin):
    list_display = ["name", "version", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "version"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(SimProfile)
class SimProfileAdmin(admin.ModelAdmin):
    list_display = ["profile_name", "user", "simulator", "is_active", "last_active"]
    list_filter = ["simulator", "is_active", "created_at"]
    search_fields = ["profile_name", "user__username", "user__email"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["user", "simulator"]


@admin.register(PitData)
class PitDataAdmin(admin.ModelAdmin):
    list_display = ["id", "fuel_unit", "drive_through_loss_sec", "refuel_flow_rate"]
    list_filter = ["fuel_unit", "tire_then_refuel", "simultaneous_actions"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(CarClass)
class CarClassAdmin(admin.ModelAdmin):
    list_display = ["name", "category"]
    search_fields = ["name", "category"]


@admin.register(CarModel)
class CarModelAdmin(admin.ModelAdmin):
    list_display = ["name", "manufacturer", "car_class", "release_year"]
    list_filter = ["car_class", "release_year"]
    search_fields = ["name", "manufacturer"]
    raw_id_fields = ["car_class"]


@admin.register(SimCar)
class SimCarAdmin(admin.ModelAdmin):
    list_display = ["car_model", "simulator", "sim_api_id", "is_active"]
    list_filter = ["simulator", "is_active", "created_at"]
    search_fields = ["car_model__name", "car_model__manufacturer", "sim_api_id"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["simulator", "car_model", "pit_data"]


@admin.register(TrackModel)
class TrackModelAdmin(admin.ModelAdmin):
    list_display = ["name", "country", "location"]
    list_filter = ["country"]
    search_fields = ["name", "country", "location"]


@admin.register(SimTrack)
class SimTrackAdmin(admin.ModelAdmin):
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
class SimLayoutAdmin(admin.ModelAdmin):
    list_display = ["name", "sim_track", "layout_code", "type", "length_km"]
    list_filter = ["type", "created_at"]
    search_fields = ["name", "layout_code", "sim_track__display_name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["sim_track", "pit_data"]


@admin.register(Series)
class SeriesAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "is_team_event",
        "min_drivers_per_entry",
        "max_drivers_per_entry",
    ]
    list_filter = ["is_team_event", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ["name", "series", "simulator", "type", "status", "event_date"]
    list_filter = ["type", "status", "simulator", "is_team_event", "created_at"]
    search_fields = ["name", "description"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["series", "simulator", "sim_layout"]
    date_hierarchy = "event_date"


@admin.register(EventSession)
class EventSessionAdmin(admin.ModelAdmin):
    list_display = ["event", "session_type", "duration", "in_game_time"]
    list_filter = ["session_type", "created_at"]
    search_fields = ["event__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["event"]


@admin.register(EventClass)
class EventClassAdmin(admin.ModelAdmin):
    list_display = ["name", "event", "car_class"]
    list_filter = ["car_class", "event"]
    search_fields = ["name", "event__name"]
    raw_id_fields = ["event", "car_class"]


@admin.register(EventInstance)
class EventInstanceAdmin(admin.ModelAdmin):
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
class LapTimeAdmin(admin.ModelAdmin):
    list_display = [
        "sim_profile",
        "sim_layout",
        "lap_time_ms",
        "rating_at_time",
        "is_valid",
        "recorded_at",
    ]
    list_filter = ["is_valid", "sim_layout__sim_track__simulator", "recorded_at"]
    search_fields = ["sim_profile__profile_name", "sim_profile__user__username"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["sim_profile", "sim_layout"]
    date_hierarchy = "recorded_at"


@admin.register(RatingSystem)
class RatingSystemAdmin(admin.ModelAdmin):
    list_display = ["name", "simulator", "code", "category", "min_value", "max_value"]
    list_filter = ["simulator", "category"]
    search_fields = ["name", "code", "description"]
    raw_id_fields = ["simulator"]


@admin.register(ProfileRating)
class ProfileRatingAdmin(admin.ModelAdmin):
    list_display = [
        "sim_profile",
        "rating_system",
        "discipline",
        "value",
        "recorded_at",
    ]
    list_filter = ["rating_system", "discipline", "recorded_at"]
    search_fields = ["sim_profile__profile_name", "sim_profile__user__username"]
    readonly_fields = ["recorded_at"]
    raw_id_fields = ["sim_profile", "rating_system"]
    date_hierarchy = "recorded_at"


@admin.register(WeatherForecast)
class WeatherForecastAdmin(admin.ModelAdmin):
    list_display = [
        "event_instance",
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
    search_fields = ["event_instance__event__name"]
    readonly_fields = ["created_at", "updated_at"]
    raw_id_fields = ["event_instance"]
    date_hierarchy = "timestamp"
