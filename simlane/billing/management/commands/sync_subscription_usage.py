from django.core.management.base import BaseCommand
from django.db import transaction
from simlane.billing.models import ClubSubscription
from simlane.teams.models import Club


class Command(BaseCommand):
    help = 'Sync subscription usage statistics for all clubs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--club-id',
            type=str,
            help='Sync usage for specific club ID only',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be updated without making changes',
        )

    def handle(self, *args, **options):
        club_id = options.get('club_id')
        dry_run = options.get('dry_run')

        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        # Get clubs to sync
        if club_id:
            try:
                clubs = Club.objects.filter(id=club_id)
                if not clubs.exists():
                    self.stdout.write(
                        self.style.ERROR(f"Club with ID {club_id} not found")
                    )
                    return
            except ValueError:
                self.stdout.write(
                    self.style.ERROR(f"Invalid club ID: {club_id}")
                )
                return
        else:
            clubs = Club.objects.all()

        updated_count = 0
        error_count = 0

        for club in clubs:
            try:
                # Get or create subscription
                subscription, created = ClubSubscription.objects.get_or_create(
                    club=club,
                    defaults={
                        'plan': self._get_default_plan(),
                        'status': 'active',
                    }
                )

                if created:
                    self.stdout.write(
                        f"Created subscription for club: {club.name}"
                    )

                # Calculate current usage
                old_seats_used = subscription.seats_used
                new_seats_used = subscription.calculate_seats_used()

                if old_seats_used != new_seats_used:
                    if not dry_run:
                        subscription.update_seats_used()
                    
                    self.stdout.write(
                        f"Club {club.name}: {old_seats_used} → {new_seats_used} members"
                    )
                    updated_count += 1
                else:
                    self.stdout.write(
                        f"Club {club.name}: {new_seats_used} members (no change)"
                    )

            except Exception as e:
                error_count += 1
                self.stdout.write(
                    self.style.ERROR(
                        f"Error syncing club {club.name}: {str(e)}"
                    )
                )

        # Summary
        self.stdout.write(
            self.style.SUCCESS(
                f"\nSummary:"
                f"\n- Clubs processed: {clubs.count()}"
                f"\n- Subscriptions updated: {updated_count}"
                f"\n- Errors: {error_count}"
            )
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "This was a dry run. Use without --dry-run to apply changes."
                )
            )

    def _get_default_plan(self):
        """Get the default subscription plan"""
        from simlane.billing.models import SubscriptionPlan
        
        try:
            return SubscriptionPlan.objects.get(is_default=True, is_active=True)
        except SubscriptionPlan.DoesNotExist:
            # Fallback to Free plan
            return SubscriptionPlan.objects.filter(
                name__iexact='free', 
                is_active=True
            ).first() 