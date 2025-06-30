from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.contrib import messages
from functools import wraps

from simlane.teams.decorators import club_member_required, club_admin_required, club_manager_required

def subscription_required(features=None, redirect_to_upgrade=True):
    """
    Decorator to ensure club has an active subscription with required features.
    
    Args:
        features (list): List of feature names required (e.g., ['race_planning'])
        redirect_to_upgrade (bool): Whether to redirect to upgrade page or show error
    """
    if features is None:
        features = []
    
    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            # First ensure we have a club context
            if not hasattr(request, 'club') or not request.club:
                return HttpResponseForbidden("Club context required")
            
            club = request.club
            
            # Get or create club subscription
            try:
                from simlane.billing.models import ClubSubscription
                subscription = ClubSubscription.objects.select_related('plan').get(
                    club=club,
                    status__in=['active', 'trialing']
                )
            except ClubSubscription.DoesNotExist:
                # No active subscription - assign to free plan or block access
                if redirect_to_upgrade:
                    messages.error(
                        request, 
                        "This feature requires an active subscription. Please upgrade your plan."
                    )
                    return HttpResponseRedirect(
                        reverse('billing:upgrade_required', kwargs={'club_slug': club.slug})
                    )
                else:
                    return HttpResponseForbidden(
                        "This feature requires an active subscription."
                    )
            
            # Check if subscription has required features
            if features:
                missing_features = []
                for feature in features:
                    if not subscription.has_feature(feature):
                        missing_features.append(feature)
                
                if missing_features:
                    if redirect_to_upgrade:
                        messages.error(
                            request,
                            f"Your current plan doesn't include: {', '.join(missing_features)}. "
                            "Please upgrade to access this feature."
                        )
                        return HttpResponseRedirect(
                            reverse('billing:upgrade_required', kwargs={'club_slug': club.slug})
                        )
                    else:
                        return HttpResponseForbidden(
                            f"Your subscription doesn't include required features: {', '.join(missing_features)}"
                        )
            
            # Add subscription context to request
            request.club_subscription = subscription
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def race_planning_required(view_func):
    """
    Decorator specifically for race planning functionality.
    Combines club membership check with race planning feature requirement.
    """
    @wraps(view_func)
    @club_member_required
    @subscription_required(features=['race_planning'])
    def wrapper(request, *args, **kwargs):
        return view_func(request, *args, **kwargs)
    
    return wrapper


def member_limit_enforced(view_func):
    """
    Decorator to prevent adding members beyond subscription limits.
    Should be used on views that add new club members.
    """
    @wraps(view_func)
    @club_admin_required
    def wrapper(request, *args, **kwargs):
        club = request.club
        
        # Get club subscription
        try:
            from simlane.billing.models import ClubSubscription
            subscription = ClubSubscription.objects.select_related('plan').get(
                club=club,
                status__in=['active', 'trialing']
            )
        except ClubSubscription.DoesNotExist:
            # No subscription - use free plan limits
            from simlane.billing.models import SubscriptionPlan
            try:
                free_plan = SubscriptionPlan.objects.get(name='Free')
                max_members = free_plan.max_members
            except SubscriptionPlan.DoesNotExist:
                max_members = 5  # Default free limit
        else:
            max_members = subscription.plan.max_members
        
        # Check current member count
        current_members = club.members.count()
        
        # For unlimited plans (max_members = -1 or None)
        if max_members is None or max_members < 0:
            # No limit - proceed with view
            request.club_subscription = getattr(request, 'club_subscription', subscription)
            return view_func(request, *args, **kwargs)
        
        # Check if adding a member would exceed limit
        # This is a simple check - for bulk operations, you might need more sophisticated logic
        if current_members >= max_members:
            messages.error(
                request,
                f"Your current plan allows up to {max_members} members. "
                f"You currently have {current_members} members. "
                "Please upgrade your plan to add more members."
            )
            return HttpResponseRedirect(
                reverse('billing:upgrade_required', kwargs={'club_slug': club.slug})
            )
        
        # Add subscription context and member info to request
        request.club_subscription = getattr(request, 'club_subscription', subscription)
        request.member_limit_info = {
            'current_members': current_members,
            'max_members': max_members,
            'can_add_members': current_members < max_members,
            'members_remaining': max_members - current_members
        }
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def subscription_admin_required(view_func):
    """
    Decorator for subscription management views.
    Ensures user is club admin and adds subscription context.
    """
    @wraps(view_func)
    @club_admin_required
    def wrapper(request, *args, **kwargs):
        club = request.club
        
        # Get or create club subscription
        try:
            from simlane.billing.models import ClubSubscription
            subscription = ClubSubscription.objects.select_related('plan').get(club=club)
        except ClubSubscription.DoesNotExist:
            # Create free subscription if none exists
            from simlane.billing.services import SubscriptionService
            service = SubscriptionService()
            subscription = service.assign_free_plan(club)
        
        # Add subscription context
        request.club_subscription = subscription
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def feature_enabled(feature_name):
    """
    Decorator to check if a specific feature is enabled for the club.
    More granular than subscription_required for optional features.
    """
    def decorator(view_func):
        @wraps(view_func)
        @club_member_required
        def wrapper(request, *args, **kwargs):
            club = request.club
            
            # Get club subscription
            try:
                from simlane.billing.models import ClubSubscription
                subscription = ClubSubscription.objects.select_related('plan').get(
                    club=club,
                    status__in=['active', 'trialing']
                )
            except ClubSubscription.DoesNotExist:
                # No subscription - check if feature is available in free plan
                from simlane.billing.models import SubscriptionPlan
                try:
                    free_plan = SubscriptionPlan.objects.get(name='Free')
                    if not free_plan.has_feature(feature_name):
                        # Feature not available in free plan
                        request.feature_available = False
                        request.feature_upgrade_required = True
                    else:
                        request.feature_available = True
                        request.feature_upgrade_required = False
                except SubscriptionPlan.DoesNotExist:
                    request.feature_available = False
                    request.feature_upgrade_required = True
            else:
                request.feature_available = subscription.has_feature(feature_name)
                request.feature_upgrade_required = not request.feature_available
                request.club_subscription = subscription
            
            # Always call the view - let the view decide how to handle unavailable features
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def api_subscription_required(features=None):
    """
    Decorator for API endpoints that require subscription features.
    Returns JSON error responses instead of redirects.
    """
    if features is None:
        features = []
    
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            from django.http import JsonResponse
            
            # Ensure we have a club context
            if not hasattr(request, 'club') or not request.club:
                return JsonResponse(
                    {'error': 'Club context required'}, 
                    status=400
                )
            
            club = request.club
            
            # Get club subscription
            try:
                from simlane.billing.models import ClubSubscription
                subscription = ClubSubscription.objects.select_related('plan').get(
                    club=club,
                    status__in=['active', 'trialing']
                )
            except ClubSubscription.DoesNotExist:
                return JsonResponse({
                    'error': 'Active subscription required',
                    'error_code': 'SUBSCRIPTION_REQUIRED',
                    'upgrade_url': reverse('billing:subscription_dashboard', kwargs={'club_slug': club.slug})
                }, status=402)  # Payment Required
            
            # Check required features
            if features:
                missing_features = []
                for feature in features:
                    if not subscription.has_feature(feature):
                        missing_features.append(feature)
                
                if missing_features:
                    return JsonResponse({
                        'error': f'Subscription plan missing required features: {", ".join(missing_features)}',
                        'error_code': 'FEATURE_NOT_AVAILABLE',
                        'missing_features': missing_features,
                        'current_plan': subscription.plan.name,
                        'upgrade_url': reverse('billing:subscription_dashboard', kwargs={'club_slug': club.slug})
                    }, status=402)  # Payment Required
            
            # Add subscription context
            request.club_subscription = subscription
            
            return view_func(request, *args, **kwargs)
        
        return wrapper
    return decorator


