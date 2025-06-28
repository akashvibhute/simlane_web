import csv
import io
import secrets
import string
from datetime import timedelta

from django.db.models import Count
from django.utils.text import slugify

from .models import AvailabilityWindow
from .models import ClubInvitation
from .models import EventParticipation

# EventSignup and TeamAllocation imports removed - models no longer exist
# Functions using these models will need to be updated to use EventParticipation

# Token Generation and Validation


def generate_invitation_token() -> str:
    """Create secure invitation tokens"""
    # Generate a secure random token
    alphabet = string.ascii_letters + string.digits
    token = "".join(secrets.choice(alphabet) for _ in range(32))

    # Ensure uniqueness
    while ClubInvitation.objects.filter(token=token).exists():
        token = "".join(secrets.choice(alphabet) for _ in range(32))

    return token


def validate_invitation_token(token: str) -> tuple[bool, ClubInvitation | None, str]:
    """Verify token validity and expiry"""
    try:
        invitation = ClubInvitation.objects.get(token=token)

        if invitation.accepted_at:
            return False, invitation, "This invitation has already been accepted"

        if invitation.declined_at:
            return False, invitation, "This invitation has been declined"

        if invitation.is_expired():
            return False, invitation, "This invitation has expired"

        return True, invitation, "Valid invitation"

    except ClubInvitation.DoesNotExist:
        return False, None, "Invalid invitation token"


def generate_secure_slug(text: str, model_class, field_name: str = "slug") -> str:
    """Create URL-safe identifiers"""
    base_slug = slugify(text)
    slug = base_slug
    counter = 1

    # Ensure uniqueness
    while model_class.objects.filter(**{field_name: slug}).exists():
        slug = f"{base_slug}-{counter}"
        counter += 1

    return slug


# Team Allocation Algorithms


# Legacy utility functions removed - these depended on EventSignup model
# Functions: balance_teams_by_skill, optimize_car_distribution, calculate_availability_overlap, suggest_team_compositions
# These will need to be rewritten to use EventParticipation model


def suggest_team_compositions_enhanced(
    participations: list[EventParticipation], criteria: dict
) -> list[dict]:
    """AI-assisted team suggestions with multiple criteria"""
    suggestions = []

    # Extract criteria
    prioritize_skill = criteria.get("prioritize_skill", True)
    prioritize_availability = criteria.get("prioritize_availability", False)
    prioritize_experience = criteria.get("prioritize_experience", False)
    team_count = criteria.get("team_count", 2)

    # Score each signup
    scored_signups = []
    for signup in signups:
        score = 0

        if prioritize_skill:
            skill_rating = signup.get_skill_rating() or 1000
            score += skill_rating / 100  # Normalize to 0-50 range

        if prioritize_availability:
            total_time_slots = signup.club_event.base_event.time_slots.count()
            if total_time_slots > 0:
                score += (
                    signup.availabilities.filter(available=True).count()
                    / total_time_slots
                ) * 30

        if prioritize_experience:
            track_experience = signup.get_track_experience()
            if track_experience:
                score += min(track_experience.count(), 20)  # Cap at 20 points

        scored_signups.append(
            {
                "signup": signup,
                "score": score,
                "skill_rating": signup.get_skill_rating(),
                "availability_pct": signup.availabilities.filter(available=True).count()
                / max(1, signup.availabilities.count())
                * 100,
            },
        )

    # Sort by score
    scored_signups.sort(key=lambda x: x["score"], reverse=True)

    # Create balanced teams
    teams = [[] for _ in range(team_count)]
    team_scores = [0 for _ in range(team_count)]

    for scored in scored_signups:
        # Add to team with lowest total score for balance
        min_team_idx = team_scores.index(min(team_scores))
        teams[min_team_idx].append(scored)
        team_scores[min_team_idx] += scored["score"]

    # Format suggestions
    for i, team in enumerate(teams):
        avg_score = team_scores[i] / max(1, len(team))
        suggestions.append(
            {
                "team_number": i + 1,
                "members": team,
                "total_score": team_scores[i],
                "average_score": avg_score,
                "member_count": len(team),
            },
        )

    return suggestions


