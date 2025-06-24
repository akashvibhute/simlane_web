from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, Http404
from django.db.models import Q, Count, Prefetch
from django.core.paginator import Paginator

from simlane.sim.models import (
    SimProfile, Simulator, CarModel, CarClass, 
    TrackModel, SimCar, SimTrack, SimLayout
)


# Public Profile Views
def profiles_list(request):
    """Public listing of all sim profiles"""
    profiles = SimProfile.objects.filter(
        is_public=True
    ).select_related('simulator', 'linked_user').order_by('-last_active', '-created_at')
    
    # Pagination
    paginator = Paginator(profiles, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'simulators': Simulator.objects.filter(is_active=True),
    }
    
    return render(request, 'sim/profiles/list.html', context)


def profiles_search(request):
    """Search sim profiles with AJAX support"""
    query = request.GET.get('q', '').strip()
    simulator_slug = request.GET.get('simulator', '')
    
    profiles = SimProfile.objects.filter(is_public=True)
    
    if query:
        profiles = profiles.filter(
            Q(profile_name__icontains=query) |
            Q(linked_user__first_name__icontains=query) |
            Q(linked_user__last_name__icontains=query) |
            Q(linked_user__username__icontains=query)
        )
    
    if simulator_slug:
        profiles = profiles.filter(simulator__slug=simulator_slug)
    
    profiles = profiles.select_related('simulator', 'linked_user')[:20]
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        # Return JSON for AJAX requests
        results = [{
            'id': str(p.id),
            'name': p.profile_name,
            'simulator': p.simulator.name,
            'url': p.get_absolute_url(),
            'linked_user': p.linked_user.get_full_name() if p.linked_user else None,
        } for p in profiles]
        return JsonResponse({'results': results})
    
    # Regular template response
    context = {'profiles': profiles, 'query': query}
    return render(request, 'sim/profiles/search_results.html', context)


def profiles_by_simulator(request, simulator_slug):
    """List profiles for a specific simulator"""
    simulator = get_object_or_404(Simulator, slug=simulator_slug, is_active=True)
    
    profiles = SimProfile.objects.filter(
        simulator=simulator,
        is_public=True
    ).select_related('linked_user').order_by('-last_active', '-created_at')
    
    # Pagination
    paginator = Paginator(profiles, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'simulator': simulator,
        'page_obj': page_obj,
    }
    
    return render(request, 'sim/profiles/simulator_list.html', context)


def profile_detail(request, simulator_slug, profile_identifier):
    """Public profile detail view"""
    simulator = get_object_or_404(Simulator, slug=simulator_slug, is_active=True)
    profile = get_object_or_404(
        SimProfile, 
        simulator=simulator, 
        external_data_id=profile_identifier,
        is_public=True
    )
    
    # Get recent lap times and ratings
    recent_lap_times = profile.lap_times.select_related('sim_layout__sim_track__track_model').order_by('-recorded_at')[:10]
    current_ratings = profile.ratings.select_related('rating_system').order_by('-recorded_at')
    
    context = {
        'profile': profile,
        'simulator': simulator,
        'recent_lap_times': recent_lap_times,
        'current_ratings': current_ratings,
    }
    
    return render(request, 'sim/profiles/detail.html', context)


# Dashboard Views
@login_required
def dashboard_home(request):
    """Main dashboard showing all simulators and user's profiles"""
    user_profiles = request.user.linked_sim_profiles.select_related('simulator').order_by('simulator__name')
    simulators = Simulator.objects.filter(is_active=True).order_by('name')
    
    context = {
        'user_profiles': user_profiles,
        'simulators': simulators,
    }
    
    return render(request, 'sim/dashboard/home.html', context)


@login_required  
def simulator_dashboard(request, simulator_slug):
    """Dashboard for a specific simulator - defaults to overview"""
    return simulator_dashboard_section(request, simulator_slug, "overview")


