# Sim Model Migration Plan: RaceWeek + Event Merger

## Progress Tracking

- [x] Phase 5.1: Model Layer Changes - **COMPLETED**
  - [x] Analyzed current RaceWeek and Event models
  - [x] Merged RaceWeek fields into Event model
  - [x] Renamed EventInstance to TimeSlot
  - [x] Updated CarRestriction to reference Event
  - [x] Removed RaceWeek model
  - [x] Updated admin.py for new models
- [x] Phase 5.2: API Integration Updates - **IN PROGRESS**
  - [x] Started updating simlane/iracing/tasks.py (imports updated, main logic partially converted)
  - [x] Started updating simlane/iracing/auto_create.py (imports updated, function signatures updated)
  - [ ] Complete tasks.py EventInstance → TimeSlot conversion
  - [ ] Complete auto_create.py RaceWeek → Event conversion  
  - [ ] Updated management commands  
  - [x] Phase 5.3: Views and Templates - **COMPLETED**
    - [x] Updated simlane/sim/views.py (partially - imports and main logic updated)
    - [x] Updated templates to use time_slots instead of instances
    - [x] Updated templates to use event fields instead of race_week_context
    - [x] Updated teams templates to use time_slots
    - [x] URL patterns remain compatible (no changes needed)
- [ ] Phase 5.4: Teams Integration
- [ ] Phase 5.5: Testing and Documentation

## Overview

This document outlines the comprehensive migration plan for:
1. **Merging RaceWeek and Event models** into a single Event model
2. **Renaming EventInstance to TimeSlot**
3. **Updating all related code, views, templates, and services**

## Phase 1: Analysis and Preparation

### 1.1 Current Model Dependencies

#### Files Referencing RaceWeek:
- `simlane/sim/models.py` - Model definition
- `simlane/sim/admin.py` - Admin interface
- `simlane/sim/views.py` - View logic
- `simlane/iracing/tasks.py` - API integration tasks
- `simlane/iracing/auto_create.py` - Auto-creation logic
- `simlane/iracing/management/commands/test_fetch_user_races.py` - Management commands
- `simlane/templates/sim/events/detail.html` - Template display
- Multiple migration files

#### Files Referencing EventInstance:
- `simlane/sim/models.py` - Model definition
- `simlane/sim/admin.py` - Admin interface
- `simlane/sim/utils/result_processing.py` - Result processing
- `simlane/iracing/tasks.py` - API integration
- `simlane/iracing/auto_create.py` - Auto-creation logic
- `simlane/teams/models.py` - Team event relationships
- `simlane/teams/services.py` - Team services
- `simlane/core/management/commands/seed_dev_data.py` - Seed data
- Multiple templates and migration files

### 1.2 Key Relationships to Preserve

```python
# Current structure
Series -> Season -> RaceWeek -> Event -> EventInstance
                         |
                    CarRestriction

# Target structure  
Series -> Season -> Event -> TimeSlot
                      |
                 CarRestriction (updated FK)
```

## Phase 2: Model Changes

### 2.1 New Event Model Structure

The merged Event model will combine fields from both RaceWeek and Event:

**Fields from RaceWeek:**
- `round_number` (replaces `week_number`)
- `start_date`, `end_date` (timing)
- `weather_config`, `weather_forecast_url`, `weather_forecast_data`
- `time_pattern` (recurring schedule)
- `category`, `enable_pitlane_collisions`, `full_course_cautions`
- `track_state`, weather summary fields

**Fields from Event:**
- All existing Event fields (name, description, visibility, etc.)
- Participation management fields
- Entry requirements
- Organizer information

### 2.2 Updated Related Models

**CarRestriction:**
- FK changes from `race_week` to `event`
- Related name updates

**TimeSlot (renamed from EventInstance):**
- No field changes, just rename
- Related name changes

## Phase 3: File-by-File Changes

### 3.1 Core Model Files

#### `simlane/sim/models.py`
**Changes Required:**
- [ ] Remove `RaceWeek` model entirely (lines 940-1022)
- [ ] Update `Event` model with merged fields
- [ ] Rename `EventInstance` to `TimeSlot` (lines 1510+)
- [ ] Update `CarRestriction` model FK (line 1024: `race_week` → `event`)
- [ ] Update related_name references
- [ ] Remove `race_week` FK from Event model (line 1164)
- [ ] Update property methods in EventInstance/TimeSlot

#### `simlane/sim/admin.py`
**Changes Required:**
- [ ] Remove `RaceWeekAdmin` (lines 290+)
- [ ] Update `EventAdmin` with new fields
- [ ] Rename `EventInstanceAdmin` to `TimeSlotAdmin`
- [ ] Update `CarRestrictionAdmin` fields and filters

### 3.2 API Integration Files

