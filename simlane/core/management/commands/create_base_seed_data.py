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
        pass  # No arguments needed for basic simulator creation

    def handle(self, *args, **options):
        self.stdout.write("Creating base simulators...")

        with transaction.atomic():
            # Create simulators only
            simulators = self.create_simulators()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully created {len(simulators)} simulators!\n"
                "To load cars and tracks data, run: python manage.py load_iracing_data"
            )
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
                # Extract and clean car category (single value, not array)
                categories = car.get('categories', [])
                if categories and isinstance(categories, list) and len(categories) > 0:
                    first_category = categories[0]
                    if isinstance(first_category, dict):
                        car_category = first_category.get('category', 'unknown')
                    else:
                        car_category = str(first_category).lower()
                else:
                    car_category = 'unknown'
                
                # Normalize category values to match our choices
                category_mapping = {
                    'formula_car': 'formula_car',
                    'sports_car': 'sports_car', 
                    'oval': 'oval',
                    'unknown': 'unknown',
                }
                normalized_category = category_mapping.get(car_category, 'unknown')

                # Extract and clean car types array
                car_types_raw = car.get('car_types', [])
                if isinstance(car_types_raw, list):
                    # Clean and deduplicate car types
                    cleaned_types = []
                    seen_types = set()
                    
                    for car_type in car_types_raw:
                        if isinstance(car_type, dict):
                            type_name = car_type.get('car_type', '').lower().strip()
                        else:
                            type_name = str(car_type).lower().strip()
                        
                        # Skip empty or duplicate types
                        if not type_name or type_name in seen_types:
                            continue
                            
                        # Normalize similar types (e.g., f1/formula1/formulaone -> formula1)
                        if type_name in ['f1', 'formulaone']:
                            type_name = 'formula1'
                        elif type_name in ['stockcar']:
                            type_name = 'stock_car'
                        
                        cleaned_types.append(type_name)
                        seen_types.add(type_name)
                else:
                    cleaned_types = []

                # Extract manufacturer and model names properly
                car_make = car.get('car_make', '').strip()
                car_model_name = car.get('car_model', '').strip()
                car_full_name = car.get('car_name', '').strip()
                
                # If car_model is empty, extract from car_name
                if not car_model_name and car_full_name:
                    if car_make and car_make in car_full_name:
                        # Remove manufacturer from full name to get model
                        car_model_name = car_full_name.replace(car_make, '').strip()
                        car_model_name = car_model_name.lstrip(' -').rstrip(' -')
                    else:
                        car_model_name = car_full_name
                
                # If car_make is empty, try to extract from car_name
                if not car_make and car_full_name:
                    car_make = self._extract_manufacturer(car_full_name)
                
                # Fallback values
                if not car_make:
                    car_make = 'Unknown'
                if not car_model_name:
                    car_model_name = car_full_name or 'Unknown'

                # Create or get car class (keeping for backward compatibility)
                car_class, class_created = CarClass.objects.get_or_create(
                    name=normalized_category.replace('_', ' ').title(),
                    defaults={
                        'slug': slugify(normalized_category),
                        'description': f'Car class from iRacing: {normalized_category}',
                    }
                )
                if class_created:
                    created_car_classes += 1

                # Prepare search filters for easier searching
                search_filters = [
                    car_make.lower(),
                    car_model_name.lower(),
                    normalized_category,
                ] + cleaned_types

                # Create or get car model with all new fields
                car_model_defaults = {
                    'slug': slugify(f"{car_make}-{car_model_name}"),
                    'full_name': car_full_name,
                    'abbreviated_name': car.get('car_name_abbreviated', ''),
                    'category': normalized_category,
                    'car_types': cleaned_types,
                    'horsepower': car.get('hp', 0),
                    'weight_lbs': car.get('car_weight', 0),
                    'has_headlights': car.get('has_headlights', False),
                    'has_multiple_dry_tire_types': car.get('has_multiple_dry_tire_types', False),
                    'has_rain_capable_tire_types': car.get('has_rain_capable_tire_types', False),
                    'rain_enabled': car.get('rain_enabled', False),
                    'ai_enabled': car.get('ai_enabled', False),
                    'search_filters': search_filters,
                    'base_specs': {
                        'hp': car.get('hp', 0),
                        'weight': car.get('car_weight', 0),
                        'displacement': car.get('displacement', 0),
                        'cylinders': car.get('cylinders', 0),
                        'fuel_capacity': car.get('fuel_capacity', 0),
                        'power_curve': car.get('power_curve', []),
                        'torque_curve': car.get('torque_curve', []),
                    }
                }

                car_model, model_created = CarModel.objects.get_or_create(
                    name=car_model_name,
                    manufacturer=car_make,
                    car_class=car_class,
                    defaults=car_model_defaults
                )
                
                if not model_created and force_update:
                    # Update existing car model with new data
                    for field, value in car_model_defaults.items():
                        if field != 'slug':  # Don't update slug to avoid URL changes
                            setattr(car_model, field, value)
                    car_model.save()
                
                if model_created:
                    created_car_models += 1

                # Create or get sim car with all new fields
                # Use sim_api_id as primary key since that's unique per car in the API
                sim_car_defaults = {
                    'car_model': car_model,
                    'package_id': car.get('package_id', 0),
                    'display_name': car_full_name,
                    'price': car.get('price', 0),
                    'price_display': car.get('price_display', ''),
                    'free_with_subscription': car.get('free_with_subscription', False),
                    'is_purchasable': car.get('is_ps_purchasable', True),
                    'max_power_adjust_pct': car.get('max_power_adjust_pct', 0),
                    'min_power_adjust_pct': car.get('min_power_adjust_pct', 0),
                    'max_weight_penalty_kg': car.get('max_weight_penalty_kg', 0),
                    'logo': car.get('logo', ''),
                    'small_image': car.get('small_image', ''),
                    'large_image': car.get('large_image', ''),
                    'image_url': car.get('logo', ''),  # Keep for backward compatibility
                    'is_active': True,
                }

                # Get or create by sim_api_id only (most reliable unique identifier)
                try:
                    sim_car = SimCar.objects.get(
                        simulator=simulator,
                        sim_api_id=str(car['car_id'])
                    )
                    sim_created = False
                    
                    if force_update:
                        # Update existing sim car with new data
                        for field, value in sim_car_defaults.items():
                            setattr(sim_car, field, value)
                        sim_car.save()
                        
                except SimCar.DoesNotExist:
                    # Create new sim car
                    sim_car = SimCar(
                        simulator=simulator,
                        sim_api_id=str(car['car_id']),
                        **sim_car_defaults
                    )
                    sim_car.save()
                    sim_created = True
                    created_sim_cars += 1

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

    def _extract_manufacturer(self, car_name: str) -> str:
        """Extract manufacturer from car_name when car_make is not available"""
        if not car_name:
            return 'Unknown'
        
        # Common manufacturer patterns in iRacing
        manufacturers = [
            'Acura', 'Audi', 'BMW', 'Chevrolet', 'Ferrari', 'Ford', 'Honda',
            'Lamborghini', 'McLaren', 'Mercedes', 'Mercedes-AMG', 'Porsche',
            'Toyota', 'Volkswagen', 'Nissan', 'Hyundai', 'Pontiac', 'Dallara',
            'Skip Barber', 'Modified', 'NASCAR', 'IndyCar', 'Formula', 'Lotus',
            'Mazda', 'Radical', 'Cadillac', 'Renault', 'Williams', 'Red Bull'
        ]
        
        car_name_upper = car_name.upper()
        for manufacturer in manufacturers:
            if manufacturer.upper() in car_name_upper:
                return manufacturer
        
        # If no manufacturer found, use first word
        return car_name.split()[0] if car_name else 'Unknown'

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