# Teams App Model Analysis v2

_Created: December 2024_  
_Version: 2.0 - Post-Consolidation Analysis_

## 🎯 Executive Summary

This document analyzes the current state of the teams app models after the recent consolidation efforts. We've successfully unified the event participation system, but there are still opportunities for improvement in code organization, performance optimization, and feature completeness.

## ✅ Current State (Post-Consolidation)

### Successfully Consolidated Models

1. **EventParticipation** - Now handles:
   - Individual event entries
   - Team event signups (interest phase)
   - Team event entries (confirmed phase)
   - All availability and preference data

2. **AvailabilityWindow** - Granular availability tracking with:
   - UTC time storage
   - Role-specific availability
   - Preference levels
   - Local timezone support

3. **Team** - Enhanced with:
   - User ownership OR SimProfile ownership
   - Imported team support
   - Club-optional structure
   - Temporary team support

4. **TeamMember** - Enhanced role system with:
   - Granular permissions
   - Time-bound memberships
   - Multiple role types

### Models Removed
- EventSignup
- EventSignupAvailability
- StintAssignment
- TeamAllocation
- TeamAllocationMember
- TeamEventStrategy

## 🔍 Identified Issues & Improvements

### 1. Legacy Models Still Present

**Issue**: `EventEntry`, `DriverAvailability`, and `PredictedStint` are still in the codebase but appear to be superseded by the new unified system.

**Recommendation**: 
```python
# These models should be marked for deprecation or removal:
- EventEntry (lines 455-498) - Replaced by EventParticipation
- DriverAvailability (lines 499-535) - Replaced by AvailabilityWindow
- PredictedStint (lines 536-575) - Should be moved to strategy system
```

**Migration Path**:
1. Verify no active code uses these models
2. Create data migration to EventParticipation
3. Mark as deprecated with warnings
4. Remove in next major version

### 2. Missing Strategy & Planning Models

**Issue**: We removed TeamEventStrategy and StintAssignment but haven't implemented the replacement models discussed in the strategy document.

**Recommendation**: Implement the new models:
```python
class RaceStrategy(models.Model):
    """High-level race strategy for a team in an event"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="strategies")
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="strategies")
    event_instance = models.ForeignKey(EventInstance, on_delete=models.CASCADE)
    
    name = models.CharField(max_length=255, default="Primary Strategy")
    is_active = models.BooleanField(default=True)
    
    # Strategy parameters
    target_stint_length = models.IntegerField(help_text="Target stint length in minutes")
    min_driver_rest = models.IntegerField(help_text="Minimum rest between stints in minutes")
    pit_stop_time = models.IntegerField(default=60, help_text="Expected pit stop time in seconds")
    
    # Fuel and tire strategy
    fuel_per_stint = models.FloatField(null=True, blank=True)
    tire_change_frequency = models.IntegerField(default=1)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['team', 'event', 'name']]
        indexes = [
            models.Index(fields=['team', 'event']),
            models.Index(fields=['is_active']),
        ]

class StintPlan(models.Model):
    """Individual stint within a race strategy"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    strategy = models.ForeignKey(RaceStrategy, on_delete=models.CASCADE, related_name='stints')
    driver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stint_plans')
    stint_number = models.IntegerField()
    
    # Planned timing
    planned_start_lap = models.IntegerField(null=True, blank=True)
    planned_end_lap = models.IntegerField(null=True, blank=True)
    planned_start_time = models.DurationField(null=True, blank=True)
    planned_duration = models.DurationField()
    
    # Actual execution
    actual_start_lap = models.IntegerField(null=True, blank=True)
    actual_end_lap = models.IntegerField(null=True, blank=True)
    actual_start_time = models.DateTimeField(null=True, blank=True)
    actual_end_time = models.DateTimeField(null=True, blank=True)
    
    # Status and instructions
    status = models.CharField(max_length=20, choices=[...], default='planned')
    pit_instructions = models.JSONField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['stint_number']
        unique_together = [['strategy', 'stint_number']]
```

### 3. Performance Optimizations Needed

**Issue**: Complex queries in AvailabilityWindow methods could impact performance at scale.

**Recommendations**:

#### a) Add Database-Level Constraints
```python
class AvailabilityWindow(models.Model):
    class Meta:
        # Add these constraints
        constraints = [
            models.CheckConstraint(
                check=models.Q(start_time__lt=models.F('end_time')),
                name='availability_window_valid_time_range'
            ),
            models.CheckConstraint(
                check=models.Q(
                    can_drive=True) | models.Q(can_spot=True) | models.Q(can_strategize=True
                ),
                name='availability_window_has_role'
            ),
        ]
```

