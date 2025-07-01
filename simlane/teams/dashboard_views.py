"""
Club dashboard views using class-based views with HTMX support.
"""
import logging
from typing import Any, Dict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import models
from django.http import Http404, HttpResponseForbidden
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic import TemplateView

from simlane.billing.models import SubscriptionPlan
from simlane.teams.mixins import ClubContextMixin
from simlane.teams.models import (
    Club,
    ClubJoinRequest,
    ClubMember,
    Event,
    EventParticipation,
    Team,
)

logger = logging.getLogger(__name__)


class AdminPermissionMixin:
    """Mixin requiring admin or teams_manager role."""

    def dispatch(self, request, *args, **kwargs):
        # Get club context
        club_slug = kwargs.get('club_slug')
        if not club_slug:
            return HttpResponseForbidden("Club not specified.")
        
        try:
            club = Club.objects.get(slug=club_slug)
            if request.user.is_authenticated:
                club_member = ClubMember.objects.get(club=club, user=request.user)
                if club_member.role not in ('admin', 'teams_manager'):
                    return HttpResponseForbidden("Only club admins and teams managers can access this section.")
            else:
                return HttpResponseForbidden("Authentication required.")
        except (Club.DoesNotExist, ClubMember.DoesNotExist):
            return HttpResponseForbidden("Access denied.")
        
        return super().dispatch(request, *args, **kwargs)


class ClubDashboardView(ClubContextMixin, TemplateView):
    """Base view for club dashboard sections with HTMX support."""
    
    def get_template_names(self):
        """Return different templates based on whether it's an HTMX request."""
        if hasattr(self.request, 'htmx') and self.request.htmx:
            # HTMX request - return content partial
            return ['teams/club_dashboard_content_partial.html']
        else:
            # Regular request - return full page template
            return [self.template_name] if hasattr(self, 'template_name') else []


class OverviewView(ClubDashboardView):
    """Club dashboard overview view."""
    template_name = "teams/club_dashboard/overview.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add overview-specific context."""
        context = super().get_context_data(**kwargs)
        club = context['club']
        
        # Add active section for content partial
        context['active_section'] = 'overview'
        
        # Basic stats
        context['total_members'] = club.members.count()
        context['total_teams'] = club.teams.filter(is_active=True).count()
        
        # Get recent event signup sheets (if the relation exists)
        try:
            context['recent_signup_sheets'] = club.event_signup_sheets.select_related('event').order_by('-created_at')[:5]
        except AttributeError:
            context['recent_signup_sheets'] = []
        
        # Event entries count
        context['total_entries'] = EventParticipation.objects.filter(
            signup_context_club=club
        ).count()
        
        # Determine if user can manage events
        user_role = context.get('user_role')
        context['can_manage_events'] = user_role in ['admin', 'teams_manager']
        
        return context


class MembersView(ClubDashboardView):
    """Club members management view."""
    template_name = "teams/club_dashboard/members.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add members-specific context."""
        context = super().get_context_data(**kwargs)
        club = context['club']
        
        # Add active section for content partial
        context['active_section'] = 'members'
        
        # Get all club members with related data
        context['club_members'] = (
            club.members.select_related('user')
            .prefetch_related('user__team_members__team')
            .order_by('-created_at')
        )
        
        # Member stats for subscription limits
        context['member_count'] = club.members.count()
        
        # Check if user can manage members
        user_role = context.get('user_role')
        context['can_manage_members'] = user_role in ['admin', 'teams_manager']
        
        return context


class TeamsView(ClubDashboardView):
    """Club teams management view."""
    template_name = "teams/club_dashboard/teams.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add teams-specific context."""
        context = super().get_context_data(**kwargs)
        club = context['club']
        
        # Add active section for content partial
        context['active_section'] = 'teams'
        
        # Get all active teams with member counts
        context['teams'] = (
            club.teams.filter(is_active=True)
            .annotate(member_count=models.Count('members'))
            .prefetch_related('members__user')
            .order_by('name')
        )
        
        # Check if user can manage teams
        user_role = context.get('user_role')
        context['can_manage_teams'] = user_role in ['admin', 'teams_manager']
        
        return context