def check_member_limit(club, additional_members=1):
    """
    Utility function to check if club can add more members.
    Can be used in views that don't use the decorator.
    
    Args:
        club: Club instance
        additional_members: Number of members to add (default 1)
    
    Returns:
        tuple: (can_add: bool, message: str, current_count: int, limit: int)
    """
    try:
        from simlane.billing.models import ClubSubscription
        subscription = ClubSubscription.objects.select_related('plan').get(
            club=club,
            status__in=['active', 'trialing']
        )
        max_members = subscription.plan.max_members
    except ClubSubscription.DoesNotExist:
        # No subscription - use free plan limits
        from simlane.billing.models import SubscriptionPlan
        try:
            free_plan = SubscriptionPlan.objects.get(name='Free')
            max_members = free_plan.max_members
        except SubscriptionPlan.DoesNotExist:
            max_members = 5  # Default free limit
    
    current_members = club.members.count()
    
    # Unlimited plans
    if max_members is None or max_members < 0:
        return True, "No member limit", current_members, -1
    
    # Check if adding members would exceed limit
    if current_members + additional_members > max_members:
        return (
            False, 
            f"Adding {additional_members} member(s) would exceed your plan limit of {max_members}. "
            f"Current members: {current_members}",
            current_members,
            max_members
        )
    
    return (
        True, 
        f"Can add {additional_members} member(s). Current: {current_members}/{max_members}",
        current_members,
        max_members
    )


def subscription_context_processor(request):
    """
    Context processor to add subscription information to all templates.
    Add this to TEMPLATES['OPTIONS']['context_processors'] in settings.
    """
    context = {}
    
    if hasattr(request, 'club') and request.club:
        try:
            from simlane.billing.models import ClubSubscription
            subscription = ClubSubscription.objects.select_related('plan').get(
                club=request.club,
                status__in=['active', 'trialing']
            )
            context['club_subscription'] = subscription
            context['subscription_features'] = subscription.get_available_features()
            context['member_usage'] = {
                'current': request.club.members.count(),
                'limit': subscription.plan.max_members,
                'percentage': subscription.get_member_usage_percentage()
            }
        except ClubSubscription.DoesNotExist:
            context['club_subscription'] = None
            context['subscription_features'] = []
            context['member_usage'] = {
                'current': request.club.members.count(),
                'limit': 5,  # Free plan default
                'percentage': (request.club.members.count() / 5) * 100
            }
    
    return context