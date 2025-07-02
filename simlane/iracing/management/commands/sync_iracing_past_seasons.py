from django.core.management.base import BaseCommand
from simlane.iracing.tasks import queue_all_past_seasons_sync_task

class Command(BaseCommand):
    help = "Queue Celery tasks to sync PAST seasons for every iRacing series in the DB."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help="Bypass API cache when fetching data",
        )

    def handle(self, *args, **options):
        refresh = options.get("refresh", False)
        task = queue_all_past_seasons_sync_task.delay(refresh=refresh)
        self.stdout.write(self.style.SUCCESS(f"Queued queue_all_past_seasons_sync_task (id={task.id}) refresh={refresh}")) 