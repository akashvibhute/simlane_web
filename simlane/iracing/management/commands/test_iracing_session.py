from django.core.management.base import BaseCommand
from simlane.iracing.iracing_api_client import IRacingAPIClient
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Test iRacing session caching by fetching current member info.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Initializing IRacingAPIClient from system cache...'))
        client = IRacingAPIClient.from_system_cache()
        if not client:
            self.stdout.write(self.style.ERROR('Failed to initialize IRacingAPIClient.'))
            return
        try:
            info = client.member_info()
            self.stdout.write(self.style.SUCCESS('Successfully fetched current member info:'))
            self.stdout.write(str(info))
        except Exception as e:
            logger.exception('Failed to fetch member info from iRacing API')
            self.stdout.write(self.style.ERROR(f'Error: {e}')) 