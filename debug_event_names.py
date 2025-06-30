#!/usr/bin/env python
"""
Debug script to check event names and see what's happening during event creation
"""

def debug_event_names(series_id=514, limit=5):
    """Debug event names for a specific series"""
    from simlane.sim.models import Event, Series, Season
    
    print("=" * 60)
    print(f"DEBUGGING EVENT NAMES FOR SERIES {series_id}")
    print("=" * 60)
    
    try:
        # Get the series
        series = Series.objects.get(external_series_id=series_id)
        print(f"Series: {series.name} (ID: {series.id})")
        
        # Get seasons for this series
        seasons = Season.objects.filter(series=series).order_by('-start_date')[:3]
        print(f"Found {seasons.count()} seasons")
        
        for season in seasons:
            print(f"\nSeason: {season.name}")
            print(f"  - Active: {season.active}, Complete: {season.complete}")
            print(f"  - Dates: {season.start_date} to {season.end_date}")
            
            # Get events for this season
            events = Event.objects.filter(season=season).order_by('round_number')[:limit]
            print(f"  - Events: {events.count()}")
            
            for event in events:
                name_status = "✓" if event.name else "✗ EMPTY"
                print(f"    {name_status} Event: '{event.name}' (Round {event.round_number})")
                print(f"      - Track: {event.sim_layout.sim_track.name if event.sim_layout else 'None'}")
                print(f"      - Layout: {event.sim_layout.name if event.sim_layout else 'None'}")
                print(f"      - Description: {event.description}")
                
                # Check entry requirements
                if event.entry_requirements:
                    print(f"      - Entry Reqs: {event.entry_requirements}")
                
    except Series.DoesNotExist:
        print(f"✗ Series {series_id} not found")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()

def test_event_creation():
    """Test creating an event manually to see what happens"""
    from simlane.sim.models import Event, Series, Season, Simulator, SimLayout
    from simlane.sim.models import EventSource, EventStatus
    
    print("\n" + "=" * 60)
    print("TESTING MANUAL EVENT CREATION")
    print("=" * 60)
    
    try:
        # Get a series and season
        series = Series.objects.filter(external_series_id__isnull=False).first()
        if not series:
            print("✗ No series found")
            return
            
        season = Season.objects.filter(series=series).first()
        if not season:
            print("✗ No season found")
            return
            
        simulator = Simulator.objects.get(name="iRacing")
        sim_layout = SimLayout.objects.first()
        
        if not sim_layout:
            print("✗ No sim layout found")
            return
        
        print(f"Creating test event for series: {series.name}")
        
        # Test event data
        test_event_name = "TEST EVENT - Manual Creation"
        
        event_defaults = {
            "series": series,
            "season": season,
            "simulator": simulator,
            "sim_layout": sim_layout,
            "event_source": EventSource.SERIES,
            "status": EventStatus.SCHEDULED,
            "name": test_event_name,  # This should be set!
            "description": "Test event created manually",
            "round_number": 999,
            "entry_requirements": {
                "round_number": 999,
                "track_id": 12345,
                "layout_id": str(sim_layout.id),
            },
        }
        
        lookup_criteria = {
            "series": series,
            "season": season,
            "round_number": 999,
            "sim_layout": sim_layout,
        }
        
        # Create event
        event, created = Event.objects.get_or_create(
            **lookup_criteria,
            defaults=event_defaults,
        )
        
        action = "Created" if created else "Found existing"
        print(f"✓ {action} event:")
        print(f"  - Name: '{event.name}'")
        print(f"  - Description: '{event.description}'")
        print(f"  - Round: {event.round_number}")
        
        if not created:
            # Test updating
            print("\nTesting update...")
            for key, value in event_defaults.items():
                if hasattr(event, key):
                    old_value = getattr(event, key)
                    setattr(event, key, value)
                    print(f"  - {key}: '{old_value}' -> '{value}'")
            
            event.save()
            
            # Refresh from DB
            event.refresh_from_db()
            print(f"\nAfter save and refresh:")
            print(f"  - Name: '{event.name}'")
            print(f"  - Description: '{event.description}'")
        
        # Clean up
        if created:
            event.delete()
            print("\n✓ Cleaned up test event")
            
    except Exception as e:
        print(f"✗ Error in manual test: {e}")
        import traceback
        traceback.print_exc()

def check_event_model():
    """Check the Event model to see if name field exists and is configured correctly"""
    from simlane.sim.models import Event
    
    print("\n" + "=" * 60)
    print("CHECKING EVENT MODEL")
    print("=" * 60)
    
    # Check if name field exists
    name_field = None
    for field in Event._meta.fields:
        if field.name == 'name':
            name_field = field
            break
    
    if name_field:
        print(f"✓ 'name' field found: {name_field}")
        print(f"  - Type: {type(name_field)}")
        print(f"  - Max length: {getattr(name_field, 'max_length', 'N/A')}")
        print(f"  - Null: {name_field.null}")
        print(f"  - Blank: {name_field.blank}")
    else:
        print("✗ 'name' field NOT found in Event model")
        print("Available fields:")
        for field in Event._meta.fields:
            print(f"  - {field.name}")

# Instructions for manual use
print("""
Available debug functions:
- debug_event_names(514)      # Check event names for series 514
- test_event_creation()       # Test manual event creation
- check_event_model()         # Check Event model configuration

Example usage:
    debug_event_names(514)
    test_event_creation()
    check_event_model()
""") 