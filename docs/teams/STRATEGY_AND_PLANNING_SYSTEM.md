# Race Strategy and Stint Planning System

_Created: December 2024_  
_Version: 1.0_

## 🎯 Overview

This document outlines the design and implementation of the race strategy and stint planning system for SimLane. The system replaces the previous complex model structure with a more flexible, service-oriented approach that supports both club-organized and individual team events.

## 🔄 Previous Model Structure (Deprecated)

The following models were removed in favor of a unified approach:
- `EventSignup` - Redundant with EventParticipation
- `EventSignupAvailability` - Merged into EventParticipation as JSON field
- `StintAssignment` - Replaced by StintPlan with better flexibility
- `TeamAllocation` - Replaced by service-layer team formation
- `TeamAllocationMember` - Unnecessary with direct team relationships
- `TeamEventStrategy` - Replaced by RaceStrategy model

### Why These Were Removed

1. **Model Duplication**: Multiple models tracked similar concepts
2. **Rigid Workflow**: Enforced club-centric patterns
3. **Data Fragmentation**: Related information scattered across tables
4. **Query Complexity**: Required multiple joins for basic operations

## 📊 New Architecture

### Core Models

#### 1. EventParticipation (Unified Participation Model)
```python
class EventParticipation(models.Model):
    """
    Single model handling all participation phases:
    - Interest/Signup collection
    - Team assignment
    - Event entry confirmation
    """
    # Core relationships
    event = models.ForeignKey(Event, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, null=True, blank=True)
    
    # Workflow tracking
    participation_type = models.CharField(max_length=20)  
    status = models.CharField(max_length=20)
    
    # All preferences in one place
    availability_windows = models.JSONField()
    preferred_car = models.ForeignKey(SimCar)
    role_preferences = models.JSONField()
    
    # Assignment results
    assigned_car = models.ForeignKey(SimCar)
    assigned_instance = models.ForeignKey(EventInstance)
```

#### 2. RaceStrategy (Replaces TeamEventStrategy)
```python
class RaceStrategy(models.Model):
    """High-level race strategy for a team"""
    team = models.ForeignKey(Team)
    event = models.ForeignKey(Event)
    event_instance = models.ForeignKey(EventInstance)
    
    # Strategy parameters
    target_stint_length = models.IntegerField()
    min_driver_rest = models.IntegerField()
    pit_stop_time = models.IntegerField()
    
    # Fuel and tire strategy
    fuel_per_stint = models.FloatField()
    tire_change_frequency = models.IntegerField()
```

#### 3. StintPlan (Replaces StintAssignment)
```python
class StintPlan(models.Model):
    """Individual stint within a strategy"""
    strategy = models.ForeignKey(RaceStrategy)
    driver = models.ForeignKey(User)
    stint_number = models.IntegerField()
    
    # Planned timing
    planned_start_time = models.DurationField()
    planned_duration = models.DurationField()
    
    # Actual execution
    actual_start_time = models.DateTimeField()
    actual_end_time = models.DateTimeField()
    
    # Status tracking
    status = models.CharField(max_length=20)
    pit_instructions = models.JSONField()
```

## 🚀 Service Layer Architecture

### Team Formation Service

The team formation process is now handled by services rather than models:

```python
class TeamFormationService:
    """Intelligent team formation based on compatibility"""
    
    def form_teams_for_event(self, event, max_team_size=4):
        # Get signups
        # Apply compatibility algorithm
        # Create teams
        # Update participations
    
    def _calculate_compatibility_score(self, user1, user2):
        # Availability overlap
        # Car preference match
        # Skill balance
        # Role complementarity
```

### Key Algorithms

#### 1. Availability Matching
```python
def calculate_availability_overlap(windows1, windows2):
    """Calculate overlap percentage between two availability sets"""
    total_overlap = 0
    
    for window1 in windows1:
        for window2 in windows2:
            overlap = calculate_time_overlap(window1, window2)
            total_overlap += overlap
    
    return total_overlap / max(len(windows1), len(windows2))
```

#### 2. Team Balancing
```python
def balance_teams_by_skill(participants, team_count):
    """Distribute participants to create balanced teams"""
    sorted_participants = sorted(participants, key=lambda p: p.skill_rating)
    teams = [[] for _ in range(team_count)]
    
    # Snake draft distribution
    for i, participant in enumerate(sorted_participants):
        if (i // team_count) % 2 == 0:
            teams[i % team_count].append(participant)
        else:
            teams[team_count - 1 - (i % team_count)].append(participant)
    
    return teams
```

