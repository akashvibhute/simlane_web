"""
Unfold Admin Configuration
"""
import json
from datetime import timedelta

from django.db.models import Count
from django.templatetags.static import static
from django.urls import reverse_lazy
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


# Unfold Configuration
UNFOLD = {
    "SITE_TITLE": "SimLane",
    "SITE_HEADER": "SimLane",
    "SITE_SUBHEADER": "SimLane",
    "SITE_DROPDOWN": [
        {
            "icon": "diamond",
            "title": _("SimLane"),
            "link": "https://simlane.app",
        },
    ],
    "SITE_URL": "/",
    "SITE_ICON": {
        "light": lambda request: static("icon.svg"),
        "dark": lambda request: static("icon.svg"),
    },
    "SITE_LOGO": {
        "light": lambda request: static("logo.svg"),
        "dark": lambda request: static("logo.svg"),
    },
    "SITE_FAVICONS": [
        {
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/svg+xml",
            "href": lambda request: static("favicon.ico"),
        },
    ],
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": True,
    "SHOW_BACK_BUTTON": False,
    "DASHBOARD_CALLBACK": "config.settings.unfold.dashboard_callback",
    "THEME": "dark",
    "BORDER_RADIUS": "6px",
    "COLORS": {
        "base": {
            "50": "249, 250, 251",
            "100": "243, 244, 246",
            "200": "229, 231, 235",
            "300": "209, 213, 219",
            "400": "156, 163, 175",
            "500": "107, 114, 128",
            "600": "75, 85, 99",
            "700": "55, 65, 81",
            "800": "31, 41, 55",
            "900": "17, 24, 39",
            "950": "3, 7, 18",
        },
        "primary": {
            "50": "250, 245, 255",
            "100": "243, 232, 255",
            "200": "233, 213, 255",
            "300": "216, 180, 254",
            "400": "192, 132, 252",
            "500": "168, 85, 247",
            "600": "147, 51, 234",
            "700": "126, 34, 206",
            "800": "107, 33, 168",
            "900": "88, 28, 135",
            "950": "59, 7, 100",
        },
        "font": {
            "subtle-light": "var(--color-base-500)",
            "subtle-dark": "var(--color-base-400)",
            "default-light": "var(--color-base-600)",
            "default-dark": "var(--color-base-300)",
            "important-light": "var(--color-base-900)",
            "important-dark": "var(--color-base-100)",
        },
    },
    "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,
        "navigation": [
            {
                "title": _("Dashboard"),
                "separator": True,
                "items": [
                    {
                        "title": _("Dashboard"),
                        "icon": "dashboard",
                        "link": reverse_lazy("admin:index"),
                    },
                ],
            },
            {
                "title": _("User Management"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Users"),
                        "icon": "people",
                        "link": reverse_lazy("admin:users_user_changelist"),
                    },
                    {
                        "title": _("Groups"),
                        "icon": "group",
                        "link": reverse_lazy("admin:auth_group_changelist"),
                    },
                ],
            },
            {
                "title": _("Core"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Contact Messages"),
                        "icon": "mail",
                        "link": reverse_lazy("admin:core_contactmessage_changelist"),
                    },
                ],
            },
            {
                "title": _("Simulation"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Simulators"),
                        "icon": "sports_esports",
                        "link": reverse_lazy("admin:sim_simulator_changelist"),
                    },
                    {
                        "title": _("Sim Profiles"),
                        "icon": "account_circle",
                        "link": reverse_lazy("admin:sim_simprofile_changelist"),
                    },
                    {
                        "title": _("Car Classes"),
                        "icon": "category",
                        "link": reverse_lazy("admin:sim_carclass_changelist"),
                    },
                    {
                        "title": _("Car Models"),
                        "icon": "directions_car",
                        "link": reverse_lazy("admin:sim_carmodel_changelist"),
                    },
                    {
                        "title": _("Sim Cars"),
                        "icon": "toys",
                        "link": reverse_lazy("admin:sim_simcar_changelist"),
                    },
                    {
                        "title": _("Track Models"),
                        "icon": "map",
                        "link": reverse_lazy("admin:sim_trackmodel_changelist"),
                    },
                    {
                        "title": _("Sim Tracks"),
                        "icon": "terrain",
                        "link": reverse_lazy("admin:sim_simtrack_changelist"),
                    },
                    {
                        "title": _("Sim Layouts"),
                        "icon": "route",
                        "link": reverse_lazy("admin:sim_simlayout_changelist"),
                    },
                    {
                        "title": _("Rating Systems"),
                        "icon": "star",
                        "link": reverse_lazy("admin:sim_ratingsystem_changelist"),
                    },
                    {
                        "title": _("Profile Ratings"),
                        "icon": "grade",
                        "link": reverse_lazy("admin:sim_profilerating_changelist"),
                    },
                ],
            },
            {
                "title": _("Events & Racing"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Series"),
                        "icon": "sports_motorsports",
                        "link": reverse_lazy("admin:sim_series_changelist"),
                    },
                    {
                        "title": _("Events"),
                        "icon": "event",
                        "link": reverse_lazy("admin:sim_event_changelist"),
                    },
                    {
                        "title": _("Event Sessions"),
                        "icon": "schedule",
                        "link": reverse_lazy("admin:sim_eventsession_changelist"),
                    },
                    {
                        "title": _("Event Classes"),
                        "icon": "class",
                        "link": reverse_lazy("admin:sim_eventclass_changelist"),
                    },
                    {
                        "title": _("Event Instances"),
                        "icon": "calendar_today",
                        "link": reverse_lazy("admin:sim_eventinstance_changelist"),
                    },
                    {
                        "title": _("Lap Times"),
                        "icon": "timer",
                        "link": reverse_lazy("admin:sim_laptime_changelist"),
                    },
                    {
                        "title": _("Pit Data"),
                        "icon": "build",
                        "link": reverse_lazy("admin:sim_pitdata_changelist"),
                    },
                    {
                        "title": _("Weather Forecast"),
                        "icon": "cloud",
                        "link": reverse_lazy("admin:sim_weatherforecast_changelist"),
                    },
                ],
            },
            {
                "title": _("Teams & Clubs"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Clubs"),
                        "icon": "groups",
                        "link": reverse_lazy("admin:teams_club_changelist"),
                    },
                    {
                        "title": _("Club Members"),
                        "icon": "person_add",
                        "link": reverse_lazy("admin:teams_clubmember_changelist"),
                    },
                    {
                        "title": _("Club Events"),
                        "icon": "event_note",
                        "link": reverse_lazy("admin:teams_clubevent_changelist"),
                    },
                    {
                        "title": _("Club Invitations"),
                        "icon": "mail_outline",
                        "link": reverse_lazy("admin:teams_clubinvitation_changelist"),
                    },
                    {
                        "title": _("Teams"),
                        "icon": "group_work",
                        "link": reverse_lazy("admin:teams_team_changelist"),
                    },
                    {
                        "title": _("Team Members"),
                        "icon": "people_outline",
                        "link": reverse_lazy("admin:teams_teammember_changelist"),
                    },
                    {
                        "title": _("Event Participation"),
                        "icon": "how_to_reg",
                        "link": reverse_lazy("admin:teams_eventparticipation_changelist"),
                    },
                    {
                        "title": _("Event Signup Invitations"),
                        "icon": "send",
                        "link": reverse_lazy("admin:teams_eventsignupinvitation_changelist"),
                    },
                    {
                        "title": _("Availability Windows"),
                        "icon": "access_time",
                        "link": reverse_lazy("admin:teams_availabilitywindow_changelist"),
                    },
                ],
            },
            {
                "title": _("Strategy & Planning"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Race Strategies"),
                        "icon": "psychology",
                        "link": reverse_lazy("admin:teams_racestrategy_changelist"),
                    },
                    {
                        "title": _("Stint Plans"),
                        "icon": "timeline",
                        "link": reverse_lazy("admin:teams_stintplan_changelist"),
                    },
                ],
            },
            {
                "title": _("Discord"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Discord Guilds"),
                        "icon": "forum",
                        "link": reverse_lazy("admin:discord_bot_discordguild_changelist"),
                    },
                    {
                        "title": _("Bot Commands"),
                        "icon": "smart_toy",
                        "link": reverse_lazy("admin:discord_bot_botcommand_changelist"),
                    },
                    {
                        "title": _("Bot Settings"),
                        "icon": "settings",
                        "link": reverse_lazy("admin:discord_bot_botsettings_changelist"),
                    },
                ],
            },
            {
                "title": _("Garage61"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Sync Logs"),
                        "icon": "sync",
                        "link": reverse_lazy("admin:garage61_garage61synclog_changelist"),
                    },
                ],
            },
            {
                "title": _("Authentication & Social"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Social Accounts"),
                        "icon": "account_box",
                        "link": reverse_lazy("admin:socialaccount_socialaccount_changelist"),
                    },
                    {
                        "title": _("Social Apps"),
                        "icon": "apps",
                        "link": reverse_lazy("admin:socialaccount_socialapp_changelist"),
                    },
                    {
                        "title": _("Social Tokens"),
                        "icon": "vpn_key",
                        "link": reverse_lazy("admin:socialaccount_socialtoken_changelist"),
                    },
                    {
                        "title": _("Email Addresses"),
                        "icon": "email",
                        "link": reverse_lazy("admin:account_emailaddress_changelist"),
                    },
                ],
            },
            {
                "title": _("Celery & Background Tasks"),
                "separator": True,
                "collapsible": True,
                "items": [
                    {
                        "title": _("Periodic Tasks"),
                        "icon": "schedule",
                        "link": reverse_lazy("admin:django_celery_beat_periodictask_changelist"),
                    },
                    {
                        "title": _("Cron Schedule"),
                        "icon": "access_time",
                        "link": reverse_lazy("admin:django_celery_beat_crontabschedule_changelist"),
                    },
                    {
                        "title": _("Interval Schedule"),
                        "icon": "timer",
                        "link": reverse_lazy("admin:django_celery_beat_intervalschedule_changelist"),
                    },
                    {
                        "title": _("Solar Schedule"),
                        "icon": "wb_sunny",
                        "link": reverse_lazy("admin:django_celery_beat_solarschedule_changelist"),
                    },
                    {
                        "title": _("Clocked Schedule"),
                        "icon": "alarm",
                        "link": reverse_lazy("admin:django_celery_beat_clockedschedule_changelist"),
                    },
                ],
            },
        ],
    },
}


