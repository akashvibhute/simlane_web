# iRacing Season Sync - Quick Reference

## Quick Start

### 1. Set up automated schedules
```bash
just manage setup_iracing_sync_schedules
```

### 2. Test the sync (development)
```bash
# Test current seasons for a few series
just manage sync_iracing_series --sync-seasons --limit 5 --dry-run

# Test past seasons for one series
just manage sync_iracing_series --sync-seasons --sync-past-seasons --limit 1
```

### 3. Run full sync (production)
```bash
# Current and future seasons only
just manage sync_iracing_series --sync-seasons

# Include past seasons (quarterly task)
just manage sync_iracing_series --sync-seasons --sync-past-seasons
```

## Common Commands

### Development Testing
```bash
# Dry run with verbose logging
just manage sync_iracing_series --sync-seasons --dry-run --verbose

# Test specific season
just manage sync_iracing_series --sync-seasons --season-year 2025 --season-quarter 1

# Force refresh (bypass cache)
just manage sync_iracing_series --sync-seasons --refresh

# Limit to specific number of series
just manage sync_iracing_series --sync-seasons --limit 10
```

### Production Operations
```bash
# Manual current seasons sync
just manage sync_iracing_series --sync-seasons

# Manual past seasons sync
just manage sync_iracing_series --sync-seasons --sync-past-seasons

# Full sync with refresh
just manage sync_iracing_series --sync-seasons --sync-past-seasons --refresh
```

## Monitoring

### Check Scheduled Tasks
```bash
just manage shell
>>> from django_celery_beat.models import PeriodicTask
>>> PeriodicTask.objects.filter(name__icontains="iRacing")
```

### View Task Results
- **Flower Dashboard**: http://localhost:5555 (if running locally)
- **Celery Logs**: `just logs celeryworker`
- **Beat Logs**: `just logs celerybeat`

### Check Database
```bash
just manage shell
>>> from simlane.sim.models import Series, Season, Event
>>> Series.objects.count()
>>> Season.objects.count()
>>> Event.objects.count()
```

## Troubleshooting

### Common Issues

#### 1. "iRacing API service is not available"
```bash
# Check credentials in settings
just manage shell
>>> from simlane.iracing.services import iracing_service
>>> iracing_service.is_available()
```

#### 2. Tasks not running
```bash
# Check Celery workers
just logs celeryworker

# Check Beat scheduler
just logs celerybeat

# Restart services if needed
just down
just up
```

#### 3. Database errors
```bash
# Check migrations
just manage showmigrations

# Run migrations if needed
just manage migrate
```

#### 4. Rate limiting
```bash
# Check API call frequency
just logs celeryworker | grep "rate limit"

# Reduce sync frequency or add delays
```

### Debug Mode
```bash
# Enable verbose logging
just manage sync_iracing_series --sync-seasons --verbose

# Check specific series
just manage shell
>>> from simlane.sim.models import Series
>>> Series.objects.filter(external_series_id=123).first()
```

## Schedule Configuration

### Current Seasons Sync
- **When**: Tuesday, Wednesday, Friday at 6 AM UTC
- **What**: Current and future seasons
- **Task**: `sync_iracing_series_task` with `sync_seasons=True`

### Past Seasons Sync
- **When**: 1st of Jan, Apr, Jul, Oct at 7 AM UTC
- **What**: Historical seasons
- **Task**: `sync_iracing_series_task` with `sync_seasons=True, sync_past_seasons=True`

### Modify Schedules
```bash
# Recreate schedules
just manage setup_iracing_sync_schedules --force

# Or modify via Django admin
# http://localhost:8000/admin/django_celery_beat/periodictask/
```

## Performance Tips

### Development
- Use `--limit` to test with fewer series
- Use `--dry-run` to test without database writes
- Use `--verbose` for detailed logging

### Production
- Monitor memory usage during large syncs
- Check API rate limits
- Use `--refresh` sparingly (bypasses cache)

### Optimization
- **Current seasons**: Single API call for all series (very efficient)
- **Past seasons**: Individual API calls per series (quarterly only)
- Use cache effectively to reduce API calls

## Data Models

### Key Relationships
```
Series (external_series_id)
├── Season (external_season_id)
│   ├── Event (round_number)
│   │   ├── EventClass (car_class)
│   │   └── CarRestriction (sim_car)
│   └── TimeSlot (event_instance)
```

### Important Fields
- `Series.external_series_id`: iRacing series ID
- `Season.external_season_id`: iRacing season ID
- `Event.round_number`: Race week number
- `Event.entry_requirements`: JSON with API metadata

## API Endpoints Used

### Current/Future Seasons
- `get_series()`: All series metadata
- `get_series_seasons()`: **Single call** returns all current/future seasons with schedules

### Past Seasons
- `get_series_past_seasons(series_id)`: List of past seasons (per series)
- `get_series_season_schedule(season_id)`: Full schedule for past season (calls iRacing API `series_season_schedule`)

## Cache Keys
- `iracing:series:{series_id}:seasons`
- `iracing:series:{series_id}:past_seasons`
- `iracing:season:{season_id}:schedule`

## Log Files
- **Celery Worker**: `logs/celeryworker.log`
- **Celery Beat**: `logs/celerybeat.log`
- **Django**: `logs/django.log`
- **iRacing Service**: `logs/iracing.log` 