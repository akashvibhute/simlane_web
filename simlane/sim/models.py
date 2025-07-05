import uuid

from django.contrib.postgres.fields import ArrayField
from django.db import models
from django.utils.text import slugify

from simlane.users.models import User

# # Enums
# class UserRole(models.TextChoices):
#     CLUB_ADMIN = "CLUB_ADMIN", "Club Admin"
#     CLUB_MANAGER = "CLUB_MANAGER", "Club Manager"
#     CLUB_MEMBER = "CLUB_MEMBER", "Club Member"
#     ADMIN = "ADMIN", "Admin"
#     USER = "USER", "User"
#     SUBSCRIBER = "SUBSCRIBER", "Subscriber"


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
    DIRT_ROAD = "DIRT_ROAD", "Dirt Road"
    DIRT_OVAL = "DIRT_OVAL", "Dirt Oval"
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


class EventSource(models.TextChoices):
    OFFICIAL = "OFFICIAL", "Official Simulator Event"
    CLUB = "CLUB", "Club-Organized Event"
    USER = "USER", "User-Created Event"


class EventVisibility(models.TextChoices):
    PUBLIC = "PUBLIC", "Public - Anyone can view and join"
    UNLISTED = "UNLISTED", "Unlisted - Anyone with link can join"
    CLUB_ONLY = "CLUB_ONLY", "Club Only - Only club members"
    INVITE_ONLY = "INVITE_ONLY", "Invite Only - By invitation"
    PRIVATE = "PRIVATE", "Private - Specific users only"


class CarCategory(models.TextChoices):
    FORMULA_CAR = "formula_car", "Formula Car"
    OVAL = "oval", "Oval"
    SPORTS_CAR = "sports_car", "Sports Car"


