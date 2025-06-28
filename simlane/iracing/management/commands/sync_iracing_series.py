"""Synchronise iRacing Series list into the local database.

This command fetches the complete list of iRacing series using
`IRacingAPIService.get_series()` and creates/updates the corresponding
`sim.Series` rows.

It is intentionally *minimal* – it does *not* pull seasons/schedules yet.
That will be added in follow-up iterations once this foundation is stable.
"""

from __future__ import annotations

import logging
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.utils.text import slugify

from simlane.iracing.services import iracing_service
from simlane.sim.models import Series, Simulator

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
            "--skip-past-seasons",
            action="store_true",
            help="Skip past seasons (default: False).",
        )

    # ---------------------------------------------------------------------
    # Command entry-point
    # ---------------------------------------------------------------------
    def handle(self, *args: Any, **options: Any):  # noqa: D401 – Django signature
        # Verbose logging – useful during development
        if options["verbose"]:
            logging.getLogger("simlane.iracing").setLevel(logging.DEBUG)
            logger.setLevel(logging.DEBUG)

        # Check service availability
        if not iracing_service.is_available():
            raise CommandError(
                "iRacing API service is not available – check credentials in settings."
            )

        dry_run: bool = bool(options["dry_run"])
        limit: int | None = options.get("limit")
        skip_past_seasons: bool = bool(options["skip_past_seasons"])

        self.stdout.write(self.style.SUCCESS("Fetching series list from iRacing …"))

        # Optional: fetch series assets (logos + copy). Fail-friendly.
        # series_assets_map: dict[int, dict] = {}
        try:
            series_assets_map = iracing_service.get_series_assets()

        except Exception as exc:  # noqa: PERF203 – optional call
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

        for obj in series_list:
            try:
                series_id = obj.get("series_id")
                if not series_id:
                    logger.debug("Skipping entry without series_id: %s", obj)
                    continue

                defaults = {
                    "name": obj.get("series_name", f"Series {series_id}"),
                    "slug": slugify(obj.get("series_name", str(series_id)))[:280],
                    "simulator": iracing_simulator,
                    "category": obj.get("category", ""),
                    "description": obj.get("forum_url", ""),  # temporary
                    "allowed_licenses": obj.get("allowed_licenses", []),
                }

                # --- Assets enrichment (logo + series copy) ---
                asset = series_assets_map.get(str(series_id))
                logo_rel = None
                logo_url_full = None
                if asset:
                    logo_rel = asset.get("logo") or asset.get("logo_small")
                    if logo_rel:
                        from simlane.sim.utils.image_downloader import (
                            download_image_from_url,
                            IRACING_BASE_URL,
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
                    logger.info("[DRY-RUN] Would upsert Series %s – %s", series_id, defaults["name"])
                    continue

                _, created_flag = Series.objects.update_or_create(
                    external_series_id=series_id,
                    defaults=defaults,
                )

                # Handle logo image download (outside update_or_create to ensure obj instance)
                if not dry_run and asset and logo_rel:
                    try:
                        from simlane.sim.utils.image_downloader import download_image_from_url
                        from simlane.sim.models import Series as SeriesModel

                        ser_obj: SeriesModel = Series.objects.get(external_series_id=series_id)

                        if not ser_obj.logo:  # Avoid re-downloading if already saved
                            logo_file = download_image_from_url(logo_url_full)
                            if logo_file:
                                ser_obj.logo.save(logo_file.name, logo_file, save=True)
                    except Exception as _img_exc:
                        logger.warning("Failed to download/save logo for series %s: %s", series_id, _img_exc)

                if created_flag:
                    created += 1
                else:
                    updated += 1

            except Exception as exc:  # pragma: no cover – problematic row
                logger.exception("Failed processing series object: %s", obj)
                self.stderr.write(self.style.ERROR(f"Error processing series {obj.get('series_id')}: {exc!s}"))

        if dry_run:
            self.stdout.write(self.style.SUCCESS("✓ DRY-RUN complete – no database writes performed."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✓ Series sync complete. Created: {created}, Updated: {updated}."
                )
            ) 