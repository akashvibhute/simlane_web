import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.text import slugify
from django.contrib.auth import get_user_model

from simlane.sim.models import Event
from simlane.sim.models import EventClass
from simlane.sim.models import EventInstance
from simlane.sim.models import SimCar
from simlane.sim.models import SimProfile
from simlane.sim.models import PitData
from simlane.users.models import User


class ClubRole(models.TextChoices):
    ADMIN = "admin", "Admin"
    TEAMS_MANAGER = "teams_manager", "Teams Manager"
    MEMBER = "member", "Member"


# Create your models here.
class Club(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)
    website = models.URLField(blank=True)
    social_links = models.JSONField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=False, help_text="Allow public viewing of club stats and information")
    discord_guild_id = models.CharField(max_length=50, blank=True)
    
    # ENHANCED: Track who created the club
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,  # Don't delete club if creator is deleted
        related_name="created_clubs",
        null=True,  # Allow null for existing clubs
        blank=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["discord_guild_id"]),
        ]

    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        """Ensure club creator becomes admin on club creation and generate slug"""
        is_new = self.pk is None
        
        # Auto-generate slug if not provided
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness
            counter = 1
            original_slug = self.slug
            while Club.objects.filter(slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        super().save(*args, **kwargs)
        
        # If this is a new club and we have a creator, make them admin
        if is_new and self.created_by:
            ClubMember.objects.get_or_create(
                user=self.created_by,
                club=self,
                defaults={'role': ClubRole.ADMIN}
            )


class ClubMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="clubs")
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=50, choices=ClubRole.choices, default=ClubRole.MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "club"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["club"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.club.name}"

    def can_manage_club(self):
        """Check if user has admin or teams manager privileges."""
        return self.role in [ClubRole.ADMIN, ClubRole.TEAMS_MANAGER]

    def is_admin(self):
        """Check if user is club admin."""
        return self.role == ClubRole.ADMIN


