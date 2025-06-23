# SimLane Club Management System - Enhanced Implementation Plan

_Created: December 2024_  
_Version: 2.1 - Enhanced Integration Plan with Role System Clarification_

## 🎯 Executive Summary

This enhanced plan combines comprehensive club management functionality with deep integration into the existing `simlane.sim` ecosystem. The approach leverages existing Event, PitData, and WeatherForecast models while adding robust club-specific workflows for member management, event planning, team allocation, and race strategy.

### Key Improvements Over ClubPlan.md

1. **Deep Sim Integration**: Direct integration with existing sim.Event, PitData, and WeatherForecast models
2. **Enhanced Data Models**: Improved model relationships that reduce duplication and leverage existing data
3. **Intelligent Team Assignment**: AI-assisted team balancing using SimProfile ratings and historical data
4. **Real-time Strategy Planning**: Pit data integration for accurate fuel/tire calculations
5. **Modern UI/UX**: Enhanced HTMX patterns with better mobile support and accessibility
6. **Corrected Role System**: Clear distinction between app-level UserRole and club-level ClubRole

## 🎯 Role System Clarification

### Two Distinct Role Systems

1. **App-Level Roles (UserRole)** - Global permissions across the entire application
   - `USER` - Regular application user
   - `SUBSCRIBER` - Paid subscriber with additional features
   - `ADMIN` - Application administrator
   - Note: `CLUB_ADMIN`, `CLUB_MANAGER`, `CLUB_MEMBER` in UserRole are legacy/unused

2. **Club-Level Roles (ClubRole)** - Permissions within specific clubs
   - `ClubRole.ADMIN` - Full control over the club (automatically assigned to club creator)
   - `ClubRole.TEAMS_MANAGER` - Can manage teams and events but not club settings
   - `ClubRole.MEMBER` - Basic club member, can participate in events

### Key Principles
- **Any app user can create clubs** regardless of their UserRole
- **Club creators automatically become `ClubRole.ADMIN`** for their club
- **Club permissions are based entirely on ClubRole**, not UserRole
- **Users can have different ClubRoles in different clubs**

---

## 📊 Enhanced Model Design (Building on ClubPlan.md)

