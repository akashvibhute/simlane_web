import os
import stripe
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from simlane.billing.models import SubscriptionPlan


class Command(BaseCommand):
    help = 'Set up initial subscription plans and sync with Stripe'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be created without actually creating anything',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force update existing plans with new data',
        )
        parser.add_argument(
            '--skip-stripe',
            action='store_true',
            help='Skip Stripe API calls and only create local plans',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.force = options['force']
        self.skip_stripe = options['skip_stripe']

        if self.dry_run:
            self.stdout.write(
                self.style.WARNING('DRY RUN MODE - No changes will be made')
            )

        # Initialize Stripe if not skipping
        if not self.skip_stripe:
            self._initialize_stripe()

        # Define subscription plans
        plans_data = self._get_plans_data()

        # Create or update plans
        for plan_data in plans_data:
            self._create_or_update_plan(plan_data)

        self.stdout.write(
            self.style.SUCCESS('Successfully set up subscription plans!')
        )

    def _initialize_stripe(self):
        """Initialize Stripe with API key from settings"""
        try:
            stripe_secret_key = getattr(settings, 'STRIPE_SECRET_KEY', None)
            if not stripe_secret_key:
                stripe_secret_key = os.environ.get('STRIPE_SECRET_KEY')
            
            if not stripe_secret_key:
                raise CommandError(
                    'STRIPE_SECRET_KEY not found in settings or environment variables. '
                    'Please set it or use --skip-stripe flag.'
                )
            
            stripe.api_key = stripe_secret_key
            
            # Test the connection
            stripe.Account.retrieve()
            self.stdout.write(
                self.style.SUCCESS('Successfully connected to Stripe API')
            )
            
        except stripe.error.AuthenticationError:
            raise CommandError(
                'Invalid Stripe API key. Please check your STRIPE_SECRET_KEY.'
            )
        except Exception as e:
            raise CommandError(f'Error connecting to Stripe: {str(e)}')

    def _get_plans_data(self):
        """Define the subscription plans data"""
        return [
            {
                'name': 'Free',
                'stripe_price_id': os.environ.get('STRIPE_FREE_PRICE_ID', ''),
                'max_members': 5,
                'monthly_price': 0.00,
                'features': {
                    'race_planning': False,
                    'team_management': True,
                    'event_participation': True,
                    'basic_analytics': True,
                    'discord_integration': True,
                    'api_access': False,
                    'priority_support': False,
                },
                'description': 'Perfect for small clubs getting started with SimLane',
            },
            {
                'name': 'Basic',
                'stripe_price_id': os.environ.get('STRIPE_BASIC_PRICE_ID', ''),
                'max_members': 25,
                'monthly_price': 9.99,
                'features': {
                    'race_planning': True,
                    'team_management': True,
                    'event_participation': True,
                    'basic_analytics': True,
                    'advanced_analytics': True,
                    'discord_integration': True,
                    'api_access': True,
                    'priority_support': False,
                    'stint_planning': True,
                    'strategy_management': True,
                },
                'description': 'Ideal for growing clubs with race planning needs',
            },
            {
                'name': 'Pro',
                'stripe_price_id': os.environ.get('STRIPE_PRO_PRICE_ID', ''),
                'max_members': -1,  # Unlimited
                'monthly_price': 24.99,
                'features': {
                    'race_planning': True,
                    'team_management': True,
                    'event_participation': True,
                    'basic_analytics': True,
                    'advanced_analytics': True,
                    'premium_analytics': True,
                    'discord_integration': True,
                    'api_access': True,
                    'priority_support': True,
                    'stint_planning': True,
                    'strategy_management': True,
                    'advanced_strategy_tools': True,
                    'custom_integrations': True,
                    'white_label_options': True,
                },
                'description': 'Complete solution for professional racing organizations',
            },
        ]

    def _create_or_update_plan(self, plan_data):
        """Create or update a subscription plan"""
        plan_name = plan_data['name']
        
        if self.dry_run:
            self.stdout.write(f'Would create/update plan: {plan_name}')
            self._display_plan_details(plan_data)
            return

        try:
            # Check if plan already exists
            existing_plan = SubscriptionPlan.objects.filter(name=plan_name).first()
            
            if existing_plan and not self.force:
                self.stdout.write(
                    self.style.WARNING(
                        f'Plan "{plan_name}" already exists. Use --force to update.'
                    )
                )
                return

            # Validate Stripe price ID if not skipping Stripe
            if not self.skip_stripe and plan_data['stripe_price_id']:
                self._validate_stripe_price(plan_data['stripe_price_id'])

            # Create or update the plan
            plan, created = SubscriptionPlan.objects.update_or_create(
                name=plan_name,
                defaults={
                    'stripe_price_id': plan_data['stripe_price_id'],
                    'max_members': plan_data['max_members'],
                    'monthly_price': plan_data['monthly_price'],
                    'features_json': plan_data['features'],
                    'description': plan_data.get('description', ''),
                    'is_active': True,
                }
            )

            action = 'Created' if created else 'Updated'
            self.stdout.write(
                self.style.SUCCESS(f'{action} plan: {plan_name}')
            )
            self._display_plan_details(plan_data)

        except Exception as e:
            self.stderr.write(
                self.style.ERROR(f'Error creating plan "{plan_name}": {str(e)}')
            )

    def _validate_stripe_price(self, price_id):
        """Validate that the Stripe price ID exists and is active"""
        if not price_id:
            return  # Skip validation for empty price IDs
            
        try:
            price = stripe.Price.retrieve(price_id)
            
            if not price.active:
                raise CommandError(f'Stripe price {price_id} is not active')
                
            self.stdout.write(f'Validated Stripe price: {price_id}')
            
        except stripe.error.InvalidRequestError:
            raise CommandError(f'Stripe price {price_id} not found')
        except Exception as e:
            raise CommandError(f'Error validating Stripe price {price_id}: {str(e)}')

    def _display_plan_details(self, plan_data):
        """Display plan details in a formatted way"""
        self.stdout.write(f'  - Max Members: {plan_data["max_members"] if plan_data["max_members"] != -1 else "Unlimited"}')
        self.stdout.write(f'  - Monthly Price: ${plan_data["monthly_price"]:.2f}')
        self.stdout.write(f'  - Stripe Price ID: {plan_data["stripe_price_id"] or "Not set"}')
        
        # Display key features
        features = plan_data['features']
        key_features = [k for k, v in features.items() if v and k in ['race_planning', 'team_management', 'api_access', 'priority_support']]
        if key_features:
            self.stdout.write(f'  - Key Features: {", ".join(key_features)}')
        
        self.stdout.write('')  # Empty line for readability