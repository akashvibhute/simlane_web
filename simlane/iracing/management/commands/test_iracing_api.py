"""
Django management command to test iRacing API integration.

This command allows testing the iRacing API service and tasks
to ensure proper functionality.
"""

from django.conf import settings
from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from simlane.iracing.services import iracing_service
from simlane.iracing.tasks import fetch_cars_data
from simlane.iracing.tasks import fetch_member_summary
from simlane.iracing.tasks import fetch_series_data
from simlane.iracing.tasks import fetch_tracks_data


class Command(BaseCommand):
    help = "Test iRacing API integration"

    def add_arguments(self, parser):
        parser.add_argument(
            "--test-service",
            action="store_true",
            help="Test the iRacing service directly",
        )
        parser.add_argument(
            "--test-tasks",
            action="store_true",
            help="Test Celery tasks (requires Celery worker)",
        )
        parser.add_argument(
            "--cust-id",
            type=int,
            help="Customer ID for member-specific tests",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS("Testing iRacing API integration..."))

        # Check configuration
        if not settings.IRACING_USERNAME or not settings.IRACING_PASSWORD:
            raise CommandError(
                "iRacing credentials not configured. "
                "Please set IRACING_USERNAME and IRACING_PASSWORD environment variables.",
            )

        if options["test_service"]:
            self.test_service(options.get("cust_id"))

        if options["test_tasks"]:
            self.test_tasks(options.get("cust_id"))

        if not options["test_service"] and not options["test_tasks"]:
            self.stdout.write(
                self.style.WARNING(
                    "No test specified. Use --test-service or --test-tasks",
                ),
            )

    def test_service(self, cust_id=None):
        """Test the iRacing service directly."""
        self.stdout.write("Testing iRacing service...")

        try:
            # Test service availability
            if not iracing_service.is_available():
                raise CommandError("iRacing service is not available")

            self.stdout.write(self.style.SUCCESS("✓ iRacing service is available"))

            # Test member summary
            self.stdout.write("Testing member summary...")
            try:
                data = iracing_service.get_member_summary(cust_id=cust_id)
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Member summary fetched (customer: {data.get('cust_id', 'authenticated user')})",
                    ),
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Member summary failed: {e}"))

            # Test series data
            self.stdout.write("Testing series data...")
            try:
                data = iracing_service.get_series()
                series_count = len(data.get("series", []))
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Series data fetched ({series_count} series)",
                    ),
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Series data failed: {e}"))

            # Test cars data
            self.stdout.write("Testing cars data...")
            try:
                data = iracing_service.get_cars()
                cars_count = len(data.get("cars", []))
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Cars data fetched ({cars_count} cars)"),
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Cars data failed: {e}"))

            # Test tracks data
            self.stdout.write("Testing tracks data...")
            try:
                data = iracing_service.get_tracks()
                tracks_count = len(data.get("tracks", []))
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Tracks data fetched ({tracks_count} tracks)",
                    ),
                )
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"✗ Tracks data failed: {e}"))

        except Exception as e:
            raise CommandError(f"Service test failed: {e}")

    def test_tasks(self, cust_id=None):
        """Test Celery tasks."""
        self.stdout.write("Testing Celery tasks...")

        try:
            # Test member summary task
            self.stdout.write("Testing member summary task...")
            result = fetch_member_summary.delay(cust_id=cust_id)
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Member summary task queued (task ID: {result.id})",
                ),
            )

            # Test series data task
            self.stdout.write("Testing series data task...")
            result = fetch_series_data.delay()
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Series data task queued (task ID: {result.id})",
                ),
            )

            # Test cars data task
            self.stdout.write("Testing cars data task...")
            result = fetch_cars_data.delay()
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Cars data task queued (task ID: {result.id})",
                ),
            )

            # Test tracks data task
            self.stdout.write("Testing tracks data task...")
            result = fetch_tracks_data.delay()
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Tracks data task queued (task ID: {result.id})",
                ),
            )

            self.stdout.write(
                self.style.WARNING(
                    "Note: Tasks have been queued. Check Celery worker logs for results.",
                ),
            )

        except Exception as e:
            raise CommandError(f"Task test failed: {e}")
