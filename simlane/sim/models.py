import uuid

from django.db import models

from simlane.users.models import User


# Enums
class UserRole(models.TextChoices):
    CLUB_ADMIN = "CLUB_ADMIN", "Club Admin"
    CLUB_MANAGER = "CLUB_MANAGER", "Club Manager"
    CLUB_MEMBER = "CLUB_MEMBER", "Club Member"
    ADMIN = "ADMIN", "Admin"
    USER = "USER", "User"
    SUBSCRIBER = "SUBSCRIBER", "Subscriber"


class EventStatus(models.TextChoices):
    DRAFT = "DRAFT", "Draft"
    SCHEDULED = "SCHEDULED", "Scheduled"
    ONGOING = "ONGOING", "Ongoing"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"


class RatingCategory(models.TextChoices):
    SKILL = "SKILL", "Skill"
    SAFETY = "SAFETY", "Safety"
    CONSISTENCY = "CONSISTENCY", "Consistency"
    OTHER = "OTHER", "Other"


class RacingDiscipline(models.TextChoices):
    ROAD = "ROAD", "Road"
    SPORTS_CAR = "SPORTS_CAR", "Sports Car"
    FORMULA = "FORMULA", "Formula"
    OVAL = "OVAL", "Oval"
    DIRT_ROAD = "DIRT_ROAD", "Dirt Road"
    DIRT_OVAL = "DIRT_OVAL", "Dirt Oval"
    OTHER = "OTHER", "Other"


class TrackType(models.TextChoices):
    ROAD = "ROAD", "Road"
    OVAL = "OVAL", "Oval"
    STREET = "STREET", "Street"
    RALLY = "RALLY", "Rally"
    DRAG = "DRAG", "Drag"
    OTHER = "OTHER", "Other"


class FuelUnit(models.TextChoices):
    LITER = "LITER", "Liter"
    GALLON = "GALLON", "Gallon"
    KG = "KG", "Kg"


class SessionType(models.TextChoices):
    WARMUP = "WARMUP", "Warmup"
    PRACTICE = "PRACTICE", "Practice"
    QUALIFYING = "QUALIFYING", "Qualifying"
    RACE = "RACE", "Race"


class EventType(models.TextChoices):
    OFFICIAL = "OFFICIAL", "Official"
    SPECIAL = "SPECIAL", "Special"
    HOSTED = "HOSTED", "Hosted"
    CUSTOM = "CUSTOM", "Custom"


