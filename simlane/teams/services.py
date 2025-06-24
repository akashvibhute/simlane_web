"""
Business logic services for the unified event participation system.
Handles team formation, availability management, and workflow orchestration.
"""

import logging
from datetime import timedelta
from typing import List, Dict, Any, Optional, Tuple
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction, connection
from django.db.models import Count
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags
from django.core.exceptions import ValidationError

# from simlane.core.services import EmailService
from simlane.sim.models import Event, EventInstance, SimCar, EventClass
from simlane.users.models import User
from .models import (
    EventParticipation, 
    AvailabilityWindow, 
    EventSignupInvitation,
    Team, 
    ClubEvent,
    # TeamAllocation removed - replaced by enhanced participation system
    Club
)

User = get_user_model()
logger = logging.getLogger(__name__)


class EventParticipationService:
    """Service for managing event participation workflows"""

    @staticmethod
    def create_individual_entry(event, user, car=None, **kwargs):
        """Create direct individual event entry"""
        with transaction.atomic():
            participation = EventParticipation.objects.create(
                event=event,
                user=user,
                participation_type='individual',
                status='entered',
                preferred_car=car,
                participant_timezone=kwargs.get('timezone', user.timezone if hasattr(user, 'timezone') else 'UTC'),
                entered_at=timezone.now(),
                **kwargs
            )
            return participation

    @staticmethod
    def create_team_signup(event, user, club_event=None, invitation=None, **preferences):
        """Create team event signup (Phase 1)"""
        with transaction.atomic():
            participation = EventParticipation.objects.create(
                event=event,
                user=user,
                participation_type='team_signup',
                status='signed_up',
                club_event=club_event,
                signup_invitation=invitation,
                participant_timezone=preferences.get('timezone', user.timezone if hasattr(user, 'timezone') else 'UTC'),
                preferred_car=preferences.get('preferred_car'),
                backup_car=preferences.get('backup_car'),
                experience_level=preferences.get('experience_level', 'intermediate'),
                max_stint_duration=preferences.get('max_stint_duration'),
                min_rest_duration=preferences.get('min_rest_duration'),
                notes=preferences.get('notes', ''),
                signed_up_at=timezone.now()
            )
            
            # Add preferred classes if provided
            if preferences.get('preferred_classes'):
                participation.preferred_classes.set(preferences['preferred_classes'])
            
            return participation

    @staticmethod
    def assign_participants_to_team(participant_ids: List[int], team: Team, assigned_by: User):
        """Assign multiple participants to a team (Phase 2)"""
        with transaction.atomic():
            participants = EventParticipation.objects.filter(
                id__in=participant_ids,
                status='signed_up',
                participation_type='team_signup'
            )
            
            if not participants.exists():
                raise ValidationError("No valid participants found for team assignment")
            
            assigned_participants = []
            for participation in participants:
                participation.assign_to_team(team, assigned_by)
                assigned_participants.append(participation)
            
            return assigned_participants

    @staticmethod
    def create_team_entry(team: Team, event: Event, car: SimCar, **kwargs):
        """Create team entry (Phase 3)"""
        with transaction.atomic():
            participation = EventParticipation.objects.create(
                event=event,
                team=team,
                participation_type='team_entry',
                status='entered',
                assigned_car=car,
                assigned_class=kwargs.get('event_class'),
                car_number=kwargs.get('car_number'),
                entered_at=timezone.now()
            )
            return participation

    @staticmethod
    def get_participation_summary(event: Event) -> Dict[str, Any]:
        """Get comprehensive participation summary for an event"""
        participations = EventParticipation.objects.filter(event=event)
        
        summary = {
            'total_participants': participations.count(),
            'by_type': {},
            'by_status': {},
            'team_signups_ready': 0,
            'confirmed_entries': 0,
            'availability_coverage': {}
        }
        
        # Count by type and status
        for participation in participations:
            summary['by_type'][participation.participation_type] = summary['by_type'].get(participation.participation_type, 0) + 1
            summary['by_status'][participation.status] = summary['by_status'].get(participation.status, 0) + 1
        
        # Count signups ready for team formation
        summary['team_signups_ready'] = participations.filter(
            participation_type='team_signup',
            status='signed_up'
        ).count()
        
        # Count confirmed entries
        summary['confirmed_entries'] = participations.filter(
            status__in=['confirmed', 'entered']
        ).count()
        
        return summary


