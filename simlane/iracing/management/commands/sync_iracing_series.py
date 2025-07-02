"""Synchronise iRacing Series list into the local database.

This command fetches the complete list of iRacing series using
`IRacingAPIService.get_series()` and creates/updates the corresponding
`sim.Series` rows.

It can optionally synchronise seasons and schedules for each series.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from simlane.iracing.services import iracing_service
from simlane.iracing.types import SeriesAsset
from simlane.sim.models import Series
from simlane.sim.models import Simulator
from simlane.iracing.tasks import sync_series_task

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Queue Celery task to sync iRacing series metadata only."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Bypass API cache when fetching data",
        )

    def handle(self, *args, **options):
        refresh = options.get("refresh", False)
        # queue task
        task = sync_series_task.delay(refresh=refresh)
        self.stdout.write(self.style.SUCCESS(f"Queued sync_series_task (id={task.id}) refresh={refresh}"))
