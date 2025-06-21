from ninja import Router
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from ninja.errors import HttpError
from typing import List

from simlane.sim.models import Simulator, SimProfile, SimCar, SimTrack, LapTime
from simlane.api.schemas.sim import (
    Simulator as SimulatorSchema,
    SimulatorCreate,
    SimulatorUpdate,
    SimProfile as SimProfileSchema,
    SimProfileCreate,
    SimProfileUpdate,
    SimCar as SimCarSchema,
    SimCarCreate,
    SimCarUpdate,
    SimTrack as SimTrackSchema,
    SimTrackCreate,
    SimTrackUpdate,
    LapTime as LapTimeSchema,
    LapTimeCreate,
    LapTimeUpdate,
    DashboardStats,
    SimDataSummary,
)

router = Router()


# Simulator endpoints
@router.get("/simulators", response=List[SimulatorSchema])
def list_simulators(request: HttpRequest):
    """List all active simulators."""
    simulators = Simulator.objects.filter(is_active=True)
    return [SimulatorSchema.from_orm(simulator) for simulator in simulators]


@router.get("/simulators/{simulator_id}", response=SimulatorSchema)
def get_simulator(request: HttpRequest, simulator_id: int):
    """Get simulator details."""
    simulator = get_object_or_404(Simulator, id=simulator_id)
    return SimulatorSchema.from_orm(simulator)


# Sim profile endpoints
@router.get("/profiles", response=List[SimProfileSchema])
def list_user_profiles(request: HttpRequest):
    """List current user's sim profiles."""
    profiles = SimProfile.objects.filter(user=request.auth)
    return [SimProfileSchema.from_orm(profile) for profile in profiles]


@router.post("/profiles", response=SimProfileSchema)
def create_sim_profile(request: HttpRequest, profile_data: SimProfileCreate):
    """Create a new sim profile."""
    # Check if profile already exists for this simulator
    if SimProfile.objects.filter(
        user=request.auth,
        simulator_id=profile_data.simulator_id
    ).exists():
        raise HttpError(400, "Profile already exists for this simulator")
    
    profile = SimProfile.objects.create(
        user=request.auth,
        simulator_id=profile_data.simulator_id,
        profile_id=profile_data.profile_id,
        display_name=profile_data.display_name,
        rating=profile_data.rating,
        license_class=profile_data.license_class,
        safety_rating=profile_data.safety_rating,
    )
    
    return SimProfileSchema.from_orm(profile)


@router.get("/profiles/{profile_id}", response=SimProfileSchema)
def get_sim_profile(request: HttpRequest, profile_id: int):
    """Get sim profile details."""
    profile = get_object_or_404(SimProfile, id=profile_id, user=request.auth)
    return SimProfileSchema.from_orm(profile)


@router.patch("/profiles/{profile_id}", response=SimProfileSchema)
def update_sim_profile(request: HttpRequest, profile_id: int, updates: SimProfileUpdate):
    """Update sim profile."""
    profile = get_object_or_404(SimProfile, id=profile_id, user=request.auth)
    
    # Update profile fields
    for field, value in updates.dict(exclude_unset=True).items():
        if hasattr(profile, field):
            setattr(profile, field, value)
    
    profile.save()
    return SimProfileSchema.from_orm(profile)


@router.delete("/profiles/{profile_id}")
def delete_sim_profile(request: HttpRequest, profile_id: int):
    """Delete sim profile."""
    profile = get_object_or_404(SimProfile, id=profile_id, user=request.auth)
    profile.delete()
    return {"message": "Profile deleted successfully"}


# Car endpoints
@router.get("/simulators/{simulator_id}/cars", response=List[SimCarSchema])
def list_simulator_cars(request: HttpRequest, simulator_id: int):
    """List cars for a simulator."""
    cars = SimCar.objects.filter(simulator_id=simulator_id, is_active=True)
    return [SimCarSchema.from_orm(car) for car in cars]


@router.get("/cars/{car_id}", response=SimCarSchema)
def get_car(request: HttpRequest, car_id: int):
    """Get car details."""
    car = get_object_or_404(SimCar, id=car_id)
    return SimCarSchema.from_orm(car)


# Track endpoints
@router.get("/simulators/{simulator_id}/tracks", response=List[SimTrackSchema])
def list_simulator_tracks(request: HttpRequest, simulator_id: int):
    """List tracks for a simulator."""
    tracks = SimTrack.objects.filter(simulator_id=simulator_id, is_active=True)
    return [SimTrackSchema.from_orm(track) for track in tracks]


@router.get("/tracks/{track_id}", response=SimTrackSchema)
def get_track(request: HttpRequest, track_id: int):
    """Get track details."""
    track = get_object_or_404(SimTrack, id=track_id)
    return SimTrackSchema.from_orm(track)


# Lap time endpoints
@router.get("/laptimes", response=List[LapTimeSchema])
def list_user_lap_times(request: HttpRequest, simulator_id: int = None, limit: int = 50):
    """List current user's lap times."""
    laptimes = LapTime.objects.filter(user=request.auth)
    
    if simulator_id:
        laptimes = laptimes.filter(simulator_id=simulator_id)
    
    laptimes = laptimes.order_by('-recorded_at')[:limit]
    return [LapTimeSchema.from_orm(laptime) for laptime in laptimes]