class EventsView(ClubDashboardView):
    """Club events management view."""
    template_name = "teams/club_dashboard/events.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add events-specific context."""
        context = super().get_context_data(**kwargs)
        club = context['club']
        
        # Add active section for content partial
        context['active_section'] = 'events'
        
        # Get tab from request (default to 'upcoming')
        events_tab = self.request.GET.get('tab', 'upcoming')
        context['events_tab'] = events_tab
        
        # Get signup sheets based on tab selection (if the relation exists)
        try:
            signup_sheets_qs = club.event_signup_sheets.select_related('event').annotate(
                signup_count=models.Count('event__participations', 
                                        filter=models.Q(event__participations__signup_context_club=club))
            )
            
            now = timezone.now()
            
            if events_tab == 'upcoming':
                context['signup_sheets'] = signup_sheets_qs.filter(
                    signup_opens__lte=now,
                    signup_closes__gt=now
                ).order_by('event__start_time')
            elif events_tab == 'ongoing':
                context['signup_sheets'] = signup_sheets_qs.filter(
                    event__start_time__lte=now,
                    event__end_time__gte=now
                ).order_by('event__start_time')
            elif events_tab == 'past':
                context['signup_sheets'] = signup_sheets_qs.filter(
                    event__end_time__lt=now
                ).order_by('-event__start_time')
            elif events_tab == 'drafts':
                context['signup_sheets'] = signup_sheets_qs.filter(
                    status='draft'
                ).order_by('-created_at')
            else:
                # Default to all
                context['signup_sheets'] = signup_sheets_qs.order_by('-event__start_time')
        except AttributeError:
            context['signup_sheets'] = []
        
        # Check if user can manage events
        user_role = context.get('user_role')
        context['can_manage_events'] = user_role in ['admin', 'teams_manager']
        
        return context


class AdminClubDashboardView(AdminPermissionMixin, ClubDashboardView):
    """Base view for admin-only club dashboard sections."""
    pass


class RequestsView(AdminClubDashboardView):
    """Club join requests management view (admin only)."""
    template_name = "teams/club_dashboard/requests.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add requests-specific context."""
        context = super().get_context_data(**kwargs)
        club = context['club']
        
        # Add active section for content partial
        context['active_section'] = 'requests'
        
        # Get status filter from request
        status_filter = self.request.GET.get('status', 'all')
        context['status_filter'] = status_filter
        
        # Get join requests based on filter
        requests_qs = club.join_requests.select_related('user').order_by('-created_at')
        
        if status_filter == 'pending':
            context['join_requests'] = requests_qs.filter(status='pending')
        elif status_filter == 'approved':
            context['join_requests'] = requests_qs.filter(status='approved')
        elif status_filter == 'rejected':
            context['join_requests'] = requests_qs.filter(status='rejected')
        else:
            context['join_requests'] = requests_qs
        
        # Request counts for tabs
        context['pending_requests_count'] = club.join_requests.filter(status='pending').count()
        context['total_requests_count'] = club.join_requests.count()
        
        return context


class DiscordSettingsView(AdminClubDashboardView):
    """Club Discord settings view (admin only)."""
    template_name = "teams/club_dashboard/discord.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add Discord-specific context."""
        context = super().get_context_data(**kwargs)
        club = context['club']
        
        # Add active section for content partial
        context['active_section'] = 'discord'
        
        # Get or create Discord settings for this club
        from simlane.discord.models import ClubDiscordSettings
        discord_settings, created = ClubDiscordSettings.objects.get_or_create(club=club)
        context['discord_settings'] = discord_settings
        
        # Discord connection status
        context['discord_connected'] = bool(club.discord_guild_id)
        
        # Fetch available Discord channels (if connected)
        available_channels = []
        if club.discord_guild_id:
            try:
                from simlane.discord.services import DiscordBotService
                import asyncio
                bot_service = DiscordBotService()
                channels_data = asyncio.run(
                    bot_service.list_channels(club.discord_guild_id)
                )
                # Keep only text channels and sort alphabetically by name
                available_channels = sorted(
                    (
                        c for c in channels_data
                        if 'text' in c.get('type', '')  # ChannelType.text or guild_text
                    ),
                    key=lambda c: c['name']
                )
            except Exception as fetch_err:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(
                    "Unable to fetch Discord channels for guild %s: %s",
                    club.discord_guild_id,
                    fetch_err,
                )
        
        context['available_channels'] = available_channels
        
        return context


class ClubSettingsView(AdminClubDashboardView):
    """Club settings view (admin only)."""
    template_name = "teams/club_dashboard/settings.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Add settings-specific context."""
        context = super().get_context_data(**kwargs)
        club = context['club']
        
        # Add active section for content partial
        context['active_section'] = 'settings'
        
        # Available subscription plans for upgrade/downgrade
        context['subscription_plans'] = SubscriptionPlan.objects.filter(
            is_active=True
        ).order_by('monthly_price')
        
        # Current subscription info (already in context from ClubContextMixin)
        
        return context