@login_required
def simulator_dashboard_section(request, simulator_slug, section="overview"):
    """Simulator dashboard section view with HTMX support"""
    simulator = get_object_or_404(Simulator, slug=simulator_slug, is_active=True)
    
    # Get user's profiles for this simulator
    user_profiles = request.user.linked_sim_profiles.filter(
        simulator=simulator
    ).select_related("simulator")

    # Handle profile selection
    selected_profile = None
    if request.method == "POST" and "profile_id" in request.POST:
        profile_id = request.POST.get("profile_id")
        if profile_id:
            try:
                selected_profile = user_profiles.get(id=profile_id)
                request.session[f"selected_{simulator_slug}_profile_id"] = str(profile_id)
            except SimProfile.DoesNotExist:
                pass
    elif f"selected_{simulator_slug}_profile_id" in request.session:
        try:
            selected_profile = user_profiles.get(
                id=request.session[f"selected_{simulator_slug}_profile_id"],
            )
        except SimProfile.DoesNotExist:
            del request.session[f"selected_{simulator_slug}_profile_id"]

    # If no profile selected and profiles exist, select the first one
    if not selected_profile and user_profiles.exists():
        selected_profile = user_profiles.first()
        if selected_profile:
            request.session[f"selected_{simulator_slug}_profile_id"] = str(selected_profile.id)

    context = {
        "simulator": simulator,
        "user_profiles": user_profiles,
        "selected_profile": selected_profile,
        "active_section": section,
    }

    # HTMX requests return partial content
    if request.headers.get("HX-Request"):
        return render(request, f"sim/{simulator_slug}/dashboard_content_partial.html", context)

    # Regular requests return full page
    return render(request, f"sim/{simulator_slug}/dashboard.html", context)


# Cars Views
def cars_list(request):
    """Public listing of all cars"""
    # Base queryset with optimizations
    cars = CarModel.objects.select_related('car_class').prefetch_related(
        Prefetch(
            'sim_cars',
            queryset=SimCar.objects.select_related('simulator').filter(is_active=True),
        )
    ).annotate(
        simulator_count=Count('sim_cars__simulator', distinct=True)
    ).order_by('manufacturer', 'name')
    
    # Filtering
    simulator_slug = request.GET.get('simulator')
    car_class_slug = request.GET.get('class')
    manufacturer = request.GET.get('manufacturer')
    search_query = request.GET.get('q', '').strip()
    
    if simulator_slug:
        cars = cars.filter(sim_cars__simulator__slug=simulator_slug)
    
    if car_class_slug:
        cars = cars.filter(car_class__slug=car_class_slug)
    
    if manufacturer:
        cars = cars.filter(manufacturer__iexact=manufacturer)
    
    if search_query:
        cars = cars.filter(
            Q(name__icontains=search_query) |
            Q(manufacturer__icontains=search_query) |
            Q(car_class__name__icontains=search_query)
        )
    
    # Get filter options
    simulators = Simulator.objects.filter(is_active=True).order_by('name')
    car_classes = CarClass.objects.order_by('name')
    manufacturers = CarModel.objects.values_list('manufacturer', flat=True).distinct().order_by('manufacturer')
    
    # Pagination
    paginator = Paginator(cars, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'simulators': simulators,
        'car_classes': car_classes,
        'manufacturers': manufacturers,
        'selected_simulator': simulator_slug,
        'selected_class': car_class_slug,
        'selected_manufacturer': manufacturer,
        'search_query': search_query,
    }
    
    return render(request, 'sim/cars/list.html', context)


def car_detail(request, car_slug):
    """Detailed view of a specific car"""
    car = get_object_or_404(
        CarModel.objects.select_related('car_class').prefetch_related(
            Prefetch(
                'sim_cars',
                queryset=SimCar.objects.select_related('simulator', 'pit_data').filter(is_active=True),
            )
        ),
        slug=car_slug
    )
    
    # Get related cars (same class or manufacturer)
    related_cars = CarModel.objects.filter(
        Q(car_class=car.car_class) | Q(manufacturer=car.manufacturer)
    ).exclude(
        id=car.id
    ).select_related('car_class').annotate(
        simulator_count=Count('sim_cars__simulator', distinct=True)
    )[:8]
    
    context = {
        'car': car,
        'related_cars': related_cars,
    }
    
    return render(request, 'sim/cars/detail.html', context)


