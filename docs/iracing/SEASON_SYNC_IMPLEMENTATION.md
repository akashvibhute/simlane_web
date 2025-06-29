# iRacing Season Synchronization Implementation

_Last updated: 2025-01-28_

## Overview

This document describes the implementation of iRacing season synchronization, which extends the existing series sync functionality to include current, future, and past seasons with their associated events and schedules.

## Strategy Summary

### Approach: Extended Management Command
We chose to **extend the existing `sync_iracing_series` command** rather than create a separate command because:

1. **Consistency**: Follows the established pattern in the codebase
2. **Efficiency**: Leverages existing infrastructure and processing logic
3. **Flexibility**: Allows granular control over what gets synced
4. **Maintainability**: Single command to manage all iRacing data synchronization

### Key Components

1. **Enhanced Management Command**: `sync_iracing_series` with new season sync options
2. **Celery Tasks**: Async processing for individual series seasons
3. **Scheduled Execution**: Automated runs via Celery Beat
4. **Caching Strategy**: Optimized API calls with cache bypass options

## Implementation Details

### 1. Enhanced Management Command

The `sync_iracing_series` command now supports these additional arguments:

```bash
# Basic series sync (existing functionality)
just manage sync_iracing_series

# Sync current and future seasons
just manage sync_iracing_series --sync-seasons

# Sync current, future, AND past seasons
just manage sync_iracing_series --sync-seasons --sync-past-seasons

# Sync specific year/quarter
just manage sync_iracing_series --sync-seasons --season-year 2025 --season-quarter 1

# Force refresh (bypass cache)
just manage sync_iracing_series --sync-seasons --refresh

# Dry run (no database writes)
just manage sync_iracing_series --sync-seasons --dry-run
```

### 2. Celery Tasks

Two new Celery tasks handle the async processing:

#### `sync_series_seasons_task(series_id, season_year=None, season_quarter=None, refresh=False)`
- Processes current and future seasons for a specific series
- Filters by year/quarter if specified
- Uses existing `_process_series_seasons` function

#### `sync_past_seasons_task(series_id, refresh=False)`
- Processes past seasons for a specific series
- Fetches individual season schedules using `get_series_season_schedule` (calls iRacing API `series_season_schedule`)
- Converts past season data to the format expected by `_process_series_seasons`

#### `sync_iracing_series_task(sync_seasons=False, sync_past_seasons=False, ...)`
- Wrapper task for periodic execution
- Calls the management command with appropriate parameters
- Used by Celery Beat schedules

### 3. API Methods

Added `get_series_season_schedule(season_id)` to `IRacingAPIService` (calls iRacing API `series_season_schedule`):
- Fetches full schedule for a specific past season
- Returns track layouts, race details, and weather information
- Used by past seasons sync task

### 4. Scheduled Execution

Automated schedules are managed via Celery Beat:

#### Current Seasons Sync
- **Frequency**: Tuesday, Wednesday, Friday at 6 AM UTC
- **Purpose**: Keep current and future seasons up to date
- **Task**: `sync_iracing_series_task` with `sync_seasons=True`

#### Past Seasons Sync
- **Frequency**: Quarterly (1st of Jan, Apr, Jul, Oct at 7 AM UTC)
- **Purpose**: Historical data for analysis and reference
- **Task**: `sync_iracing_series_task` with `sync_seasons=True, sync_past_seasons=True`

## Usage Examples

### Development Testing

```bash
# Test current seasons sync for a few series
just manage sync_iracing_series --sync-seasons --limit 5 --dry-run

# Test past seasons sync for a specific series
just manage sync_iracing_series --sync-seasons --sync-past-seasons --limit 1

# Test specific season
just manage sync_iracing_series --sync-seasons --season-year 2024 --season-quarter 4
```

### Production Setup

```bash
# Set up automated schedules
just manage setup_iracing_sync_schedules

# Manual full sync (if needed)
just manage sync_iracing_series --sync-seasons --sync-past-seasons

# Force refresh (bypass cache)
just manage sync_iracing_series --sync-seasons --refresh
```

### Monitoring

```bash
# Check scheduled tasks
just manage shell
>>> from django_celery_beat.models import PeriodicTask
>>> PeriodicTask.objects.filter(name__icontains="iRacing")

# View task results in Flower
# http://localhost:5555 (if running locally)
```

## Data Flow

### Current/Future Seasons
1. `sync_iracing_series` command fetches all series
2. **Single task** `sync_series_seasons_task` is queued for all series
3. Task calls `get_series_seasons()` (single API call returns all series data)
4. Processes all seasons using `_process_series_seasons`
5. Creates/updates `Season` and `Event` records for all series

### Past Seasons
1. `sync_iracing_series` command fetches all series
2. **Individual tasks** `sync_past_seasons_task` are queued for each series
3. Each task calls `get_series_past_seasons(series_id)`
4. For each past season, calls `get_series_season_schedule(season_id)` (iRacing API `series_season_schedule`)
5. Converts data and processes using `_process_series_seasons`
6. Creates/updates `Season` and `Event` records

## Caching Strategy

- **Development**: 24-hour cache TTL for API responses
- **Production**: Configurable TTL with `--refresh` bypass option
- **Cache Keys**:
  - `iracing:series:{series_id}:seasons`
  - `iracing:series:{series_id}:past_seasons`
  - `iracing:season:{season_id}:schedule`

## Error Handling

- **Retry Logic**: Tasks retry up to 3 times with 60-second delays
- **Graceful Degradation**: Individual series failures don't stop the entire sync
- **Logging**: Comprehensive logging for debugging and monitoring
- **Idempotency**: Safe to re-run without creating duplicates

## Performance Optimizations

### API Call Efficiency
- **Current seasons**: Single API call (`get_series_seasons()`) returns data for all series
- **Past seasons**: Individual API calls per series (required by iRacing API design)
- **Series metadata**: Single API call (`get_series()`) for all series

### Task Queuing Strategy
- **Current seasons**: One task processes all series (efficient)
- **Past seasons**: Individual tasks per series (necessary for API design)
- **Error isolation**: Individual series failures don't affect others

## Monitoring and Maintenance

### Health Checks
- Monitor task success/failure rates
- Track API response times
- Watch for rate limit violations

### Maintenance Tasks
- Periodic cache cleanup
- Database optimization
- Log rotation and cleanup

### Troubleshooting
- Check Celery worker logs for task failures
- Verify iRacing API credentials
- Monitor database connection pool usage

## Future Enhancements

### Potential Improvements
1. **Incremental Updates**: Track last sync time to avoid reprocessing unchanged data
2. **Parallel Processing**: Process multiple series concurrently (with rate limiting)
3. **Smart Caching**: Cache invalidation based on data freshness
4. **Webhook Integration**: Real-time updates when iRacing data changes
5. **Analytics Dashboard**: Visual monitoring of sync performance

### API Optimizations
1. **Bulk Operations**: Batch API calls where possible
2. **Delta Sync**: Only fetch changed data
3. **Compression**: Reduce bandwidth usage
4. **Connection Pooling**: Optimize HTTP connections

## Conclusion

This implementation provides a robust, scalable solution for iRacing season synchronization that:

- ✅ Minimizes API calls through intelligent caching
- ✅ Provides flexible scheduling options
- ✅ Handles errors gracefully with retry logic
- ✅ Maintains data consistency through idempotent operations
- ✅ Scales from development to production environments
- ✅ Integrates seamlessly with existing infrastructure

The solution follows Django best practices and leverages the existing Celery infrastructure for reliable background processing. 