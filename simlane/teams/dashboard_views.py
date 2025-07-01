"""Class-based views for the revamped club dashboard.

Each view inherits `ClubContextMixin` for common lookups.
Only *Overview* is fully implemented for now; others can be
incrementally fleshed out but already return useful data.
"""
from __future__ import annotations

from typing import Any, Dict

from django.db import models
from django.urls import reverse
from django.views.generic import TemplateView
from django.core.paginator import Paginator

from simlane.teams.mixins import ClubContextMixin
from simlane.teams.models import ClubMember, Team, TeamMember, EventParticipation  # type: ignore


class OverviewView(ClubContextMixin, TemplateView):
    template_name = "teams/club_dashboard/overview.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        ctx = super().get_context_data(**kwargs)

        # Recent participations (same logic as old FBV, shortened)
        ctx["recent_entries"] = (
            EventParticipation.objects.filter(
                team__club=self.club,
                status__in=["confirmed", "participated"],
            )
            .select_related("event", "user", "assigned_car", "team")
            .order_by("-created_at")[:10]
        )

        # Teams that belong to this club (for sidebar counts)
        ctx["club_team_count"] = Team.objects.filter(
            club=self.club, is_active=True
        ).count()

        # Member + team counts for quick stats
        ctx["member_count"] = self.club.members.count()

        return ctx


class MembersView(ClubContextMixin, TemplateView):
    template_name = "teams/club_dashboard/members.html"

    def get_context_data(self, **kwargs):  # type: ignore[override]
        ctx = super().get_context_data(**kwargs)
        ctx["members"] = (
            ClubMember.objects.filter(club=self.club)
            .select_related("user")
            .order_by("-role", "user__username")
        )
        return ctx


class TeamsView(ClubContextMixin, TemplateView):
    template_name = "teams/club_dashboard/teams.html"

    def get_context_data(self, **kwargs):  # type: ignore[override]
        ctx = super().get_context_data(**kwargs)
        ctx["teams"] = Team.objects.filter(club=self.club, is_active=True).order_by(
            "name"
        )
        return ctx


class EventsView(ClubContextMixin, TemplateView):
    template_name = "teams/club_dashboard/events.html"

    def get_context_data(self, **kwargs):  # type: ignore[override]
        ctx = super().get_context_data(**kwargs)
        from simlane.sim.models import Event

        ctx["club_events"] = (
            Event.objects.filter(organizing_club=self.club)
            .select_related("sim_layout", "sim_layout__sim_track")
            .order_by("-created_at")
        )
        return ctx


# ---------------------------------------------------------------------------
# Admin-only sections
# ---------------------------------------------------------------------------


class AdminPermissionMixin:
    """Mixin requiring admin or teams_manager role."""

    def dispatch(self, request, *args, **kwargs):  # type: ignore[override]
        if getattr(self, "club_member", None) and self.club_member.role in (
            "admin",
            "teams_manager",
        ):
            return super().dispatch(request, *args, **kwargs)
        from django.http import HttpResponseForbidden

        return HttpResponseForbidden("Admins only")


class RequestsView(ClubContextMixin, AdminPermissionMixin, TemplateView):
    template_name = "teams/club_dashboard/requests.html"

    def get_context_data(self, **kwargs):  # type: ignore[override]
        ctx = super().get_context_data(**kwargs)
        from simlane.teams.models import ClubJoinRequest

        status_filter = self.request.GET.get("status", "all")

        qs = ClubJoinRequest.objects.filter(club=self.club).select_related(
            "user", "reviewed_by"
        ).order_by("-created_at")

        if status_filter != "all":
            qs = qs.filter(status=status_filter)

        paginator = Paginator(qs, 20)
        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        ctx.update(
            {
                "join_requests": page_obj.object_list,
                "page_obj": page_obj,
                "paginator": paginator,
                "is_paginated": page_obj.has_other_pages(),
                "status_filter": status_filter,
                "pending_requests_count": ClubJoinRequest.objects.filter(
                    club=self.club, status="pending"
                ).count(),
                "total_requests_count": qs.count() if status_filter == "all" else ClubJoinRequest.objects.filter(club=self.club).count(),
            }
        )
        return ctx


class DiscordSettingsView(ClubContextMixin, AdminPermissionMixin, TemplateView):
    template_name = "teams/club_dashboard/discord_settings.html"


class ClubSettingsView(ClubContextMixin, AdminPermissionMixin, TemplateView):
    template_name = "teams/club_dashboard/settings.html" 