# Stint Planning Calculations


def calculate_stint_duration(
    event_length: timedelta,
    driver_count: int,
    pit_stops: int,
) -> int:
    """Calculate optimal stint lengths"""
    total_minutes = event_length.total_seconds() / 60

    # Account for pit stop time (assume 2 minutes per stop)
    driving_time = total_minutes - (pit_stops * 2)

    # Calculate stints needed
    total_stints = driver_count * 2  # Assume each driver does 2 stints

    # Base stint length
    stint_length = int(driving_time / total_stints)

    # Cap at reasonable limits
    stint_length = max(30, min(120, stint_length))

    return stint_length


def estimate_fuel_consumption(car, track, stint_duration: int) -> float:
    """Estimate fuel needs for a stint"""
    # This is a simplified calculation - in reality would use telemetry data

    # Base consumption rate (liters per minute)
    base_rate = 1.5

    # Track factors (longer tracks = higher average speed = more fuel)
    if track and hasattr(track, "length_km"):
        if track.length_km > 5:
            base_rate *= 1.2
        elif track.length_km < 3:
            base_rate *= 0.9

    # Car factors (if available)
    # In reality, would have car-specific consumption data

    return stint_duration * base_rate


def calculate_pit_windows(time_slot, pit_data) -> list[dict]:
    """Calculate optimal pit stop timing"""
    if not pit_data:
        return []

    duration = time_slot.end_time - time_slot.start_time
    total_minutes = duration.total_seconds() / 60

    # Fuel tank capacity (assumed)
    fuel_capacity = 100  # liters
    fuel_consumption_rate = 1.5  # liters per minute

    # Calculate stint length based on fuel
    fuel_stint_minutes = fuel_capacity / fuel_consumption_rate

    # Calculate number of stops needed
    stops_needed = int(total_minutes / fuel_stint_minutes)

    pit_windows = []
    for i in range(1, stops_needed + 1):
        window_center = i * fuel_stint_minutes

        # Calculate pit duration
        fuel_needed = min(fuel_capacity, fuel_capacity * 0.8)  # 80% refuel
        refuel_time = fuel_needed / pit_data.refuel_flow_rate

        pit_duration = pit_data.stop_go_base_loss_sec + refuel_time

        # Add tire change on even stops
        if i % 2 == 0:
            if pit_data.simultaneous_actions:
                pit_duration = max(
                    pit_duration,
                    pit_data.stop_go_base_loss_sec + pit_data.tire_change_all_four_sec,
                )
            else:
                pit_duration += pit_data.tire_change_all_four_sec

        pit_windows.append(
            {
                "stop_number": i,
                "window": {
                    "earliest": max(0, window_center - 10),
                    "optimal": window_center,
                    "latest": min(total_minutes, window_center + 10),
                },
                "fuel_needed": fuel_needed,
                "tire_change": i % 2 == 0,
                "estimated_duration": round(pit_duration, 1),
                "time_loss": round(pit_duration + pit_data.drive_through_loss_sec, 1),
            },
        )

    return pit_windows


def generate_driver_rotation(
    team_members: list,
    availability: dict,
    event_duration: int,
) -> list[dict]:
    """Create fair driver rotation schedule"""
    rotations = []

    # Get available drivers
    available_drivers = [m for m in team_members if m.event_signup.can_drive]

    if not available_drivers:
        return rotations

    # Calculate stint duration
    driver_count = len(available_drivers)
    stint_duration = calculate_stint_duration(
        timedelta(minutes=event_duration),
        driver_count,
        pit_stops=3,  # Assumed
    )

    # Create rotation
    current_time = 0
    stint_number = 1
    driver_index = 0

    while current_time < event_duration:
        driver = available_drivers[driver_index % driver_count]
        stint_end = min(current_time + stint_duration, event_duration)

        rotations.append(
            {
                "stint_number": stint_number,
                "driver": driver.event_signup.user,
                "start_minute": current_time,
                "end_minute": stint_end,
                "duration": stint_end - current_time,
            },
        )

        current_time = stint_end
        stint_number += 1
        driver_index += 1

    return rotations


