# Development Scripts

This directory contains scripts for development and testing. **These scripts should NOT be included in production builds.**

## Available Scripts

### `seed_dev_data.py`
Seeds the database with comprehensive development/testing data.

**Usage:**
```bash
# Using the standalone script
python scripts/seed_dev_data.py

# Clear existing data and reseed
python scripts/seed_dev_data.py --clear

# Using Django management command directly
just manage seed_dev_data
just manage seed_dev_data --clear
```

**What it creates:**
- **Users**: 8 test users including an admin user
  - Admin: `admin_user` / `password123`
  - Regular users: `john_doe`, `jane_smith`, `mike_wilson`, etc.
- **Simulator**: iRacing simulator with full configuration
- **Cars**: 10+ car models across multiple classes (GT3, GTE, LMP2, Formula, NASCAR)
- **Tracks**: 8 famous racing circuits with layouts and pit data
- **Events**: 8 racing events with series, classes, and instances
- **Clubs**: 4 racing clubs with different configurations
- **Teams**: 2-3 teams per club with assigned members
- **Club Events**: Club-specific events linked to racing events
- **Event Signups**: Member signups for club events

**Generated Data Structure:**
```
Users (8)
├── SimProfiles (1 per user for iRacing)
└── ClubMembers (assigned to clubs)

Simulator (iRacing)
├── CarClasses (6) → CarModels (10) → SimCars (10)
├── TrackModels (8) → SimTracks (8) → SimLayouts (8)
└── Events (8)
    ├── EventClasses (1-2 per event)
    ├── EventInstances (3 per event: practice, qualifying, race)
    └── WeatherForecasts (every 15 minutes during events)

Clubs (4)
├── ClubMembers (3-6 per club)
├── Teams (2-3 per club)
│   └── TeamMembers (2-4 per team)
├── ClubEvents (2-3 per club)
└── EventSignups (6-12 per club event)
```

## Security Notes

⚠️ **Important**: 
- All test users have the simple password: `password123`
- The admin user has superuser privileges
- This is for development/testing only - never use in production

## Production Exclusion

To exclude these scripts from production builds, ensure your Dockerfile and deployment scripts ignore the `scripts/` directory:

```dockerfile
# In Dockerfile
COPY --exclude=scripts/ . /app/
```

Or add to `.dockerignore`:
```
scripts/
``` 