```python
# simlane/teams/models.py - ENHANCED INTEGRATION VERSION

class Club(models.Model):
    # ... existing fields ...
    created_by = models.ForeignKey(
        User, 
        on_delete=models.PROTECT,  # Don't delete club if creator is deleted
        related_name="created_clubs"
    )
    
    def save(self, *args, **kwargs):
        """Ensure club creator becomes admin on club creation"""
        is_new = self.pk is None
        creator = kwargs.pop('creator', None)
        
        super().save(*args, **kwargs)
        
        if is_new and creator:
            # Automatically make creator the club admin
            ClubMember.objects.get_or_create(
                user=creator,
                club=self,
                defaults={'role': ClubRole.ADMIN}
            )

class ClubInvitation(models.Model):
    """Enhanced invitation model with better token security and tracking"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    invited_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_invitations")
    
    # CORRECTED: Use ClubRole for invitation
    role = models.CharField(
        max_length=50, 
        choices=ClubRole.choices, 
        default=ClubRole.MEMBER,
        help_text="Role the user will have in this specific club"
    )
    
    # ENHANCED: More secure token with expiry tracking
    token = models.CharField(max_length=128, unique=True)  # Longer, more secure tokens
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    declined_at = models.DateTimeField(null=True, blank=True)
    
    # ENHANCED: Better tracking and communication
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
    
    def is_expired(self):
        from django.utils import timezone
        return timezone.now() > self.expires_at
    
    def can_send_reminder(self):
        """Check if reminder can be sent (max 2 reminders, 24h apart)"""
        from django.utils import timezone
        if self.reminder_count >= 2:
            return False
        if self.reminder_sent_at:
            return timezone.now() - self.reminder_sent_at > timezone.timedelta(hours=24)
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

class ClubEvent(models.Model):
    """ENHANCED: Deep integration with sim.Event + club workflow management"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club = models.ForeignKey(Club, on_delete=models.CASCADE, related_name="club_events")
    
    # INTEGRATION: Link to existing sim.Event (instead of duplicating event data)
    base_event = models.ForeignKey(
        'sim.Event', 
        on_delete=models.CASCADE, 
        related_name="club_events"
    )
    
    # Club-specific overlay data
    club_name = models.CharField(max_length=255, help_text="Club-specific event name override")
    club_description = models.TextField(blank=True)
    
    # ENHANCED: Signup management with better controls
    signup_opens = models.DateTimeField()
    signup_closes = models.DateTimeField()
    max_participants = models.IntegerField(null=True, blank=True)
    min_experience_level = models.CharField(max_length=20, choices=[
        ('any', 'Any Level'),
        ('beginner', 'Beginner+'),
        ('intermediate', 'Intermediate+'),
        ('advanced', 'Advanced+'),
        ('professional', 'Professional Only'),
    ], default='any')
    
    # ENHANCED: Team management with intelligence
    requires_team_assignment = models.BooleanField(default=True)
    auto_assign_teams = models.BooleanField(default=False)
    team_balancing_criteria = models.JSONField(default=dict, help_text="Criteria for auto team balancing")
    team_size_min = models.IntegerField(default=2)
    team_size_max = models.IntegerField(default=4)
    
    # ENHANCED: Better status tracking
    status = models.CharField(max_length=20, choices=[
        ('draft', 'Draft'),
        ('signup_open', 'Signup Open'),
        ('signup_closed', 'Signup Closed'),
        ('teams_assigned', 'Teams Assigned'),
        ('strategies_planned', 'Strategies Planned'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ], default='draft')
    
    # INTEGRATION: Leverage existing sim data
    allowed_event_classes = models.ManyToManyField(
        'sim.EventClass', 
        blank=True,
        help_text="Restrict signup to specific car classes"
    )
    preferred_instances = models.ManyToManyField(
        'sim.EventInstance',
        blank=True,
        help_text="Preferred time slots for this club event"
    )
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['club', 'base_event']
        indexes = [
            models.Index(fields=['club', 'status']),
            models.Index(fields=['signup_opens', 'signup_closes']),
            models.Index(fields=['base_event']),
        ]
    
    @property
    def effective_name(self):
        """Return club name or base event name"""
        return self.club_name or self.base_event.name
    
    @property
    def track_layout(self):
        """Direct access to track layout from base event"""
        return self.base_event.sim_layout
    
    @property
    def pit_data(self):
        """Access pit data for strategy planning"""
        return self.base_event.sim_layout.pit_data
    
    def get_weather_forecasts(self):
        """Get weather forecasts for all event instances"""
        forecasts = []
        for instance in self.base_event.instances.all():
            forecasts.extend(instance.weather_forecasts.all())
        return forecasts
    
    @property
    def is_signup_open(self):
        from django.utils import timezone
        now = timezone.now()
        return (self.status == 'signup_open' and 
                self.signup_opens <= now <= self.signup_closes)

class EventSignup(models.Model):
    """ENHANCED: Member signup with sim data integration and intelligence"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club_event = models.ForeignKey(ClubEvent, on_delete=models.CASCADE, related_name="signups")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="event_signups")
    
    # INTEGRATION: Direct links to sim models for intelligent suggestions
    preferred_cars = models.ManyToManyField('sim.SimCar', blank=True, related_name="preferred_signups")
    backup_cars = models.ManyToManyField('sim.SimCar', blank=True, related_name="backup_signups")
    preferred_instances = models.ManyToManyField('sim.EventInstance', blank=True)
    preferred_classes = models.ManyToManyField('sim.EventClass', blank=True)
    
    # ENHANCED: Better availability and preferences
    can_drive = models.BooleanField(default=True)
    can_spectate = models.BooleanField(default=True)
    can_spot = models.BooleanField(default=True)  # New: Spotting/coaching role
    
    experience_level = models.CharField(max_length=20, choices=[
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('professional', 'Professional'),
    ], default='intermediate')
    
    # INTEGRATION: Link to sim profile for automatic skill assessment
    primary_sim_profile = models.ForeignKey(
        'sim.SimProfile',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Primary sim profile for skill assessment"
    )
    
    # ENHANCED: Better availability tracking
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

# Note: EventSignupEntry and EventSignupAvailability from ClubPlan.md 
# are merged into EventSignup with ManyToMany relationships for better integration

class TeamAllocation(models.Model):
    """Team allocation for club events"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    club_event = models.ForeignKey(ClubEvent, on_delete=models.CASCADE, related_name="allocations")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="allocations")
    assigned_sim_car = models.ForeignKey('sim.SimCar', on_delete=models.CASCADE)
    
    # Members assigned to this allocation
    members = models.ManyToManyField(EventSignup, through='TeamAllocationMember')
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['club_event', 'team']
        indexes = [
            models.Index(fields=['club_event']),
            models.Index(fields=['team']),
        ]

class TeamAllocationMember(models.Model):
    """Members assigned to each team allocation"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team_allocation = models.ForeignKey(TeamAllocation, on_delete=models.CASCADE)
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

# ENHANCED: More intelligent team strategy with real pit data integration
class TeamEventStrategy(models.Model):
    """ENHANCED: Strategy planning with deep pit data and weather integration"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="event_strategies")
    club_event = models.ForeignKey(ClubEvent, on_delete=models.CASCADE, related_name="team_strategies")
    team_allocation = models.OneToOneField(TeamAllocation, on_delete=models.CASCADE, related_name="strategy")
    
    # INTEGRATION: Direct sim model relationships
    selected_car = models.ForeignKey('sim.SimCar', on_delete=models.CASCADE)
    selected_instance = models.ForeignKey('sim.EventInstance', on_delete=models.CASCADE)
    selected_class = models.ForeignKey('sim.EventClass', on_delete=models.SET_NULL, null=True, blank=True)
    
    # ENHANCED: Calculated strategy data using PitData
    strategy_notes = models.TextField(blank=True)
    
    # INTEGRATION: Automated calculations using pit data
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
    
    # INTEGRATION: Weather-responsive strategy
    weather_contingencies = models.JSONField(
        null=True, 
        blank=True, 
        help_text="Strategy adjustments based on WeatherForecast data"
    )
    
    # ENHANCED: Better strategy management
    is_finalized = models.BooleanField(default=False)
    finalized_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="finalized_strategies")
    finalized_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['team', 'club_event']
        indexes = [
            models.Index(fields=['club_event', 'is_finalized']),
            models.Index(fields=['selected_instance']),
        ]
    
    def calculate_optimal_strategy(self):
        """INTEGRATION: Calculate strategy using pit data and weather"""
        if not self.selected_car.pit_data:
            return None
        
        pit_data = self.selected_car.pit_data
        layout_pit_data = self.club_event.track_layout.pit_data
        event_duration = self.selected_instance.end_time - self.selected_instance.start_time
        
        # Use track pit data if available, otherwise car pit data
        active_pit_data = layout_pit_data or pit_data
        
        # Calculate fuel consumption and pit stops needed
        strategy = {
            'event_duration_minutes': event_duration.total_seconds() / 60,
            'refuel_rate_per_second': active_pit_data.refuel_flow_rate,
            'tire_change_duration': active_pit_data.tire_change_all_four_sec,
            'simultaneous_service': active_pit_data.simultaneous_actions,
            'tire_then_refuel': active_pit_data.tire_then_refuel,
        }
        
        # Integrate weather forecasts
        weather_forecasts = self.selected_instance.weather_forecasts.all()
        if weather_forecasts:
            strategy['weather_windows'] = [
                {
                    'time_offset': f.time_offset,
                    'precipitation_chance': f.precipitation_chance,
                    'temperature': f.air_temperature,
                    'strategy_impact': 'rain_likely' if f.precipitation_chance > 40 else 'dry'
                }
                for f in weather_forecasts
            ]
        
        return strategy
    
    def save(self, *args, **kwargs):
        """Auto-calculate strategy on save"""
        if self.selected_car and self.selected_instance:
            self.calculated_pit_windows = self.calculate_optimal_strategy()
        super().save(*args, **kwargs)

# ENHANCED: More detailed stint assignments with pit integration
class StintAssignment(models.Model):
    """ENHANCED: Stint assignments with pit strategy integration"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    team_strategy = models.ForeignKey(TeamEventStrategy, on_delete=models.CASCADE, related_name="stint_assignments")
    driver = models.ForeignKey(User, on_delete=models.CASCADE, related_name="stint_assignments")
    
    stint_number = models.IntegerField()
    estimated_start_time = models.DateTimeField()
    estimated_end_time = models.DateTimeField()  # ENHANCED: Explicit end time
    estimated_duration_minutes = models.IntegerField()
    
    # INTEGRATION: Link to existing PredictedStint model
    predicted_stint = models.OneToOneField(
        PredictedStint, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name="club_assignment"
    )
    
    # ENHANCED: More detailed role assignments
    role = models.CharField(max_length=20, choices=[
        ('primary_driver', 'Primary Driver'),
        ('secondary_driver', 'Secondary Driver'),
        ('reserve_driver', 'Reserve Driver'),
        ('spotter', 'Spotter'),
        ('strategist', 'Strategist'),
        ('pit_crew', 'Pit Crew'),
    ], default='primary_driver')
    
    # INTEGRATION: Pit strategy for this stint
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
    
    def calculate_pit_strategy(self):
        """Calculate pit requirements for this stint using PitData"""
        if not self.team_strategy.selected_car.pit_data:
            return None
        
        pit_data = self.team_strategy.selected_car.pit_data
        duration_seconds = self.estimated_duration_minutes * 60
        
        # Calculate fuel needed for stint
        return {
            'refuel_time': (self.fuel_load_start / pit_data.refuel_flow_rate) if self.fuel_load_start else 0,
            'tire_change_time': pit_data.tire_change_all_four_sec if self.tire_compound else 0,
            'total_pit_time': 0,  # Calculated based on above and simultaneous_actions
        }
```

## 🔄 Implementation Plan

Now that I've saved the enhanced plan, let's start implementing following the ClubPlan.md structure with the improvements I've identified. 

### Implementation Order:

1. **Models** - Add the new models with enhanced integration
2. **Migrations** - Generate migrations for the new models
3. **Forms** - Create forms with proper role handling
4. **Services** - Implement business logic with AI features
5. **Views** - Create views with correct permission decorators
6. **Templates** - Build responsive UI components
7. **Admin** - Configure admin interfaces
8. **Tests** - Add comprehensive test coverage

Let's start with implementing the models! 