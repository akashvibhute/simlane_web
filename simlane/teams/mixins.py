"""Mixins for club dashboard CBVs.

This module is **new** and contains reusable building blocks so that each
section view stays tiny while core lookup / permission logic lives in one
place.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.generic.base import ContextMixin

from simlane.teams.models import Club, ClubMember

logger = logging.getLogger(__name__)


class ClubContextMixin(LoginRequiredMixin, ContextMixin):
    """Fetch the *club* by slug, expose common context & helper methods.

    Other dashboard views inherit this + a TemplateView or ListView.
    """

    club_lookup_url_kwarg = "club_slug"
    request: HttpRequest

    # ----------------------------------------------------------------------------------
    # dispatch / permission helpers
    # ----------------------------------------------------------------------------------
    def dispatch(self, request, *args, **kwargs):  # type: ignore[override]
        slug = kwargs.get(self.club_lookup_url_kwarg)
        if not slug:
            raise Http404("Club slug missing in URL")

        self.club = get_object_or_404(Club, slug=slug)

        # Permission – allow if club is public or user is member
        self.club_member = (
            ClubMember.objects.filter(club=self.club, user=request.user).first()
        )
        if not self.club_member and not self.club.is_public:
            raise PermissionDenied("This club is private. You must be a member to view it.")

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Enhanced context with all data needed for dashboard sections."""
        ctx = super().get_context_data(**kwargs)
        
        # Basic club and user info
        ctx.update({
            "club": self.club,
            "user_role": self.club_member.role if self.club_member else None,
            "is_public_view": self.club_member is None,
        })

        # Get subscription information for the club
        subscription_info = None
        member_usage_info = None
        subscription_features = []
        
        try:
            from simlane.billing.models import ClubSubscription
            subscription = ClubSubscription.objects.select_related('plan').get(
                club=self.club, 
                status__in=['active', 'trialing']
            )
            subscription_info = {
                'plan': subscription.plan,
                'status': subscription.status,
                'current_period_end': subscription.current_period_end,
                'seats_used': subscription.seats_used,
            }
            subscription_features = subscription.get_available_features()
            
            # Get member usage information
            current_members = self.club.members.count()
            max_members = subscription.plan.max_members
            member_usage_info = {
                'current': current_members,
                'limit': max_members if max_members and max_members > 0 else 'Unlimited',
                'percentage': subscription.get_member_usage_percentage() if max_members and max_members > 0 else 0,
                'can_add_members': max_members is None or max_members < 0 or current_members < max_members,
                'approaching_limit': max_members and max_members > 0 and current_members >= (max_members * 0.8),
            }
        except (ImportError, Exception):
            # Billing not available or no subscription - use free plan defaults
            current_members = self.club.members.count()
            member_usage_info = {
                'current': current_members,
                'limit': 5,  # Free plan default
                'percentage': (current_members / 5) * 100,
                'can_add_members': current_members < 5,
                'approaching_limit': current_members >= 4,
            }

        # Add subscription context
        ctx.update({
            'subscription_info': subscription_info,
            'member_usage_info': member_usage_info,
            'subscription_features': subscription_features,
            'race_planning_available': 'race_planning' in subscription_features,
        })

        # Get user's other clubs for navigation
        if self.request.user.is_authenticated:
            user_clubs = ClubMember.objects.filter(user=self.request.user).select_related("club")
            ctx['user_clubs'] = user_clubs
        else:
            ctx['user_clubs'] = []

        # Common counts for sidebar and overview
        ctx.update({
            'total_members': self.club.members.count(),
            'total_teams': self.club.teams.filter(is_active=True).count(),
        })

        # Check if user can manage events
        can_manage_events = False
        if self.club_member:
            can_manage_events = self.club_member.can_manage_events()
        ctx['can_manage_events'] = can_manage_events

        # Discord integration context
        discord_settings = None
        available_channels = []
        
        # Check if club has discord guild (using the discord_guild_id field)
        if self.club.discord_guild_id:
            try:
                from simlane.discord.models import ClubDiscordSettings
                discord_settings, _ = ClubDiscordSettings.objects.get_or_create(club=self.club)
                
                # Fetch available channels (simplified - may need async handling)
                try:
                    from simlane.discord.services import DiscordBotService
                    import asyncio
                    bot_service = DiscordBotService()
                    channels_data = asyncio.run(
                        bot_service.list_channels(self.club.discord_guild_id)
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
                    logger.warning(
                        "Unable to fetch Discord channels for guild %s: %s",
                        self.club.discord_guild_id,
                        fetch_err,
                    )
            except ImportError:
                pass  # Discord app not available

        ctx.update({
            'discord_settings': discord_settings,
            'available_channels': available_channels,
        })

        return ctx 