# Data Export Utilities


def export_signup_data(club_event, format: str = "csv") -> io.BytesIO:
    """Export signup sheets as CSV/Excel"""
    output = io.BytesIO()

    if format == "csv":
        writer = csv.writer(io.TextIOWrapper(output, encoding="utf-8", newline=""))

        # Header
        writer.writerow(
            [
                "Username",
                "Email",
                "Experience Level",
                "Can Drive",
                "Can Spectate",
                "Preferred Cars",
                "Backup Cars",
                "Availability %",
                "Notes",
            ],
        )

        # Data
        for signup in club_event.signups.all():
            preferred_cars = ", ".join(str(car) for car in signup.preferred_cars.all())
            backup_cars = ", ".join(str(car) for car in signup.backup_cars.all())

            total_time_slots = signup.club_event.base_event.time_slots.count()
            available_time_slots = signup.availabilities.filter(available=True).count()
            availability_pct = (
                (available_time_slots / total_time_slots * 100)
                if total_time_slots > 0
                else 0
            )

            writer.writerow(
                [
                    signup.user.username,
                    signup.user.email,
                    signup.get_experience_level_display(),
                    "Yes" if signup.can_drive else "No",
                    "Yes" if signup.can_spectate else "No",
                    preferred_cars,
                    backup_cars,
                    f"{availability_pct:.0f}%",
                    signup.notes,
                ],
            )

    output.seek(0)
    return output


# Legacy functions removed - TeamAllocation model no longer exists
# These functions depended on the removed TeamAllocation model and are replaced
# by enhanced team formation system in views.py


def generate_stint_plan_pdf_enhanced(event_participation) -> io.BytesIO:
    """Create printable stint plans for enhanced participation system"""
    # TODO: Implement enhanced stint plan generation based on EventParticipation
    # and AvailabilityWindow models when stint planning is required
    output = io.BytesIO()
    output.write(b"Enhanced stint plan generation not yet implemented")
    output.seek(0)
    return output


def export_team_roster_enhanced(event_id) -> dict:
    """Generate team contact lists for enhanced participation system"""
    # TODO: Implement enhanced roster export based on EventParticipation model
    # when team rosters are required
    return {
        "message": "Enhanced team roster export not yet implemented",
        "event_id": event_id,
        "members": [],
    }


# Notification Helpers


def prepare_invitation_context(invitation: ClubInvitation) -> dict:
    """Email template context for invitations"""
    from django.conf import settings

    return {
        "invitation": invitation,
        "club": invitation.club,
        "inviter": invitation.invited_by,
        "role": invitation.get_role_display(),
        "personal_message": invitation.personal_message,
        "expires_at": invitation.expires_at,
        "accept_url": f"{settings.SITE_URL}/teams/invite/{invitation.token}/accept/",
        "decline_url": f"{settings.SITE_URL}/teams/invite/{invitation.token}/decline/",
        "site_name": settings.SITE_NAME,
        "support_email": settings.DEFAULT_FROM_EMAIL,
    }


def format_event_details(event) -> str:
    """Consistent event formatting for notifications"""
    details = f"Event: {event.name}\n"

    if hasattr(event, "sim_layout"):
        details += f"Track: {event.sim_layout.name}\n"

    if event.event_date:
        details += f"Date: {event.event_date.strftime('%B %d, %Y at %I:%M %p')}\n"

    if hasattr(event, "simulator"):
        details += f"Simulator: {event.simulator.name}\n"

    if hasattr(event, "type"):
        details += f"Type: {event.get_type_display()}\n"

    return details


def generate_notification_summary(club_event) -> dict:
    """Generate signup summary for emails"""
    signups = club_event.signups.all()

    summary = {
        "total_signups": signups.count(),
        "drivers": signups.filter(can_drive=True).count(),
        "spectators": signups.filter(can_spectate=True).count(),
        "signup_deadline": club_event.signup_deadline,
        "event_details": format_event_details(club_event.base_event),
        "status": club_event.get_status_display(),
    }

    # Experience breakdown
    experience_counts = signups.values("experience_level").annotate(count=Count("id"))
    summary["experience_breakdown"] = {
        item["experience_level"]: item["count"] for item in experience_counts
    }

    return summary