class Simulator(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=280, blank=True, unique=True)
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

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness
            counter = 1
            original_slug = self.slug
            while Simulator.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class SimProfile(models.Model):
    """
    Independent sim racing profile that can optionally be linked to a user.
    Profiles exist regardless of user association and are publicly discoverable.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Core identity (platform-specific)
    simulator = models.ForeignKey(
        Simulator,
        on_delete=models.CASCADE,
        related_name="sim_profiles",
    )
    sim_api_id = models.CharField(
        max_length=255,
        blank=True,
        help_text="Platform-specific unique ID (e.g., customer ID, driver ID)",
    )
    profile_name = models.CharField(
        max_length=255,
        help_text="Display name on the platform",
    )

    # User relationship (optional one-to-one)
    linked_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="linked_sim_profiles",
        help_text="User who has claimed this profile",
    )

    # Verification and metadata
    is_verified = models.BooleanField(
        default=False,
        help_text="True if the linked user has verified ownership of this profile",
    )
    is_public = models.BooleanField(
        default=True,
        help_text="Whether this profile appears in public searches and listings",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    linked_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this profile was linked to the current user",
    )
    last_active = models.DateTimeField(null=True, blank=True)

    # Data storage
    preferences = models.JSONField(
        null=True,
        blank=True,
        help_text="User-controlled preferences and settings",
    )
    profile_data = models.JSONField(
        default=dict,
        help_text="Platform-specific profile data (stats, achievements, etc.)",
    )

    class Meta:
        unique_together = ["simulator", "sim_api_id"]
        indexes = [
            models.Index(fields=["simulator", "sim_api_id"]),
            models.Index(fields=["linked_user"]),
            models.Index(fields=["is_public"]),
            models.Index(fields=["profile_name"]),
        ]

    def __str__(self):
        return f"{self.simulator.name}: {self.profile_name}"

    def get_absolute_url(self):
        """Public URL for this profile"""
        from django.urls import reverse

        return reverse(
            "drivers:profile_detail",
            kwargs={
                "simulator_slug": self.simulator.slug,
                "profile_identifier": self.sim_api_id,
            },
        )

    def get_user_management_url(self):
        """URL for user to manage this profile (if they own it)"""
        if self.linked_user:
            from django.urls import reverse

            return reverse(
                "users:profile_sim_profile_manage",
                kwargs={"profile_id": self.pk},
            )
        return None

    @property
    def is_owned(self):
        """Returns True if this profile is linked to a user"""
        return self.linked_user is not None

    @property
    def display_name(self):
        """Returns the best display name for this profile"""
        if self.linked_user and self.linked_user.get_full_name():
            return f"{self.profile_name} ({self.linked_user.get_full_name()})"
        return self.profile_name

    def can_user_link(self, user):
        """Check if a user can link this profile"""
        if self.linked_user is None:
            return True
        return self.linked_user == user

    def link_to_user(self, user, verified=False):
        """Link this profile to a user"""
        from django.utils import timezone

        if self.linked_user and self.linked_user != user:
            raise ValueError(f"Profile already linked to {self.linked_user}")

        self.linked_user = user
        self.is_verified = verified
        self.linked_at = timezone.now()
        self.save(update_fields=["linked_user", "is_verified", "linked_at"])

    def unlink_from_user(self):
        """Remove user link from this profile"""
        self.linked_user = None
        self.is_verified = False
        self.linked_at = None
        self.save(update_fields=["linked_user", "is_verified", "linked_at"])


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
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=120, blank=True)
    short_name = models.CharField(
        max_length=50,
        blank=True,
        help_text="Short display name (e.g., 'GT3 Class')",
    )
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    icon_url = models.URLField(blank=True)

    # Simulator-specific fields
    simulator = models.ForeignKey(
        Simulator,
        on_delete=models.CASCADE,
        related_name="car_classes",
        help_text="Simulator this car class belongs to",
        null=True,
        blank=True,
    )
    sim_api_id = models.CharField(
        max_length=50,
        help_text="Car class ID from simulator API (e.g., car_class_id from iRacing)",
        null=True,
        blank=True,
    )

    # Additional API fields
    relative_speed = models.IntegerField(
        null=True,
        blank=True,
        help_text="Relative speed rating from simulator API",
    )
    rain_enabled = models.BooleanField(
        default=False,
        help_text="Whether rain is supported for this car class",
    )

    # Car IDs in this class (from API cars_in_class)
    car_sim_api_ids = ArrayField(
        models.CharField(max_length=50),
        blank=True,
        default=list,
        help_text="Array of car sim_api_ids in this class (from cars_in_class API field)",
    )

    class Meta:
        indexes = [
            models.Index(fields=["simulator"]),
            models.Index(fields=["sim_api_id"]),
            models.Index(fields=["name"]),
            models.Index(fields=["slug"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["simulator", "sim_api_id"],
                condition=models.Q(simulator__isnull=False, sim_api_id__isnull=False),
                name="unique_simulator_sim_api_id",
            ),
        ]

    def __str__(self):
        if self.simulator:
            return f"{self.simulator.name}: {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness
            counter = 1
            original_slug = self.slug
            while CarClass.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class CarModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # GROUP 1: Core Identification
    name = models.CharField(max_length=255)  # Extracted model name (e.g., "Solstice")
    slug = models.SlugField(max_length=280, blank=True)
    manufacturer = models.CharField(max_length=255)  # car_make (e.g., "Pontiac")
    full_name = models.CharField(
        max_length=255,
        blank=True,
    )  # car_name from API (e.g., "Pontiac Solstice")
    abbreviated_name = models.CharField(
        max_length=20,
        blank=True,
    )  # car_name_abbreviated (e.g., "SOL")

    # GROUP 2: Categorization
    category = models.CharField(
        max_length=20,
        choices=CarCategory,
        default=CarCategory.SPORTS_CAR,
        help_text="Primary car category from iRacing API",
    )
    car_types = ArrayField(
        models.CharField(max_length=50),
        blank=True,
        default=list,
        help_text="Array of car types for searching (cleaned from API car_types)",
    )
    search_filters = models.CharField(
        max_length=500,
        blank=True,
        help_text="Search filters from iRacing API for advanced searching",
    )

    # GROUP 3: Technical Specifications (Base Car Properties)
    horsepower = models.IntegerField(
        null=True,
        blank=True,
        help_text="HP from iRacing API",
    )
    weight_lbs = models.IntegerField(
        null=True,
        blank=True,
        help_text="Car weight in pounds",
    )
    has_headlights = models.BooleanField(
        default=False,
        help_text="Whether car has headlights",
    )
    has_multiple_dry_tire_types = models.BooleanField(
        default=False,
        help_text="Multiple dry tire compounds available",
    )
    has_rain_capable_tire_types = models.BooleanField(
        default=False,
        help_text="Rain tires available",
    )
    rain_enabled = models.BooleanField(
        default=False,
        help_text="Can race in rain conditions",
    )
    ai_enabled = models.BooleanField(default=True, help_text="AI can drive this car")

    # Existing fields
    # NOTE: car_class field removed - cars can belong to multiple classes
    # Use CarClass.car_sim_api_ids to find which classes a car belongs to
    release_year = models.IntegerField(null=True, blank=True)
    default_image_url = models.URLField(blank=True)
    base_specs = models.JSONField(null=True, blank=True)

    class Meta:
        unique_together = ["manufacturer", "name", "slug"]
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["manufacturer"]),
            models.Index(fields=["category"]),
            models.Index(fields=["full_name"]),
            # Technical specs for filtering
            models.Index(fields=["horsepower"]),
            models.Index(fields=["weight_lbs"]),
            models.Index(fields=["rain_enabled"]),
            models.Index(fields=["has_headlights"]),
            # GIN index for car_types array field for fast searching
            models.Index(fields=["car_types"], name="car_model_types_gin"),
        ]

    def __str__(self):
        return f"{self.manufacturer} {self.name}"

    def get_car_classes(self, simulator=None):
        """Get all car classes this car belongs to for a specific simulator."""
        if not hasattr(self, "_cached_car_classes"):
            self._cached_car_classes = {}
        # Assuming SimCar is a related model to CarModel through a ManyToManyField
        sim_cars = SimCar.objects.filter(car_model=self, is_active=True)
        if simulator:
            sim_cars = sim_cars.filter(simulator=simulator)

        car_sim_api_ids = list(sim_cars.values_list("sim_api_id", flat=True))

        if not car_sim_api_ids:
            return CarClass.objects.none()

        # Find CarClasses that contain any of these car IDs
        car_classes = CarClass.objects.filter(
            car_sim_api_ids__overlap=car_sim_api_ids,
        )

        if simulator:
            car_classes = car_classes.filter(simulator=simulator)

        return car_classes.distinct()

    # Helper methods to get images from associated SimCars
    def get_logo(self, simulator_preference=None):
        """Get the best available logo from associated SimCars."""
        return self._get_best_image("logo", simulator_preference)

    def get_small_image(self, simulator_preference=None):
        """Get the best available small image from associated SimCars."""
        return self._get_best_image("small_image", simulator_preference)

    def get_large_image(self, simulator_preference=None):
        """Get the best available large image from associated SimCars."""
        return self._get_best_image("large_image", simulator_preference)

    def _get_best_image(self, image_field, simulator_preference=None):
        sim_cars = [sc for sc in list(self.sim_cars.all()) if sc.is_active]
        if simulator_preference:
            preferred_sim_cars = [
                sc
                for sc in sim_cars
                if simulator_preference.lower() in sc.simulator.name.lower()
            ]
            for sim_car in preferred_sim_cars:
                image = getattr(sim_car, image_field, None)
                if image:
                    return image
        for sim_car in sim_cars:
            image = getattr(sim_car, image_field, None)
            if image:
                return image
        return None

    def get_gallery_images(self, gallery_type="screenshots", simulator_preference=None):
        """Get gallery images from MediaGallery for this car model or its SimCars."""
        from django.contrib.contenttypes.models import ContentType

        from simlane.core.models import MediaGallery

        # First try to get gallery images directly linked to this CarModel
        car_model_ct = ContentType.objects.get_for_model(self)
        gallery_images = MediaGallery.objects.filter(
            content_type=car_model_ct,
            object_id=str(self.id),
            gallery_type=gallery_type,
        ).order_by("order")

        if gallery_images.exists():
            return gallery_images

        # Fall back to gallery images from associated SimCars
        sim_cars_manager = self.sim_cars
        sim_car_ct = ContentType.objects.get_for_model(sim_cars_manager.model)
        sim_car_ids = list(
            sim_cars_manager.filter(is_active=True).values_list("id", flat=True),
        )

        if simulator_preference:
            # Try preferred simulator first
            preferred_sim_car_ids = list(
                sim_cars_manager.filter(
                    is_active=True,
                    simulator__name__icontains=simulator_preference,
                ).values_list("id", flat=True),
            )
            if preferred_sim_car_ids:
                gallery_images = MediaGallery.objects.filter(
                    content_type=sim_car_ct,
                    object_id__in=[str(id) for id in preferred_sim_car_ids],
                    gallery_type=gallery_type,
                ).order_by("order")
                if gallery_images.exists():
                    return gallery_images

        # Fall back to any SimCar gallery images
        return MediaGallery.objects.filter(
            content_type=sim_car_ct,
            object_id__in=[str(id) for id in sim_car_ids],
            gallery_type=gallery_type,
        ).order_by("order")

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.manufacturer} {self.name}")
            # Ensure uniqueness
            counter = 1
            original_slug = self.slug
            while CarModel.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class SimCar(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Relationships
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

    # GROUP 1: API IDs - CRITICAL for ownership tracking
    sim_api_id = models.CharField(
        max_length=255,
        help_text="car_id from iRacing API for API calls",
    )
    package_id = models.IntegerField(
        help_text="package_id from iRacing API for ownership tracking",
    )

    # Display and configuration
    display_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Full display name from car_name field",
    )
    bop_version = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)

    # GROUP 3: BOP (Balance of Performance) Adjustments - Simulator Specific
    max_power_adjust_pct = models.IntegerField(
        default=0,
        help_text="Maximum power adjustment percentage",
    )
    min_power_adjust_pct = models.IntegerField(
        default=0,
        help_text="Minimum power adjustment percentage",
    )
    max_weight_penalty_kg = models.IntegerField(
        default=0,
        help_text="Maximum weight penalty in kg",
    )

    # GROUP 4: Pricing & Ownership - Simulator Specific
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price in USD",
    )
    price_display = models.CharField(
        max_length=50,
        blank=True,
        help_text="Formatted price string",
    )
    free_with_subscription = models.BooleanField(
        default=False,
        help_text="Free with base subscription",
    )
    is_purchasable = models.BooleanField(
        default=True,
        help_text="Can be purchased (is_ps_purchasable)",
    )

    # GROUP 6: Media Fields - Simulator Specific Images
    logo = models.ImageField(
        upload_to="cars/logos/",
        blank=True,
        null=True,
        help_text="Car/manufacturer logo",
    )
    small_image = models.ImageField(
        upload_to="cars/thumbnails/",
        blank=True,
        null=True,
        help_text="Thumbnail image",
    )
    large_image = models.ImageField(
        upload_to="cars/images/",
        blank=True,
        null=True,
        help_text="Main/hero image",
    )
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
        unique_together = [
            ["simulator", "sim_api_id"],
        ]
        indexes = [
            models.Index(fields=["car_model"]),
            models.Index(fields=["simulator", "sim_api_id"]),
            models.Index(fields=["simulator", "package_id"]),
            models.Index(fields=["package_id"]),  # For ownership queries
            models.Index(fields=["is_active"]),
            # Pricing and filtering indexes
            models.Index(fields=["free_with_subscription"]),
            models.Index(fields=["is_purchasable"]),
            models.Index(fields=["price"]),
        ]

    def __str__(self):
        return f"{self.simulator.name}: {self.display_name or self.car_model.full_name or self.car_model.name}"


class TrackModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, blank=True)
    country = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    description = models.TextField(blank=True)

    # Basic track categorization - universal across simulators
    category = models.CharField(
        max_length=20,
        blank=True,
        help_text="Track category: 'road' or 'oval'",
    )
    time_zone = models.CharField(
        max_length=50,
        blank=True,
        help_text="Track time zone (e.g., 'America/New_York')",
    )

    # New: Official information page URL (e.g., iRacing site link)
    site_url = models.URLField(
        blank=True,
        help_text="Official simulator site URL for this track (from track assets API)",
    )

    class Meta:
        unique_together = ["name", "country", "slug"]
        indexes = [
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_name = f"{self.name}"
            if self.country:
                base_name += f" {self.country}"
            self.slug = slugify(base_name)
            # Ensure uniqueness
            counter = 1
            original_slug = self.slug
            while TrackModel.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def get_logo(self, simulator_preference=None):
        """Get the best available logo from associated SimTracks."""
        return self._get_best_image("logo", simulator_preference)

    def get_small_image(self, simulator_preference=None):
        """Get the best available small image from associated SimTracks."""
        return self._get_best_image("small_image", simulator_preference)

    def get_large_image(self, simulator_preference=None):
        """Get the best available large image from associated SimTracks."""
        return self._get_best_image("large_image", simulator_preference)

    def _get_best_image(self, image_field, simulator_preference=None):
        sim_tracks = [st for st in list(self.sim_tracks.all()) if st.is_active]
        if simulator_preference:
            preferred = [
                st
                for st in sim_tracks
                if simulator_preference.lower() in st.simulator.name.lower()
            ]
            for sim_track in preferred:
                image = getattr(sim_track, image_field, None)
                if image:
                    return image
        for sim_track in sim_tracks:
            image = getattr(sim_track, image_field, None)
            if image:
                return image
        return None


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
    slug = models.SlugField(max_length=300, blank=True)
    sim_api_id = models.CharField(max_length=255)
    display_name = models.CharField(max_length=255)
    is_laser_scanned = models.BooleanField(null=True, blank=True)

    # Ownership & Pricing - simulator-specific
    package_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Package ID from API for ownership tracking",
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Track price in USD",
    )
    is_free = models.BooleanField(default=False, help_text="Free with subscription")
    is_purchasable = models.BooleanField(default=True, help_text="Can be purchased")
    rain_enabled = models.BooleanField(
        default=False,
        help_text="Rain weather supported",
    )
    search_filters = models.CharField(
        max_length=500,
        blank=True,
        help_text="Search filters from API for optimization",
    )

    # Media Fields
    logo = models.ImageField(
        upload_to="tracks/logos/",
        blank=True,
        null=True,
        help_text="Track logo",
    )
    small_image = models.ImageField(
        upload_to="tracks/thumbnails/",
        blank=True,
        null=True,
        help_text="Thumbnail image",
    )
    large_image = models.ImageField(
        upload_to="tracks/images/",
        blank=True,
        null=True,
        help_text="Main/hero image",
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ["simulator", "sim_api_id"],
            ["simulator", "track_model"],
            ["simulator", "slug"],
        ]
        indexes = [
            models.Index(fields=["simulator"]),
            models.Index(fields=["track_model"]),
            models.Index(fields=["simulator", "slug"]),
        ]

    def __str__(self):
        return f"{self.simulator.name} - {self.track_model.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.track_model.name}")
            # Ensure uniqueness within simulator
            counter = 1
            original_slug = self.slug
            while SimTrack.objects.filter(
                simulator=self.simulator,
                slug=self.slug,
            ).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class SimLayout(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sim_track = models.ForeignKey(
        SimTrack,
        on_delete=models.CASCADE,
        related_name="layouts",
    )
    layout_code = models.CharField(max_length=50)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, blank=True)
    type = models.CharField(max_length=20, choices=TrackType)
    length_km = models.FloatField(help_text="Track configuration length in kilometers")
    image_url = models.URLField(blank=True)

    # Layout-specific properties
    layout_type = models.CharField(
        max_length=20,
        choices=TrackType,
        default=TrackType.ROAD,
        help_text="Specific layout type (road, oval, dirt_road, dirt_oval, etc.)",
    )
    retired = models.BooleanField(
        default=False,
        help_text="Layout is retired/deprecated",
    )

    # Technical specifications - layout-specific
    max_cars = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum cars supported on this layout",
    )
    grid_stalls = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of grid starting positions",
    )
    number_pitstalls = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of pit stalls available",
    )
    corners_per_lap = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of corners per lap",
    )

    # Session configuration - layout-specific
    qualify_laps = models.IntegerField(
        null=True,
        blank=True,
        help_text="Number of qualifying laps",
    )
    allow_rolling_start = models.BooleanField(
        default=True,
        help_text="Whether rolling starts are allowed",
    )
    pit_road_speed_limit = models.IntegerField(
        null=True,
        blank=True,
        help_text="Pit road speed limit (mph/kph)",
    )

    # Lighting capabilities - layout-specific
    night_lighting = models.BooleanField(
        default=False,
        help_text="Track has night lighting capabilities",
    )
    fully_lit = models.BooleanField(
        default=False,
        help_text="Track is fully lit for night racing",
    )

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
        unique_together = ["sim_track", "layout_code", "slug"]
        indexes = [
            models.Index(fields=["sim_track"]),
            models.Index(fields=["sim_track", "slug"]),
        ]

    def __str__(self):
        return f"{self.sim_track.track_model.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness within sim_track
            counter = 1
            original_slug = self.slug
            while SimLayout.objects.filter(
                sim_track=self.sim_track,
                slug=self.slug,
            ).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def get_svg_map_layers(self):
        """Get SVG track map layers from MediaGallery."""
        from django.contrib.contenttypes.models import ContentType

        from simlane.core.models import MediaGallery

        content_type = ContentType.objects.get_for_model(self)
        return (
            MediaGallery.objects.filter(
                content_type=content_type,
                object_id=str(self.id),
                gallery_type="track_maps",
            )
            .exclude(caption="background")
            .order_by("order")
        )

    def has_svg_maps(self):
        """Check if this layout has SVG track maps available."""
        return self.get_svg_map_layers().exists()


class Series(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, blank=True)
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)
    # Directly stored logo image (downloaded from iRacing static assets)
    logo = models.ImageField(
        upload_to="series/logos/",
        blank=True,
        null=True,
        help_text="Logo image downloaded from iRacing assets",
    )
    website = models.URLField(blank=True)

    # Enhanced simulator-specific fields
    external_series_id = models.IntegerField(
        unique=True,
        null=True,
        blank=True,
        help_text="Series ID from simulator API",
    )
    simulator = models.ForeignKey(
        Simulator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="series",
        help_text="Simulator this series belongs to (if simulator-specific)",
    )
    category = models.CharField(
        max_length=50,
        blank=True,
        help_text="Track category: 'oval', 'road', etc.",
    )

    is_official = models.BooleanField(default=True, help_text="Official series")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Series"
        verbose_name_plural = "Series"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["external_series_id"]),
            models.Index(fields=["simulator"]),
            models.Index(fields=["category"]),
            models.Index(fields=["is_official"]),
        ]
        unique_together = ["simulator", "external_series_id"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(
                self.simulator.slug
                + "-"
                + self.name
                + (
                    "-" + str(self.external_series_id)
                    if self.external_series_id
                    else ""
                )
            )
            # Ensure uniqueness
            counter = 1
            original_slug = self.slug
            while Series.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class Season(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    series = models.ForeignKey(Series, on_delete=models.CASCADE, related_name="seasons")

    # Core season identification
    external_season_id = models.IntegerField(
        unique=True,
        help_text="Season ID from simulator API",
    )
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=300, blank=True)

    # Season timing
    start_date = models.DateTimeField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)
    # Removed: current_race_week, max_weeks (legacy RaceWeek fields)

    # Season status
    active = models.BooleanField(default=True)
    complete = models.BooleanField(default=False)

    # Additional metadata
    schedule_description = models.TextField(blank=True)
    season_settings = models.JSONField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["series"]),
            models.Index(fields=["external_season_id"]),
            models.Index(fields=["active"]),
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return f"{self.series.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.series.name} {self.name}")
            # Ensure uniqueness
            counter = 1
            original_slug = self.slug
            while Season.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class CarRestriction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        "Event",
        on_delete=models.CASCADE,
        related_name="car_restrictions",
    )
    sim_car = models.ForeignKey(
        SimCar,
        on_delete=models.CASCADE,
        related_name="event_restrictions",
    )

    # BOP restrictions per car per week (from iRacing car_restrictions data)
    max_dry_tire_sets = models.IntegerField(
        default=0,
        help_text="Maximum dry tire sets allowed",
    )
    max_pct_fuel_fill = models.IntegerField(
        default=100,
        help_text="Maximum fuel fill percentage",
    )
    power_adjust_pct = models.FloatField(
        default=0.0,
        help_text="Power adjustment percentage (can be decimal)",
    )
    weight_penalty_kg = models.IntegerField(
        default=0,
        help_text="Weight penalty in kilograms",
    )

    # Simplified setup restriction
    is_fixed_setup = models.BooleanField(
        default=False,
        help_text="Whether this car uses fixed setup",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["event", "sim_car"]
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["sim_car"]),
        ]

    def __str__(self):
        return f"{self.event} - {self.sim_car.display_name}"


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    series = models.ForeignKey(
        Series,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        related_name="events",
        null=True,
        blank=True,
        help_text="Season this event belongs to (optional)",
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
    slug = models.SlugField(max_length=280, blank=True)
    description = models.TextField(blank=True)
    type = models.CharField(max_length=20, choices=EventType, default=EventType.CUSTOM)
    status = models.CharField(
        max_length=20,
        choices=EventStatus,
        default=EventStatus.DRAFT,
    )

    # Enhanced: Event ownership and organization
    event_source = models.CharField(
        max_length=20,
        choices=EventSource,
        default=EventSource.USER,
        help_text="Source/type of this event",
    )

    # Organizer can be a club OR user (using string reference to avoid circular import)
    organizing_club = models.ForeignKey(
        "teams.Club",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organized_events",
        help_text="Club organizing this event (if club-organized)",
    )
    organizing_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organized_events",
        help_text="User organizing this event (if user-created)",
    )

    # Enhanced: Visibility and access control
    visibility = models.CharField(
        max_length=20,
        choices=EventVisibility,
        default=EventVisibility.PUBLIC,
        help_text="Who can see and join this event",
    )

    # Enhanced: Entry requirements
    min_license_level = models.CharField(
        max_length=10,
        blank=True,
        help_text="Minimum license level required (e.g., 'D', 'C', 'B')",
    )
    min_safety_rating = models.FloatField(
        null=True,
        blank=True,
        help_text="Minimum safety rating required",
    )
    min_skill_rating = models.FloatField(
        null=True,
        blank=True,
        help_text="Minimum skill rating required",
    )
    max_entries = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of entries allowed",
    )

    additional_details = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional details like specific licenses, achievements, etc.",
    )

    # Car class restrictions (simplified approach - can override series)
    allowed_car_class_ids = ArrayField(
        models.CharField(max_length=50),
        blank=True,
        default=list,
        help_text="Array of car class sim_api_ids allowed in this event (overrides series if set)",
    )

    # Merged fields from RaceWeek
    round_number = models.IntegerField(
        null=True,
        blank=True,
        help_text="Round number in series (was week_number in legacy model)",
    )
    schedule_name = models.CharField(max_length=255, blank=True)

    multiclass = models.BooleanField(default=False)

    # Event timing
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateTimeField(null=True, blank=True)

    # Track-specific settings
    category = models.CharField(
        max_length=20,
        blank=True,
        help_text="Track category: 'oval', 'road'",
    )
    enable_pitlane_collisions = models.BooleanField(default=False)
    full_course_cautions = models.BooleanField(default=True)

    simulated_start_time = models.DateTimeField(null=True, blank=True)

    # Store the recurring schedule pattern from iRacing API
    time_pattern = models.JSONField(
        null=True,
        blank=True,
        help_text="race_time_descriptors from API - e.g., {'first_session_time': '00:45:00', 'repeat_minutes': 120}",
    )

    # Weather configuration and forecast URLs
    weather_config = models.JSONField(
        null=True,
        blank=True,
        help_text="Full weather configuration from iRacing API including forecast_options, weather_summary, etc.",
    )
    weather_forecast_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="iRacing weather forecast URL for this event",
    )
    weather_forecast_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Cached weather forecast data from iRacing API",
    )
    weather_forecast_version = models.IntegerField(
        null=True,
        blank=True,
        help_text="Weather forecast API version (1=Forecast/hourly, 3=Timeline/15min)",
    )

    # Summary stats for quick filtering/display
    min_air_temp = models.FloatField(
        null=True,
        blank=True,
        help_text="Minimum forecasted air temp (Celsius)",
    )
    max_air_temp = models.FloatField(
        null=True,
        blank=True,
        help_text="Maximum forecasted air temp (Celsius)",
    )
    max_precip_chance = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum precipitation chance percentage (0-100)",
    )

    # Track state
    track_state = models.JSONField(
        null=True,
        blank=True,
        help_text="leave_marbles, etc.",
    )

    # Existing fields
    registration_open_minutes = models.IntegerField(null=True, blank=True)
    is_team_event = models.BooleanField(null=True, blank=True)
    min_drivers_per_entry = models.IntegerField(null=True, blank=True)
    max_drivers_per_entry = models.IntegerField(null=True, blank=True)
    fair_share_pct = models.FloatField(null=True, blank=True)
    min_pit_stops = models.IntegerField(null=True, blank=True)
    required_compounds = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["series"]),
            models.Index(fields=["simulator"]),
            models.Index(fields=["sim_layout"]),
            models.Index(fields=["status"]),
            models.Index(fields=["slug"]),
            # Enhanced indexes for new fields
            models.Index(fields=["event_source"]),
            models.Index(fields=["organizing_club"]),
            models.Index(fields=["organizing_user"]),
            models.Index(fields=["visibility"]),
            models.Index(fields=["event_source", "visibility"]),
            # Indexes for round_number and merged fields
            models.Index(fields=["round_number"]),
            models.Index(fields=["start_date", "end_date"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    # Must have exactly one organizer type (or none for imported events)
                    models.Q(
                        organizing_club__isnull=False,
                        organizing_user__isnull=True,
                    )
                    | models.Q(
                        organizing_club__isnull=True,
                        organizing_user__isnull=False,
                    )
                    | models.Q(
                        organizing_club__isnull=True,
                        organizing_user__isnull=True,
                    )
                ),
                name="event_has_single_organizer_or_none",
            ),
        ]

    def __str__(self):
        if self.season:
            return f"{self.season.name} - {self.name}"
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness
            counter = 1
            original_slug = self.slug
            while Event.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    @property
    def effective_organizer(self):
        """Get the effective organizer user (if any)"""
        if self.organizing_user:
            return self.organizing_user
        if self.organizing_club:
            return self.organizing_club.created_by
        return None

    @property
    def is_user_organized(self):
        """Check if this event is organized by an individual user"""
        return self.event_source == EventSource.USER and self.organizing_user

    @property
    def is_club_organized(self):
        """Check if this event is organized by a club"""
        return self.event_source == EventSource.CLUB and self.organizing_club

    @property
    def is_official(self):
        """Check if this is an official event"""
        return self.event_source == EventSource.OFFICIAL

    def can_user_view(self, user):
        """Check if a user can view this event"""
        # Public events are visible to all
        if self.visibility == EventVisibility.PUBLIC:
            return True

        # Unlisted events are visible to all (but not discoverable)
        if self.visibility == EventVisibility.UNLISTED:
            return True

        # Organizer can always view
        if user == self.organizing_user:
            return True

        # Club organizer - check club membership
        if self.organizing_club:
            try:
                from django.apps import apps

                ClubMember = apps.get_model("teams", "ClubMember")
                member = ClubMember.objects.get(user=user, club=self.organizing_club)

                if self.visibility == EventVisibility.CLUB_ONLY:
                    return True  # Any club member can view
                if self.visibility in [
                    EventVisibility.INVITE_ONLY,
                    EventVisibility.PRIVATE,
                ]:
                    return member.can_manage_club()  # Only club managers can view

            except ClubMember.DoesNotExist:
                pass

        # For invite-only events, check if user has been invited
        if self.visibility == EventVisibility.INVITE_ONLY:
            # This would need EventInvitation model which we'll implement later
            pass

        return False

    def can_user_join(self, user):
        """Check if a user can join this event"""
        # Must be able to view first
        if not self.can_user_view(user):
            return False

        # Check if event is open for registration
        if self.status not in [EventStatus.DRAFT, EventStatus.SCHEDULED]:
            return False

        # Check entry limits (TODO: implement when EventParticipation model is ready)
        # if self.max_entries:
        #     current_entries = self.participations.count()
        #     if current_entries >= self.max_entries:
        #         return False

        # Check skill requirements (if user has sim profiles)
        if self.min_skill_rating or self.min_safety_rating:
            user_profiles = user.linked_sim_profiles.filter(simulator=self.simulator)
            if not user_profiles.exists():
                return False

            # Check if any profile meets requirements
            for profile in user_profiles:
                if self._check_profile_requirements(profile):
                    break
            else:
                return False

        return True

    def can_user_manage(self, user):
        """Check if a user can manage this event"""
        # Direct organizer can always manage
        if user == self.organizing_user:
            return True

        # Club organizer - check club admin/manager permissions
        if self.organizing_club:
            try:
                from django.apps import apps

                ClubMember = apps.get_model("teams", "ClubMember")
                member = ClubMember.objects.get(user=user, club=self.organizing_club)
                return member.can_manage_club()
            except ClubMember.DoesNotExist:
                pass

        return False

    def _check_profile_requirements(self, sim_profile):
        """
        Check if a sim profile meets the event requirements.
        Returns (meets_requirements: bool, reasons: list[str])
        """
        reasons = []

        # Check license level requirement
        if self.min_license_level:
            # This would need to be implemented based on how license levels are stored
            # For now, just a placeholder
            pass

        # Check safety rating requirement
        if self.min_safety_rating is not None:
            # This would need actual safety rating from sim profile
            pass

        # Check skill rating requirement
        if self.min_skill_rating is not None:
            # This would need actual skill rating from sim profile
            pass

        # If we have custom requirements, check those too
        if self.entry_requirements:
            # Custom logic for entry requirements
            pass

        return len(reasons) == 0, reasons

    @property
    def is_multiclass(self):
        """Check if this event has multiple classes"""
        return self.classes.count() > 1

    def get_effective_car_class_ids(self):
        """Get car class IDs for this event (event-specific or from series)"""
        if self.allowed_car_class_ids:
            return self.allowed_car_class_ids
        if self.series and self.series.allowed_car_class_ids:
            return self.series.allowed_car_class_ids
        return []

    def get_allowed_cars(self):
        """Get all cars allowed in this event across all classes"""
        all_cars = SimCar.objects.none()
        for event_class in self.classes.all():
            all_cars = all_cars.union(event_class.get_allowed_cars())
        return all_cars

    def get_class_for_car(self, car):
        """Get the event class that allows a specific car"""
        for event_class in self.classes.all():
            if car in event_class.get_allowed_cars():
                return event_class
        return None


class EventSession(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="sessions")
    session_type = models.CharField(max_length=20, choices=SessionType)
    duration = models.IntegerField(null=True, blank=True)  # Duration in minutes
    laps = models.IntegerField(null=True, blank=True)
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
    slug = models.SlugField(max_length=280, blank=True)
    car_class = models.ForeignKey(
        CarClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="event_classes",
    )
    # REMOVED: allowed_sim_car_ids - get this from car_class.car_sim_api_ids instead
    bop_overrides = models.JSONField(null=True, blank=True)

    # Multi-class and club management fields
    class_order = models.IntegerField(
        default=0,
        help_text="Order for multi-class display (0=fastest class)",
    )
    min_entries = models.IntegerField(
        null=True,
        blank=True,
        help_text="Minimum entries needed for this class",
    )
    max_entries = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum entries allowed for this class",
    )
    entry_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Entry fee for this class",
    )
    inherit_series_restrictions = models.BooleanField(
        default=True,
        help_text="Whether to inherit BOP restrictions from series/race week",
    )

    class Meta:
        unique_together = ["event", "slug"]
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["car_class"]),
            models.Index(fields=["class_order"]),
        ]

    def __str__(self):
        return f"{self.event.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness within the event
            counter = 1
            original_slug = self.slug
            while EventClass.objects.filter(event=self.event, slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    def get_allowed_cars(self):
        """Get all cars allowed in this class from the linked CarClass"""
        if self.car_class and self.car_class.car_sim_api_ids:
            # Get SimCar objects that match the car_sim_api_ids from the CarClass
            return SimCar.objects.filter(
                sim_api_id__in=self.car_class.car_sim_api_ids,
                simulator=self.event.simulator,
            )
        return SimCar.objects.none()

    def get_bop_restrictions(self, round_number=None):
        """Get BOP restrictions for a given round_number (replaces legacy race_week logic)."""
        if round_number is None:
            round_number = self.event.round_number

        restrictions = {}

        if self.inherit_series_restrictions:
            # Get base restrictions from series for cars in this class
            allowed_cars = self.get_allowed_cars()
            for car in allowed_cars:
                try:
                    car_restriction = CarRestriction.objects.get(
                        event=self.event,
                        sim_car=car,
                    )
                    restrictions[car.sim_api_id] = {
                        "max_dry_tire_sets": car_restriction.max_dry_tire_sets,
                        "max_pct_fuel_fill": car_restriction.max_pct_fuel_fill,
                        "power_adjust_pct": car_restriction.power_adjust_pct,
                        "weight_penalty_kg": car_restriction.weight_penalty_kg,
                        "is_fixed_setup": car_restriction.is_fixed_setup,
                    }
                except CarRestriction.DoesNotExist:
                    continue

        # Apply event-specific BOP overrides
        if self.bop_overrides:
            for car_id, overrides in self.bop_overrides.items():
                if car_id in restrictions:
                    restrictions[car_id].update(overrides)
                else:
                    restrictions[car_id] = overrides

        return restrictions


class TimeSlot(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="time_slots",
    )
    slug = models.SlugField(max_length=300, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    registration_open = models.DateTimeField()
    registration_ends = models.DateTimeField()

    # Simulator API identifiers (populated after race occurs)
    external_subsession_id = models.BigIntegerField(
        null=True,
        blank=True,
        unique=True,
        help_text="Actual subsession/race ID from simulator API",
    )
    external_session_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Session ID from simulator API (if different from subsession)",
    )

    # Matching status
    is_predicted = models.BooleanField(
        default=True,
        help_text="True if generated from time pattern, False if from actual results",
    )
    is_matched = models.BooleanField(
        default=False,
        help_text="True if matched to actual simulator subsession",
    )

    # Allow time adjustments when matching
    predicted_start_time = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Original predicted time (before matching to actual)",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["event", "slug"]
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["start_time"]),
            models.Index(fields=["registration_open"]),
            models.Index(fields=["registration_ends"]),
            models.Index(fields=["event", "slug"]),
            # New indexes for simulator data
            models.Index(fields=["external_subsession_id"]),
            models.Index(fields=["external_session_id"]),
            models.Index(fields=["is_predicted", "is_matched"]),
            models.Index(fields=["start_time", "event"]),  # For time-based matching
        ]

    def __str__(self):
        return f"{self.event.name} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    def save(self, *args, **kwargs):
        if not self.slug:
            # Create slug from event name and date
            date_str = (
                self.start_time.strftime("%Y-%m-%d-%H%M") if self.start_time else "tbd"
            )
            self.slug = slugify(f"{self.event.name} {date_str}")
            # Ensure uniqueness within event
            counter = 1
            original_slug = self.slug
            while TimeSlot.objects.filter(
                event=self.event,
                slug=self.slug,
            ).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    # ---------------- Weather helpers ----------------
    @property
    def weather_forecast(self):
        """Return cached weather forecast JSON from the event (legacy RaceWeek logic removed)."""
        return self.event.weather_forecast_data

    @property
    def weather_summary(self):
        """Quick access to summary stats stored on the event."""
        return {
            "min_air_temp": self.event.min_air_temp,
            "max_air_temp": self.event.max_air_temp,
            "max_precip_chance": self.event.max_precip_chance,
        }


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
    time_slot = models.ForeignKey(
        TimeSlot,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="weather_forecasts",
    )
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="weather_forecasts",
    )
    time_offset = models.IntegerField(help_text="Minutes from event start")
    timestamp = models.DateTimeField(
        help_text="Absolute timestamp for this forecast point",
    )
    is_sun_up = models.BooleanField(help_text="True if sun is up at this time")
    affects_session = models.BooleanField(
        help_text="True if a session is running at this time",
    )

    # Temperature and Pressure
    air_temperature = models.FloatField(
        help_text="Air temperature in Celsius (convert from simulator-specific units)",
    )
    pressure = models.FloatField(
        help_text="Atmospheric pressure in hectopascals/hPa (convert from simulator-specific units)",
    )

    # Wind
    wind_speed = models.FloatField(
        help_text="Wind speed in meters per second (convert from simulator-specific units)",
    )
    wind_direction = models.IntegerField(
        help_text="Wind direction in degrees 0-359",
    )

    # Precipitation
    precipitation_chance = models.IntegerField(
        help_text="Chance of precipitation as percentage 0-100",
    )
    precipitation_amount = models.FloatField(
        help_text="Precipitation rate in mm/hour (convert from simulator-specific units)",
    )
    allow_precipitation = models.BooleanField(
        help_text="Whether precipitation is allowed during this period",
    )

    # Cloud and Humidity
    cloud_cover = models.IntegerField(
        help_text="Cloud cover as percentage 0-100",
    )
    relative_humidity = models.IntegerField(
        help_text="Relative humidity as percentage 0-100",
    )

    # Metadata
    forecast_version = models.IntegerField(
        help_text="Weather forecast API version from simulator",
    )
    valid_stats = models.BooleanField(
        help_text="Whether rain statistics are available for this period",
    )

    # Unit conversion reference
    units_info = models.JSONField(
        null=True,
        blank=True,
        help_text="Store unit conversion factors and original units for reference",
        default=dict,
    )

    raw_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Complete API response for future use and reference",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["time_slot"]),
            models.Index(fields=["time_offset"]),
            models.Index(fields=["timestamp"]),
        ]

    def __str__(self):
        return f"{self.event.name} - {self.time_offset} minutes"


class SimProfileCarOwnership(models.Model):
    sim_profile = models.ForeignKey(
        "sim.SimProfile",
        on_delete=models.CASCADE,
        related_name="owned_cars",
    )
    sim_car = models.ForeignKey(
        "sim.SimCar",
        on_delete=models.CASCADE,
        related_name="owners",
    )
    acquired_at = models.DateTimeField(auto_now_add=True)
    is_favorite = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("sim_profile", "sim_car")
        verbose_name = "Car Ownership"
        verbose_name_plural = "Car Ownerships"


class SimProfileTrackOwnership(models.Model):
    sim_profile = models.ForeignKey(
        "sim.SimProfile",
        on_delete=models.CASCADE,
        related_name="owned_tracks",
    )
    sim_track = models.ForeignKey(
        "sim.SimTrack",
        on_delete=models.CASCADE,
        related_name="owners",
    )
    acquired_at = models.DateTimeField(auto_now_add=True)
    is_favorite = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ("sim_profile", "sim_track")
        verbose_name = "Track Ownership"
        verbose_name_plural = "Track Ownerships"


class EventResult(models.Model):
    """
    Stores the overall result data for a TimeSlot (race).
    Generic model that works across all simulators.
    """

    time_slot = models.OneToOneField(
        TimeSlot,
        on_delete=models.CASCADE,
        related_name="result",
    )

    # Core identifiers (simulator agnostic)
    subsession_id = models.BigIntegerField(
        unique=True,
        help_text="Simulator subsession ID",
    )
    session_id = models.BigIntegerField(
        null=True,
        blank=True,
        help_text="Simulator session ID",
    )

    # Event summary statistics (universal)
    num_drivers = models.IntegerField(help_text="Number of participants in the event")
    event_best_lap_time = models.IntegerField(
        help_text="Best lap time in milliseconds",
        null=True,
        blank=True,
    )
    event_average_lap = models.IntegerField(
        help_text="Average lap time in milliseconds",
        null=True,
        blank=True,
    )

    # Timing (universal)
    start_time = models.DateTimeField(help_text="Race start time")
    end_time = models.DateTimeField(help_text="Race end time")

    # Weather and track conditions (stored as JSON for flexibility)
    weather_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Complete weather conditions data",
    )
    track_state = models.JSONField(
        null=True,
        blank=True,
        help_text="Track rubber/marble state data",
    )
    track_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Track information data",
    )

    # Processing status
    results_fetched_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When results were fetched",
    )
    is_processed = models.BooleanField(
        default=False,
        help_text="Whether results have been processed",
    )

    # Raw data backup (includes simulator-specific fields)
    raw_api_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Complete raw API response data",
    )

    class Meta:
        verbose_name = "Event Result"
        verbose_name_plural = "Event Results"
        indexes = [
            models.Index(fields=["subsession_id"]),
            models.Index(fields=["time_slot"]),
            models.Index(fields=["start_time"]),
            models.Index(fields=["is_processed"]),
        ]

    def __str__(self):
        return f"Event Result: {self.time_slot} (Session: {self.subsession_id})"

    @property
    def duration(self):
        """Calculate race duration in seconds"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None

    @property
    def simulator(self):
        """Get simulator from event chain"""
        return self.time_slot.event.simulator

    # Simulator-specific data access methods
    @property
    def iracing_strength_of_field(self):
        """Get iRacing strength of field from raw data"""
        if self.raw_api_data and self.simulator == "iracing":
            return self.raw_api_data.get("event_strength_of_field")
        return None

    @property
    def iracing_cautions(self):
        """Get iRacing caution data from raw data"""
        if self.raw_api_data and self.simulator == "iracing":
            return {
                "num_cautions": self.raw_api_data.get("num_cautions", 0),
                "num_caution_laps": self.raw_api_data.get("num_caution_laps", 0),
                "num_lead_changes": self.raw_api_data.get("num_lead_changes", 0),
            }
        return None

    @property
    def is_team_event(self):
        """Check if this is a team event based on raw data structure"""
        if self.raw_api_data and self.simulator == "iracing":
            session_results = self.raw_api_data.get("session_results", [])
            if session_results and "results" in session_results[0]:
                results = session_results[0]["results"]
                # Check if first result has team_id and driver_results
                if (
                    results
                    and "team_id" in results[0]
                    and "driver_results" in results[0]
                ):
                    return True
        return False


