from django.core.management.base import BaseCommand
from simlane.iracing.tasks import check_completed_events_task


class Command(BaseCommand):
    help = 'Test the completed events check task manually'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be processed without actually queuing tasks',
        )

    def handle(self, *args, **options):
        self.stdout.write("Testing completed events check task...")
        
        if options['dry_run']:
            self.stdout.write("DRY RUN MODE - No tasks will be queued")
        
        try:
            # Run the task
            result = check_completed_events_task()
            
            # Display results
            self.stdout.write(self.style.SUCCESS("Task completed successfully!"))
            self.stdout.write(f"Completed events found: {result.get('completed_events_found', 0)}")
            self.stdout.write(f"Queued for processing: {result.get('queued_for_processing', 0)}")
            
            if result.get('errors'):
                self.stdout.write(self.style.WARNING("Errors encountered:"))
                for error in result['errors']:
                    self.stdout.write(f"  - {error}")
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Task failed: {str(e)}"))
            raise 