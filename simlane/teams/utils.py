import secrets
import string
import json
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import csv
import io
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch

from django.db.models import Count, Avg, Q, Sum
from django.utils import timezone
from django.utils.text import slugify

from .models import (
    ClubInvitation, EventSignup, TeamAllocation,
    StintAssignment, TeamEventStrategy
)


# Token Generation and Validation

def generate_invitation_token() -> str:
    """Create secure invitation tokens"""
    # Generate a secure random token
    alphabet = string.ascii_letters + string.digits
    token = ''.join(secrets.choice(alphabet) for _ in range(32))
    
    # Ensure uniqueness
    while ClubInvitation.objects.filter(token=token).exists():
        token = ''.join(secrets.choice(alphabet) for _ in range(32))
    
    return token


def validate_invitation_token(token: str) -> Tuple[bool, Optional[ClubInvitation], str]:
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


def generate_secure_slug(text: str, model_class, field_name: str = 'slug') -> str:
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

def balance_teams_by_skill(signups: List[EventSignup], team_count: int) -> List[List[EventSignup]]:
    """Distribute members by skill level using snake draft"""
    # Sort signups by skill rating
    signup_data = []
    for signup in signups:
        skill_rating = signup.get_skill_rating() or 1000
        signup_data.append((signup, skill_rating))
    
    signup_data.sort(key=lambda x: x[1], reverse=True)
    
    # Initialize teams
    teams = [[] for _ in range(team_count)]
    
    # Snake draft distribution
    for i, (signup, _) in enumerate(signup_data):
        if i // team_count % 2 == 0:
            # Forward pass
            team_idx = i % team_count
        else:
            # Reverse pass
            team_idx = team_count - 1 - (i % team_count)
        teams[team_idx].append(signup)
    
    return teams


def optimize_car_distribution(signups: List[EventSignup], available_cars: List) -> Dict[str, List[EventSignup]]:
    """Assign cars based on preferences"""
    car_assignments = {str(car.id): [] for car in available_cars}
    unassigned = []
    
    # First pass: Assign based on first preference
    for signup in signups:
        preferred_cars = list(signup.preferred_cars.all())
        if preferred_cars:
            first_choice = preferred_cars[0]
            if str(first_choice.id) in car_assignments:
                car_assignments[str(first_choice.id)].append(signup)
            else:
                unassigned.append(signup)
        else:
            unassigned.append(signup)
    
    # Second pass: Balance assignments
    for signup in unassigned:
        # Find car with fewest assignments
        min_car = min(car_assignments.items(), key=lambda x: len(x[1]))
        car_assignments[min_car[0]].append(signup)
    
    return car_assignments


def calculate_availability_overlap(members: List[EventSignup], event_instances) -> Dict:
    """Find optimal driver rotations based on availability"""
    overlap_matrix = {}
    
    for instance in event_instances:
        available_members = []
        for member in members:
            availability = member.availabilities.filter(
                event_instance=instance,
                available=True
            ).first()
            if availability:
                available_members.append({
                    'member': member,
                    'preferred_duration': availability.preferred_stint_duration
                })
        
        overlap_matrix[str(instance.id)] = {
            'instance': instance,
            'available_count': len(available_members),
            'members': available_members
        }
    
    return overlap_matrix