class Team(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="teams")
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["club", "name", "slug"]
        indexes = [
            models.Index(fields=["club"]),
            models.Index(fields=["club", "slug"]),
        ]

    def __str__(self):
        return f"{self.club.name} - {self.name}"
    
    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided"""
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness within the club
            counter = 1
            original_slug = self.slug
            while Team.objects.filter(club=self.club, slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        super().save(*args, **kwargs)


class TeamMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="team_members",
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "team"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["team"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.team.name}"


class EventEntry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="entries")
    sim_car = models.ForeignKey(
        SimCar,
        on_delete=models.CASCADE,
        related_name="entries",
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entries",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="event_entries",
    )
    event_class = models.ForeignKey(
        EventClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entries",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["event"]),
            models.Index(fields=["sim_car"]),
            models.Index(fields=["team"]),
            models.Index(fields=["user"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.event.name}"


class DriverAvailability(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_entry = models.ForeignKey(
        EventEntry,
        on_delete=models.CASCADE,
        related_name="availabilities",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="driver_availabilities",
    )
    instance = models.ForeignKey(
        EventInstance,
        on_delete=models.CASCADE,
        related_name="availabilities",
    )
    available = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["event_entry", "user", "instance"]
        indexes = [
            models.Index(fields=["event_entry"]),
            models.Index(fields=["user"]),
            models.Index(fields=["instance"]),
        ]

    def __str__(self):
        return (
            f"{self.event_entry.user.username} - "
            f"{self.instance.event.name} - "
            f"{self.available}"
        )


class PredictedStint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_entry = models.ForeignKey(
        EventEntry,
        on_delete=models.CASCADE,
        related_name="predicted_stints",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="predicted_stints",
    )
    instance = models.ForeignKey(
        EventInstance,
        on_delete=models.CASCADE,
        related_name="predicted_stints",
    )
    stint_order = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["event_entry"]),
            models.Index(fields=["user"]),
            models.Index(fields=["instance"]),
        ]

    def __str__(self):
        return (
            f"{self.event_entry.user.username} - "
            f"{self.instance.event.name} - "
            f"{self.stint_order}"
        )


# NEW MODELS FOR CLUB MANAGEMENT SYSTEM

class ClubInvitation(models.Model):
    """Track invitations sent to users to join clubs"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_invitations")
    
    # Use ClubRole for invitation
    role = models.CharField(
        max_length=50, 
        choices=ClubRole.choices, 
        default=ClubRole.MEMBER,
        help_text="Role the user will have in this specific club"
    )
    
    # More secure token with expiry tracking
    token = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    
    # Better tracking and communication
    personal_message = models.TextField(blank=True, max_length=500)
    reminder_sent_at = models.DateTimeField(null=True, blank=True)
    reminder_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['club', 'email']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['expires_at']),
            models.Index(fields=['club', 'email']),
        ]
    
    def __str__(self):
        return f"Invitation to {self.email} for {self.club.name}"
    
    @staticmethod
    def generate_token() -> str:
        """Generate a secure unique token"""
        import secrets
        return secrets.token_urlsafe(32)
    
    def is_expired(self):
        return timezone.now() > self.expires_at
    
    def can_send_reminder(self):
        """Check if reminder can be sent (max 2 reminders, 24h apart)"""
        if self.reminder_count >= 2:
            return False
        if self.reminder_sent_at:
            return timezone.now() - self.reminder_sent_at > timedelta(hours=24)
        return True
    
    def accept(self, user):
        """Accept invitation and create ClubMember with specified role"""
        if self.is_expired():
            raise ValueError("Invitation has expired")
        
        # Create or update club membership
        club_member, created = ClubMember.objects.get_or_create(
            user=user,
            club=self.club,
            defaults={'role': self.role}
        )
        
        if not created:
            # User was already a member, update their role if invitation role is higher
            if self.role == ClubRole.ADMIN:
                club_member.role = ClubRole.ADMIN
            elif self.role == ClubRole.TEAMS_MANAGER and club_member.role == ClubRole.MEMBER:
                club_member.role = ClubRole.TEAMS_MANAGER
            club_member.save()
        
        # Mark invitation as accepted
        self.accepted_at = timezone.now()
        self.save()
        
        return club_member
    
    def decline(self):
        """Decline the invitation"""
        self.declined_at = timezone.now()
        self.save()


