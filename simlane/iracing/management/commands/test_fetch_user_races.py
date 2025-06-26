from django.core.management.base import BaseCommand
from django.utils import timezone

from simlane.iracing.services import iracing_service
from simlane.iracing.auto_create import process_member_recent_races


class Command(BaseCommand):
    help = "Test fetching recent races for the logged-in iRacing user and creating all relevant models"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=10,
            help="Number of recent races to process (default: 10)",
        )

    def handle(self, *args, **options):
        self.stdout.write("=" * 80)
        self.stdout.write(self.style.SUCCESS("Testing iRacing Recent Races Fetch"))
        self.stdout.write("=" * 80)
        
        # Check if iRacing service is available
        if not iracing_service.is_available():
            self.stdout.write(self.style.ERROR("iRacing API service is not available!"))
            self.stdout.write("Please ensure IRACING_EMAIL and IRACING_PASSWORD are set in environment")
            return
        
        try:
            # First, get the logged-in user's member info
            self.stdout.write("\n1. Fetching member info...")
            member_info = iracing_service.get_member_info()
            
            if not member_info:
                self.stdout.write(self.style.ERROR("Failed to fetch member info"))
                return
            
            cust_id = member_info.get('cust_id')
            display_name = member_info.get('display_name', 'Unknown')
            
            if not cust_id:
                self.stdout.write(self.style.ERROR("No customer ID found in member info"))
                return
                
            self.stdout.write(self.style.SUCCESS(f"✓ Logged in as: {display_name} (Customer ID: {cust_id})"))
            
            # Now fetch recent races using the auto_create module
            self.stdout.write(f"\n2. Processing recent races (limit: {options['limit']})...")
            self.stdout.write("This will create: Series → Season → RaceWeek → Event → EventInstance")
            self.stdout.write("-" * 60)
            
            # Process recent races
            result = process_member_recent_races(cust_id)
            
            if 'error' in result:
                self.stdout.write(self.style.ERROR(f"Error: {result['error']}"))
                return
            
            processed_races = result.get('processed_races', 0)
            created_counts = result.get('created_counts', {})
            errors = result.get('errors', [])
            
            if processed_races == 0:
                self.stdout.write(self.style.ERROR("No races were processed. See errors below."))
            elif errors:
                self.stdout.write(self.style.WARNING(f"Processed {processed_races} races, but encountered {len(errors)} errors."))
            else:
                self.stdout.write(self.style.SUCCESS(f"\n✓ Processed {processed_races} races"))
            
            # Show created counts
            self.stdout.write("\n3. Created Records:")
            for model_type, count in created_counts.items():
                if count > 0:
                    self.stdout.write(f"   • {model_type}: {self.style.SUCCESS(str(count))}")
            
            # Show any errors
            if errors:
                self.stdout.write(self.style.WARNING(f"\n4. Errors encountered ({len(errors)}):"))
                for i, error in enumerate(errors[:1]):  # Show first 1 errors
                    self.stdout.write(f"   {i+1}. {"error"}")
                if len(errors) > 1:
                    self.stdout.write(f"   ... and {len(errors) - 1} more errors")
            
            # Fetch and display some of the created data
            self.stdout.write("\n5. Sample of Created Data:")
            
            # Show recent EventInstances
            from simlane.sim.models import EventInstance, Series, Season, RaceWeek
            
            recent_instances = EventInstance.objects.filter(
                external_subsession_id__isnull=False
            ).select_related('event', 'event__series', 'event__sim_layout').order_by('-start_time')[:5]
            
            if recent_instances:
                self.stdout.write("\n   Recent Event Instances:")
                for instance in recent_instances:
                    self.stdout.write(
                        f"   • {instance.event.name}\n"
                        f"     Start: {instance.start_time.strftime('%Y-%m-%d %H:%M')} | "
                        f"     Subsession: {instance.external_subsession_id}"
                    )
            
            # Show series/seasons created
            recent_series = Series.objects.filter(
                external_series_id__isnull=False
            ).order_by('-created_at')[:3]
            
            if recent_series:
                self.stdout.write("\n   Recent Series:")
                for series in recent_series:
                    season_count = series.seasons.count()
                    self.stdout.write(
                        f"   • {series.name} (ID: {series.external_series_id})\n"
                        f"     Seasons: {season_count} | Category: {series.category or 'N/A'}"
                    )
            
            # Show race weeks with weather
            race_weeks_with_weather = RaceWeek.objects.filter(
                weather_forecast_url__isnull=False
            ).select_related('season', 'season__series', 'sim_layout').order_by('-created_at')[:3]
            
            if race_weeks_with_weather:
                self.stdout.write("\n   Race Weeks with Weather:")
                for race_week in race_weeks_with_weather:
                    self.stdout.write(
                        f"   • {race_week.season.series.name} - Week {race_week.week_number}\n"
                        f"     Track: {race_week.sim_layout} | "
                        f"     Weather: {'Cached' if race_week.weather_forecast_data else 'URL Available'}"
                    )
            
            # Final success/failure message
            if processed_races > 0 and not errors:
                self.stdout.write(self.style.SUCCESS("Test completed successfully!"))
            else:
                self.stdout.write(self.style.ERROR("Test did not complete successfully."))
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\nUnexpected error: {str(e)}"))
            import traceback
            self.stdout.write(traceback.format_exc()) 