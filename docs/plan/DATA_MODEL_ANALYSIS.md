# SimLane Data Model Analysis & Improvement Recommendations

_Created: December 2024_  
_Version: 1.1 - Updated with Event Participation Workflow Clarification_

## 🎯 Executive Summary

This document analyzes the current data models in the `sim` and `teams` apps and provides recommendations for improvements to support the full vision of SimLane as a comprehensive sim racing management platform. The analysis identifies opportunities to create a more flexible, scalable, and user-friendly system that supports both individual racers and organized clubs.

**Latest Update**: Added detailed event participation workflow analysis based on user clarification.

## 📊 Current State Analysis

### Sim App Models

The sim app provides a solid foundation with well-structured models for:
- **Simulator** - Different racing simulators (iRacing, ACC, etc.)
- **SimProfile** - User profiles per simulator with ratings and preferences
- **Track/Car Models** - Comprehensive track and car data with simulator-specific variants
- **Event System** - Events, sessions, instances with weather and pit data integration
- **Performance Data** - Lap times, ratings, and skill tracking

**Strengths:**
- Good separation between generic models (TrackModel, CarModel) and sim-specific variants
- Flexible event system with instances for different time slots
- Integration of pit data and weather forecasting
- Proper use of UUIDs and indexing

**Weaknesses:**
- Events are not clearly owned by anyone (no creator/organizer field)
- No clear distinction between official simulator events and user-created events
- Limited event visibility/privacy controls

### Teams App Models

The teams app has evolved to support club management with:
- **Club** - Racing clubs/organizations
- **Team** - Teams within clubs
- **ClubEvent** - Club-specific event organization
- **EventSignup** - Member signup management
- **TeamAllocation** - Team assignments for events

**Strengths:**
- Comprehensive club management workflow
- Good role-based permission system (ClubRole)
- Detailed event signup and team allocation process
- Integration with sim models for cars and tracks

**Weaknesses:**
- Teams are locked to clubs only - no support for ad-hoc teams
- Complex model relationships that could be simplified
- Some duplication between EventEntry and EventSignup models
- No support for individual users organizing events without clubs

## 🔄 Core Design Issues

### 1. Team-Club Coupling
Currently, teams can only exist within clubs. This prevents:
- Individual users from creating teams for one-off events
- Cross-club teams for special events
- Importing teams from simulators (like iRacing teams)

### 2. Event Ownership Ambiguity
Events in the sim app have no clear ownership model:
- No way to distinguish official vs user-created events
- No privacy/visibility controls
- No clear organizer responsibility

### 3. Model Duplication
Several models overlap in functionality:
- EventEntry vs EventSignupEntry
- PredictedStint vs StintAssignment
- Multiple allocation models that could be unified

### 4. Missing User Journey
No clear path for individual users who want to:
- Create their own events
- Invite friends without creating a formal club
- Manage simple team formations

## 🚀 Recommended Improvements

### 1. Flexible Team Model

```python
class Team(models.Model):
    """Teams can be club-based OR user-based"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=255, blank=True)
    
    # EITHER club-based OR user-based
    club = models.ForeignKey(
        Club, 
        on_delete=models.CASCADE, 
        related_name="teams",
        null=True, 
        blank=True
    )
    owner_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_teams",
        null=True,
        blank=True
    )
    
    # Support importing from simulators
    external_team_id = models.CharField(
        max_length=255, 
        blank=True,
        help_text="Team ID from simulator (e.g., iRacing team ID)"
    )
    simulator = models.ForeignKey(
        Simulator,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Source simulator for imported team"
    )
    
    # Team metadata
    description = models.TextField(blank=True)
    logo_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    is_public = models.BooleanField(default=True)
    
    # Team settings
    team_type = models.CharField(
        max_length=20,
        choices=[
            ('club', 'Club Team'),
            ('user', 'User Team'),
            ('imported', 'Imported Team'),
            ('temporary', 'Temporary Team')
        ]
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(club__isnull=False, owner_user__isnull=True) |
                    models.Q(club__isnull=True, owner_user__isnull=False)
                ),
                name='team_has_single_owner'
            )
        ]
```

