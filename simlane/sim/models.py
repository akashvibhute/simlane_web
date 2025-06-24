import uuid

from django.db import models
from django.utils.text import slugify

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


class EventSource(models.TextChoices):
    SPECIAL = "SPECIAL", "Special Event - Official"
    SERIES = "SERIES", "Series Event - Official"
    CLUB = "CLUB", "Club-Organized Event"
    USER = "USER", "User-Created Event"


class EventVisibility(models.TextChoices):
    PUBLIC = "PUBLIC", "Public - Anyone can view and join"
    UNLISTED = "UNLISTED", "Unlisted - Anyone with link can join"
    CLUB_ONLY = "CLUB_ONLY", "Club Only - Only club members"
    INVITE_ONLY = "INVITE_ONLY", "Invite Only - By invitation"
    PRIVATE = "PRIVATE", "Private - Specific users only"


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
    external_data_id = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Platform-specific unique ID (e.g., iRacing customer ID)"
    )
    profile_name = models.CharField(
        max_length=255, 
        help_text="Display name on the platform"
    )
    
    # User relationship (optional one-to-one)
    linked_user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='linked_sim_profiles',
        help_text="User who has claimed this profile"
    )
    
    # Verification and metadata
    is_verified = models.BooleanField(
        default=False, 
        help_text="True if the linked user has verified ownership of this profile"
    )
    is_public = models.BooleanField(
        default=True, 
        help_text="Whether this profile appears in public searches and listings"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    linked_at = models.DateTimeField(
        null=True, 
        blank=True, 
        help_text="When this profile was linked to the current user"
    )
    last_active = models.DateTimeField(null=True, blank=True)
    
    # Data storage
    preferences = models.JSONField(
        null=True, 
        blank=True,
        help_text="User-controlled preferences and settings"
    )
    profile_data = models.JSONField(
        default=dict, 
        help_text="Platform-specific profile data (stats, achievements, etc.)"
    )

    class Meta:
        unique_together = ['simulator', 'external_data_id']
        indexes = [
            models.Index(fields=['simulator', 'external_data_id']),
            models.Index(fields=['linked_user']),
            models.Index(fields=['is_public']),
            models.Index(fields=['profile_name']),
        ]

    def __str__(self):
        return f"{self.simulator.name}: {self.profile_name}"

    def get_absolute_url(self):
        """Public URL for this profile"""
        from django.urls import reverse
        return reverse('profiles:detail', kwargs={
            'simulator_slug': self.simulator.slug,
            'profile_identifier': self.external_data_id
        })

    def get_user_management_url(self):
        """URL for user to manage this profile (if they own it)"""
        if self.linked_user:
            from django.urls import reverse
            return reverse('users:profile_sim_profile_manage', kwargs={'profile_id': self.pk})
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
        self.save(update_fields=['linked_user', 'is_verified', 'linked_at'])

    def unlink_from_user(self):
        """Remove user link from this profile"""
        self.linked_user = None
        self.is_verified = False
        self.linked_at = None
        self.save(update_fields=['linked_user', 'is_verified', 'linked_at'])


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
    slug = models.SlugField(max_length=120, blank=True)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    icon_url = models.URLField(blank=True)

    def __str__(self):
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
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, blank=True)
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
        unique_together = ["manufacturer", "name", "slug"]
        indexes = [
            models.Index(fields=["car_class"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return f"{self.manufacturer} {self.name}"

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
    slug = models.SlugField(max_length=280, blank=True)
    country = models.CharField(max_length=100, blank=True)
    location = models.CharField(max_length=255, blank=True)
    latitude = models.FloatField(null=True, blank=True)
    longitude = models.FloatField(null=True, blank=True)
    default_image_url = models.URLField(blank=True)
    description = models.TextField(blank=True)

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
    image_url = models.URLField(blank=True)
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


class Series(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, blank=True)
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
        indexes = [
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness
            counter = 1
            original_slug = self.slug
            while Series.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


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
        help_text="Source/type of this event"
    )
    
    # Organizer can be a club OR user (using string reference to avoid circular import)
    organizing_club = models.ForeignKey(
        "teams.Club",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organized_events",
        help_text="Club organizing this event (if club-organized)"
    )
    organizing_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organized_events",
        help_text="User organizing this event (if user-created)"
    )
    
    # Enhanced: Visibility and access control
    visibility = models.CharField(
        max_length=20,
        choices=EventVisibility,
        default=EventVisibility.PUBLIC,
        help_text="Who can see and join this event"
    )
    
    # Enhanced: Entry requirements
    min_license_level = models.CharField(
        max_length=10,
        blank=True,
        help_text="Minimum license level required (e.g., 'D', 'C', 'B')"
    )
    min_safety_rating = models.FloatField(
        null=True,
        blank=True,
        help_text="Minimum safety rating required"
    )
    min_skill_rating = models.FloatField(
        null=True,
        blank=True,
        help_text="Minimum skill rating required"
    )
    max_entries = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum number of entries allowed"
    )
    
    # Enhanced: Custom entry requirements
    entry_requirements = models.JSONField(
        null=True,
        blank=True,
        help_text="Custom requirements like specific licenses, achievements, etc."
    )
    
    # Existing fields
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
            models.Index(fields=["series"]),
            models.Index(fields=["simulator"]),
            models.Index(fields=["sim_layout"]),
            models.Index(fields=["event_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["slug"]),
            # Enhanced indexes for new fields
            models.Index(fields=["event_source"]),
            models.Index(fields=["organizing_club"]),
            models.Index(fields=["organizing_user"]),
            models.Index(fields=["visibility"]),
            models.Index(fields=["event_source", "visibility"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    # Must have exactly one organizer type (or none for imported events)
                    models.Q(organizing_club__isnull=False, organizing_user__isnull=True) |
                    models.Q(organizing_club__isnull=True, organizing_user__isnull=False) |
                    models.Q(organizing_club__isnull=True, organizing_user__isnull=True)
                ),
                name='event_has_single_organizer_or_none'
            )
        ]

    def __str__(self):
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
        elif self.organizing_club:
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
        return self.event_source in [EventSource.SPECIAL, EventSource.SERIES]
    
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
                ClubMember = apps.get_model('teams', 'ClubMember')
                member = ClubMember.objects.get(user=user, club=self.organizing_club)
                
                if self.visibility == EventVisibility.CLUB_ONLY:
                    return True  # Any club member can view
                elif self.visibility in [EventVisibility.INVITE_ONLY, EventVisibility.PRIVATE]:
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
                ClubMember = apps.get_model('teams', 'ClubMember')
                member = ClubMember.objects.get(user=user, club=self.organizing_club)
                return member.can_manage_club()
            except ClubMember.DoesNotExist:
                pass
        
        return False
    
    def _check_profile_requirements(self, sim_profile):
        """Check if a sim profile meets event requirements"""
        # Check skill rating
        if self.min_skill_rating:
            skill_ratings = sim_profile.ratings.filter(
                rating_system__category='SKILL'
            ).order_by('-recorded_at')
            if not skill_ratings.exists():
                return False
            if skill_ratings.first().value < self.min_skill_rating:
                return False
        
        # Check safety rating
        if self.min_safety_rating:
            safety_ratings = sim_profile.ratings.filter(
                rating_system__category='SAFETY'
            ).order_by('-recorded_at')
            if not safety_ratings.exists():
                return False
            if safety_ratings.first().value < self.min_safety_rating:
                return False
        
        # Check license level (would need license data in sim profile)
        if self.min_license_level:
            # This would need license information stored in sim profile
            # For now, assume it passes
            pass
        
        return True


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
    slug = models.SlugField(max_length=280, blank=True)
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
        unique_together = ["event", "slug"]
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["car_class"]),
            models.Index(fields=["event", "slug"]),
        ]

    def __str__(self):
        return f"{self.event.name} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness within event
            counter = 1
            original_slug = self.slug
            while EventClass.objects.filter(event=self.event, slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class EventInstance(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="instances")
    slug = models.SlugField(max_length=300, blank=True)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    registration_open = models.DateTimeField()
    registration_ends = models.DateTimeField()
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
            while EventInstance.objects.filter(
                event=self.event,
                slug=self.slug,
            ).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


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