### Stint Planning Service

```python
class StintPlanningService:
    """Create and manage stint plans"""
    
    def create_initial_plan(self, strategy):
        # Calculate required stints
        # Distribute among drivers
        # Apply rest constraints
        # Return stint plan
    
    def validate_plan(self, strategy):
        # Check rest periods
        # Verify total coverage
        # Ensure regulation compliance
    
    def optimize_plan(self, strategy, constraints):
        # Balance drive time
        # Minimize pit stops
        # Optimize driver freshness
```

## 🎮 Real-Time Management

### Live Strategy Updates
```python
class LiveRaceService:
    def update_stint_progress(self, stint_id, lap=None, status=None):
        # Update actual times
        # Auto-ready next stint
        # Notify team
    
    def emergency_driver_swap(self, stint_id, new_driver_id):
        # Validate swap
        # Update stint
        # Adjust future stints
    
    def extend_current_stint(self, stint_id, additional_laps):
        # Update current stint
        # Shift subsequent stints
        # Recalculate fuel
```

### Strategy Adjustments

#### 1. Dynamic Rebalancing
- Adjust for pace differences
- Account for incidents/delays  
- Optimize based on current standings

#### 2. Weather Adaptations
- Tire strategy changes
- Stint length adjustments
- Driver specialization (wet/dry)

## 📈 Analytics and Reporting

### Performance Metrics
```python
class StrategyAnalytics:
    def analyze_strategy_performance(self, strategy):
        return {
            'driver_equality': self.calculate_drive_time_variance(),
            'pit_efficiency': self.calculate_pit_stop_efficiency(),
            'pace_consistency': self.calculate_pace_variance(),
            'strategy_adherence': self.calculate_plan_vs_actual()
        }
```

### Post-Race Analysis
- Planned vs actual comparison
- Driver performance metrics
- Pit stop analysis
- Strategic decision impact

## 🔧 Implementation Plan

### Phase 1: Core Models (Week 1)
1. Create RaceStrategy model
2. Create StintPlan model  
3. Add strategy relationship to Team
4. Create migrations

### Phase 2: Services (Week 2)
1. Implement TeamFormationService
2. Build StintPlanningService
3. Create LiveRaceService
4. Add validation logic

### Phase 3: UI Components (Week 3-4)
1. Team formation wizard
2. Stint planning interface
3. Live strategy dashboard
4. Post-race analytics

### Phase 4: Testing & Optimization (Week 5)
1. Unit tests for services
2. Integration testing
3. Performance optimization
4. User acceptance testing

## 🎯 Benefits

### For Users
- **Flexibility**: Support for various event formats
- **Intelligence**: Smart team formation
- **Real-time**: Live strategy adjustments
- **Analytics**: Detailed performance insights

### For Development  
- **Maintainability**: Clean service architecture
- **Testability**: Isolated business logic
- **Extensibility**: Easy to add new features
- **Performance**: Optimized queries

## 🔒 Technical Considerations

### Caching Strategy
```python
# Cache strategy calculations
@cache_page(60 * 5)
def get_stint_plan_view(request, strategy_id):
    # Expensive calculations cached
    
# Cache compatibility scores
cache.set(f'compatibility_{user1}_{user2}', score, 3600)
```

### Real-time Updates
- WebSocket for live stint updates
- Pub/sub for team notifications
- Optimistic UI updates

### Data Integrity
- Transactions for team formation
- Locks for stint updates
- Validation at every step

## 📊 Database Optimization

### Indexes
```python
class Meta:
    indexes = [
        models.Index(fields=['strategy', 'stint_number']),
        models.Index(fields=['driver', 'status']),
        models.Index(fields=['event', 'team']),
    ]
```

### Query Optimization
- Use select_related for foreign keys
- Prefetch_related for many-to-many
- Aggregate queries for analytics

## 🚀 Future Enhancements

### AI-Powered Strategy
- Machine learning for optimal stint lengths
- Predictive pit stop timing
- Driver performance prediction

### Advanced Features
- Multi-class strategy coordination
- Weather prediction integration
- Fuel saving calculations
- Tire degradation models

### Integration
- Import strategies from other tools
- Export to racing simulators
- Team communication integration

## 📝 Conclusion

The new strategy and planning system provides a flexible, powerful foundation for managing endurance racing teams. By moving from rigid models to intelligent services, we enable teams to adapt strategies in real-time while maintaining clean, maintainable code.

The system supports everything from casual weekend races to professional endurance events, with the flexibility to grow as SimLane's needs evolve. 