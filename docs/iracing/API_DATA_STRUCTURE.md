# iRacing API Data Structure Analysis

## Overview
This document tracks the structure of iRacing API responses and our model design decisions for storing race results data.

## Sample Data Sources
- **Subsession ID**: 77539725
- **Session ID**: 276891443
- **Event**: Formula C - Super Formula Lights by Ready Set Sim
- **Track**: Circuit de Spa-Francorchamps - Classic Pits
- **Date**: 2025-06-06

## API Response Structure

### Top-Level Response Structure
```json
{
  "subsession_id": 77539725,
  "session_id": 276891443,
  "series_id": 551,
  "season_id": 5442,
  "event_strength_of_field": 1235,
  "num_drivers": 26,
  "event_best_lap_time": 1291303,
  "event_average_lap": 1308060,
  "start_time": "2025-06-06T12:45:00Z",
  "end_time": "2025-06-06T13:31:53Z",
  "session_results": [...],
  "track": {...},
  "weather": {...},
  "car_classes": [...],
  "allowed_licenses": [...]
}
```

### Key Top-Level Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `subsession_id` | int | Unique race identifier | 77539725 |
| `session_id` | int | Session identifier | 276891443 |
| `series_id` | int | Series identifier | 551 |
| `season_id` | int | Season identifier | 5442 |
| `event_strength_of_field` | int | Overall field strength rating | 1235 |
| `num_drivers` | int | Number of participants | 26 |
| `event_best_lap_time` | int | Best lap time (milliseconds) | 1291303 |
| `event_average_lap` | int | Average lap time (milliseconds) | 1308060 |
| `start_time` | string | Race start time (ISO) | "2025-06-06T12:45:00Z" |
| `end_time` | string | Race end time (ISO) | "2025-06-06T13:31:53Z" |
| `num_cautions` | int | Number of caution periods | 0 |
| `num_caution_laps` | int | Laps under caution | 0 |
| `num_lead_changes` | int | Number of lead changes | 0 |

### Session Results Structure
The `session_results` array contains different session types (Practice, Qualify, Race). The race results are typically in `session_results[0].results`.

### Participant Result Structure
Each participant has detailed performance data:

```json
{
  "cust_id": 1106339,
  "display_name": "Akash Vibhute",
  "finish_position": 22,
  "starting_position": 2,
  "laps_complete": 5,
  "incidents": 8,
  "best_lap_time": 1326566,
  "average_lap": 1510496,
  "champ_points": 9,
  "oldi_rating": 1546,
  "newi_rating": 1459,
  "old_license_level": 10,
  "new_license_level": 10,
  "reason_out": "Disconnected",
  "reason_out_id": 32,
  "car_id": 178,
  "car_class_id": 4049,
  "car_class_name": "Super Formula Lights",
  "country_code": "GB",
  "division": 4,
  "drop_race": false
}
```

### Key Participant Fields

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `cust_id` | int | iRacing customer ID | 1106339 |
| `display_name` | string | Driver display name | "Akash Vibhute" |
| `finish_position` | int | Final race position | 22 |
| `starting_position` | int | Starting grid position | 2 |
| `laps_complete` | int | Number of laps completed | 5 |
| `incidents` | int | Number of incidents | 8 |
| `best_lap_time` | int | Best lap time (ms) | 1326566 |
| `average_lap` | int | Average lap time (ms) | 1510496 |
| `champ_points` | int | Championship points earned | 9 |
| `oldi_rating` | int | iRating before race | 1546 |
| `newi_rating` | int | iRating after race | 1459 |
| `old_license_level` | int | License level before | 10 |
| `new_license_level` | int | License level after | 10 |
| `reason_out` | string | Reason for DNF | "Disconnected" |
| `reason_out_id` | int | DNF reason code | 32 |
| `car_id` | int | Car identifier | 178 |
| `car_class_id` | int | Car class identifier | 4049 |
| `country_code` | string | Driver country | "GB" |
| `division` | int | Driver division | 4 |
| `drop_race` | boolean | Whether race is dropped | false |

### Track Information
```json
{
  "track": {
    "category": "Road",
    "category_id": 2,
    "config_name": "Classic Pits",
    "track_id": 524,
    "track_name": "Circuit de Spa-Francorchamps"
  }
}
```

### Weather Information
```json
{
  "weather": {
    "allow_fog": false,
    "fog": 0,
    "precip_mm2hr_before_final_session": 0,
    "precip_mm_final_session": 0,
    "precip_option": 8,
    "precip_time_pct": 0,
    "rel_humidity": 0,
    "simulated_start_time": "2025-06-07T14:55:00",
    "skies": 2,
    "temp_units": 1,
    "temp_value": 21,
    "time_of_day": 0,
    "track_water": 0,
    "type": 3,
    "version": 1,
    "wind_dir": 5,
    "wind_units": 1,
    "wind_value": 2
  }
}
```