class AvailabilityService:
    """Service for managing availability windows and timezone handling"""

    @staticmethod
    def create_availability_window(participation: EventParticipation, 
                                 start_time_local, end_time_local, 
                                 timezone_str: str, **preferences):
        """Create availability window with timezone conversion"""
        import pytz
        
        # Convert local times to UTC
        user_tz = pytz.timezone(timezone_str)
        start_utc = user_tz.localize(start_time_local).astimezone(pytz.UTC)
        end_utc = user_tz.localize(end_time_local).astimezone(pytz.UTC)
        
        window = AvailabilityWindow.objects.create(
            participation=participation,
            start_time=start_utc,
            end_time=end_utc,
            can_drive=preferences.get('can_drive', True),
            can_spot=preferences.get('can_spot', True),
            can_strategize=preferences.get('can_strategize', False),
            preference_level=preferences.get('preference_level', 3),
            max_consecutive_stints=preferences.get('max_consecutive_stints', 1),
            preferred_stint_length=preferences.get('preferred_stint_length'),
            notes=preferences.get('notes', '')
        )
        
        return window

    @staticmethod
    def bulk_create_availability(participation: EventParticipation, 
                               availability_data: List[Dict], 
                               timezone_str: str):
        """Create multiple availability windows efficiently"""
        import pytz
        
        user_tz = pytz.timezone(timezone_str)
        windows = []
        
        for data in availability_data:
            start_utc = user_tz.localize(data['start_time_local']).astimezone(pytz.UTC)
            end_utc = user_tz.localize(data['end_time_local']).astimezone(pytz.UTC)
            
            windows.append(AvailabilityWindow(
                participation=participation,
                start_time=start_utc,
                end_time=end_utc,
                can_drive=data.get('can_drive', True),
                can_spot=data.get('can_spot', True),
                can_strategize=data.get('can_strategize', False),
                preference_level=data.get('preference_level', 3),
                max_consecutive_stints=data.get('max_consecutive_stints', 1),
                preferred_stint_length=data.get('preferred_stint_length'),
                notes=data.get('notes', '')
            ))
        
        return AvailabilityWindow.objects.bulk_create(windows)

    @staticmethod
    def get_availability_conflicts(event: Event, target_start, target_end) -> List[Dict]:
        """Find availability conflicts for stint assignment"""
        conflicts = []
        
        # Find overlapping windows where users are NOT available for driving
        unavailable_windows = AvailabilityWindow.objects.filter(
            participation__event=event,
            start_time__lt=target_end,
            end_time__gt=target_start,
            can_drive=False
        ).select_related('participation__user')
        
        for window in unavailable_windows:
            conflicts.append({
                'user': window.participation.user,
                'reason': 'Not available for driving',
                'window_start': window.start_time,
                'window_end': window.end_time,
                'available_roles': window.get_roles_list()
            })
        
        return conflicts

    @staticmethod
    def generate_coverage_report(event: Event, timezone_display='UTC') -> Dict[str, Any]:
        """Generate comprehensive availability coverage report"""
        import pytz
        
        display_tz = pytz.timezone(timezone_display)
        windows = AvailabilityWindow.objects.filter(
            participation__event=event
        ).select_related('participation__user').order_by('start_time')
        
        # Group by hour for coverage analysis
        coverage = {}
        total_participants = EventParticipation.objects.filter(event=event).count()
        
        for window in windows:
            start_hour = window.start_time.replace(minute=0, second=0, microsecond=0)
            end_hour = window.end_time.replace(minute=0, second=0, microsecond=0)
            
            current_hour = start_hour
            while current_hour <= end_hour:
                hour_key = current_hour.astimezone(display_tz).strftime('%Y-%m-%d %H:00')
                
                if hour_key not in coverage:
                    coverage[hour_key] = {
                        'drivers': 0,
                        'spotters': 0,
                        'strategists': 0,
                        'total_available': 0,
                        'users': set()
                    }
                
                if window.can_drive:
                    coverage[hour_key]['drivers'] += 1
                if window.can_spot:
                    coverage[hour_key]['spotters'] += 1
                if window.can_strategize:
                    coverage[hour_key]['strategists'] += 1
                
                coverage[hour_key]['users'].add(window.participation.user.id)
                current_hour += timedelta(hours=1)
        
        # Convert sets to counts and calculate percentages
        for hour_data in coverage.values():
            hour_data['total_available'] = len(hour_data['users'])
            hour_data['coverage_percentage'] = (hour_data['total_available'] / total_participants * 100) if total_participants > 0 else 0
            hour_data['users'] = list(hour_data['users'])  # Convert set to list for JSON serialization
        
        return {
            'total_participants': total_participants,
            'hourly_coverage': coverage,
            'timezone': timezone_display
        }


