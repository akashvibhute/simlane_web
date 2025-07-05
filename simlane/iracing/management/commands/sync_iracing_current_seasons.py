from django.core.management.base import BaseCommand
from simlane.iracing.tasks import sync_current_seasons_task

class Command(BaseCommand):
    help = "Queue Celery task to sync CURRENT & FUTURE seasons for all iRacing series."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Bypass API cache when fetching data",
        )

    def handle(self, *args, **options):
        refresh = options.get("refresh", False)
        task = sync_current_seasons_task.delay(refresh=refresh) # type: ignore[call-arg]
        self.stdout.write(self.style.SUCCESS(f"Queued sync_current_seasons_task (id={task.id}) refresh={refresh}")) 