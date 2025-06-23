"""
Management command to create test data for the unified event participation system.
Useful for testing team formation, availability, and workflow features.
"""

import random
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone
import pytz

# Import models dynamically to avoid circular import issues
User = get_user_model()


class Command(BaseCommand):
    help = 'Creates test data for the unified event participation system'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=12,
            help='Number of test users to create'
        )
        parser.add_argument(
            '--event-name',
            type=str,
            default='Test Endurance Race',
            help='Name of the test event'
        )
        parser.add_argument(
            '--club-name',
            type=str,
            default='Test Racing Club',
            help='Name of the test club'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing test data first'
        )

    def handle(self, *args, **options):
        # Dynamic imports to avoid circular dependencies
        from simlane.sim.models import Event, SimCar, Simulator
        from simlane.teams.models import Club, ClubEvent, EventParticipation
        from simlane.teams.services import EventParticipationService, AvailabilityService
        
        # Import Track dynamically
        try:
            from simlane.sim.models import Track
        except ImportError:
            try:
                from simlane.sim.models import TrackModel as Track
            except ImportError:
                self.stdout.write(self.style.ERROR("Cannot import Track model"))
                return
        
        if options['clear']:
            self.clear_test_data()

        # Create or get simulator
        simulator, _ = Simulator.objects.get_or_create(
            name='iRacing',
            defaults={'slug': 'iracing'}
        )

        # Create or get track  
        track, _ = Track.objects.get_or_create(
            name='Spa-Francorchamps',
            defaults={
                'location': 'Belgium',
                'length_km': 7.004,
                'simulator': simulator
            }
        )

        # Create test cars
        cars = []
        car_names = ['BMW M4 GT3', 'Mercedes AMG GT3', 'Porsche 911 GT3 R', 'Ferrari 488 GT3']
        for car_name in car_names:
            car, _ = SimCar.objects.get_or_create(
                name=car_name,
                defaults={
                    'car_class': 'GT3',
                    'simulator': simulator
                }
            )
            cars.append(car)

        # Create test event
        event_start = timezone.now() + timedelta(days=14)
        event = Event.objects.create(
            name=options['event_name'],
            simulator=simulator,
            track=track,
            start_date=event_start,
            end_date=event_start + timedelta(hours=24),
            event_type='endurance',
            duration_hours=24,
            event_source='user',
            visibility='public',
            max_entries=30
        )

        self.stdout.write(f"Created event: {event.name}")

        # Create test club
        admin_user = User.objects.filter(is_superuser=True).first()
        if not admin_user:
            # Create admin user using proper method
            admin_user = User(
                username='admin',
                email='admin@example.com',
                is_superuser=True,
                is_staff=True
            )
            admin_user.set_password('admin123')
            admin_user.save()

        club, _ = Club.objects.get_or_create(
            name=options['club_name'],
            defaults={
                'slug': 'test-racing-club',
                'description': 'A test club for the participation system',
                'created_by': admin_user
            }
        )

        # Create club event
        club_event = ClubEvent.objects.create(
            club=club,
            event=event,
            status='signup_active'
        )

        self.stdout.write(f"Created club: {club.name} with event: {club_event}")

        # Create test users with diverse profiles
        users = []
        experience_levels = ['beginner', 'intermediate', 'advanced', 'professional']
        timezones = ['US/Eastern', 'US/Pacific', 'Europe/London', 'Europe/Paris', 'Australia/Sydney']
        
        for i in range(options['users']):
            user, created = User.objects.get_or_create(
                username=f'testdriver{i+1}',
                defaults={
                    'email': f'driver{i+1}@example.com',
                    'first_name': f'Test{i+1}',
                    'last_name': f'Driver{i+1}',
                }
            )
            if created:
                user.set_password('password123')
                user.save()
            users.append(user)

        self.stdout.write(f"Created {len(users)} test users")

        # Create participations with varied preferences
        participations = []
        for i, user in enumerate(users):
            # Vary preferences
            preferred_car = random.choice(cars)
            backup_car = random.choice([c for c in cars if c != preferred_car] + [None])
            experience = random.choice(experience_levels)
            user_timezone = random.choice(timezones)
            
            participation = EventParticipationService.create_team_signup(
                event=event,
                user=user,
                club_event=club_event,
                preferred_car=preferred_car,
                backup_car=backup_car,
                experience_level=experience,
                max_stint_duration=random.randint(45, 120),
                min_rest_duration=random.randint(15, 45),
                timezone=user_timezone,
                notes=f"Test participant {i+1} - {experience} level driver"
            )
            participations.append(participation)

            # Create availability windows
            self.create_availability_windows(participation, event_start, user_timezone, AvailabilityService)

        self.stdout.write(f"Created {len(participations)} participations with availability")

        # Show summary
        self.show_summary(event, club_event, participations)

    def create_availability_windows(self, participation, event_start, timezone_str, AvailabilityService):
        """Create realistic availability windows for a participant"""
        # Different availability patterns
        patterns = [
            'full',      # Available for entire event
            'daytime',   # Only available during day hours
            'nighttime', # Only available during night hours
            'sporadic',  # Random availability windows
            'limited'    # Very limited availability
        ]
        
        pattern = random.choice(patterns)
        windows = []
        
        if pattern == 'full':
            # Available for most of the event
            windows.append({
                'start_time_local': event_start,
                'end_time_local': event_start + timedelta(hours=20),
                'can_drive': True,
                'can_spot': True,
                'preference_level': 1
            })
        
        elif pattern == 'daytime':
            # Available during day hours (8am-8pm local)
            for day_offset in range(2):  # Two days
                day_start = event_start + timedelta(days=day_offset)
                start_time = day_start.replace(hour=8, minute=0)
                end_time = day_start.replace(hour=20, minute=0)
                windows.append({
                    'start_time_local': start_time,
                    'end_time_local': end_time,
                    'can_drive': True,
                    'can_spot': True,
                    'preference_level': random.randint(1, 3)
                })
        
        elif pattern == 'nighttime':
            # Available during night hours (8pm-8am local)
            for day_offset in range(2):
                day_start = event_start + timedelta(days=day_offset)
                start_time = day_start.replace(hour=20, minute=0)
                end_time = start_time + timedelta(hours=12)
                windows.append({
                    'start_time_local': start_time,
                    'end_time_local': end_time,
                    'can_drive': True,
                    'can_spot': False,  # Tired at night
                    'preference_level': random.randint(2, 4)
                })
        
        elif pattern == 'sporadic':
            # Random windows throughout the event
            num_windows = random.randint(3, 6)
            for _ in range(num_windows):
                start_offset = random.randint(0, 18)
                duration = random.randint(2, 6)
                start_time = event_start + timedelta(hours=start_offset)
                end_time = start_time + timedelta(hours=duration)
                windows.append({
                    'start_time_local': start_time,
                    'end_time_local': end_time,
                    'can_drive': random.choice([True, True, False]),
                    'can_spot': True,
                    'preference_level': random.randint(1, 5)
                })
        
        else:  # limited
            # Very limited availability
            windows.append({
                'start_time_local': event_start + timedelta(hours=random.randint(4, 16)),
                'end_time_local': event_start + timedelta(hours=random.randint(18, 22)),
                'can_drive': True,
                'can_spot': True,
                'preference_level': random.randint(3, 5)
            })
        
        # Create the windows
        created_windows = AvailabilityService.bulk_create_availability(
            participation=participation,
            availability_data=windows,
            timezone_str=timezone_str
        )
        
        return created_windows

    def clear_test_data(self):
        """Clear existing test data"""
        self.stdout.write("Clearing existing test data...")
        
        # Delete test users (cascade will handle related data)
        test_users = User.objects.filter(username__startswith='testdriver')
        count = test_users.count()
        test_users.delete()
        
        # Dynamic imports
        from simlane.sim.models import Event
        from simlane.teams.models import Club
        
        # Delete test events
        Event.objects.filter(name__contains='Test').delete()
        
        # Delete test clubs
        Club.objects.filter(name__contains='Test').delete()
        
        self.stdout.write(f"Deleted {count} test users and related data")

    def show_summary(self, event, club_event, participations):
        """Show summary of created data"""
        from simlane.teams.services import WorkflowService, AvailabilityService, EventParticipationService
        
        # Get participation summary
        summary = EventParticipationService.get_participation_summary(event)
        
        # Get workflow status
        workflow = WorkflowService.get_workflow_status(event)
        
        # Get coverage report
        coverage = AvailabilityService.generate_coverage_report(event, timezone_display='UTC')
        
        self.stdout.write("\n" + "="*50)
        self.stdout.write(self.style.SUCCESS("TEST DATA CREATED SUCCESSFULLY"))
        self.stdout.write("="*50)
        
        self.stdout.write(f"\nEvent: {event.name}")
        self.stdout.write(f"URL: /teams/events/{club_event.id}/formation/")
        self.stdout.write(f"\nParticipants: {summary['total_participants']}")
        self.stdout.write(f"Ready for teams: {summary['team_signups_ready']}")
        self.stdout.write(f"Current phase: {workflow['phase']}")
        
        self.stdout.write("\nAvailability Coverage:")
        total_hours = len(coverage['hourly_coverage'])
        covered_hours = sum(1 for h in coverage['hourly_coverage'].values() if h['drivers'] > 0)
        self.stdout.write(f"Coverage: {covered_hours}/{total_hours} hours ({covered_hours/total_hours*100:.0f}%)")
        
        self.stdout.write("\nNext Steps:")
        self.stdout.write("1. Visit the team formation dashboard URL above")
        self.stdout.write("2. Review participant signups and availability")
        self.stdout.write("3. Generate team suggestions")
        self.stdout.write("4. Create teams from suggestions")
        self.stdout.write("5. Finalize team allocations")
        
        self.stdout.write("\nTest User Credentials:")
        self.stdout.write("Username: testdriver1 (through testdriver12)")
        self.stdout.write("Password: password123")
        self.stdout.write("\nAdmin User:")
        self.stdout.write("Username: admin")
        self.stdout.write("Password: admin123") 