### 2. Enhanced Event Model

```python
class Event(models.Model):
    """Enhanced event model with ownership and visibility"""
    # ... existing fields ...
    
    # Ownership and organization
    event_source = models.CharField(
        max_length=20,
        choices=[
            ('official', 'Official Simulator Event'),
            ('series', 'Official Series Event'),
            ('club', 'Club-Organized Event'),
            ('user', 'User-Created Event'),
            ('imported', 'Imported Event')
        ],
        default='user'
    )
    
    # Organizer can be a club OR user
    organizing_club = models.ForeignKey(
        Club,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organized_events"
    )
    organizing_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="organized_events"
    )
    
    # Visibility and access control
    visibility = models.CharField(
        max_length=20,
        choices=[
            ('public', 'Public - Anyone can view and join'),
            ('unlisted', 'Unlisted - Anyone with link can join'),
            ('club_only', 'Club Only - Only club members'),
            ('invite_only', 'Invite Only - By invitation'),
            ('private', 'Private - Specific users only')
        ],
        default='public'
    )
    
    # Entry requirements
    min_license_level = models.CharField(max_length=10, blank=True)
    min_safety_rating = models.FloatField(null=True, blank=True)
    min_skill_rating = models.FloatField(null=True, blank=True)
    max_entries = models.IntegerField(null=True, blank=True)
    
    # Allow custom entry fees or requirements
    entry_requirements = models.JSONField(
        null=True,
        blank=True,
        help_text="Custom requirements like specific licenses, achievements, etc."
    )
```

### 3. Unified Event Participation Model

Replace EventEntry, EventSignupEntry with a single flexible model:

```python
class EventParticipation(models.Model):
    """Unified model for all event participation"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # The event being participated in
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="participations"
    )
    
    # Participant can be user OR team
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
    
    # Entry details
    entry_type = models.CharField(
        max_length=20,
        choices=[
            ('individual', 'Individual Entry'),
            ('team', 'Team Entry'),
            ('substitute', 'Substitute/Reserve')
        ]
    )
    
    # Status tracking
    status = models.CharField(
        max_length=20,
        choices=[
            ('interested', 'Interested'),
            ('registered', 'Registered'),
            ('confirmed', 'Confirmed'),
            ('waitlist', 'Waitlist'),
            ('withdrawn', 'Withdrawn'),
            ('disqualified', 'Disqualified')
        ],
        default='registered'
    )
    
    # Car and class selection
    selected_car = models.ForeignKey(
        SimCar,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    selected_class = models.ForeignKey(
        EventClass,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Entry number (for race day)
    car_number = models.CharField(max_length=10, blank=True)
    
    # Metadata
    registration_data = models.JSONField(
        null=True,
        blank=True,
        help_text="Additional registration information"
    )
    registered_at = models.DateTimeField(auto_now_add=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(user__isnull=False, team__isnull=True) |
                    models.Q(user__isnull=True, team__isnull=False)
                ),
                name='participation_has_single_entity'
            )
        ]
        unique_together = [
            ['event', 'user'],
            ['event', 'team']
        ]
```

### 4. Team Membership Enhancement

```python
class TeamMember(models.Model):
    """Enhanced team membership with roles and permissions"""
    # ... existing fields ...
    
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
    can_manage_entries = models.BooleanField(default=False)
    can_invite_members = models.BooleanField(default=False)
    can_edit_team = models.BooleanField(default=False)
    
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
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
```

### 5. Event Invitation System

New model for inviting users to events:

```python
class EventInvitation(models.Model):
    """Allow users to invite others to events"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name="invitations"
    )
    
    # Who is inviting
    inviter = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="sent_event_invitations"
    )
    
    # Who is being invited (email or user)
    invitee_email = models.EmailField()
    invitee_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="received_event_invitations"
    )
    
    # Invitation details
    invitation_type = models.CharField(
        max_length=20,
        choices=[
            ('participate', 'Invitation to Participate'),
            ('team', 'Invitation to Join Team'),
            ('spectate', 'Invitation to Spectate')
        ]
    )
    
    # If team invitation
    team = models.ForeignKey(
        Team,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="invitations"
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('accepted', 'Accepted'),
            ('declined', 'Declined'),
            ('expired', 'Expired')
        ],
        default='pending'
    )
    
    # Metadata
    message = models.TextField(blank=True)
    token = models.CharField(max_length=128, unique=True)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(null=True, blank=True)
```

## 🔄 Event Participation Workflow Analysis

### User-Clarified Process Flow

Based on detailed user feedback, the event participation process has two distinct phases:

#### Phase 1: Interest & Signup Collection
**Purpose**: Gather member interest, availability, and preferences before team formation

**Club-based Team Events**:
1. Club members express interest in an event
2. Provide preferences:
   - Preferred timeslots/event instances  
   - Car preferences (primary/backup)
   - Specific availability windows for driving/spotting
   - Experience level and stint preferences

**Individual User Team Events**:
- Non-team events: Skip to direct participation
- Team events: User creates "open signup" and invites others
- Same preference collection as club events

#### Phase 2: Team Formation & Event Entry
**Club Events**:
1. Club manager reviews all signups
2. Splits members into teams based on:
   - Compatible timeslots
   - Car choice alignment  
   - Availability overlap
   - Skill balance
3. Each formed team becomes an event entry
4. Team members collaborate on strategy/stint planning

**Individual Events**:
1. For single teams: Skip splitting, proceed directly to entry
2. Team members plan strategy together

### Key Insights
- **Two-Phase Process**: Signup collection → Team formation & entry
- **Flexibility**: Club vs individual paths converge after team formation
- **No Club Enforcement**: Individual users shouldn't be forced to create clubs
- **Invitation System**: Non-club users need way to invite others for team events

## 🚀 Updated EventParticipation Model Recommendation

Based on the clarified workflow, here's the refined approach:

### Option A: Unified Model with Workflow States

```python
class EventParticipation(models.Model):
    """
    Unified model handling both signup and participation phases
    Uses status field to track workflow progression
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # === CORE RELATIONSHIPS ===
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="participations")
    
    # Participant (always user during signup phase)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="event_participations")
    
    # Team assignment (populated during team formation phase)
    team = models.ForeignKey(
        "teams.Team",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="event_participations"
    )
    
    # === WORKFLOW TRACKING ===
    participation_type = models.CharField(
        max_length=20,
        choices=[
            ('individual', 'Individual Entry'),        # Direct participation
            ('team_signup', 'Team Event Signup'),      # Phase 1: Interest collection
            ('team_entry', 'Team Event Entry'),        # Phase 2: Actual team entry
        ]
    )
    
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
    
    # === SIGNUP PHASE DATA ===
    # Car preferences
    preferred_car = models.ForeignKey('sim.SimCar', on_delete=models.SET_NULL, null=True, blank=True)
    backup_car = models.ForeignKey('sim.SimCar', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    
    # Instance/timeslot preferences
    preferred_instances = models.ManyToManyField('sim.EventInstance', blank=True)
    
    # Availability and preferences
    availability_windows = models.JSONField(
        null=True, 
        blank=True,
        help_text="Specific time windows when user can drive/spot"
    )
    role_preferences = models.JSONField(
        null=True,
        blank=True, 
        help_text="Preferred roles: driver, spotter, strategist, etc."
    )
    experience_level = models.CharField(max_length=20, choices=[...], blank=True)
    max_stint_duration = models.IntegerField(null=True, blank=True)
    min_rest_duration = models.IntegerField(null=True, blank=True)
    
    # === ENTRY PHASE DATA ===
    # Final assignments (populated after team formation)
    assigned_car = models.ForeignKey('sim.SimCar', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')
    assigned_instance = models.ForeignKey('sim.EventInstance', on_delete=models.SET_NULL, null=True, blank=True)
    car_number = models.CharField(max_length=10, blank=True)
    
    # === CONTEXT TRACKING ===
    # For club events
    club_event = models.ForeignKey("teams.ClubEvent", on_delete=models.SET_NULL, null=True, blank=True)
    
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
    preferences_data = models.JSONField(null=True, blank=True)
    
    # Timestamps
    signed_up_at = models.DateTimeField(null=True, blank=True)
    team_assigned_at = models.DateTimeField(null=True, blank=True) 
    entered_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['event', 'user']]  # User can only have one participation per event
        indexes = [
            models.Index(fields=['event', 'status']),
            models.Index(fields=['participation_type', 'status']),
            models.Index(fields=['club_event']),
            models.Index(fields=['team']),
        ]

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
    invitee_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    
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
```

