"""
Debug management command to examine categories and car_types fields from iRacing API.
"""

import logging
from collections import Counter

from django.core.management.base import BaseCommand

from simlane.iracing.services import IRacingServiceError
from simlane.iracing.services import iracing_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Debug categories and car_types fields from iRacing API"

    def handle(self, *args, **options):
        self.stdout.write("Analyzing categories and car_types from iRacing API...")

        try:
            # Get cars data from iRacing API
            cars_data = iracing_service.get_cars()

            # Handle both list and dict responses
            if isinstance(cars_data, dict):
                cars = cars_data.get("data", [])
            else:
                cars = cars_data if isinstance(cars_data, list) else []

            if not cars:
                self.stdout.write("No cars found in the data")
                return

            self.stdout.write(f"Analyzing {len(cars)} cars...")

            # Analyze categories
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("CATEGORIES ANALYSIS")
            self.stdout.write("=" * 60)

            categories_counter = Counter()
            cars_with_multiple_categories = []
            cars_with_no_categories = []

            for i, car in enumerate(cars[:20]):  # Look at first 20 cars
                car_name = car.get("car_name", "Unknown")
                categories = car.get("categories", [])

                self.stdout.write(f"{i + 1:2d}. {car_name}")
                self.stdout.write(f"    categories: {categories}")

                if not categories:
                    cars_with_no_categories.append(car_name)
                elif len(categories) > 1:
                    cars_with_multiple_categories.append((car_name, categories))

                # Count individual categories
                for category in categories:
                    categories_counter[category] += 1

                self.stdout.write("")

            # Analyze car_types
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("CAR_TYPES ANALYSIS")
            self.stdout.write("=" * 60)

            car_types_counter = Counter()
            cars_with_multiple_types = []
            cars_with_no_types = []

            for i, car in enumerate(cars[:20]):  # Look at first 20 cars
                car_name = car.get("car_name", "Unknown")
                car_types = car.get("car_types", [])

                self.stdout.write(f"{i + 1:2d}. {car_name}")
                self.stdout.write(f"    car_types: {car_types}")

                if not car_types:
                    cars_with_no_types.append(car_name)
                elif len(car_types) > 1:
                    cars_with_multiple_types.append((car_name, car_types))

                # Count individual car types
                for car_type_obj in car_types:
                    if isinstance(car_type_obj, dict):
                        car_type = car_type_obj.get("car_type", "")
                        if car_type:
                            car_types_counter[car_type] += 1

                self.stdout.write("")

            # Summary
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write("SUMMARY")
            self.stdout.write("=" * 60)

            self.stdout.write("\nCATEGORIES:")
            self.stdout.write(
                f"  - Cars with multiple categories: {len(cars_with_multiple_categories)}"
            )
            self.stdout.write(
                f"  - Cars with no categories: {len(cars_with_no_categories)}"
            )
            self.stdout.write(
                f"  - Unique categories found: {list(categories_counter.keys())}"
            )
            self.stdout.write(f"  - Category counts: {dict(categories_counter)}")

            if cars_with_multiple_categories:
                self.stdout.write("\n  Cars with multiple categories:")
                for car_name, categories in cars_with_multiple_categories:
                    self.stdout.write(f"    - {car_name}: {categories}")

            self.stdout.write("\nCAR_TYPES:")
            self.stdout.write(
                f"  - Cars with multiple types: {len(cars_with_multiple_types)}"
            )
            self.stdout.write(f"  - Cars with no types: {len(cars_with_no_types)}")
            self.stdout.write(
                f"  - Unique car types found: {list(car_types_counter.keys())}"
            )
            self.stdout.write(f"  - Car type counts: {dict(car_types_counter)}")

            if cars_with_multiple_types:
                self.stdout.write("\n  Cars with multiple types:")
                for car_name, car_types in cars_with_multiple_types:
                    self.stdout.write(f"    - {car_name}: {car_types}")

        except IRacingServiceError as e:
            self.stdout.write(
                self.style.ERROR(f"iRacing API error: {e}"),
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Unexpected error: {e}"),
            )
            logger.exception("Error in debug_categories command")