# Tracks Views
def tracks_list(request):
    """Public listing of all tracks"""
    # Base queryset with optimizations
    tracks = TrackModel.objects.prefetch_related(
        Prefetch(
            'sim_tracks',
            queryset=SimTrack.objects.select_related('simulator').filter(is_active=True).prefetch_related('layouts'),
        )
    ).annotate(
        simulator_count=Count('sim_tracks__simulator', distinct=True),
        layout_count=Count('sim_tracks__layouts', distinct=True)
    ).order_by('name')
    
    # Filtering
    simulator_slug = request.GET.get('simulator')
    country = request.GET.get('country')
    track_type = request.GET.get('type')
    laser_scanned_only = request.GET.get('laser_scanned') == 'true'
    search_query = request.GET.get('q', '').strip()
    
    if simulator_slug:
        tracks = tracks.filter(sim_tracks__simulator__slug=simulator_slug)
    
    if country:
        tracks = tracks.filter(country__iexact=country)
    
    if track_type:
        tracks = tracks.filter(sim_tracks__layouts__type=track_type).distinct()
    
    if laser_scanned_only:
        tracks = tracks.filter(sim_tracks__is_laser_scanned=True)
    
    if search_query:
        tracks = tracks.filter(
            Q(name__icontains=search_query) |
            Q(location__icontains=search_query) |
            Q(country__icontains=search_query)
        )
    
    # Get filter options
    simulators = Simulator.objects.filter(is_active=True).order_by('name')
    countries = TrackModel.objects.values_list('country', flat=True).distinct().order_by('country')
    track_types = SimLayout.type.field.choices
    
    # Pagination
    paginator = Paginator(tracks, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'simulators': simulators,
        'countries': countries,
        'track_types': track_types,
        'selected_simulator': simulator_slug,
        'selected_country': country,
        'selected_type': track_type,
        'laser_scanned_only': laser_scanned_only,
        'search_query': search_query,
    }
    
    return render(request, 'sim/tracks/list.html', context)


def track_detail(request, track_slug):
    """Detailed view of a specific track with all layouts"""
    track = get_object_or_404(
        TrackModel.objects.prefetch_related(
            Prefetch(
                'sim_tracks',
                queryset=SimTrack.objects.select_related('simulator').filter(is_active=True).prefetch_related(
                    Prefetch(
                        'layouts',
                        queryset=SimLayout.objects.select_related('pit_data').order_by('name')
                    )
                ),
            )
        ),
        slug=track_slug
    )
    
    # Get all unique layouts across simulators
    all_layouts = []
    layout_simulators = {}  # Track which simulators have which layouts
    
    for sim_track in track.sim_tracks.all():
        for layout in sim_track.layouts.all():
            layout_key = layout.slug
            if layout_key not in layout_simulators:
                layout_simulators[layout_key] = {
                    'layout': layout,
                    'simulators': []
                }
            layout_simulators[layout_key]['simulators'].append(sim_track.simulator)
    
    # Convert to list for template
    layouts_data = list(layout_simulators.values())
    
    # Get lap time records for this track
    from simlane.sim.models import LapTime
    lap_records = LapTime.objects.filter(
        sim_layout__sim_track__track_model=track,
        is_valid=True
    ).select_related(
        'sim_profile__linked_user',
        'sim_profile__simulator',
        'sim_layout'
    ).order_by('sim_layout', 'lap_time_ms')[:10]
    
    context = {
        'track': track,
        'layouts_data': layouts_data,
        'lap_records': lap_records,
    }
    
    return render(request, 'sim/tracks/detail.html', context)


def layout_detail(request, track_slug, layout_slug):
    """Detailed view of a specific track layout"""
    track = get_object_or_404(TrackModel, slug=track_slug)
    
    # Find the layout across all sim tracks
    layout = None
    layout_simulators = []
    
    for sim_track in track.sim_tracks.filter(is_active=True):
        try:
            found_layout = sim_track.layouts.get(slug=layout_slug)
            if not layout:
                layout = found_layout
            layout_simulators.append({
                'simulator': sim_track.simulator,
                'sim_track': sim_track,
                'layout': found_layout
            })
        except SimLayout.DoesNotExist:
            continue
    
    if not layout:
        raise Http404("Layout not found")
    
    # Get lap times for this layout
    from simlane.sim.models import LapTime
    lap_times = LapTime.objects.filter(
        sim_layout__slug=layout_slug,
        sim_layout__sim_track__track_model=track,
        is_valid=True
    ).select_related(
        'sim_profile__linked_user',
        'sim_profile__simulator',
        'sim_layout__sim_track__simulator'
    ).order_by('lap_time_ms')[:50]
    
    # Get other layouts for this track
    other_layouts = []
    for sim_track in track.sim_tracks.all():
        for other_layout in sim_track.layouts.exclude(slug=layout_slug):
            if other_layout.slug not in [l.slug for l in other_layouts]:
                other_layouts.append(other_layout)
    
    context = {
        'track': track,
        'layout': layout,
        'layout_simulators': layout_simulators,
        'lap_times': lap_times,
        'other_layouts': other_layouts,
    }
    
    return render(request, 'sim/tracks/layout_detail.html', context)



