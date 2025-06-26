import json
from django.core.management.base import BaseCommand
from simlane.iracing.services import iracing_service


class Command(BaseCommand):
    help = 'Fetch and print iRacing results data for a specific subsession or session ID'

    def add_arguments(self, parser):
        parser.add_argument(
            '--subsession-id',
            type=int,
            help='iRacing subsession ID to fetch results for',
        )
        parser.add_argument(
            '--session-id',
            type=int,
            help='iRacing session ID to fetch results for',
        )
        parser.add_argument(
            '--pretty',
            action='store_true',
            help='Pretty print the JSON response',
        )

    def handle(self, *args, **options):
        subsession_id = options.get('subsession_id')
        session_id = options.get('session_id')
        pretty = options.get('pretty')

        if not subsession_id and not session_id:
            self.stdout.write(self.style.ERROR("Please provide either --subsession-id or --session-id"))
            return

        try:
            if subsession_id:
                self.stdout.write(f"Fetching results for subsession ID: {subsession_id}")
                results = iracing_service.results_get(
                    subsession_id=subsession_id,
                    include_licenses=True
                )
            else:
                self.stdout.write(f"Fetching results for session ID: {session_id}")
                # Note: We might need to implement session_get method
                self.stdout.write(self.style.ERROR("Session ID fetching not implemented yet"))
                return

            # Print the results
            self.stdout.write(self.style.SUCCESS("Results fetched successfully!"))
            self.stdout.write("=" * 80)
            
            if pretty:
                # Pretty print the JSON
                print(json.dumps(results, indent=2, default=str))
            else:
                # Print key structure info
                self.stdout.write(f"Response type: {type(results)}")
                self.stdout.write(f"Top-level keys: {list(results.keys()) if isinstance(results, dict) else 'Not a dict'}")
                
                if isinstance(results, dict):
                    for key, value in results.items():
                        if isinstance(value, list):
                            self.stdout.write(f"{key}: List with {len(value)} items")
                            if value and len(value) > 0:
                                self.stdout.write(f"  First item keys: {list(value[0].keys()) if isinstance(value[0], dict) else 'Not a dict'}")
                        elif isinstance(value, dict):
                            self.stdout.write(f"{key}: Dict with keys: {list(value.keys())}")
                        else:
                            self.stdout.write(f"{key}: {type(value).__name__} = {value}")
                
                # Also save to file for detailed inspection
                filename = f"results_{subsession_id or session_id}.json"
                with open(filename, 'w') as f:
                    json.dump(results, f, indent=2, default=str)
                self.stdout.write(f"Full response saved to: {filename}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Failed to fetch results: {str(e)}"))
            raise 