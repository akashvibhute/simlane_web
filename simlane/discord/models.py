import uuid
from django.db import models
from django.utils import timezone


class DiscordGuild(models.Model):
    """Discord Guild (Server) information"""

    guild_id = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    club = models.OneToOneField(
        "teams.Club",
        on_delete=models.CASCADE,
        related_name="discord_guild",
        null=True,
        blank=True,
    )
    
    # Enhanced metadata
    member_count = models.IntegerField(
        default=0,
        help_text="Total number of members in the Discord guild"
    )
    last_sync_timestamp = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time member sync was performed"
    )
    bot_permissions = models.BigIntegerField(
        default=0,
        help_text="Bot permissions as integer bitfield"
    )
    
    # Guild features and settings
    icon_url = models.URLField(blank=True, help_text="Guild icon URL")
    owner_id = models.CharField(max_length=50, blank=True, help_text="Discord guild owner ID")
    region = models.CharField(max_length=50, blank=True, help_text="Guild voice region")
    verification_level = models.IntegerField(
        default=0,
        help_text="Guild verification level (0-4)"
    )
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Discord Guild"
        verbose_name_plural = "Discord Guilds"
        indexes = [
            models.Index(fields=['guild_id']),
            models.Index(fields=['club', 'is_active']),
            models.Index(fields=['last_sync_timestamp']),
        ]

    def __str__(self):
        return f"{self.name} ({self.guild_id})"
    
    def update_member_count(self, count):
        """Update member count and sync timestamp"""
        self.member_count = count
        self.last_sync_timestamp = timezone.now()
        self.save(update_fields=['member_count', 'last_sync_timestamp'])
    
    def has_permission(self, permission):
        """Check if bot has specific permission"""
        return bool(self.bot_permissions & permission)
    
    @property
    def sync_overdue(self):
        """Check if member sync is overdue (more than 24 hours)"""
        if not self.last_sync_timestamp:
            return True
        from datetime import timedelta
        return timezone.now() - self.last_sync_timestamp > timedelta(hours=24)


class BotCommand(models.Model):
    """Log of bot commands executed"""

    command_name = models.CharField(max_length=100)
    discord_user_id = models.CharField(max_length=50)  # Discord user ID
    username = models.CharField(max_length=100)  # Discord username at time of command
    guild = models.ForeignKey(DiscordGuild, on_delete=models.CASCADE)
    channel_id = models.CharField(max_length=50)
    arguments = models.JSONField(default=dict, blank=True)
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Bot Command"
        verbose_name_plural = "Bot Commands"
        ordering = ["-timestamp"]

    def __str__(self):
        return f"{self.command_name} by {self.username} in {self.guild.name}"

    @property
    def django_user(self):
        """Get the Django user if they've linked their Discord account"""
        from allauth.socialaccount.models import SocialAccount

        try:
            social_account = SocialAccount.objects.get(
                provider="discord",
                uid=self.discord_user_id,
            )
        except SocialAccount.DoesNotExist:
            return None
        else:
            return social_account.user


class BotSettings(models.Model):
    """Global bot settings"""

    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Bot Setting"
        verbose_name_plural = "Bot Settings"

    def __str__(self):
        return self.key


