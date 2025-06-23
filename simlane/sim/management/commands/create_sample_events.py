"""
Management command to create sample events for testing club functionality.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.text import slugify

from simlane.sim.models import Event
from simlane.sim.models import EventInstance
from simlane.sim.models import EventSession
from simlane.sim.models import Series
from simlane.sim.models import SimLayout
from simlane.sim.models import SimTrack
from simlane.sim.models import Simulator
from simlane.sim.models import TrackModel


class Command(BaseCommand):
    help = "Creates sample events for testing club functionality"

    def add_arguments(self, parser):
        parser.add_argument(
            "--count",
            type=int,
            default=10,
            help="Number of sample events to create (default: 10)",
        )

    def handle(self, *args, **options):
        count = options["count"]

        # Ensure we have simulators first
        if not Simulator.objects.filter(is_active=True).exists():
            self.stdout.write(
                self.style.ERROR(
                    "No active simulators found. Please run 'python manage.py create_simulators' first.",
                ),
            )
            return

        # Get or create some basic track data
        track_data = [
            {
                "name": "Spa-Francorchamps",
                "country": "Belgium",
                "length_km": 7.004,
                "layout": "Grand Prix",
            },
            {
                "name": "Silverstone Circuit",
                "country": "United Kingdom",
                "length_km": 5.891,
                "layout": "Grand Prix",
            },
            {
                "name": "Circuit de Monaco",
                "country": "Monaco",
                "length_km": 3.337,
                "layout": "Grand Prix",
            },
            {
                "name": "Nürburgring",
                "country": "Germany",
                "length_km": 5.148,
                "layout": "Grand Prix",
            },
            {
                "name": "Suzuka Circuit",
                "country": "Japan",
                "length_km": 5.807,
                "layout": "Grand Prix",
            },
        ]

        # Create tracks and layouts
        created_tracks = []
        for track_info in track_data:
            track_model, _ = TrackModel.objects.get_or_create(
                name=track_info["name"],
                defaults={
                    "country": track_info["country"],
                    "length_km": track_info["length_km"],
                },
            )

            track, _ = SimTrack.objects.get_or_create(
                track_model=track_model,
                defaults={
                    "display_name": track_info["name"],
                    "sim_api_id": f"sim_{track_info['name'].lower().replace(' ', '_')}",
                },
            )

            sim_layout, _ = SimLayout.objects.get_or_create(
                sim_track=track,
                name=track_info["layout"],
                defaults={
                    "length_km": track_info["length_km"],
                },
            )
            created_tracks.append(sim_layout)

        # Get or create a sample series
        series, _ = Series.objects.get_or_create(
            name="Sample Racing Series",
            defaults={
                "description": "A sample racing series for testing purposes",
                "is_active": True,
            },
        )

        # Get simulators
        simulators = list(Simulator.objects.filter(is_active=True))
        if not simulators:
            self.stdout.write(
                self.style.ERROR("No simulators available"),
            )
            return

        # Create sample events
        events_data = [
            {
                "name": "Belgian Grand Prix",
                "description": "Classic endurance race at the legendary Spa-Francorchamps circuit.",
                "event_type": "CHAMPIONSHIP",
            },
            {
                "name": "British Grand Prix",
                "description": "High-speed racing at the home of British motorsport.",
                "event_type": "CHAMPIONSHIP",
            },
            {
                "name": "Monaco Grand Prix",
                "description": "The most prestigious street circuit in the world.",
                "event_type": "CHAMPIONSHIP",
            },
            {
                "name": "German Grand Prix",
                "description": "Technical challenge at the modern Nürburgring layout.",
                "event_type": "CHAMPIONSHIP",
            },
            {
                "name": "Japanese Grand Prix",
                "description": "Figure-eight layout providing exciting racing action.",
                "event_type": "CHAMPIONSHIP",
            },
            {
                "name": "Sprint Race Series - Spa",
                "description": "Short format racing for quick competition.",
                "event_type": "CUSTOM",
            },
            {
                "name": "Endurance Challenge - Silverstone",
                "description": "3-hour endurance race for teams.",
                "event_type": "CUSTOM",
            },
            {
                "name": "Time Trial - Monaco",
                "description": "Individual time attack around Monaco streets.",
                "event_type": "CUSTOM",
            },
        ]

        created_count = 0

        for i in range(min(count, len(events_data) * len(created_tracks))):
            event_info = events_data[i % len(events_data)]
            sim_layout = created_tracks[i % len(created_tracks)]
            simulator = simulators[i % len(simulators)]

            # Create unique event name
            event_name = f"{event_info['name']} - {sim_layout.sim_track.name}"

            # Check if event already exists
            if Event.objects.filter(name=event_name, simulator=simulator).exists():
                continue

            # Create event date (random future date)
            event_date = timezone.now() + timedelta(days=7 + (i * 3))

            event = Event.objects.create(
                name=event_name,
                slug=slugify(event_name),
                description=event_info["description"],
                series=series,
                simulator=simulator,
                sim_layout=sim_layout,
                type=event_info["event_type"],
                status="SCHEDULED",
                event_date=event_date,
                registration_deadline=event_date - timedelta(days=1),
                is_team_event=event_info["event_type"] == "CUSTOM",
                min_drivers_per_entry=1,
                max_drivers_per_entry=4 if event_info["event_type"] == "CUSTOM" else 1,
            )

            # Create practice session
            EventSession.objects.create(
                event=event,
                session_type="PRACTICE",
                duration=30,  # 30 minutes
                in_game_time=event_date - timedelta(hours=2),
            )

            # Create qualifying session
            EventSession.objects.create(
                event=event,
                session_type="QUALIFYING",
                duration=20,  # 20 minutes
                in_game_time=event_date - timedelta(hours=1),
            )

            # Create race session
            race_duration = (
                180 if "Endurance" in event_name else 60
            )  # 3 hours or 1 hour
            EventSession.objects.create(
                event=event,
                session_type="RACE",
                duration=race_duration,
                in_game_time=event_date,
            )

            # Create event instance
            EventInstance.objects.create(
                event=event,
                start_time=event_date - timedelta(hours=2),  # Start with practice
                end_time=event_date + timedelta(minutes=race_duration),
                registration_open=timezone.now(),
                registration_ends=event_date - timedelta(hours=12),
            )

            created_count += 1
            self.stdout.write(
                self.style.SUCCESS(f"Created event: {event.name}"),
            )

        success_msg = f"\nCompleted! Created {created_count} sample events."
        self.stdout.write(self.style.SUCCESS(success_msg))

        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    "\nYou can now add these events to your clubs using the 'Add Events' button "
                    "in the club dashboard, then create event signups.",
                ),
            )
