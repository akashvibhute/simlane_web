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
from django.http import Http404
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

    # ----------------------------------------------------------------------------------
    # Context helpers
    # ----------------------------------------------------------------------------------
    def _get_subscription_context(self) -> Dict[str, Any]:
        """Return subscription & member-usage information (mirrors existing logic)."""
        subscription_info = None
        member_usage_info = None
        subscription_features: list[Any] = []  # noqa: ANN401 – simplified typing

        try:
            from simlane.billing.models import ClubSubscription  # imported lazily

            subscription = ClubSubscription.objects.select_related("plan").get(
                club=self.club, status__in=["active", "trialing"]
            )
            subscription_info = {
                "plan": subscription.plan,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "seats_used": subscription.seats_used,
            }
            subscription_features = subscription.get_available_features()

            # member limits
            current_members = self.club.members.count()
            max_members = subscription.plan.max_members
            member_usage_info = {
                "current": current_members,
                "limit": max_members if max_members and max_members > 0 else "Unlimited",
                "percentage": subscription.get_member_usage_percentage()
                if max_members and max_members > 0
                else 0,
                "can_add_members": max_members is None
                or max_members < 0
                or current_members < max_members,
                "approaching_limit": max_members
                and max_members > 0
                and current_members >= (max_members * 0.8),
            }
        except Exception:  # noqa: BLE001 – any failure falls back to free defaults
            current_members = self.club.members.count()
            member_usage_info = {
                "current": current_members,
                "limit": 5,
                "percentage": (current_members / 5) * 100,
                "can_add_members": current_members < 5,
                "approaching_limit": current_members >= 4,
            }

        return {
            "subscription_info": subscription_info,
            "member_usage_info": member_usage_info,
            "subscription_features": subscription_features,
        }

    # ----------------------------------------------------------------------------------
    def get_common_context(self) -> Dict[str, Any]:
        return {
            "club": self.club,
            "user_role": getattr(self.club_member, "role", None),
            **self._get_subscription_context(),
        }

    def get_context_data(self, **kwargs):  # type: ignore[override]
        data = super().get_context_data(**kwargs)
        data.update(self.get_common_context())
        return data 