class TeamResult(models.Model):
    """
    Stores team result data for team events.
    Links to EventResult and existing Team model.
    """

    event_result = models.ForeignKey(
        EventResult,
        on_delete=models.CASCADE,
        related_name="team_results",
    )
    team = models.ForeignKey(
        "teams.Team",
        on_delete=models.CASCADE,
        related_name="race_results",
    )

    # Team identification (backup from API)
    team_display_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Team name from API (backup)",
    )

    # Position data
    finish_position = models.IntegerField(help_text="Team's final position")
    finish_position_in_class = models.IntegerField(
        null=True,
        blank=True,
        help_text="Team's position in class",
    )

    # Performance data
    laps_complete = models.IntegerField(help_text="Total laps completed by team")
    laps_lead = models.IntegerField(default=0, help_text="Total laps led by team")
    incidents = models.IntegerField(default=0, help_text="Total incidents by team")

    # Lap times (in milliseconds)
    best_lap_time = models.IntegerField(
        null=True,
        blank=True,
        help_text="Team's best lap time",
    )
    best_lap_num = models.IntegerField(
        null=True,
        blank=True,
        help_text="Lap number of team's best lap",
    )
    average_lap = models.IntegerField(
        null=True,
        blank=True,
        help_text="Team's average lap time",
    )

    # Points and race outcome
    champ_points = models.IntegerField(
        default=0,
        help_text="Championship points earned",
    )
    reason_out = models.CharField(
        max_length=50,
        blank=True,
        help_text="Reason for DNF",
    )
    reason_out_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="DNF reason code",
    )
    drop_race = models.BooleanField(default=False, help_text="Whether race is dropped")

    # Car and class info
    car_id = models.IntegerField(null=True, blank=True, help_text="Car identifier")
    car_class_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Car class identifier",
    )
    car_class_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Car class name",
    )
    car_name = models.CharField(max_length=100, blank=True, help_text="Car name")

    # Additional data
    country_code = models.CharField(max_length=3, blank=True, help_text="Team country")
    division = models.IntegerField(null=True, blank=True, help_text="Team division")

    # Raw team data
    raw_team_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Raw team data from API",
    )

    class Meta:
        verbose_name = "Team Result"
        verbose_name_plural = "Team Results"
        unique_together = [["event_result", "team"]]
        indexes = [
            models.Index(fields=["event_result", "finish_position"]),
            models.Index(fields=["team", "finish_position"]),
            models.Index(fields=["car_class_id", "finish_position_in_class"]),
        ]

    def __str__(self):
        return f"Team Result: {self.team} - {self.event_result} (Position: {self.finish_position})"

    @property
    def simulator(self):
        """Get simulator from event chain"""
        return self.event_result.simulator

    @property
    def duration(self):
        """Get race duration from event result"""
        return self.event_result.duration

    @property
    def is_dnf(self):
        """Check if team DNF'd"""
        return bool(self.reason_out)

    @property
    def best_lap_time_seconds(self):
        """Convert best lap time to seconds"""
        if self.best_lap_time:
            return self.best_lap_time / 1000.0
        return None

    @property
    def average_lap_time_seconds(self):
        """Convert average lap time to seconds"""
        if self.average_lap:
            return self.average_lap / 1000.0
        return None


