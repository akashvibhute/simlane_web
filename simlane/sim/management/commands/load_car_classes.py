"""
Management command to load and update car classes data from iRacing API.
"""

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from simlane.iracing.services import IRacingServiceError
from simlane.iracing.services import iracing_service
from simlane.sim.models import CarClass, Simulator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Load and update car classes data from iRacing API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--force-update",
            action="store_true",
            help="Force update existing car classes from API",
        )
        parser.add_argument(
            "--simulator",
            type=str,
            default="iracing",
            help="Simulator slug to load data for (default: iracing)",
        )

    def handle(self, *args, **options):
        self.stdout.write("Loading car classes from iRacing API...")

        # Get simulator
        try:
            simulator = Simulator.objects.get(slug=options["simulator"])
        except Simulator.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(f"Simulator '{options['simulator']}' not found. Please create it first.")
            )
            return

        force_update = options["force_update"]
        
        try:
            self.load_car_classes(simulator, force_update)
            self.stdout.write(
                self.style.SUCCESS("Successfully loaded car classes!")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error loading car classes: {e}")
            )

    def load_car_classes(self, simulator: Simulator, force_update: bool = False):
        """Load and update car classes data from iRacing API"""
        self.stdout.write("Fetching car classes from iRacing API...")

        try:
            car_classes_data = iracing_service.get_car_classes()
            
            if not car_classes_data:
                self.stdout.write(
                    self.style.ERROR("Failed to fetch car classes data from API")
                )
                return

            self.process_car_classes(simulator, car_classes_data, force_update)

        except IRacingServiceError as e:
            self.stdout.write(
                self.style.ERROR(f"iRacing API error: {e}")
            )

    def process_car_classes(self, simulator: Simulator, car_classes_data: list[dict[str, Any]], force_update: bool):
        """Process car classes data from iRacing API"""
        self.stdout.write("Processing car classes...")
        
        created_count = 0
        updated_count = 0
        skipped_count = 0

        for car_class_data in car_classes_data:
            try:
                car_class_id = str(car_class_data.get('car_class_id'))
                name = car_class_data.get('name', f'Class {car_class_id}')
                short_name = car_class_data.get('short_name', name)
                
                # Extract cars in class
                cars_in_class = car_class_data.get('cars_in_class', [])
                car_sim_api_ids = [str(car.get('car_id')) for car in cars_in_class if car.get('car_id')]
                
                # Check if car class already exists
                car_class, created = CarClass.objects.get_or_create(
                    simulator=simulator,
                    sim_api_id=car_class_id,
                    defaults={
                        'name': name,
                        'short_name': short_name,
                        'slug': slugify(name),
                        'relative_speed': car_class_data.get('relative_speed', 0),
                        'rain_enabled': car_class_data.get('rain_enabled', False),
                        'car_sim_api_ids': car_sim_api_ids,
                    }
                )
                
                if created:
                    created_count += 1
                    self.stdout.write(f"  ✓ Created: {name} (ID: {car_class_id})")
                elif force_update:
                    # Update existing car class
                    car_class.name = name
                    car_class.short_name = short_name
                    car_class.relative_speed = car_class_data.get('relative_speed', 0)
                    car_class.rain_enabled = car_class_data.get('rain_enabled', False)
                    car_class.car_sim_api_ids = car_sim_api_ids
                    car_class.save()
                    updated_count += 1
                    self.stdout.write(f"  ↻ Updated: {name} (ID: {car_class_id})")
                else:
                    skipped_count += 1
                    self.stdout.write(f"  - Skipped: {name} (ID: {car_class_id}) - already exists")

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"Error processing car class {car_class_data.get('car_class_id', 'unknown')}: {e}")
                )
                continue

        # Summary
        self.stdout.write(f"\nSummary:")
        self.stdout.write(f"  Created: {created_count}")
        self.stdout.write(f"  Updated: {updated_count}")
        self.stdout.write(f"  Skipped: {skipped_count}")
        self.stdout.write(f"  Total processed: {len(car_classes_data)}") 