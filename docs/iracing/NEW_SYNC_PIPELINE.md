# iRacing Sync Pipeline Refactor

## Overview

The iRacing sync pipeline has been completely refactored to address the issues with the previous interconnected and duplicating system. The new implementation provides a cleaner, more modular approach with separated concerns.

## What Was Wrong Before

1. **Interconnected Logic**: Series, seasons, and events were all processed in a single monolithic function
2. **Duplicates Creation**: The tightly coupled logic was creating duplicate events and handling recurrence poorly
3. **Poor Recurrence Handling**: Time slots were being created for every possible recurrence, leading to database bloat
4. **Difficult Maintenance**: Changes to one part of the sync affected everything else

## New Architecture

### Separated Concerns

The new system separates sync responsibilities into distinct, focused modules:

1. **Series Sync** (`sync_series_task`): Only handles series data (names, licenses, basic info)
2. **Season Sync** (`sync_season_task`): Accepts a season ID, creates season, processes schedule
3. **Schedule Processing** (`ScheduleProcessor`): Handles event creation, car restrictions, and recurrence patterns
4. **Recurrence Handler** (`RecurrenceHandler`): Dynamically generates time slots for display without creating DB records

### Key Files

- `simlane/iracing/tasks.py` - Main Celery tasks (replaces old tasks.py)
- `simlane/iracing/season_sync.py` - Schedule processing logic
- `simlane/iracing/admin_sync.py` - Django admin interface for triggering syncs
- `simlane/iracing/tasks_old.py` - Backup of old implementation

## New Task Structure

### Core Tasks

#### 1. `sync_series_task(refresh=False)`
- Fetches all iRacing series
- Creates/updates Series records with basic data only
- No seasons or events processing
- Fast and lightweight

#### 2. `sync_season_task(season_id, refresh=False)`
- Accepts a specific season ID
- Fetches season schedule from iRacing API
- Creates Season record if it doesn't exist
- Processes schedule to create events
- Handles car restrictions and classes
- Processes time patterns

#### 3. `sync_current_seasons_task(refresh=False)`
- Uses series_seasons API for current/future seasons
- Processes all current seasons across all series
- Calls season processing for each season found
- Efficient bulk operation for current data

#### 4. `sync_past_seasons_for_series_task(series_id, refresh=False)`
- Gets past seasons for a specific series
- Queues individual `sync_season_task` for each past season
- Avoids overwhelming the system with too many concurrent tasks

#### 5. `queue_all_past_seasons_sync_task(refresh=False)`
- Queues past season sync for all series
- Used for complete historical data sync
- **Use with caution** - can create many background tasks

#### 6. `sync_car_classes_task(refresh=False)`
- Syncs car class definitions
- Independent of series/seasons
- Working properly from before

### Supporting Classes

#### ScheduleProcessor
Handles the complex logic of processing season schedules:
- Creates/updates Event records
- Processes car restrictions (BOP)
- Handles car classes
- Manages time patterns and recurrence

#### RecurrenceHandler
Provides dynamic time slot generation:
- Generates time slots for display without creating DB records
- Handles repeating patterns (every 2 hours, etc.)
- Calculates upcoming races for UI display
- Supports complex recurrence patterns from iRacing

## Recurrence Pattern Handling

### Two Types of Patterns

1. **Repeating Patterns** (e.g., every 2 hours, every 30 minutes)
   - Stored in `Event.time_pattern` field
   - No TimeSlot records created
   - Generated dynamically when needed for display
   - Prevents database bloat

2. **Specific Times** (e.g., special events with fixed times)
   - Creates actual TimeSlot records
   - Used for non-repeating, scheduled events
   - TODO: Implementation needed when examples are found

### Benefits
- Dramatically reduces database size
- Faster queries and better performance
- Easy to calculate "next race" times
- Supports complex recurrence patterns

## Django Admin Integration

### Sync Dashboard
New admin interface provides easy access to sync operations:

- **Sync Series**: Update all series data
- **Sync Current Seasons**: Update current/future seasons and events
- **Sync Car Classes**: Update car class definitions
- **Sync Past Seasons**: Queue historical season sync (use carefully)

### Admin Actions
- Bulk sync selected seasons from Season admin
- Queue past seasons sync for selected series from Series admin

### Access
Available at: `/admin/` → Look for iRacing sync options

## Migration Strategy

### What's Working
- ✅ Car classes sync
- ✅ Car and track data sync
- ✅ Series data sync
- ✅ Track SVG image gallery (verify)

### What's New
- ✅ Separated season sync by season_id
- ✅ Modular schedule processing
- ✅ Smart recurrence handling
- ✅ Admin interface for manual triggers
- ✅ Better error handling and logging

### Old Files
- `tasks_old.py` - Backup of old implementation
- Can be removed after testing confirms new system works

## Usage Examples

### Manual Sync from Code
```python
# Sync all series data
from simlane.iracing.tasks import sync_series_task
task = sync_series_task.delay(refresh=True)

# Sync a specific season
from simlane.iracing.tasks import sync_season_task
task = sync_season_task.delay(season_id=3742, refresh=False)

# Sync all current seasons
from simlane.iracing.tasks import sync_current_seasons_task
task = sync_current_seasons_task.delay()
```

### Dynamic Time Slot Generation
```python
from simlane.iracing.season_sync import RecurrenceHandler
from datetime import datetime, timedelta

# Generate upcoming time slots for an event
start_date = datetime.now()
end_date = start_date + timedelta(days=7)
time_slots = RecurrenceHandler.generate_time_slots_for_period(
    event, start_date, end_date
)
```

## Testing the New System

### Recommended Testing Order

1. **Sync Series** - Start with this to ensure basic series data is correct
2. **Sync Current Seasons** - Test with current/future seasons
3. **Check Event Creation** - Verify events are created properly
4. **Test Recurrence** - Check that repeating patterns work
5. **Sync Single Season** - Test individual season sync
6. **Limited Past Seasons** - Test with a few past seasons only

### Monitoring
- Check Celery logs for task execution
- Monitor database for duplicate creation
- Verify event time patterns are stored correctly
- Test dynamic time slot generation

## Benefits of New System

1. **Modular**: Each component has a single responsibility
2. **Scalable**: Can sync individual seasons without affecting others
3. **Efficient**: No more massive database bloat from time slots
4. **Maintainable**: Clear separation of concerns
5. **User-Friendly**: Admin interface for manual operations
6. **Flexible**: Easy to add new sync operations
7. **Robust**: Better error handling and recovery

## Future Improvements

1. **Implement Specific Time Patterns**: When examples are found in API data
2. **Add Progress Tracking**: UI for monitoring long-running sync operations
3. **Smart Scheduling**: Automatic scheduling of sync operations
4. **Data Validation**: Enhanced validation of synced data
5. **Conflict Resolution**: Handle API data conflicts better

## Configuration

No configuration changes required. The new system uses the same:
- iRacing API credentials
- Database models
- Celery configuration

The refactor is backward-compatible with existing data. 