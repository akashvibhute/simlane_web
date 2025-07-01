# League Management System - Product Requirements Document
_Version 1.0 - January 2025_

## 📋 Executive Summary

This PRD outlines the implementation of a comprehensive league management system for SimLane, enabling users and clubs to create and manage competitive racing leagues across multiple simulators. The system will support custom scoring rules, championship standings, and flexible participation models while integrating seamlessly with existing event and results infrastructure.

## 🎯 Goals & Objectives

### Primary Goals
1. Enable any authenticated user to create and manage racing leagues
2. Support multi-simulator leagues (iRacing, ACC, rFactor 2, etc.)
3. Provide flexible scoring systems with automatic standings calculation
4. Integrate with existing Event and Results models
5. Maintain mobile-first API design for future app development

### Success Metrics
- 50+ active leagues within 3 months of launch
- 80% of league events successfully using automated standings
- <2s load time for standings pages with 100+ participants
- 90% user satisfaction with league creation flow

## 👥 User Stories

### League Organizer
- As a league organizer, I want to create a league with custom scoring rules
- As a league organizer, I want to schedule a season of events
- As a league organizer, I want to see real-time standings after each event
- As a league organizer, I want to manage participant registrations

### Participant
- As a driver, I want to register for a league championship
- As a driver, I want to opt-out of specific events while remaining in the championship
- As a driver, I want to view my standings and points progression
- As a driver, I want to see which events count toward my championship (drop rounds)

### Club Admin
- As a club admin, I want to create multiple leagues under my club
- As a club admin, I want to restrict league participation to club members
- As a club admin, I want to delegate league management to other members

## 🔧 Technical Architecture

### Data Models

#### 1. League Model
```python
class League(models.Model):
    """Represents a user or club-created racing league"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    
    # Identity
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=280, unique=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='league_logos/', null=True, blank=True)
    
    # Organization
    organizing_club = models.ForeignKey(
        'teams.Club',
        on_delete=models.CASCADE,
        related_name='leagues',
        help_text="Club that owns this league"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name='created_leagues'
    )
    
    # Series linkage (for car/track rules)
    base_series = models.ForeignKey(
        'sim.Series',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Optional: inherit car/track rules from existing series"
    )
    
    # League settings
    visibility = models.CharField(
        max_length=20,
        choices=EventVisibility.choices,  # Reuse existing choices
        default=EventVisibility.PUBLIC
    )
    registration_required = models.BooleanField(
        default=True,
        help_text="Require championship registration before event participation"
    )
    
    # Simulator support
    supported_simulators = models.ManyToManyField(
        'sim.Simulator',
        help_text="Which simulators this league supports"
    )
    
    # Status
    is_active = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

#### 2. LeagueSeason Model
```python
class LeagueSeason(models.Model):
    """Represents a season/championship within a league"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    league = models.ForeignKey(League, on_delete=models.CASCADE, related_name='seasons')
    
    # Season identity
    name = models.CharField(max_length=255)
    slug = models.SlugField(max_length=300)
    season_number = models.IntegerField(default=1)
    
    # Timing
    start_date = models.DateField()
    end_date = models.DateField()
    registration_opens = models.DateTimeField(null=True, blank=True)
    registration_closes = models.DateTimeField(null=True, blank=True)
    
    # Scoring configuration
    scoring_system = models.JSONField(
        default=dict,
        help_text="""
        Example: {
            "positions": {
                "1": 25, "2": 20, "3": 15, "4": 12, "5": 10,
                "6": 8, "7": 6, "8": 4, "9": 2, "10": 1
            },
            "fastest_lap_bonus": 0,
            "drop_rounds": 2,
            "min_events_for_classification": 3
        }
        """
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('upcoming', 'Upcoming'),
            ('registration_open', 'Registration Open'),
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled')
        ],
        default='upcoming'
    )
    
    # Requirements
    min_license_level = models.CharField(max_length=10, blank=True)
    max_entries = models.IntegerField(null=True, blank=True)
    entry_requirements = models.JSONField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['league', 'slug']
        ordering = ['-season_number']
```

#### 3. LeagueRegistration Model
```python
class LeagueRegistration(models.Model):
    """Championship registration for a league season"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    
    season = models.ForeignKey(
        LeagueSeason,
        on_delete=models.CASCADE,
        related_name='registrations'
    )
    
    # Participant (user or team)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='league_registrations'
    )
    team = models.ForeignKey(
        'teams.Team',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='league_registrations'
    )
    
    # Registration details
    car_number = models.CharField(max_length=10, blank=True)
    car_class = models.ForeignKey(
        'sim.CarClass',
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    
    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('registered', 'Registered'),
            ('confirmed', 'Confirmed'),
            ('withdrawn', 'Withdrawn'),
            ('disqualified', 'Disqualified')
        ],
        default='registered'
    )
    
    # Metadata
    registration_date = models.DateTimeField(auto_now_add=True)
    withdrawn_date = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        unique_together = [
            ['season', 'user'],
            ['season', 'team']
        ]
        
    def clean(self):
        if not (self.user or self.team) or (self.user and self.team):
            raise ValidationError("Must have either user or team, not both")
