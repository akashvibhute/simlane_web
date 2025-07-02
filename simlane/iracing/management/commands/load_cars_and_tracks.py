"""
Management command to load and update iRacing cars and tracks data from API.
This replaces the car/track loading functionality from create_base_seed_data.
"""

import logging
from typing import Any

import requests
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from simlane.iracing.services import IRacingServiceError
from simlane.iracing.services import iracing_service
from simlane.sim.models import CarModel
from simlane.sim.models import SimCar
from simlane.sim.models import SimLayout
from simlane.sim.models import SimTrack
from simlane.sim.models import Simulator
from simlane.sim.models import TrackModel
from simlane.sim.models import TrackType

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Load and update iRacing cars and tracks data from API"

    def add_arguments(self, parser):
        parser.add_argument(
            "--cars-only",
            action="store_true",
            help="Only load/update cars data",
        )
        parser.add_argument(
            "--tracks-only",
            action="store_true",
            help="Only load/update tracks data",
        )
        parser.add_argument(
            "--force-update",
            action="store_true",
            help="Force update existing data from API",
        )
        parser.add_argument(
            "--simulator",
            type=str,
            default="iracing",
            help="Simulator slug to load data for (default: iracing)",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Verbose output",
        )

    def handle(self, *args, **options):
        self.stdout.write("Loading iRacing data from API...")

        # Get simulator
        try:
            simulator = Simulator.objects.get(slug=options["simulator"])
        except Simulator.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f"Simulator '{options['simulator']}' not found. Please create it first.",
                ),
            )
            return

        cars_only = options["cars_only"]
        tracks_only = options["tracks_only"]
        force_update = options["force_update"]
        verbose = options["verbose"]

        # If neither flag is set, load both
        if not cars_only and not tracks_only:
            cars_only = True
            tracks_only = True

        # Don't use atomic transaction to avoid cascading failures
        if cars_only:
            self.load_cars_data(simulator, force_update, verbose)

        if tracks_only:
            self.load_tracks_data(simulator, force_update, verbose)

        self.stdout.write(
            self.style.SUCCESS("Successfully loaded iRacing data!"),
        )

    def load_cars_data(
        self, simulator: Simulator, force_update: bool = False, verbose: bool = False
    ):
        """Load and update cars data from iRacing API"""
        self.stdout.write("Fetching cars data from iRacing API...")

        try:
            cars_data = iracing_service.get_cars()

            if not cars_data:
                self.stdout.write(
                    self.style.ERROR("Failed to fetch cars data from API"),
                )
                return

            self.process_cars(simulator, cars_data, force_update, verbose)

        except IRacingServiceError as e:
            self.stdout.write(
                self.style.ERROR(f"iRacing API error: {e}"),
            )

    def load_tracks_data(
        self, simulator: Simulator, force_update: bool = False, verbose: bool = False
    ):
        """Load and update tracks data from iRacing API"""
        self.stdout.write("Fetching tracks data from iRacing API...")

        try:
            tracks_data = iracing_service.get_tracks()

            if not tracks_data:
                self.stdout.write(
                    self.style.ERROR("Failed to fetch tracks data from API"),
                )
                return

            self.process_tracks(simulator, tracks_data, force_update, verbose)

        except IRacingServiceError as e:
            self.stdout.write(
                self.style.ERROR(f"iRacing API error: {e}"),
            )

    def process_cars(
        self,
        simulator: Simulator,
        cars_data: Any,
        force_update: bool,
        verbose: bool = False,
    ):
        """Process cars data from iRacing API"""
        self.stdout.write("Processing iRacing cars...")

        # Handle both list and dict responses
        if isinstance(cars_data, dict):
            cars = cars_data.get("data", [])
        else:
            cars = cars_data if isinstance(cars_data, list) else []

        created_car_classes = 0
        created_car_models = 0
        created_sim_cars = 0
        updated_car_models = 0
        updated_sim_cars = 0

        for car in cars:
            try:
                # Extract and clean car category (single value, not array)
                categories = car.get("categories", [])
                if categories and isinstance(categories, list) and len(categories) > 0:
                    first_category = categories[0]
                    if isinstance(first_category, dict):
                        car_category = first_category.get("category", "unknown")
                    else:
                        car_category = str(first_category).lower()
                else:
                    car_category = "unknown"

                # Normalize category values to match our choices
                category_mapping = {
                    "formula_car": "formula_car",
                    "sports_car": "sports_car",
                    "oval": "oval",
                    "unknown": "unknown",
                }
                normalized_category = category_mapping.get(car_category, "unknown")

                # Extract and clean car types array
                car_types_raw = car.get("car_types", [])
                if isinstance(car_types_raw, list):
                    # Clean and deduplicate car types
                    cleaned_types = []
                    seen_types = set()

                    for car_type in car_types_raw:
                        if isinstance(car_type, dict):
                            type_name = car_type.get("car_type", "").lower().strip()
                        else:
                            type_name = str(car_type).lower().strip()

                        # Skip empty or duplicate types
                        if not type_name or type_name in seen_types:
                            continue

                        # Normalize similar types (e.g., f1/formula1/formulaone -> formula1)
                        if type_name in ["f1", "formulaone"]:
                            type_name = "formula1"
                        elif type_name in ["stockcar"]:
                            type_name = "stock_car"

                        cleaned_types.append(type_name)
                        seen_types.add(type_name)
                else:
                    cleaned_types = []

                # Extract manufacturer and model names properly
                car_make = car.get("car_make", "").strip()
                car_model_name = car.get("car_model", "").strip()
                car_full_name = car.get("car_name", "").strip()

                # If car_model is empty, extract from car_name
                if not car_model_name and car_full_name:
                    if car_make and car_make in car_full_name:
                        # Remove manufacturer from full name to get model
                        car_model_name = car_full_name.replace(car_make, "").strip()
                        car_model_name = car_model_name.lstrip(" -").rstrip(" -")
                    else:
                        car_model_name = car_full_name

                # If car_make is empty, try to extract from car_name
                if not car_make and car_full_name:
                    car_make = self._extract_manufacturer(car_full_name)

                # Fallback values
                if not car_make:
                    car_make = "Unknown"
                if not car_model_name:
                    car_model_name = car_full_name or "Unknown"

                # NOTE: No longer creating artificial car classes from category
                # Real car classes will be imported via load_car_classes command

                # Prepare search filters for easier searching
                search_filters = [
                    car_make.lower(),
                    car_model_name.lower(),
                    normalized_category,
                ] + cleaned_types

                # Create or get car model with all new fields
                car_model_defaults = {
                    "slug": slugify(f"{car_make}-{car_model_name}"),
                    "full_name": car_full_name,
                    "abbreviated_name": car.get("car_name_abbreviated", ""),
                    "category": normalized_category,
                    "car_types": cleaned_types,
                    "horsepower": car.get("hp", 0),
                    "weight_lbs": car.get("car_weight", 0),
                    "has_headlights": car.get("has_headlights", False),
                    "has_multiple_dry_tire_types": car.get(
                        "has_multiple_dry_tire_types",
                        False,
                    ),
                    "has_rain_capable_tire_types": car.get(
                        "has_rain_capable_tire_types",
                        False,
                    ),
                    "rain_enabled": car.get("rain_enabled", False),
                    "ai_enabled": car.get("ai_enabled", False),
                    "search_filters": search_filters,
                    "base_specs": {
                        "hp": car.get("hp", 0),
                        "weight": car.get("car_weight", 0),
                        "displacement": car.get("displacement", 0),
                        "cylinders": car.get("cylinders", 0),
                        "fuel_capacity": car.get("fuel_capacity", 0),
                        "power_curve": car.get("power_curve", []),
                        "torque_curve": car.get("torque_curve", []),
                    },
                }

                car_model, model_created = CarModel.objects.get_or_create(
                    name=car_model_name,
                    manufacturer=car_make,
                    defaults=car_model_defaults,
                )

                if not model_created and force_update:
                    # Update existing car model with new data
                    for field, value in car_model_defaults.items():
                        if field != "slug":  # Don't update slug to avoid URL changes
                            setattr(car_model, field, value)
                    car_model.save()
                    updated_car_models += 1

                if model_created:
                    created_car_models += 1

                # Set is_active based on API's retired field
                is_active = not car.get("retired", False)
                sim_car_defaults = {
                    "car_model": car_model,
                    "package_id": car.get("package_id", 0),
                    "display_name": car_full_name,
                    "price": car.get("price", 0),
                    "price_display": car.get("price_display", ""),
                    "free_with_subscription": car.get("free_with_subscription", False),
                    "is_purchasable": car.get("is_ps_purchasable", True),
                    "max_power_adjust_pct": car.get("max_power_adjust_pct", 0),
                    "min_power_adjust_pct": car.get("min_power_adjust_pct", 0),
                    "max_weight_penalty_kg": car.get("max_weight_penalty_kg", 0),
                    "is_active": is_active,
                }

                # Prepare image URLs for downloading
                car_folder = car.get("folder", "")  # Get the folder path from API
                image_urls = {
                    "logo": car.get("logo", ""),
                    "small_image": car.get("small_image", ""),
                    "large_image": car.get("large_image", ""),
                }

                # Get or create by sim_api_id only (most reliable unique identifier)
                try:
                    sim_car = SimCar.objects.get(
                        simulator=simulator,
                        sim_api_id=str(car["car_id"]),
                    )
                    sim_created = False

                    if force_update:
                        # Update existing sim car with new data
                        for field, value in sim_car_defaults.items():
                            setattr(sim_car, field, value)

                        # Handle image downloads separately
                        for field, url in image_urls.items():
                            current_value = getattr(sim_car, field)
                            if url and self._should_update_image(current_value, url):
                                image_file = self._download_and_save_image(
                                    url,
                                    field,
                                    sim_car.display_name,
                                    car_folder,
                                    verbose,
                                )
                                if image_file:
                                    setattr(sim_car, field, image_file)

                        sim_car.save()
                        updated_sim_cars += 1

                except SimCar.DoesNotExist:
                    sim_car = SimCar(
                        simulator=simulator,
                        sim_api_id=str(car["car_id"]),
                        **sim_car_defaults,
                    )
                    sim_car.save()  # Save first to get the object saved

                    # Download and save images
                    for field, url in image_urls.items():
                        if url:
                            image_file = self._download_and_save_image(
                                url,
                                field,
                                sim_car.display_name,
                                car_folder,
                                verbose,
                            )
                            if image_file:
                                setattr(sim_car, field, image_file)

                    sim_car.save()  # Save again with images
                    sim_created = True
                    created_sim_cars += 1

                # If this car is active, mark all other cars with the same package_id as inactive
                if is_active:
                    SimCar.objects.filter(
                        simulator=simulator,
                        package_id=car.get("package_id", 0),
                    ).exclude(sim_api_id=str(car["car_id"])).update(is_active=False)

            except Exception as e:
                logger.error(
                    f"Error processing car {car.get('car_name', 'Unknown')}: {e}",
                )
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Cars: Created {created_car_classes} classes, "
                f"{created_car_models} models, {created_sim_cars} sim cars. "
                f"Updated {updated_car_models} models, {updated_sim_cars} sim cars.",
            ),
        )

    def process_tracks(
        self,
        simulator: Simulator,
        tracks_data: Any,
        force_update: bool,
        verbose: bool = False,
    ):
        """Process tracks data from iRacing API"""
        self.stdout.write("Processing iRacing tracks...")

        # Handle both list and dict responses
        if isinstance(tracks_data, dict):
            tracks = tracks_data.get("data", [])
        else:
            tracks = tracks_data if isinstance(tracks_data, list) else []

        created_track_models = 0
        created_sim_tracks = 0
        created_sim_layouts = 0
        updated_track_models = 0
        updated_sim_tracks = 0
        updated_sim_layouts = 0

        # Group tracks by track_name since each API entry is actually a track configuration
        tracks_by_name = {}
        for track in tracks:
            track_name = track.get("track_name", "Unknown")
            if track_name not in tracks_by_name:
                tracks_by_name[track_name] = []
            tracks_by_name[track_name].append(track)

        for track_name, track_configs in tracks_by_name.items():
            try:
                # Use the first config to get basic track info
                base_track = track_configs[0]

                # Determine basic track category (road vs oval) from configurations
                track_category = self._determine_track_category(track_configs)

                # Create or get track model (one per unique track name)
                track_model_defaults = {
                    "slug": slugify(track_name),
                    "country": self._parse_location_country(
                        base_track.get("location", ""),
                    ),
                    "location": base_track.get("location", ""),
                    "latitude": base_track.get("latitude"),
                    "longitude": base_track.get("longitude"),
                    "description": f"Track from iRacing: {track_name}",
                    "category": track_category,
                    "time_zone": base_track.get("time_zone", ""),
                    "site_url": base_track.get("site_url", ""),
                }

                track_model, model_created = TrackModel.objects.get_or_create(
                    name=track_name,
                    defaults=track_model_defaults,
                )

                if not model_created and force_update:
                    # Update existing track model
                    for field, value in track_model_defaults.items():
                        if field != "slug":  # Don't update slug to avoid URL changes
                            setattr(track_model, field, value)
                    track_model.save()
                    updated_track_models += 1

                if model_created:
                    created_track_models += 1

                # Prepare image URLs for downloading
                track_folder = base_track.get(
                    "folder",
                    "",
                )  # Get the folder path from API
                image_urls = {
                    "logo": base_track.get("logo", ""),
                    "small_image": base_track.get("small_image", ""),
                    "large_image": base_track.get("large_image", ""),
                }

                # Create or get sim track (one per track name in this simulator)
                # Use the first track config's track_id as the base API ID for the track
                base_track_id = str(base_track.get("track_id", ""))
                package_id = str(base_track.get("package_id", ""))

                sim_track_defaults = {
                    "sim_api_id": base_track_id,  # Use actual track_id from API
                    "package_id": package_id,  # Critical for ownership tracking
                    "display_name": track_name,
                    "slug": slugify(f"iracing-{track_name}"),
                    "is_laser_scanned": True, # All iRacing tracks are laser scanned
                    "rain_enabled": any(
                        config.get("rain_enabled", False) for config in track_configs
                    ),
                    "price": base_track.get("price"),  # May be None
                    "is_free": base_track.get("free_with_subscription", False),
                    "is_purchasable": base_track.get("is_ps_purchasable", True),
                    "search_filters": self._build_track_search_filters(
                        track_name,
                        track_configs,
                    ),
                    "is_active": True,
                }

                sim_track, track_created = SimTrack.objects.get_or_create(
                    simulator=simulator,
                    track_model=track_model,
                    defaults=sim_track_defaults,
                )

                if not track_created and force_update:
                    # Update existing sim track
                    for field, value in sim_track_defaults.items():
                        if field not in [
                            "sim_api_id",
                            "slug",
                        ]:  # Don't update these IDs
                            setattr(sim_track, field, value)

                    # Handle image downloads separately
                    for field, url in image_urls.items():
                        current_value = getattr(sim_track, field)
                        if url and self._should_update_image(current_value, url):
                            image_file = self._download_and_save_image(
                                url,
                                field,
                                sim_track.display_name,
                                track_folder,
                                verbose,
                            )
                            if image_file:
                                setattr(sim_track, field, image_file)

                    sim_track.save()
                    updated_sim_tracks += 1

                if track_created:
                    # Download and save images for new track
                    for field, url in image_urls.items():
                        if url:
                            image_file = self._download_and_save_image(
                                url,
                                field,
                                sim_track.display_name,
                                track_folder,
                                verbose,
                            )
                            if image_file:
                                setattr(sim_track, field, image_file)

                    sim_track.save()  # Save again with images
                    created_sim_tracks += 1

                # Create SimLayout for each track configuration
                for config in track_configs:
                    track_type = self._determine_track_type(
                        config.get("config_name", ""),
                    )
                    config_name = config.get("config_name", "Default")

                    layout_defaults = {
                        "name": config_name,
                        "slug": slugify(f"{track_name}-{config_name}"),
                        "type": track_type,
                        "layout_type": track_type,  # Set both fields for compatibility
                        "length_km": config.get("track_config_length", 0) * 1.60934,  # Convert miles to km
                        "image_url": config.get("track_map_image", ""),
                        "retired": config.get("retired", False),
                        # Technical specifications from API
                        "max_cars": config.get("max_cars"),
                        "grid_stalls": config.get("grid_stalls"),
                        "number_pitstalls": config.get("pit_stalls"),
                        "corners_per_lap": config.get("corners_per_lap"),
                        "qualify_laps": config.get("qualify_laps"),
                        "allow_rolling_start": config.get("rolling_start", True),
                        "pit_road_speed_limit": config.get("pit_road_speed_limit"),
                        "night_lighting": config.get("night_lighting", False),
                        "fully_lit": config.get("fully_lit", False),
                    }

                    layout, layout_created = SimLayout.objects.get_or_create(
                        sim_track=sim_track,
                        layout_code=str(
                            config["track_id"],
                        ),  # Use track_id as layout code
                        defaults=layout_defaults,
                    )

                    if not layout_created and force_update:
                        # Update existing layout
                        for field, value in layout_defaults.items():
                            if field not in ["slug"]:  # Don't update slug
                                setattr(layout, field, value)
                        layout.save()
                        updated_sim_layouts += 1

                    if layout_created:
                        created_sim_layouts += 1

            except Exception as e:
                logger.error(f"Error processing track {track_name}: {e}")
                continue

        self.stdout.write(
            self.style.SUCCESS(
                f"Tracks: Created {created_track_models} models, {created_sim_tracks} sim tracks, "
                f"{created_sim_layouts} layouts. Updated {updated_track_models} models, "
                f"{updated_sim_tracks} sim tracks, {updated_sim_layouts} layouts.",
            ),
        )

    def _extract_manufacturer(self, car_name: str) -> str:
        """Extract manufacturer from car_name when car_make is not available"""
        if not car_name:
            return "Unknown"

        # Common manufacturer patterns in iRacing
        manufacturers = [
            "Acura",
            "Audi",
            "BMW",
            "Chevrolet",
            "Ferrari",
            "Ford",
            "Honda",
            "Lamborghini",
            "McLaren",
            "Mercedes",
            "Mercedes-AMG",
            "Porsche",
            "Toyota",
            "Volkswagen",
            "Nissan",
            "Hyundai",
            "Pontiac",
            "Dallara",
            "Skip Barber",
            "Modified",
            "NASCAR",
            "IndyCar",
            "Formula",
            "Lotus",
            "Mazda",
            "Radical",
            "Cadillac",
            "Renault",
            "Williams",
            "Red Bull",
        ]

        car_name_upper = car_name.upper()
        for manufacturer in manufacturers:
            if manufacturer.upper() in car_name_upper:
                return manufacturer

        # If no manufacturer found, use first word
        return car_name.split()[0] if car_name else "Unknown"

    def _determine_track_type(self, config_name: str) -> str:
        """Determine track type based on configuration name"""
        config_lower = config_name.lower()

        if "oval" in config_lower:
            return TrackType.OVAL
        if "drag" in config_lower:
            return TrackType.DRAG
        if "rally" in config_lower or "dirt" in config_lower:
            return TrackType.RALLY
        if "street" in config_lower or "city" in config_lower:
            return TrackType.STREET
        return TrackType.ROAD

    def _parse_location_country(self, location: str) -> str:
        """Parse country from location string (e.g., 'Lakeville, Connecticut, USA' -> 'USA')"""
        if not location:
            return ""

        # Split by comma and take the last part as country
        parts = [part.strip() for part in location.split(",")]
        return parts[-1] if parts else ""

    def _determine_track_category(self, track_configs: list) -> str:
        """Determine overall track category (road vs oval) from track configurations"""
        oval_count = 0
        road_count = 0

        for config in track_configs:
            config_name = config.get("config_name", "").lower()
            if "oval" in config_name:
                oval_count += 1
            else:
                road_count += 1

        # If more configurations are oval, consider it an oval track
        return "oval" if oval_count > road_count else "road"

    def _build_track_search_filters(self, track_name: str, track_configs: list) -> str:
        """Build search filters string for track"""
        filters = [track_name.lower()]

        # Add configuration names
        for config in track_configs:
            config_name = config.get("config_name", "")
            if config_name:
                filters.append(config_name.lower())

        # Add track types
        track_types = set()
        for config in track_configs:
            track_type = self._determine_track_type(config.get("config_name", ""))
            track_types.add(track_type.lower())

        filters.extend(list(track_types))

        # Remove duplicates and join
        unique_filters = list(set(filters))
        return " ".join(unique_filters)

    def _should_update_image(self, current_image, new_url: str) -> bool:
        """
        Determine if an image should be updated.

        Args:
            current_image: Current ImageField value
            new_url: New image URL from API

        Returns:
            True if image should be updated, False otherwise
        """
        # If no new URL, don't update
        if not new_url:
            return False

        return True

    def _download_and_save_image(
        self,
        image_url: str,
        field_name: str,
        car_name: str,
        folder: str | None = None,
        verbose: bool = False,
    ) -> ContentFile | None:
        """
        Download an image from iRacing and return a ContentFile for saving to ImageField.

        Args:
            image_url: URL or filename from iRacing API
            field_name: Name of the field (for filename generation)
            car_name: Car name for filename generation

        Returns:
            ContentFile object or None if download fails
        """
        if not image_url:
            return None

        try:
            # Handle relative URLs from iRacing using the correct static image domain
            if image_url.startswith("/"):
                full_url = f"https://images-static.iracing.com{image_url}"
            elif not image_url.startswith("http"):
                # Handle filenames like "skipbarberformula2000-small.jpg" using provided folder
                if folder:
                    full_url = f"https://images-static.iracing.com{folder}/{image_url}"
                # Fallback: Extract car name by removing -small/-large suffix
                elif "-small." in image_url or "-large." in image_url:
                    car_folder = image_url.rsplit("-", 1)[
                        0
                    ]  # Remove -small/-large part
                    full_url = f"https://images-static.iracing.com/img/cars/{car_folder}/{image_url}"
                else:
                    # Fallback for other image types
                    full_url = f"https://images-static.iracing.com/img/cars/{image_url}"
            else:
                full_url = image_url

            # Download the image
            response = requests.get(full_url, timeout=10)
            response.raise_for_status()

            # Create filename
            car_slug = slugify(car_name.replace("[", "").replace("]", ""))
            file_extension = image_url.split(".")[-1] if "." in image_url else "jpg"
            filename = f"{car_slug}_{field_name}.{file_extension}"

            # Create ContentFile
            content_file = ContentFile(response.content, name=filename)
            if verbose:
                self.stdout.write(f"    Downloaded {field_name}: {filename}")
            return content_file

        except requests.RequestException as e:
            self.stdout.write(
                self.style.WARNING(
                    f"    Failed to download {field_name} from {image_url}: {e}",
                ),
            )
            return None
        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"    Error processing {field_name} image: {e}"),
            )
            return None