# === SETTINGS ACTION VIEWS ===

class UpdateBasicInfoView(AdminClubDashboardView):
    """Handle basic club info updates."""
    
    def post(self, request, *args, **kwargs):
        """Handle basic info form submission."""
        # TODO: Implement basic info update logic
        from django.http import JsonResponse
        return JsonResponse({'status': 'success', 'message': 'Basic info updated successfully'})


class UploadLogoView(AdminClubDashboardView):
    """Handle club logo uploads."""
    
    def post(self, request, *args, **kwargs):
        """Handle logo upload form submission."""
        # TODO: Implement logo upload logic
        from django.http import JsonResponse
        return JsonResponse({'status': 'success', 'message': 'Logo uploaded successfully'})


class RemoveBannerView(AdminClubDashboardView):
    """Handle club banner removal."""
    
    def delete(self, request, *args, **kwargs):
        """Handle banner removal."""
        # TODO: Implement banner removal logic
        from django.http import JsonResponse
        return JsonResponse({'status': 'success', 'message': 'Banner removed successfully'})


class UploadBannerView(AdminClubDashboardView):
    """Handle club banner uploads."""
    
    def post(self, request, *args, **kwargs):
        """Handle banner upload form submission."""
        # TODO: Implement banner upload logic
        from django.http import JsonResponse
        return JsonResponse({'status': 'success', 'message': 'Banner uploaded successfully'})


class UpdatePrivacySettingsView(AdminClubDashboardView):
    """Handle privacy settings updates."""
    
    def post(self, request, *args, **kwargs):
        """Handle privacy settings form submission."""
        # TODO: Implement privacy settings update logic
        from django.http import JsonResponse
        return JsonResponse({'status': 'success', 'message': 'Privacy settings updated successfully'})


class ArchiveClubView(AdminClubDashboardView):
    """Handle club archiving."""
    
    def post(self, request, *args, **kwargs):
        """Handle club archiving."""
        # TODO: Implement club archiving logic
        from django.http import JsonResponse
        return JsonResponse({'status': 'success', 'message': 'Club archived successfully'})


class DeleteClubView(AdminClubDashboardView):
    """Handle club deletion."""
    
    def delete(self, request, *args, **kwargs):
        """Handle club deletion."""
        # TODO: Implement club deletion logic
        from django.http import JsonResponse
        return JsonResponse({'status': 'success', 'message': 'Club deleted successfully'})


# === DISCORD ACTION VIEWS ===

class SyncDiscordRolesView(AdminClubDashboardView):
    """Handle Discord role synchronization."""
    
    def post(self, request, *args, **kwargs):
        """Handle Discord role sync."""
        # TODO: Implement Discord role sync logic
        from django.http import JsonResponse
        return JsonResponse({'status': 'success', 'message': 'Discord roles synced successfully'})


class RefreshDiscordChannelsView(AdminClubDashboardView):
    """Handle Discord channel refresh."""
    
    def post(self, request, *args, **kwargs):
        """Handle Discord channel refresh."""
        # Get club from context like other views
        context = self.get_context_data(**kwargs)
        club = context['club']
        
        # Get or create Discord settings
        from simlane.discord.models import ClubDiscordSettings
        discord_settings, created = ClubDiscordSettings.objects.get_or_create(club=club)
        
        # Fetch fresh channels from Discord
        available_channels = []
        if club.discord_guild_id:
            try:
                from simlane.discord.services import DiscordBotService
                import asyncio
                bot_service = DiscordBotService()
                channels_data = asyncio.run(
                    bot_service.list_channels(club.discord_guild_id)
                )
                available_channels = sorted(
                    (
                        c for c in channels_data
                        if 'text' in c.get('type', '')
                    ),
                    key=lambda c: c['name']
                )
            except Exception:
                pass  # Ignore errors for now
        
        # Return the updated form section
        from django.template.loader import render_to_string
        html = render_to_string('teams/club_dashboard/_discord_join_request_form.html', {
            'club': club,
            'discord_settings': discord_settings,
            'available_channels': available_channels,
            'request': request,
        })
        
        from django.http import HttpResponse
        return HttpResponse(html)


