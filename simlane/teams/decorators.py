from functools import wraps
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden, Http404
from django.shortcuts import get_object_or_404
from django.core.exceptions import PermissionDenied

from .models import Club, ClubMember, ClubRole, ClubEvent, TeamAllocation, ClubInvitation


def club_admin_required(view_func):
    """Decorator to ensure user is club admin (ClubRole.ADMIN)"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        # Try to get club from various sources
        club = None
        
        # Try club_slug first (new URL pattern)
        club_slug = kwargs.get('club_slug')
        if club_slug:
            try:
                club = Club.objects.get(slug=club_slug)
            except Club.DoesNotExist:
                raise Http404("Club not found")
        
        # Fallback to club_id (legacy support)
        if not club:
            club_id = kwargs.get('club_id') or request.POST.get('club_id')
            if club_id:
                try:
                    club = Club.objects.get(id=club_id)
                except Club.DoesNotExist:
                    raise Http404("Club not found")
        
        # Try to get from related objects if still not found
        if not club:
            # Try from signup_id
            signup_id = kwargs.get('signup_id')
            if signup_id:
                try:
                    club_event = ClubEvent.objects.select_related('club').get(id=signup_id)
                    club = club_event.club
                except ClubEvent.DoesNotExist:
                    raise Http404("Event not found")
        
        if not club:
            return HttpResponseForbidden("Club identifier required")
        
        try:
            club_member = ClubMember.objects.get(
                user=request.user,
                club=club,
                role=ClubRole.ADMIN
            )
        except ClubMember.DoesNotExist:
            return HttpResponseForbidden("You must be a club admin to access this page")
        
        # Add club_member to request for use in view
        request.club_member = club_member
        request.club = club
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def club_manager_required(view_func):
    """Decorator for admin or teams_manager roles"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        # Try to get club from various sources
        club = None
        
        # Try club_slug first (new URL pattern)
        club_slug = kwargs.get('club_slug')
        if club_slug:
            try:
                club = Club.objects.get(slug=club_slug)
            except Club.DoesNotExist:
                raise Http404("Club not found")
        
        # Fallback to club_id (legacy support)
        if not club:
            club_id = kwargs.get('club_id') or request.POST.get('club_id')
            if club_id:
                try:
                    club = Club.objects.get(id=club_id)
                except Club.DoesNotExist:
                    raise Http404("Club not found")
        
        # Try to get from related objects if still not found
        if not club:
            # Try from signup_id or event_id
            signup_id = kwargs.get('signup_id') or kwargs.get('event_id')
            if signup_id:
                try:
                    club_event = ClubEvent.objects.select_related('club').get(id=signup_id)
                    club = club_event.club
                except ClubEvent.DoesNotExist:
                    raise Http404("Event not found")
            
            # Try from allocation_id
            allocation_id = kwargs.get('allocation_id')
            if allocation_id:
                try:
                    allocation = TeamAllocation.objects.select_related('club_event__club').get(id=allocation_id)
                    club = allocation.club_event.club
                except TeamAllocation.DoesNotExist:
                    raise Http404("Allocation not found")
        
        if not club:
            return HttpResponseForbidden("Club identifier required")
        
        try:
            club_member = ClubMember.objects.get(
                user=request.user,
                club=club,
                role__in=[ClubRole.ADMIN, ClubRole.TEAMS_MANAGER]
            )
        except ClubMember.DoesNotExist:
            return HttpResponseForbidden("You must be a club admin or teams manager to access this page")
        
        request.club_member = club_member
        request.club = club
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def club_member_required(view_func):
    """Decorator to ensure user is club member (any role)"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        # Handle invitation token access first
        token = kwargs.get('token')
        if token:
            try:
                invitation = ClubInvitation.objects.select_related('club').get(
                    token=token,
                    accepted_at__isnull=True,
                    declined_at__isnull=True
                )
                # Allow access to view invitation details
                request.invitation = invitation
                request.club = invitation.club
                return view_func(request, *args, **kwargs)
            except ClubInvitation.DoesNotExist:
                raise Http404("Invalid invitation")
        
        # Try to get club from various sources
        club = None
        
        # Try club_slug first (new URL pattern)
        club_slug = kwargs.get('club_slug')
        if club_slug:
            try:
                club = Club.objects.get(slug=club_slug)
            except Club.DoesNotExist:
                raise Http404("Club not found")
        
        # Fallback to club_id (legacy support)
        if not club:
            club_id = kwargs.get('club_id') or request.POST.get('club_id')
            if club_id:
                try:
                    club = Club.objects.get(id=club_id)
                except Club.DoesNotExist:
                    raise Http404("Club not found")
        
        # Try to get from related objects if still not found
        if not club:
            # Try from signup_id or event_id
            signup_id = kwargs.get('signup_id') or kwargs.get('event_id')
            if signup_id:
                try:
                    club_event = ClubEvent.objects.select_related('club').get(id=signup_id)
                    club = club_event.club
                except ClubEvent.DoesNotExist:
                    raise Http404("Event not found")
        
        if not club:
            return HttpResponseForbidden("Club identifier required")
        
        try:
            club_member = ClubMember.objects.get(
                user=request.user,
                club=club
            )
        except ClubMember.DoesNotExist:
            return HttpResponseForbidden("You must be a club member to access this page")
        
        request.club_member = club_member
        request.club = club
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def event_signup_access(view_func):
    """Decorator for event signup permissions"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        signup_id = kwargs.get('signup_id') or kwargs.get('event_id')
        
        if not signup_id:
            return HttpResponseForbidden("Event ID required")
        
        try:
            club_event = ClubEvent.objects.select_related('club').get(id=signup_id)
        except ClubEvent.DoesNotExist:
            raise Http404("Event not found")
        
        # Check if user is club member
        try:
            club_member = ClubMember.objects.get(
                user=request.user,
                club=club_event.club
            )
        except ClubMember.DoesNotExist:
            return HttpResponseForbidden("You must be a club member to access this event")
        
        # Check if signup is open (for signup actions)
        if request.method == 'POST' and 'join' in request.path:
            if not club_event.is_signup_open:
                return HttpResponseForbidden("Event signup is closed")
        
        request.club_member = club_member
        request.club = club_event.club
        request.club_event = club_event
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def team_allocation_access(view_func):
    """Decorator for team allocation permissions"""
    @wraps(view_func)
    @login_required
    def wrapper(request, *args, **kwargs):
        allocation_id = kwargs.get('allocation_id')
        team_id = kwargs.get('team_id')
        
        if allocation_id:
            try:
                allocation = TeamAllocation.objects.select_related(
                    'team__club',
                    'club_event__club'
                ).get(id=allocation_id)
                club = allocation.club_event.club
                team = allocation.team
            except TeamAllocation.DoesNotExist:
                raise Http404("Allocation not found")
        elif team_id:
            try:
                from .models import Team
                team = Team.objects.select_related('club').get(id=team_id)
                club = team.club
                allocation = None
            except Team.DoesNotExist:
                raise Http404("Team not found")
        else:
            return HttpResponseForbidden("Team allocation ID required")
        
        # Check if user is team member or club manager
        try:
            club_member = ClubMember.objects.get(
                user=request.user,
                club=club
            )
            
            # For viewing, any club member can access
            # For modifying, need to be manager or admin
            if request.method == 'POST':
                if club_member.role not in [ClubRole.ADMIN, ClubRole.TEAMS_MANAGER]:
                    # Check if user is part of the team
                    from .models import TeamMember
                    if team and not TeamMember.objects.filter(team=team, user=request.user).exists():
                        return HttpResponseForbidden("You must be a team member or club manager to modify this allocation")
            
        except ClubMember.DoesNotExist:
            return HttpResponseForbidden("You must be a club member to access this allocation")
        
        request.club_member = club_member
        request.club = club
        if allocation:
            request.allocation = allocation
        if team:
            request.team = team
        
        return view_func(request, *args, **kwargs)
    
    return wrapper


def club_exists(view_func):
    """Simple decorator to ensure club exists and add to request"""
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        club_id = kwargs.get('club_id')
        if club_id:
            club = get_object_or_404(Club, id=club_id)
            request.club = club
        
        return view_func(request, *args, **kwargs)
    
    return wrapper 