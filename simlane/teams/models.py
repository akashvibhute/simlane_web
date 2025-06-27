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
    
    # Replace logo_url with ImageField
    logo = models.ImageField(
        upload_to='club_logos/',
        blank=True,
        null=True,
        help_text="Club logo image"
    )
    
    website = models.URLField(blank=True)
    
    # Replace social_links JSONField with individual fields for better UX
    discord_url = models.URLField(blank=True, help_text="Discord server invite link")
    twitter_url = models.URLField(blank=True, help_text="Twitter/X profile URL")
    youtube_url = models.URLField(blank=True, help_text="YouTube channel URL")
    twitch_url = models.URLField(blank=True, help_text="Twitch channel URL")
    facebook_url = models.URLField(blank=True, help_text="Facebook page URL")
    instagram_url = models.URLField(blank=True, help_text="Instagram profile URL")
    
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(
        default=False,
        help_text="Allow public viewing of club stats and information",
    )
    discord_guild_id = models.CharField(max_length=50, blank=True)

    # Track who created the club
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
        """Auto-generate slug if not provided"""
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

    @property
    def social_links(self):
        """Return a dictionary of social links for backward compatibility"""
        links = {}
        if self.discord_url:
            links['discord'] = self.discord_url
        if self.twitter_url:
            links['twitter'] = self.twitter_url
        if self.youtube_url:
            links['youtube'] = self.youtube_url
        if self.twitch_url:
            links['twitch'] = self.twitch_url
        if self.facebook_url:
            links['facebook'] = self.facebook_url
        if self.instagram_url:
            links['instagram'] = self.instagram_url
        return links

    @property
    def logo_url(self):
        """Return logo URL for backward compatibility"""
        return self.logo.url if self.logo else None


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

    def can_manage_events(self):
        """Check if this member can manage club events and signups"""
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
    
    # Simulator integration - if sim_api_id exists, team is imported
    sim_api_id = models.CharField(
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
            models.Index(fields=["sim_api_id", "source_simulator"]),
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
        return bool(self.sim_api_id)
    
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
    
    # Club context for signup - tracks which club's signup sheet this came from
    signup_context_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='event_signups',
        help_text="Which club this signup is associated with (for club-organized signups)"
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
    
    # Instance/timeslot preferences
    preferred_instances = models.ManyToManyField(
        EventInstance,
        blank=True,
        related_name="preferred_participations"
    )
    assigned_instance = models.ForeignKey(
        EventInstance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_participations",
        help_text="Final instance assignment after team formation"
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
    
    # Legacy team allocation field removed - using direct team assignment in enhanced system
    
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
            ),
            # User can only participate in one instance at a time
            models.UniqueConstraint(
                fields=['assigned_instance', 'user'],
                name='unique_user_event_instance_participation',
                condition=models.Q(assigned_instance__isnull=False, user__isnull=False)
            ),
            # Team can only participate in one instance at a time  
            models.UniqueConstraint(
                fields=['assigned_instance', 'team'],
                name='unique_team_event_instance_participation',
                condition=models.Q(assigned_instance__isnull=False, team__isnull=False)
            )
        ]
        
        unique_together = []  # Remove event-level constraints
        
        indexes = [
            models.Index(fields=['event', 'status']),
            models.Index(fields=['user', 'status']),
            models.Index(fields=['team', 'status']),
            models.Index(fields=['participation_type', 'status']),
            models.Index(fields=['event', 'participation_type']),
            models.Index(fields=['signup_context_club', 'event']),  # New index for club signups
            models.Index(fields=['assigned_instance', 'status']),  # New index for instance queries
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
            # Basic time validation - start must be before end
            models.CheckConstraint(
                check=models.Q(start_time__lt=models.F('end_time')),
                name='availability_window_valid_time_range'
            ),
            # Must be available for at least one role (drive, spot, or strategize)
            models.CheckConstraint(
                check=(
                    models.Q(can_drive=True) | 
                    models.Q(can_spot=True) | 
                    models.Q(can_strategize=True)
                ),
                name='availability_window_has_role'
            )
        ]
    
    def clean(self):
        """
        Custom validation for complex constraints that can't be done at database level
        """
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        from datetime import timedelta
        
        # Check minimum duration (15 minutes)
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            if duration < timedelta(minutes=15):
                raise ValidationError({
                    '__all__': 'Availability window must be at least 15 minutes long.'
                })
            
            # Check that duration is a multiple of 15 minutes
            duration_minutes = int(duration.total_seconds() / 60)
            if duration_minutes % 15 != 0:
                raise ValidationError({
                    '__all__': 'Availability window duration must be a multiple of 15 minutes.'
                })
        
        # Check if window is within event time boundaries
        if self.participation and self.participation.event:
            event = self.participation.event
            
            # Get event time boundaries
            if hasattr(event, 'start_time') and event.start_time:
                if self.start_time < event.start_time:
                    raise ValidationError({
                        'start_time': f'Availability window cannot start before event start time ({event.start_time})'
                    })
            
            if hasattr(event, 'end_time') and event.end_time:
                if self.end_time > event.end_time:
                    raise ValidationError({
                        'end_time': f'Availability window cannot end after event end time ({event.end_time})'
                    })
        
        # Check for overlapping windows for the same participation
        if self.participation:
            overlapping_windows = AvailabilityWindow.objects.filter(
                participation=self.participation,
                start_time__lt=self.end_time,
                end_time__gt=self.start_time
            ).exclude(pk=self.pk)
            
            if overlapping_windows.exists():
                overlapping = overlapping_windows.first()
                if overlapping:
                    raise ValidationError({
                        '__all__': f'This availability window overlaps with another window '
                                  f'({overlapping.start_time} to {overlapping.end_time}). '
                                  f'Windows for the same participant cannot overlap.'
                    })
    
    def save(self, *args, **kwargs):
        """Override save to call clean() validation"""
        self.full_clean()
        super().save(*args, **kwargs)
    
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


