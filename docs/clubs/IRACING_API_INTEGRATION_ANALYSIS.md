# iRacing API Integration & Model Analysis

## Overview
Comprehensive analysis of the iRacing API integration in SimLane, including all endpoints, data flows, model creation, and identified gaps. This document covers both the completed car/class restrictions enhancements and the broader API integration architecture.

## Current API Integration Architecture

### 1. iRacing API Client Structure

**Base Client**: `IRacingAPIClient` (extends `irDataClient`)
- **Session Management**: Persistent system session caching (24-hour cache)
- **Authentication**: System account only (Phase 1)
- **Cache Key**: `'iracing_session_system'`
- **Location**: `simlane/iracing/iracing_api_client.py`

**Service Layer**: `IRacingAPIService`
- **Error Handling**: Custom `IRacingServiceError` exceptions
- **Rate Limiting**: Built into underlying client
- **Location**: `simlane/iracing/services.py`

**Task Layer**: Celery background tasks
- **Retry Logic**: 3 retries with 60-second delay
- **Error Handling**: Comprehensive logging and error responses
- **Location**: `simlane/iracing/tasks.py`

## 2. Complete API Endpoint Mapping

### A. Core Data APIs (Static/Reference Data)

#### **Cars API**
- **Endpoint**: `client.cars`
- **Service Method**: `get_cars()`
- **Task**: `fetch_cars_data()`
- **Data Structure**:
```json
{
  "car_id": 132,
  "car_name": "Mercedes-AMG GT3 2020",
  "car_name_abbreviated": "AMG20",
  "car_make": "Mercedes-Benz",
  "car_model": "AMG GT3",
  "package_id": 123,
  "price": 11.95,
  "car_types": [{"car_type": "gt3"}, {"car_type": "road"}],
  "horsepower": 550,
  "weight": 2866,
  "has_headlights": true,
  "rain_enabled": true
}
```
- **Models Created**: `CarModel`, `SimCar`
- **Status**: ✅ **IMPLEMENTED**

#### **Tracks API**
- **Endpoint**: `client.tracks`
- **Service Method**: `get_tracks()`
- **Task**: `fetch_tracks_data()`
- **Data Structure**:
```json
{
  "track_id": 510,
  "track_name": "Algarve International Circuit",
  "config_name": "Grand Prix - Chicanes",
  "package_id": 456,
  "price": 14.95,
  "category": "road",
  "is_laser_scanned": true
}
```
- **Models Created**: `TrackModel`, `SimTrack`, `SimLayout`
- **Status**: ✅ **IMPLEMENTED**

#### **Series API**
- **Endpoint**: `client.get_series()`
- **Service Method**: `get_series()`
- **Task**: `fetch_series_data()`
- **Data Structure**:
```json
{
  "series_id": 280,
  "series_name": "GT3 Challenge",
  "category": "road",
  "license_group": 4,
  "multiclass": false,
  "fixed_setup": true,
  "car_class_ids": [2708]
}
```
- **Models Created**: `Series`
- **Status**: ✅ **IMPLEMENTED**

#### **Car Classes API**
- **Endpoint**: `client.get_carclasses()`
- **Service Method**: `get_car_classes()`
- **Task**: Not implemented as task
- **Data Structure**:
```json
{
  "car_class_id": 2708,
  "name": "GT3 Class",
  "short_name": "GT3 Class",
  "cars_in_class": [
    {"car_id": 156, "car_dirpath": "mercedesamgevogt3"},
    {"car_id": 188, "car_dirpath": "mclaren720sgt3"}
  ],
  "relative_speed": 52,
  "rain_enabled": true
}
```
- **Models Created**: `CarClass`
- **Status**: ✅ **IMPLEMENTED** (enhanced with simulator-specific fields)

### B. Season & Schedule APIs