class ClubEvent(models.Model):
    """Club-specific event organization around existing sim.Event"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="club_events")
    
    # Link to existing sim.Event
    base_event = models.ForeignKey(
        Event, 
        on_delete=models.CASCADE, 
        related_name="club_events"
    )
    
    # Club-specific event settings
    title = models.CharField(max_length=255, help_text="Club-specific event title")
    slug = models.SlugField(max_length=280, blank=True)
    description = models.TextField(blank=True)
    signup_deadline = models.DateTimeField()
    max_participants = models.IntegerField(null=True, blank=True)
    
    # Team management settings
    requires_team_assignment = models.BooleanField(default=True)
    auto_assign_teams = models.BooleanField(default=False)
    team_size_min = models.IntegerField(default=2)
    team_size_max = models.IntegerField(default=4)
    
    # Status tracking
    status = models.CharField(max_length=20, choices=[
        ('draft', 'Draft'),
        ('signup_open', 'Signup Open'),
        ('signup_closed', 'Signup Closed'),
        ('teams_assigned', 'Teams Assigned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft')
    
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['club', 'base_event', 'slug']
        indexes = [
            models.Index(fields=['club']),
            models.Index(fields=['base_event']),
            models.Index(fields=['status']),
            models.Index(fields=['signup_deadline']),
            models.Index(fields=['club', 'slug']),
        ]
    
    def __str__(self):
        return f"{self.club.name} - {self.title}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
            # Ensure uniqueness within club
            counter = 1
            original_slug = self.slug
            while ClubEvent.objects.filter(club=self.club, slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)

    @property
    def is_signup_open(self):
        return self.status == 'signup_open' and timezone.now() < self.signup_deadline

    @property
    def track_layout(self):
        """Get the track layout from the base event"""
        return self.base_event.sim_layout

    @property
    def pit_data(self):
        """Get pit data from the track layout"""
        if self.track_layout and self.track_layout.pit_data:
            return self.track_layout.pit_data
        return None


class EventSignup(models.Model):
    """Member signup for club events with preferences"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club_event = models.ForeignKey(ClubEvent, on_delete=models.CASCADE, related_name="signups")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="event_signups")
    
    # Car preferences (ManyToMany will be set after this model is defined)
    # preferred_cars
    # backup_cars
    
    # Availability and preferences
    can_drive = models.BooleanField(default=True)
    can_spectate = models.BooleanField(default=True)
    experience_level = models.CharField(max_length=20, choices=[
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('professional', 'Professional'),
    ], default='intermediate')
    
    # Link to sim profile for automatic skill assessment
    primary_sim_profile = models.ForeignKey(
        SimProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Primary sim profile for skill assessment"
    )
    
    # Better availability tracking
    availability_notes = models.TextField(blank=True)
    max_stint_duration = models.IntegerField(null=True, blank=True, help_text="Maximum stint duration in minutes")
    min_rest_duration = models.IntegerField(null=True, blank=True, help_text="Minimum rest between stints in minutes")
    
    notes = models.TextField(blank=True)
    
    # Team assignment (filled by admin)
    assigned_team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True)
    assigned_at = models.DateTimeField(null=True, blank=True)
    assignment_locked = models.BooleanField(default=False)  # Prevent auto-reassignment
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['club_event', 'user']
        indexes = [
            models.Index(fields=['club_event', 'assigned_team']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['experience_level']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.club_event.title}"
    
    def get_skill_rating(self):
        """Get skill rating from sim profile if available"""
        if self.primary_sim_profile:
            # Get latest rating from the profile
            latest_rating = self.primary_sim_profile.ratings.filter(
                rating_system__category='SKILL'
            ).order_by('-recorded_at').first()
            return latest_rating.value if latest_rating else None
        return None
    
    def get_track_experience(self):
        """Get lap times for this track if available"""
        if self.primary_sim_profile and self.club_event.track_layout:
            return self.primary_sim_profile.lap_times.filter(
                sim_layout=self.club_event.track_layout,
                is_valid=True
            ).order_by('lap_time_ms')
        return None


# Add ManyToMany relationships after EventSignup is defined
EventSignup.add_to_class('preferred_cars', models.ManyToManyField(SimCar, blank=True, related_name="preferred_signups"))
EventSignup.add_to_class('backup_cars', models.ManyToManyField(SimCar, blank=True, related_name="backup_signups"))
EventSignup.add_to_class('preferred_instances', models.ManyToManyField(EventInstance, blank=True, related_name="signups"))
EventSignup.add_to_class('preferred_classes', models.ManyToManyField(EventClass, blank=True, related_name="signups"))


class EventSignupAvailability(models.Model):
    """Member availability for event instances"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signup = models.ForeignKey(EventSignup, on_delete=models.CASCADE, related_name="availabilities")
    event_instance = models.ForeignKey(EventInstance, on_delete=models.CASCADE)
    available = models.BooleanField(default=True)
    preferred_stint_duration = models.IntegerField(null=True, blank=True, help_text="Preferred stint duration in minutes")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['signup', 'event_instance']
        indexes = [
            models.Index(fields=['signup']),
            models.Index(fields=['event_instance']),
        ]
    
    def __str__(self):
        return f"{self.signup.user.username} - {self.event_instance} - {'Available' if self.available else 'Unavailable'}"


class TeamAllocation(models.Model):
    """Team allocation for club events"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club_event = models.ForeignKey(ClubEvent, on_delete=models.CASCADE, related_name="allocations")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="allocations")
    slug = models.SlugField(max_length=320, blank=True)
    assigned_sim_car = models.ForeignKey(SimCar, on_delete=models.CASCADE)
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['club_event', 'team', 'slug']
        indexes = [
            models.Index(fields=['club_event']),
            models.Index(fields=['team']),
            models.Index(fields=['club_event', 'slug']),
        ]
    
    def __str__(self):
        return f"{self.club_event.title} - {self.team.name}"
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.team.name} {self.club_event.title}")
            # Ensure uniqueness within club_event
            counter = 1
            original_slug = self.slug
            while TeamAllocation.objects.filter(club_event=self.club_event, slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class TeamAllocationMember(models.Model):
    """Members assigned to each team allocation"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team_allocation = models.ForeignKey(TeamAllocation, on_delete=models.CASCADE, related_name="members")
    event_signup = models.ForeignKey(EventSignup, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=[
        ('driver', 'Driver'),
        ('reserve', 'Reserve Driver'),
        ('spotter', 'Spotter'),
        ('strategist', 'Strategist'),
    ], default='driver')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['team_allocation', 'event_signup']
        indexes = [
            models.Index(fields=['team_allocation']),
            models.Index(fields=['event_signup']),
        ]
    
    def __str__(self):
        return f"{self.event_signup.user.username} - {self.team_allocation.team.name} ({self.role})"


class TeamEventStrategy(models.Model):
    """Strategy planning with deep pit data and weather integration"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="event_strategies")
    club_event = models.ForeignKey(ClubEvent, on_delete=models.CASCADE, related_name="team_strategies")
    team_allocation = models.OneToOneField(TeamAllocation, on_delete=models.CASCADE, related_name="strategy")
    slug = models.SlugField(max_length=340, blank=True)
    
    # Direct sim model relationships
    selected_car = models.ForeignKey(SimCar, on_delete=models.CASCADE)
    selected_instance = models.ForeignKey(EventInstance, on_delete=models.CASCADE)
    selected_class = models.ForeignKey(EventClass, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Strategy data
    strategy_notes = models.TextField(blank=True)
    
    # Automated calculations using pit data
    calculated_pit_windows = models.JSONField(
        null=True, 
        blank=True, 
        help_text="Calculated using PitData - optimal pit stop windows"
    )
    fuel_strategy = models.JSONField(
        null=True, 
        blank=True, 
        help_text="Fuel loads per stint calculated from PitData.refuel_flow_rate"
    )
    tire_strategy = models.JSONField(
        null=True, 
        blank=True, 
        help_text="Tire change schedule based on PitData.tire_change_all_four_sec"
    )
    weather_contingencies = models.JSONField(
        null=True, 
        blank=True, 
        help_text="Strategy adjustments based on WeatherForecast data"
    )
    
    # Strategy management
    is_finalized = models.BooleanField(default=False)
    finalized_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="finalized_strategies")
    finalized_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['team', 'club_event', 'slug']
        indexes = [
            models.Index(fields=['team']),
            models.Index(fields=['club_event']),
            models.Index(fields=['team_allocation']),
            models.Index(fields=['team', 'slug']),
        ]

    def __str__(self):
        return f"{self.team.name} - {self.club_event.title} Strategy"
    
    def calculate_optimal_strategy(self):
        """Calculate optimal strategy using pit data and weather forecasts"""
        if not self.club_event.pit_data:
            return None
        
        pit_data = self.club_event.pit_data
        event_duration = self.selected_instance.end_time - self.selected_instance.start_time
        
        # Calculate fuel strategy
        fuel_strategy = {
            'refuel_flow_rate': pit_data.refuel_flow_rate,
            'fuel_unit': pit_data.fuel_unit,
            'optimal_fuel_loads': []  # Would be calculated based on stint length
        }
        
        # Calculate pit windows
        pit_windows = {
            'drive_through_penalty': pit_data.drive_through_loss_sec,
            'stop_go_penalty': pit_data.stop_go_base_loss_sec,
            'tire_change_time': pit_data.tire_change_all_four_sec,
            'simultaneous_actions': pit_data.simultaneous_actions,
            'tire_then_refuel': pit_data.tire_then_refuel
        }
        
        # Get weather data if available
        weather_data = []
        if hasattr(self.selected_instance, 'weather_forecasts'):
            weather_data = list(self.selected_instance.weather_forecasts.all().values())
        
        return {
            'fuel_strategy': fuel_strategy,
            'pit_windows': pit_windows,
            'weather_contingencies': weather_data,
            'calculated_at': timezone.now().isoformat()
        }

    def save(self, *args, **kwargs):
        # Generate slug if not provided
        if not self.slug:
            self.slug = slugify(f"{self.team.name} {self.club_event.title} strategy")
            # Ensure uniqueness within team
            counter = 1
            original_slug = self.slug
            while TeamEventStrategy.objects.filter(team=self.team, slug=self.slug).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        
        # Auto-calculate strategy on save
        if self.club_event.pit_data and not self.calculated_pit_windows:
            strategy = self.calculate_optimal_strategy()
            if strategy:
                self.fuel_strategy = strategy['fuel_strategy']
                self.calculated_pit_windows = strategy['pit_windows']
                self.weather_contingencies = strategy['weather_contingencies']
        
        super().save(*args, **kwargs)


class StintAssignment(models.Model):
    """Stint assignments with pit strategy integration"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team_strategy = models.ForeignKey(TeamEventStrategy, on_delete=models.CASCADE, related_name="stint_assignments")
    driver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="stint_assignments")
    
    stint_number = models.IntegerField()
    estimated_start_time = models.DateTimeField()
    estimated_end_time = models.DateTimeField()
    estimated_duration_minutes = models.IntegerField()
    
    # Link to existing PredictedStint model
    predicted_stint = models.OneToOneField(
        PredictedStint, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="club_assignment"
    )
    
    # More detailed role assignments
    role = models.CharField(max_length=20, choices=[
        ('primary_driver', 'Primary Driver'),
        ('secondary_driver', 'Secondary Driver'),
        ('reserve_driver', 'Reserve Driver'),
        ('spotter', 'Spotter'),
        ('strategist', 'Strategist'),
        ('pit_crew', 'Pit Crew'),
    ], default='primary_driver')
    
    # Pit strategy for this stint
    pit_entry_planned = models.BooleanField(default=False)
    pit_strategy_notes = models.TextField(blank=True)
    fuel_load_start = models.FloatField(null=True, blank=True, help_text="Fuel load at stint start")
    fuel_load_end = models.FloatField(null=True, blank=True, help_text="Expected fuel at stint end")
    tire_compound = models.CharField(max_length=50, blank=True)
    
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['team_strategy', 'stint_number']
        indexes = [
            models.Index(fields=['team_strategy', 'driver']),
            models.Index(fields=['estimated_start_time']),
            models.Index(fields=['stint_number']),
        ]
    
    def __str__(self):
        return f"{self.driver.username} - Stint {self.stint_number} ({self.team_strategy.club_event.title})"
    
    def calculate_pit_strategy(self):
        """Calculate pit requirements for this stint using PitData"""
        if not self.team_strategy.selected_car.pit_data:
            return None
        
        pit_data = self.team_strategy.selected_car.pit_data
        
        # Calculate fuel needed for stint
        return {
            'refuel_time': (self.fuel_load_start / pit_data.refuel_flow_rate) if self.fuel_load_start else 0,
            'tire_change_time': pit_data.tire_change_all_four_sec if self.tire_compound else 0,
            'total_pit_time': 0,  # Would be calculated based on above and simultaneous_actions
        }