def suggest_team_compositions(signups: List[EventSignup], criteria: Dict) -> List[Dict]:
    """AI-assisted team suggestions with multiple criteria"""
    suggestions = []
    
    # Extract criteria
    prioritize_skill = criteria.get('prioritize_skill', True)
    prioritize_availability = criteria.get('prioritize_availability', False)
    prioritize_experience = criteria.get('prioritize_experience', False)
    team_count = criteria.get('team_count', 2)
    
    # Score each signup
    scored_signups = []
    for signup in signups:
        score = 0
        
        if prioritize_skill:
            skill_rating = signup.get_skill_rating() or 1000
            score += skill_rating / 100  # Normalize to 0-50 range
        
        if prioritize_availability:
            availability_count = signup.availabilities.filter(available=True).count()
            total_instances = signup.club_event.base_event.instances.count()
            if total_instances > 0:
                score += (availability_count / total_instances) * 30
        
        if prioritize_experience:
            track_experience = signup.get_track_experience()
            if track_experience:
                score += min(track_experience.count(), 20)  # Cap at 20 points
        
        scored_signups.append({
            'signup': signup,
            'score': score,
            'skill_rating': signup.get_skill_rating(),
            'availability_pct': signup.availabilities.filter(available=True).count() / max(1, signup.availabilities.count()) * 100
        })
    
    # Sort by score
    scored_signups.sort(key=lambda x: x['score'], reverse=True)
    
    # Create balanced teams
    teams = [[] for _ in range(team_count)]
    team_scores = [0 for _ in range(team_count)]
    
    for scored in scored_signups:
        # Add to team with lowest total score for balance
        min_team_idx = team_scores.index(min(team_scores))
        teams[min_team_idx].append(scored)
        team_scores[min_team_idx] += scored['score']
    
    # Format suggestions
    for i, team in enumerate(teams):
        avg_score = team_scores[i] / max(1, len(team))
        suggestions.append({
            'team_number': i + 1,
            'members': team,
            'total_score': team_scores[i],
            'average_score': avg_score,
            'member_count': len(team)
        })
    
    return suggestions


# Stint Planning Calculations

def calculate_stint_duration(event_length: timedelta, driver_count: int, pit_stops: int) -> int:
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
    if track and hasattr(track, 'length_km'):
        if track.length_km > 5:
            base_rate *= 1.2
        elif track.length_km < 3:
            base_rate *= 0.9
    
    # Car factors (if available)
    # In reality, would have car-specific consumption data
    
    return stint_duration * base_rate


def calculate_pit_windows(event_instance, pit_data) -> List[Dict]:
    """Calculate optimal pit stop timing"""
    if not pit_data:
        return []
    
    duration = event_instance.end_time - event_instance.start_time
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
                pit_duration = max(pit_duration, pit_data.stop_go_base_loss_sec + pit_data.tire_change_all_four_sec)
            else:
                pit_duration += pit_data.tire_change_all_four_sec
        
        pit_windows.append({
            'stop_number': i,
            'window': {
                'earliest': max(0, window_center - 10),
                'optimal': window_center,
                'latest': min(total_minutes, window_center + 10)
            },
            'fuel_needed': fuel_needed,
            'tire_change': i % 2 == 0,
            'estimated_duration': round(pit_duration, 1),
            'time_loss': round(pit_duration + pit_data.drive_through_loss_sec, 1)
        })
    
    return pit_windows


def generate_driver_rotation(team_members: List, availability: Dict, event_duration: int) -> List[Dict]:
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
        pit_stops=3  # Assumed
    )
    
    # Create rotation
    current_time = 0
    stint_number = 1
    driver_index = 0
    
    while current_time < event_duration:
        driver = available_drivers[driver_index % driver_count]
        stint_end = min(current_time + stint_duration, event_duration)
        
        rotations.append({
            'stint_number': stint_number,
            'driver': driver.event_signup.user,
            'start_minute': current_time,
            'end_minute': stint_end,
            'duration': stint_end - current_time
        })
        
        current_time = stint_end
        stint_number += 1
        driver_index += 1
    
    return rotations


# Data Export Utilities

def export_signup_data(club_event, format: str = 'csv') -> io.BytesIO:
    """Export signup sheets as CSV/Excel"""
    output = io.BytesIO()
    
    if format == 'csv':
        writer = csv.writer(io.TextIOWrapper(output, encoding='utf-8', newline=''))
        
        # Header
        writer.writerow([
            'Username', 'Email', 'Experience Level', 'Can Drive', 'Can Spectate',
            'Preferred Cars', 'Backup Cars', 'Availability %', 'Notes'
        ])
        
        # Data
        for signup in club_event.signups.all():
            preferred_cars = ', '.join(str(car) for car in signup.preferred_cars.all())
            backup_cars = ', '.join(str(car) for car in signup.backup_cars.all())
            
            total_instances = signup.club_event.base_event.instances.count()
            available_instances = signup.availabilities.filter(available=True).count()
            availability_pct = (available_instances / total_instances * 100) if total_instances > 0 else 0
            
            writer.writerow([
                signup.user.username,
                signup.user.email,
                signup.get_experience_level_display(),
                'Yes' if signup.can_drive else 'No',
                'Yes' if signup.can_spectate else 'No',
                preferred_cars,
                backup_cars,
                f"{availability_pct:.0f}%",
                signup.notes
            ])
    
    output.seek(0)
    return output