# ===== RACE STRATEGY AND PLANNING MODELS =====

class RaceStrategy(models.Model):
    """
    High-level race strategy for a team in an event
    Replaces the legacy TeamEventStrategy model with more flexibility
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Core relationships
    team = models.ForeignKey(
        Team, 
        on_delete=models.CASCADE, 
        related_name="race_strategies"
    )
    event = models.ForeignKey(
        Event, 
        on_delete=models.CASCADE, 
        related_name="race_strategies"
    )
    event_instance = models.ForeignKey(
        EventInstance,
        on_delete=models.CASCADE,
        related_name="race_strategies",
        help_text="Specific event instance/session this strategy is for"
    )
    
    # Strategy identification
    name = models.CharField(
        max_length=255, 
        default="Primary Strategy",
        help_text="Name for this strategy variant"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this is the active strategy being used"
    )
    
    # Strategy parameters
    target_stint_length = models.IntegerField(
        help_text="Target stint length in minutes"
    )
    min_driver_rest = models.IntegerField(
        help_text="Minimum rest between stints in minutes"
    )
    pit_stop_time = models.IntegerField(
        default=60,
        help_text="Expected pit stop time in seconds"
    )
    
    # Fuel strategy
    fuel_per_stint = models.FloatField(
        null=True, 
        blank=True,
        help_text="Expected fuel consumption per stint in liters/gallons"
    )
    fuel_tank_size = models.FloatField(
        null=True,
        blank=True,
        help_text="Fuel tank capacity in liters/gallons"
    )
    
    # Tire strategy
    tire_change_frequency = models.IntegerField(
        default=1,
        help_text="Change tires every N pit stops"
    )
    tire_compound_strategy = models.JSONField(
        null=True,
        blank=True,
        help_text="Tire compound plan for different conditions/phases"
    )
    
    # Additional strategy data
    notes = models.TextField(blank=True)
    strategy_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional strategy parameters and calculations"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_strategies"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['team', 'event', 'event_instance', 'name']]
        indexes = [
            models.Index(fields=['team', 'event']),
            models.Index(fields=['is_active']),
            models.Index(fields=['event_instance']),
        ]
        ordering = ['-is_active', '-created_at']
    
    def __str__(self):
        return f"{self.team.name} - {self.event.name} - {self.name}"
    
    def calculate_total_stints(self):
        """Calculate total number of stints based on event duration"""
        if not self.event_instance.session:
            return 0
        
        session_duration = self.event_instance.session.duration  # in minutes
        return int(session_duration / self.target_stint_length)
    
    def validate_driver_rest(self):
        """Validate that all drivers get sufficient rest between stints"""
        # This will check the stint plans associated with this strategy
        from collections import defaultdict
        driver_stints = defaultdict(list)
        
        for stint in self.stint_plans.all().order_by('stint_number'):
            driver_stints[stint.driver_id].append(stint)
        
        issues = []
        for driver_id, stints in driver_stints.items():
            for i in range(1, len(stints)):
                prev_end = stints[i-1].get_planned_end_time()
                next_start = stints[i].planned_start_time
                
                if prev_end and next_start:
                    rest_duration = (next_start - prev_end).total_seconds() / 60
                    if rest_duration < self.min_driver_rest:
                        issues.append(f"Insufficient rest for driver {stints[i].driver}")
        
        return issues


class StintPlan(models.Model):
    """
    Individual stint within a race strategy
    Replaces the legacy StintAssignment model with better tracking
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Core relationships
    strategy = models.ForeignKey(
        RaceStrategy, 
        on_delete=models.CASCADE, 
        related_name='stint_plans'
    )
    driver = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='stint_plans'
    )
    
    # Stint identification
    stint_number = models.IntegerField(
        help_text="Sequential stint number in the race"
    )
    
    # Planned timing (laps)
    planned_start_lap = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Planned starting lap for this stint"
    )
    planned_end_lap = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Planned ending lap for this stint"
    )
    
    # Planned timing (time-based)
    planned_start_time = models.DurationField(
        null=True, 
        blank=True,
        help_text="Planned start time from race start"
    )
    planned_duration = models.DurationField(
        help_text="Planned stint duration"
    )
    
    # Actual execution tracking
    actual_start_lap = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Actual starting lap"
    )
    actual_end_lap = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Actual ending lap"
    )
    actual_start_time = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Actual start timestamp"
    )
    actual_end_time = models.DateTimeField(
        null=True, 
        blank=True,
        help_text="Actual end timestamp"
    )
    
    # Pit stop instructions
    pit_instructions = models.JSONField(
        null=True, 
        blank=True,
        help_text="Detailed pit stop instructions (fuel, tires, repairs, etc.)"
    )
    
    # Example pit_instructions structure:
    # {
    #     "fuel_amount": 60,  # liters
    #     "tire_change": true,
    #     "tire_compound": "medium",
    #     "tire_pressures": {"fl": 26.5, "fr": 26.5, "rl": 26.0, "rr": 26.0},
    #     "repairs": [],
    #     "driver_change": true,
    #     "special_instructions": "Check front wing damage"
    # }
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('planned', 'Planned'),
            ('ready', 'Ready to Execute'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('skipped', 'Skipped'),
            ('aborted', 'Aborted'),
        ],
        default='planned'
    )
    
    # Performance tracking
    avg_lap_time = models.DurationField(
        null=True,
        blank=True,
        help_text="Average lap time during this stint"
    )
    fastest_lap_time = models.DurationField(
        null=True,
        blank=True,
        help_text="Fastest lap time during this stint"
    )
    incidents_count = models.IntegerField(
        default=0,
        help_text="Number of incidents during this stint"
    )
    
    # Notes and metadata
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['stint_number']
        unique_together = [['strategy', 'stint_number']]
        indexes = [
            models.Index(fields=['strategy', 'stint_number']),
            models.Index(fields=['driver', 'status']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"Stint {self.stint_number} - {self.driver.username} ({self.strategy.team.name})"
    
    def get_planned_end_time(self):
        """Calculate planned end time based on start time and duration"""
        if self.planned_start_time and self.planned_duration:
            return self.planned_start_time + self.planned_duration
        return None
    
    def get_actual_duration(self):
        """Calculate actual stint duration"""
        if self.actual_start_time and self.actual_end_time:
            return self.actual_end_time - self.actual_start_time
        return None
    
    def is_overdue(self):
        """Check if stint has exceeded planned duration"""
        if self.status != 'in_progress' or not self.actual_start_time:
            return False
        
        from django.utils import timezone
        elapsed = timezone.now() - self.actual_start_time
        return elapsed > self.planned_duration
    
    def can_start(self):
        """Check if this stint can be started"""
        if self.status != 'ready':
            return False
        
        # Check if previous stint is completed
        previous_stint = StintPlan.objects.filter(
            strategy=self.strategy,
            stint_number=self.stint_number - 1
        ).first()
        
        if previous_stint and previous_stint.status != 'completed':
            return False
        
        return True


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


class ClubEventSignupSheet(models.Model):
    """
    Represents a club's signup sheet for an existing event.
    This allows clubs to open signups for events without creating duplicate events.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Core relationships
    club = models.ForeignKey(
        Club, 
        on_delete=models.CASCADE, 
        related_name="event_signup_sheets"
    )
    event = models.ForeignKey(
        Event, 
        on_delete=models.CASCADE, 
        related_name="club_signup_sheets"
    )
    created_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name="created_signup_sheets"
    )
    
    # Club-specific signup details
    title = models.CharField(
        max_length=255, 
        help_text="Club-specific title for this signup (e.g., 'Team Endurance - Le Mans')"
    )
    description = models.TextField(
        blank=True,
        help_text="Club-specific instructions or notes about this event"
    )
    
    # Signup window
    signup_opens = models.DateTimeField(
        help_text="When signups open for club members"
    )
    signup_closes = models.DateTimeField(
        help_text="When signups close"
    )
    
    # Team formation settings
    max_teams = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Maximum number of teams the club will enter"
    )
    target_team_size = models.IntegerField(
        default=4,
        help_text="Target number of drivers per team"
    )
    min_drivers_per_team = models.IntegerField(
        default=2,
        help_text="Minimum drivers needed to form a team"
    )
    max_drivers_per_team = models.IntegerField(
        default=6,
        help_text="Maximum drivers allowed per team"
    )
    
    # Requirements
    min_license_level = models.CharField(
        max_length=20,
        blank=True,
        help_text="Minimum license level required (club-specific requirement)"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('open', 'Open for Signups'),
            ('closed', 'Signups Closed'),
            ('teams_forming', 'Teams Being Formed'),
            ('teams_finalized', 'Teams Finalized'),
            ('cancelled', 'Cancelled'),
        ],
        default='draft'
    )
    
    # Metadata
    notes_for_admins = models.TextField(
        blank=True,
        help_text="Internal notes for club admins/managers"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['club', 'event']]  # One signup sheet per club per event
        indexes = [
            models.Index(fields=['club', 'status']),
            models.Index(fields=['event', 'status']),
            models.Index(fields=['signup_opens', 'signup_closes']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.club.name} - {self.event.name} Signup"
    
    @property
    def is_open(self):
        """Check if signups are currently open"""
        from django.utils import timezone
        now = timezone.now()
        return (
            self.status == 'open' and 
            self.signup_opens <= now <= self.signup_closes
        )
    
    @property
    def signup_count(self):
        """Get count of signups for this sheet"""
        return self.event.participations.filter(
            signup_context_club=self.club,
            status__in=['signed_up', 'team_formation', 'team_assigned', 'entered', 'confirmed']
        ).count()
    
    @property
    def can_open_signups(self):
        """Check if signups can be opened"""
        from django.utils import timezone
        return (
            self.status == 'draft' and 
            self.signup_opens <= timezone.now()
        )
    
    def open_signups(self):
        """Open signups for this event"""
        if not self.can_open_signups():
            raise ValueError("Cannot open signups at this time")
        
        self.status = 'open'
        self.save()
    
    def close_signups(self):
        """Close signups and prepare for team formation"""
        if self.status != 'open':
            raise ValueError("Signups are not open")
        
        self.status = 'closed'
        self.save()
    
    def get_signups(self):
        """Get all signups for this sheet"""
        return self.event.participations.filter(
            signup_context_club=self.club
        ).select_related('user').prefetch_related('availability_windows')
    
    def can_user_signup(self, user):
        """Check if a user can sign up through this sheet"""
        # Must be club member
        is_member = self.club.members.filter(user=user).exists()
        if not is_member:
            return False, "You must be a member of this club"
        
        # Signups must be open
        if not self.is_open:
            return False, "Signups are not currently open"
        
        # User can't already be signed up for this event instance
        existing_signup = self.event.participations.filter(user=user).exists()
        if existing_signup:
            return False, "You have already signed up for this event"
        
        return True, "You can sign up"


# ClubEvent model removed - using sim.Event.organizing_club instead