#### b) Optimize Overlap Queries
```python
# Add GiST index for time range queries (PostgreSQL)
from django.contrib.postgres.indexes import GistIndex
from django.contrib.postgres.fields import DateTimeRangeField

class AvailabilityWindow(models.Model):
    # Consider using DateTimeRangeField for better performance
    time_range = DateTimeRangeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            GistIndex(fields=['time_range']),  # For overlap queries
        ]
```

#### c) Add Caching for Complex Calculations
```python
from django.core.cache import cache

class AvailabilityWindow(models.Model):
    @classmethod
    def get_team_formation_recommendations(cls, event, team_size=3, min_coverage_hours=6):
        cache_key = f'team_recommendations_{event.id}_{team_size}_{min_coverage_hours}'
        recommendations = cache.get(cache_key)
        
        if recommendations is None:
            recommendations = cls._calculate_recommendations(event, team_size, min_coverage_hours)
            cache.set(cache_key, recommendations, 300)  # Cache for 5 minutes
        
        return recommendations
```

### 4. Model Method Organization

**Issue**: Large model classes with many methods reduce readability and violate single responsibility principle.

**Recommendation**: Extract complex logic to services and managers:

```python
# models.py
class EventParticipationQuerySet(models.QuerySet):
    def for_event(self, event):
        return self.filter(event=event)
    
    def signed_up(self):
        return self.filter(status='signed_up')
    
    def awaiting_team_formation(self):
        return self.filter(
            participation_type='team_signup',
            status__in=['signed_up', 'team_formation']
        )

class EventParticipationManager(models.Manager):
    def get_queryset(self):
        return EventParticipationQuerySet(self.model, using=self._db)
    
    def create_signup(self, event, user, **kwargs):
        return self.create(
            event=event,
            user=user,
            participation_type='team_signup',
            status='signed_up',
            signed_up_at=timezone.now(),
            **kwargs
        )

class EventParticipation(models.Model):
    # ... fields ...
    
    objects = EventParticipationManager()
    
    # Keep only simple property methods in the model
    @property
    def is_confirmed(self):
        return self.status == 'confirmed'
```

### 5. Missing Event Organization Features

**Issue**: Event creation and management still requires direct Event model manipulation.

**Recommendation**: Add event organization helpers:
```python
class EventOrganizer(models.Model):
    """Track who can organize events"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    can_create_public_events = models.BooleanField(default=False)
    can_create_private_events = models.BooleanField(default=True)
    max_concurrent_events = models.IntegerField(default=5)
    
    class Meta:
        unique_together = ['user']

class UserOrganizedEvent(models.Model):
    """Link events to their organizers (non-club events)"""
    event = models.OneToOneField(Event, on_delete=models.CASCADE)
    organizer = models.ForeignKey(User, on_delete=models.CASCADE)
    is_team_event = models.BooleanField(default=False)
    team_size_target = models.IntegerField(null=True, blank=True)
    
    # Privacy settings
    visibility = models.CharField(max_length=20, choices=[...])
    password = models.CharField(max_length=128, blank=True)  # For private events
```

### 6. Data Integrity Improvements

**Issue**: Some business rules are enforced in Python rather than database constraints.

**Recommendations**:

#### a) Add Trigger for Team Member Limits
```python
# In migration
from django.db import migrations

def create_team_size_trigger(apps, schema_editor):
    schema_editor.execute("""
        CREATE OR REPLACE FUNCTION check_team_size()
        RETURNS TRIGGER AS $$
        BEGIN
            IF (SELECT COUNT(*) FROM teams_teammember 
                WHERE team_id = NEW.team_id AND status = 'active') >= 10 THEN
                RAISE EXCEPTION 'Team cannot have more than 10 active members';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        
        CREATE TRIGGER enforce_team_size
        BEFORE INSERT ON teams_teammember
        FOR EACH ROW EXECUTE FUNCTION check_team_size();
    """)
```

#### b) Ensure Participation Consistency
```python
class EventParticipation(models.Model):
    class Meta:
        constraints = [
            # Add this constraint
            models.CheckConstraint(
                check=~models.Q(
                    status='confirmed',
                    assigned_car__isnull=True
                ),
                name='confirmed_participation_requires_car'
            ),
        ]
```

### 7. API Integration Preparedness

**Issue**: Models lack serialization-friendly methods and API versioning support.

