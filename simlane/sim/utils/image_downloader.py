"""
Utility functions for downloading and storing images from external sources.
"""

import logging
import os
import uuid
from io import BytesIO
from typing import Optional
from urllib.parse import urljoin, urlparse

import requests
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from simlane.core.models import MediaGallery

logger = logging.getLogger(__name__)

# iRacing base URL for images
IRACING_BASE_URL = "https://images-static.iracing.com"


def download_image_from_url(url: str, timeout: int = 30) -> Optional[ContentFile]:
    """
    Download an image from a URL and return a Django ContentFile.
    
    Args:
        url: The URL to download from
        timeout: Request timeout in seconds
        
    Returns:
        ContentFile object or None if download failed
    """
    try:
        # Handle relative URLs from iRacing
        if url.startswith('/'):
            url = urljoin(IRACING_BASE_URL, url)
        
        logger.info(f"Downloading image from: {url}")
        
        response = requests.get(url, timeout=timeout, stream=True)
        response.raise_for_status()
        
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        if not content_type.startswith('image/'):
            logger.warning(f"URL does not return an image: {url} (content-type: {content_type})")
            return None
        
        # Read image data
        image_data = BytesIO()
        for chunk in response.iter_content(chunk_size=8192):
            image_data.write(chunk)
        
        image_data.seek(0)
        
        # Generate filename from URL
        parsed_url = urlparse(url)
        filename = os.path.basename(parsed_url.path)
        if not filename or '.' not in filename:
            # Generate a filename if none exists
            extension = content_type.split('/')[-1] if '/' in content_type else 'jpg'
            filename = f"{uuid.uuid4().hex}.{extension}"
        
        return ContentFile(image_data.getvalue(), name=filename)
        
    except requests.RequestException as e:
        logger.error(f"Failed to download image from {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error downloading image from {url}: {e}")
        return None


def save_car_images(car_model, car_data: dict) -> dict:
    """
    Download and save images for a car model from iRacing API data.
    
    Args:
        car_model: CarModel instance
        car_data: Dictionary containing car data from iRacing API
        
    Returns:
        Dictionary with success/failure counts
    """
    results = {
        'logo': False,
        'small_image': False,
        'large_image': False,
        'gallery_images': 0,
        'gallery_errors': 0
    }
    
    # Download main images
    logo_url = car_data.get('logo')
    if logo_url:
        logo_file = download_image_from_url(logo_url)
        if logo_file:
            car_model.logo.save(logo_file.name, logo_file, save=True)
            results['logo'] = True
            logger.info(f"Saved logo for {car_model.full_name}")
    
    small_image_url = car_data.get('small_image')
    if small_image_url:
        # Construct full URL for small image
        if not small_image_url.startswith('http'):
            small_image_url = f"{IRACING_BASE_URL}/img/cars/{small_image_url}"
        
        small_file = download_image_from_url(small_image_url)
        if small_file:
            car_model.small_image.save(small_file.name, small_file, save=True)
            results['small_image'] = True
            logger.info(f"Saved small image for {car_model.full_name}")
    
    large_image_url = car_data.get('large_image')
    if large_image_url:
        # Construct full URL for large image
        if not large_image_url.startswith('http'):
            large_image_url = f"{IRACING_BASE_URL}/img/cars/{large_image_url}"
        
        large_file = download_image_from_url(large_image_url)
        if large_file:
            car_model.large_image.save(large_file.name, large_file, save=True)
            results['large_image'] = True
            logger.info(f"Saved large image for {car_model.full_name}")
    
    # Download gallery images (screenshots)
    screenshot_images = car_data.get('detail_screen_shot_images', '')
    if screenshot_images:
        screenshot_list = [img.strip() for img in screenshot_images.split(',') if img.strip()]
        
        for i, screenshot_name in enumerate(screenshot_list):
            try:
                # Construct full URL for screenshot
                if not screenshot_name.startswith('http'):
                    screenshot_url = f"{IRACING_BASE_URL}/img/cars/{screenshot_name}.jpg"
                else:
                    screenshot_url = screenshot_name
                
                screenshot_file = download_image_from_url(screenshot_url)
                if screenshot_file:
                    # Create gallery entry
                    MediaGallery.objects.create(
                        content_object=car_model,
                        gallery_type='screenshots',
                        image=screenshot_file,
                        caption=f"Screenshot {i + 1}",
                        order=i,
                        original_filename=screenshot_name,
                        original_url=screenshot_url
                    )
                    results['gallery_images'] += 1
                    logger.info(f"Saved screenshot {i + 1} for {car_model.full_name}")
                else:
                    results['gallery_errors'] += 1
                    
            except Exception as e:
                logger.error(f"Error saving screenshot {screenshot_name} for {car_model.full_name}: {e}")
                results['gallery_errors'] += 1
    
    return results


