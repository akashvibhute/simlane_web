from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, Http404
from django.db.models import Q, Count, Prefetch
from django.core.paginator import Paginator
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_cookie
from django.core.cache import cache
from django.views.decorators.http import require_POST
import logging
from django.utils import timezone

from simlane.sim.models import (
    SimProfile, Simulator, CarModel, CarClass, 
    TrackModel, SimCar, SimTrack, SimLayout, SimProfileCarOwnership, Event, EventSource, EventStatus
)
from simlane.core.cache_utils import (
    cache_for_anonymous, CacheKeyManager, cache_query
)
from simlane.iracing.tasks import sync_iracing_owned_content

logger = logging.getLogger(__name__)


# Query-level caching helpers
@cache_query(timeout=600, cache_alias='query_cache')  # 10 minutes
def get_public_profiles():
    return list(SimProfile.objects.filter(
        is_public=True
    ).select_related('simulator', 'linked_user').order_by('-last_active', '-created_at'))

@cache_query(timeout=1800, cache_alias='query_cache')  # 30 minutes
def get_active_simulators():
    return list(Simulator.objects.filter(is_active=True))

@cache_query(timeout=600, cache_alias='query_cache')
def get_all_cars_queryset():
    return CarModel.objects.prefetch_related(
        Prefetch(
            'sim_cars',
            queryset=SimCar.objects.select_related('simulator').only(
                'id', 'car_model', 'logo', 'small_image', 'large_image', 'is_active', 'simulator__icon', 'simulator__name', 'simulator__id'
            ),
        )
    ).only(
        'id', 'name', 'manufacturer', 'slug', 'category', 'default_image_url', 'release_year'
    ).annotate(
        simulator_count=Count('sim_cars__simulator', distinct=True)
    ).order_by('manufacturer', 'name')

@cache_query(timeout=600, cache_alias='query_cache')
def get_all_tracks_queryset():
    return TrackModel.objects.prefetch_related(
        Prefetch(
            'sim_tracks',
            queryset=SimTrack.objects.select_related('simulator').only(
                'id', 'track_model', 'logo', 'small_image', 'large_image', 'is_active', 'simulator__icon', 'simulator__name', 'simulator__id'
            ).prefetch_related('layouts'),
        )
    ).only(
        'id', 'name', 'slug', 'country', 'location'
    ).annotate(
        simulator_count=Count('sim_tracks__simulator', distinct=True),
        layout_count=Count('sim_tracks__layouts', distinct=True)
    ).order_by('name')

@cache_query(timeout=600, cache_alias='query_cache')
def get_events_queryset():
    """Get optimized events queryset with related data"""
    return Event.objects.select_related(
        'simulator',
        'series',
        'series__simulator',
        'sim_layout__sim_track__track_model',
        'organizing_club',
        'organizing_user'
    ).prefetch_related(
        'instances',
        'sessions'
    ).filter(
        visibility__in=['PUBLIC', 'UNLISTED']
    ).order_by('-created_at')


# Public Profile Views
@cache_for_anonymous(timeout=900)  # 15 minutes
def profiles_list(request):
    """Public listing of all sim profiles"""
    profiles = get_public_profiles()
    
    # Pagination
    paginator = Paginator(profiles, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'simulators': get_active_simulators(),
    }
    
    if request.headers.get('HX-Request'):
        if request.GET:
            return render(request, 'sim/profiles/profiles_results_partial.html', context)
        return render(request, 'sim/profiles/list_partial.html', context)
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
    """View individual profile details"""
    simulator = get_object_or_404(Simulator, slug=simulator_slug, is_active=True)
    
    # Generate cache key for public profiles
    cache_key = None
    if not request.user.is_authenticated:
        cache_key = CacheKeyManager.get_view_cache_key(
            'profile_detail',
            simulator_slug=simulator_slug,
            profile_identifier=profile_identifier
        )
        
        # Try to get from cache
        cached_response = cache.get(cache_key)
        if cached_response:
            return cached_response
    
    # Try to find the profile by sim_api_id first, then by profile_name
    profile = None
    try:
        profile = SimProfile.objects.select_related('simulator', 'linked_user').get(
            simulator=simulator,
            sim_api_id=profile_identifier,
            is_public=True
        )
    except SimProfile.DoesNotExist:
        # Fallback to profile_name if sim_api_id doesn't match
        try:
            profile = SimProfile.objects.select_related('simulator', 'linked_user').get(
                simulator=simulator,
                profile_name=profile_identifier,
                is_public=True
            )
        except SimProfile.DoesNotExist:
            raise Http404("Profile not found")
    
    # Get current ratings
    current_ratings = profile.ratings.select_related('rating_system').order_by('-recorded_at')[:6]
    
    # Get recent lap times
    recent_lap_times = profile.lap_times.select_related(
        'sim_layout__sim_track__track_model'
    ).order_by('-recorded_at')[:10]
    
    # Check if current user can link this profile
    can_link = False
    if request.user.is_authenticated:
        can_link = profile.can_user_link(request.user)
    
    context = {
        'profile': profile,
        'current_ratings': current_ratings,
        'recent_lap_times': recent_lap_times,
        'can_link': can_link,
    }
    
    response = render(request, 'sim/profiles/detail.html', context)
    
    # Cache the response for anonymous users viewing public profiles
    if cache_key and profile.is_public:
        cache.set(cache_key, response, 300)  # 5 minutes
    
    return response