#### **Series Seasons API**
- **Endpoint**: `client.series_seasons(include_series=True)`
- **Service Method**: `get_series_seasons()`
- **Task**: `fetch_series_seasons()`
- **Data Structure**:
```json
{
  "series_id": 280,
  "season_id": 5621,
  "season_name": "GT3 Challenge - 2025 Season 2",
  "active": true,
  "car_class_ids": [2708],
  "multiclass": false,
  "schedules": [
    {
      "race_week_num": 3,
      "track": {
        "track_id": 510,
        "track_name": "Algarve International Circuit",
        "config_name": "Grand Prix - Chicanes"
      },
      "car_restrictions": [
        {
          "car_id": 132,
          "max_dry_tire_sets": 0,
          "max_pct_fuel_fill": 50,
          "power_adjust_pct": -1.75,
          "weight_penalty_kg": 5,
          "race_setup_id": 265755,
          "qual_setup_id": 263880
        }
      ],
      "weather": {
        "weather_url": "https://scorpio-assets.s3.amazonaws.com/...",
        "forecast_options": {...},
        "weather_summary": {...}
      }
    }
  ]
}
```
- **Models Created**: `Series`, `Season`, `RaceWeek`, `Event`, `EventClass`, `CarRestriction`
- **Status**: ✅ **IMPLEMENTED** (with EventClass creation)

#### **Season Race Guide API**
- **Endpoint**: `client.season_race_guide()`
- **Service Method**: `get_season_race_guide()`
- **Task**: `fetch_season_race_guide()`
- **Data Structure**:
```json
{
  "sessions": [
    {
      "session_id": 278507891,
      "series_id": 554,
      "session_name": "Practice",
      "start_time": "2025-06-28T11:30:00Z",
      "series_name": "Formula Vee",
      "track": {
        "track_name": "Lime Rock Park",
        "config_name": "Grand Prix"
      }
    }
  ]
}
```
- **Models Created**: `Event` (basic events without track/layout info)
- **Status**: ⚠️ **PARTIALLY IMPLEMENTED** (missing `sim_layout` constraint issue)

#### **Season List API**
- **Endpoint**: `client.season_list()`
- **Service Method**: `get_season_list()`
- **Task**: `fetch_season_list()`
- **Status**: ✅ **IMPLEMENTED** (task only, no model creation)

### C. Results & Event APIs

#### **Subsession Data API**
- **Endpoint**: `client.subsession_data(subsession_id)`
- **Service Method**: `get_subsession_data()`
- **Task**: `fetch_subsession_data()`, `sync_subsession_results_task()`
- **Data Structure**:
```json
{
  "subsession_id": 12345,
  "session_id": 67890,
  "start_time": "2025-06-28T15:00:00Z",
  "end_time": "2025-06-28T16:00:00Z",
  "num_drivers": 24,
  "weather": {...},
  "session_results": [
    {
      "cust_id": 123456,
      "display_name": "John Doe",
      "finish_position": 1,
      "car_id": 132,
      "incidents": 2,
      "best_lap_time": 85432
    }
  ]
}
```
- **Models Created**: `EventResult`, `ParticipantResult`, `TeamResult`
- **Status**: ✅ **IMPLEMENTED**

#### **Season Results API**
- **Endpoint**: `client.season_results()`
- **Service Method**: `season_results()`
- **Task**: `match_season_results_to_instances_task()`
- **Status**: ✅ **IMPLEMENTED**

#### **Series Search Results API**
- **Endpoint**: `client.result_search_series()`
- **Service Method**: `search_series_results()`
- **Task**: `fetch_series_search_results()`
- **Status**: ✅ **IMPLEMENTED** (task only)

### D. Member/Profile APIs

#### **Member Summary API**
- **Endpoint**: `client.stats_member_summary()`
- **Service Method**: `get_member_summary()`
- **Task**: `fetch_member_summary()`
- **Status**: ✅ **IMPLEMENTED** (no model creation)

#### **Member Recent Races API**
- **Endpoint**: `client.stats_member_recent_races()`
- **Service Method**: `get_member_recent_races()`
- **Task**: `fetch_member_recent_races()`, `process_member_recent_races_task()`
- **Status**: ✅ **IMPLEMENTED**

#### **Member Info API**
- **Endpoint**: `client.member_info()`
- **Service Method**: `get_member_info()`
- **Task**: `sync_iracing_owned_content()`
- **Data Structure**:
```json
{
  "cust_id": 123456,
  "display_name": "John Doe",
  "owned_cars": [132, 156, 188],
  "owned_tracks": [510, 245, 123]
}
```
- **Models Created**: `SimProfile`, `SimProfileCarOwnership`, `SimProfileTrackOwnership`
- **Status**: ✅ **IMPLEMENTED**

#### **Lap Data API**
- **Endpoint**: `client.result_lap_data()`
- **Service Method**: `get_result_lap_data()`
- **Task**: Not implemented as task
- **Status**: ⏳ **API AVAILABLE** (not used in model creation)