class TeamFormationService:
    """Service for intelligent team formation using availability analysis"""

    @staticmethod
    def analyze_compatibility(event: Event, user_ids: List[int]) -> Dict[str, Any]:
        """Analyze compatibility between potential team members"""
        overlaps = AvailabilityWindow.find_overlapping_availability(user_ids, event, min_overlap_hours=1)
        
        compatibility_matrix = {}
        total_overlap_by_user = {}
        
        for overlap in overlaps:
            user1, user2 = overlap['user1_id'], overlap['user2_id']
            overlap_hours = overlap['total_overlap_hours']
            
            # Build compatibility matrix
            if user1 not in compatibility_matrix:
                compatibility_matrix[user1] = {}
            if user2 not in compatibility_matrix:
                compatibility_matrix[user2] = {}
            
            compatibility_matrix[user1][user2] = overlap_hours
            compatibility_matrix[user2][user1] = overlap_hours
            
            # Track total overlap per user
            total_overlap_by_user[user1] = total_overlap_by_user.get(user1, 0) + overlap_hours
            total_overlap_by_user[user2] = total_overlap_by_user.get(user2, 0) + overlap_hours
        
        return {
            'compatibility_matrix': compatibility_matrix,
            'total_overlap_by_user': total_overlap_by_user,
            'pairwise_overlaps': overlaps
        }

    @staticmethod
    def suggest_optimal_teams(event: Event, team_size: int = 3, max_teams: int = None) -> List[Dict]:
        """Generate optimal team suggestions using advanced algorithms"""
        participants = EventParticipation.objects.filter(
            event=event,
            status='signed_up',
            participation_type='team_signup'
        ).values_list('user_id', flat=True)
        
        if len(participants) < team_size:
            return []
        
        # Get AI recommendations from the model
        recommendations = AvailabilityWindow.get_team_formation_recommendations(
            event, team_size=team_size
        )
        
        # Enhance recommendations with additional data
        enhanced_recommendations = []
        for rec in recommendations:
            # Get user objects and their preferences
            team_users = User.objects.filter(id__in=rec['team_members'])
            team_participations = EventParticipation.objects.filter(
                event=event,
                user__in=team_users
            ).select_related('user')
            
            # Calculate team stats
            car_preferences = {}
            experience_levels = []
            total_availability_hours = 0
            
            for participation in team_participations:
                if participation.preferred_car:
                    car_name = str(participation.preferred_car)
                    car_preferences[car_name] = car_preferences.get(car_name, 0) + 1
                
                if participation.experience_level:
                    experience_levels.append(participation.experience_level)
                
                # Calculate total availability
                for window in participation.availability_windows.all():
                    total_availability_hours += window.duration_hours()
            
            enhanced_recommendations.append({
                'team_members': list(team_users.values('id', 'username', 'first_name', 'last_name')),
                'compatibility_score': rec['total_overlap_score'],
                'total_availability_hours': total_availability_hours,
                'car_preferences': car_preferences,
                'experience_levels': experience_levels,
                'recommended_car': max(car_preferences.keys()) if car_preferences else None,
                'team_balance_score': TeamFormationService._calculate_balance_score(team_participations)
            })
        
        return sorted(enhanced_recommendations, key=lambda x: x['compatibility_score'], reverse=True)[:max_teams]

    @staticmethod
    def _calculate_balance_score(participations) -> float:
        """Calculate team balance score based on experience and preferences"""
        if not participations:
            return 0.0
        
        experience_mapping = {'beginner': 1, 'intermediate': 2, 'advanced': 3, 'professional': 4}
        experience_scores = []
        
        for p in participations:
            score = experience_mapping.get(p.experience_level, 2)
            experience_scores.append(score)
        
        if len(experience_scores) < 2:
            return 0.5
        
        # Calculate variance (lower variance = better balance)
        mean_score = sum(experience_scores) / len(experience_scores)
        variance = sum((score - mean_score) ** 2 for score in experience_scores) / len(experience_scores)
        
        # Convert to 0-1 scale (lower variance = higher balance score)
        max_variance = 2.25  # Max possible variance for our 1-4 scale
        balance_score = 1 - (variance / max_variance)
        
        return max(0, min(1, balance_score))

    @staticmethod
    def create_teams_from_recommendations(event: Event, recommendations: List[Dict], 
                                        club: Club = None, created_by: User = None) -> List[Team]:
        """Create actual teams from recommendations"""
        created_teams = []
        
        with transaction.atomic():
            for i, rec in enumerate(recommendations):
                # Create team
                team_name = f"Team {chr(65 + i)}"  # Team A, Team B, etc.
                if club:
                    team_name = f"{club.name} {team_name}"
                
                team = Team.objects.create(
                    name=team_name,
                    owner_user=created_by,
                    club=club,
                    is_temporary=not bool(club),
                    description=f"Auto-generated team with {rec['compatibility_score']:.1f}h overlap"
                )
                
                # Assign participants to team
                user_ids = [member['id'] for member in rec['team_members']]
                EventParticipationService.assign_participants_to_team(
                    user_ids, team, created_by
                )
                
                created_teams.append(team)
        
        return created_teams