class EventDiscordChannel(models.Model):
    """Track Discord channels created for events"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    event_signup_sheet = models.OneToOneField(
        'teams.ClubEventSignupSheet',
        on_delete=models.CASCADE,
        related_name='discord_channel'
    )
    guild = models.ForeignKey(
        DiscordGuild, 
        on_delete=models.CASCADE,
        related_name='event_channels'
    )
    
    # Channel IDs
    category_id = models.CharField(max_length=50, help_text="Discord category ID")
    text_channel_id = models.CharField(max_length=50, help_text="Main event channel")
    voice_channel_id = models.CharField(max_length=50, null=True, blank=True)
    practice_voice_channel_id = models.CharField(max_length=50, null=True, blank=True)
    
    # Additional channel types for team formation
    team_formation_channel_id = models.CharField(
        max_length=50, 
        null=True, 
        blank=True,
        help_text="Channel for team formation discussions"
    )
    announcements_channel_id = models.CharField(
        max_length=50,
        null=True,
        blank=True, 
        help_text="Channel for event announcements"
    )
    
    # Message tracking for key messages
    signup_message_id = models.CharField(max_length=50, null=True, blank=True)
    last_update_message_id = models.CharField(max_length=50, null=True, blank=True)
    team_formation_message_id = models.CharField(max_length=50, null=True, blank=True)
    event_info_message_id = models.CharField(max_length=50, null=True, blank=True)
    
    # Channel configuration
    channel_name = models.CharField(
        max_length=100,
        help_text="Generated channel name"
    )
    auto_archive_after_event = models.BooleanField(
        default=True,
        help_text="Automatically archive channels after event completion"
    )
    
    # Status tracking
    status = models.CharField(max_length=20, choices=[
        ('creating', 'Creating'),
        ('active', 'Active'),
        ('team_formation', 'Team Formation Phase'),
        ('event_ready', 'Event Ready'),
        ('event_live', 'Event Live'),
        ('completed', 'Completed'),
        ('archived', 'Archived'),
        ('error', 'Error'),
    ], default='creating')
    
    # Timestamps for lifecycle tracking
    channels_created_at = models.DateTimeField(null=True, blank=True)
    team_formation_started_at = models.DateTimeField(null=True, blank=True)
    event_started_at = models.DateTimeField(null=True, blank=True)
    archived_at = models.DateTimeField(null=True, blank=True)
    
    # Error tracking
    last_error = models.TextField(blank=True)
    error_count = models.IntegerField(default=0)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Event Discord Channel"
        verbose_name_plural = "Event Discord Channels"
        indexes = [
            models.Index(fields=['guild', 'status']),
            models.Index(fields=['text_channel_id']),
            models.Index(fields=['category_id']),
            models.Index(fields=['event_signup_sheet']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['auto_archive_after_event', 'status']),
        ]

    def __str__(self):
        return f"{self.event_signup_sheet.event.name} - {self.guild.name}"
    
    def mark_error(self, error_message):
        """Mark channel as having an error"""
        self.status = 'error'
        self.last_error = error_message
        self.error_count += 1
        self.save(update_fields=['status', 'last_error', 'error_count', 'updated_at'])
    
    def start_team_formation(self):
        """Mark team formation phase as started"""
        self.status = 'team_formation'
        self.team_formation_started_at = timezone.now()
        self.save(update_fields=['status', 'team_formation_started_at', 'updated_at'])
    
    def mark_event_ready(self):
        """Mark event as ready to start"""
        self.status = 'event_ready'
        self.save(update_fields=['status', 'updated_at'])
    
    def start_event(self):
        """Mark event as live"""
        self.status = 'event_live'
        self.event_started_at = timezone.now()
        self.save(update_fields=['status', 'event_started_at', 'updated_at'])
    
    def complete_event(self):
        """Mark event as completed"""
        self.status = 'completed'
        self.save(update_fields=['status', 'updated_at'])
    
    def archive_channels(self):
        """Archive the channels"""
        self.status = 'archived'
        self.archived_at = timezone.now()
        self.save(update_fields=['status', 'archived_at', 'updated_at'])


class DiscordMemberSync(models.Model):
    """Track member sync operations"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    guild = models.ForeignKey(
        DiscordGuild, 
        on_delete=models.CASCADE,
        related_name='member_syncs'
    )
    sync_timestamp = models.DateTimeField(auto_now_add=True)
    sync_type = models.CharField(max_length=20, choices=[
        ('manual', 'Manual'),
        ('automatic', 'Automatic'), 
        ('scheduled', 'Scheduled'),
        ('webhook', 'Webhook'),
        ('initial', 'Initial Setup'),
    ])
    
    # Sync trigger information
    triggered_by_user = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="User who triggered manual sync"
    )
    
    # Results tracking
    total_discord_members = models.IntegerField(default=0)
    matched_members = models.IntegerField(default=0)
    new_club_members = models.IntegerField(default=0)
    updated_members = models.IntegerField(default=0)
    removed_members = models.IntegerField(default=0)
    errors_count = models.IntegerField(default=0)
    
    # Detailed results and statistics
    results = models.JSONField(default=dict, help_text="Detailed sync results")
    # Example results structure:
    # {
    #     "matched_users": [{"discord_id": "123", "user_id": 456, "username": "test"}],
    #     "new_members": [{"discord_id": "789", "username": "newuser"}],
    #     "errors": [{"discord_id": "999", "error": "Invalid user data"}],
    #     "role_updates": [{"user_id": 123, "old_role": "member", "new_role": "admin"}],
    #     "sync_duration_seconds": 15.5
    # }
    
    # Performance tracking
    sync_duration_seconds = models.FloatField(
        null=True,
        blank=True,
        help_text="Time taken to complete sync"
    )
    
    # Status and error handling
    success = models.BooleanField(default=True)
    error_message = models.TextField(blank=True)
    
    # Sync configuration used
    sync_config = models.JSONField(
        default=dict,
        help_text="Configuration used for this sync"
    )

    class Meta:
        verbose_name = "Discord Member Sync"
        verbose_name_plural = "Discord Member Syncs"
        ordering = ["-sync_timestamp"]
        indexes = [
            models.Index(fields=['guild', 'sync_timestamp']),
            models.Index(fields=['sync_type', 'success']),
            models.Index(fields=['success', 'sync_timestamp']),
            models.Index(fields=['triggered_by_user', 'sync_timestamp']),
        ]

    def __str__(self):
        return f"{self.guild.name} - {self.sync_type} sync ({self.sync_timestamp.date()})"
    
    @property
    def sync_summary(self):
        """Get a summary of sync results"""
        return {
            'total_processed': self.total_discord_members,
            'successful_matches': self.matched_members,
            'new_additions': self.new_club_members,
            'updates': self.updated_members,
            'removals': self.removed_members,
            'errors': self.errors_count,
            'success_rate': (self.matched_members / max(self.total_discord_members, 1)) * 100
        }
    
    def mark_completed(self, duration_seconds=None):
        """Mark sync as completed with optional duration"""
        if duration_seconds:
            self.sync_duration_seconds = duration_seconds
        self.save(update_fields=['sync_duration_seconds'])
    
    def add_error(self, error_message, discord_id=None):
        """Add an error to the sync results"""
        if 'errors' not in self.results:
            self.results['errors'] = []
        
        error_entry = {'error': error_message}
        if discord_id:
            error_entry['discord_id'] = discord_id
            
        self.results['errors'].append(error_entry)
        self.errors_count += 1
        self.save(update_fields=['results', 'errors_count'])