### Workflow Examples

#### Club-based Team Event
```python
# 1. Club member signs up
participation = EventParticipation.objects.create(
    event=endurance_race,
    user=club_member,
    participation_type='team_signup',
    status='signed_up',
    preferred_car=gt3_bmw,
    backup_car=gt3_mercedes,
    availability_windows={
        "saturday_morning": {"start": "09:00", "end": "13:00", "roles": ["driver"]},
        "saturday_evening": {"start": "18:00", "end": "22:00", "roles": ["spotter"]}
    },
    club_event=club_endurance_event,
    signed_up_at=timezone.now()
)

# 2. Club manager forms teams
team = Team.objects.create(name="Club Team Alpha", owner_user=manager, club=racing_club)
participation.team = team
participation.status = 'team_assigned'
participation.assigned_car = gt3_bmw
participation.team_assigned_at = timezone.now()
participation.save()

# 3. Team entry confirmed
participation.participation_type = 'team_entry'
participation.status = 'entered'
participation.entered_at = timezone.now()
participation.save()
```

#### Individual User Team Event
```python
# 1. User creates signup invitation
invitation = EventSignupInvitation.objects.create(
    event=endurance_race,
    organizer_user=individual_user,
    team_name="Weekend Warriors",
    invitee_email="friend@example.com",
    message="Want to do Le Mans together?",
    token=generate_secure_token(),
    expires_at=timezone.now() + timedelta(days=7)
)

# 2. Friend accepts and signs up
participation = EventParticipation.objects.create(
    event=endurance_race,
    user=friend_user,
    participation_type='team_signup',
    status='signed_up',
    signup_invitation=invitation,
    # ... preferences ...
)

# 3. Team formation (automatic for single team)
team = Team.objects.create(
    name="Weekend Warriors", 
    owner_user=individual_user,
    is_temporary=True
)
participation.team = team
participation.status = 'team_assigned'
participation.save()
```

## 🎯 Benefits of This Approach

### 1. **Unified Data Model**
- Single model handles both phases with clear status progression
- Consistent querying across club and individual workflows
- Reduced complexity compared to separate models

### 2. **Flexible Workflows**
- Club events: `signed_up` → `team_assigned` → `entered` → `confirmed`
- Individual teams: Same flow but simplified team formation
- Direct individual: `interested` → `entered` → `confirmed`

### 3. **Clear Phase Separation**
- Signup phase: Collect preferences and availability
- Formation phase: Create teams based on compatibility  
- Entry phase: Official event participation
- Strategy phase: Existing stint planning models

### 4. **Future Extensibility**
- Easy to add new participation types
- Support for different team formation algorithms
- Flexible invitation systems

## 🚀 Implementation Plan