def _should_update_track_image(current_field, new_url: str) -> bool:
    """
    Check if we should update a track image field.
    
    Args:
        current_field: Current ImageField value
        new_url: New URL from API
        
    Returns:
        True if image should be updated
    """
    # If no current image, we should download
    if not current_field:
        return True
    
    # If current image exists as file, skip download
    try:
        if current_field.file:
            return False
    except (ValueError, FileNotFoundError):
        # Current image file missing, should re-download
        return True
    
    return True


def save_track_images(sim_track, track_data: dict) -> dict:
    """
    Download and save images for a track from iRacing API data.
    
    Args:
        sim_track: SimTrack instance
        track_data: Dictionary containing track data from iRacing API
        
    Returns:
        Dictionary with success/failure counts
    """
    results = {
        'logo': False,
        'small_image': False,
        'large_image': False,
        'skipped': 0
    }
    
    track_folder = track_data.get('folder', '')
    
    # Check and download logo
    logo_url = track_data.get('logo')
    if logo_url:
        if _should_update_track_image(sim_track.logo, logo_url):
            logo_file = download_image_from_url(logo_url)
            if logo_file:
                sim_track.logo.save(logo_file.name, logo_file, save=True)
                results['logo'] = True
                logger.info(f"Saved logo for {sim_track.display_name}")
        else:
            results['skipped'] += 1
            logger.info(f"Skipped logo for {sim_track.display_name} - file already exists")
    
    # Check and download small image
    small_image_url = track_data.get('small_image')
    if small_image_url:
        if _should_update_track_image(sim_track.small_image, small_image_url):
            # Construct full URL for small image
            if not small_image_url.startswith('http') and track_folder:
                small_image_url = f"{IRACING_BASE_URL}{track_folder}/{small_image_url}"
            elif not small_image_url.startswith('http'):
                small_image_url = f"{IRACING_BASE_URL}/img/tracks/{small_image_url}"
            
            small_file = download_image_from_url(small_image_url)
            if small_file:
                sim_track.small_image.save(small_file.name, small_file, save=True)
                results['small_image'] = True
                logger.info(f"Saved small image for {sim_track.display_name}")
        else:
            results['skipped'] += 1
            logger.info(f"Skipped small image for {sim_track.display_name} - file already exists")
    
    # Check and download large image
    large_image_url = track_data.get('large_image')
    if large_image_url:
        if _should_update_track_image(sim_track.large_image, large_image_url):
            # Construct full URL for large image
            if not large_image_url.startswith('http') and track_folder:
                large_image_url = f"{IRACING_BASE_URL}{track_folder}/{large_image_url}"
            elif not large_image_url.startswith('http'):
                large_image_url = f"{IRACING_BASE_URL}/img/tracks/{large_image_url}"
            
            large_file = download_image_from_url(large_image_url)
            if large_file:
                sim_track.large_image.save(large_file.name, large_file, save=True)
                results['large_image'] = True
                logger.info(f"Saved large image for {sim_track.display_name}")
        else:
            results['skipped'] += 1
            logger.info(f"Skipped large image for {sim_track.display_name} - file already exists")
    
    return results