@login_required
def profile_link(request, simulator_slug, profile_identifier):
    """Link a profile to the current user"""
    simulator = get_object_or_404(Simulator, slug=simulator_slug, is_active=True)
    
    # Try to find the profile by sim_api_id first, then by profile_name
    profile = None
    try:
        profile = SimProfile.objects.get(
            simulator=simulator,
            sim_api_id=profile_identifier
        )
    except SimProfile.DoesNotExist:
        # Fallback to profile_name if sim_api_id doesn't match
        try:
            profile = SimProfile.objects.get(
                simulator=simulator,
                profile_name=profile_identifier
            )
        except SimProfile.DoesNotExist:
            raise Http404("Profile not found")
    
    # Check if user can link this profile
    if not profile.can_user_link(request.user):
        messages.error(request, "This profile is already linked to another user.")
        return redirect('drivers:profile_detail', 
                       simulator_slug=simulator_slug, 
                       profile_identifier=profile_identifier)
    
    if request.method == 'POST':
        try:
            profile.link_to_user(request.user, verified=False)
            logger.info(f"[PROFILE LINK] Linking profile id: {profile.id} for user {request.user.id}")
            # Trigger iRacing owned content sync in the background
            sync_iracing_owned_content.delay(profile.id)
            messages.success(
                request, 
                f"Successfully linked {profile.simulator.name} profile: {profile.profile_name}. "
                "Please verify your ownership to complete the process. Owned content is being synced."
            )
            return redirect('drivers:profile_detail', 
                           simulator_slug=simulator_slug, 
                           profile_identifier=profile_identifier)
        except ValueError as e:
            messages.error(request, str(e))
    
    context = {
        'profile': profile,
        'action': 'link',
    }
    
    if request.htmx:
        return render(request, 'sim/profiles/link_confirm_partial.html', context)
    return render(request, 'sim/profiles/link_confirm.html', context)


@login_required
def profile_unlink(request, simulator_slug, profile_identifier):
    """Unlink a profile from the current user"""
    simulator = get_object_or_404(Simulator, slug=simulator_slug, is_active=True)
    
    # Try to find the profile by sim_api_id first, then by profile_name
    profile = None
    try:
        profile = SimProfile.objects.get(
            simulator=simulator,
            sim_api_id=profile_identifier,
            linked_user=request.user
        )
    except SimProfile.DoesNotExist:
        # Fallback to profile_name if sim_api_id doesn't match
        try:
            profile = SimProfile.objects.get(
                simulator=simulator,
                profile_name=profile_identifier,
                linked_user=request.user
            )
        except SimProfile.DoesNotExist:
            raise Http404("Profile not found or not linked to your account")
    
    if request.method == 'POST':
        profile_name = profile.profile_name
        simulator_name = profile.simulator.name
        profile.unlink_from_user()
        
        messages.success(
            request,
            f"Successfully unlinked {simulator_name} profile: {profile_name}"
        )
        return redirect('drivers:profile_detail', 
                       simulator_slug=simulator_slug, 
                       profile_identifier=profile_identifier)
    
    context = {
        'profile': profile,
        'action': 'unlink',
    }
    
    if request.htmx:
        return render(request, 'sim/profiles/link_confirm_partial.html', context)
    return render(request, 'sim/profiles/link_confirm.html', context)