class Simulator(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    logo_url = models.URLField(blank=True)
    logo = models.ImageField(upload_to="simulators/logos/", blank=True, null=True)
    icon = models.ImageField(upload_to="simulators/icons/", blank=True, null=True)
    website = models.URLField(blank=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class SimProfile(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sim_profiles",
    )
    simulator = models.ForeignKey(
        Simulator,
        on_delete=models.CASCADE,
        related_name="sim_profiles",
    )
    profile_name = models.CharField(max_length=255)
    external_data_id = models.CharField(max_length=255, blank=True)
    is_verified = models.BooleanField(default=False)
    last_active = models.DateTimeField(null=True, blank=True)
    preferences = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "simulator", "profile_name"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["simulator"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.simulator.name} - {self.profile_name}"


class PitData(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    drive_through_loss_sec = models.FloatField()
    stop_go_base_loss_sec = models.FloatField()
    stop_go_stationary_sec = models.FloatField(null=True, blank=True)
    fuel_unit = models.CharField(max_length=10, choices=FuelUnit)
    refuel_flow_rate = models.FloatField()
    tire_change_all_four_sec = models.FloatField()
    tire_then_refuel = models.BooleanField()
    simultaneous_actions = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Pit Data"
        verbose_name_plural = "Pit Data"

    def __str__(self):
        return f"{self.id}"


class CarClass(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    icon_url = models.URLField(blank=True)

    def __str__(self):
        return self.name


class CarModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    manufacturer = models.CharField(max_length=255)
    car_class = models.ForeignKey(
        CarClass,
        on_delete=models.CASCADE,
        related_name="car_models",
    )
    release_year = models.IntegerField(null=True, blank=True)
    default_image_url = models.URLField(blank=True)
    base_specs = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ["manufacturer", "name"]
        indexes = [
            models.Index(fields=["car_class"]),
        ]

    def __str__(self):
        return f"{self.manufacturer} {self.name}"


class SimCar(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    simulator = models.ForeignKey(
        Simulator,
        on_delete=models.CASCADE,
        related_name="sim_cars",
    )
    car_model = models.ForeignKey(
        CarModel,
        on_delete=models.CASCADE,
        related_name="sim_cars",
    )
    sim_api_id = models.CharField(max_length=255)
    bop_version = models.CharField(max_length=50, blank=True)
    image_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    pit_data = models.OneToOneField(
        PitData,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sim_car",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["simulator", "sim_api_id"], ["simulator", "car_model"]]
        indexes = [
            models.Index(fields=["car_model"]),
        ]

    def __str__(self):
        return f"{self.simulator.name} - {self.car_model.name}"


class TrackModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    country = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    default_image_url = models.URLField(blank=True)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ["name", "country"]

    def __str__(self):
        return f"{self.name} ({self.country})" if self.country else self.name


class SimTrack(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    simulator = models.ForeignKey(
        Simulator,
        on_delete=models.CASCADE,
        related_name="sim_tracks",
    )
    track_model = models.ForeignKey(
        TrackModel,
        on_delete=models.CASCADE,
        related_name="sim_tracks",
    )
    sim_api_id = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    is_laser_scanned = models.BooleanField(null=True, blank=True)
    image_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [["simulator", "sim_api_id"], ["simulator", "track_model"]]
        indexes = [
            models.Index(fields=["track_model"]),
        ]

    def __str__(self):
        return f"{self.simulator.name} - {self.track_model.name}"


class SimLayout(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sim_track = models.ForeignKey(
        SimTrack,
        on_delete=models.CASCADE,
        related_name="layouts",
    )
    layout_code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    type = models.CharField(max_length=20, choices=TrackType)
    length_km = models.FloatField()
    image_url = models.URLField(blank=True)
    pit_data = models.OneToOneField(
        PitData,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sim_layout",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["sim_track", "layout_code"]
        indexes = [
            models.Index(fields=["sim_track"]),
        ]

    def __str__(self):
        return f"{self.sim_track.name} - {self.layout_code}"


class Series(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)
    website = models.URLField(blank=True)
    is_team_event = models.BooleanField(default=False)
    min_drivers_per_entry = models.IntegerField(null=True, blank=True)
    max_drivers_per_entry = models.IntegerField(null=True, blank=True)
    fair_share_pct = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Series"
        verbose_name_plural = "Series"

    def __str__(self):
        return self.name


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    series = models.ForeignKey(
        Series,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    simulator = models.ForeignKey(
        Simulator,
        on_delete=models.CASCADE,
        related_name="events",
    )
    sim_layout = models.ForeignKey(
        SimLayout,
        on_delete=models.CASCADE,
        related_name="events",
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=EventType, default=EventType.CUSTOM)
    status = models.CharField(
        max_length=20,
        choices=EventStatus,
        default=EventStatus.DRAFT,
    )
    event_date = models.DateTimeField(null=True, blank=True)
    registration_deadline = models.DateTimeField(null=True, blank=True)
    is_team_event = models.BooleanField(null=True, blank=True)
    min_drivers_per_entry = models.IntegerField(null=True, blank=True)
    max_drivers_per_entry = models.IntegerField(null=True, blank=True)
    fair_share_pct = models.FloatField(null=True, blank=True)
    min_pit_stops = models.IntegerField(null=True, blank=True)
    required_compounds = models.JSONField(null=True, blank=True)
    weather = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["simulator"]),
            models.Index(fields=["series"]),
            models.Index(fields=["status"]),
            models.Index(fields=["type"]),
        ]

    def __str__(self):
        return self.name


class EventSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="sessions")
    session_type = models.CharField(max_length=20, choices=SessionType)
    duration = models.IntegerField()  # Duration in minutes
    in_game_time = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["session_type"]),
        ]

    def __str__(self):
        return f"{self.event.name} - {self.session_type}"


class EventClass(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="classes")
    name = models.CharField(max_length=255)
    car_class = models.ForeignKey(
        CarClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="event_classes",
    )
    allowed_sim_car_ids = models.JSONField(null=True, blank=True)
    bop_overrides = models.JSONField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["car_class"]),
        ]

    def __str__(self):
        return f"{self.event.name} - {self.name}"


class EventInstance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="instances")
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    registration_open = models.DateTimeField()
    registration_ends = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["start_time"]),
            models.Index(fields=["registration_open"]),
            models.Index(fields=["registration_ends"]),
        ]

    def __str__(self):
        return f"{self.event.name} - {self.start_time} - {self.end_time}"