def dashboard_callback(request, context):
    """
    Callback to prepare custom variables for index template which is used as dashboard
    template. It can be overridden in application by creating custom admin/index.html.
    """
    from simlane.core.models import ContactMessage
    from simlane.sim.models import Event, Series, SimProfile
    from simlane.teams.models import Club, EventParticipation, Team
    from simlane.users.models import User

    # Get date range for the last 30 days
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=30)

    # User signups per day for the last 30 days
    daily_signups = []
    daily_labels = []

    for i in range(30):
        date = start_date + timedelta(days=i)
        count = User.objects.filter(date_joined__date=date).count()
        daily_signups.append(count)
        daily_labels.append(date.strftime("%m/%d"))

    # Overall counts
    total_users = User.objects.count()
    total_clubs = Club.objects.count()
    total_teams = Team.objects.count()
    total_sim_profiles = SimProfile.objects.count()
    total_events = Event.objects.count()
    total_series = Series.objects.count()
    pending_contact_messages = ContactMessage.objects.filter(status="pending").count()

    # Recent activity
    recent_users = User.objects.order_by("-date_joined")[:5]
    recent_clubs = Club.objects.order_by("-created_at")[:5]
    recent_events = Event.objects.order_by("-created_at")[:5]

    # Event participation data for the last 30 days
    daily_participation = []
    daily_participation_labels = []

    for i in range(30):
        date = start_date + timedelta(days=i)
        count = EventParticipation.objects.filter(created_at__date=date).count()
        daily_participation.append(count)
        daily_participation_labels.append(date.strftime("%m/%d"))

    # Event participation by status
    participation_by_status = (
        EventParticipation.objects.values("status")
        .annotate(count=Count("id"))
        .order_by("status")
    )

    participation_status_labels = []
    participation_status_data = []
    status_colors = {
        "pending": "#f59e0b",  # amber
        "confirmed": "#10b981",  # emerald
        "declined": "#ef4444",  # red
        "waitlist": "#6b7280",  # gray
    }
    participation_status_colors = []

    for item in participation_by_status:
        status = item["status"]
        participation_status_labels.append(status.title())
        participation_status_data.append(item["count"])
        participation_status_colors.append(
            status_colors.get(status, "#9333ea")
        )  # default purple

    # User growth this month vs last month
    current_month_start = timezone.now().replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    last_month_start = (current_month_start - timedelta(days=1)).replace(day=1)

    current_month_users = User.objects.filter(
        date_joined__gte=current_month_start
    ).count()
    last_month_users = User.objects.filter(
        date_joined__gte=last_month_start, date_joined__lt=current_month_start
    ).count()

    growth_percentage = 0
    if last_month_users > 0:
        growth_percentage = (
            (current_month_users - last_month_users) / last_month_users
        ) * 100

    context.update(
        {
            # Chart data
            "daily_signups_data": json.dumps(daily_signups),
            "daily_signups_labels": json.dumps(daily_labels),
            "daily_participation_data": json.dumps(daily_participation),
            "daily_participation_labels": json.dumps(daily_participation_labels),
            "participation_status_data": json.dumps(participation_status_data),
            "participation_status_labels": json.dumps(participation_status_labels),
            "participation_status_colors": json.dumps(participation_status_colors),
            # Overall counts
            "total_users": total_users,
            "total_clubs": total_clubs,
            "total_teams": total_teams,
            "total_sim_profiles": total_sim_profiles,
            "total_events": total_events,
            "total_series": total_series,
            "pending_contact_messages": pending_contact_messages,
            "total_event_participation": EventParticipation.objects.count(),
            # Growth metrics
            "current_month_users": current_month_users,
            "last_month_users": last_month_users,
            "growth_percentage": round(growth_percentage, 1),
            # Recent activity
            "recent_users": recent_users,
            "recent_clubs": recent_clubs,
            "recent_events": recent_events,
        }
    )
    return context 