"""
Utility functions for team formation, availability analysis, and chart generation.
"""

from datetime import datetime
from datetime import timedelta
from typing import Any

import pytz
from django.contrib.auth import get_user_model
from django.utils import timezone

User = get_user_model()


class TimezoneUtils:
    """Utilities for timezone handling and conversion"""

    @staticmethod
    def convert_to_user_timezone(utc_datetime, user_timezone_str: str):
        """Convert UTC datetime to user's local timezone"""
        if not utc_datetime:
            return None

        user_tz = pytz.timezone(user_timezone_str)
        return utc_datetime.astimezone(user_tz)

    @staticmethod
    def convert_from_user_timezone(local_datetime, user_timezone_str: str):
        """Convert user's local datetime to UTC"""
        if not local_datetime:
            return None

        user_tz = pytz.timezone(user_timezone_str)
        if local_datetime.tzinfo is None:
            local_datetime = user_tz.localize(local_datetime)

        return local_datetime.astimezone(pytz.UTC)

    @staticmethod
    def get_common_timezones():
        """Get list of common timezones for dropdown"""
        return [
            "UTC",
            "US/Eastern",
            "US/Central",
            "US/Mountain",
            "US/Pacific",
            "Europe/London",
            "Europe/Paris",
            "Europe/Berlin",
            "Europe/Rome",
            "Australia/Sydney",
            "Australia/Melbourne",
            "Asia/Tokyo",
            "Asia/Singapore",
            "America/Sao_Paulo",
            "America/Mexico_City",
        ]

    @staticmethod
    def format_timezone_display(timezone_str: str) -> str:
        """Format timezone for user-friendly display"""
        try:
            tz = pytz.timezone(timezone_str)
            now = timezone.now()
            offset = now.astimezone(tz).strftime("%z")
            return f"{timezone_str} (UTC{offset[:3]}:{offset[3:]})"
        except:
            return timezone_str


class AvailabilityChartGenerator:
    """Generate charts and visualizations for availability data"""

    @staticmethod
    def generate_coverage_heatmap_data(
        event, timezone_display="UTC", resolution_hours=1
    ) -> dict[str, Any]:
        """Generate data for availability coverage heatmap"""
        import pytz

        display_tz = pytz.timezone(timezone_display)

        # Get all availability windows
        windows = (
            AvailabilityWindow.objects.filter(
                participation__event=event,
            )
            .select_related("participation__user")
            .order_by("start_time")
        )

        if not windows.exists():
            return {"data": [], "users": [], "time_slots": []}

        # Determine time range
        earliest = windows.first().start_time
        latest = windows.last().end_time

        # Round to hour boundaries
        start_time = earliest.replace(minute=0, second=0, microsecond=0)
        end_time = latest.replace(minute=0, second=0, microsecond=0) + timedelta(
            hours=1
        )

        # Get unique users
        users = list(
            User.objects.filter(
                event_participations__event=event,
            )
            .values("id", "username", "first_name", "last_name")
            .distinct()
        )

        # Generate time slots
        time_slots = []
        current_time = start_time
        while current_time < end_time:
            local_time = current_time.astimezone(display_tz)
            time_slots.append(
                {
                    "utc": current_time.isoformat(),
                    "local": local_time.isoformat(),
                    "display": local_time.strftime("%a %m/%d %H:%M"),
                }
            )
            current_time += timedelta(hours=resolution_hours)

        # Build heatmap data
        heatmap_data = []

        for user in users:
            user_windows = windows.filter(participation__user_id=user["id"])
            user_row = {
                "user": user,
                "availability": [],
            }

            for slot in time_slots:
                slot_start = datetime.fromisoformat(slot["utc"].replace("Z", "+00:00"))
                slot_end = slot_start + timedelta(hours=resolution_hours)

                # Check if user is available in this slot
                available_windows = user_windows.filter(
                    start_time__lt=slot_end,
                    end_time__gt=slot_start,
                )

                if available_windows.exists():
                    # Get the highest preference level (1 is best)
                    best_preference = min(w.preference_level for w in available_windows)
                    roles = set()
                    for w in available_windows:
                        if w.can_drive:
                            roles.add("driver")
                        if w.can_spot:
                            roles.add("spotter")
                        if w.can_strategize:
                            roles.add("strategist")

                    user_row["availability"].append(
                        {
                            "available": True,
                            "preference_level": best_preference,
                            "roles": list(roles),
                        }
                    )
                else:
                    user_row["availability"].append(
                        {
                            "available": False,
                            "preference_level": 0,
                            "roles": [],
                        }
                    )

            heatmap_data.append(user_row)

        return {
            "data": heatmap_data,
            "users": users,
            "time_slots": time_slots,
            "timezone": timezone_display,
        }

    @staticmethod
    def generate_team_overlap_chart(
        user_ids: list[int], event, timezone_display="UTC"
    ) -> dict[str, Any]:
        """Generate chart data for team member availability overlap"""
        overlaps = AvailabilityWindow.find_overlapping_availability(user_ids, event)

        # Build network-style data for D3.js or similar
        nodes = []
        links = []
        users = User.objects.filter(id__in=user_ids)

        for user in users:
            nodes.append(
                {
                    "id": user.id,
                    "name": user.get_full_name() or user.username,
                    "username": user.username,
                }
            )

        for overlap in overlaps:
            links.append(
                {
                    "source": overlap["user1_id"],
                    "target": overlap["user2_id"],
                    "value": overlap["total_overlap_hours"],
                    "overlap_windows": overlap["overlap_windows"],
                }
            )

        return {
            "nodes": nodes,
            "links": links,
            "timezone": timezone_display,
        }