**Recommendation**: Add API-friendly methods:
```python
class Team(models.Model):
    # ... existing fields ...
    
    api_version = models.IntegerField(default=1)
    
    def to_api_dict(self, version=None):
        """Serialize for API consumption"""
        version = version or self.api_version
        
        data = {
            'id': str(self.id),
            'name': self.name,
            'slug': self.slug,
            'is_active': self.is_active,
            'member_count': self.members.filter(status='active').count(),
        }
        
        if version >= 2:
            data['created_at'] = self.created_at.isoformat()
            data['owner_type'] = 'user' if self.owner_user else 'sim_profile'
        
        return data
```

### 8. Testing Infrastructure

**Issue**: Complex model methods lack comprehensive test coverage indicators.

**Recommendation**: Add test helpers:
```python
# tests/factories.py
import factory
from factory.django import DjangoModelFactory
from teams.models import Team, EventParticipation

class TeamFactory(DjangoModelFactory):
    class Meta:
        model = Team
    
    name = factory.Sequence(lambda n: f"Team {n}")
    owner_user = factory.SubFactory('users.tests.factories.UserFactory')
    is_active = True

class EventParticipationFactory(DjangoModelFactory):
    class Meta:
        model = EventParticipation
    
    event = factory.SubFactory('sim.tests.factories.EventFactory')
    user = factory.SubFactory('users.tests.factories.UserFactory')
    participation_type = 'individual'
    status = 'signed_up'
```

## 🚀 Implementation Priorities

### High Priority (Week 1-2)
1. Remove/deprecate legacy models (EventEntry, DriverAvailability, PredictedStint)
2. Implement RaceStrategy and StintPlan models
3. Add missing database constraints
4. Extract complex logic to services

### Medium Priority (Week 3-4)
1. Performance optimizations (indexes, caching)
2. Event organization features
3. API preparation methods
4. Comprehensive test factories

### Low Priority (Future)
1. PostgreSQL-specific optimizations
2. Advanced caching strategies
3. Real-time features preparation
4. Analytics pre-computation

## 📊 Migration Strategy

### Phase 1: Data Migration
```python
# migrations/0006_migrate_legacy_data.py
def migrate_event_entries(apps, schema_editor):
    EventEntry = apps.get_model('teams', 'EventEntry')
    EventParticipation = apps.get_model('teams', 'EventParticipation')
    
    for entry in EventEntry.objects.all():
        EventParticipation.objects.create(
            event=entry.event,
            user=entry.user,
            team=entry.team,
            participation_type='individual' if entry.user else 'team_entry',
            status='confirmed',
            assigned_car=entry.sim_car,
            assigned_class=entry.event_class,
            entered_at=entry.created_at,
        )
```

### Phase 2: Code Updates
1. Update all views using legacy models
2. Update serializers and API endpoints
3. Update admin interfaces
4. Update background tasks

### Phase 3: Cleanup
1. Add deprecation warnings
2. Monitor for usage
3. Remove in next major version

## 💡 Future Enhancements

### 1. Multi-Series Championships
```python
class Championship(models.Model):
    """Support for multi-event championships"""
    name = models.CharField(max_length=255)
    events = models.ManyToManyField(Event, through='ChampionshipRound')
    scoring_system = models.JSONField()  # Points allocation rules

class ChampionshipStanding(models.Model):
    """Track standings across championship"""
    championship = models.ForeignKey(Championship, on_delete=models.CASCADE)
    participant = models.ForeignKey(EventParticipation, on_delete=models.CASCADE)
    points = models.IntegerField(default=0)
```

### 2. Advanced Team Analytics
```python
class TeamPerformanceMetric(models.Model):
    """Track team performance over time"""
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    
    avg_lap_time = models.DurationField()
    consistency_score = models.FloatField()
    pit_stop_efficiency = models.FloatField()
    driver_rotation_score = models.FloatField()
```

### 3. Social Features
```python
class TeamPost(models.Model):
    """Team news and updates"""
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    is_public = models.BooleanField(default=False)
    
class TeamFollower(models.Model):
    """Allow users to follow teams"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    notifications_enabled = models.BooleanField(default=True)
```

## 📝 Conclusion

The teams app has made significant progress with the model consolidation. The unified EventParticipation and enhanced Team models provide a solid foundation. However, there are clear opportunities for improvement in:

1. **Cleanup**: Removing legacy models
2. **Completeness**: Adding strategy/planning models
3. **Performance**: Optimizing queries and adding indexes
4. **Organization**: Extracting logic to services
5. **Robustness**: Adding database constraints

By addressing these areas systematically, we can create a more maintainable, performant, and feature-rich teams system. 