#### `simlane/iracing/tasks.py`
**Changes Required:**
- [ ] Remove RaceWeek import (line 24)
- [ ] Update `_process_series_seasons()` function (lines 876+)
- [ ] Remove RaceWeek creation logic (lines 1168+)
- [ ] Update Event creation to include merged fields
- [ ] Update `update_weather_forecast_task()` (lines 1696+)
- [ ] Rename EventInstance to TimeSlot references

#### `simlane/iracing/auto_create.py`
**Changes Required:**
- [ ] Remove RaceWeek import (line 21)
- [ ] Update `auto_create_event_chain_from_results()` signature
- [ ] Remove RaceWeek creation (lines 357+)
- [ ] Update Event creation with weather/timing fields
- [ ] Update `fetch_and_cache_weather_forecast()` to work with Event
- [ ] Rename EventInstance to TimeSlot

### 3.3 View Files

#### `simlane/sim/views.py`
**Changes Required:**
- [ ] Remove `race_week_context` logic (lines 985+)
- [ ] Update context building in `event_detail()`
- [ ] Update BOP restriction queries
- [ ] Use `event.round_number` instead of `race_week_context.week_number`
- [ ] Update weather data access patterns
- [ ] Rename EventInstance to TimeSlot references

### 3.4 Template Files

#### `simlane/templates/sim/events/detail.html`
**Changes Required:**
- [ ] Remove `race_week_context` references (line 154)
- [ ] Update to use `event.round_number`
- [ ] Update weather data access
- [ ] Rename `instances` to `time_slots`

#### `simlane/templates/sim/events/events_list_partial.html`
**Changes Required:**
- [ ] Rename `instances` to `time_slots` (lines 131+)
- [ ] Update instance counting logic

#### `simlane/templates/teams/club_event_signup_detail.html`
**Changes Required:**
- [ ] Rename `instances` to `time_slots` (line 32)
- [ ] Update time slot references

#### `simlane/templates/emails/event_signup_confirmation.html`
**Changes Required:**
- [ ] Rename `event_instance` to `time_slot` (line 493)
- [ ] Update all time slot property references

### 3.5 Teams App Integration

#### `simlane/teams/models.py`
**Changes Required:**
- [ ] Rename EventInstance import to TimeSlot (line 9)
- [ ] Update FK field references to `time_slots`
- [ ] Update related_name references

#### `simlane/teams/services.py`
**Changes Required:**
- [ ] Update EventInstance import to TimeSlot (line 19)
- [ ] Update query logic and method signatures

#### `simlane/teams/tests/test_models.py`
**Changes Required:**
- [ ] Update EventInstance import (line 12)
- [ ] Update test data creation (line 201)

### 3.6 Management Commands

#### `simlane/iracing/management/commands/test_fetch_user_races.py`
**Changes Required:**
- [ ] Remove RaceWeek import (line 88)
- [ ] Update query logic (lines 118+)
- [ ] Rename EventInstance to TimeSlot

#### `simlane/core/management/commands/seed_dev_data.py`
**Changes Required:**
- [ ] Remove RaceWeek creation logic
- [ ] Update Event creation with merged fields (line 701)
- [ ] Rename EventInstance to TimeSlot (line 16)

### 3.7 Utility Files

#### `simlane/sim/utils/result_processing.py`
**Changes Required:**
- [ ] Rename EventInstance to TimeSlot in function signatures
- [ ] Update import statements

## Phase 4: Migration Strategy

### 4.1 Database Migration Approach

Since we're not live yet, we'll use the clean migration approach:

```bash
# 1. Remove all migration files (except __init__.py)
find simlane/*/migrations/ -name "0*.py" -delete

# 2. Update models.py with new structure
# (Apply all model changes first)

# 3. Create fresh migrations
python manage.py makemigrations sim
python manage.py makemigrations teams
python manage.py makemigrations

# 4. Apply migrations
python manage.py migrate
```

### 4.2 Model Implementation Order

1. **Update Event model** with merged fields
2. **Remove RaceWeek model** completely
3. **Rename EventInstance to TimeSlot**
4. **Update CarRestriction** FK references
5. **Update all imports** and references

## Phase 5: Implementation Phases

### Phase 5.1: Model Layer (Week 1)
**Priority: Critical**
- [ ] Update `simlane/sim/models.py`
- [ ] Update `simlane/sim/admin.py` 
- [ ] Delete and recreate migrations
- [ ] Update core model tests
- [ ] Verify database schema

### Phase 5.2: API Integration (Week 2) 
**Priority: High**
- [ ] Update `simlane/iracing/tasks.py`
- [ ] Update `simlane/iracing/auto_create.py`
- [ ] Update `simlane/iracing/services.py`
- [ ] Update management commands
- [ ] Test API integration flow