class ParticipantResult(models.Model):
    """
    Stores individual driver result data for both solo and team events.
    Links to SimProfile and either EventResult (solo) or TeamResult (team events).
    """

    # Core relationships
    sim_profile = models.ForeignKey(
        "sim.SimProfile",
        on_delete=models.CASCADE,
        related_name="race_results",
    )

    # For team events: link to TeamResult
    team_result = models.ForeignKey(
        TeamResult,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="participants",
    )

    # For solo events: link directly to EventResult
    event_result = models.ForeignKey(
        EventResult,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="participants",
    )

    # Driver identification (backup from API)
    driver_display_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Driver name from API (backup)",
    )

    # Position data
    finish_position = models.IntegerField(help_text="Driver's final position")
    finish_position_in_class = models.IntegerField(
        null=True,
        blank=True,
        help_text="Driver's position in class",
    )
    starting_position = models.IntegerField(help_text="Starting grid position")
    starting_position_in_class = models.IntegerField(
        null=True,
        blank=True,
        help_text="Starting position in class",
    )

    # Performance data
    laps_complete = models.IntegerField(help_text="Laps completed by driver")
    laps_lead = models.IntegerField(default=0, help_text="Laps led by driver")
    incidents = models.IntegerField(default=0, help_text="Incidents by driver")

    # Lap times (in milliseconds)
    best_lap_time = models.IntegerField(
        null=True,
        blank=True,
        help_text="Driver's best lap time",
    )
    best_lap_num = models.IntegerField(
        null=True,
        blank=True,
        help_text="Lap number of driver's best lap",
    )
    average_lap = models.IntegerField(
        null=True,
        blank=True,
        help_text="Driver's average lap time",
    )

    # Points and ratings
    champ_points = models.IntegerField(
        default=0,
        help_text="Championship points earned",
    )
    oldi_rating = models.IntegerField(
        null=True,
        blank=True,
        help_text="iRating before race",
    )
    newi_rating = models.IntegerField(
        null=True,
        blank=True,
        help_text="iRating after race",
    )
    old_license_level = models.IntegerField(
        null=True,
        blank=True,
        help_text="License level before race",
    )
    new_license_level = models.IntegerField(
        null=True,
        blank=True,
        help_text="License level after race",
    )
    old_sub_level = models.IntegerField(
        null=True,
        blank=True,
        help_text="Sub-level before race",
    )
    new_sub_level = models.IntegerField(
        null=True,
        blank=True,
        help_text="Sub-level after race",
    )

    # Race outcome
    reason_out = models.CharField(
        max_length=50,
        blank=True,
        help_text="Reason for DNF",
    )
    reason_out_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="DNF reason code",
    )
    drop_race = models.BooleanField(default=False, help_text="Whether race is dropped")

    # Car and class info
    car_id = models.IntegerField(null=True, blank=True, help_text="Car identifier")
    car_class_id = models.IntegerField(
        null=True,
        blank=True,
        help_text="Car class identifier",
    )
    car_class_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Car class name",
    )
    car_name = models.CharField(max_length=100, blank=True, help_text="Car name")

    # Additional data
    country_code = models.CharField(
        max_length=3,
        blank=True,
        help_text="Driver country",
    )
    division = models.IntegerField(null=True, blank=True, help_text="Driver division")

    # Raw participant data
    raw_participant_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Raw participant data from API",
    )

    class Meta:
        verbose_name = "Participant Result"
        verbose_name_plural = "Participant Results"
        unique_together = [
            ["event_result", "sim_profile"],  # For solo events
            ["team_result", "sim_profile"],  # For team events
        ]
        indexes = [
            models.Index(fields=["event_result", "finish_position"]),
            models.Index(fields=["team_result", "finish_position"]),
            models.Index(fields=["sim_profile", "finish_position"]),
            models.Index(fields=["oldi_rating", "newi_rating"]),
            models.Index(fields=["car_class_id", "finish_position_in_class"]),
        ]

    def __str__(self):
        if self.team_result:
            return f"Participant: {self.sim_profile} - Team: {self.team_result.team} (Position: {self.finish_position})"
        return (
            f"Participant: {self.sim_profile} - Solo (Position: {self.finish_position})"
        )

    def clean(self):
        """Validate that either team_result or event_result is set, but not both"""
        from django.core.exceptions import ValidationError

        if bool(self.team_result) == bool(self.event_result):
            raise ValidationError(
                "Must have either team_result (team event) or event_result (solo event), but not both",
            )

    @property
    def is_team_event(self):
        """Check if this is from a team event"""
        return bool(self.team_result)

    @property
    def event_result_actual(self):
        """Get the actual event result (either direct or via team)"""
        if self.event_result:
            return self.event_result
        if self.team_result:
            return self.team_result.event_result
        return None

    @property
    def simulator(self):
        """Get simulator from event chain"""
        if self.event_result_actual:
            return self.event_result_actual.simulator
        return None

    @property
    def team(self):
        """Get team for team events"""
        if self.team_result:
            return self.team_result.team
        return None

    @property
    def is_dnf(self):
        """Check if driver DNF'd"""
        return bool(self.reason_out)

    @property
    def i_rating_change(self):
        """Calculate iRating change"""
        if self.oldi_rating is not None and self.newi_rating is not None:
            return self.newi_rating - self.oldi_rating
        return None

    @property
    def license_change(self):
        """Calculate license level change"""
        if self.old_license_level is not None and self.new_license_level is not None:
            return self.new_license_level - self.old_license_level
        return None

    @property
    def best_lap_time_seconds(self):
        """Convert best lap time to seconds"""
        if self.best_lap_time:
            return self.best_lap_time / 1000.0
        return None

    @property
    def average_lap_time_seconds(self):
        """Convert average lap time to seconds"""
        if self.average_lap:
            return self.average_lap / 1000.0
        return None
