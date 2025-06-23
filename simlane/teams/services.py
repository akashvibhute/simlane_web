import logging
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Count
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

# Removed EmailService import - using Django's send_mail directly
from .models import Club
from .models import ClubEvent
from .models import ClubInvitation
from .models import ClubMember
from .models import EventEntry
from .models import EventSignup
from .models import EventSignupAvailability
from .models import StintAssignment
from .models import TeamAllocation
from .models import TeamAllocationMember

User = get_user_model()
logger = logging.getLogger(__name__)


class ClubInvitationService:
    """Handle club invitation workflow"""

    @staticmethod
    def send_invitation(
        club: Club,
        inviter: User,
        email: str,
        role: str,
        message: str = "",
    ) -> ClubInvitation:
        """Create and send invitation emails"""
        try:
            # Create invitation
            invitation = ClubInvitation.objects.create(
                club=club,
                email=email,
                invited_by=inviter,
                role=role,
                personal_message=message,
                token=ClubInvitation.generate_token(),
                expires_at=timezone.now() + timedelta(days=7),
            )

            # Prepare email context
            context = {
                "invitation": invitation,
                "club": club,
                "inviter": inviter,
                "personal_message": message,
                "accept_url": f"{settings.SITE_URL}/teams/invite/{invitation.token}/accept/",
                "decline_url": f"{settings.SITE_URL}/teams/invite/{invitation.token}/decline/",
            }

            # Send email
            subject = f"You're invited to join {club.name} on SimLane"
            html_message = render_to_string(
                "templates/emails/club_invitation.html",
                context,
            )
            text_message = strip_tags(html_message)

            send_mail(
                subject=subject,
                message=text_message,
                html_message=html_message,
                recipient_list=[email],
                from_email=settings.DEFAULT_FROM_EMAIL,
                fail_silently=False,
            )

            logger.info(f"Invitation sent to {email} for club {club.name}")
            return invitation

        except Exception as e:
            logger.error(f"Failed to send invitation: {e!s}")
            raise

    @staticmethod
    @transaction.atomic
    def accept_invitation(token: str, user: User) -> ClubMember:
        """Process invitation acceptance"""
        try:
            invitation = ClubInvitation.objects.select_for_update().get(
                token=token,
                accepted_at__isnull=True,
                declined_at__isnull=True,
            )

            if invitation.is_expired():
                raise ValueError("Invitation has expired")

            # Use the model's accept method
            club_member = invitation.accept(user)

            # Send notification to inviter
            ClubInvitationService._send_acceptance_notification(invitation, user)

            logger.info(
                f"User {user.username} accepted invitation to {invitation.club.name}",
            )
            return club_member

        except ClubInvitation.DoesNotExist:
            raise ValueError("Invalid or already used invitation")
        except Exception as e:
            logger.error(f"Failed to accept invitation: {e!s}")
            raise

    @staticmethod
    def decline_invitation(token: str) -> None:
        """Process invitation decline"""
        try:
            invitation = ClubInvitation.objects.get(
                token=token,
                accepted_at__isnull=True,
                declined_at__isnull=True,
            )

            invitation.decline()

            # Send notification to inviter
            ClubInvitationService._send_decline_notification(invitation)

            logger.info(f"Invitation to {invitation.club.name} was declined")

        except ClubInvitation.DoesNotExist:
            raise ValueError("Invalid or already used invitation")

    @staticmethod
    def cleanup_expired_invitations() -> int:
        """Remove expired invitations"""
        expired_count = ClubInvitation.objects.filter(
            expires_at__lt=timezone.now(),
            accepted_at__isnull=True,
            declined_at__isnull=True,
        ).delete()[0]

        logger.info(f"Cleaned up {expired_count} expired invitations")
        return expired_count

    @staticmethod
    def _send_acceptance_notification(invitation: ClubInvitation, user: User) -> None:
        """Send notification to inviter when invitation is accepted"""
        subject = f"{user.username} joined {invitation.club.name}"
        message = f"{user.username} has accepted your invitation to join {invitation.club.name}."

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.invited_by.email],
            fail_silently=False,
        )

    @staticmethod
    def _send_decline_notification(invitation: ClubInvitation) -> None:
        """Send notification to inviter when invitation is declined"""
        subject = f"Invitation to {invitation.club.name} was declined"
        message = f"The invitation sent to {invitation.email} was declined."

        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.invited_by.email],
            fail_silently=False,
        )


