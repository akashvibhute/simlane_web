#!/usr/bin/env python
"""
Direct test script for iRacing sync - no Celery, no queuing
Run this in Django shell to isolate exactly where SSL/connection errors occur

Usage:
    docker compose exec django python manage.py shell
    >>> exec(open('test_iracing_sync_direct.py').read())
"""

import logging
import traceback
from simlane.iracing.services import iracing_service
from simlane.iracing.tasks import _process_series_seasons
from simlane.sim.models import Series, Simulator

# Enable debug logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_single_series_sync(series_id=None, test_past_seasons=True):
    """
    Test syncing a single series with current and past seasons
    Returns detailed info about what succeeded/failed
    """
    results = {
        "series_list_fetch": None,
        "current_seasons_fetch": None,
        "past_seasons_fetch": None,
        "current_seasons_process": None,
        "past_seasons_process": None,
        "errors": []
    }
    
    try:
        print("=" * 60)
        print("TESTING iRacing SYNC - DIRECT (No Celery)")
        print("=" * 60)
        
        # Check service availability
        print("\n1. Checking iRacing service availability...")
        if not iracing_service.is_available():
            raise Exception("iRacing service not available")
        print("✓ iRacing service is available")
        
        # Step 1: Get series list
        print("\n2. Fetching series list...")
        try:
            series_response = iracing_service.get_series()
            if isinstance(series_response, dict):
                series_list = series_response.get("data", [])
            else:
                series_list = series_response or []
            
            print(f"✓ Fetched {len(series_list)} series")
            results["series_list_fetch"] = "SUCCESS"
            
            # Pick a series to test (use specified or first one)
            if series_id:
                test_series = next((s for s in series_list if s.get("series_id") == series_id), None)
                if not test_series:
                    raise Exception(f"Series {series_id} not found in series list")
            else:
                test_series = series_list[0] if series_list else None
                
            if not test_series:
                raise Exception("No series found to test")
                
            test_series_id = test_series.get("series_id")
            test_series_name = test_series.get("series_name", "Unknown")
            print(f"✓ Testing with series {test_series_id}: {test_series_name}")
            
        except Exception as e:
            error_msg = f"Error fetching series list: {e}"
            print(f"✗ {error_msg}")
            results["series_list_fetch"] = "FAILED"
            results["errors"].append(error_msg)
            return results
        
        # Step 2: Test current seasons fetch
        print("\n3. Testing current/future seasons fetch...")
        try:
            # This is the same call that sync_series_seasons_task makes
            current_seasons_data = iracing_service.get_series_seasons(include_series=True)
            
            # Filter to our test series
            test_series_seasons = [s for s in current_seasons_data if s.get("series_id") == test_series_id]
            
            print(f"✓ Fetched current seasons data for series {test_series_id}")
            if test_series_seasons:
                seasons_count = len(test_series_seasons[0].get("seasons", []))
                print(f"  - Found {seasons_count} current/future seasons")
            results["current_seasons_fetch"] = "SUCCESS"
            
        except Exception as e:
            error_msg = f"Error fetching current seasons: {e}"
            print(f"✗ {error_msg}")
            results["current_seasons_fetch"] = "FAILED"
            results["errors"].append(error_msg)
            traceback.print_exc()
        
        # Step 3: Test current seasons processing
        print("\n4. Testing current seasons processing...")
        try:
            if results["current_seasons_fetch"] == "SUCCESS" and test_series_seasons:
                created, updated, errors = _process_series_seasons(test_series_seasons)
                print(f"✓ Processed current seasons: {created} created, {updated} updated, {len(errors)} errors")
                if errors:
                    print(f"  - Processing errors: {errors[:3]}")  # Show first 3 errors
                results["current_seasons_process"] = "SUCCESS"
            else:
                print("⚠ Skipping current seasons processing due to fetch failure")
                
        except Exception as e:
            error_msg = f"Error processing current seasons: {e}"
            print(f"✗ {error_msg}")
            results["current_seasons_process"] = "FAILED"
            results["errors"].append(error_msg)
            traceback.print_exc()
        
        # Step 4: Test past seasons fetch (if requested)
        if test_past_seasons:
            print(f"\n5. Testing past seasons fetch for series {test_series_id}...")
            try:
                # This is the call that causes the most API load
                past_seasons_response = iracing_service.get_series_past_seasons(series_id=test_series_id)
                
                if isinstance(past_seasons_response, dict) and "seasons" in past_seasons_response:
                    past_seasons = past_seasons_response["seasons"]
                    print(f"✓ Fetched {len(past_seasons)} past seasons for series {test_series_id}")
                    results["past_seasons_fetch"] = "SUCCESS"
                    
                    # Step 5: Test processing a few past seasons
                    print("\n6. Testing past seasons processing...")
                    try:
                        # Process only first 2 past seasons to test the logic
                        # test_past_seasons = past_seasons[:2] if len(past_seasons) > 2 else past_seasons
                        test_past_seasons = past_seasons
                        for i, past_season in enumerate(test_past_seasons):
                            season_id = past_season.get("season_id")
                            season_name = past_season.get("season_name", "Unknown")
                            print(f"  - Testing past season {i+1}/{len(test_past_seasons)}: {season_id} ({season_name})")
                            
                            try:
                                # This is another API call that could cause issues
                                season_schedule_response = iracing_service.get_series_season_schedule(season_id)
                                schedules = season_schedule_response.get("schedules", [])
                                print(f"    ✓ Fetched {len(schedules)} schedules for season {season_id}")
                                
                                # Test the transformation logic that was causing UUID errors
                                transformed_season = {
                                    "season_id": season_id,
                                    "season_name": past_season.get("season_name", ""),
                                    "season_year": past_season.get("season_year"),
                                    "season_quarter": past_season.get("season_quarter"),
                                    "series_id": test_series_id,
                                    "schedules": schedules
                                }
                                
                                print(f"    ℹ Season details: {season_name}, Year: {past_season.get('season_year')}, Quarter: {past_season.get('season_quarter')}")
                                
                                season_data = {
                                    "series_id": test_series_id,
                                    "series_name": test_series_name,
                                    "allowed_licenses": test_series.get("allowed_licenses", []),
                                    "seasons": [transformed_season],
                                }
                                
                                # Show some schedule details for debugging
                                if schedules:
                                    sample_schedule = schedules[0]
                                    print(f"    ℹ Sample schedule: Week {sample_schedule.get('race_week_num')}, Track: {sample_schedule.get('track', {}).get('track_name', 'Unknown')}")
                                
                                # Test processing
                                created, updated, season_errors = _process_series_seasons([season_data])
                                print(f"    ✓ Processed: {created} created, {updated} updated, {len(season_errors)} errors")
                                
                                # Check the season that was created/updated
                                try:
                                    from simlane.sim.models import Season, Event
                                    season_obj = Season.objects.get(external_season_id=season_id)
                                    print(f"    ℹ Season status: active={season_obj.active}, complete={season_obj.complete}")
                                    print(f"    ℹ Season dates: {season_obj.start_date} to {season_obj.end_date}")
                                    
                                    # Check a sample event from this season
                                    sample_event = Event.objects.filter(season=season_obj).first()
                                    if sample_event:
                                        print(f"    ℹ Sample event: '{sample_event.name}' (slug: '{sample_event.slug}')")
                                        print(f"    ℹ Weather config: {bool(sample_event.weather_config)}")
                                        print(f"    ℹ Time pattern: {bool(sample_event.time_pattern)}")
                                        print(f"    ℹ Temp range: {sample_event.min_air_temp}°C to {sample_event.max_air_temp}°C")
                                        print(f"    ℹ Car restrictions: {sample_event.car_restrictions.count()}")
                                        
                                except Exception as e:
                                    print(f"    ⚠ Could not retrieve season/event info: {e}")
                                
                                if season_errors:
                                    print(f"    ⚠ Processing errors: {season_errors[:2]}")
                                    
                            except Exception as e:
                                error_msg = f"Error processing past season {season_id}: {e}"
                                print(f"    ✗ {error_msg}")
                                results["errors"].append(error_msg)
                                traceback.print_exc()
                                
                        results["past_seasons_process"] = "SUCCESS"
                        
                    except Exception as e:
                        error_msg = f"Error in past seasons processing: {e}"
                        print(f"✗ {error_msg}")
                        results["past_seasons_process"] = "FAILED"
                        results["errors"].append(error_msg)
                        traceback.print_exc()
                        
                else:
                    error_msg = f"Unexpected past seasons response format: {type(past_seasons_response)}"
                    print(f"✗ {error_msg}")
                    results["past_seasons_fetch"] = "FAILED"
                    results["errors"].append(error_msg)
                    
            except Exception as e:
                error_msg = f"Error fetching past seasons: {e}"
                print(f"✗ {error_msg}")
                results["past_seasons_fetch"] = "FAILED"
                results["errors"].append(error_msg)
                traceback.print_exc()
        else:
            print("\n5. Skipping past seasons test (test_past_seasons=False)")
            
    except Exception as e:
        error_msg = f"General error in test: {e}"
        print(f"✗ {error_msg}")
        results["errors"].append(error_msg)
        traceback.print_exc()
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for step, result in results.items():
        if step != "errors":
            status = "✓" if result == "SUCCESS" else "✗" if result == "FAILED" else "⚠"
            print(f"{status} {step}: {result}")
    
    if results["errors"]:
        print(f"\nErrors encountered: {len(results['errors'])}")
        for i, error in enumerate(results["errors"][:5], 1):  # Show first 5 errors
            print(f"  {i}. {error}")
    
    return results

def test_specific_series(series_id):
    """Test a specific series by ID"""
    return test_single_series_sync(series_id=series_id, test_past_seasons=True)

def test_quick():
    """Quick test with first available series, no past seasons"""
    return test_single_series_sync(series_id=None, test_past_seasons=False)

def test_full():
    """Full test with first available series including past seasons"""
    return test_single_series_sync(series_id=None, test_past_seasons=True)

# Main execution if run directly
if __name__ == "__main__":
    print("Running full test...")
    results = test_full()
    
    if any(status == "FAILED" for status in results.values() if status in ["SUCCESS", "FAILED"]):
        print("\n⚠ Some tests failed. Check the errors above.")
    else:
        print("\n✓ All tests passed!")

# Instructions for manual use
print("""
Available test functions:
- test_quick()                    # Test current seasons only, first series
- test_full()                     # Test current + past seasons, first series  
- test_specific_series(483)       # Test specific series ID with past seasons

Example usage:
    results = test_specific_series(483)
    results = test_full()
""") 