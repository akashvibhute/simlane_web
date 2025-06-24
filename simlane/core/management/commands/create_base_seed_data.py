"""
Management command to create base seed data that should always be present.
This includes simulators, and their tracks/cars from API data.
"""

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from simlane.iracing.services import IRacingServiceError
from simlane.iracing.services import iracing_service
from simlane.sim.models import CarClass
from simlane.sim.models import CarModel
from simlane.sim.models import SimCar
from simlane.sim.models import SimLayout
from simlane.sim.models import SimTrack
from simlane.sim.models import Simulator
from simlane.sim.models import TrackModel
from simlane.sim.models import TrackType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Creates base seed data including simulators and iRacing content from API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-iracing",
            action="store_true",
            help="Skip iRacing API data fetching (useful when API is unavailable)",
        )
        parser.add_argument(
            "--force-update",
            action="store_true",
            help="Force update existing data from API",
        )

    def handle(self, *args, **options):
        self.stdout.write("Creating base seed data...")

        with transaction.atomic():
            # Create simulators
            simulators = self.create_simulators()
            
            # Get iRacing simulator
            iracing_simulator = simulators.get("iracing")
            
            if not options["skip_iracing"] and iracing_simulator:
                # Create iRacing data from API
                self.create_iracing_data(iracing_simulator, options["force_update"])

        self.stdout.write(
            self.style.SUCCESS("Successfully created base seed data!")
        )

    def create_simulators(self) -> dict[str, Simulator]:
        """Create essential simulators"""
        simulators_data = [
            {
                "name": "iRacing",
                "slug": "iracing",
                "website": "https://www.iracing.com",
                "description": "The premier online racing simulation service for PC.",
                "is_active": True,
            },
        ]

        simulators = {}
        for sim_data in simulators_data:
            # Try to get by slug first, then by name to handle existing data
            try:
                simulator = Simulator.objects.get(slug=sim_data["slug"])
                created = False
            except Simulator.DoesNotExist:
                try:
                    simulator = Simulator.objects.get(name=sim_data["name"])
                    # Update the slug if it exists but doesn't have the right slug
                    if not simulator.slug:
                        simulator.slug = sim_data["slug"]
                        simulator.save()
                    created = False
                except Simulator.DoesNotExist:
                    simulator = Simulator.objects.create(**sim_data)
                    created = True
            
            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"Created simulator: {simulator.name}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"Simulator already exists: {simulator.name}")
                )
            
            simulators[sim_data["slug"]] = simulator

        return simulators

    def create_iracing_data(self, simulator: Simulator, force_update: bool = False):
        """Create iRacing cars and tracks from API data"""
        self.stdout.write("Fetching iRacing data from API...")

        try:
            # Fetch cars and tracks data
            cars_data = iracing_service.get_cars()
            tracks_data = iracing_service.get_tracks()

            if not cars_data or not tracks_data:
                self.stdout.write(
                    self.style.ERROR("Failed to fetch iRacing data from API")
                )
                return

            # Process cars
            self.process_iracing_cars(simulator, cars_data, force_update)
            
            # Process tracks
            self.process_iracing_tracks(simulator, tracks_data, force_update)

        except IRacingServiceError as e:
            self.stdout.write(
                self.style.ERROR(f"iRacing API error: {e}")
            )
            self.stdout.write(
                self.style.WARNING(
                    "Skipping iRacing data creation. "
                    "Use --skip-iracing flag to avoid this check."
                )
            )

    def process_iracing_cars(self, simulator: Simulator, cars_data: Any, force_update: bool):
        """Process cars data from iRacing API"""
        self.stdout.write("Processing iRacing cars...")
        
        # Handle both list and dict responses
        if isinstance(cars_data, dict):
            cars = cars_data.get('data', [])
        else:
            cars = cars_data if isinstance(cars_data, list) else []
        created_car_classes = 0
        created_car_models = 0
        created_sim_cars = 0

        for car in cars:
            try:
                # Create or get car class
                categories = car.get('categories', [])
                if categories and isinstance(categories, list) and len(categories) > 0:
                    first_category = categories[0]
                    if isinstance(first_category, dict):
                        car_class_name = first_category.get('category', 'Unknown')
                    else:
                        car_class_name = str(first_category)
                else:
                    car_class_name = 'Unknown'
                
                if not car_class_name or car_class_name == 'Unknown':
                    car_class_name = 'Uncategorized'

                car_class, class_created = CarClass.objects.get_or_create(
                    name=car_class_name,
                    defaults={
                        'slug': slugify(car_class_name),
                        'description': f'Car class from iRacing: {car_class_name}',
                    }
                )
                if class_created:
                    created_car_classes += 1

                # Create or get car model
                car_model, model_created = CarModel.objects.get_or_create(
                    name=car['car_name'],
                    manufacturer=car.get('car_make', 'Unknown'),
                    car_class=car_class,
                    defaults={
                        'slug': slugify(f"{car.get('car_make', 'unknown')}-{car['car_name']}"),
                        'base_specs': {
                            'hp': car.get('hp', 0),
                            'weight': car.get('weight', 0),
                            'displacement': car.get('displacement', 0),
                            'cylinders': car.get('cylinders', 0),
                            'fuel_capacity': car.get('fuel_capacity', 0),
                        }
                    }
                )
                if model_created:
                    created_car_models += 1

                # Create or get sim car
                sim_car, sim_created = SimCar.objects.get_or_create(
                    simulator=simulator,
                    sim_api_id=str(car['car_id']),
                    defaults={
                        'car_model': car_model,
                        'image_url': car.get('logo', ''),
                        'is_active': True,
                    }
                )
                
                if sim_created:
                    created_sim_cars += 1
                elif force_update:
                    # Update existing sim car
                    sim_car.car_model = car_model
                    sim_car.image_url = car.get('logo', '')
                    sim_car.save()

            except Exception as e:
                logger.error(f"Error processing car {car.get('car_name', 'Unknown')}: {e}")
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_car_classes} car classes, "
                f"{created_car_models} car models, "
                f"{created_sim_cars} sim cars"
            )
        )

    def process_iracing_tracks(self, simulator: Simulator, tracks_data: Any, force_update: bool):
        """Process tracks data from iRacing API"""
        self.stdout.write("Processing iRacing tracks...")
        
        # Handle both list and dict responses
        if isinstance(tracks_data, dict):
            tracks = tracks_data.get('data', [])
        else:
            tracks = tracks_data if isinstance(tracks_data, list) else []
        
        created_track_models = 0
        created_sim_tracks = 0
        created_sim_layouts = 0
        
        # Group tracks by track_name since each API entry is actually a track configuration
        tracks_by_name = {}
        for track in tracks:
            track_name = track.get('track_name', 'Unknown')
            if track_name not in tracks_by_name:
                tracks_by_name[track_name] = []
            tracks_by_name[track_name].append(track)

        for track_name, track_configs in tracks_by_name.items():
            try:
                # Use the first config to get basic track info
                base_track = track_configs[0]
                
                # Create or get track model (one per unique track name)
                track_model, model_created = TrackModel.objects.get_or_create(
                    name=track_name,
                    defaults={
                        'slug': slugify(track_name),
                        'country': self._parse_location_country(base_track.get('location', '')),
                        'location': base_track.get('location', ''),
                        'latitude': base_track.get('latitude'),
                        'longitude': base_track.get('longitude'),
                        'description': f"Track from iRacing: {track_name}",
                        'default_image_url': base_track.get('logo', ''),
                    }
                )
                if model_created:
                    created_track_models += 1

                # Create or get sim track (one per track name in this simulator)
                sim_track, track_created = SimTrack.objects.get_or_create(
                    simulator=simulator,
                    track_model=track_model,
                    defaults={
                        'sim_api_id': f"track_{slugify(track_name)}",  # Use track name as base ID
                        'display_name': track_name,
                        'slug': slugify(f"iracing-{track_name}"),
                        'is_laser_scanned': any(config.get('tech_track', False) for config in track_configs),
                        'image_url': base_track.get('logo', ''),
                        'is_active': True,
                    }
                )
                
                if track_created:
                    created_sim_tracks += 1
                elif force_update:
                    # Update existing sim track
                    sim_track.display_name = track_name
                    sim_track.is_laser_scanned = any(config.get('tech_track', False) for config in track_configs)
                    sim_track.image_url = base_track.get('logo', '')
                    sim_track.save()

                # Create SimLayout for each track configuration
                for config in track_configs:
                    track_type = self._determine_track_type(config.get('config_name', ''))
                    config_name = config.get('config_name', 'Unknown Configuration')
                    
                    layout, layout_created = SimLayout.objects.get_or_create(
                        sim_track=sim_track,
                        layout_code=str(config['track_id']),  # Use track_id as layout code
                        defaults={
                            'name': config_name,
                            'slug': slugify(f"{track_name}-{config_name}"),
                            'type': track_type,
                            'length_km': config.get('track_config_length', 0) / 1000 if config.get('track_config_length') else 0,
                        }
                    )
                    
                    if layout_created:
                        created_sim_layouts += 1
                    elif force_update:
                        # Update existing layout
                        layout.name = config_name
                        layout.type = track_type
                        layout.length_km = config.get('track_config_length', 0) / 1000 if config.get('track_config_length') else 0
                        layout.save()

            except Exception as e:
                logger.error(f"Error processing track {track_name}: {e}")
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Created {created_track_models} track models, "
                f"{created_sim_tracks} sim tracks, "
                f"{created_sim_layouts} sim layouts"
            )
        )

    def _determine_track_type(self, config_name: str) -> str:
        """Determine track type based on configuration name"""
        config_lower = config_name.lower()
        
        if 'oval' in config_lower:
            return TrackType.OVAL
        elif 'drag' in config_lower:
            return TrackType.DRAG
        elif 'rally' in config_lower or 'dirt' in config_lower:
            return TrackType.RALLY
        elif 'street' in config_lower or 'city' in config_lower:
            return TrackType.STREET
        else:
            return TrackType.ROAD

    def _parse_location_country(self, location: str) -> str:
        """Parse country from location string (e.g., 'Lakeville, Connecticut, USA' -> 'USA')"""
        if not location:
            return ''
        
        # Split by comma and take the last part as country
        parts = [part.strip() for part in location.split(',')]
        return parts[-1] if parts else '' 