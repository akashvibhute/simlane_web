"""
Django management command to seed development/testing data.
DO NOT USE IN PRODUCTION - This is for development and testing only.
"""

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from simlane.sim.models import CarClass
from simlane.sim.models import CarModel
from simlane.sim.models import Event
from simlane.sim.models import EventClass
from simlane.sim.models import EventInstance
from simlane.sim.models import EventStatus
from simlane.sim.models import EventType
from simlane.sim.models import FuelUnit
from simlane.sim.models import PitData
from simlane.sim.models import Series
from simlane.sim.models import SimCar
from simlane.sim.models import SimLayout
from simlane.sim.models import SimProfile
from simlane.sim.models import SimTrack
from simlane.sim.models import Simulator
from simlane.sim.models import TrackModel
from simlane.sim.models import TrackType
from simlane.sim.models import WeatherForecast
from simlane.teams.models import Club
from simlane.teams.models import ClubEvent
from simlane.teams.models import ClubMember
from simlane.teams.models import ClubRole
# EventSignup model removed - use EventParticipation instead
from simlane.teams.models import Team
from simlane.teams.models import TeamMember
from simlane.teams.models import EventParticipation

User = get_user_model()


class Command(BaseCommand):
    help = "Seed development/testing data - DO NOT USE IN PRODUCTION"

    def add_arguments(self, parser):
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before seeding",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            self.clear_data()

        self.stdout.write("Seeding development data...")

        # First, ensure base seed data exists
        self.stdout.write("Ensuring base seed data exists...")
        from django.core.management import call_command
        call_command('create_base_seed_data')

        # Create users first
        users = self.create_users()

        # Get the iRacing simulator (should exist from base seed data)
        try:
            simulator = Simulator.objects.get(slug='iracing')
        except Simulator.DoesNotExist:
            # Fallback to creating it if it doesn't exist
            simulator = self.create_simulator()

        # Create car classes and models
        car_classes = self.create_car_classes()
        car_models = self.create_car_models(car_classes)
        sim_cars = self.create_sim_cars(simulator, car_models)

        # Create tracks
        track_models = self.create_track_models()
        sim_tracks = self.create_sim_tracks(simulator, track_models)
        sim_layouts = self.create_sim_layouts(sim_tracks)

        # Create series and events
        series = self.create_series()
        events = self.create_events(simulator, sim_layouts, series)
        event_classes = self.create_event_classes(events, car_classes, sim_cars)
        event_instances = self.create_event_instances(events)

        # Create weather forecasts
        self.create_weather_forecasts(event_instances)

        # Create sim profiles for users
        self.create_sim_profiles(users, simulator)

        # Create clubs and teams
        clubs = self.create_clubs(users)
        teams = self.create_teams(clubs)

        # Create club events
        club_events = self.create_club_events(clubs, events, users)

        # Create event participations
        self.create_event_signups(club_events, users, sim_cars, teams)

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully seeded development data:\n"
                f"- {len(users)} users\n"
                f"- 1 simulator (iRacing)\n"
                f"- {len(car_classes)} car classes\n"
                f"- {len(car_models)} car models\n"
                f"- {len(sim_cars)} sim cars\n"
                f"- {len(track_models)} track models\n"
                f"- {len(sim_tracks)} sim tracks\n"
                f"- {len(sim_layouts)} sim layouts\n"
                f"- {len(series)} series\n"
                f"- {len(events)} events\n"
                f"- {len(clubs)} clubs\n"
                f"- {len(teams)} teams\n"
                f"- {len(club_events)} club events",
            ),
        )

    def clear_data(self):
        """Clear existing data - BE CAREFUL!"""
        models_to_clear = [
            WeatherForecast,
            EventParticipation,  # Use EventParticipation instead of EventSignup
            ClubEvent,
            TeamMember,
            Team,
            ClubMember,
            Club,
            EventInstance,
            EventClass,
            Event,
            Series,
            SimLayout,
            SimTrack,
            TrackModel,
            SimCar,
            CarModel,
            CarClass,
            SimProfile,
            Simulator,
            PitData,
        ]

        for model in models_to_clear:
            count = model.objects.count()
            if count > 0:
                model.objects.all().delete()
                self.stdout.write(f"Cleared {count} {model.__name__} records")

    def create_users(self):
        """Create test users"""
        users_data = [
            {
                "username": "admin_user",
                "email": "admin@example.com",
                "name": "Admin User",
                "is_staff": True,
                "is_superuser": True,
            },
            {"username": "john_doe", "email": "john@example.com", "name": "John Doe"},
            {
                "username": "jane_smith",
                "email": "jane@example.com",
                "name": "Jane Smith",
            },
            {
                "username": "mike_wilson",
                "email": "mike@example.com",
                "name": "Mike Wilson",
            },
            {
                "username": "sarah_jones",
                "email": "sarah@example.com",
                "name": "Sarah Jones",
            },
            {
                "username": "alex_brown",
                "email": "alex@example.com",
                "name": "Alex Brown",
            },
            {
                "username": "emma_davis",
                "email": "emma@example.com",
                "name": "Emma Davis",
            },
            {
                "username": "chris_miller",
                "email": "chris@example.com",
                "name": "Chris Miller",
            },
        ]

        users = []
        for user_data in users_data:
            user, created = User.objects.get_or_create(
                username=user_data["username"],
                defaults={
                    "email": user_data["email"],
                    "name": user_data["name"],
                    "is_staff": user_data.get("is_staff", False),
                    "is_superuser": user_data.get("is_superuser", False),
                },
            )
            if created:
                user.set_password("password123")  # Simple password for development
                user.save()
            users.append(user)

        return users

    def create_simulator(self):
        """Create iRacing simulator"""
        simulator, created = Simulator.objects.get_or_create(
            name="iRacing",
            defaults={
                "description": "iRacing is the world's premier motorsports racing simulation.",
                "website": "https://www.iracing.com/",
                "is_active": True,
            },
        )
        return simulator

    def create_car_classes(self):
        """Create car classes"""
        classes_data = [
            {
                "name": "GT3",
                "category": "Sports Car",
                "description": "GT3 class sports cars",
            },
            {
                "name": "GTE/GTLM",
                "category": "Sports Car",
                "description": "GTE/GTLM class sports cars",
            },
            {
                "name": "LMP2",
                "category": "Prototype",
                "description": "LMP2 prototype cars",
            },
            {
                "name": "Formula 3",
                "category": "Formula",
                "description": "Formula 3 single seaters",
            },
            {
                "name": "NASCAR Cup",
                "category": "Stock Car",
                "description": "NASCAR Cup Series cars",
            },
            {
                "name": "Touring Car",
                "category": "Touring",
                "description": "Touring car category",
            },
        ]

        car_classes = []
        for class_data in classes_data:
            car_class, created = CarClass.objects.get_or_create(
                name=class_data["name"],
                defaults=class_data,
            )
            car_classes.append(car_class)

        return car_classes

    def create_car_models(self, car_classes):
        """Create car models"""
        # Create pit data first
        pit_data_configs = [
            {
                "drive_through_loss_sec": 25.0,
                "stop_go_base_loss_sec": 30.0,
                "fuel_unit": FuelUnit.LITER,
                "refuel_flow_rate": 2.5,
                "tire_change_all_four_sec": 12.0,
            },
            {
                "drive_through_loss_sec": 28.0,
                "stop_go_base_loss_sec": 35.0,
                "fuel_unit": FuelUnit.LITER,
                "refuel_flow_rate": 3.0,
                "tire_change_all_four_sec": 15.0,
            },
            {
                "drive_through_loss_sec": 22.0,
                "stop_go_base_loss_sec": 28.0,
                "fuel_unit": FuelUnit.LITER,
                "refuel_flow_rate": 4.0,
                "tire_change_all_four_sec": 10.0,
            },
        ]

        pit_data_objects = []
        for config in pit_data_configs:
            pit_data = PitData.objects.create(
                tire_then_refuel=True,
                simultaneous_actions=False,
                **config,
            )
            pit_data_objects.append(pit_data)

        cars_data = [
            # GT3 Cars
            {
                "manufacturer": "BMW",
                "name": "M4 GT3",
                "car_class": "GT3",
                "release_year": 2022,
            },
            {
                "manufacturer": "Mercedes-AMG",
                "name": "GT3 2020",
                "car_class": "GT3",
                "release_year": 2020,
            },
            {
                "manufacturer": "Porsche",
                "name": "911 GT3 R",
                "car_class": "GT3",
                "release_year": 2019,
            },
            {
                "manufacturer": "Ferrari",
                "name": "488 GT3 Evo 2020",
                "car_class": "GT3",
                "release_year": 2020,
            },
            # GTE Cars
            {
                "manufacturer": "Ford",
                "name": "GT GTE",
                "car_class": "GTE/GTLM",
                "release_year": 2018,
            },
            {
                "manufacturer": "Corvette",
                "name": "C8.R GTE",
                "car_class": "GTE/GTLM",
                "release_year": 2020,
            },
            # LMP2
            {
                "manufacturer": "Dallara",
                "name": "P217 LMP2",
                "car_class": "LMP2",
                "release_year": 2017,
            },
            # Formula
            {
                "manufacturer": "Dallara",
                "name": "F3 2019",
                "car_class": "Formula 3",
                "release_year": 2019,
            },
            # NASCAR
            {
                "manufacturer": "Chevrolet",
                "name": "Camaro ZL1",
                "car_class": "NASCAR Cup",
                "release_year": 2022,
            },
            {
                "manufacturer": "Ford",
                "name": "Mustang GT",
                "car_class": "NASCAR Cup",
                "release_year": 2022,
            },
        ]

        car_models = []
        class_dict = {cls.name: cls for cls in car_classes}

        for car_data in cars_data:
            car_class = class_dict.get(car_data.pop("car_class"))
            if car_class:
                car_model, created = CarModel.objects.get_or_create(
                    manufacturer=car_data["manufacturer"],
                    name=car_data["name"],
                    defaults={
                        "car_class": car_class,
                        "release_year": car_data.get("release_year"),
                        "base_specs": {
                            "power_hp": random.randint(400, 700),
                            "weight_kg": random.randint(1200, 1600),
                            "max_fuel_liters": random.randint(80, 120),
                        },
                    },
                )
                car_models.append(car_model)

        return car_models

    def create_sim_cars(self, simulator, car_models):
        """Create sim cars linked to car models"""
        sim_cars = []

        for i, car_model in enumerate(car_models):
            sim_car, created = SimCar.objects.get_or_create(
                simulator=simulator,
                car_model=car_model,
                defaults={
                    "sim_api_id": f"car_{i + 1:03d}",
                    "bop_version": "2024.1",
                    "is_active": True,
                },
            )
            sim_cars.append(sim_car)

        return sim_cars

    def create_track_models(self):
        """Create track models"""
        tracks_data = [
            {"name": "Spa-Francorchamps", "country": "Belgium", "location": "Stavelot"},
            {
                "name": "Circuit de la Sarthe",
                "country": "France",
                "location": "Le Mans",
            },
            {"name": "Nürburgring", "country": "Germany", "location": "Nürburg"},
            {
                "name": "Silverstone Circuit",
                "country": "United Kingdom",
                "location": "Silverstone",
            },
            {"name": "Monza", "country": "Italy", "location": "Monza"},
            {"name": "Suzuka Circuit", "country": "Japan", "location": "Suzuka"},
            {
                "name": "Daytona International Speedway",
                "country": "USA",
                "location": "Daytona Beach, FL",
            },
            {"name": "Road America", "country": "USA", "location": "Elkhart Lake, WI"},
        ]

        track_models = []
        for track_data in tracks_data:
            track_model, created = TrackModel.objects.get_or_create(
                name=track_data["name"],
                country=track_data["country"],
                defaults={
                    "location": track_data["location"],
                    "description": f"Famous racing circuit in {track_data['location']}, {track_data['country']}",
                },
            )
            track_models.append(track_model)

        return track_models

    def create_sim_tracks(self, simulator, track_models):
        """Create sim tracks"""
        sim_tracks = []

        for i, track_model in enumerate(track_models):
            sim_track, created = SimTrack.objects.get_or_create(
                simulator=simulator,
                track_model=track_model,
                defaults={
                    "sim_api_id": f"track_{i + 1:03d}",
                    "display_name": track_model.name,
                    "is_laser_scanned": random.choice([True, False]),
                    "is_active": True,
                },
            )
            sim_tracks.append(sim_track)

        return sim_tracks

    def create_sim_layouts(self, sim_tracks):
        """Create sim layouts for tracks"""
        layouts_data = [
            {
                "layout_code": "FULL",
                "name": "Full Course",
                "type": TrackType.ROAD,
                "length_km": 7.004,
            },
            {
                "layout_code": "FULL",
                "name": "Full Circuit",
                "type": TrackType.ROAD,
                "length_km": 13.626,
            },
            {
                "layout_code": "GP",
                "name": "Grand Prix",
                "type": TrackType.ROAD,
                "length_km": 5.148,
            },
            {
                "layout_code": "FULL",
                "name": "Full Circuit",
                "type": TrackType.ROAD,
                "length_km": 5.891,
            },
            {
                "layout_code": "GP",
                "name": "Grand Prix",
                "type": TrackType.ROAD,
                "length_km": 5.793,
            },
            {
                "layout_code": "GP",
                "name": "Grand Prix",
                "type": TrackType.ROAD,
                "length_km": 5.807,
            },
            {
                "layout_code": "OVAL",
                "name": "Oval",
                "type": TrackType.OVAL,
                "length_km": 4.023,
            },
            {
                "layout_code": "FULL",
                "name": "Full Course",
                "type": TrackType.ROAD,
                "length_km": 6.515,
            },
        ]

        sim_layouts = []
        for sim_track, layout_data in zip(sim_tracks, layouts_data, strict=False):
            # Create pit data for each layout
            pit_data = PitData.objects.create(
                drive_through_loss_sec=random.uniform(20.0, 30.0),
                stop_go_base_loss_sec=random.uniform(25.0, 40.0),
                fuel_unit=FuelUnit.LITER,
                refuel_flow_rate=random.uniform(2.0, 4.0),
                tire_change_all_four_sec=random.uniform(8.0, 18.0),
                tire_then_refuel=random.choice([True, False]),
                simultaneous_actions=random.choice([True, False]),
            )

            sim_layout, created = SimLayout.objects.get_or_create(
                sim_track=sim_track,
                layout_code=layout_data["layout_code"],
                defaults={
                    "name": layout_data["name"],
                    "type": layout_data["type"],
                    "length_km": layout_data["length_km"],
                    "pit_data": pit_data,
                },
            )
            sim_layouts.append(sim_layout)

        return sim_layouts

    def create_series(self):
        """Create racing series"""
        series_data = [
            {
                "name": "IMSA SportsCar Championship",
                "description": "Premier sports car racing series",
                "is_team_event": True,
                "min_drivers_per_entry": 2,
                "max_drivers_per_entry": 4,
            },
            {
                "name": "Blancpain GT Series",
                "description": "GT3 championship series",
                "is_team_event": True,
                "min_drivers_per_entry": 2,
                "max_drivers_per_entry": 3,
            },
            {
                "name": "Formula Renault 2.0",
                "description": "Single seater championship",
                "is_team_event": False,
                "min_drivers_per_entry": 1,
                "max_drivers_per_entry": 1,
            },
            {
                "name": "Touring Car Championship",
                "description": "Touring car racing series",
                "is_team_event": False,
                "min_drivers_per_entry": 1,
                "max_drivers_per_entry": 2,
            },
        ]

        series_objects = []
        for series_info in series_data:
            series_obj, created = Series.objects.get_or_create(
                name=series_info["name"],
                defaults=series_info,
            )
            series_objects.append(series_obj)

        return series_objects

    def create_events(self, simulator, sim_layouts, series):
        """Create racing events"""
        events = []
        event_names = [
            "Spa 6 Hours",
            "Le Mans 24 Hours",
            "Nürburgring 4 Hours",
            "Silverstone 6 Hours",
            "Monza Sprint Race",
            "Suzuka 8 Hours",
            "Daytona 24 Hours",
            "Road America 500",
        ]

        for i, (name, sim_layout, series_obj) in enumerate(
            zip(event_names, sim_layouts, series, strict=False),
        ):
            event_date = timezone.now() + timedelta(days=random.randint(7, 90))
            registration_deadline = event_date - timedelta(days=random.randint(3, 14))

            event, created = Event.objects.get_or_create(
                name=name,
                simulator=simulator,
                defaults={
                    "series": series_obj,
                    "sim_layout": sim_layout,
                    "description": f"{name} - Exciting endurance race at {sim_layout.sim_track.display_name}",
                    "type": EventType.OFFICIAL,
                    "status": EventStatus.SCHEDULED,
                    "event_date": event_date,
                    "registration_deadline": registration_deadline,
                    "is_team_event": series_obj.is_team_event,
                    "min_drivers_per_entry": series_obj.min_drivers_per_entry,
                    "max_drivers_per_entry": series_obj.max_drivers_per_entry,
                    "min_pit_stops": random.randint(1, 8),
                    "weather": {
                        "temperature": random.randint(15, 30),
                        "conditions": "Clear",
                    },
                },
            )
            events.append(event)

        return events

    def create_event_classes(self, events, car_classes, sim_cars):
        """Create event classes"""
        event_classes = []

        for event in events:
            # Create 1-2 classes per event
            num_classes = random.randint(1, 2)
            available_classes = random.sample(
                car_classes,
                min(num_classes, len(car_classes)),
            )

            for car_class in available_classes:
                # Get cars for this class
                class_cars = [
                    car for car in sim_cars if car.car_model.car_class == car_class
                ]
                if class_cars:
                    num_cars = min(
                        len(class_cars),
                        random.randint(1, max(1, len(class_cars))),
                    )
                    allowed_car_ids = [str(car.id) for car in class_cars[:num_cars]]

                    event_class, created = EventClass.objects.get_or_create(
                        event=event,
                        name=f"{car_class.name} Class",
                        defaults={
                            "car_class": car_class,
                            "allowed_sim_car_ids": allowed_car_ids,
                        },
                    )
                    event_classes.append(event_class)

        return event_classes

    def create_event_instances(self, events):
        """Create event instances (practice, qualifying, race sessions)"""
        event_instances = []

        for event in events:
            # Create practice, qualifying, and race instances
            base_time = event.event_date - timedelta(hours=4)

            instances_data = [
                {"name": "Practice", "start_offset": 0, "duration": 90},
                {"name": "Qualifying", "start_offset": 120, "duration": 30},
                {"name": "Race", "start_offset": 180, "duration": 360},  # 6 hour race
            ]

            for i, instance_data in enumerate(instances_data):
                start_time = base_time + timedelta(
                    minutes=instance_data["start_offset"],
                )
                end_time = start_time + timedelta(minutes=instance_data["duration"])

                event_instance, created = EventInstance.objects.get_or_create(
                    event=event,
                    start_time=start_time,
                    defaults={
                        "end_time": end_time,
                        "registration_open": start_time - timedelta(days=14),
                        "registration_ends": start_time - timedelta(hours=2),
                    },
                )
                event_instances.append(event_instance)

        return event_instances

    def create_weather_forecasts(self, event_instances):
        """Create weather forecasts for event instances"""
        for event_instance in event_instances:
            # Create weather forecast every 15 minutes during the event
            current_time = event_instance.start_time
            time_offset = 0

            while current_time <= event_instance.end_time:
                WeatherForecast.objects.get_or_create(
                    event_instance=event_instance,
                    time_offset=time_offset,
                    defaults={
                        "timestamp": current_time,
                        "is_sun_up": 6 <= current_time.hour <= 18,
                        "affects_session": True,
                        "air_temperature": random.uniform(15.0, 30.0),
                        "pressure": random.uniform(1000.0, 1030.0),
                        "wind_speed": random.uniform(0.0, 15.0),
                        "wind_direction": random.randint(0, 359),
                        "precipitation_chance": random.randint(0, 40),
                        "precipitation_amount": random.uniform(0.0, 5.0),
                        "allow_precipitation": True,
                        "cloud_cover": random.randint(0, 80),
                        "relative_humidity": random.randint(30, 90),
                        "forecast_version": 3,
                        "valid_stats": True,
                    },
                )

                current_time += timedelta(minutes=15)
                time_offset += 15

    def create_sim_profiles(self, users, simulator):
        """Create sim profiles for users"""
        for user in users:
            sim_profile, created = SimProfile.objects.get_or_create(
                user=user,
                simulator=simulator,
                profile_name=f"{user.username}_iracing",
                defaults={
                    "external_data_id": f"{random.randint(100000, 999999)}",
                    "is_verified": random.choice([True, False]),
                    "last_active": timezone.now()
                    - timedelta(days=random.randint(0, 30)),
                    "preferences": {
                        "preferred_discipline": random.choice(["road", "oval", "dirt"]),
                        "notifications": True,
                    },
                },
            )

    def create_clubs(self, users):
        """Create racing clubs"""
        clubs_data = [
            {
                "name": "Apex Racing Club",
                "description": "Premier endurance racing club",
                "is_public": True,
            },
            {
                "name": "SimSpeed Racing",
                "description": "Competitive GT racing community",
                "is_public": True,
            },
            {
                "name": "Velocity Motorsports",
                "description": "Multi-class racing club",
                "is_public": False,
            },
            {
                "name": "Thunder Racing League",
                "description": "Oval and road racing specialists",
                "is_public": True,
            },
        ]

        clubs = []
        for i, club_data in enumerate(clubs_data):
            creator = users[i % len(users)]  # Rotate through users as creators

            club, created = Club.objects.get_or_create(
                name=club_data["name"],
                defaults={
                    "description": club_data["description"],
                    "is_public": club_data["is_public"],
                    "created_by": creator,
                    "is_active": True,
                },
            )
            clubs.append(club)

            # Add members to each club
            club_users = random.sample(users, random.randint(3, 6))
            for user in club_users:
                role = (
                    ClubRole.ADMIN
                    if user == creator
                    else random.choice([ClubRole.MEMBER, ClubRole.TEAMS_MANAGER])
                )
                ClubMember.objects.get_or_create(
                    user=user,
                    club=club,
                    defaults={"role": role},
                )

        return clubs

    def create_teams(self, clubs):
        """Create teams for each club"""
        teams = []
        team_names = [
            "Alpha Team",
            "Bravo Team",
            "Charlie Team",
            "Delta Team",
            "Echo Team",
            "Foxtrot Team",
            "Golf Team",
            "Hotel Team",
        ]

        for club in clubs:
            # Create 2-3 teams per club
            num_teams = random.randint(2, 3)
            club_members = list(club.members.all())

            for i in range(num_teams):
                team_name = f"{club.name} {team_names[i % len(team_names)]}"

                team, created = Team.objects.get_or_create(
                    club=club,
                    name=team_name,
                    defaults={
                        "description": f"Competitive racing team from {club.name}",
                        "is_active": True,
                    },
                )
                teams.append(team)

                # Add team members
                team_size = random.randint(2, 4)
                team_members = random.sample(
                    club_members,
                    min(team_size, len(club_members)),
                )

                for member in team_members:
                    TeamMember.objects.get_or_create(
                        user=member.user,
                        team=team,
                    )

        return teams

    def create_club_events(self, clubs, events, users):
        """Create club events linked to racing events"""
        club_events = []

        for club in clubs:
            # Create 2-3 club events per club
            club_event_count = random.randint(2, 3)
            selected_events = random.sample(events, min(club_event_count, len(events)))

            for event in selected_events:
                creator = random.choice(
                    list(
                        club.members.filter(
                            role__in=[ClubRole.ADMIN, ClubRole.TEAMS_MANAGER],
                        ),
                    ),
                )
                signup_deadline = event.event_date - timedelta(
                    days=random.randint(1, 7),
                )

                club_event, created = ClubEvent.objects.get_or_create(
                    club=club,
                    base_event=event,
                    defaults={
                        "title": f"{club.name} - {event.name}",
                        "description": f"Club participation in {event.name}",
                        "signup_deadline": signup_deadline,
                        "max_participants": random.randint(12, 24),
                        "requires_team_assignment": True,
                        "auto_assign_teams": random.choice([True, False]),
                        "team_size_min": 2,
                        "team_size_max": 4,
                        "status": "signup_open",
                        "created_by": creator.user,
                    },
                )
                club_events.append(club_event)

        return club_events

    def create_event_signups(self, club_events, users, sim_cars, teams):
        """Create event signups for club events"""
        for club_event in club_events:
            # Get club members
            club_members = club_event.club.members.all()

            # Create signups for some club members
            max_signups = min(12, len(club_members))
            signup_count = (
                random.randint(min(6, max_signups), max_signups)
                if max_signups > 0
                else 0
            )
            selected_members = (
                random.sample(list(club_members), signup_count)
                if signup_count > 0
                else []
            )

            for member in selected_members:
                # Get sim profile
                sim_profile = member.user.linked_sim_profiles.first()

                # Select preferred cars (EventParticipation uses single car fields)
                preferred_car = random.choice(sim_cars)
                backup_car = random.choice([car for car in sim_cars if car != preferred_car])

                # Create EventParticipation using the enhanced system
                participation, created = EventParticipation.objects.get_or_create(
                    event=club_event,
                    user=member.user,
                    defaults={
                        "participation_type": "team_signup",
                        "status": "signed_up",
                        "preferred_car": preferred_car,
                        "backup_car": backup_car,
                        "experience_level": random.choice(
                            ["beginner", "intermediate", "advanced"],
                        ),
                        "max_stint_duration": random.randint(60, 120),
                        "min_rest_duration": random.randint(15, 30),
                        "notes": "Available for full event",
                        "club_event": club_event,
                    },
                )