```

#### 4. LeagueStanding Model
```python
class LeagueStanding(models.Model):
    """Points standings for a league season"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    
    season = models.ForeignKey(
        LeagueSeason,
        on_delete=models.CASCADE,
        related_name='standings'
    )
    registration = models.OneToOneField(
        LeagueRegistration,
        on_delete=models.CASCADE,
        related_name='standing'
    )
    
    # Points data
    total_points = models.IntegerField(default=0)
    position = models.IntegerField(null=True, blank=True)
    
    # Event participation tracking
    events_participated = models.IntegerField(default=0)
    events_completed = models.IntegerField(default=0)
    
    # Detailed points breakdown
    points_breakdown = models.JSONField(
        default=list,
        help_text="""
        List of: {
            "event_id": "uuid",
            "event_name": "Round 1 - Spa",
            "points": 25,
            "position": 1,
            "dropped": false
        }
        """
    )
    
    # Statistics
    wins = models.IntegerField(default=0)
    podiums = models.IntegerField(default=0)
    dnfs = models.IntegerField(default=0)
    best_finish = models.IntegerField(null=True, blank=True)
    average_finish = models.FloatField(null=True, blank=True)
    
    # Last calculation
    last_calculated = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['position', '-total_points']
        indexes = [
            models.Index(fields=['season', 'position']),
            models.Index(fields=['season', '-total_points'])
        ]
```

#### 5. Model Updates

##### Update Club Model
```python
# Add to Club model
club_type = models.CharField(
    max_length=20,
    choices=[
        ('standard', 'Standard Club'),
        ('personal_league', 'Personal League Organization'),
        ('private', 'Private Club')
    ],
    default='standard'
)
```

##### Update Event Model
```python
# Add to Event model
league_season = models.ForeignKey(
    'LeagueSeason',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='events',
    help_text="If this event is part of a league championship"
)
```

### Services & Business Logic

#### 1. LeagueService
```python
class LeagueService:
    @staticmethod
    def create_league(user, name, organizing_club=None, **kwargs):
        """Create a new league with optional personal club creation"""
        if not organizing_club:
            # Create personal league club
            organizing_club = Club.objects.create(
                name=f"{user.username}'s Racing League",
                slug=slugify(f"{user.username}-racing-league"),
                club_type='personal_league',
                is_public=False,
                created_by=user
            )
            # Auto-add creator as admin
            ClubMember.objects.create(
                user=user,
                club=organizing_club,
                role=ClubRole.ADMIN
            )
        
        league = League.objects.create(
            name=name,
            organizing_club=organizing_club,
            created_by=user,
            **kwargs
        )
        return league
```

#### 2. StandingsCalculationService
```python
class StandingsCalculationService:
    def calculate_season_standings(self, season):
        """Calculate standings for all participants in a season"""
        standings_data = {}
        
        # Get all events for this season
        events = Event.objects.filter(
            league_season=season,
            status=EventStatus.COMPLETED
        ).order_by('event_date')
        
        # Get scoring rules
        scoring_system = season.scoring_system
        positions_points = scoring_system.get('positions', {})
        drop_rounds = scoring_system.get('drop_rounds', 0)
        
        # Process each registration
        for registration in season.registrations.filter(
            status__in=['registered', 'confirmed']
        ):
            participant_data = self._calculate_participant_points(
                registration, events, positions_points, drop_rounds
            )
            standings_data[registration.id] = participant_data
        
        # Update standings
        self._update_standings_records(season, standings_data)
```

### API Endpoints

#### League Management
- `GET /api/leagues/` - List leagues (filtered by visibility)
- `POST /api/leagues/` - Create new league
- `GET /api/leagues/{id}/` - League details
- `PUT /api/leagues/{id}/` - Update league
- `DELETE /api/leagues/{id}/` - Delete league

#### Season Management
- `GET /api/leagues/{id}/seasons/` - List seasons for a league
- `POST /api/leagues/{id}/seasons/` - Create new season
- `GET /api/seasons/{id}/` - Season details
- `PUT /api/seasons/{id}/` - Update season
- `GET /api/seasons/{id}/standings/` - Current standings
- `POST /api/seasons/{id}/calculate-standings/` - Force standings recalculation

#### Registration
- `POST /api/seasons/{id}/register/` - Register for championship
- `GET /api/seasons/{id}/registrations/` - List registrations
- `PUT /api/registrations/{id}/` - Update registration (withdraw, etc.)

#### Event Participation
- `POST /api/events/{id}/opt-out/` - Opt out of specific event
- `POST /api/events/{id}/opt-in/` - Opt back into event

## 📱 Mobile Considerations

### API Design Principles
1. **Pagination**: All list endpoints support cursor-based pagination
2. **Filtering**: Support filtering by league, season, simulator
3. **Sparse Fieldsets**: Allow mobile clients to request only needed fields
4. **Caching**: ETags on standings endpoints for efficient updates

### Key Mobile Features
1. **Push Notifications**
   - New event scheduled
   - Registration opening/closing
   - Standings updated after event
   - Position changes in championship

2. **Offline Support**
   - Cache league standings for offline viewing
   - Queue registration actions when offline
   - Sync when connection restored

## 🚀 Implementation Plan

### Phase 1: Core Models & Migrations (Week 1)
- [ ] Create League, LeagueSeason, LeagueRegistration, LeagueStanding models
- [ ] Add club_type field to Club model
- [ ] Add league_season field to Event model
- [ ] Create and test migrations
- [ ] Update admin interface

### Phase 2: Business Logic (Week 2)
- [ ] Implement LeagueService for league/season creation
- [ ] Implement StandingsCalculationService
- [ ] Create Celery task for automatic standings updates
- [ ] Add league permission helpers
- [ ] Create management commands for testing

### Phase 3: API Development (Week 3)
- [ ] Create serializers for all league models
- [ ] Implement league CRUD endpoints
- [ ] Implement registration endpoints
- [ ] Implement standings endpoints
- [ ] Add API tests

### Phase 4: Frontend UI (Week 4)
- [ ] League creation modal/flow
- [ ] League listing and filtering
- [ ] Season management interface
- [ ] Registration management
- [ ] Standings display with driver details
- [ ] Event schedule with league context

### Phase 5: Testing & Polish (Week 5)
- [ ] Comprehensive unit tests
- [ ] Integration tests for standings calculation
- [ ] Performance testing with large leagues
- [ ] UI/UX testing and refinements
- [ ] Documentation updates

## 🔒 Security & Permissions

### Permission Model
```python
def can_manage_league(user, league):
    """Check if user can manage league"""
    # League creator
    if league.created_by == user:
        return True
    
    # Club admin/teams manager
    try:
        member = ClubMember.objects.get(
            user=user,
            club=league.organizing_club
        )
        return member.can_manage_club()
    except ClubMember.DoesNotExist:
        return False

def can_view_league(user, league):
    """Check if user can view league"""
    if league.visibility == EventVisibility.PUBLIC:
        return True
    # ... additional visibility checks
```

## 📊 Performance Considerations

### Database Optimization
1. **Indexes**: Add composite indexes for common queries
2. **Denormalization**: Cache participant count on LeagueSeason
3. **Query Optimization**: Use select_related/prefetch_related
4. **Standings Cache**: Redis cache for standings with 5-minute TTL

### Scaling Strategy
1. **Background Processing**: All standings calculations in Celery
2. **Pagination**: Limit standings API to 50 participants per page
3. **CDN**: Cache standings pages at edge for public leagues

## 🚦 Feature Flags

```python
# config/settings/base.py
FEATURE_FLAGS = {
    'LEAGUES_ENABLED': env.bool('FEATURE_LEAGUES_ENABLED', default=False),
    'LEAGUES_BETA_USERS': env.list('FEATURE_LEAGUES_BETA_USERS', default=[]),
}

# Usage in views/serializers
if not settings.FEATURE_FLAGS['LEAGUES_ENABLED']:
    if request.user.username not in settings.FEATURE_FLAGS['LEAGUES_BETA_USERS']:
        raise PermissionDenied("Leagues feature not yet available")
```

## 📈 Success Metrics & Monitoring

### Key Metrics
1. **Adoption**: Number of leagues created per week
2. **Engagement**: Average participants per league
3. **Retention**: % of registered users completing >50% of events
4. **Performance**: P95 standings calculation time

### Monitoring
- Sentry for error tracking
- DataDog for performance metrics
- Custom Django admin dashboard for league statistics

## 🔄 Future Enhancements

### Version 1.1
- Team championships (multiple drivers per entry)
- Custom points for qualifying/fastest lap
- League championships spanning multiple series

### Version 1.2
- Automated invitations and waitlists
- League statistics and records
- Driver of the Day voting
- Live timing integration

### Version 2.0
- Multi-class championships
- Handicap/ballast systems
- League licensing system
- Sponsor management

## 📝 Appendix

### Example Scoring System JSON
```json
{
  "positions": {
    "1": 25,
    "2": 18,
    "3": 15,
    "4": 12,
    "5": 10,
    "6": 8,
    "7": 6,
    "8": 4,
    "9": 2,
    "10": 1
  },
  "fastest_lap_bonus": 0,
  "pole_position_bonus": 0,
  "drop_rounds": 2,
  "min_events_for_classification": 4,
  "dnf_classification_percentage": 90
}
```

### Example League Creation Flow
1. User clicks "Create League"
2. System checks if user has any clubs with admin rights
3. If no: "Would you like to create this league under your personal organization?"
4. User enters league details (name, description, base series)
5. System creates personal club (if needed) and league
6. Redirects to season creation flow

---

_End of PRD v1.0_ 