class EventSignupService:
    """Manage event signup workflows"""

    @staticmethod
    @transaction.atomic
    def create_signup_sheet(
        club: Club,
        event,
        creator: User,
        details: dict,
    ) -> ClubEvent:
        """Create new signup sheet"""
        club_event = ClubEvent.objects.create(
            club=club,
            base_event=event,
            created_by=creator,
            **details,
        )

        # Send notification to club members
        EventSignupService._notify_signup_open(club_event)

        logger.info(f"Created signup sheet for {club_event.title}")
        return club_event

    @staticmethod
    @transaction.atomic
    def process_member_signup(
        club_event: ClubEvent,
        user: User,
        preferences: dict,
        availability: list[dict],
    ) -> EventSignup:
        """Handle member signups"""
        # Create signup
        signup = EventSignup.objects.create(
            club_event=club_event,
            user=user,
            **preferences,
        )

        # Add car preferences
        if "preferred_cars" in preferences:
            signup.preferred_cars.set(preferences["preferred_cars"])
        if "backup_cars" in preferences:
            signup.backup_cars.set(preferences["backup_cars"])

        # Add availability
        for avail_data in availability:
            EventSignupAvailability.objects.create(
                signup=signup,
                **avail_data,
            )

        # Send confirmation
        EventSignupService._send_signup_confirmation(signup)

        logger.info(f"User {user.username} signed up for {club_event.title}")
        return signup

    @staticmethod
    def get_signup_summary(club_event_id: str) -> dict:
        """Generate signup statistics and summaries"""
        try:
            club_event = ClubEvent.objects.get(id=club_event_id)
            signups = club_event.signups.all()

            summary = {
                "total_signups": signups.count(),
                "driver_count": signups.filter(can_drive=True).count(),
                "spectator_count": signups.filter(can_spectate=True).count(),
                "experience_breakdown": list(
                    signups.values("experience_level").annotate(
                        count=Count("id"),
                    ),
                ),
                "car_preferences": {},
                "unique_cars_count": 0,
            }

            # Analyze car preferences
            unique_cars = set()
            for signup in signups.prefetch_related("preferred_cars"):
                for car in signup.preferred_cars.all():
                    unique_cars.add(car.id)
                    if car.id not in summary["car_preferences"]:
                        summary["car_preferences"][car.id] = {
                            "car": str(car),
                            "count": 0,
                        }
                    summary["car_preferences"][car.id]["count"] += 1

            summary["unique_cars_count"] = len(unique_cars)

            return summary
        except ClubEvent.DoesNotExist:
            logger.error(f"ClubEvent with id {club_event_id} not found")
            return {
                "total_signups": 0,
                "driver_count": 0,
                "spectator_count": 0,
                "experience_breakdown": [],
                "car_preferences": {},
                "unique_cars_count": 0,
            }

    @staticmethod
    @transaction.atomic
    def close_signup(club_event_id: str) -> None:
        """Close signup and prepare for team allocation"""
        club_event = ClubEvent.objects.get(id=club_event_id)
        club_event.status = "signup_closed"
        club_event.save()

        # Notify members that signup is closed
        EventSignupService._notify_signup_closed(club_event)

        logger.info(f"Closed signup for {club_event.title}")

    @staticmethod
    def _notify_signup_open(club_event: ClubEvent) -> None:
        """Notify club members when signup opens"""
        members = club_event.club.members.all()
        for member in members:
            # Send email notification
            subject = f"New event signup: {club_event.title}"
            context = {
                "club_event": club_event,
                "member": member,
                "signup_url": f"{settings.SITE_URL}/teams/signups/{club_event.id}/join/",
            }

            html_message = render_to_string("emails/event_signup_open.html", context)
            text_message = strip_tags(html_message)

            send_mail(
                subject=subject,
                message=text_message,
                html_message=html_message,
                recipient_list=[member.user.email],
                from_email=settings.DEFAULT_FROM_EMAIL,
                fail_silently=False,
            )

    @staticmethod
    def _send_signup_confirmation(signup: EventSignup) -> None:
        """Send confirmation email for signup"""
        subject = f"Signup confirmed: {signup.club_event.title}"
        context = {
            "signup": signup,
            "club_event": signup.club_event,
            "user": signup.user,
        }

        html_message = render_to_string(
            "emails/event_signup_confirmation.html",
            context,
        )
        text_message = strip_tags(html_message)

        send_mail(
            subject=subject,
            message=text_message,
            html_message=html_message,
            recipient_list=[signup.user.email],
            from_email=settings.DEFAULT_FROM_EMAIL,
            fail_silently=False,
        )

    @staticmethod
    def _notify_signup_closed(club_event: ClubEvent) -> None:
        """Notify participants when signup closes"""
        signups = club_event.signups.all()
        for signup in signups:
            subject = f"Signup closed: {club_event.title}"
            message = f"Signup for {club_event.title} is now closed. Team assignments will be announced soon."

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[signup.user.email],
                fail_silently=False,
            )


