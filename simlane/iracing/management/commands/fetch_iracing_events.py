"""
Management command to fetch iRacing events and sync them to the database.
"""

import logging

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError
from django.utils import timezone

from simlane.iracing.services import iracing_service
from simlane.iracing.tasks import fetch_and_sync_events

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch iRacing events from the API and sync them to the database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--season-year",
            type=int,
            help="Season year to fetch (defaults to current year)",
        )
        parser.add_argument(
            "--season-quarter",
            type=int,
            choices=[1, 2, 3, 4],
            help="Season quarter to fetch (1-4, defaults to current quarter)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch data but don't save to database",
        )
        parser.add_argument(
            "--async",
            action="store_true",
            dest="use_async",
            help="Run the task asynchronously using Celery",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose output",
        )

    def handle(self, *args, **options):
        """Handle the management command execution."""

        # Set up logging level
        if options["verbose"]:
            logging.getLogger("simlane.iracing").setLevel(logging.DEBUG)

        # Check if iRacing service is available
        if not iracing_service.is_available():
            raise CommandError(
                "iRacing API service is not available. "
                "Please check your iRacing credentials in settings.",
            )

        # Get season parameters
        season_year = options.get("season_year")
        season_quarter = options.get("season_quarter")
        dry_run = options["dry_run"]
        use_async = options["use_async"]

        # Default to current date if not specified
        if season_year is None or season_quarter is None:
            current_date = timezone.now()
            if season_year is None:
                season_year = current_date.year
            if season_quarter is None:
                # Calculate quarter based on month
                season_quarter = ((current_date.month - 1) // 3) + 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Fetching iRacing events for {season_year} Q{season_quarter}",
            ),
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY RUN MODE: Data will be fetched but not saved to database",
                ),
            )

        try:
            if use_async:
                # Run asynchronously using Celery
                self.stdout.write("Starting asynchronous task...")
                task = fetch_and_sync_events.delay(
                    season_year=season_year,
                    season_quarter=season_quarter,
                    sync_to_database=not dry_run,
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Task started with ID: {task.id}"),
                )
                self.stdout.write(
                    "Use 'celery -A config worker -l info' to process the task",
                )
            else:
                # Run synchronously
                self.stdout.write("Starting synchronous execution...")

                # Execute the sync logic directly without Celery

                events_created = 0
                events_updated = 0
                errors = []

                # Fetch race guide for upcoming events
                try:
                    race_guide_data = iracing_service.get_season_race_guide()
                    self.stdout.write(
                        f"Fetched race guide with {len(race_guide_data.get('sessions', []))} sessions"
                    )

                    if not dry_run:
                        from simlane.iracing.tasks import _process_race_guide_events

                        created, updated, guide_errors = _process_race_guide_events(
                            race_guide_data
                        )
                        events_created += created
                        events_updated += updated
                        errors.extend(guide_errors)

                except Exception as e:
                    error_msg = f"Error processing race guide: {e!s}"
                    self.stdout.write(self.style.ERROR(error_msg))
                    errors.append(error_msg)

                # Fetch series seasons
                try:
                    series_seasons_data = iracing_service.get_series_seasons(
                        include_series=True
                    )
                    self.stdout.write(
                        f"Fetched {len(series_seasons_data)} series seasons"
                    )

                    if not dry_run:
                        from simlane.iracing.tasks import _process_series_seasons

                        created, updated, season_errors = _process_series_seasons(
                            series_seasons_data
                        )
                        events_created += created
                        events_updated += updated
                        errors.extend(season_errors)

                except Exception as e:
                    error_msg = f"Error processing series seasons: {e!s}"
                    self.stdout.write(self.style.ERROR(error_msg))
                    errors.append(error_msg)

                result = {
                    "success": True,
                    "events_created": events_created,
                    "events_updated": events_updated,
                    "errors": errors,
                }

                # Display results
                if result.get("success"):
                    self.stdout.write(
                        self.style.SUCCESS("✓ Event sync completed successfully!"),
                    )
                    self.stdout.write(
                        f"Events created: {result.get('events_created', 0)}",
                    )
                    self.stdout.write(
                        f"Events updated: {result.get('events_updated', 0)}",
                    )

                    errors = result.get("errors", [])
                    if errors:
                        self.stdout.write(
                            self.style.WARNING(f"Errors encountered: {len(errors)}"),
                        )
                        for error in errors:
                            self.stdout.write(self.style.ERROR(f"  - {error}"))
                else:
                    raise CommandError(
                        f"Task failed: {result.get('error', 'Unknown error')}"
                    )

        except Exception as e:
            logger.exception("Error executing fetch_iracing_events command")
            raise CommandError(f"Failed to fetch iRacing events: {e!s}")

        self.stdout.write(
            self.style.SUCCESS("Command completed successfully!"),
        )

    def show_api_endpoints(self):
        """Display available iRacing API endpoints for events."""
        self.stdout.write(
            self.style.SUCCESS("\n=== Available iRacing Event API Endpoints ===\n")
        )

        endpoints_info = [
            {
                "endpoint": "season_race_guide",
                "description": "Get upcoming race schedule with session times",
                "data_structure": {
                    "sessions": [
                        {
                            "session_id": "int - Unique session identifier",
                            "session_name": "str - Name of the session",
                            "start_time": "str - ISO format start time",
                            "series_name": "str - Name of the racing series",
                            "track": {
                                "track_name": "str - Name of the track",
                                "track_id": "int - Track identifier",
                            },
                            "car_classes": "list - Available car classes",
                        },
                    ],
                },
            },
            {
                "endpoint": "season_list",
                "description": "Get official seasons for a specific year/quarter",
                "data_structure": {
                    "seasons": [
                        {
                            "season_id": "int - Season identifier",
                            "season_name": "str - Season name",
                            "series_name": "str - Series name",
                            "active": "bool - Whether season is active",
                            "official": "bool - Whether season has standings",
                        },
                    ],
                },
            },
            {
                "endpoint": "series_seasons",
                "description": "Get all series and their seasons",
                "data_structure": {
                    "series_id": "int - Series identifier",
                    "series_name": "str - Series name",
                    "season_name": "str - Current season name",
                    "active": "bool - Whether series is active",
                    "official": "bool - Whether series is official",
                },
            },
            {
                "endpoint": "spectator_subsession_ids",
                "description": "Get live session IDs for different event types",
                "data_structure": {
                    "subsession_ids": [
                        "int - Live subsession identifiers",
                    ],
                },
            },
        ]

        for endpoint in endpoints_info:
            self.stdout.write(f"📍 {endpoint['endpoint']}")
            self.stdout.write(f"   {endpoint['description']}")
            self.stdout.write("   Data structure:")
            self._print_data_structure(endpoint["data_structure"], indent=6)
            self.stdout.write("")

    def _print_data_structure(self, data, indent=0):
        """Helper to print data structure in a readable format."""
        spaces = " " * indent

        if isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)):
                    self.stdout.write(f"{spaces}{key}:")
                    self._print_data_structure(value, indent + 2)
                else:
                    self.stdout.write(f"{spaces}{key}: {value}")
        elif isinstance(data, list):
            if data and isinstance(data[0], dict):
                self.stdout.write(f"{spaces}[")
                self._print_data_structure(data[0], indent + 2)
                self.stdout.write(f"{spaces}]")
            else:
                for item in data:
                    self.stdout.write(f"{spaces}- {item}")