### E. Constants APIs

#### **Event Types API**
- **Endpoint**: `client.constants_event_types()`
- **Service Method**: `get_constants_event_types()`
- **Status**: ✅ **IMPLEMENTED** (no model creation)

## 3. Data Flow Analysis

### Primary Import Flows

#### **Flow 1: Static Data Import**
```
Cars API → CarModel + SimCar
Tracks API → TrackModel + SimTrack + SimLayout  
Series API → Series
Car Classes API → CarClass
```

#### **Flow 2: Season Data Import**
```
Series Seasons API → Series Update → Season Creation → RaceWeek Creation → Event Creation → EventClass Creation
                                                    → CarRestriction Creation
                                                    → Weather URL Storage
```

#### **Flow 3: Event Results Import**
```
Subsession Data API → EventResult Creation → ParticipantResult Creation
                                          → TeamResult Creation
                   → Auto Event Chain Creation → Series/Season/RaceWeek/Event/EventInstance
```

#### **Flow 4: Member Data Import**
```
Member Info API → SimProfile Creation → SimProfileCarOwnership
                                     → SimProfileTrackOwnership
Member Recent Races API → Results Processing
```

## 4. Implementation Status & Gaps

### ✅ **COMPLETED IMPLEMENTATIONS**

#### **Car/Class Restrictions Enhancement** (Phase 1)
- ✅ Enhanced `CarClass` model with simulator-specific fields
- ✅ Enhanced `Series` model with `allowed_car_class_ids` array
- ✅ Enhanced `EventClass` model with multi-class fields (removed redundant `allowed_sim_car_ids`)
- ✅ Enhanced `CarRestriction` model with BOP fields
- ✅ EventClass creation logic in series import
- ✅ Admin interface enhancements

#### **Core API Integration**
- ✅ All static data APIs (cars, tracks, series, car classes)
- ✅ Series seasons import with complete model creation
- ✅ Results processing with auto event chain creation
- ✅ Member profile and ownership tracking

### ⚠️ **PARTIAL IMPLEMENTATIONS**

#### **Race Guide Events**
- ⚠️ **Issue**: Events created without required `sim_layout` constraint
- **Root Cause**: Race guide data lacks track configuration details
- **Impact**: Database constraint violations
- **Solution Needed**: Either make `sim_layout` nullable for race guide events or skip creation

#### **Weather Forecast Processing & Track-State Mapping**
- ⚠️ **Issue**: Weather URLs stored but not processed
- **Current State**: `weather_forecast_url` stored in `RaceWeek`
- **Missing**: Actual fetching and `WeatherForecast` model population
- **Implementation**: `fetch_and_cache_weather_forecast()` exists but not fully integrated
- ✅ **Completed**: Weather URLs are now fetched asynchronously via the new `update_weather_forecast_task` Celery task.
  - Full JSON cached in `RaceWeek.weather_forecast_data`
  - Summary metrics (`min_air_temp`, `max_air_temp`, `max_precip_chance`) populated for fast lookup
  - Forecast refresh is queued only when data is missing or stale
- ✅ **Track-State**: `track_state` from the schedule API is now stored directly in `RaceWeek.track_state`.
- 🔄 **Next**: Expose this data via API & UI components (see Phase 2 below)

### ❌ **IDENTIFIED GAPS**

#### **Weather Forecast Processing & Track-State Mapping**
- ✅ **Completed**: Weather URLs are now fetched asynchronously via the new `update_weather_forecast_task` Celery task.
  - Full JSON cached in `RaceWeek.weather_forecast_data`
  - Summary metrics (`min_air_temp`, `max_air_temp`, `max_precip_chance`) populated for fast lookup
  - Forecast refresh is queued only when data is missing or stale
- ✅ **Track-State**: `track_state` from the schedule API is now stored directly in `RaceWeek.track_state`.
- 🔄 **Next**: Expose this data via API & UI components (see Phase 2 below)

## 5. Enhanced Model Relationships

### Current Model Structure
```
Series (1) --> (N) Season (1) --> (N) RaceWeek (1) --> (N) Event
                                                     |
CarClass (1) --> (N) EventClass (N) <-- (1) Event
                                     |
                          CarRestriction (N) <-- (1) RaceWeek
                                     |
                              SimCar (1)
```