class TeamFormationAlgorithms:
    """Advanced algorithms for team formation"""

    @staticmethod
    def greedy_team_formation(
        event, team_size: int = 3, max_teams: int = None
    ) -> list[list[int]]:
        """
        Greedy algorithm for team formation based on availability overlap.
        Returns list of teams (each team is a list of user IDs).
        """
        # Get all participants
        participants = list(
            EventParticipation.objects.filter(
                event=event,
                status="signed_up",
                participation_type="team_signup",
            ).values_list("user_id", flat=True)
        )

        if len(participants) < team_size:
            return []

        # Get all pairwise overlaps
        all_overlaps = AvailabilityWindow.find_overlapping_availability(
            participants, event
        )

        # Build adjacency matrix with overlap hours as weights
        overlap_matrix = {}
        for user_id in participants:
            overlap_matrix[user_id] = {}

        for overlap in all_overlaps:
            user1, user2 = overlap["user1_id"], overlap["user2_id"]
            hours = overlap["total_overlap_hours"]
            overlap_matrix[user1][user2] = hours
            overlap_matrix[user2][user1] = hours

        # Greedy team formation
        teams = []
        available_users = set(participants)

        while len(available_users) >= team_size:
            if max_teams and len(teams) >= max_teams:
                break

            # Find the pair with highest overlap
            best_pair = None
            best_score = 0

            for user1 in available_users:
                for user2 in available_users:
                    if user1 >= user2:  # Avoid duplicates
                        continue
                    score = overlap_matrix[user1].get(user2, 0)
                    if score > best_score:
                        best_score = score
                        best_pair = (user1, user2)

            if not best_pair:
                break

            # Start team with best pair
            current_team = list(best_pair)
            available_users.remove(best_pair[0])
            available_users.remove(best_pair[1])

            # Add more members to reach team_size
            while len(current_team) < team_size and available_users:
                best_addition = None
                best_addition_score = 0

                for candidate in available_users:
                    # Calculate average overlap with current team members
                    total_overlap = sum(
                        overlap_matrix[candidate].get(member, 0)
                        for member in current_team
                    )
                    avg_overlap = total_overlap / len(current_team)

                    if avg_overlap > best_addition_score:
                        best_addition_score = avg_overlap
                        best_addition = candidate

                if best_addition and best_addition_score > 0:
                    current_team.append(best_addition)
                    available_users.remove(best_addition)
                else:
                    break

            if len(current_team) == team_size:
                teams.append(current_team)

        return teams

    @staticmethod
    def balanced_team_formation(event, team_size: int = 3) -> list[dict[str, Any]]:
        """
        Create balanced teams considering both availability and skill/experience diversity.
        """
        participants = EventParticipation.objects.filter(
            event=event,
            status="signed_up",
            participation_type="team_signup",
        ).select_related("user")

        if participants.count() < team_size:
            return []

        # Get user experience levels
        experience_mapping = {
            "beginner": 1,
            "intermediate": 2,
            "advanced": 3,
            "professional": 4,
        }
        user_data = {}

        for p in participants:
            user_data[p.user_id] = {
                "user": p.user,
                "experience": experience_mapping.get(p.experience_level, 2),
                "max_stint": p.max_stint_duration or 60,
                "preferred_car": p.preferred_car,
            }

        # Get availability overlaps
        user_ids = list(user_data.keys())
        overlaps = AvailabilityWindow.find_overlapping_availability(user_ids, event)

        # Build teams using a more sophisticated approach
        teams = []
        remaining_users = set(user_ids)

        while len(remaining_users) >= team_size:
            # Find the most balanced team combination
            best_team = None
            best_balance_score = -1

            # Try different combinations (simplified for performance)
            from itertools import combinations

            for team_combo in combinations(remaining_users, team_size):
                # Calculate balance score
                team_list = list(team_combo)

                # Experience balance
                experiences = [user_data[uid]["experience"] for uid in team_list]
                exp_variance = TeamFormationAlgorithms._calculate_variance(experiences)

                # Availability overlap
                team_overlaps = [
                    o
                    for o in overlaps
                    if o["user1_id"] in team_list and o["user2_id"] in team_list
                ]
                avg_overlap = sum(
                    o["total_overlap_hours"] for o in team_overlaps
                ) / max(len(team_overlaps), 1)

                # Combined score (lower variance = better balance, higher overlap = better)
                balance_score = avg_overlap / max(
                    exp_variance, 0.1
                )  # Avoid division by zero

                if balance_score > best_balance_score:
                    best_balance_score = balance_score
                    best_team = team_list

            if best_team:
                team_info = {
                    "members": [user_data[uid]["user"] for uid in best_team],
                    "member_ids": best_team,
                    "balance_score": best_balance_score,
                    "average_experience": sum(
                        user_data[uid]["experience"] for uid in best_team
                    )
                    / len(best_team),
                    "total_overlap_hours": sum(
                        o["total_overlap_hours"]
                        for o in overlaps
                        if o["user1_id"] in best_team and o["user2_id"] in best_team
                    ),
                }
                teams.append(team_info)

                # Remove assigned users
                for uid in best_team:
                    remaining_users.remove(uid)
            else:
                break

        return teams

    @staticmethod
    def _calculate_variance(numbers: list[float]) -> float:
        """Calculate variance of a list of numbers"""
        if len(numbers) < 2:
            return 0

        mean = sum(numbers) / len(numbers)
        variance = sum((x - mean) ** 2 for x in numbers) / len(numbers)
        return variance