### Phase 5.3: Views and Templates (Week 2-3)
**Priority: High**
- [ ] Update `simlane/sim/views.py`
- [ ] Update all templates in `simlane/templates/`
- [ ] Update context building logic
- [ ] Test UI functionality

### Phase 5.4: Teams Integration (Week 3)
**Priority: Medium**
- [ ] Update `simlane/teams/models.py`
- [ ] Update `simlane/teams/services.py`
- [ ] Update team-related templates
- [ ] Update team tests

### Phase 5.5: Utilities and Commands (Week 3)
**Priority: Medium**
- [ ] Update `simlane/sim/utils/`
- [ ] Update `simlane/core/management/commands/`
- [ ] Update seed data commands
- [ ] Test data seeding

### Phase 5.6: Testing and Documentation (Week 4)
**Priority: Medium**
- [ ] Update all test files
- [ ] Comprehensive integration testing
- [ ] Update documentation
- [ ] Performance testing

## Phase 6: Detailed Implementation Checklist

### 6.1 Model Changes Checklist

#### Event Model Updates:
- [ ] Add `round_number` field (replaces week_number)
- [ ] Add weather fields from RaceWeek
- [ ] Add timing fields from RaceWeek  
- [ ] Add track settings from RaceWeek
- [ ] Add time_pattern field
- [ ] Remove `race_week` FK field
- [ ] Update Meta class indexes
- [ ] Update `__str__` method
- [ ] Add property methods for weather access

#### TimeSlot Model (renamed from EventInstance):
- [ ] Rename model class
- [ ] Update related_name to `time_slots`
- [ ] Update `__str__` method
- [ ] Update property methods

#### CarRestriction Model Updates:
- [ ] Change FK from `race_week` to `event`
- [ ] Update related_name to `event_restrictions`
- [ ] Update Meta class unique_together
- [ ] Update `__str__` method

### 6.2 Critical Code Patterns to Update

#### Import Statements:
```python
# Old
from simlane.sim.models import RaceWeek, EventInstance
# New  
from simlane.sim.models import TimeSlot
```

#### Model Queries:
```python
# Old
race_week.car_restrictions.all()
event.race_week.weather_forecast_data
event.instances.all()

# New
event.car_restrictions.all()
event.weather_forecast_data  
event.time_slots.all()
```

#### Template Variables:
```html
<!-- Old -->
{{ race_week_context.week_number }}
{{ event.instances.all }}

<!-- New -->
{{ event.round_number }}
{{ event.time_slots.all }}
```

### 6.3 Testing Strategy

#### Unit Tests:
- [ ] Model creation and validation
- [ ] Model relationships and queries
- [ ] Property methods and computed fields
- [ ] Admin interface functionality

#### Integration Tests:
- [ ] API data import flow
- [ ] Event creation from iRacing data
- [ ] Weather forecast integration
- [ ] Team event signup flow

#### Manual Testing:
- [ ] Admin interface CRUD operations
- [ ] Event detail page display
- [ ] Event list functionality
- [ ] Team event features
- [ ] API integration endpoints

## Phase 7: Risk Mitigation

### 7.1 High Risk Areas

1. **Complex API Integration**: iRacing tasks with intricate RaceWeek logic
2. **Template Dependencies**: Multiple templates using race_week_context
3. **Team App Integration**: Deep EventInstance dependencies
4. **Query Performance**: Potential performance impact from model changes

### 7.2 Mitigation Strategies

1. **Incremental Implementation**: Test each file change individually
2. **Backup Strategy**: Git branching for easy rollback
3. **Documentation**: Detailed change log for debugging
4. **Performance Monitoring**: Before/after performance comparisons

### 7.3 Rollback Plan

If critical issues arise:
1. **Git Revert**: Roll back to pre-migration state
2. **Migration Rollback**: Restore previous migration state
3. **Data Recovery**: Restore from backup if needed
4. **Hotfix Strategy**: Temporary fixes while addressing root cause

## Phase 8: Success Criteria

### 8.1 Functional Requirements
- [ ] All existing functionality preserved
- [ ] Event creation from API works correctly
- [ ] Weather forecast integration functional
- [ ] Team event signup flow operational
- [ ] Admin interface fully functional

### 8.2 Technical Requirements  
- [ ] Simplified model structure achieved
- [ ] No performance regressions
- [ ] All tests passing
- [ ] Clean, maintainable code
- [ ] Proper error handling

### 8.3 Documentation Requirements
- [ ] Updated model documentation
- [ ] Updated API documentation  
- [ ] Updated admin user guides
- [ ] Migration notes documented

This comprehensive plan provides a roadmap for successfully merging the RaceWeek and Event models while maintaining all existing functionality and improving the overall architecture. 