class LapTime(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sim_profile = models.ForeignKey(
        SimProfile,
        on_delete=models.CASCADE,
        related_name="lap_times",
    )
    sim_layout = models.ForeignKey(
        SimLayout,
        on_delete=models.CASCADE,
        related_name="lap_times",
    )
    lap_time_ms = models.IntegerField()
    rating_at_time = models.FloatField(null=True, blank=True)
    is_valid = models.BooleanField(default=True)
    fuel_level = models.FloatField(null=True, blank=True)
    tire_wear = models.JSONField(null=True, blank=True)
    setup = models.JSONField(null=True, blank=True)
    video_url = models.URLField(blank=True)
    notes = models.TextField(blank=True)
    conditions = models.JSONField(null=True, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["sim_profile"]),
            models.Index(fields=["sim_layout"]),
            models.Index(fields=["recorded_at"]),
        ]

    def __str__(self):
        return (
            f"{self.sim_profile.user.username} - "
            f"{self.sim_layout.name} - "
            f"{self.lap_time_ms}ms"
        )


class RatingSystem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    simulator = models.ForeignKey(
        Simulator,
        on_delete=models.CASCADE,
        related_name="rating_systems",
    )
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=255)
    category = models.CharField(max_length=20, choices=RatingCategory)
    min_value = models.FloatField(null=True, blank=True)
    max_value = models.FloatField(null=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = ["simulator", "code"]

    def __str__(self):
        return f"{self.simulator.name} - {self.name}"


class ProfileRating(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sim_profile = models.ForeignKey(
        SimProfile,
        on_delete=models.CASCADE,
        related_name="ratings",
    )
    rating_system = models.ForeignKey(
        RatingSystem,
        on_delete=models.CASCADE,
        related_name="profile_ratings",
    )
    discipline = models.CharField(
        max_length=20,
        choices=RacingDiscipline,
        blank=True,
    )
    value = models.FloatField()
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(
                fields=["sim_profile", "rating_system", "discipline", "recorded_at"],
            ),
        ]

    def __str__(self):
        return (
            f"{self.sim_profile.user.username} - "
            f"{self.rating_system.name} - "
            f"{self.value}"
        )


class WeatherForecast(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_instance = models.ForeignKey(
        EventInstance,
        on_delete=models.CASCADE,
        related_name="weather_forecasts",
    )
    time_offset = models.IntegerField()  # Minutes from event start
    timestamp = models.DateTimeField()
    is_sun_up = models.BooleanField()
    affects_session = models.BooleanField()

    # Temperature and Pressure
    air_temperature = models.FloatField()  # Celsius
    pressure = models.FloatField()  # Hectopascals (hPa)

    # Wind
    wind_speed = models.FloatField()  # Meters per second
    wind_direction = models.IntegerField()  # Degrees (0-359)

    # Precipitation
    precipitation_chance = models.IntegerField()  # Percentage (0-100)
    precipitation_amount = models.FloatField()  # mm/hour
    allow_precipitation = models.BooleanField()

    # Cloud and Humidity
    cloud_cover = models.IntegerField()  # Percentage (0-100)
    relative_humidity = models.IntegerField()  # Percentage (0-100)

    # Metadata
    forecast_version = (
        models.IntegerField()
    )  # 1 for Forecast (hourly), 3 for Timeline (15-min intervals)
    valid_stats = models.BooleanField()  # Whether rain statistics are available
    raw_data = models.JSONField(
        null=True,
        blank=True,
    )  # Complete API response for future use
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["event_instance"]),
            models.Index(fields=["time_offset"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"{self.event_instance.event.name} - {self.time_offset} minutes"