@login_required
def profile_search_to_link(request):
    """Search profiles that can be linked to user account"""
    query = request.GET.get('q', '').strip()
    simulator_slug = request.GET.get('simulator', '')
    from_profile = request.GET.get('from_profile', '')
    
    profiles = SimProfile.objects.filter(
        is_public=True,
        linked_user__isnull=True  # Only show unlinked profiles
    ).select_related('simulator').order_by('-last_active', '-created_at')
    
    # Filter by search query
    if query:
        profiles = profiles.filter(
            Q(profile_name__icontains=query) |
            Q(sim_api_id__icontains=query)
        )
    
    # Filter by simulator
    if simulator_slug:
        simulator = get_object_or_404(Simulator, slug=simulator_slug, is_active=True)
        profiles = profiles.filter(simulator=simulator)
    
    # Pagination
    paginator = Paginator(profiles, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'simulators': Simulator.objects.filter(is_active=True),
        'query': query,
        'selected_simulator': simulator_slug,
        'from_profile': from_profile,
    }
    
    # If this is from profile management area, always return partials
    if from_profile or request.htmx:
        # If the target is search-results-container, we're updating search results only
        hx_target = request.headers.get('HX-Target', '')
        if 'search-results' in hx_target:
            return render(request, 'sim/profiles/search_results_partial.html', context)
        else:
            # Otherwise return the full partial template for profile management
            return render(request, 'sim/profiles/search_to_link_partial.html', context)
    
    # Non-HTMX request - return full page
    return render(request, 'sim/profiles/search_to_link.html', context)


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
    # Use cached queryset
    cars = get_all_cars_queryset()
    
    # Filtering
    simulator_slug = request.GET.get('simulator')
    car_class_slug = request.GET.get('class')
    manufacturer = request.GET.get('manufacturer')
    search_query = request.GET.get('q', '').strip()
    
    if simulator_slug:
        cars = cars.filter(sim_cars__simulator__slug=simulator_slug)
    
    # TODO: Update car class filtering to use new system
    # if car_class_slug:
    #     cars = cars.filter(car_class__slug=car_class_slug)
    
    if manufacturer:
        cars = cars.filter(manufacturer__iexact=manufacturer)
    
    if search_query:
        cars = cars.filter(
            Q(name__icontains=search_query) |
            Q(manufacturer__icontains=search_query) |
            Q(category__icontains=search_query)
        )
    
    # Get filter options
    simulators = Simulator.objects.filter(is_active=True).order_by('name')
    car_classes = CarClass.objects.order_by('name')
    manufacturers = CarModel.objects.values_list('manufacturer', flat=True).distinct().order_by('manufacturer')
    
    # Pagination
    paginator = Paginator(cars, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Annotate owned status
    owned_car_ids = set()
    if request.user.is_authenticated and hasattr(request.user, 'linked_sim_profiles') and request.user.linked_sim_profiles.exists():
        sim_profile = request.user.linked_sim_profiles.first()
        owned_car_ids = set(
            SimProfileCarOwnership.objects.filter(sim_profile=sim_profile)
            .values_list('sim_car__car_model_id', flat=True)
        )
    for car in page_obj:
        car.is_owned = car.id in owned_car_ids
        car.active_sim_cars = [sc for sc in list(getattr(car, 'sim_cars').all()) if sc.is_active]
    
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
    
    if request.htmx:
        # Distinguish between initial HTMX load and subsequent filter/pagination requests
        if request.GET:
            return render(request, 'sim/cars/cars_list_partial.html', context)
        return render(request, 'sim/cars/list_partial.html', context)
    return render(request, 'sim/cars/list.html', context)


def car_detail(request, car_slug):
    """Detailed view of a specific car"""
    car = get_object_or_404(
        CarModel.objects.prefetch_related(
            Prefetch(
                'sim_cars',
                queryset=SimCar.objects.select_related('simulator', 'pit_data').filter(is_active=True),
            )
        ),
        slug=car_slug
    )
    
    # Get related cars (same category or manufacturer)
    related_cars = CarModel.objects.filter(
        Q(category=car.category) | Q(manufacturer=car.manufacturer)
    ).exclude(
        id=car.id
    ).annotate(
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
    # Use cached queryset
    tracks = get_all_tracks_queryset()
    
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
    
    # Annotate owned status (if needed)
    owned_track_ids = set()
    if request.user.is_authenticated and hasattr(request.user, 'linked_sim_profiles') and request.user.linked_sim_profiles.exists():
        sim_profile = request.user.linked_sim_profiles.first()
        owned_track_ids = set(
            SimProfileCarOwnership.objects.filter(sim_profile=sim_profile)
            .values_list('sim_car__car_model_id', flat=True)
        )

    # Prefetch sim_tracks and their simulators in a single query for all tracks on the page, with caching
    track_ids = tuple(sorted(t.id for t in page_obj))
    cache_key = f"tracksimtracks:{'-'.join(str(tid) for tid in track_ids)}"
    sim_track_map = cache.get(cache_key)
    if sim_track_map is None:
        sim_track_map = {}
        sim_track_qs = SimTrack.objects.filter(track_model__in=track_ids).select_related('simulator')
        for st in sim_track_qs:
            sim_track_map.setdefault(st.track_model_id, []).append(st)
        cache.set(cache_key, sim_track_map, 600)  # 10 minutes

    for track in page_obj:
        track.is_owned = track.id in owned_track_ids
        prefetched_sim_tracks = sim_track_map.get(track.id, [])
        track._prefetched_sim_tracks = prefetched_sim_tracks
        track.active_sim_tracks = [st for st in prefetched_sim_tracks if st.is_active]
    
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
    
    if request.htmx:
        if request.GET:
            return render(request, 'sim/tracks/tracks_list_partial.html', context)
        return render(request, 'sim/tracks/list_partial.html', context)
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


@require_POST
@login_required
def refresh_iracing_owned_content(request):
    """HTMX endpoint to trigger iRacing owned content sync for the user's sim profile."""
    sim_profile_id = request.POST.get('sim_profile_id')
    if not sim_profile_id:
        return JsonResponse({'error': 'No sim_profile_id provided.'}, status=400)
    try:
        profile = SimProfile.objects.get(id=sim_profile_id, linked_user=request.user)
    except SimProfile.DoesNotExist:
        return JsonResponse({'error': 'SimProfile not found or not linked to user.'}, status=404)
    sync_iracing_owned_content.delay(profile.id)
    return render(request, 'sim/components/refresh_status.html', {'status': 'syncing'})


@cache_for_anonymous(timeout=900)  # 15 minutes
def events_list(request):
    """Public listing of all events"""
    events = get_events_queryset()
    
    # Apply search filter
    search_query = request.GET.get('q')
    if search_query:
        events = events.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(sim_layout__sim_track__track_model__name__icontains=search_query) |
            Q(sim_layout__name__icontains=search_query) |
            Q(series__name__icontains=search_query) |
            Q(organizing_club__name__icontains=search_query) |
            Q(organizing_user__username__icontains=search_query)
        )
    
    # Apply filters
    simulator_slug = request.GET.get('simulator')
    event_source = request.GET.get('source')
    status = request.GET.get('status')
    
    if simulator_slug:
        events = events.filter(simulator__slug=simulator_slug)
    
    if event_source:
        events = events.filter(event_source=event_source)
        
    if status:
        events = events.filter(status=status)
    
    # Pagination
    paginator = Paginator(events, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'simulators': get_active_simulators(),
        'event_sources': EventSource.choices,
        'event_statuses': EventStatus.choices,
        'current_filters': {
            'simulator': simulator_slug,
            'source': event_source,
            'status': status,
            'q': search_query,
        }
    }
    
    if request.headers.get('HX-Request'):
        # Check if this is a filter/pagination request (has query parameters)
        if request.GET:
            # Return only the events list partial for filter/pagination requests
            return render(request, 'sim/events/events_list_partial.html', context)
        else:
            # Return the full partial with filters for initial HTMX load
            return render(request, 'sim/events/list_partial.html', context)
    return render(request, 'sim/events/list.html', context)


@cache_for_anonymous(timeout=900)  # 15 minutes
def upcoming_events_list(request):
    """Public listing of upcoming events only"""
    from django.utils import timezone
    
    events = get_events_queryset()
    
    # Filter to only upcoming events (events with future instances)
    events = events.filter(
        instances__start_time__gt=timezone.now()
    ).distinct()
    
    # Apply search filter
    search_query = request.GET.get('q')
    if search_query:
        events = events.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(sim_layout__sim_track__track_model__name__icontains=search_query) |
            Q(sim_layout__name__icontains=search_query) |
            Q(series__name__icontains=search_query) |
            Q(organizing_club__name__icontains=search_query) |
            Q(organizing_user__username__icontains=search_query)
        )
    
    # Apply filters
    simulator_slug = request.GET.get('simulator')
    event_source = request.GET.get('source')
    status = request.GET.get('status')
    
    if simulator_slug:
        events = events.filter(simulator__slug=simulator_slug)
    
    if event_source:
        events = events.filter(event_source=event_source)
        
    if status:
        events = events.filter(status=status)
    
    # Check for dropdown mode (for club signup autocomplete)
    dropdown_mode = request.GET.get('dropdown') or request.POST.get('dropdown')
    
    if dropdown_mode:
        # For dropdown mode, only show results if there's a search query
        if not search_query or search_query.strip() == '':
            context = {
                'events': [],
                'search_query': search_query,
            }
            return render(request, 'sim/events/dropdown_results_partial.html', context)
        
        # For dropdown mode, limit results and return simple dropdown template
        events = events.select_related(
            'simulator', 'series', 'sim_layout__sim_track__track_model'
        ).prefetch_related('instances').order_by('instances__start_time')[:10]
        
        context = {
            'events': events,
            'search_query': search_query,
        }
        return render(request, 'sim/events/dropdown_results_partial.html', context)
    
    # Normal page mode - with pagination
    events = events.order_by('instances__start_time')
    paginator = Paginator(events, 24)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'simulators': get_active_simulators(),
        'event_sources': EventSource.choices,
        'event_statuses': EventStatus.choices,
        'current_filters': {
            'simulator': simulator_slug,
            'source': event_source,
            'status': status,
            'q': search_query,
        },
        'is_upcoming_view': True,  # Flag to indicate this is the upcoming view
    }
    
    if request.headers.get('HX-Request'):
        # Check if this is a filter/pagination request (has query parameters)
        if request.GET and not dropdown_mode:
            # Return only the events list partial for filter/pagination requests
            return render(request, 'sim/events/events_list_partial.html', context)
        else:
            # Return the full partial with filters for initial HTMX load
            return render(request, 'sim/events/list_partial.html', context)
    return render(request, 'sim/events/upcoming_list.html', context)