### Data Population Flow
1. **Static Data**: Cars, Tracks, Series, CarClasses imported first
2. **Season Data**: Series Seasons API creates Season → RaceWeek → Event → EventClass chain
3. **Restrictions**: CarRestriction records created per RaceWeek per Car
4. **Weather**: URLs stored, forecasts should be fetched separately
5. **Results**: Subsession data creates EventResult → ParticipantResult/TeamResult

## 6. Priority Implementation Plan

### **Phase 1: Critical Gaps (High Priority)**
1. **Fix Race Guide Events** - Resolve `sim_layout` constraint
2. **Event Instance Generation** - Create recurring instances from time patterns
3. **Multi-Class Event Logic** - Complete business logic for multi-class events

### **Phase 2: Weather UI & Alerts (Medium Priority)**
4. **Weather-Based UI Components** – Charts, badges, alerts using the cached data
5. **Forecast Refresh Schedule** – Nightly Celery-beat job to keep forecasts up-to-date

### **Phase 3: Enhancements (Low Priority)**
6. **Car Class Import Task** - Background task for car class updates
7. **Setup Restrictions Enhancement** - Store specific setup IDs
8. **Advanced BOP Features** - Historical BOP tracking, conflict detection

## 7. API Response Samples

### Series Seasons API Response (Partial)
```json
{
  "series_id": 280,
  "season_id": 5621,
  "season_name": "GT3 Challenge - 2025 Season 2",
  "series_name": "GT3 Challenge",
  "active": true,
  "official": true,
  "license_group": 4,
  "fixed_setup": false,
  "car_class_ids": [2708],
  "multiclass": false,
  "schedules": [
    {
      "race_week_num": 3,
      "season_id": 5621,
      "series_id": 280,
      "start_date": "2025-07-07T12:00:00Z",
      "end_date": "2025-07-14T12:00:00Z",
      "track": {
        "track_id": 510,
        "track_name": "Algarve International Circuit",
        "config_name": "Grand Prix - Chicanes",
        "category": "road"
      },
      "car_restrictions": [
        {
          "car_id": 132,
          "max_dry_tire_sets": 0,
          "max_pct_fuel_fill": 50,
          "power_adjust_pct": -1.75,
          "weight_penalty_kg": 5,
          "race_setup_id": 265755,
          "qual_setup_id": 263880
        }
      ],
      "race_time_descriptors": {
        "first_session_time": "00:45:00",
        "repeat_minutes": 120,
        "super_speedway_no_qual": false
      },
      "weather": {
        "weather_url": "https://scorpio-assets.s3.amazonaws.com/members/messaging-services/non_expiring/weather-forecast/season/5621/rw3_evt5.json",
        "forecast_options": {
          "forecast_type": 1,
          "precipitation": 1,
          "temperature": 0,
          "wind_speed": 0
        },
        "weather_summary": {
          "temp_high": 24.2,
          "temp_low": 23.1,
          "wind_high": 18.2,
          "wind_low": 17.5,
          "precip_chance": 0
        }
      }
    }
  ]
}
```

### Weather Forecast API Response (from weather_url)
```json
[
  {
    "time_offset": 0,
    "timestamp": "2025-07-12T12:00:00Z",
    "is_sun_up": true,
    "affects_session": true,
    "air_temp": 2420,
    "pressure": 10132,
    "wind_speed": 1750,
    "wind_dir": 7,
    "precip_chance": 0,
    "precip_amount": 0,
    "allow_precip": false,
    "cloud_cover": 10,
    "rel_humidity": 4800,
    "valid_stats": true
  }
]
```

## 8. Technical Debt & Optimization Opportunities

### **Performance Optimizations**
1. **Bulk Operations**: Use `bulk_create()` for large data imports
2. **Database Indexing**: Add indexes for frequently queried fields
3. **API Rate Limiting**: Implement intelligent rate limiting
4. **Caching**: Cache frequently accessed static data

### **Code Quality Improvements**
1. **Error Handling**: Standardize error handling across all tasks
2. **Validation**: Add comprehensive data validation
3. **Documentation**: API endpoint documentation
4. **Testing**: Unit tests for all import functions

### **Monitoring & Observability**
1. **Import Metrics**: Track import success/failure rates
2. **Data Quality**: Monitor data consistency and completeness
3. **Performance Monitoring**: Track API response times
4. **Alerting**: Alert on import failures or data anomalies

This comprehensive analysis provides a complete picture of the current iRacing API integration, implemented features, and remaining gaps that need to be addressed for a fully functional system. 