from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'simlane.billing'
    verbose_name = 'Billing'

    def ready(self):
        """
        Initialize app-specific configuration for Stripe integration.
        Import signals and perform any startup tasks.
        """
        try:
            import simlane.billing.signals  # noqa F401
        except ImportError:
            pass
        
        # Initialize Stripe configuration
        self._configure_stripe()

    def _configure_stripe(self):
        """Configure Stripe SDK with project settings."""
        try:
            import stripe
            from django.conf import settings
            
            # Set Stripe API key from settings
            if hasattr(settings, 'STRIPE_SECRET_KEY'):
                stripe.api_key = settings.STRIPE_SECRET_KEY
                
            # Set API version for consistency
            stripe.api_version = '2023-10-16'
            
        except ImportError:
            # Stripe not installed yet, will be configured when available
            pass
        except Exception:
            # Handle any configuration errors gracefully
            pass