def event_detail(request, event_slug):
    """View individual event details"""
    # Generate cache key for public events
    cache_key = None
    if not request.user.is_authenticated:
        cache_key = CacheKeyManager.get_view_cache_key(
            'event_detail',
            event_slug=event_slug
        )
        
        # Try to get from cache
        cached_response = cache.get(cache_key)
        if cached_response:
            return cached_response
    
    event = get_object_or_404(
        Event.objects.select_related(
            'simulator',
            'series',
            'series__simulator',
            'sim_layout__sim_track__track_model',
            'organizing_club',
            'organizing_user'
        ).prefetch_related(
            'instances__weather_forecasts',
            'instances__result',
            'sessions',
            'classes',
            'classes__car_class'
        ),
        slug=event_slug,
        visibility__in=['PUBLIC', 'UNLISTED']
    )
    
    # Check if user can view this event
    if not event.can_user_view(request.user):
        raise Http404("Event not found")
    
    # Get upcoming instances
    upcoming_instances = event.instances.filter(
        start_time__gt=timezone.now()
    ).order_by('start_time')[:5]
    
    # Get recent/completed instances
    recent_instances = event.instances.filter(
        start_time__lte=timezone.now()
    ).order_by('-start_time')[:10]
    
    # Get weather data for next instance if available
    next_instance = upcoming_instances.first()
    weather_forecasts = []
    if next_instance:
        weather_forecasts = next_instance.weather_forecasts.order_by('timestamp')[:24]  # Next 24 hours
    
    # Check if current user can join this event
    can_join = False
    can_manage = False
    if request.user.is_authenticated:
        can_join = event.can_user_join(request.user)
        can_manage = event.can_user_manage(request.user)
    
    # Get series and season context if this is a series event
    series_context = None
    season_context = None
    race_week_context = None
    
    if event.series:
        series_context = event.series
        # Prefer explicit FK
        if event.race_week:
            race_week_context = event.race_week
            season_context = event.race_week.season
        else:
            # Derive via sim_layout
            race_weeks = (
                event.sim_layout.race_weeks
                .filter(season__series=event.series)
                .select_related('season')
                .order_by('-season__active', '-week_number')
            )
            if race_weeks.exists():
                race_week_context = race_weeks.first()
                season_context = race_week_context.season

    # Build per-class car + restriction data
    class_car_data = []
    for ec in event.classes.all():
        allowed_cars = list(ec.get_allowed_cars())
        restrictions_map = ec.get_bop_restrictions(race_week_context)
        entries = []
        for car in allowed_cars:
            entries.append({
                'car': car,
                'restrictions': restrictions_map.get(car.sim_api_id, {})
            })
        class_car_data.append({'event_class': ec, 'entries': entries})

    context = {
        'event': event,
        'upcoming_instances': upcoming_instances,
        'recent_instances': recent_instances,
        'next_instance': next_instance,
        'weather_forecasts': weather_forecasts,
        'can_join': can_join,
        'can_manage': can_manage,
        'series_context': series_context,
        'season_context': season_context,
        'race_week_context': race_week_context,
        'class_car_data': class_car_data,
    }
    
    response = render(request, 'sim/events/detail.html', context)
    
    # Cache the response for anonymous users
    if cache_key and not request.user.is_authenticated:
        cache.set(cache_key, response, timeout=900)  # 15 minutes
    
    return response