def generate_stint_plan_pdf(team_allocation: TeamAllocation) -> io.BytesIO:
    """Create printable stint plans"""
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Title
    title = Paragraph(f"Stint Plan - {team_allocation.team.name}", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 0.2*inch))
    
    # Event info
    event_info = Paragraph(
        f"Event: {team_allocation.club_event.title}<br/>"
        f"Car: {team_allocation.assigned_sim_car}<br/>"
        f"Date: {team_allocation.club_event.base_event.event_date}",
        styles['Normal']
    )
    elements.append(event_info)
    elements.append(Spacer(1, 0.3*inch))
    
    # Stint table
    if hasattr(team_allocation, 'strategy') and team_allocation.strategy:
        stints = team_allocation.strategy.stint_assignments.all().order_by('stint_number')
        
        data = [['Stint', 'Driver', 'Start Time', 'Duration', 'Pit Entry', 'Notes']]
        
        for stint in stints:
            data.append([
                str(stint.stint_number),
                stint.driver.username,
                stint.estimated_start_time.strftime('%H:%M'),
                f"{stint.estimated_duration_minutes} min",
                'Yes' if stint.pit_entry_planned else 'No',
                stint.notes[:30] + '...' if len(stint.notes) > 30 else stint.notes
            ])
        
        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))
        
        elements.append(table)
    
    doc.build(elements)
    output.seek(0)
    return output


def export_team_roster(allocation: TeamAllocation) -> Dict:
    """Generate team contact lists"""
    roster = {
        'team': str(allocation.team),
        'event': str(allocation.club_event),
        'car': str(allocation.assigned_sim_car),
        'members': []
    }
    
    for member in allocation.members.all():
        signup = member.event_signup
        roster['members'].append({
            'name': signup.user.get_full_name() or signup.user.username,
            'email': signup.user.email,
            'role': member.get_role_display(),
            'can_drive': signup.can_drive,
            'can_spectate': signup.can_spectate,
            'experience': signup.get_experience_level_display()
        })
    
    return roster


# Notification Helpers

def prepare_invitation_context(invitation: ClubInvitation) -> Dict:
    """Email template context for invitations"""
    from django.conf import settings
    
    return {
        'invitation': invitation,
        'club': invitation.club,
        'inviter': invitation.invited_by,
        'role': invitation.get_role_display(),
        'personal_message': invitation.personal_message,
        'expires_at': invitation.expires_at,
        'accept_url': f"{settings.SITE_URL}/teams/invite/{invitation.token}/accept/",
        'decline_url': f"{settings.SITE_URL}/teams/invite/{invitation.token}/decline/",
        'site_name': settings.SITE_NAME,
        'support_email': settings.DEFAULT_FROM_EMAIL
    }


def format_event_details(event) -> str:
    """Consistent event formatting for notifications"""
    details = f"Event: {event.name}\n"
    
    if hasattr(event, 'sim_layout'):
        details += f"Track: {event.sim_layout.name}\n"
    
    if event.event_date:
        details += f"Date: {event.event_date.strftime('%B %d, %Y at %I:%M %p')}\n"
    
    if hasattr(event, 'simulator'):
        details += f"Simulator: {event.simulator.name}\n"
    
    if hasattr(event, 'type'):
        details += f"Type: {event.get_type_display()}\n"
    
    return details


def generate_notification_summary(club_event) -> Dict:
    """Generate signup summary for emails"""
    signups = club_event.signups.all()
    
    summary = {
        'total_signups': signups.count(),
        'drivers': signups.filter(can_drive=True).count(),
        'spectators': signups.filter(can_spectate=True).count(),
        'signup_deadline': club_event.signup_deadline,
        'event_details': format_event_details(club_event.base_event),
        'status': club_event.get_status_display()
    }
    
    # Experience breakdown
    experience_counts = signups.values('experience_level').annotate(count=Count('id'))
    summary['experience_breakdown'] = {
        item['experience_level']: item['count'] 
        for item in experience_counts
    }
    
    return summary 