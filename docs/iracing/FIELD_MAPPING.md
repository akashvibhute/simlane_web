# iRacing API Field Mapping

## Overview
This document maps iRacing API response fields to our database models, indicating which fields we'll store and which we'll discard.

## Weather Object Analysis
The weather object contains **static weather conditions** set for the race, not dynamic weather at different times. It includes initial conditions and weather variation settings, but no time-series data of changing conditions during the race.

## EventResult Model Field Mapping

### Fields to Map (Store in Database)
| API Field | Database Field | Type | Description |
|-----------|----------------|------|-------------|
| `subsession_id` | `subsession_id` | BigIntegerField | Unique race identifier |
| `session_id` | `session_id` | BigIntegerField | Session identifier |
| `num_drivers` | `num_drivers` | IntegerField | Number of participants |
| `event_strength_of_field` | `event_strength_of_field` | IntegerField | Overall field strength rating |
| `event_best_lap_time` | `event_best_lap_time` | IntegerField | Best lap time (milliseconds) |
| `event_average_lap` | `event_average_lap` | IntegerField | Average lap time (milliseconds) |
| `num_cautions` | `num_cautions` | IntegerField | Number of caution periods |
| `num_caution_laps` | `num_caution_laps` | IntegerField | Laps under caution |
| `num_lead_changes` | `num_lead_changes` | IntegerField | Number of lead changes |
| `start_time` | `start_time` | DateTimeField | Race start time |
| `end_time` | `end_time` | DateTimeField | Race end time |
| `weather` | `weather_data` | JSONField | Complete weather object |
| `track_state` | `track_state` | JSONField | Track rubber/marble state |
| `track` | `track_data` | JSONField | Track information |

### Fields to Discard
| API Field | Reason |
|-----------|--------|
| `series_id` | Already available via EventInstance → Event → RaceWeek → Season → Series |
| `season_id` | Already available via EventInstance → Event → RaceWeek → Season |
| `session_results` | Will be processed into ParticipantResult/TeamResult |
| `car_classes` | Not essential for result analysis |
| `allowed_licenses` | Not essential for result analysis |
| `session_splits` | Not essential for result analysis |
| `special_event_type` | Not essential for result analysis |

## TeamResult Model Field Mapping

### Fields to Map (Store in Database)
| API Field | Database Field | Type | Description |
|-----------|----------------|------|-------------|
| `team_id` | `team` | ForeignKey | Link to existing Team model |
| `display_name` | `team_display_name` | CharField | Team name from API (backup) |
| `finish_position` | `finish_position` | IntegerField | Team's final position |
| `finish_position_in_class` | `finish_position_in_class` | IntegerField | Team's position in class |
| `laps_complete` | `laps_complete` | IntegerField | Total laps completed by team |
| `laps_lead` | `laps_lead` | IntegerField | Total laps led by team |
| `incidents` | `incidents` | IntegerField | Total incidents by team |
| `best_lap_time` | `best_lap_time` | IntegerField | Team's best lap time |
| `best_lap_num` | `best_lap_num` | IntegerField | Lap number of team's best lap |
| `average_lap` | `average_lap` | IntegerField | Team's average lap time |
| `champ_points` | `champ_points` | IntegerField | Championship points earned |
| `reason_out` | `reason_out` | CharField | Reason for DNF |
| `reason_out_id` | `reason_out_id` | IntegerField | DNF reason code |
| `drop_race` | `drop_race` | BooleanField | Whether race is dropped |
| `car_id` | `car_id` | IntegerField | Car identifier |
| `car_class_id` | `car_class_id` | IntegerField | Car class identifier |
| `car_class_name` | `car_class_name` | CharField | Car class name |
| `car_name` | `car_name` | CharField | Car name |
| `country_code` | `country_code` | CharField | Team country |
| `division` | `division` | IntegerField | Team division |

### Fields to Discard
| API Field | Reason |
|-----------|--------|
| `driver_results` | Will be processed into ParticipantResult |
| `aggregate_champ_points` | Redundant with champ_points |
| `ai` | Not essential for result analysis |
| `best_nlaps_num` | Not essential for result analysis |
| `best_nlaps_time` | Not essential for result analysis |
| `best_qual_lap_at` | Not essential for result analysis |
| `best_qual_lap_num` | Not essential for result analysis |
| `best_qual_lap_time` | Not essential for result analysis |
| `carcfg` | Not essential for result analysis |
| `class_interval` | Not essential for result analysis |
| `flair_id` | Not essential for result analysis |
| `flair_name` | Not essential for result analysis |
| `flair_shortname` | Not essential for result analysis |
| `friend` | Not essential for result analysis |
| `helmet` | Not essential for result analysis |
| `interval` | Not essential for result analysis |
| `league_agg_points` | Not essential for result analysis |
| `league_points` | Not essential for result analysis |
| `license_change_oval` | Not essential for result analysis |
| `license_change_road` | Not essential for result analysis |
| `livery` | Not essential for result analysis |
| `max_pct_fuel_fill` | Not essential for result analysis |
| `new_cpi` | Not essential for result analysis |
| `new_license_level` | Not essential for result analysis |
| `new_sub_level` | Not essential for result analysis |
| `new_ttrating` | Not essential for result analysis |
| `newi_rating` | Not essential for result analysis |
| `old_cpi` | Not essential for result analysis |
| `old_license_level` | Not essential for result analysis |
| `old_sub_level` | Not essential for result analysis |
| `old_ttrating` | Not essential for result analysis |
| `oldi_rating` | Not essential for result analysis |
| `opt_laps_complete` | Not essential for result analysis |
| `position` | Redundant with finish_position |
| `qual_lap_time` | Not essential for result analysis |
| `starting_position` | Not essential for result analysis |
| `starting_position_in_class` | Not essential for result analysis |
| `suit` | Not essential for result analysis |
| `watched` | Not essential for result analysis |
| `weight_penalty_kg` | Not essential for result analysis |