class ClubDiscordSettings(models.Model):
    """Per-club Discord configuration"""
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    club = models.OneToOneField(
        'teams.Club',
        on_delete=models.CASCADE,
        related_name='discord_settings'
    )
    
    # Channel creation settings
    auto_create_channels = models.BooleanField(
        default=True,
        help_text="Automatically create channels for new events"
    )
    channel_naming_pattern = models.CharField(
        max_length=255,
        default="{series_name}-{event_name}",
        help_text="Template for channel names. Available variables: {series_name}, {event_name}, {date}, {club_name}"
    )
    category_naming_pattern = models.CharField(
        max_length=255,
        default="{series_name} Events",
        help_text="Template for category names"
    )
    
    # Voice channel settings  
    enable_voice_channels = models.BooleanField(
        default=True,
        help_text="Create voice channels for events"
    )
    enable_practice_voice = models.BooleanField(
        default=True,
        help_text="Create separate practice voice channels"
    )
    voice_channel_user_limit = models.IntegerField(
        default=0,
        help_text="User limit for voice channels (0 = unlimited)"
    )
    
    # Team formation settings
    enable_team_formation_channels = models.BooleanField(
        default=True,
        help_text="Create channels for team formation discussions"
    )
    auto_create_team_threads = models.BooleanField(
        default=True,
        help_text="Automatically create threads for formed teams"
    )
    
    # Member sync settings
    auto_sync_members = models.BooleanField(
        default=True,
        help_text="Automatically sync Discord members with club members"
    )
    sync_frequency_hours = models.IntegerField(
        default=24,
        help_text="Hours between automatic member syncs"
    )
    require_linked_account = models.BooleanField(
        default=False,
        help_text="Require Discord account to be linked to club membership"
    )
    
    # Notification settings
    enable_stint_alerts = models.BooleanField(
        default=True,
        help_text="Send alerts for stint changes during events"
    )
    signup_update_frequency = models.IntegerField(
        default=6,
        help_text="Hours between signup status updates"
    )
    enable_event_reminders = models.BooleanField(
        default=True,
        help_text="Send reminders before events start"
    )
    reminder_times_hours = models.JSONField(
        default=list,
        help_text="Hours before event to send reminders (e.g., [24, 2, 0.5])"
    )
    
    # Role management
    auto_assign_roles = models.BooleanField(
        default=True,
        help_text="Automatically assign Discord roles based on club membership"
    )
    member_role_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Discord role ID for club members"
    )
    admin_role_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Discord role ID for club admins"
    )
    teams_manager_role_id = models.CharField(
        max_length=50,
        blank=True,
        help_text="Discord role ID for teams managers"
    )
    
    # Advanced notification preferences
    notification_preferences = models.JSONField(
        default=dict,
        help_text="Advanced notification settings"
    )
    # Example notification_preferences structure:
    # {
    #     "signup_opened": {"enabled": True, "mention_role": "member"},
    #     "signup_closed": {"enabled": True, "mention_role": None},
    #     "teams_formed": {"enabled": True, "mention_role": "member"},
    #     "event_starting": {"enabled": True, "mention_role": "participant"},
    #     "stint_change": {"enabled": True, "mention_role": None},
    #     "event_completed": {"enabled": True, "mention_role": None}
    # }
    
    # Channel cleanup settings
    auto_archive_completed_events = models.BooleanField(
        default=True,
        help_text="Automatically archive channels after events complete"
    )
    archive_delay_hours = models.IntegerField(
        default=24,
        help_text="Hours to wait before archiving completed event channels"
    )
    delete_archived_after_days = models.IntegerField(
        default=30,
        help_text="Days to keep archived channels before deletion (0 = never delete)"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Club Discord Settings"
        verbose_name_plural = "Club Discord Settings"
        indexes = [
            models.Index(fields=['club']),
            models.Index(fields=['auto_create_channels']),
            models.Index(fields=['auto_sync_members']),
        ]

    def __str__(self):
        return f"{self.club.name} Discord Settings"
    
    def get_default_notification_preferences(self):
        """Get default notification preferences if none set"""
        if not self.notification_preferences:
            return {
                "signup_opened": {"enabled": True, "mention_role": "member"},
                "signup_closed": {"enabled": True, "mention_role": None},
                "teams_formed": {"enabled": True, "mention_role": "member"},
                "event_starting": {"enabled": True, "mention_role": "participant"},
                "stint_change": {"enabled": True, "mention_role": None},
                "event_completed": {"enabled": True, "mention_role": None}
            }
        return self.notification_preferences
    
    def should_send_notification(self, notification_type):
        """Check if a specific notification type should be sent"""
        prefs = self.get_default_notification_preferences()
        return prefs.get(notification_type, {}).get("enabled", False)
    
    def get_mention_role(self, notification_type):
        """Get the role to mention for a notification type"""
        prefs = self.get_default_notification_preferences()
        return prefs.get(notification_type, {}).get("mention_role")
    
    def format_channel_name(self, event, **extra_vars):
        """Format channel name using the pattern and event data"""
        variables = {
            'series_name': getattr(event.series, 'name', 'Event') if hasattr(event, 'series') else 'Event',
            'event_name': event.name,
            'date': event.start_time.strftime('%m-%d') if hasattr(event, 'start_time') and event.start_time else 'tbd',
            'club_name': self.club.name,
            **extra_vars
        }
        
        # Clean up the name for Discord (lowercase, replace spaces with hyphens, etc.)
        formatted_name = self.channel_naming_pattern.format(**variables)
        # Discord channel name restrictions: lowercase, no spaces, limited special chars
        formatted_name = formatted_name.lower().replace(' ', '-').replace('_', '-')
        # Remove any characters that aren't alphanumeric or hyphens
        import re
        formatted_name = re.sub(r'[^a-z0-9\-]', '', formatted_name)
        # Remove multiple consecutive hyphens
        formatted_name = re.sub(r'-+', '-', formatted_name)
        # Remove leading/trailing hyphens
        formatted_name = formatted_name.strip('-')
        
        return formatted_name[:100]  # Discord channel name limit
    
    def format_category_name(self, **extra_vars):
        """Format category name using the pattern"""
        variables = {
            'series_name': 'Events',
            'club_name': self.club.name,
            **extra_vars
        }
        
        return self.category_naming_pattern.format(**variables)[:100]  # Discord category name limit
