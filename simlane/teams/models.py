import uuid
from datetime import timedelta

from django.db import models
from django.utils import timezone
from django.utils.text import slugify

from simlane.sim.models import Event
from simlane.sim.models import EventClass
from simlane.sim.models import EventInstance
from simlane.sim.models import SimCar
from simlane.sim.models import SimProfile
from simlane.sim.models import Simulator
from simlane.users.models import User

# Enhanced imports for unified system
import secrets
import pytz
from django.core.exceptions import ValidationError


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
    is_public = models.BooleanField(
        default=False,
        help_text="Allow public viewing of club stats and information",
    )
    discord_guild_id = models.CharField(max_length=50, blank=True)

    # ENHANCED: Track who created the club
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,  # Don't delete club if creator is deleted
        related_name="created_clubs",
        null=True,  # Allow null for existing clubs
        blank=True,
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
                defaults={"role": ClubRole.ADMIN},
            )


class ClubMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="clubs")
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="members")
    role = models.CharField(max_length=50, choices=ClubRole, default=ClubRole.MEMBER)
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
    
    # Team ownership - either user-created OR imported from simulator
    owner_user = models.ForeignKey(
        User,
        on_delete=models.PROTECT,  # Protect team from accidental user deletion
        related_name="owned_teams",
        null=True,
        blank=True,
        help_text="User who created this team (for user-created teams)"
    )
    
    # For imported teams - linked to SimProfile which may or may not have a User
    owner_sim_profile = models.ForeignKey(
        SimProfile,
        on_delete=models.PROTECT,  # Protect team from profile deletion
        related_name="owned_teams",
        null=True,
        blank=True,
        help_text="SimProfile that owns this team (for imported teams)"
    )
    
    # Optional club association
    club = models.ForeignKey(
        Club, 
        on_delete=models.SET_NULL,  # Team can exist without club
        related_name="teams",
        null=True,
        blank=True,
        help_text="Club this team is associated with (optional)"
    )
    
    # Team identity
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)
    
    # Simulator integration - if external_team_id exists, team is imported
    external_team_id = models.CharField(
        max_length=255, 
        blank=True,
        null=True,
        help_text="Team ID from simulator (e.g., iRacing team ID). If present, team is imported."
    )
    source_simulator = models.ForeignKey(
        Simulator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="imported_teams",
        help_text="Simulator this team was imported from"
    )
    
    # Team settings
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(
        default=True,
        help_text="Whether this team is visible to other users"
    )
    is_temporary = models.BooleanField(
        default=False,
        help_text="Temporary teams created for specific events"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [
            ["owner_user", "slug"],  # Unique slug per user (when user-owned)
            ["owner_sim_profile", "slug"],  # Unique slug per sim profile (when imported)
            ["club", "slug"],  # Unique slug per club (when associated)
        ]
        indexes = [
            models.Index(fields=["owner_user"]),
            models.Index(fields=["owner_sim_profile"]),
            models.Index(fields=["club"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["external_team_id", "source_simulator"]),
        ]
        constraints = [
            models.CheckConstraint(
                check=(
                    # Must have exactly one owner type
                    models.Q(owner_user__isnull=False, owner_sim_profile__isnull=True) |
                    models.Q(owner_user__isnull=True, owner_sim_profile__isnull=False)
                ),
                name='team_has_single_owner_type'
            )
        ]

    def __str__(self):
        if self.club:
            return f"{self.club.name} - {self.name}"
        elif self.owner_user:
            return f"{self.name} (by {self.owner_user.username})"
        elif self.owner_sim_profile:
            if self.owner_sim_profile.user:
                return f"{self.name} (by {self.owner_sim_profile.user.username})"
            else:
                return f"{self.name} (by {self.owner_sim_profile.profile_name})"
        return self.name

    def save(self, *args, **kwargs):
        """Auto-generate slug if not provided"""
        if not self.slug:
            self.slug = slugify(self.name)
            # Ensure uniqueness based on context
            counter = 1
            original_slug = self.slug
            
            # Check uniqueness within owner's teams
            if self.owner_user:
                while Team.objects.filter(
                    owner_user=self.owner_user, 
                    slug=self.slug
                ).exclude(pk=self.pk).exists():
                    self.slug = f"{original_slug}-{counter}"
                    counter += 1
            
            # Check uniqueness within sim profile's teams  
            if self.owner_sim_profile:
                while Team.objects.filter(
                    owner_sim_profile=self.owner_sim_profile, 
                    slug=self.slug
                ).exclude(pk=self.pk).exists():
                    self.slug = f"{original_slug}-{counter}"
                    counter += 1
            
            # Also check within club if associated
            if self.club:
                while Team.objects.filter(
                    club=self.club, 
                    slug=self.slug
                ).exclude(pk=self.pk).exists():
                    self.slug = f"{original_slug}-{counter}"
                    counter += 1

        super().save(*args, **kwargs)
    
    @property
    def effective_owner(self):
        """Get the effective owner user (if any)"""
        if self.owner_user:
            return self.owner_user
        elif self.owner_sim_profile and self.owner_sim_profile.user:
            return self.owner_sim_profile.user
        return None
    
    @property
    def is_imported(self):
        """Check if this team was imported from a simulator"""
        return bool(self.external_team_id)
    
    @property
    def is_claimable(self):
        """Check if this team can be claimed by a user"""
        # Imported teams with sim profiles that have no user can be claimed
        return (self.is_imported and 
                self.owner_sim_profile and 
                not self.owner_sim_profile.user)
    
    def can_user_manage(self, user):
        """Check if a user can manage this team"""
        # Direct owner can always manage
        if user == self.owner_user:
            return True
        
        # Sim profile owner can manage if they have a user account
        if (self.owner_sim_profile and 
            self.owner_sim_profile.user == user):
            return True
        
        # If club team, check club permissions
        if self.club:
            try:
                member = self.club.members.get(user=user)
                return member.can_manage_club()
            except ClubMember.DoesNotExist:
                pass
        
        return False
    
    def can_user_view(self, user):
        """Check if a user can view this team"""
        # Public teams are visible to all
        if self.is_public:
            return True
        
        # Direct owner can always view
        if user == self.owner_user:
            return True
        
        # Sim profile owner can view if they have a user account
        if (self.owner_sim_profile and 
            self.owner_sim_profile.user == user):
            return True
        
        # Members can view their team
        # This will be checked via TeamMember model when called
        from django.apps import apps
        TeamMember = apps.get_model('teams', 'TeamMember')
        if TeamMember.objects.filter(team=self, user=user).exists():
            return True
        
        # Club members can view club teams
        if self.club and self.club.members.filter(user=user).exists():
            return True
        
        return False
    
    def claim_team(self, user):
        """Allow a user to claim an imported team"""
        if not self.is_claimable:
            raise ValueError("This team cannot be claimed")
        
        if not self.owner_sim_profile:
            raise ValueError("No sim profile associated with this team")
        
        # Link the sim profile to the user
        self.owner_sim_profile.user = user
        self.owner_sim_profile.save()
        
        # Optionally make them a team member
        from django.apps import apps
        TeamMember = apps.get_model('teams', 'TeamMember')
        TeamMember.objects.get_or_create(
            team=self,
            user=user,
            defaults={'role': 'owner'}  # We'll need to add this role
        )


class TeamMember(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="team_members",
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    
    # Enhanced role system
    role = models.CharField(
        max_length=20,
        choices=[
            ('owner', 'Team Owner'),
            ('manager', 'Team Manager'),
            ('driver', 'Driver'),
            ('reserve', 'Reserve Driver'),
            ('engineer', 'Engineer/Strategist'),
            ('spotter', 'Spotter'),
            ('guest', 'Guest Driver')
        ],
        default='driver'
    )
    
    # Permissions within team
    can_manage_entries = models.BooleanField(
        default=False,
        help_text="Can manage event entries for this team"
    )
    can_invite_members = models.BooleanField(
        default=False,
        help_text="Can invite new members to this team"
    )
    can_edit_team = models.BooleanField(
        default=False,
        help_text="Can edit team settings and information"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('suspended', 'Suspended')
        ],
        default='active'
    )
    
    # For temporary/event-specific membership
    valid_from = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When this membership becomes valid"
    )
    valid_until = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="When this membership expires"
    )
    
    # Metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["user", "team"]
        indexes = [
            models.Index(fields=["user"]),
            models.Index(fields=["team"]),
            models.Index(fields=["role"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.team.name} ({self.role})"
    
    def is_manager_level(self):
        """Check if this member has management privileges"""
        return self.role in ['owner', 'manager'] or any([
            self.can_manage_entries,
            self.can_invite_members, 
            self.can_edit_team
        ])
    
    def is_active_membership(self):
        """Check if membership is currently active"""
        if self.status != 'active':
            return False
        
        from django.utils import timezone
        now = timezone.now()
        
        if self.valid_from and now < self.valid_from:
            return False
        
        if self.valid_until and now > self.valid_until:
            return False
        
        return True


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

# ===== UNIFIED EVENT PARTICIPATION MODELS =====

class EventParticipation(models.Model):
    """
    Unified model for ALL event participation - replaces EventEntry and EventSignupEntry
    Supports both individual users and teams, with flexible workflow states
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # === CORE RELATIONSHIPS ===
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="participations"
    )
    
    # Participant can be EITHER user OR team
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="event_participations"
    )
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="event_participations"
    )
    
    # === PARTICIPATION TYPE ===
    participation_type = models.CharField(
        max_length=20,
        choices=[
            ('individual', 'Individual Entry'),        # Direct participation
            ('team_signup', 'Team Event Signup'),      # Phase 1: Interest collection
            ('team_entry', 'Team Event Entry'),        # Phase 2: Actual team entry
        ],
        help_text="Type of participation in this event"
    )
    
    # === WORKFLOW STATUS ===
    status = models.CharField(
        max_length=20,
        choices=[
            # Phase 1: Signup/Interest
            ('interested', 'Interested'),
            ('signed_up', 'Signed Up'),
            
            # Phase 2: Team Formation  
            ('team_formation', 'Awaiting Team Formation'),
            ('team_assigned', 'Team Assigned'),
            
            # Phase 3: Event Entry
            ('entry_pending', 'Entry Pending'),
            ('entered', 'Event Entry Confirmed'),
            
            # Final states
            ('confirmed', 'Confirmed for Race'),
            ('waitlist', 'Waitlist'),
            ('withdrawn', 'Withdrawn'),
            ('participated', 'Participated'),
        ],
        default='interested'
    )
    
    # === CAR AND CLASS SELECTION ===
    preferred_car = models.ForeignKey(
        SimCar,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="preferred_participations"
    )
    backup_car = models.ForeignKey(
        SimCar,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="backup_participations"
    )
    assigned_car = models.ForeignKey(
        SimCar,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_participations",
        help_text="Final car assignment after team formation"
    )
    
    # Class selection
    preferred_classes = models.ManyToManyField(
        EventClass,
        blank=True,
        related_name="preferred_participations"
    )
    assigned_class = models.ForeignKey(
        EventClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_participations"
    )
    
    # === RACE DAY DETAILS ===
    car_number = models.CharField(
        max_length=10, 
        blank=True,
        help_text="Assigned car number for race day"
    )
    starting_position = models.IntegerField(
        null=True,
        blank=True,
        help_text="Starting grid position (if applicable)"
    )
    
    # === PREFERENCES AND REQUIREMENTS ===
    experience_level = models.CharField(
        max_length=20,
        choices=[
            ('beginner', 'Beginner'),
            ('intermediate', 'Intermediate'),
            ('advanced', 'Advanced'),
            ('professional', 'Professional'),
        ],
        blank=True
    )
    
    # Stint preferences  
    max_stint_duration = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum stint duration in minutes"
    )
    min_rest_duration = models.IntegerField(
        null=True,
        blank=True,
        help_text="Minimum rest between stints in minutes"
    )
    
    # === TIMEZONE AND LOCATION ===
    participant_timezone = models.CharField(
        max_length=50,
        blank=True,
        help_text="Participant's timezone for this event (e.g., 'America/New_York')"
    )
    
    # === CLUB EVENT INTEGRATION ===
    club_event = models.ForeignKey(
        "ClubEvent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participations",
        help_text="Club event this participation is associated with"
    )
    
    # Link to team allocation (for club events)
    team_allocation = models.ForeignKey(
        "TeamAllocation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="participations"
    )
    
    # For individual team formation
    signup_invitation = models.ForeignKey(
        "EventSignupInvitation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Invitation that led to this signup (for individual-organized events)"
    )
    
    # === METADATA ===
    notes = models.TextField(blank=True)
    registration_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional registration information"
    )
    
    # === TIMESTAMPS ===
    signed_up_at = models.DateTimeField(null=True, blank=True)
    team_assigned_at = models.DateTimeField(null=True, blank=True) 
    entered_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    withdrawn_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    # Must have exactly one participant type
                    models.Q(user__isnull=False, team__isnull=True) |
                    models.Q(user__isnull=True, team__isnull=False)
                ),
                name='participation_has_single_participant_type'
            ),
            models.CheckConstraint(
                check=(
                    # Team entries must have team set
                    ~models.Q(participation_type='team_entry', team__isnull=True)
                ),
                name='team_entry_requires_team'
            )
        ]
        
        unique_together = [
            ['event', 'user'],  # User can only participate once per event
            ['event', 'team'],  # Team can only participate once per event
        ]
        
        indexes = [
            models.Index(fields=['event', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['team', 'status']),
            models.Index(fields=['participation_type', 'status']),
            models.Index(fields=['club_event']),
            models.Index(fields=['event', 'participation_type']),
        ]
    
    def __str__(self):
        participant = self.user.username if self.user else self.team.name
        return f"{participant} - {self.event.name} ({self.status})"
    
    @property
    def effective_participant_name(self):
        """Get the name of the participant (user or team)"""
        return self.user.username if self.user else self.team.name
    
    @property
    def is_team_participation(self):
        """Check if this is team-based participation"""
        return self.participation_type in ['team_signup', 'team_entry']
    
    @property
    def is_individual_participation(self):
        """Check if this is individual participation"""
        return self.participation_type == 'individual'
    
    def get_effective_timezone(self):
        """Get participant's timezone, falling back to user profile timezone"""
        if self.participant_timezone:
            return self.participant_timezone
        if self.user and hasattr(self.user, 'timezone'):
            return self.user.timezone
        return 'UTC'  # Default fallback
    
    def can_be_assigned_to_team(self):
        """Check if participation can be assigned to a team"""
        return (self.status in ['signed_up', 'team_formation'] and 
                self.participation_type == 'team_signup')
    
    def assign_to_team(self, team, assigned_by=None):
        """Assign this participation to a team"""
        if not self.can_be_assigned_to_team():
            raise ValueError(f"Cannot assign participation in status {self.status}")
        
        self.team = team
        self.status = 'team_assigned'
        self.team_assigned_at = timezone.now()
        self.save()
        
        return self
    
    def confirm_entry(self):
        """Confirm the event entry"""
        if self.status != 'entered':
            raise ValueError(f"Cannot confirm participation in status {self.status}")
        
        self.status = 'confirmed'
        self.confirmed_at = timezone.now()
        self.save()
        
        return self
    
    @classmethod
    def get_participants_for_event(cls, event, status_filter=None):
        """Get all participants for an event with optional status filter"""
        queryset = cls.objects.filter(event=event).select_related('user', 'team__owner_user')
        
        if status_filter:
            if isinstance(status_filter, str):
                status_filter = [status_filter]
            queryset = queryset.filter(status__in=status_filter)
        
        return queryset
    
    @classmethod
    def get_team_formation_candidates(cls, event):
        """Get participants ready for team formation"""
        return cls.objects.filter(
            event=event,
            participation_type='team_signup',
            status='signed_up'
        ).select_related('user').prefetch_related('availability_windows')


class AvailabilityWindow(models.Model):
    """
    Granular time-based availability with timezone support
    Each record represents a contiguous time window with specific role availability
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    participation = models.ForeignKey(
        EventParticipation,
        on_delete=models.CASCADE,
        related_name="availability_windows"
    )
    
    # Absolute times stored in UTC
    start_time = models.DateTimeField(help_text="Start time in UTC")
    end_time = models.DateTimeField(help_text="End time in UTC")
    
    # Role-specific availability during this window
    can_drive = models.BooleanField(default=False)
    can_spot = models.BooleanField(default=False)
    can_strategize = models.BooleanField(default=False)
    
    # Preference level for this window
    preference_level = models.IntegerField(
        choices=[
            (1, 'Strongly Preferred'),
            (2, 'Preferred'), 
            (3, 'Available'),
            (4, 'If Needed'),
            (5, 'Emergency Only')
        ],
        default=3,
        help_text="How much the user prefers this time slot"
    )
    
    # Constraints for this window
    max_consecutive_stints = models.IntegerField(
        default=1,
        help_text="Max consecutive stints during this window"
    )
    preferred_stint_length = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Preferred stint length in minutes for this window"
    )
    
    # Metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['participation']),
            models.Index(fields=['start_time', 'end_time']),
            models.Index(fields=['can_drive', 'can_spot']),
            models.Index(fields=['preference_level']),
            # Compound index for overlap queries
            models.Index(fields=['participation', 'start_time', 'end_time']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(start_time__lt=models.F('end_time')),
                name='availability_window_valid_time_range'
            ),
            models.CheckConstraint(
                check=(
                    models.Q(can_drive=True) |
                    models.Q(can_spot=True) |
                    models.Q(can_strategize=True)
                ),
                name='availability_window_has_role'
            )
        ]
    
    def __str__(self):
        participant = self.participation.effective_participant_name
        roles = []
        if self.can_drive: roles.append('drive')
        if self.can_spot: roles.append('spot')
        if self.can_strategize: roles.append('strategize')
        return f"{participant} - {self.start_time} to {self.end_time} ({'/'.join(roles)})"
    
    def get_local_times(self):
        """Get start/end times in participant's timezone"""
        import pytz
        user_tz_str = self.participation.get_effective_timezone()
        user_tz = pytz.timezone(user_tz_str)
        return {
            'start_local': self.start_time.astimezone(user_tz),
            'end_local': self.end_time.astimezone(user_tz),
            'timezone': str(user_tz)
        }
    
    def overlaps_with(self, other_window):
        """Check if this window overlaps with another"""
        return (self.start_time < other_window.end_time and 
                self.end_time > other_window.start_time)
    
    def contains_time(self, target_time):
        """Check if target time falls within this window"""
        return self.start_time <= target_time <= self.end_time
    
    def duration_minutes(self):
        """Get window duration in minutes"""
        return int((self.end_time - self.start_time).total_seconds() / 60)
    
    def duration_hours(self):
        """Get window duration in hours"""
        return self.duration_minutes() / 60
    
    def get_roles_list(self):
        """Get list of available roles during this window"""
        roles = []
        if self.can_drive: roles.append('driver')
        if self.can_spot: roles.append('spotter')
        if self.can_strategize: roles.append('strategist')
        return roles
    
    @classmethod
    def find_available_for_time_range(cls, event, start_time, end_time, role='drive'):
        """
        Find all availability windows that cover the specified time range for a role
        """
        role_field = f'can_{role}' if role in ['drive', 'spot', 'strategize'] else 'can_drive'
        
        return cls.objects.filter(
            participation__event=event,
            start_time__lte=start_time,
            end_time__gte=end_time,
            **{role_field: True}
        ).select_related('participation__user')
    
    @classmethod
    def generate_availability_chart_data(cls, event, display_timezone='UTC'):
        """
        Generate availability chart data for visualization
        """
        import pytz
        
        windows = cls.objects.filter(
            participation__event=event
        ).select_related('participation__user').order_by('start_time')
        
        chart_data = []
        display_tz = pytz.timezone(display_timezone)
        
        for window in windows:
            local_times = window.get_local_times()
            display_start = window.start_time.astimezone(display_tz)
            display_end = window.end_time.astimezone(display_tz)
            
            chart_data.append({
                'user': window.participation.user,
                'user_id': window.participation.user.id if window.participation.user else None,
                'start_utc': window.start_time,
                'end_utc': window.end_time,
                'start_display': display_start,
                'end_display': display_end,
                'start_local': local_times['start_local'],
                'end_local': local_times['end_local'],
                'user_timezone': window.participation.get_effective_timezone(),
                'can_drive': window.can_drive,
                'can_spot': window.can_spot,
                'can_strategize': window.can_strategize,
                'preference_level': window.preference_level,
                'preference_display': f"Level {window.preference_level}",
                'duration_hours': window.duration_hours(),
                'roles': window.get_roles_list(),
                'notes': window.notes
            })
        
        return chart_data
    
    @classmethod
    def find_overlapping_availability(cls, user_ids, event, min_overlap_hours=2):
        """
        Find overlapping availability between multiple users using optimized SQL
        """
        from django.db import connection
        
        sql = """
        WITH user_windows AS (
            SELECT 
                aw.participation_id,
                p.user_id,
                aw.start_time,
                aw.end_time,
                aw.can_drive,
                aw.can_spot,
                aw.preference_level
            FROM teams_availabilitywindow aw
            JOIN teams_eventparticipation p ON aw.participation_id = p.id
            WHERE p.event_id = %s 
              AND p.user_id = ANY(%s)
              AND aw.can_drive = true
        ),
        overlaps AS (
            SELECT 
                w1.user_id as user1_id,
                w2.user_id as user2_id,
                GREATEST(w1.start_time, w2.start_time) as overlap_start,
                LEAST(w1.end_time, w2.end_time) as overlap_end,
                EXTRACT(EPOCH FROM (
                    LEAST(w1.end_time, w2.end_time) - 
                    GREATEST(w1.start_time, w2.start_time)
                )) / 3600 as overlap_hours
            FROM user_windows w1
            JOIN user_windows w2 ON w1.user_id < w2.user_id
            WHERE w1.start_time < w2.end_time 
              AND w1.end_time > w2.start_time
              AND EXTRACT(EPOCH FROM (
                  LEAST(w1.end_time, w2.end_time) - 
                  GREATEST(w1.start_time, w2.start_time)
              )) / 3600 >= %s
        )
        SELECT 
            user1_id,
            user2_id,
            SUM(overlap_hours) as total_overlap_hours,
            COUNT(*) as overlap_count,
            MIN(overlap_start) as first_overlap_start,
            MAX(overlap_end) as last_overlap_end
        FROM overlaps
        GROUP BY user1_id, user2_id
        ORDER BY total_overlap_hours DESC
        """
        
        with connection.cursor() as cursor:
            cursor.execute(sql, [event.id, user_ids, min_overlap_hours])
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    @classmethod
    def get_team_formation_recommendations(cls, event, team_size=3, min_coverage_hours=6):
        """
        Advanced team formation algorithm using availability overlap analysis
        """
        from django.db import connection
        
        # Get all signed up participants
        participants = EventParticipation.objects.filter(
            event=event,
            status='signed_up'
        ).values_list('user_id', flat=True)
        
        if len(participants) < team_size:
            return []
        
        # Find all pairwise overlaps
        overlaps = cls.find_overlapping_availability(
            list(participants), 
            event, 
            min_overlap_hours=1  # Start with any overlap
        )
        
        # Group formation algorithm (simplified)
        # In practice, you'd want a more sophisticated algorithm
        recommendations = []
        used_users = set()
        
        # Sort by total overlap hours
        overlap_dict = {}
        for overlap in overlaps:
            user1, user2 = overlap['user1_id'], overlap['user2_id']
            if user1 not in overlap_dict:
                overlap_dict[user1] = {}
            if user2 not in overlap_dict:
                overlap_dict[user2] = {}
            
            overlap_dict[user1][user2] = overlap['total_overlap_hours']
            overlap_dict[user2][user1] = overlap['total_overlap_hours']
        
        # Simple greedy team formation
        for user1 in participants:
            if user1 in used_users:
                continue
                
            potential_team = [user1]
            candidates = [u for u in participants if u != user1 and u not in used_users]
            
            # Find best teammates based on overlap
            while len(potential_team) < team_size and candidates:
                best_candidate = None
                best_score = 0
                
                for candidate in candidates:
                    score = sum(
                        overlap_dict.get(team_member, {}).get(candidate, 0)
                        for team_member in potential_team
                    )
                    
                    if score > best_score:
                        best_score = score
                        best_candidate = candidate
                
                if best_candidate and best_score > 0:
                    potential_team.append(best_candidate)
                    candidates.remove(best_candidate)
                else:
                    break
            
            if len(potential_team) >= team_size:
                recommendations.append({
                    'team_members': potential_team,
                    'total_overlap_score': best_score,
                    'coverage_estimate': best_score  # Simplified
                })
                used_users.update(potential_team)
        
        return sorted(recommendations, key=lambda x: x['total_overlap_score'], reverse=True)


class EventSignupInvitation(models.Model):
    """
    For individual users to invite others to form teams for events
    Alternative to club-based team formation
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="signup_invitations")
    organizer_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_signup_invitations")
    
    # Invitation details
    team_name = models.CharField(max_length=255, help_text="Proposed team name")
    invitee_email = models.EmailField()
    invitee_user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name="received_signup_invitations"
    )
    
    message = models.TextField(blank=True)
    token = models.CharField(max_length=128, unique=True)
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('declined', 'Declined'),
            ('expired', 'Expired'),
        ],
        default='pending'
    )
    
    expires_at = models.DateTimeField()
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['event', 'organizer_user', 'invitee_email']
        indexes = [
            models.Index(fields=['token']),
            models.Index(fields=['event', 'status']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        return f"Invitation from {self.organizer_user.username} to {self.invitee_email} for {self.team_name}"
    
    @staticmethod
    def generate_token():
        """Generate a secure unique token"""
        import secrets
        return secrets.token_urlsafe(32)
    
    def is_expired(self):
        """Check if invitation has expired"""
        return timezone.now() > self.expires_at
    
    def accept(self, user):
        """Accept invitation and create participation"""
        if self.is_expired():
            raise ValueError("Invitation has expired")
        
        if self.status != 'pending':
            raise ValueError(f"Cannot accept invitation with status {self.status}")
        
        # Create EventParticipation for the invitee
        participation = EventParticipation.objects.create(
            event=self.event,
            user=user,
            participation_type='team_signup',
            status='signed_up',
            signup_invitation=self,
            signed_up_at=timezone.now()
        )
        
        # Update invitation status
        self.status = 'accepted'
        self.responded_at = timezone.now()
        self.invitee_user = user
        self.save()
        
        return participation
    
    def decline(self):
        """Decline the invitation"""
        self.status = 'declined'
        self.responded_at = timezone.now()
        self.save()


class ClubInvitation(models.Model):
    """Track invitations sent to users to join clubs"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    invited_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_invitations",
    )

    # Use ClubRole for invitation
    role = models.CharField(
        max_length=50,
        choices=ClubRole,
        default=ClubRole.MEMBER,
        help_text="Role the user will have in this specific club",
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
        unique_together = ["club", "email"]
        indexes = [
            models.Index(fields=["token"]),
            models.Index(fields=["expires_at"]),
            models.Index(fields=["club", "email"]),
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
            defaults={"role": self.role},
        )

        if not created:
            # User was already a member, update their role if invitation role is higher
            if self.role == ClubRole.ADMIN:
                club_member.role = ClubRole.ADMIN
            elif (
                self.role == ClubRole.TEAMS_MANAGER
                and club_member.role == ClubRole.MEMBER
            ):
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
        related_name="club_events",
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
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("signup_open", "Signup Open"),
            ("signup_closed", "Signup Closed"),
            ("teams_assigned", "Teams Assigned"),
            ("in_progress", "In Progress"),
            ("completed", "Completed"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
    )

    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["club", "base_event", "slug"]
        indexes = [
            models.Index(fields=["club"]),
            models.Index(fields=["base_event"]),
            models.Index(fields=["status"]),
            models.Index(fields=["signup_deadline"]),
            models.Index(fields=["club", "slug"]),
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
        return self.status == "signup_open" and timezone.now() < self.signup_deadline

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
    club_event = models.ForeignKey(
        ClubEvent,
        on_delete=models.CASCADE,
        related_name="signups",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="event_signups",
    )

    # Car preferences (ManyToMany will be set after this model is defined)
    # preferred_cars
    # backup_cars

    # Availability and preferences
    can_drive = models.BooleanField(default=True)
    can_spectate = models.BooleanField(default=True)
    experience_level = models.CharField(
        max_length=20,
        choices=[
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("advanced", "Advanced"),
            ("professional", "Professional"),
        ],
        default="intermediate",
    )

    # Link to sim profile for automatic skill assessment
    primary_sim_profile = models.ForeignKey(
        SimProfile,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Primary sim profile for skill assessment",
    )

    # Better availability tracking
    availability_notes = models.TextField(blank=True)
    max_stint_duration = models.IntegerField(
        null=True,
        blank=True,
        help_text="Maximum stint duration in minutes",
    )
    min_rest_duration = models.IntegerField(
        null=True,
        blank=True,
        help_text="Minimum rest between stints in minutes",
    )

    notes = models.TextField(blank=True)

    # Team assignment (filled by admin)
    assigned_team = models.ForeignKey(
        Team,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    assigned_at = models.DateTimeField(null=True, blank=True)
    assignment_locked = models.BooleanField(default=False)  # Prevent auto-reassignment

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["club_event", "user"]
        indexes = [
            models.Index(fields=["club_event", "assigned_team"]),
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["experience_level"]),
        ]

    def __str__(self):
        return f"{self.user.username} - {self.club_event.title}"

    def get_skill_rating(self):
        """Get skill rating from sim profile if available"""
        if self.primary_sim_profile:
            # Get latest rating from the profile
            latest_rating = (
                self.primary_sim_profile.ratings.filter(
                    rating_system__category="SKILL",
                )
                .order_by("-recorded_at")
                .first()
            )
            return latest_rating.value if latest_rating else None
        return None

    def get_track_experience(self):
        """Get lap times for this track if available"""
        if self.primary_sim_profile and self.club_event.track_layout:
            return self.primary_sim_profile.lap_times.filter(
                sim_layout=self.club_event.track_layout,
                is_valid=True,
            ).order_by("lap_time_ms")
        return None


# Add ManyToMany relationships after EventSignup is defined
EventSignup.add_to_class(
    "preferred_cars",
    models.ManyToManyField(SimCar, blank=True, related_name="preferred_signups"),
)
EventSignup.add_to_class(
    "backup_cars",
    models.ManyToManyField(SimCar, blank=True, related_name="backup_signups"),
)
EventSignup.add_to_class(
    "preferred_instances",
    models.ManyToManyField(EventInstance, blank=True, related_name="signups"),
)
EventSignup.add_to_class(
    "preferred_classes",
    models.ManyToManyField(EventClass, blank=True, related_name="signups"),
)


class EventSignupAvailability(models.Model):
    """Member availability for event instances"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    signup = models.ForeignKey(
        EventSignup,
        on_delete=models.CASCADE,
        related_name="availabilities",
    )
    event_instance = models.ForeignKey(EventInstance, on_delete=models.CASCADE)
    available = models.BooleanField(default=True)
    preferred_stint_duration = models.IntegerField(
        null=True,
        blank=True,
        help_text="Preferred stint duration in minutes",
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["signup", "event_instance"]
        indexes = [
            models.Index(fields=["signup"]),
            models.Index(fields=["event_instance"]),
        ]

    def __str__(self):
        return f"{self.signup.user.username} - {self.event_instance} - {'Available' if self.available else 'Unavailable'}"


class TeamAllocation(models.Model):
    """Team allocation for club events"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club_event = models.ForeignKey(
        ClubEvent,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="allocations")
    slug = models.SlugField(max_length=320, blank=True)
    assigned_sim_car = models.ForeignKey(SimCar, on_delete=models.CASCADE)

    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["club_event", "team", "slug"]
        indexes = [
            models.Index(fields=["club_event"]),
            models.Index(fields=["team"]),
            models.Index(fields=["club_event", "slug"]),
        ]

    def __str__(self):
        return f"{self.club_event.title} - {self.team.name}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(f"{self.team.name} {self.club_event.title}")
            # Ensure uniqueness within club_event
            counter = 1
            original_slug = self.slug
            while TeamAllocation.objects.filter(
                club_event=self.club_event,
                slug=self.slug,
            ).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1
        super().save(*args, **kwargs)


class TeamAllocationMember(models.Model):
    """Members assigned to each team allocation"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team_allocation = models.ForeignKey(
        TeamAllocation,
        on_delete=models.CASCADE,
        related_name="members",
    )
    event_signup = models.ForeignKey(EventSignup, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=20,
        choices=[
            ("driver", "Driver"),
            ("reserve", "Reserve Driver"),
            ("spotter", "Spotter"),
            ("strategist", "Strategist"),
        ],
        default="driver",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["team_allocation", "event_signup"]
        indexes = [
            models.Index(fields=["team_allocation"]),
            models.Index(fields=["event_signup"]),
        ]

    def __str__(self):
        return f"{self.event_signup.user.username} - {self.team_allocation.team.name} ({self.role})"


class TeamEventStrategy(models.Model):
    """Strategy planning with deep pit data and weather integration"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        related_name="event_strategies",
    )
    club_event = models.ForeignKey(
        ClubEvent,
        on_delete=models.CASCADE,
        related_name="team_strategies",
    )
    team_allocation = models.OneToOneField(
        TeamAllocation,
        on_delete=models.CASCADE,
        related_name="strategy",
    )
    slug = models.SlugField(max_length=340, blank=True)

    # Direct sim model relationships
    selected_car = models.ForeignKey(SimCar, on_delete=models.CASCADE)
    selected_instance = models.ForeignKey(EventInstance, on_delete=models.CASCADE)
    selected_class = models.ForeignKey(
        EventClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # Strategy data
    strategy_notes = models.TextField(blank=True)

    # Automated calculations using pit data
    calculated_pit_windows = models.JSONField(
        null=True,
        blank=True,
        help_text="Calculated using PitData - optimal pit stop windows",
    )
    fuel_strategy = models.JSONField(
        null=True,
        blank=True,
        help_text="Fuel loads per stint calculated from PitData.refuel_flow_rate",
    )
    tire_strategy = models.JSONField(
        null=True,
        blank=True,
        help_text="Tire change schedule based on PitData.tire_change_all_four_sec",
    )
    weather_contingencies = models.JSONField(
        null=True,
        blank=True,
        help_text="Strategy adjustments based on WeatherForecast data",
    )

    # Strategy management
    is_finalized = models.BooleanField(default=False)
    finalized_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="finalized_strategies",
    )
    finalized_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["team", "club_event", "slug"]
        indexes = [
            models.Index(fields=["team"]),
            models.Index(fields=["club_event"]),
            models.Index(fields=["team_allocation"]),
            models.Index(fields=["team", "slug"]),
        ]

    def __str__(self):
        return f"{self.team.name} - {self.club_event.title} Strategy"

    def calculate_optimal_strategy(self):
        """Calculate optimal strategy using pit data and weather forecasts"""
        if not self.club_event.pit_data:
            return None

        pit_data = self.club_event.pit_data
        event_duration = (
            self.selected_instance.end_time - self.selected_instance.start_time
        )

        # Calculate fuel strategy
        fuel_strategy = {
            "refuel_flow_rate": pit_data.refuel_flow_rate,
            "fuel_unit": pit_data.fuel_unit,
            "optimal_fuel_loads": [],  # Would be calculated based on stint length
        }

        # Calculate pit windows
        pit_windows = {
            "drive_through_penalty": pit_data.drive_through_loss_sec,
            "stop_go_penalty": pit_data.stop_go_base_loss_sec,
            "tire_change_time": pit_data.tire_change_all_four_sec,
            "simultaneous_actions": pit_data.simultaneous_actions,
            "tire_then_refuel": pit_data.tire_then_refuel,
        }

        # Get weather data if available
        weather_data = []
        if hasattr(self.selected_instance, "weather_forecasts"):
            weather_data = list(self.selected_instance.weather_forecasts.all().values())

        return {
            "fuel_strategy": fuel_strategy,
            "pit_windows": pit_windows,
            "weather_contingencies": weather_data,
            "calculated_at": timezone.now().isoformat(),
        }

    def save(self, *args, **kwargs):
        # Generate slug if not provided
        if not self.slug:
            self.slug = slugify(f"{self.team.name} {self.club_event.title} strategy")
            # Ensure uniqueness within team
            counter = 1
            original_slug = self.slug
            while TeamEventStrategy.objects.filter(
                team=self.team,
                slug=self.slug,
            ).exists():
                self.slug = f"{original_slug}-{counter}"
                counter += 1

        # Auto-calculate strategy on save
        if self.club_event.pit_data and not self.calculated_pit_windows:
            strategy = self.calculate_optimal_strategy()
            if strategy:
                self.fuel_strategy = strategy["fuel_strategy"]
                self.calculated_pit_windows = strategy["pit_windows"]
                self.weather_contingencies = strategy["weather_contingencies"]

        super().save(*args, **kwargs)


class StintAssignment(models.Model):
    """Stint assignments with pit strategy integration"""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team_strategy = models.ForeignKey(
        TeamEventStrategy,
        on_delete=models.CASCADE,
        related_name="stint_assignments",
    )
    driver = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="stint_assignments",
    )

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
        related_name="club_assignment",
    )

    # More detailed role assignments
    role = models.CharField(
        max_length=20,
        choices=[
            ("primary_driver", "Primary Driver"),
            ("secondary_driver", "Secondary Driver"),
            ("reserve_driver", "Reserve Driver"),
            ("spotter", "Spotter"),
            ("strategist", "Strategist"),
            ("pit_crew", "Pit Crew"),
        ],
        default="primary_driver",
    )

    # Pit strategy for this stint
    pit_entry_planned = models.BooleanField(default=False)
    pit_strategy_notes = models.TextField(blank=True)
    fuel_load_start = models.FloatField(
        null=True,
        blank=True,
        help_text="Fuel load at stint start",
    )
    fuel_load_end = models.FloatField(
        null=True,
        blank=True,
        help_text="Expected fuel at stint end",
    )
    tire_compound = models.CharField(max_length=50, blank=True)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["team_strategy", "stint_number"]
        indexes = [
            models.Index(fields=["team_strategy", "driver"]),
            models.Index(fields=["estimated_start_time"]),
            models.Index(fields=["stint_number"]),
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
            "refuel_time": (self.fuel_load_start / pit_data.refuel_flow_rate)
            if self.fuel_load_start
            else 0,
            "tire_change_time": pit_data.tire_change_all_four_sec
            if self.tire_compound
            else 0,
            "total_pit_time": 0,  # Would be calculated based on above and simultaneous_actions
        }
