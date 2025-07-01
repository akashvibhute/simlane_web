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
from simlane.sim.models import Series
from simlane.sim.models import Simulator

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Fetch iRacing series metadata and upsert Series records."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch data but do not write to the database.",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Enable verbose logging output.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Only process the first N series (for quick testing).",
        )
        parser.add_argument(
            "--sync-seasons",
            action="store_true",
            help="Also sync current and future seasons for each series.",
        )
        parser.add_argument(
            "--sync-past-seasons",
            action="store_true",
            help="Also sync past seasons for each series (requires --sync-seasons).",
        )
        parser.add_argument(
            "--season-year",
            type=int,
            help="Specific season year to sync (optional).",
        )
        parser.add_argument(
            "--season-quarter",
            type=int,
            choices=[1, 2, 3, 4],
            help="Specific season quarter to sync (optional).",
        )
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Bypass cache and force fresh API calls.",
        )

    # ---------------------------------------------------------------------
    # Command entry-point
    # ---------------------------------------------------------------------
    def handle(self, *args: Any, **options: Any):
        # Verbose logging – useful during development
        if options["verbose"]:
            logging.getLogger("simlane.iracing").setLevel(logging.DEBUG)
            logger.setLevel(logging.DEBUG)

        # Check service availability
        if not iracing_service.is_available():
            raise CommandError(
                "iRacing API service is not available – check credentials in settings.",
            )

        dry_run: bool = bool(options["dry_run"])
        limit: int | None = options.get("limit")
        sync_seasons: bool = bool(options["sync_seasons"])
        sync_past_seasons: bool = bool(options["sync_past_seasons"])
        season_year: int | None = options.get("season_year")
        season_quarter: int | None = options.get("season_quarter")
        refresh: bool = bool(options["refresh"])

        # Validate arguments
        if sync_past_seasons and not sync_seasons:
            raise CommandError("--sync-past-seasons requires --sync-seasons")

        self.stdout.write(self.style.SUCCESS("Fetching series list from iRacing …"))

        # Optional: fetch series assets (logos + copy). Fail-friendly.
        series_assets_map: dict[str, dict] = {}
        try:
            series_assets_map = iracing_service.get_series_assets()
        except Exception as exc:
            logger.warning("Could not fetch series_assets: %s", exc)

        try:
            series_response = iracing_service.get_series()
        except Exception as exc:  # pragma: no cover – network error
            logger.exception("Error calling get_series()")
            raise CommandError(f"Failed to fetch series list: {exc!s}") from exc

        # API can return either a list directly or a dict with `data` key
        if isinstance(series_response, dict):
            series_list = series_response.get("data", [])
        else:
            series_list = series_response or []

        if not series_list:
            raise CommandError("No series returned – API response empty.")

        if limit:
            series_list = series_list[:limit]
            self.stdout.write(f"Limiting to first {limit} series for test run.")

        # Ensure we have the iRacing Simulator record for FK
        iracing_simulator, _created = Simulator.objects.get_or_create(
            name="iRacing",
            defaults={"is_active": True},
        )

        created = 0
        updated = 0
        season_tasks_queued = 0
        past_season_tasks_queued = 0

        for obj in series_list:
            try:
                series_id = obj.get("series_id")
                
                if not series_id:
                    logger.debug("Skipping entry without series_id: %s", obj)
                    continue
                
                defaults = {
                    "name": obj.get("series_name", f"Series {series_id}"),
                    "simulator": iracing_simulator,
                    "category": obj.get("category", ""),
                    "description": obj.get("forum_url", ""),  # temporary
                    "allowed_licenses": obj.get("allowed_licenses", []),
                }

                # --- Assets enrichment (logo + series copy) ---
                asset: dict | None = series_assets_map.get(str(series_id))
                logo_rel = None
                logo_url_full = None
                if asset:
                    logo_rel = asset.get("logo") or asset.get("logo_small")
                    if logo_rel:
                        from simlane.sim.utils.image_downloader import IRACING_BASE_URL
                        from simlane.sim.utils.image_downloader import (
                            download_image_from_url,
                        )

                        # build full URL if relative
                        logo_url_full = (
                            logo_rel
                            if logo_rel.startswith("http")
                            else f"{IRACING_BASE_URL}/img/logos/series/{logo_rel}"
                        )
                        defaults["logo_url"] = logo_url_full

                        # series_copy is a plain-text description
                        if asset.get("series_copy"):
                            defaults["description"] = asset["series_copy"].strip()

                if dry_run:
                    logger.info(
                        "[DRY-RUN] Would upsert Series %s – %s",
                        series_id,
                        defaults["name"],
                    )
                    continue

                _, created_flag = Series.objects.update_or_create(
                    external_series_id=series_id,
                    simulator=iracing_simulator,
                    defaults=defaults,
                )

                # Handle logo image download (outside update_or_create to ensure obj instance)
                if not dry_run and asset and logo_rel:
                    try:
                        from simlane.sim.models import Series as SeriesModel
                        from simlane.sim.utils.image_downloader import (
                            download_image_from_url,
                        )

                        ser_obj: SeriesModel = Series.objects.get(
                            external_series_id=series_id
                        )

                        if not ser_obj.logo:  # Avoid re-downloading if already saved
                            logo_file = download_image_from_url(logo_url_full or "")
                            if logo_file:
                                ser_obj.logo.save(logo_file.name, logo_file, save=True)
                    except Exception as _img_exc:
                        logger.warning(
                            "Failed to download/save logo for series %s: %s",
                            series_id,
                            _img_exc,
                        )

                if created_flag:
                    created += 1
                else:
                    updated += 1

            except Exception as exc:  # pragma: no cover – problematic row
                logger.exception("Failed processing series object: %s", obj)
                self.stderr.write(
                    self.style.ERROR(
                        f"Error processing series {obj.get('series_id')}: {exc!s}"
                    )
                )

        # --- Queue season sync tasks after processing all series ---
        if sync_seasons and not dry_run:
            try:
                # Import tasks here to avoid circular import issues
                from simlane.iracing.tasks import sync_past_seasons_batched_task
                from simlane.iracing.tasks import sync_series_seasons_task

                # Queue current/future seasons sync for all series (single API call)
                sync_series_seasons_task.delay(
                    series_id=None,  # None means sync all series
                    season_year=season_year,
                    season_quarter=season_quarter,
                    refresh=refresh,
                )
                season_tasks_queued = 1

                # Queue past seasons sync if requested (batched sequential processing)
                if sync_past_seasons:
                    # Collect all series IDs for batched processing
                    series_ids = [
                        obj.get("series_id") for obj in series_list 
                        if obj.get("series_id")
                    ]
                    
                    if series_ids:
                        # Queue single batched task that processes all series sequentially
                        sync_past_seasons_batched_task.delay(
                            series_ids=series_ids,
                            refresh=refresh,
                            batch_delay=10,  # 10 seconds between each series
                        )
                        past_season_tasks_queued = 1  # Single batched task
                        
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ Queued batched past seasons sync for {len(series_ids)} series "
                                f"(sequential processing with 10s delays)"
                            )
                        )

            except Exception as e:
                logger.error("Failed to queue season sync tasks: %s", e)

        # Summary output
        if dry_run:
            self.stdout.write(
                self.style.SUCCESS("✓ DRY-RUN complete – no database writes performed.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Series sync complete. Created: {created}, Updated: {updated}.",
                ),
            )

        if sync_seasons and not dry_run:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Season sync tasks queued: {season_tasks_queued} current/future (all series), {past_season_tasks_queued} past seasons.",
                ),
            )
