"""
Refactored Celery tasks for iRacing data synchronization.

This module contains the new modular approach to syncing iRacing data:
- Series sync (basic series data only)
- Season sync (accepts season_id, handles schedule)
- Separate recurrence handling
"""

import logging
from typing import Any, Dict, List
from pathlib import Path

from celery import shared_task
from django.utils import timezone
from django.core.files.base import ContentFile
from django.contrib.contenttypes.models import ContentType
import requests

from simlane.iracing.services import IRacingServiceError, iracing_service
from simlane.iracing.season_sync import ScheduleProcessor, create_season_from_schedule_data
from simlane.iracing.types import PastSeasonsResponse, Series as SeriesType
from simlane.sim.models import CarClass, Season, Series, Simulator, SimLayout
from simlane.core.models import MediaGallery
from django.conf import settings

logger = logging.getLogger(__name__)


def _ensure_service_available() -> None:
    """Ensure iRacing service is available or raise custom error."""
    if not iracing_service.client:
        msg = "iRacing service not available"
        raise IRacingServiceError(msg)


def _get_or_create_iracing_series(
    series_id: int,
    series_info: SeriesType,
    iracing_simulator: Simulator,
) -> tuple:
    """
    Get or create an iRacing series (basic data only).

    Args:
        series_id: External series ID from iRacing
        series_info: Series information from API
        iracing_simulator: iRacing simulator instance

    Returns:
        Tuple of (series, created)
    """
    series_name = series_info.get("series_name", "")

    # Clean series name
    import re
    name_cleanup_patterns = [
        r"^iRacing\s+",
        r"\s+Series$",
        r"\s+Championship$",
        r"\s+Cup$",
    ]

    cleaned_name = series_name
    for pattern in name_cleanup_patterns:
        cleaned_name = re.sub(pattern, "", cleaned_name, flags=re.IGNORECASE)

    if not cleaned_name.strip():
        cleaned_name = series_name

    series, created = Series.objects.get_or_create(
        external_series_id=series_id,
        defaults={
            "name": cleaned_name,
            "simulator": iracing_simulator,
            "is_active": True,
        },
    )

    if not created:
        # Update existing series
        series.name = cleaned_name
        series.save(update_fields=["name"])

    return series, created


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_series_task(self, refresh: bool = False) -> Dict[str, Any]:
    """
    Sync series data only (no seasons or events).
    
    Args:
        refresh: Whether to bypass cache
        
    Returns:
        Dict containing sync results
    """
    try:
        logger.info("Syncing iRacing series data")
        _ensure_service_available()
        
        # Get iRacing simulator
        try:
            iracing_simulator = Simulator.objects.get(name="iRacing")
        except Simulator.DoesNotExist:
            error_msg = "iRacing simulator not found in database"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Fetch series data
        series_response = iracing_service.get_series()
        
        series_created = 0
        series_updated = 0
        errors = []
        
        for series_info in series_response:
            try:
                series_id = series_info.get("series_id")
                if not series_id:
                    continue
                
                series, created = _get_or_create_iracing_series(
                    series_id, series_info, iracing_simulator
                )
                
                if created:
                    series_created += 1
                    logger.debug(f"Created series: {series.name}")
                else:
                    series_updated += 1
                    logger.debug(f"Updated series: {series.name}")
                
            except Exception as e:
                error_msg = f"Error processing series {series_info.get('series_id', 'unknown')}: {e}"
                logger.exception(error_msg)
                errors.append(error_msg)
        
        result = {
            "success": True,
            "series_created": series_created,
            "series_updated": series_updated,
            "errors": errors,
            "completed_at": timezone.now().isoformat(),
        }
        
        logger.info(
            f"Series sync completed: {series_created} created, {series_updated} updated, "
            f"{len(errors)} errors"
        )
        
        return result
        
    except Exception as e:
        logger.exception("Failed to sync series")
        return {"success": False, "error": str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_season_task(self, season_id: int, refresh: bool = False) -> Dict[str, Any]:
    """
    Sync a specific season by ID and process its schedule.
    
    Args:
        season_id: iRacing season ID
        refresh: Whether to bypass cache
        
    Returns:
        Dict containing sync results
    """
    try:
        logger.info(f"Syncing season {season_id}")
        _ensure_service_available()
        
        # Get iRacing simulator
        try:
            iracing_simulator = Simulator.objects.get(name="iRacing")
        except Simulator.DoesNotExist:
            error_msg = "iRacing simulator not found in database"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Fetch season schedule
        schedule_data = iracing_service.get_series_season_schedule(season_id)
        
        if not schedule_data or "schedules" not in schedule_data:
            error_msg = f"No schedule data found for season {season_id}"
            logger.warning(error_msg)
            return {"success": False, "error": error_msg}
        
        # Get series information
        series_id = schedule_data.get("series_id")
        if not series_id:
            error_msg = f"No series_id in schedule data for season {season_id}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        try:
            series = Series.objects.get(external_series_id=series_id)
        except Series.DoesNotExist:
            error_msg = f"Series {series_id} not found. Run series sync first."
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Create or update season
        season = create_season_from_schedule_data(series, schedule_data)
        
        # Process schedule
        processor = ScheduleProcessor(iracing_simulator)
        events_created, events_updated, time_slots_created, errors = processor.process_season_schedule(
            season, schedule_data["schedules"]
        )
        
        result = {
            "success": True,
            "season_id": season_id,
            "season_name": season.name,
            "events_created": events_created,
            "events_updated": events_updated,
            "time_slots_created": time_slots_created,
            "errors": errors,
            "completed_at": timezone.now().isoformat(),
        }
        
        logger.info(
            f"Season {season_id} sync completed: {events_created} events created, "
            f"{events_updated} events updated, {time_slots_created} time slots created, "
            f"{len(errors)} errors"
        )
        
        return result
        
    except Exception as e:
        logger.exception(f"Failed to sync season {season_id}")
        return {"success": False, "error": str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_current_seasons_task(self, refresh: bool = False) -> Dict[str, Any]:
    """
    Sync current and future seasons for all series.
    
    This uses the series_seasons API which returns current season data
    and schedules for all series in a single call.
    
    Args:
        refresh: Whether to bypass cache
        
    Returns:
        Dict containing sync results
    """
    try:
        logger.info("Syncing current and future seasons for all series")
        _ensure_service_available()
        
        # Get iRacing simulator
        try:
            iracing_simulator = Simulator.objects.get(name="iRacing")
        except Simulator.DoesNotExist:
            error_msg = "iRacing simulator not found in database"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Fetch current seasons data (includes schedules)
        seasons_data = iracing_service.get_series_seasons(include_series=True)
        
        total_seasons_processed = 0
        total_events_created = 0
        total_events_updated = 0
        total_time_slots_created = 0
        all_errors = []
        
        for season_data in seasons_data:
            try:
                series_id = season_data.get("series_id")
                if not series_id:
                    continue
                
                # Ensure series exists
                try:
                    series = Series.objects.get(external_series_id=series_id)
                except Series.DoesNotExist:
                    logger.warning(f"Series {series_id} not found. Skipping seasons.")
                    continue
                
                # Create season if it doesn't exist
                season_id = season_data.get("season_id")
                if not season_id:
                    continue
                
                season, created = Season.objects.get_or_create(
                    external_season_id=season_id,
                    defaults={
                        "name": season_data.get("name", ""),
                        "start_date": season_data.get("start_date"),
                        "end_date": season_data.get("end_date"),
                        "active": season_data.get("active", False),
                        "complete": season_data.get("complete", False),
                        "series": series,
                    }
                )
                
                # Process schedules
                schedules = season_data.get("schedules", [])
                if schedules:
                    processor = ScheduleProcessor(iracing_simulator)
                    events_created, events_updated, time_slots_created, errors = (
                        processor.process_season_schedule(season, schedules)
                            )
                            
                total_events_created += events_created
                total_events_updated += events_updated  
                total_time_slots_created += time_slots_created
                all_errors.extend(errors)
                
                total_seasons_processed += 1
                
            except Exception as e:
                error_msg = f"Error processing series current season for {season_data.get('series_id', 'unknown')}: {e}"
                logger.exception(error_msg)
                all_errors.append(error_msg)
                
        
        result = {
            "success": True,
            "seasons_processed": total_seasons_processed,
            "events_created": total_events_created,
            "events_updated": total_events_updated,
            "time_slots_created": total_time_slots_created,
            "errors": all_errors,
            "completed_at": timezone.now().isoformat(),
        }
        
        logger.info(
            f"Current seasons sync completed: {total_seasons_processed} seasons processed, "
            f"{total_events_created} events created, {total_events_updated} events updated, "
            f"{total_time_slots_created} time slots created, {len(all_errors)} errors"
        )
        
        return result
        
    except Exception as e:
        logger.exception("Failed to sync current seasons")
        return {"success": False, "error": str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_past_seasons_for_series_task(
    self, series_id: int, refresh: bool = False
) -> Dict[str, Any]:
    """
    Sync past seasons for a specific series.
    
    Args:
        series_id: iRacing series ID
        refresh: Whether to bypass cache
        
    Returns:
        Dict containing sync results
    """
    try:
        logger.info(f"Syncing past seasons for series {series_id}")
        _ensure_service_available()
        
        # Ensure series exists
        try:
            series = Series.objects.get(external_series_id=series_id)
        except Series.DoesNotExist:
            error_msg = f"Series {series_id} not found. Run series sync first."
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Get past seasons for this series
        past_seasons_data: PastSeasonsResponse = iracing_service.get_series_past_seasons(series_id)
        
        if not past_seasons_data:
            logger.info(f"No past seasons found for series {series_id}")
            return {
                "success": True,
                "series_id": series_id,
                "seasons_queued": 0,
                "message": "No past seasons found",
            }
        
        # Queue individual season sync tasks
        seasons_queued = 0
        series = past_seasons_data["series"]
        past_seasons = series["seasons"]
        
        for season_info in past_seasons:
            season_id = season_info.get("season_id")
            if season_id:
                # Queue the season sync task - using apply_async to avoid naming conflicts
                from celery import current_app
                current_app.send_task('simlane.iracing.tasks.sync_season_task', args=[season_id], kwargs={'refresh': refresh})
                seasons_queued += 1
                logger.debug(f"Queued season {season_id} for sync")
        
        result = {
            "success": True,
            "series_id": series_id,
            "series_name": series["series_name"],
            "seasons_queued": seasons_queued,
            "completed_at": timezone.now().isoformat(),
        }
        
        logger.info(
            f"Past seasons sync for series {series_id} completed: "
            f"{seasons_queued} seasons queued for processing"
        )
        
        return result
        
    except Exception as e:
        logger.exception(f"Failed to sync past seasons for series {series_id}")
        return {"success": False, "error": str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def queue_all_past_seasons_sync_task(self, refresh: bool = False) -> Dict[str, Any]:
    """
    Queue past season sync tasks for all series.
    
    This task finds all series and queues individual past season sync tasks.
    
    Args:
        refresh: Whether to bypass cache
        
    Returns:
        Dict containing sync results
    """
    try:
        logger.info("Queuing past seasons sync for all series")
        
        # Get all iRacing series
        iracing_series = Series.objects.filter(
            simulator__name="iRacing",
            is_active=True
        ).values_list("external_series_id", flat=True)
        
        series_queued = 0
        
        for series_id in iracing_series:
            if series_id:
                # Queue past seasons sync for this series - using apply_async to avoid naming conflicts
                from celery import current_app
                current_app.send_task('simlane.iracing.tasks.sync_past_seasons_for_series_task', args=[series_id], kwargs={'refresh': refresh})
                series_queued += 1
                logger.debug(f"Queued past seasons sync for series {series_id}")
        
        result = {
            "success": True,
            "series_queued": series_queued,
            "completed_at": timezone.now().isoformat(),
        }
        
        logger.info(f"Queued past seasons sync for {series_queued} series")
        
        return result
        
    except Exception as e:
        logger.exception("Failed to queue past seasons sync")
        return {"success": False, "error": str(e)}


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_car_classes_task(self, refresh: bool = False) -> Dict[str, Any]:
    """
    Sync car classes from iRacing API.
    
    Args:
        refresh: Whether to bypass cache
        
    Returns:
        Dict containing sync results
    """
    try:
        logger.info("Syncing iRacing car classes")
        _ensure_service_available()
        
        # Get iRacing simulator
        try:
            iracing_simulator = Simulator.objects.get(name="iRacing")
        except Simulator.DoesNotExist:
            error_msg = "iRacing simulator not found in database"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Fetch car classes
        car_classes_data = iracing_service.get_car_classes()
        
        classes_created = 0
        classes_updated = 0
        errors = []
        
        for car_class_info in car_classes_data:
            try:
                car_class_id = car_class_info.get("car_class_id")
                if not car_class_id:
                    continue
                
                car_class, created = CarClass.objects.get_or_create(
                    sim_api_id=car_class_id,
                    simulator=iracing_simulator,
                    defaults={
                        "name": car_class_info.get("name", ""),
                        "short_name": car_class_info.get("short_name", ""),
                        "relative_speed": car_class_info.get("relative_speed"),
                        "rain_enabled": car_class_info.get("rain_enabled", False),
                        "car_sim_api_ids": car_class_info.get("cars_in_class", []),
                    },
                )
                
                if not created:
                    # Update existing car class
                    car_class.name = car_class_info.get("name", car_class.name)
                    car_class.short_name = car_class_info.get("short_name", car_class.short_name)
                    car_class.relative_speed = car_class_info.get("relative_speed", car_class.relative_speed)
                    car_class.rain_enabled = car_class_info.get("rain_enabled", car_class.rain_enabled)
                    car_class.car_sim_api_ids = car_class_info.get("cars_in_class", car_class.car_sim_api_ids)
                    car_class.save()
                    classes_updated += 1
                else:
                    classes_created += 1
                
                logger.debug(f"{'Created' if created else 'Updated'} car class: {car_class.name}")
                
            except Exception as e:
                error_msg = f"Error processing car class {car_class_info.get('car_class_id', 'unknown')}: {e}"
                logger.exception(error_msg)
                errors.append(error_msg)
        
        result = {
            "success": True,
            "classes_created": classes_created,
            "classes_updated": classes_updated,
            "errors": errors,
            "completed_at": timezone.now().isoformat(),
        }
        
        logger.info(
            f"Car classes sync completed: {classes_created} created, {classes_updated} updated, "
            f"{len(errors)} errors"
        )
        
        return result
        
    except Exception as e:
        logger.exception("Failed to sync car classes")
        return {"success": False, "error": str(e)}


# Keep the existing owned content sync task as it works fine
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_iracing_owned_content(self, sim_profile_id: int) -> Dict[str, Any]:
    """
    Sync owned cars and tracks for a specific sim profile.
    
    Args:
        sim_profile_id: SimProfile ID
        
    Returns:
        Dict containing sync results
    """
    try:
        from simlane.sim.models import SimProfile, SimProfileCarOwnership, SimProfileTrackOwnership
        
        logger.info(f"Syncing owned content for sim profile {sim_profile_id}")
        _ensure_service_available()
        
        # Get the sim profile
        try:
            sim_profile = SimProfile.objects.get(id=sim_profile_id)
        except SimProfile.DoesNotExist:
            error_msg = f"SimProfile {sim_profile_id} not found"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        if not sim_profile.sim_api_id:
            error_msg = f"SimProfile {sim_profile_id} has no sim_api_id"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Get member info which includes owned content
        member_info = iracing_service.get_member_info()
        
        owned_cars = member_info.get("owned", {}).get("cars", [])
        owned_tracks = member_info.get("owned", {}).get("tracks", [])
        
        # Sync owned cars
        cars_synced = 0
        for car_id in owned_cars:
            from simlane.sim.models import SimCar
            
            try:
                sim_car = SimCar.objects.get(
                    sim_api_id=car_id,
                    simulator=sim_profile.simulator
                )
                
                SimProfileCarOwnership.objects.get_or_create(
                    sim_profile=sim_profile,
                    sim_car=sim_car,
                )
                cars_synced += 1
                
            except SimCar.DoesNotExist:
                logger.warning(f"SimCar not found for car_id {car_id}")
        
        # Sync owned tracks
        tracks_synced = 0
        for track_id in owned_tracks:
            from simlane.sim.models import SimTrack
            
            try:
                sim_track = SimTrack.objects.get(
                    sim_api_id=track_id,
                    simulator=sim_profile.simulator
                )
                
                SimProfileTrackOwnership.objects.get_or_create(
                    sim_profile=sim_profile,
                    sim_track=sim_track,
                )
                tracks_synced += 1
                
            except SimTrack.DoesNotExist:
                logger.warning(f"SimTrack not found for track_id {track_id}")
        
        result = {
            "success": True,
            "sim_profile_id": sim_profile_id,
            "cars_synced": cars_synced,
            "tracks_synced": tracks_synced,
            "completed_at": timezone.now().isoformat(),
        }
        
        logger.info(
            f"Owned content sync completed for profile {sim_profile_id}: "
            f"{cars_synced} cars, {tracks_synced} tracks"
        )
        
        return result
        
    except Exception as e:
        logger.exception(f"Failed to sync owned content for profile {sim_profile_id}")
        return {"success": False, "error": str(e)}


# -------------------------
# Track SVG map syncing
# -------------------------

def sync_track_svg_maps(refresh: bool = False) -> dict:
    """Download SVG layers for iRacing tracks and save to MediaGallery.

    This function contains the actual logic so it can be called directly from
    tests or a Django management command. The Celery task wrapper below just
    delegates to it.
    """
    try:
        logger.info("Starting track SVG map sync (refresh=%s)", refresh)

        # Pull assets and track list from API
        try:
            track_assets = iracing_service.get_track_assets()
            
        except Exception as e:
            logger.exception("Failed to fetch assets or track list")
            return {"success": False, "error": str(e)}

        iracing_sim = Simulator.objects.get(name="iRacing")
        layouts = SimLayout.objects.filter(sim_track__simulator=iracing_sim)

        processed = created = skipped = errors = 0
        error_list: list[str] = []

        content_type = ContentType.objects.get_for_model(SimLayout)

        import random, string

        for layout in layouts:
            processed += 1
            try:
                track_id_int = int(layout.layout_code)
            except (TypeError, ValueError):
                skipped += 1
                continue

            asset = track_assets.get(str(track_id_int))
            if not asset:
                skipped += 1
                continue

            base_url = asset.get("track_map")
            layers = asset.get("track_map_layers", {})
            if not base_url or not layers:
                skipped += 1
                continue

            existing_captions = set(
                MediaGallery.objects.filter(
                    content_type=content_type,
                    object_id=str(layout.id),
                    gallery_type="track_maps",
                ).values_list("caption", flat=True)
            )

            for order, (layer_name, filename) in enumerate(layers.items()):
                if layer_name in existing_captions and not refresh:
                    continue

                url = f"{base_url}{filename}"
                try:
                    resp = requests.get(url, timeout=15)
                    resp.raise_for_status()

                    file_content = ContentFile(resp.content)
                    random_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=6))
                    file_name = f"{layout.slug}-{layer_name}-{random_suffix}.svg"

                    gallery_item, _ = MediaGallery.objects.get_or_create(
                        content_type=content_type,
                        object_id=str(layout.id),
                        gallery_type="track_maps",
                        caption=layer_name,
                        defaults={"order": order, "original_url": url},
                    )
                    gallery_item.image.save(file_name, file_content, save=True)
                    created += 1

                except Exception as e:
                    errors += 1
                    error_list.append(f"{layout} {layer_name}: {e}")
                    logger.exception("Failed to download SVG for %s layer %s", layout, layer_name)

        result = {
            "success": True,
            "layouts_processed": processed,
            "svg_created": created,
            "skipped": skipped,
            "errors": errors,
            "error_details": error_list[:20],
        }
        logger.info(
            "Track SVG map sync finished: %d processed, %d created, %d skipped, %d errors",
            processed,
            created,
            skipped,
            errors,
        )
        return result

    except Exception as exc:
        logger.exception("Track SVG map sync failed")
        return {"success": False, "error": str(exc)}


# Celery wrapper

@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def sync_track_svg_maps_task(self, refresh: bool = False):  # noqa: D401
    """Celery wrapper around :pyfunc:`sync_track_svg_maps`."""
    return sync_track_svg_maps(refresh) 