## ParticipantResult Model Field Mapping

### Fields to Map (Store in Database)
| API Field | Database Field | Type | Description |
|-----------|----------------|------|-------------|
| `cust_id` | `sim_profile` | ForeignKey | Link to existing SimProfile |
| `display_name` | `driver_display_name` | CharField | Driver name from API (backup) |
| `finish_position` | `finish_position` | IntegerField | Driver's final position |
| `finish_position_in_class` | `finish_position_in_class` | IntegerField | Driver's position in class |
| `starting_position` | `starting_position` | IntegerField | Starting grid position |
| `starting_position_in_class` | `starting_position_in_class` | IntegerField | Starting position in class |
| `laps_complete` | `laps_complete` | IntegerField | Laps completed by driver |
| `laps_lead` | `laps_lead` | IntegerField | Laps led by driver |
| `incidents` | `incidents` | IntegerField | Incidents by driver |
| `best_lap_time` | `best_lap_time` | IntegerField | Driver's best lap time |
| `best_lap_num` | `best_lap_num` | IntegerField | Lap number of driver's best lap |
| `average_lap` | `average_lap` | IntegerField | Driver's average lap time |
| `champ_points` | `champ_points` | IntegerField | Championship points earned |
| `oldi_rating` | `oldi_rating` | IntegerField | iRating before race |
| `newi_rating` | `newi_rating` | IntegerField | iRating after race |
| `old_license_level` | `old_license_level` | IntegerField | License level before |
| `new_license_level` | `new_license_level` | IntegerField | License level after |
| `old_sub_level` | `old_sub_level` | IntegerField | Sub-level before |
| `new_sub_level` | `new_sub_level` | IntegerField | Sub-level after |
| `reason_out` | `reason_out` | CharField | Reason for DNF |
| `reason_out_id` | `reason_out_id` | IntegerField | DNF reason code |
| `drop_race` | `drop_race` | BooleanField | Whether race is dropped |
| `car_id` | `car_id` | IntegerField | Car identifier |
| `car_class_id` | `car_class_id` | IntegerField | Car class identifier |
| `car_class_name` | `car_class_name` | CharField | Car class name |
| `car_name` | `car_name` | CharField | Car name |
| `country_code` | `country_code` | CharField | Driver country |
| `division` | `division` | IntegerField | Driver division |

### Fields to Discard
| API Field | Reason |
|-----------|--------|
| `team_id` | Will be handled via TeamResult relationship |
| `aggregate_champ_points` | Redundant with champ_points |
| `ai` | Not essential for result analysis |
| `best_nlaps_num` | Not essential for result analysis |
| `best_nlaps_time` | Not essential for result analysis |
| `best_qual_lap_at` | Not essential for result analysis |
| `best_qual_lap_num` | Not essential for result analysis |
| `best_qual_lap_time` | Not essential for result analysis |
| `carcfg` | Not essential for result analysis |
| `class_interval` | Not essential for result analysis |
| `flair_id` | Not essential for result analysis |
| `flair_name` | Not essential for result analysis |
| `flair_shortname` | Not essential for result analysis |
| `friend` | Not essential for result analysis |
| `helmet` | Not essential for result analysis |
| `interval` | Not essential for result analysis |
| `league_agg_points` | Not essential for result analysis |
| `league_points` | Not essential for result analysis |
| `license_change_oval` | Not essential for result analysis |
| `license_change_road` | Not essential for result analysis |
| `livery` | Not essential for result analysis |
| `max_pct_fuel_fill` | Not essential for result analysis |
| `new_cpi` | Not essential for result analysis |
| `new_ttrating` | Not essential for result analysis |
| `old_cpi` | Not essential for result analysis |
| `old_ttrating` | Not essential for result analysis |
| `opt_laps_complete` | Not essential for result analysis |
| `position` | Redundant with finish_position |
| `qual_lap_time` | Not essential for result analysis |
| `suit` | Not essential for result analysis |
| `watched` | Not essential for result analysis |
| `weight_penalty_kg` | Not essential for result analysis |

## Summary

### Key Decisions:
1. **Weather Data**: Store complete weather object as JSON for future analysis
2. **Track Data**: Store complete track object as JSON for reference
3. **Raw Data**: Store complete API response as JSON backup
4. **Essential Fields**: Focus on performance, position, and rating data
5. **Visual/Cosmetic Fields**: Discard helmet, livery, suit, flair data
6. **Redundant Fields**: Discard fields that duplicate other data
7. **Non-Essential Fields**: Discard fields not needed for result analysis

### Benefits:
- **Focused Data Model**: Only essential fields stored as database columns
- **Future-Proof**: Raw JSON preserves all data for future features
- **Performance**: Optimized queries on indexed fields
- **Flexibility**: JSON fields allow for future analysis without schema changes 