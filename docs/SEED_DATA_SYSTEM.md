# Seed Data System

This document explains the seed data system in SimLane, which ensures that essential data is always available in the database.

## Overview

The seed data system consists of two types of data:

1. **Base Seed Data** - Essential data that should always be present (simulators, tracks, cars)
2. **Development Seed Data** - Test data for development and testing

## Base Seed Data

Base seed data is automatically created through Django migrations and includes:

### Simulators
- iRacing simulator with proper configuration

### iRacing Content (from API)
- All available cars with proper categorization
- All available tracks with all configurations/layouts
- Proper relationships between models (CarModel → SimCar, TrackModel → SimTrack → SimLayout)

**Important**: The iRacing API returns track configurations as individual entries, not nested structures. Each API response item represents a track layout with fields like `track_name`, `config_name`, and `track_id`. The system groups these by `track_name` to create the proper model hierarchy.

## Management Commands

### `create_base_seed_data`

Creates essential seed data that should always be present in the system.

```bash
just manage create_base_seed_data
```

**Options:**
- `--skip-iracing`: Skip iRacing API data fetching (useful when API is unavailable)
- `--force-update`: Force update existing data from API

**What it does:**
1. Creates the iRacing simulator entry
2. Fetches cars from iRacing API and creates:
   - CarClass entries based on car categories
   - CarModel entries with specifications
   - SimCar entries linking to iRacing API IDs
3. Fetches tracks from iRacing API and creates:
   - TrackModel entries for each track
   - SimTrack entries linking to iRacing API IDs
   - SimLayout entries for each track configuration

### `seed_dev_data`

Creates development/testing data including users, clubs, events, etc.

```bash
just manage seed_dev_data
```

This command now automatically calls `create_base_seed_data` first to ensure the foundation exists.

## Automatic Migration

Base seed data is automatically created through a Django data migration:
- `simlane/core/migrations/0002_create_base_seed_data.py`

This ensures that whenever you:
- Create a fresh database
- Run migrations on a new environment
- Reset your development database

The essential simulator and iRacing data will be automatically populated.

## API Integration

The system uses the iRacing API to fetch real-time data about:

### Cars
- Car names and manufacturers
- Categories and specifications (HP, weight, etc.)
- Car images/logos
- API IDs for linking

### Tracks
- Track names and locations
- Track configurations and layouts
- Track lengths and types (Road, Oval, etc.)
- Laser scan information
- Track images/logos

## Data Structure

The seed data creates a proper hierarchy:

```
Simulator (iRacing)
├── SimCar (links to CarModel via API ID)
│   └── CarModel (with specifications)
│       └── CarClass (categorization)
└── SimTrack (links to TrackModel via API ID)
    └── TrackModel (basic track info)
        └── SimLayout (specific configurations)
```

## Error Handling

- If iRacing API is unavailable during migration, the system gracefully skips API data but still creates the simulator entry
- The `--skip-iracing` flag allows manual skipping of API calls
- Individual car/track processing errors don't stop the entire process
- Existing data is preserved unless `--force-update` is used

## Development Workflow

1. **Fresh Setup:** Run `just manage migrate` - base seed data is created automatically
2. **Add Test Data:** Run `just manage seed_dev_data` for development data
3. **Update API Data:** Run `just manage create_base_seed_data --force-update` to refresh from iRacing API
4. **API Unavailable:** Use `--skip-iracing` flag when the API is down

## Configuration

iRacing API credentials are configured in settings:
- `IRACING_USERNAME`
- `IRACING_PASSWORD`

If these are not configured, the API integration will be skipped automatically.

## Benefits

1. **Consistency:** Every development environment has the same base data
2. **Automation:** No manual setup required for basic functionality
3. **Real Data:** Uses actual iRacing data for realistic development
4. **Flexibility:** Can skip API calls when needed
5. **Safety:** Doesn't overwrite existing data unless explicitly requested 