class UpdateDiscordChannelsView(AdminClubDashboardView):
    """Handle Discord channel configuration updates."""
    
    def post(self, request, *args, **kwargs):
        """Handle Discord channel updates."""
        # Get club from context like other views
        context = self.get_context_data(**kwargs)
        club = context['club']
        
        # Get or create Discord settings
        from simlane.discord.models import ClubDiscordSettings
        discord_settings, created = ClubDiscordSettings.objects.get_or_create(club=club)
        
        # Update all settings from form data
        
        # Join Request Settings
        discord_settings.enable_join_request_notifications = request.POST.get('enable_join_request_notifications') == 'on'
        discord_settings.join_requests_channel_id = request.POST.get('join_requests_channel_id', '')
        
        # Channel Creation Settings
        discord_settings.auto_create_channels = request.POST.get('auto_create_channels') == 'on'
        discord_settings.channel_naming_pattern = request.POST.get('channel_naming_pattern', '{series_name}-{event_name}')
        discord_settings.category_naming_pattern = request.POST.get('category_naming_pattern', '{series_name} Events')
        
        # Voice Channel Settings
        discord_settings.enable_voice_channels = request.POST.get('enable_voice_channels') == 'on'
        discord_settings.enable_practice_voice = request.POST.get('enable_practice_voice') == 'on'
        voice_limit = request.POST.get('voice_channel_user_limit', '0')
        discord_settings.voice_channel_user_limit = int(voice_limit) if voice_limit.isdigit() else 0
        
        # Team Formation Settings
        discord_settings.enable_team_formation_channels = request.POST.get('enable_team_formation_channels') == 'on'
        discord_settings.auto_create_team_threads = request.POST.get('auto_create_team_threads') == 'on'
        
        # Member Sync Settings
        discord_settings.auto_sync_members = request.POST.get('auto_sync_members') == 'on'
        sync_freq = request.POST.get('sync_frequency_hours', '24')
        discord_settings.sync_frequency_hours = int(sync_freq) if sync_freq.isdigit() else 24
        discord_settings.require_linked_account = request.POST.get('require_linked_account') == 'on'
        
        # Event Notification Settings
        discord_settings.enable_stint_alerts = request.POST.get('enable_stint_alerts') == 'on'
        discord_settings.enable_event_reminders = request.POST.get('enable_event_reminders') == 'on'
        signup_freq = request.POST.get('signup_update_frequency', '6')
        discord_settings.signup_update_frequency = int(signup_freq) if signup_freq.isdigit() else 6
        
        # Channel Cleanup Settings
        discord_settings.auto_archive_completed_events = request.POST.get('auto_archive_completed_events') == 'on'
        archive_delay = request.POST.get('archive_delay_hours', '24')
        discord_settings.archive_delay_hours = int(archive_delay) if archive_delay.isdigit() else 24
        delete_after = request.POST.get('delete_archived_after_days', '30')
        discord_settings.delete_archived_after_days = int(delete_after) if delete_after.isdigit() else 30
        
        # Role Mapping Settings (if included in form)
        discord_settings.auto_assign_roles = request.POST.get('auto_assign_roles') == 'on'
        discord_settings.admin_role_id = request.POST.get('admin_role_id', '')
        discord_settings.teams_manager_role_id = request.POST.get('teams_manager_role_id', '')
        discord_settings.member_role_id = request.POST.get('member_role_id', '')
        
        discord_settings.save()
        
        # Return success response for HTMX
        from django.http import JsonResponse
        return JsonResponse({
            'status': 'success', 
            'message': 'Discord settings updated successfully'
        })


class UpdateDiscordNotificationsView(AdminClubDashboardView):
    """Handle Discord notification settings updates."""
    
    def post(self, request, *args, **kwargs):
        """Handle Discord notification updates."""
        # TODO: Implement Discord notification update logic
        from django.http import JsonResponse
        return JsonResponse({'status': 'success', 'message': 'Discord notifications updated successfully'})


class UpdateDiscordRoleMappingView(AdminClubDashboardView):
    """Handle Discord role mapping updates."""
    
    def post(self, request, *args, **kwargs):
        """Handle Discord role mapping updates."""
        # TODO: Implement Discord role mapping update logic
        from django.http import JsonResponse
        return JsonResponse({'status': 'success', 'message': 'Discord role mapping updated successfully'})


class TestDiscordNotificationsView(AdminClubDashboardView):
    """Handle Discord notification testing."""
    
    def post(self, request, *args, **kwargs):
        """Handle Discord notification test."""
        # TODO: Implement Discord notification test logic
        from django.http import JsonResponse
        return JsonResponse({'status': 'success', 'message': 'Discord notification test sent successfully'})


class DisconnectDiscordView(AdminClubDashboardView):
    """Handle Discord disconnection."""
    
    def post(self, request, *args, **kwargs):
        """Handle Discord disconnection."""
        # TODO: Implement Discord disconnection logic
        from django.http import JsonResponse
        return JsonResponse({'status': 'success', 'message': 'Discord disconnected successfully'}) 