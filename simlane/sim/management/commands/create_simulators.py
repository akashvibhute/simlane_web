"""
Management command to create initial simulator data for testing.
"""

from django.core.management.base import BaseCommand

from simlane.sim.models import Simulator


class Command(BaseCommand):
    help = "Creates initial simulator data for testing sim profiles"

    def handle(self, *args, **options):
        simulators_data = [
            {
                "name": "iRacing",
                "version": "2024.1",
                "website": "https://www.iracing.com",
                "description": "The premier online racing simulation service for PC.",
                "logo_url": "",
            },
            {
                "name": "Assetto Corsa Competizione",
                "version": "1.10",
                "website": "https://www.assettocorsa.it/competizione/",
                "description": "Official GT World Challenge game with stunning graphics and physics.",
                "logo_url": "",
            },
            {
                "name": "rFactor 2",
                "version": "1.1121",
                "website": "https://www.studio-397.com",
                "description": "Advanced racing simulation with realistic physics and AI.",
                "logo_url": "",
            },
            {
                "name": "Automobilista 2",
                "version": "1.5.5",
                "website": "https://www.game-automobilista2.com",
                "description": "Brazilian racing simulation with diverse content.",
                "logo_url": "",
            },
            {
                "name": "F1 24",
                "version": "1.0",
                "website": "https://www.ea.com/games/f1",
                "description": "Official Formula 1 racing game.",
                "logo_url": "",
            },
            {
                "name": "Gran Turismo 7",
                "version": "1.0",
                "website": "https://www.gran-turismo.com",
                "description": "PlayStation exclusive racing simulation.",
                "logo_url": "",
            },
            {
                "name": "Forza Motorsport",
                "version": "2023",
                "website": "https://forza.net",
                "description": "Xbox and PC racing simulation.",
                "logo_url": "",
            },
        ]

        created_count = 0
        updated_count = 0

        for sim_data in simulators_data:
            simulator, created = Simulator.objects.get_or_create(
                name=sim_data["name"],
                version=sim_data["version"],
                defaults={
                    "website": sim_data["website"],
                    "description": sim_data["description"],
                    "logo_url": sim_data["logo_url"],
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created simulator: {simulator.name} {simulator.version}",
                    ),
                )
            else:
                updated_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"Simulator already exists: {simulator.name} {simulator.version}",
                    ),
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nCompleted! Created {created_count} new simulators, {updated_count} already existed.",
            ),
        )