## Team Event API Response Structure (Differences from Solo Events)

### Team Event Structure
In team events, the API response introduces a new layer for teams. The main results array contains team objects, each with a `team_id`, `display_name`, and team-level stats. Each team object contains a `driver_results` array, listing all drivers who participated for that team, with their individual stats.

#### Example (Simplified):
```json
{
  "results": [
    {
      "team_id": 12345,
      "display_name": "Team Example",
      "finish_position": 1,
      "laps_complete": 100,
      "incidents": 5,
      "driver_results": [
        {
          "cust_id": 111,
          "display_name": "Driver One",
          "laps_complete": 60,
          "incidents": 2
        },
        {
          "cust_id": 222,
          "display_name": "Driver Two",
          "laps_complete": 40,
          "incidents": 3
        }
      ]
    },
    ...
  ]
}
```

### Key Differences from Solo Events
- **Team Layer**: Results are grouped by team, not just by driver.
- **driver_results**: Nested array under each team, containing individual driver stats.
- **Team Stats**: Team-level stats (finish position, laps, incidents, etc.) are present alongside aggregated driver stats.
- **Linkage**: Each driver result includes a `team_id` for reference.

## Proposed Model Relationships for Results

### Existing Models (for reference)
- **SimProfile**: Represents a driver (linked to user and sim account)
- **Team**: Represents a team (in `simlane.teams` app)

### New/Updated Models

#### EventResult
- Represents the overall result for an EventInstance (solo or team event)
- One-to-one with EventInstance
- Has many TeamResults (for team events) or ParticipantResults (for solo events)

#### TeamResult
- Represents a team's result in a team event
- ForeignKey to EventResult
- ForeignKey to Team (from `simlane.teams`)
- Contains team-level stats (finish position, laps, incidents, etc.)
- Has many ParticipantResults (one per driver in the team for this event)

#### ParticipantResult
- Represents an individual driver's result
- ForeignKey to SimProfile (from `simlane.sim`)
- ForeignKey to TeamResult (nullable, for solo events)
- ForeignKey to EventResult (for solo events)
- Contains driver-level stats (laps, incidents, iRating, etc.)

### Model Relationship Diagram (Textual)

- **EventResult** (1) ──< (M) **TeamResult** (for team events)
- **EventResult** (1) ──< (M) **ParticipantResult** (for solo events)
- **TeamResult** (1) ──< (M) **ParticipantResult** (for team events)
- **TeamResult** (M) ── (1) **Team** (existing)
- **ParticipantResult** (M) ── (1) **SimProfile** (existing)

#### Notes:
- For solo events, ParticipantResult links directly to EventResult (team field is null).
- For team events, ParticipantResult links to TeamResult, which links to EventResult and Team.
- This structure supports both solo and team events, and allows querying all participants for an event, all teams for an event, and all drivers for a team in an event.

## Example Model Definitions (Django-style, simplified)

```python
class EventResult(models.Model):
    event_instance = models.OneToOneField(EventInstance, on_delete=models.CASCADE)
    # ... summary fields ...

class TeamResult(models.Model):
    event_result = models.ForeignKey(EventResult, on_delete=models.CASCADE, related_name='team_results')
    team = models.ForeignKey('teams.Team', on_delete=models.CASCADE)
    # ... team stats ...

class ParticipantResult(models.Model):
    sim_profile = models.ForeignKey('sim.SimProfile', on_delete=models.CASCADE)
    team_result = models.ForeignKey(TeamResult, null=True, blank=True, on_delete=models.CASCADE, related_name='participants')
    event_result = models.ForeignKey(EventResult, null=True, blank=True, on_delete=models.CASCADE, related_name='participants')
    # ... driver stats ...
```

## Summary
- Team events require a TeamResult model to aggregate team-level stats and link to multiple drivers.
- ParticipantResult should link to TeamResult for team events, and directly to EventResult for solo events.
- Existing SimProfile and Team models are used for linking drivers and teams.
- This structure is flexible and supports both solo and team event result storage and querying.

## Proposed Database Models