def save_track_svg_maps(sim_layout, track_data: dict) -> dict:
    """
    Download and save SVG track map layers for a layout from iRacing API data.
    
    Args:
        sim_layout: SimLayout instance
        track_data: Dictionary containing track data from iRacing API
        
    Returns:
        Dictionary with success/failure counts
    """
    results = {
        'svg_layers': 0,
        'svg_errors': 0
    }
    
    # Check if track has SVG maps
    if not track_data.get('has_svg_map', False):
        return results
    
    base_url = track_data.get('track_map', '')
    layers_data = track_data.get('track_map_layers', {})
    
    if not base_url or not layers_data:
        return results
    
    # Check if SVG maps already exist
    existing_svg_maps = sim_layout.get_svg_map_layers()
    if existing_svg_maps.exists():
        # Check if we have all expected layers
        existing_captions = set(existing_svg_maps.values_list('caption', flat=True))
        expected_captions = set(layer_name.replace('-', ' ').title() for layer_name in layers_data.keys())
        
        if existing_captions >= expected_captions:  # We have all or more layers
            logger.info(f"Skipped SVG maps for {sim_layout} - files already exist")
            results['svg_layers'] = len(existing_captions)
            return results
        else:
            # Some layers missing, clean up and re-download all
            logger.info(f"Some SVG layers missing for {sim_layout}, re-downloading all")
            clean_existing_track_svg_maps(sim_layout)
    
    # No need to store metadata - MediaGallery entries are the source of truth
    
    # Download each SVG layer
    for i, (layer_name, filename) in enumerate(layers_data.items()):
        try:
            # Construct full URL
            svg_url = f"{base_url}{filename}"
            
            svg_file = download_image_from_url(svg_url)
            if svg_file:
                # Create gallery entry for this SVG layer
                MediaGallery.objects.create(
                    content_object=sim_layout,
                    gallery_type='track_maps',
                    image=svg_file,
                    caption=layer_name.replace('-', ' ').title(),  # "start-finish" -> "Start Finish"
                    order=i,
                    original_filename=filename,
                    original_url=svg_url
                )
                results['svg_layers'] += 1
                logger.info(f"Saved SVG layer '{layer_name}' for {sim_layout}")
            else:
                results['svg_errors'] += 1
                
        except Exception as e:
            logger.error(f"Error saving SVG layer {layer_name} for {sim_layout}: {e}")
            results['svg_errors'] += 1
    
    return results


def clean_existing_images(car_model):
    """
    Clean up existing images for a car model before re-downloading.
    
    Args:
        car_model: CarModel instance
    """
    # Delete existing image files
    if car_model.logo:
        car_model.logo.delete(save=False)
    if car_model.small_image:
        car_model.small_image.delete(save=False)
    if car_model.large_image:
        car_model.large_image.delete(save=False)
    
    # Delete existing gallery images
    gallery_items = MediaGallery.objects.filter(
        content_type__model='carmodel',
        object_id=str(car_model.id)
    )
    for item in gallery_items:
        if item.image:
            item.image.delete(save=False)
        item.delete()
    
    logger.info(f"Cleaned existing images for {car_model.full_name}")


def clean_existing_track_svg_maps(sim_layout):
    """
    Clean up existing SVG track map layers for a layout before re-downloading.
    
    Args:
        sim_layout: SimLayout instance
    """
    from django.contrib.contenttypes.models import ContentType
    
    # Delete existing SVG gallery images
    content_type = ContentType.objects.get_for_model(sim_layout)
    gallery_items = MediaGallery.objects.filter(
        content_type=content_type,
        object_id=str(sim_layout.id),
        gallery_type='track_maps'
    )
    for item in gallery_items:
        if item.image:
            item.image.delete(save=False)
        item.delete()
    
    # No metadata to clear - MediaGallery entries were the only storage
    
    logger.info(f"Cleaned existing SVG track maps for {sim_layout}") 