class AvailabilityConflictDetector:
    """Detect and resolve availability conflicts in team assignments"""

    @staticmethod
    def detect_stint_conflicts(
        team_members: list[int], proposed_stints: list[dict]
    ) -> list[dict]:
        """
        Detect conflicts between proposed stint assignments and member availability.

        Args:
            team_members: List of user IDs
            proposed_stints: List of dicts with 'user_id', 'start_time', 'end_time'

        Returns:
            List of conflict descriptions
        """
        conflicts = []

        for stint in proposed_stints:
            user_id = stint["user_id"]
            start_time = stint["start_time"]
            end_time = stint["end_time"]

            # Check if user is available during this time
            available_windows = AvailabilityWindow.objects.filter(
                participation__user_id=user_id,
                start_time__lte=start_time,
                end_time__gte=end_time,
                can_drive=True,
            )

            if not available_windows.exists():
                # Check partial availability
                partial_windows = AvailabilityWindow.objects.filter(
                    participation__user_id=user_id,
                    start_time__lt=end_time,
                    end_time__gt=start_time,
                    can_drive=True,
                )

                if partial_windows.exists():
                    conflicts.append(
                        {
                            "type": "partial_availability",
                            "user_id": user_id,
                            "stint_start": start_time,
                            "stint_end": end_time,
                            "available_windows": list(
                                partial_windows.values(
                                    "start_time",
                                    "end_time",
                                    "preference_level",
                                )
                            ),
                            "severity": "warning",
                        }
                    )
                else:
                    conflicts.append(
                        {
                            "type": "no_availability",
                            "user_id": user_id,
                            "stint_start": start_time,
                            "stint_end": end_time,
                            "severity": "error",
                        }
                    )

        return conflicts

    @staticmethod
    def suggest_alternative_stints(
        team_members: list[int], event, total_duration_hours: int
    ) -> list[dict]:
        """
        Suggest alternative stint arrangements that work better with availability.
        """
        # Get all availability windows for team members
        windows = AvailabilityWindow.objects.filter(
            participation__user_id__in=team_members,
            participation__event=event,
            can_drive=True,
        ).order_by("start_time")

        if not windows.exists():
            return []

        # Find the longest continuous periods where at least one driver is available
        continuous_periods = []

        for window in windows:
            # Find overlapping windows
            overlapping = windows.filter(
                start_time__lt=window.end_time,
                end_time__gt=window.start_time,
            ).exclude(id=window.id)

            period_start = window.start_time
            period_end = window.end_time
            available_drivers = [window.participation.user_id]

            # Extend period with overlapping windows
            for overlap_window in overlapping:
                if overlap_window.start_time < period_end:
                    period_end = max(period_end, overlap_window.end_time)
                    if overlap_window.participation.user_id not in available_drivers:
                        available_drivers.append(overlap_window.participation.user_id)

            continuous_periods.append(
                {
                    "start": period_start,
                    "end": period_end,
                    "duration_hours": (period_end - period_start).total_seconds()
                    / 3600,
                    "available_drivers": available_drivers,
                    "driver_count": len(available_drivers),
                }
            )

        # Merge overlapping periods and sort by driver availability
        merged_periods = []
        for period in sorted(continuous_periods, key=lambda x: x["start"]):
            if not merged_periods:
                merged_periods.append(period)
                continue

            last_period = merged_periods[-1]
            if period["start"] <= last_period["end"]:
                # Merge periods
                last_period["end"] = max(last_period["end"], period["end"])
                last_period["duration_hours"] = (
                    last_period["end"] - last_period["start"]
                ).total_seconds() / 3600
                # Combine available drivers
                all_drivers = set(
                    last_period["available_drivers"] + period["available_drivers"]
                )
                last_period["available_drivers"] = list(all_drivers)
                last_period["driver_count"] = len(all_drivers)
            else:
                merged_periods.append(period)

        # Sort by driver count (descending) and duration
        optimal_periods = sorted(
            merged_periods,
            key=lambda x: (x["driver_count"], x["duration_hours"]),
            reverse=True,
        )

        return optimal_periods[:3]  # Return top 3 suggestions


def calculate_team_chemistry_score(user_ids: list[int]) -> float:
    """
    Calculate a "chemistry" score for a potential team based on various factors.
    This is a placeholder for more sophisticated matching algorithms.
    """
    # For now, return a random score between 0.5 and 1.0
    # In a real implementation, this might consider:
    # - Past racing history together
    # - Communication preferences
    # - Racing style compatibility
    # - Geographic proximity (for timezone alignment)

    import random

    return 0.5 + (random.random() * 0.5)


def format_duration_hours(hours: float) -> str:
    """Format duration in hours to human-readable string"""
    if hours < 1:
        minutes = int(hours * 60)
        return f"{minutes}m"
    if hours < 24:
        return f"{hours:.1f}h"
    days = int(hours // 24)
    remaining_hours = hours % 24
    return f"{days}d {remaining_hours:.1f}h"


def get_user_display_name(user) -> str:
    """Get display name for user (full name or username)"""
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    if user.first_name:
        return user.first_name
    return user.username
