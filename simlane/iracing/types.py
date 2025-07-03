"""
Type definitions for iRacing API responses.

This module provides TypedDict classes for all iRacing API responses to ensure
proper type checking and better IDE support.
"""

from typing import List, TypedDict, Union


# Member Information Types
class MemberInfo(TypedDict):
    """Response type for /data/member/info endpoint."""
    cust_id: int
    display_name: str
    helmet: dict
    last_login: str
    member_since: str
    club_id: int
    club_name: str
    ai: bool


# Series Types
class SeriesAsset(TypedDict):
    """Asset information for a series."""
    series_id: int
    logo: str
    logo_small: str
    series_copy: str





# Season Types
class Schedule(TypedDict):
    """Schedule information for a race week."""
    season_id: int
    race_week_num: int
    race_lap_limit: int
    race_time_limit: int
    restrict_by_member: bool
    restrict_to_car: bool
    paid_event: bool
    track_id: int
    track_name: str
    config_name: str
    track_state: dict
    weather_temp_units: int
    weather_wind_speed_units: int
    weather_wind_dir: int
    weather_skies: int
    weather_var_initial: int
    weather_var_ongoing: int
    time_of_day: int
    simulated_start_utc: str
    race_time_descriptors: List[dict]
    car_restrictions: List[dict]
    start_date: str
    week_end_time: str


class SeasonInfo(TypedDict):
    """Season information."""
    season_id: int
    series_id: int
    season_name: str
    series_name: str
    official: bool
    season_year: int
    season_quarter: int
    license_group: int
    fixed_setup: bool
    driver_changes: bool
    schedules: List[Schedule]


class SeriesSeasons(TypedDict):
    """Response type for /data/series/seasons endpoint."""
    series_id: int
    series_name: str
    category: str
    category_id: int
    schedules: List[Schedule]



class SeasonScheduleResponse(TypedDict):
    """Response type for /data/series/season_schedule endpoint."""
    success: bool
    season_id: int
    schedules: List[Schedule]


# Car Types
class Car(TypedDict):
    """Car information from /data/car/get endpoint."""
    car_id: int
    car_name: str
    car_name_abbreviated: str
    car_weight: int
    car_types: List[str]
    car_make: str
    created: str
    free_with_subscription: bool
    has_headlights: bool
    has_multiple_dry_tire_types: bool
    hp: int
    is_ps_purchasable: bool
    package_id: int
    patterns: int
    price: float
    price_display: str
    retired: bool
    search_filters: str
    sku: int
    car_dirpath: str
    has_rain_capable_tire_types: bool
    rain_enabled: bool
    ai_enabled: bool
    award_exempt: bool
    paint_rules: dict
    site_url: str


class CarAsset(TypedDict):
    """Car asset information."""
    car_id: int
    car_rules: List[int]
    detail_copy: str
    detail_screen_shot_images: str
    detail_techspecs_copy: str
    folder: str
    gallery_images: str
    gallery_prefix: str
    group_image: str
    group_name: str
    large_image: str
    logo: str
    small_image: str
    sponsor_logo: str
    template_path: str


# Track Types
class Track(TypedDict):
    """Track information from /data/track/get endpoint."""
    track_id: int
    track_name: str
    config_name: str
    category_id: int
    category: str
    price: float
    price_display: str
    package_id: int
    sku: int
    is_ps_purchasable: bool
    created: str
    release_date: str
    retired: bool
    site_url: str
    search_filters: str
    track_types: List[dict]
    has_svg_map: bool
    ai_enabled: bool
    award_exempt: bool
    is_dirt: bool
    is_oval: bool
    supports_grip_compound: bool
    banking: str
    corners: int
    track_dirpath: str
    track_map_layers: dict
    track_config_length: float
    grid_stalls: int
    pit_road_speed_limit: int
    number_pitstalls: int
    qualifying_laps: int
    restart_on_left: bool
    time_zone: str
    latitude: float
    longitude: float
    north_offset: float
    allow_pitlane_collisions: bool
    allow_rolling_start: bool
    first_sale: str
    free_with_subscription: bool
    fully_lit: bool
    has_opt_track_surface: bool
    location: str
    max_cars: int
    night_lighting: bool
    nominal_lap_time: float
    opens: str


class TrackAsset(TypedDict):
    """Track asset information."""
    track_id: int
    detail_copy: str
    detail_techspecs_copy: str
    detail_video: str
    folder: str
    gallery_images: str
    gallery_prefix: str
    large_image: str
    logo: str
    north: str
    num_svg_images: int
    small_image: str
    track_map: str
    track_map_layers: dict

class CarInCarClass(TypedDict):
    """Car in car class information."""
    car_dirpath: str
    car_id: int
    rain_enabled: bool
    retired: bool

# Car Class Types
class CarClass(TypedDict):
    """Car class information from /data/carclass/get endpoint."""
    car_class_id: int
    cars_in_class: List[CarInCarClass]
    cust_id: int
    name: str
    relative_speed: int
    short_name: str
    rain_enabled: bool 
    
    
# Season Types
class Season(TypedDict):
    """Season information."""
    season_id: int
    season_name: str
    season_year: int
    season_quarter: int
    series_id: int
    series_name: str
    official: bool
    
class Series(TypedDict):
    """Series information from /data/series/get endpoint."""
    series_id: int
    series_name: str
    series_short_name: str
    active: bool
    official: bool
    fixed_setup: bool
    multiclass: bool
    car_types: List[str]
    car_classes: List[int]
    category: str
    category_id: int
    eligible: bool
    is_heat_racing: bool
    license_group: int
    license_group_type: int
    min_license_level: int
    max_license_level: int
    min_sr: int
    max_sr: int
    rookie_season: str
    race_week: int
    search_filters: str
    series_lic: int
    tag: bool
    cars_in_class: List[int]
    complete: bool
    oval_caution_type: int
    parent_season_id: int
    seasons: List[Season]


class PastSeasonsResponse(TypedDict):
    """Response type for /data/series/past_seasons endpoint."""
    series: Series
    series_id: int