### Phase 1: Create New Models
1. Implement `EventParticipation` with workflow statuses
2. Implement `EventSignupInvitation` for individual team formation
3. Create migrations

### Phase 2: Update Team Formation Logic
1. Create services for club-based team splitting
2. Create services for individual team formation
3. Update existing team allocation logic

### Phase 3: UI Implementation
1. Signup forms with availability collection
2. Team formation wizards for club managers
3. Invitation system for individual users

### Phase 4: Migration & Cleanup
1. Migrate existing data to new model
2. Update all references
3. Deprecate old models

This approach provides the flexibility you described while maintaining clean separation between the interest/signup phase and the actual event participation phase. What are your thoughts on this refined approach?

## 🏗️ Migration Strategy

### Phase 1: Add New Models
1. Create flexible Team model with backward compatibility
2. Add EventParticipation as alternative to EventEntry
3. Implement EventInvitation system

### Phase 2: Data Migration
1. Migrate existing club teams to new model
2. Convert EventEntry records to EventParticipation
3. Update existing events with ownership information

### Phase 3: UI Updates
1. Add "Create Team" option for users
2. Implement event creation for individuals
3. Add team invitation workflow

### Phase 4: Deprecation
1. Mark old models as deprecated
2. Update all references to use new models
3. Clean up duplicate functionality

## 🎯 Benefits of Proposed Changes

### For Individual Users
- Create and manage their own teams without clubs
- Organize events and invite friends
- Import teams from simulators
- Join events without club membership

### For Clubs
- More flexible team management
- Better event organization tools
- Support for guest drivers
- Cross-club collaboration

### For Development
- Cleaner, more maintainable code
- Reduced model duplication
- Better separation of concerns
- More flexible permission system

## 📊 Database Impact

### New Indexes Needed
- Team: owner_user, club, team_type
- Event: organizing_user, organizing_club, visibility
- EventParticipation: event + status, user, team
- EventInvitation: event, invitee_email, token

### Performance Considerations
- Use select_related for owner/club queries
- Prefetch team members for team listings
- Cache visibility checks for events
- Index on slug fields for URL lookups

## 🔒 Security Considerations

### Permission Checks
- Event visibility enforcement
- Team membership validation
- Club role verification
- Invitation token security

### Privacy Controls
- User-controlled team visibility
- Event participant lists
- Contact information protection
- GDPR compliance for invitations

## 📝 Implementation Priority

### High Priority
1. Flexible Team model - enables core functionality
2. Event ownership - clarifies responsibilities
3. EventParticipation - unifies participation logic

### Medium Priority
1. Event invitation system
2. Team import from simulators
3. Enhanced team roles

### Low Priority
1. Legacy model deprecation
2. Advanced privacy controls
3. Cross-club features

## 🚀 Next Steps

1. **Review and Approve** - Get stakeholder agreement on changes
2. **Create Migrations** - Write Django migrations for new models
3. **Update Services** - Modify business logic for new models
4. **UI Implementation** - Build interfaces for new features
5. **Testing** - Comprehensive testing of migrations and new features
6. **Documentation** - Update API and user documentation

## 💡 Future Enhancements

### Simulator Integration
- Auto-import teams from iRacing/ACC
- Sync event results back to profiles
- Pull official event schedules

### Advanced Features
- Team performance analytics
- Event recommendation engine
- Skill-based matchmaking
- Championship management

### Social Features
- Team chat/communication
- Event forums
- Driver marketplace
- Coaching connections

## 📚 Conclusion

The proposed changes will transform SimLane from a club-centric platform to a comprehensive sim racing management system that serves both individual racers and organized clubs. By decoupling teams from clubs and adding flexible event management, we enable new user journeys while maintaining backward compatibility and improving code maintainability.

The phased migration approach ensures minimal disruption while delivering value incrementally. These changes position SimLane for future growth and enhanced user engagement across the sim racing community. 