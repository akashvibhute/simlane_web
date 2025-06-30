#!/usr/bin/env python
"""
Fetch and save reference responses from iRacing API for documentation.
Uses PostgreSQL MCP to get required IDs from our database.
"""

import json
import os
import sys
import django

# Add the project root to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
django.setup()

from django.db import connection
from simlane.iracing.client import IRacingClient, IRacingAPIError

def get_sample_ids():
    """Get sample IDs from the database for API calls."""
    ids = {}
    
    with connection.cursor() as cursor:
        # Get a sample series ID
        cursor.execute("""
            SELECT external_series_id, name 
            FROM sim_series 
            WHERE external_series_id IS NOT NULL 
            LIMIT 1
        """)
        result = cursor.fetchone()
        if result:
            ids['series_id'] = result[0]
            ids['series_name'] = result[1]
            print(f"Using series: {result[1]} (ID: {result[0]})")
        
        # Get a sample season ID
        cursor.execute("""
            SELECT external_season_id, name, series_id 
            FROM sim_season 
            WHERE external_season_id IS NOT NULL 
            LIMIT 1
        """)
        result = cursor.fetchone()
        if result:
            ids['season_id'] = result[0]
            ids['season_name'] = result[1]
            print(f"Using season: {result[1]} (ID: {result[0]})")
    
    return ids

def save_response(endpoint_name: str, response_data):
    """Save API response to reference_responses directory."""
    output_dir = "docs/iracing/reference_responses"
    os.makedirs(output_dir, exist_ok=True)
    
    filename = f"{endpoint_name}.json"
    filepath = os.path.join(output_dir, filename)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(response_data, f, indent=2, ensure_ascii=False)
    
    print(f"  ✓ Saved to {filepath}")
    
    # Also save a truncated version for quick reference
    if isinstance(response_data, list) and len(response_data) > 3:
        truncated = response_data[:3]
        truncated_filename = f"{endpoint_name}_sample.json"
        truncated_filepath = os.path.join(output_dir, truncated_filename)
        
        with open(truncated_filepath, 'w', encoding='utf-8') as f:
            json.dump(truncated, f, indent=2, ensure_ascii=False)
        
        print(f"  ✓ Saved sample to {truncated_filepath}")

def fetch_all_responses():
    """Fetch and save all API endpoint responses."""
    print("Fetching iRacing API Reference Responses")
    print("=" * 50)
    
    # Get sample IDs from database
    ids = get_sample_ids()
    
    if not ids:
        print("✗ No sample data found in database. Please sync some data first.")
        return
    
    # Initialize client
    try:
        client = IRacingClient.from_settings()
        print("\n✓ Client initialized successfully\n")
    except Exception as e:
        print(f"✗ Failed to initialize client: {e}")
        return
    
    # Fetch responses for each endpoint
    endpoints = [
        {
            'name': 'member_info',
            'method': client.get_member_info,
            'args': [],
            'description': 'Member information for authenticated user'
        },
        {
            'name': 'series',
            'method': client.get_series,
            'args': [],
            'description': 'All available series'
        },
        {
            'name': 'series_assets',
            'method': client.get_series_assets,
            'args': [],
            'description': 'Series assets (logos, descriptions)'
        },
        {
            'name': 'series_seasons',
            'method': client.get_series_seasons,
            'args': [True],  # include_series=True
            'description': 'Current series seasons with details'
        },
        {
            'name': 'series_past_seasons',
            'method': client.get_series_past_seasons,
            'args': [ids.get('series_id', 260)],  # Default to Skip Barber if none found
            'description': f'Past seasons for series {ids.get("series_name", "Skip Barber")}'
        },
        {
            'name': 'season_schedule',
            'method': client.get_series_season_schedule,
            'args': [ids.get('season_id', 4627)],  # Default season ID if none found
            'description': f'Schedule for season {ids.get("season_name", "sample")}'
        },
        {
            'name': 'cars',
            'method': client.get_cars,
            'args': [],
            'description': 'All available cars'
        },
        {
            'name': 'car_assets',
            'method': client.get_car_assets,
            'args': [],
            'description': 'Car assets (images, etc.)'
        },
        {
            'name': 'tracks',
            'method': client.get_tracks,
            'args': [],
            'description': 'All available tracks'
        },
        {
            'name': 'track_assets',
            'method': client.get_track_assets,
            'args': [],
            'description': 'Track assets (images, etc.)'
        },
        {
            'name': 'car_classes',
            'method': client.get_car_classes,
            'args': [],
            'description': 'All car classes'
        }
    ]
    
    for endpoint in endpoints:
        print(f"\nFetching {endpoint['name']}...")
        print(f"  Description: {endpoint['description']}")
        
        try:
            # Call the endpoint
            response = endpoint['method'](*endpoint['args'])
            
            # Save the response
            save_response(endpoint['name'], response)
            
            # Print summary
            if isinstance(response, list):
                print(f"  ✓ Retrieved {len(response)} items")
            elif isinstance(response, dict):
                print(f"  ✓ Retrieved object with {len(response)} keys")
            
        except IRacingAPIError as e:
            print(f"  ✗ API Error: {e}")
            if e.status_code:
                print(f"     Status Code: {e.status_code}")
        except Exception as e:
            print(f"  ✗ Error: {e}")
    
    print("\n" + "=" * 50)
    print("✓ Reference response fetching completed!")
    print(f"\nResponses saved to: docs/iracing/reference_responses/")

if __name__ == "__main__":
    fetch_all_responses() 