### EventResult Model (Summary Level)
```python
class EventResult(models.Model):
    event_instance = models.OneToOneField(EventInstance, on_delete=models.CASCADE)
    subsession_id = models.BigIntegerField(unique=True)
    session_id = models.BigIntegerField(null=True, blank=True)
    
    # Event summary
    num_drivers = models.IntegerField()
    event_strength_of_field = models.IntegerField()
    event_best_lap_time = models.IntegerField(help_text="Best lap time in milliseconds")
    event_average_lap = models.IntegerField(help_text="Average lap time in milliseconds")
    
    # Race statistics
    num_cautions = models.IntegerField(default=0)
    num_caution_laps = models.IntegerField(default=0)
    num_lead_changes = models.IntegerField(default=0)
    
    # Weather and track conditions
    weather_data = models.JSONField(null=True, blank=True)
    track_state = models.JSONField(null=True, blank=True)
    
    # Processing status
    results_fetched_at = models.DateTimeField(auto_now_add=True)
    is_processed = models.BooleanField(default=False)
    
    # Raw data backup
    raw_api_data = models.JSONField(null=True, blank=True)
```

### ParticipantResult Model (Detailed Level)
```python
class ParticipantResult(models.Model):
    event_result = models.ForeignKey(EventResult, on_delete=models.CASCADE, related_name='participants')
    sim_profile = models.ForeignKey(SimProfile, on_delete=models.CASCADE, related_name='race_results')
    
    # Position data
    finish_position = models.IntegerField()
    starting_position = models.IntegerField()
    finish_position_in_class = models.IntegerField(null=True, blank=True)
    
    # Performance data
    laps_complete = models.IntegerField()
    laps_lead = models.IntegerField(default=0)
    incidents = models.IntegerField(default=0)
    
    # Lap times (in milliseconds)
    best_lap_time = models.IntegerField(null=True, blank=True)
    best_lap_num = models.IntegerField(null=True, blank=True)
    average_lap = models.IntegerField(null=True, blank=True)
    
    # Points and ratings
    champ_points = models.IntegerField(default=0)
    oldi_rating = models.IntegerField(null=True, blank=True)
    newi_rating = models.IntegerField(null=True, blank=True)
    old_license_level = models.IntegerField(null=True, blank=True)
    new_license_level = models.IntegerField(null=True, blank=True)
    
    # Race outcome
    reason_out = models.CharField(max_length=50, blank=True)
    reason_out_id = models.IntegerField(null=True, blank=True)
    drop_race = models.BooleanField(default=False)
    
    # Car and class info
    car_id = models.IntegerField(null=True, blank=True)
    car_class_id = models.IntegerField(null=True, blank=True)
    car_class_name = models.CharField(max_length=100, blank=True)
    
    # Additional data
    country_code = models.CharField(max_length=3, blank=True)
    division = models.IntegerField(null=True, blank=True)
    
    # Raw participant data
    raw_participant_data = models.JSONField(null=True, blank=True)
    
    class Meta:
        unique_together = ['event_result', 'sim_profile']
        indexes = [
            models.Index(fields=['event_result', 'finish_position']),
            models.Index(fields=['sim_profile', 'finish_position']),
            models.Index(fields=['oldi_rating', 'newi_rating']),
        ]
```

## Design Decisions

### 1. Hybrid Approach
- **EventResult**: Stores race summary and statistics for quick access
- **ParticipantResult**: Stores detailed individual performance data
- **Raw JSON**: Preserves complete API data for future use

### 2. Data Types
- **Time fields**: Stored as integers (milliseconds) for precision
- **Ratings**: Stored as integers (iRacing uses integer ratings)
- **Positions**: Stored as integers (1-based positions)
- **JSON fields**: Store complex nested data (weather, track state, raw data)

### 3. Indexing Strategy
- Index on `event_result` + `finish_position` for race results queries
- Index on `sim_profile` + `finish_position` for driver history queries
- Index on rating changes for rating analysis

### 4. Future Considerations
- **Team events**: May need additional fields for team results
- **Multi-class races**: Already supported via `finish_position_in_class`
- **Historical data**: Rating changes tracked via old/new fields
- **Weather analysis**: Raw weather data preserved in JSON fields

## Implementation Status

### Completed
- [x] API data structure analysis
- [x] Model design decisions
- [x] Sample data collection
- [x] Celery task infrastructure for result fetching

### Pending
- [ ] Create EventResult and ParticipantResult models
- [ ] Implement result processing logic
- [ ] Add result fetching to scheduled tasks
- [ ] Create result display views
- [ ] Add result analytics and statistics

## Notes
- All lap times are in milliseconds (iRacing standard)
- Rating changes are tracked via old/new fields for historical analysis
- Raw JSON data is preserved for future feature development
- Team events can be supported by adding team_id field to ParticipantResult 