class TeamAllocationService:
    """Handle team splitting and allocation"""

    @staticmethod
    def suggest_team_allocations(
        club_event_id: str,
        criteria: dict | None = None,
    ) -> list[list[EventSignup]]:
        """AI-assisted team splitting based on availability, car preferences, and skill levels"""
        club_event = ClubEvent.objects.get(id=club_event_id)
        signups = list(club_event.signups.filter(can_drive=True))

        if not signups:
            return []

        # Calculate team count
        team_count = max(1, len(signups) // club_event.team_size_max)
        if len(signups) % club_event.team_size_max > club_event.team_size_min:
            team_count += 1

        # Get skill ratings and experience
        signup_data = []
        for signup in signups:
            skill_rating = signup.get_skill_rating() or 1000  # Default rating
            track_experience = signup.get_track_experience()
            lap_count = track_experience.count() if track_experience else 0

            signup_data.append(
                {
                    "signup": signup,
                    "skill_rating": skill_rating,
                    "lap_count": lap_count,
                    "availability_score": TeamAllocationService._calculate_availability_score(
                        signup,
                    ),
                    "car_preference_match": TeamAllocationService._calculate_car_preference_match(
                        signup,
                        club_event,
                    ),
                },
            )

        # Sort by skill rating
        signup_data.sort(key=lambda x: x["skill_rating"], reverse=True)

        # Distribute evenly across teams (snake draft style)
        teams = [[] for _ in range(team_count)]
        for i, data in enumerate(signup_data):
            if i // team_count % 2 == 0:
                # Forward pass
                team_idx = i % team_count
            else:
                # Reverse pass (snake draft)
                team_idx = team_count - 1 - (i % team_count)
            teams[team_idx].append(data["signup"])

        return teams

    @staticmethod
    @transaction.atomic
    def create_team_allocation(
        club_event_id: str,
        allocations: list[dict],
    ) -> list[TeamAllocation]:
        """Create team allocations from admin decisions"""
        club_event = ClubEvent.objects.get(id=club_event_id)
        created_allocations = []

        for allocation_data in allocations:
            # Create team allocation
            team_allocation = TeamAllocation.objects.create(
                club_event=club_event,
                team=allocation_data["team"],
                assigned_sim_car=allocation_data["assigned_car"],
                created_by=allocation_data["created_by"],
            )

            # Assign members
            for member_data in allocation_data["members"]:
                signup = member_data["signup"]
                TeamAllocationMember.objects.create(
                    team_allocation=team_allocation,
                    event_signup=signup,
                    role=member_data.get("role", "driver"),
                )

                # Update signup with team assignment
                signup.assigned_team = allocation_data["team"]
                signup.assigned_at = timezone.now()
                signup.save()

            created_allocations.append(team_allocation)

        # Send notifications
        TeamAllocationService._notify_team_assignments(club_event)

        return created_allocations

    @staticmethod
    def validate_allocation(allocation_data: dict) -> tuple[bool, list[str]]:
        """Ensure allocations meet event requirements"""
        errors = []

        # Check team size constraints
        member_count = len(allocation_data.get("members", []))
        club_event = allocation_data.get("club_event")

        if club_event:
            if member_count < club_event.team_size_min:
                errors.append(
                    f"Team must have at least {club_event.team_size_min} members",
                )
            if member_count > club_event.team_size_max:
                errors.append(f"Team cannot exceed {club_event.team_size_max} members")

        # Check if all members can drive
        drivers = sum(
            1 for m in allocation_data.get("members", []) if m["signup"].can_drive
        )
        if drivers == 0:
            errors.append("Team must have at least one driver")

        return len(errors) == 0, errors

    @staticmethod
    @transaction.atomic
    def finalize_allocations(club_event_id: str) -> None:
        """Convert allocations to actual EventEntry records"""
        club_event = ClubEvent.objects.get(id=club_event_id)
        allocations = club_event.allocations.all()

        for allocation in allocations:
            # Create EventEntry for the team
            event_entry = EventEntry.objects.create(
                event=club_event.base_event,
                sim_car=allocation.assigned_sim_car,
                team=allocation.team,
            )

            # Create driver availabilities
            for member in allocation.members.all():
                signup = member.event_signup
                for availability in signup.availabilities.all():
                    if availability.available:
                        DriverAvailability.objects.create(
                            event_entry=event_entry,
                            user=signup.user,
                            instance=availability.event_instance,
                            available=True,
                        )

        club_event.status = "teams_assigned"
        club_event.save()

        logger.info(f"Finalized allocations for {club_event.title}")

    @staticmethod
    def _calculate_availability_score(signup: EventSignup) -> float:
        """Calculate how available a driver is across all instances"""
        total_instances = signup.club_event.base_event.instances.count()
        available_instances = signup.availabilities.filter(available=True).count()

        return available_instances / total_instances if total_instances > 0 else 0

    @staticmethod
    def _calculate_car_preference_match(
        signup: EventSignup,
        club_event: ClubEvent,
    ) -> float:
        """Calculate how well driver's car preferences match available cars"""
        # This is a simplified version - could be enhanced with more complex matching
        preferred_cars = set(signup.preferred_cars.all())
        available_cars = set(club_event.base_event.sim_cars.all())

        if not preferred_cars:
            return 0.5  # Neutral score if no preferences

        matches = preferred_cars & available_cars
        return len(matches) / len(preferred_cars)

    @staticmethod
    def _notify_team_assignments(club_event: ClubEvent) -> None:
        """Notify members of their team assignments"""
        signups = club_event.signups.filter(assigned_team__isnull=False)

        for signup in signups:
            subject = f"Team assignment: {club_event.title}"
            context = {
                "signup": signup,
                "club_event": club_event,
                "team": signup.assigned_team,
                "planning_url": f"{settings.SITE_URL}/teams/allocations/{signup.assigned_team.id}/planning/",
            }

            html_message = render_to_string(
                "emails/team_allocation_notification.html",
                context,
            )
            text_message = strip_tags(html_message)

            send_mail(
                subject=subject,
                message=text_message,
                html_message=html_message,
                recipient_list=[signup.user.email],
                from_email=settings.DEFAULT_FROM_EMAIL,
                fail_silently=False,
            )


class StintPlanningService:
    """Generate stint plans and pit strategies"""

    @staticmethod
    def generate_stint_plan(
        team_allocation: TeamAllocation,
        event_instance,
    ) -> list[StintAssignment]:
        """Create initial stint assignments"""
        # Get team members who can drive
        drivers = team_allocation.members.filter(
            event_signup__can_drive=True,
        ).select_related("event_signup__user")

        if not drivers:
            return []

        # Get event duration
        duration = event_instance.end_time - event_instance.start_time
        total_minutes = int(duration.total_seconds() / 60)

        # Calculate stint length based on driver count
        driver_count = drivers.count()
        avg_stint_length = min(
            120,
            max(30, total_minutes // (driver_count * 2)),
        )  # 2 stints per driver

        # Generate stints
        stints = []
        current_time = event_instance.start_time
        stint_number = 1
        driver_index = 0

        while current_time < event_instance.end_time:
            driver = drivers[driver_index % driver_count]
            stint_end = min(
                current_time + timedelta(minutes=avg_stint_length),
                event_instance.end_time,
            )

            stint = StintAssignment(
                team_strategy=team_allocation.strategy,  # Assumes strategy exists
                driver=driver.event_signup.user,
                stint_number=stint_number,
                estimated_start_time=current_time,
                estimated_end_time=stint_end,
                estimated_duration_minutes=int(
                    (stint_end - current_time).total_seconds() / 60,
                ),
                role="primary_driver",
            )
            stints.append(stint)

            current_time = stint_end
            stint_number += 1
            driver_index += 1

        return stints

    @staticmethod
    def calculate_pit_windows(event_instance, sim_car) -> list[dict]:
        """Use PitData to suggest optimal pit stops"""
        if not sim_car.pit_data:
            return []

        pit_data = sim_car.pit_data
        duration = event_instance.end_time - event_instance.start_time
        total_minutes = duration.total_seconds() / 60

        # Simple calculation - would be more complex in reality
        # Assume fuel tank lasts 60 minutes
        fuel_stint_length = 60
        pit_stops_needed = int(total_minutes / fuel_stint_length)

        pit_windows = []
        for i in range(1, pit_stops_needed + 1):
            window_center = i * fuel_stint_length
            pit_windows.append(
                {
                    "lap_estimate": i * 40,  # Rough estimate
                    "time_window": {
                        "earliest": window_center - 5,
                        "latest": window_center + 5,
                        "optimal": window_center,
                    },
                    "fuel_needed": 60,  # Liters
                    "tire_change": i % 2 == 0,  # Change tires every other stop
                    "estimated_duration": StintPlanningService._calculate_pit_duration(
                        pit_data,
                        60,
                        i % 2 == 0,
                    ),
                },
            )

        return pit_windows

    @staticmethod
    def optimize_driver_rotation(
        team_allocation: TeamAllocation,
        availability: dict,
    ) -> list[StintAssignment]:
        """Balance driving time based on availability"""
        # This is a placeholder for more complex optimization
        # Could use linear programming or other optimization techniques
        return StintPlanningService.generate_stint_plan(
            team_allocation,
            team_allocation.club_event.base_event.instances.first(),
        )

    @staticmethod
    def export_stint_plan(team_allocation: TeamAllocation) -> dict:
        """Generate exportable stint plan"""
        stints = team_allocation.strategy.stint_assignments.all().order_by(
            "stint_number",
        )

        plan = {
            "team": str(team_allocation.team),
            "event": str(team_allocation.club_event),
            "car": str(team_allocation.assigned_sim_car),
            "stints": [],
        }

        for stint in stints:
            plan["stints"].append(
                {
                    "number": stint.stint_number,
                    "driver": stint.driver.username,
                    "start": stint.estimated_start_time.isoformat(),
                    "end": stint.estimated_end_time.isoformat(),
                    "duration": stint.estimated_duration_minutes,
                    "pit_entry": stint.pit_entry_planned,
                    "fuel_load": stint.fuel_load_start,
                    "tire_compound": stint.tire_compound,
                },
            )

        return plan

    @staticmethod
    def _calculate_pit_duration(
        pit_data,
        fuel_amount: float,
        tire_change: bool,
    ) -> float:
        """Calculate total pit stop duration"""
        duration = 0

        # Refuel time
        if fuel_amount > 0:
            duration += fuel_amount / pit_data.refuel_flow_rate

        # Tire change time
        if tire_change:
            if pit_data.simultaneous_actions and fuel_amount > 0:
                # Tires and fuel at same time
                duration = max(duration, pit_data.tire_change_all_four_sec)
            else:
                # Sequential
                duration += pit_data.tire_change_all_four_sec

        # Add base loss time
        duration += pit_data.stop_go_base_loss_sec

        return duration


class NotificationService:
    """Handle email and future Discord notifications"""

    @staticmethod
    def send_invitation_email(invitation: ClubInvitation) -> None:
        """Send club invitation emails"""
        ClubInvitationService.send_invitation(
            invitation.club,
            invitation.invited_by,
            invitation.email,
            invitation.role,
            invitation.personal_message,
        )

    @staticmethod
    def send_signup_confirmation(signup: EventSignup) -> None:
        """Confirm event signup"""
        EventSignupService._send_signup_confirmation(signup)

    @staticmethod
    def send_team_allocation_notification(allocation: TeamAllocation) -> None:
        """Notify members of team assignments"""
        for member in allocation.members.all():
            subject = f"Team assignment: {allocation.team.name}"
            context = {
                "member": member,
                "team": allocation.team,
                "event": allocation.club_event,
                "car": allocation.assigned_sim_car,
            }

            html_message = render_to_string(
                "emails/team_allocation_notification.html",
                context,
            )
            text_message = strip_tags(html_message)

            send_mail(
                subject=subject,
                message=text_message,
                html_message=html_message,
                recipient_list=[member.event_signup.user.email],
                from_email=settings.DEFAULT_FROM_EMAIL,
                fail_silently=False,
            )

    @staticmethod
    def send_stint_plan_update(team_allocation: TeamAllocation) -> None:
        """Notify team of stint plan changes"""
        members = team_allocation.members.all()

        for member in members:
            subject = f"Stint plan updated: {team_allocation.club_event.title}"
            message = f"The stint plan for {team_allocation.team.name} has been updated. Please review your assignments."

            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[member.event_signup.user.email],
                fail_silently=False,
            )
