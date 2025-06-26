"""
Debug management command to examine car data structure from iRacing API.
"""

import json
import logging
from typing import Any

from django.core.management.base import BaseCommand

from simlane.iracing.services import IRacingServiceError
from simlane.iracing.services import iracing_service

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Debug car data structure from iRacing API"

    def handle(self, *args, **options):
        self.stdout.write("Fetching car data from iRacing API...")

        try:
            # Get cars data from iRacing API
            cars_data = iracing_service.get_cars()
            
            self.stdout.write(f"Type of cars_data: {type(cars_data)}")
            
            # Handle both list and dict responses
            if isinstance(cars_data, dict):
                cars = cars_data.get('data', [])
                self.stdout.write(f"Cars data is a dict with keys: {list(cars_data.keys())}")
            else:
                cars = cars_data if isinstance(cars_data, list) else []
                self.stdout.write(f"Cars data is a list with {len(cars)} items")
            
            if not cars:
                self.stdout.write("No cars found in the data")
                return
                
            self.stdout.write(f"Total cars found: {len(cars)}")
            
            # Show examples of different car name patterns
            self.stdout.write("\n" + "="*50)
            self.stdout.write("CAR NAME ANALYSIS:")
            self.stdout.write("="*50)
            
            examples = []
            for i, car in enumerate(cars[:10]):  # Look at first 10 cars
                car_name = car.get('car_name', 'Unknown')
                car_make = car.get('car_make', '')
                car_model = car.get('car_model', '')
                
                example = {
                    'index': i,
                    'car_name': car_name,
                    'car_make': car_make,
                    'car_model': car_model,
                    'suggested_manufacturer': car_make if car_make else self._extract_manufacturer(car_name),
                    'suggested_model': car_model if car_model else self._extract_model(car_name, car_make),
                }
                examples.append(example)
                
                self.stdout.write(f"{i+1:2d}. car_name: '{car_name}'")
                self.stdout.write(f"    car_make: '{car_make}'")
                self.stdout.write(f"    car_model: '{car_model}'")
                self.stdout.write(f"    → Suggested manufacturer: '{example['suggested_manufacturer']}'")
                self.stdout.write(f"    → Suggested model: '{example['suggested_model']}'")
                self.stdout.write("")
            
            # Show field mapping recommendations
            self.stdout.write("\n" + "="*50)
            self.stdout.write("RECOMMENDED FIELD MAPPING:")
            self.stdout.write("="*50)
            self.stdout.write("CarModel fields:")
            self.stdout.write("  - name: Use car_model if available, else extract from car_name")
            self.stdout.write("  - manufacturer: Use car_make if available, else extract from car_name")
            self.stdout.write("  - base_specs: Use hp, car_weight, etc.")
            self.stdout.write("")
            self.stdout.write("SimCar fields:")
            self.stdout.write("  - sim_api_id: Use car_id (NOT package_id)")
            self.stdout.write("  - display_name: Use car_name (full name for display)")
            self.stdout.write("  - image_url: Use logo")
            self.stdout.write("")
            self.stdout.write("For ownership tracking:")
            self.stdout.write("  - Use package_id to match with user's owned content")

        except IRacingServiceError as e:
            self.stdout.write(
                self.style.ERROR(f"iRacing API error: {e}")
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Unexpected error: {e}")
            )
            logger.exception("Error in debug_car_data command")
    
    def _extract_manufacturer(self, car_name: str) -> str:
        """Extract manufacturer from car_name when car_make is not available"""
        # Common manufacturer patterns
        manufacturers = [
            'Acura', 'Audi', 'BMW', 'Chevrolet', 'Ferrari', 'Ford', 'Honda',
            'Lamborghini', 'McLaren', 'Mercedes', 'Mercedes-AMG', 'Porsche',
            'Toyota', 'Volkswagen', 'Nissan', 'Hyundai', 'Pontiac', 'Dallara',
            'Skip Barber', 'Modified', 'NASCAR'
        ]
        
        car_name_upper = car_name.upper()
        for manufacturer in manufacturers:
            if manufacturer.upper() in car_name_upper:
                return manufacturer
        
        # If no manufacturer found, use first word
        return car_name.split()[0] if car_name else 'Unknown'
    
    def _extract_model(self, car_name: str, car_make: str) -> str:
        """Extract model from car_name, removing manufacturer if present"""
        if not car_name:
            return 'Unknown'
        
        # If we have car_make, remove it from car_name to get model
        if car_make and car_make in car_name:
            model = car_name.replace(car_make, '').strip()
            # Remove leading/trailing separators
            model = model.lstrip(' -').rstrip(' -')
            return model if model else car_name
        
        # Otherwise, try to extract model by removing common manufacturer names
        manufacturer = self._extract_manufacturer(car_name)
        if manufacturer and manufacturer in car_name:
            model = car_name.replace(manufacturer, '').strip()
            model = model.lstrip(' -').rstrip(' -')
            return model if model else car_name
        
        return car_name 