class InvitationService:
    """Service for managing event signup invitations"""

    @staticmethod
    def send_event_invitation(organizer: User, event: Event, invitee_email: str, 
                            team_name: str, message: str = "") -> EventSignupInvitation:
        """Send invitation for individual team formation"""
        
        # Check if invitation already exists
        existing = EventSignupInvitation.objects.filter(
            event=event,
            organizer_user=organizer,
            invitee_email=invitee_email,
            status='pending'
        ).first()
        
        if existing and not existing.is_expired():
            raise ValidationError(f"Pending invitation already exists for {invitee_email}")
        
        # Create new invitation
        invitation = EventSignupInvitation.objects.create(
            event=event,
            organizer_user=organizer,
            team_name=team_name,
            invitee_email=invitee_email,
            message=message,
            token=EventSignupInvitation.generate_token(),
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # Send email
        InvitationService._send_invitation_email(invitation)
        
        return invitation

    @staticmethod
    def _send_invitation_email(invitation: EventSignupInvitation):
        """Send invitation email to invitee"""
        # This would integrate with your email service
        # For now, just a placeholder
        email_service = EmailService()
        
        context = {
            'invitation': invitation,
            'organizer': invitation.organizer_user,
            'event': invitation.event,
            'team_name': invitation.team_name,
            'accept_url': f"/teams/invitations/{invitation.token}/accept/",
            'decline_url': f"/teams/invitations/{invitation.token}/decline/"
        }
        
        email_service.send_template_email(
            to_email=invitation.invitee_email,
            template_name='teams/emails/event_signup_invitation.html',
            context=context,
            subject=f"Join {invitation.team_name} for {invitation.event.name}"
        )

    @staticmethod
    def process_invitation_response(token: str, user: User, accepted: bool):
        """Process invitation acceptance or decline"""
        try:
            invitation = EventSignupInvitation.objects.get(token=token)
        except EventSignupInvitation.DoesNotExist:
            raise ValidationError("Invalid invitation token")
        
        if invitation.is_expired():
            raise ValidationError("Invitation has expired")
        
        if invitation.status != 'pending':
            raise ValidationError("Invitation has already been responded to")
        
        with transaction.atomic():
            if accepted:
                participation = invitation.accept(user)
                return {'status': 'accepted', 'participation': participation}
            else:
                invitation.decline()
                return {'status': 'declined'}


class WorkflowService:
    """Service for managing participation workflow transitions"""

    @staticmethod
    def close_signup_phase(event: Event, club_event: ClubEvent = None):
        """Close signup phase and prepare for team formation"""
        with transaction.atomic():
            # Update all signed up participants to team formation status
            participants = EventParticipation.objects.filter(
                event=event,
                status='signed_up',
                participation_type='team_signup'
            )
            
            if club_event:
                participants = participants.filter(club_event=club_event)
            
            participants.update(status='team_formation')
            
            # Update club event status if provided
            if club_event:
                club_event.status = 'signup_closed'
                club_event.save()
            
            return participants.count()

    @staticmethod
    def finalize_team_allocations(event: Event, club_event: ClubEvent = None):
        """Finalize team allocations and create event entries"""
        with transaction.atomic():
            participants = EventParticipation.objects.filter(
                event=event,
                status='team_assigned',
                participation_type='team_signup'
            )
            
            if club_event:
                participants = participants.filter(club_event=club_event)
            
            # Convert team signups to team entries
            for participation in participants:
                if participation.team:
                    # Create or update team entry
                    team_entry, created = EventParticipation.objects.get_or_create(
                        event=event,
                        team=participation.team,
                        participation_type='team_entry',
                        defaults={
                            'status': 'entered',
                            'assigned_car': participation.preferred_car,
                            'entered_at': timezone.now()
                        }
                    )
                    
                    # Update individual participation status
                    participation.status = 'entered'
                    participation.entered_at = timezone.now()
                    participation.save()
            
            # Update club event status
            if club_event:
                club_event.status = 'teams_assigned'
                club_event.save()
            
            return participants.count()

    @staticmethod
    def get_workflow_status(event: Event) -> Dict[str, Any]:
        """Get comprehensive workflow status for an event"""
        participations = EventParticipation.objects.filter(event=event)
        
        status_counts = {}
        for participation in participations:
            key = f"{participation.participation_type}_{participation.status}"
            status_counts[key] = status_counts.get(key, 0) + 1
        
        # Determine overall workflow phase
        if status_counts.get('team_signup_signed_up', 0) > 0:
            phase = 'signup_active'
        elif status_counts.get('team_signup_team_formation', 0) > 0:
            phase = 'team_formation'
        elif status_counts.get('team_signup_team_assigned', 0) > 0:
            phase = 'team_allocation'
        elif status_counts.get('team_entry_entered', 0) > 0:
            phase = 'event_ready'
        else:
            phase = 'not_started'
        
        return {
            'phase': phase,
            'status_counts': status_counts,
            'total_participants': participations.count(),
            'ready_for_team_formation': status_counts.get('team_signup_signed_up', 0),
            'ready_for_finalization': status_counts.get('team_signup_team_assigned', 0)
        }


# ===== LEGACY SERVICE COMPATIBILITY LAYER =====
# These services provide compatibility with existing views while transitioning to the new system

class ClubInvitationService:
    """Legacy service for club invitations - wraps existing model methods"""
    
    @staticmethod
    def send_invitation(club, inviter, email, role, message=""):
        """Send club invitation - delegates to model"""
        from .models import ClubInvitation
        import secrets
        from datetime import timedelta
        
        invitation = ClubInvitation.objects.create(
            club=club,
            email=email,
            invited_by=inviter,
            role=role,
            personal_message=message,
            token=secrets.token_urlsafe(32),
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        # Send email (placeholder - would integrate with email service)
        logger.info(f"Club invitation sent to {email} for {club.name}")
        return invitation
    
    @staticmethod
    def accept_invitation(token, user):
        """Accept club invitation"""
        from .models import ClubInvitation
        invitation = ClubInvitation.objects.get(token=token)
        return invitation.accept(user)
    
    @staticmethod
    def decline_invitation(token):
        """Decline club invitation"""
        from .models import ClubInvitation
        invitation = ClubInvitation.objects.get(token=token)
        return invitation.decline()


# EventSignupService removed - EventSignup model no longer exists
# Use EventParticipationService for new participation system
    
# Legacy services removed (TeamAllocationService, StintPlanningService)
# TeamAllocation and TeamEventStrategy models no longer exist
# Use enhanced participation system and team formation services


class NotificationService:
    """Legacy service for notifications"""
    
    @staticmethod
    def send_signup_confirmation(signup):
        """Send signup confirmation email"""
        logger.info(f"Signup confirmation sent to {signup.user.email}")
        # Placeholder - would integrate with email service
        return True
    
    @staticmethod
    def send_team_assignment_notification(allocation):
        """Send team assignment notification"""
        logger.info(f"Team assignment notification sent for {allocation.team.name}")
        return True