@router.post("/laptimes", response=LapTimeSchema)
def create_lap_time(request: HttpRequest, laptime_data: LapTimeCreate):
    """Create a new lap time record."""
    laptime = LapTime.objects.create(
        user=request.auth,
        simulator_id=laptime_data.simulator_id,
        car_id=laptime_data.car_id,
        track_id=laptime_data.track_id,
        lap_time=laptime_data.lap_time,
        session_type=laptime_data.session_type,
        weather_conditions=laptime_data.weather_conditions,
        track_temperature=laptime_data.track_temperature,
        air_temperature=laptime_data.air_temperature,
        recorded_at=laptime_data.recorded_at,
        is_valid=True,  # Auto-validate for now
    )
    
    return LapTimeSchema.from_orm(laptime)


@router.get("/laptimes/{laptime_id}", response=LapTimeSchema)
def get_lap_time(request: HttpRequest, laptime_id: int):
    """Get lap time details."""
    laptime = get_object_or_404(LapTime, id=laptime_id, user=request.auth)
    return LapTimeSchema.from_orm(laptime)


@router.patch("/laptimes/{laptime_id}", response=LapTimeSchema)
def update_lap_time(request: HttpRequest, laptime_id: int, updates: LapTimeUpdate):
    """Update lap time record."""
    laptime = get_object_or_404(LapTime, id=laptime_id, user=request.auth)
    
    # Update laptime fields
    for field, value in updates.dict(exclude_unset=True).items():
        if hasattr(laptime, field):
            setattr(laptime, field, value)
    
    laptime.save()
    return LapTimeSchema.from_orm(laptime)


@router.delete("/laptimes/{laptime_id}")
def delete_lap_time(request: HttpRequest, laptime_id: int):
    """Delete lap time record."""
    laptime = get_object_or_404(LapTime, id=laptime_id, user=request.auth)
    laptime.delete()
    return {"message": "Lap time deleted successfully"}


# Dashboard and statistics endpoints
@router.get("/dashboard/stats", response=DashboardStats)
def get_dashboard_stats(request: HttpRequest):
    """Get sim racing dashboard statistics."""
    # Calculate statistics
    total_simulators = Simulator.objects.filter(is_active=True).count()
    total_cars = SimCar.objects.filter(is_active=True).count()
    total_tracks = SimTrack.objects.filter(is_active=True).count()
    total_lap_times = LapTime.objects.filter(user=request.auth).count()
    
    # Get best lap time
    best_laptime_obj = LapTime.objects.filter(
        user=request.auth,
        is_valid=True
    ).order_by('lap_time').first()
    
    best_lap_time = best_laptime_obj.lap_time if best_laptime_obj else None
    
    user_profiles = SimProfile.objects.filter(user=request.auth).count()
    verified_profiles = SimProfile.objects.filter(user=request.auth, is_verified=True).count()
    
    # Recent sessions (lap times in last 30 days)
    from datetime import datetime, timedelta
    recent_cutoff = datetime.now() - timedelta(days=30)
    recent_sessions = LapTime.objects.filter(
        user=request.auth,
        recorded_at__gte=recent_cutoff
    ).count()
    
    return DashboardStats(
        total_simulators=total_simulators,
        total_cars=total_cars,
        total_tracks=total_tracks,
        total_lap_times=total_lap_times,
        best_lap_time=best_lap_time,
        recent_sessions=recent_sessions,
        user_profiles=user_profiles,
        verified_profiles=verified_profiles,
    )


@router.get("/dashboard/simulators", response=List[SimDataSummary])
def get_simulator_summaries(request: HttpRequest):
    """Get summary data for each simulator."""
    simulators = Simulator.objects.filter(is_active=True)
    summaries = []
    
    for simulator in simulators:
        car_count = SimCar.objects.filter(simulator=simulator, is_active=True).count()
        track_count = SimTrack.objects.filter(simulator=simulator, is_active=True).count()
        user_profiles = SimProfile.objects.filter(simulator=simulator).count()
        recent_lap_times = LapTime.objects.filter(
            simulator=simulator,
            user=request.auth
        ).count()
        
        # Get average and best lap times for user
        user_laptimes = LapTime.objects.filter(
            simulator=simulator,
            user=request.auth,
            is_valid=True
        )
        
        avg_lap_time = None
        best_lap_time = None
        
        if user_laptimes.exists():
            best_laptime_obj = user_laptimes.order_by('lap_time').first()
            best_lap_time = best_laptime_obj.lap_time if best_laptime_obj else None
            
            # Calculate average (this is simplified - would need proper time averaging)
            # For now, just use the best time as a placeholder
            avg_lap_time = best_lap_time
        
        summaries.append(SimDataSummary(
            simulator=simulator,
            car_count=car_count,
            track_count=track_count,
            user_profiles=user_profiles,
            recent_lap_times=recent_lap_times,
            avg_lap_time=avg_lap_time,
            best_lap_time=best_lap_time,
        ))
    
    return summaries 