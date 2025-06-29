"""Set up Celery Beat schedules for iRacing synchronization.

This command creates the necessary periodic tasks for automated iRacing data synchronization:
- Current seasons sync: Tuesday, Wednesday, Friday at 6 AM UTC
- Past seasons sync: Every 3 months (quarterly)
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule
from django_celery_beat.models import PeriodicTask

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Set up Celery Beat schedules for iRacing synchronization"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be created without actually creating it.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Force recreation of existing schedules.",
        )

    def handle(self, *args: Any, **options: Any):
        dry_run: bool = bool(options["dry_run"])
        force: bool = bool(options["force"])

        self.stdout.write(self.style.SUCCESS("Setting up iRacing sync schedules..."))

        schedules_to_create = [
            {
                "name": "iRacing Current Seasons Sync",
                "task": "simlane.iracing.tasks.sync_iracing_series_task",
                "cron": {
                    "minute": "0",
                    "hour": "6",
                    "day_of_week": "2,4,6",  # Tuesday, Thursday, Saturday
                    "day_of_month": "*",
                    "month_of_year": "*",
                },
                "kwargs": {
                    "sync_seasons": True,
                    "sync_past_seasons": False,
                },
                "description": "Sync current and future seasons every Tuesday, Wednesday, Friday at 6 AM UTC",
            },
            {
                "name": "iRacing Past Seasons Sync",
                "task": "simlane.iracing.tasks.sync_iracing_series_task",
                "cron": {
                    "minute": "0",
                    "hour": "7",
                    "day_of_week": "*",
                    "day_of_month": "1",  # First day of month
                    "month_of_year": "1,4,7,10",  # Every 3 months (Jan, Apr, Jul, Oct)
                },
                "kwargs": {
                    "sync_seasons": True,
                    "sync_past_seasons": True,
                },
                "description": "Sync past seasons quarterly on the 1st of Jan, Apr, Jul, Oct at 7 AM UTC",
            },
        ]

        created_count = 0
        updated_count = 0

        for schedule_config in schedules_to_create:
            try:
                # Create or get the cron schedule
                cron_schedule, cron_created = CrontabSchedule.objects.get_or_create(
                    minute=schedule_config["cron"]["minute"],
                    hour=schedule_config["cron"]["hour"],
                    day_of_week=schedule_config["cron"]["day_of_week"],
                    day_of_month=schedule_config["cron"]["day_of_month"],
                    month_of_year=schedule_config["cron"]["month_of_year"],
                    timezone="UTC",
                )

                if cron_created:
                    logger.info("Created cron schedule: %s", cron_schedule)

                # Check if periodic task already exists
                existing_task = PeriodicTask.objects.filter(
                    name=schedule_config["name"],
                ).first()

                if existing_task and not force:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Periodic task '{schedule_config['name']}' already exists. Use --force to recreate.",
                        ),
                    )
                    continue

                if existing_task and force:
                    # Update existing task
                    existing_task.task = schedule_config["task"]
                    existing_task.crontab = cron_schedule
                    existing_task.kwargs = str(schedule_config["kwargs"])
                    existing_task.description = schedule_config["description"]
                    existing_task.save()
                    updated_count += 1

                    if not dry_run:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Updated periodic task: {schedule_config['name']}",
                            ),
                        )
                    else:
                        self.stdout.write(
                            f"[DRY-RUN] Would update periodic task: {schedule_config['name']}",
                        )

                elif not existing_task:
                    # Create new task
                    if not dry_run:
                        PeriodicTask.objects.create(
                            name=schedule_config["name"],
                            task=schedule_config["task"],
                            crontab=cron_schedule,
                            kwargs=str(schedule_config["kwargs"]),
                            description=schedule_config["description"],
                            enabled=True,
                        )
                        created_count += 1

                        self.stdout.write(
                            self.style.SUCCESS(
                                f"Created periodic task: {schedule_config['name']}",
                            ),
                        )
                    else:
                        self.stdout.write(
                            f"[DRY-RUN] Would create periodic task: {schedule_config['name']}",
                        )

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"Error creating schedule '{schedule_config['name']}': {e!s}",
                    ),
                )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ DRY-RUN complete. Would create: {created_count}, Would update: {updated_count}",
                ),
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Setup complete. Created: {created_count}, Updated: {updated_count}",
                ),
            )

        # Show current schedules
        self.stdout.write("\nCurrent iRacing sync schedules:")
        for task in PeriodicTask.objects.filter(name__icontains="iRacing"):
            self.stdout.write(
                f"  - {task.name}: {task.task} (enabled: {task.enabled})",
            )
