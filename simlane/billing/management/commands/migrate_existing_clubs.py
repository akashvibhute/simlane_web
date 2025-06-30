from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.conf import settings
import logging

from simlane.teams.models import Club, ClubMember
from simlane.billing.models import SubscriptionPlan, ClubSubscription

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migrate existing clubs to the billing system with Free plan assignments'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be done without making changes',
        )
        parser.add_argument(
            '--auto-upgrade',
            action='store_true',
            help='Automatically upgrade clubs that exceed Free plan limits to Basic plan',
        )
        parser.add_argument(
            '--report-only',
            action='store_true',
            help='Generate report of clubs and their member counts without creating subscriptions',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force migration even if clubs already have subscriptions',
        )
        parser.add_argument(
            '--club-id',
            type=str,
            help='Migrate specific club by ID (UUID)',
        )
        parser.add_argument(
            '--output-file',
            type=str,
            help='Write detailed report to specified file',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.auto_upgrade = options['auto_upgrade']
        self.report_only = options['report_only']
        self.force = options['force']
        self.club_id = options['club_id']
        self.output_file = options['output_file']

        # Validate options
        if self.auto_upgrade and self.report_only:
            raise CommandError("Cannot use --auto-upgrade with --report-only")

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN MODE - No changes will be made")
            )

        try:
            # Get subscription plans
            self.free_plan = self._get_free_plan()
            self.basic_plan = self._get_basic_plan() if self.auto_upgrade else None

            # Get clubs to migrate
            clubs = self._get_clubs_to_migrate()

            if not clubs.exists():
                self.stdout.write(
                    self.style.SUCCESS("No clubs found to migrate")
                )
                return

            # Analyze clubs
            club_analysis = self._analyze_clubs(clubs)

            # Generate report
            self._generate_report(club_analysis)

            if not self.report_only:
                # Perform migration
                self._migrate_clubs(club_analysis)

            self.stdout.write(
                self.style.SUCCESS(
                    f"Migration completed successfully. Processed {len(club_analysis)} clubs."
                )
            )

        except Exception as e:
            logger.exception("Error during club migration")
            raise CommandError(f"Migration failed: {str(e)}")

    def _get_free_plan(self):
        """Get the Free subscription plan"""
        try:
            return SubscriptionPlan.objects.get(
                name__iexact='free',
                is_active=True
            )
        except SubscriptionPlan.DoesNotExist:
            raise CommandError(
                "Free subscription plan not found. Please run 'setup_subscription_plans' first."
            )

    def _get_basic_plan(self):
        """Get the Basic subscription plan"""
        try:
            return SubscriptionPlan.objects.get(
                name__iexact='basic',
                is_active=True
            )
        except SubscriptionPlan.DoesNotExist:
            if self.auto_upgrade:
                raise CommandError(
                    "Basic subscription plan not found. Cannot auto-upgrade clubs."
                )
            return None

    def _get_clubs_to_migrate(self):
        """Get clubs that need migration"""
        queryset = Club.objects.filter(is_active=True)

        if self.club_id:
            queryset = queryset.filter(id=self.club_id)

        if not self.force:
            # Exclude clubs that already have subscriptions
            existing_subscription_club_ids = ClubSubscription.objects.values_list(
                'club_id', flat=True
            )
            queryset = queryset.exclude(id__in=existing_subscription_club_ids)

        return queryset.prefetch_related('members')

    def _analyze_clubs(self, clubs):
        """Analyze clubs and their member counts"""
        analysis = []

        for club in clubs:
            member_count = club.members.filter(
                user__is_active=True
            ).count()

            # Check if club already has subscription
            existing_subscription = None
            if hasattr(club, 'subscription'):
                try:
                    existing_subscription = club.subscription
                except ClubSubscription.DoesNotExist:
                    pass

            exceeds_free_limit = member_count > self.free_plan.max_members
            recommended_plan = self.basic_plan if exceeds_free_limit and self.basic_plan else self.free_plan

            club_data = {
                'club': club,
                'member_count': member_count,
                'exceeds_free_limit': exceeds_free_limit,
                'existing_subscription': existing_subscription,
                'recommended_plan': recommended_plan,
                'action': self._determine_action(
                    club, member_count, exceeds_free_limit, existing_subscription
                ),
            }

            analysis.append(club_data)

        return analysis

    def _determine_action(self, club, member_count, exceeds_free_limit, existing_subscription):
        """Determine what action to take for a club"""
        if existing_subscription and not self.force:
            return 'skip_existing'

        if self.report_only:
            return 'report_only'

        if exceeds_free_limit:
            if self.auto_upgrade:
                return 'upgrade_to_basic'
            else:
                return 'assign_free_flagged'
        else:
            return 'assign_free'

    def _generate_report(self, club_analysis):
        """Generate and display migration report"""
        total_clubs = len(club_analysis)
        clubs_exceeding_limit = sum(1 for c in club_analysis if c['exceeds_free_limit'])
        clubs_with_subscriptions = sum(1 for c in club_analysis if c['existing_subscription'])

        # Summary statistics
        self.stdout.write("\n" + "="*60)
        self.stdout.write(self.style.HTTP_INFO("CLUB MIGRATION ANALYSIS REPORT"))
        self.stdout.write("="*60)
        self.stdout.write(f"Total clubs analyzed: {total_clubs}")
        self.stdout.write(f"Clubs exceeding Free plan limit ({self.free_plan.max_members} members): {clubs_exceeding_limit}")
        self.stdout.write(f"Clubs with existing subscriptions: {clubs_with_subscriptions}")

        # Action breakdown
        action_counts = {}
        for club_data in club_analysis:
            action = club_data['action']
            action_counts[action] = action_counts.get(action, 0) + 1

        self.stdout.write("\nPlanned Actions:")
        for action, count in action_counts.items():
            action_display = {
                'assign_free': 'Assign to Free plan',
                'assign_free_flagged': 'Assign to Free plan (FLAGGED - exceeds limit)',
                'upgrade_to_basic': 'Upgrade to Basic plan',
                'skip_existing': 'Skip (already has subscription)',
                'report_only': 'Report only (no action)',
            }.get(action, action)
            self.stdout.write(f"  {action_display}: {count}")

        # Detailed club list
        self.stdout.write("\n" + "-"*60)
        self.stdout.write("DETAILED CLUB ANALYSIS")
        self.stdout.write("-"*60)

        report_lines = []
        for club_data in self._sort_clubs_for_report(club_analysis):
            club = club_data['club']
            member_count = club_data['member_count']
            action = club_data['action']
            recommended_plan = club_data['recommended_plan']

            status_indicator = "⚠️ " if club_data['exceeds_free_limit'] else "✅ "
            existing_sub = " (HAS SUBSCRIPTION)" if club_data['existing_subscription'] else ""

            line = f"{status_indicator}{club.name[:40]:<40} | {member_count:>3} members | {recommended_plan.name:<8} | {action}{existing_sub}"
            
            if club_data['exceeds_free_limit']:
                self.stdout.write(self.style.WARNING(line))
            elif club_data['existing_subscription']:
                self.stdout.write(self.style.HTTP_INFO(line))
            else:
                self.stdout.write(line)

            report_lines.append({
                'club_name': club.name,
                'club_id': str(club.id),
                'member_count': member_count,
                'exceeds_limit': club_data['exceeds_free_limit'],
                'recommended_plan': recommended_plan.name,
                'action': action,
                'has_existing_subscription': bool(club_data['existing_subscription']),
            })

        # Write detailed report to file if requested
        if self.output_file:
            self._write_report_file(report_lines, club_analysis)

        # Show warnings for clubs exceeding limits
        if clubs_exceeding_limit > 0 and not self.auto_upgrade:
            self.stdout.write("\n" + self.style.WARNING("⚠️  WARNING: Some clubs exceed the Free plan member limit!"))
            self.stdout.write(self.style.WARNING(f"   Free plan allows {self.free_plan.max_members} members maximum."))
            self.stdout.write(self.style.WARNING("   Consider using --auto-upgrade to assign Basic plans automatically."))

    def _sort_clubs_for_report(self, club_analysis):
        """Sort clubs for report display - flagged clubs first, then by member count"""
        return sorted(
            club_analysis,
            key=lambda x: (
                not x['exceeds_free_limit'],  # Flagged clubs first
                -x['member_count'],  # Then by member count descending
                x['club'].name.lower()  # Then alphabetically
            )
        )

    def _write_report_file(self, report_lines, club_analysis):
        """Write detailed report to file"""
        try:
            import json
            from datetime import datetime

            report_data = {
                'generated_at': datetime.now().isoformat(),
                'migration_settings': {
                    'dry_run': self.dry_run,
                    'auto_upgrade': self.auto_upgrade,
                    'report_only': self.report_only,
                    'force': self.force,
                },
                'summary': {
                    'total_clubs': len(club_analysis),
                    'clubs_exceeding_limit': sum(1 for c in club_analysis if c['exceeds_free_limit']),
                    'free_plan_limit': self.free_plan.max_members,
                },
                'clubs': report_lines,
            }

            with open(self.output_file, 'w') as f:
                json.dump(report_data, f, indent=2)

            self.stdout.write(f"\nDetailed report written to: {self.output_file}")

        except Exception as e:
            self.stdout.write(
                self.style.WARNING(f"Failed to write report file: {str(e)}")
            )

    def _migrate_clubs(self, club_analysis):
        """Perform the actual migration"""
        if self.dry_run:
            self.stdout.write("\n" + self.style.WARNING("DRY RUN - No actual changes made"))
            return

        self.stdout.write("\n" + "-"*60)
        self.stdout.write("PERFORMING MIGRATION")
        self.stdout.write("-"*60)

        success_count = 0
        error_count = 0

        for club_data in club_analysis:
            club = club_data['club']
            action = club_data['action']

            if action in ['skip_existing', 'report_only']:
                continue

            try:
                with transaction.atomic():
                    subscription = self._create_club_subscription(club_data)
                    if subscription:
                        success_count += 1
                        plan_name = subscription.plan.name
                        self.stdout.write(
                            f"✅ {club.name}: Assigned to {plan_name} plan"
                        )
                    else:
                        self.stdout.write(
                            f"⏭️  {club.name}: Skipped"
                        )

            except Exception as e:
                error_count += 1
                logger.exception(f"Failed to migrate club {club.name}")
                self.stdout.write(
                    self.style.ERROR(f"❌ {club.name}: Failed - {str(e)}")
                )

        self.stdout.write(f"\nMigration Results:")
        self.stdout.write(f"  Successfully migrated: {success_count}")
        self.stdout.write(f"  Errors: {error_count}")

    def _create_club_subscription(self, club_data):
        """Create subscription for a club"""
        club = club_data['club']
        action = club_data['action']
        
        if action in ['skip_existing', 'report_only']:
            return None

        # Determine plan
        if action == 'upgrade_to_basic':
            plan = self.basic_plan
        else:  # assign_free or assign_free_flagged
            plan = self.free_plan

        # Check if subscription already exists
        existing_subscription = ClubSubscription.objects.filter(club=club).first()
        if existing_subscription and not self.force:
            return None

        # Create or update subscription
        subscription, created = ClubSubscription.objects.update_or_create(
            club=club,
            defaults={
                'plan': plan,
                'status': 'active',
                'current_period_start': timezone.now(),
                'current_period_end': timezone.now() + timezone.timedelta(days=365),  # 1 year for free plans
                'seats_used': club_data['member_count'],
                'stripe_customer_id': '',  # Empty for free plans
                'stripe_subscription_id': '',  # Empty for free plans
            }
        )

        return subscription

    def _validate_migration_state(self):
        """Validate that the system is ready for migration"""
        # Check that subscription plans exist
        if not SubscriptionPlan.objects.filter(is_active=True).exists():
            raise CommandError(
                "No active subscription plans found. Please run 'setup_subscription_plans' first."
            )

        # Check for required plans
        required_plans = ['free']
        if self.auto_upgrade:
            required_plans.append('basic')

        for plan_name in required_plans:
            if not SubscriptionPlan.objects.filter(
                name__iexact=plan_name,
                is_active=True
            ).exists():
                raise CommandError(
                    f"Required subscription plan '{plan_name}' not found."
                )