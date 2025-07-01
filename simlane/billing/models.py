import uuid
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from simlane.teams.models import Club
from simlane.users.models import User


class SubscriptionPlan(models.Model):
    """
    Defines subscription tiers with member limits and feature access
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Plan identification
    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Plan name (e.g., 'Free', 'Basic', 'Pro')"
    )
    slug = models.SlugField(
        max_length=100,
        unique=True,
        help_text="URL-friendly plan identifier"
    )
    
    # Stripe integration
    stripe_price_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Stripe Price ID for this plan"
    )
    
    # Plan limits and pricing
    max_members = models.IntegerField(
        help_text="Maximum number of club members allowed (-1 for unlimited)"
    )
    monthly_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Monthly price in USD"
    )
    
    # Feature configuration
    features_json = models.JSONField(
        default=dict,
        help_text="JSON object defining available features for this plan"
    )
    
    # Plan status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this plan is available for new subscriptions"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Whether this is the default plan for new clubs"
    )
    
    # Display information
    description = models.TextField(
        blank=True,
        help_text="Plan description for display purposes"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Order for displaying plans (lower numbers first)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['display_order', 'monthly_price']
        indexes = [
            models.Index(fields=['is_active', 'display_order']),
            models.Index(fields=['stripe_price_id']),
        ]
    
    def __str__(self):
        return f"{self.name} (${self.monthly_price}/month)"
    
    def clean(self):
        """Validate plan configuration"""
        if self.is_default:
            # Ensure only one default plan exists
            existing_default = SubscriptionPlan.objects.filter(
                is_default=True
            ).exclude(pk=self.pk)
            if existing_default.exists():
                raise ValidationError("Only one plan can be set as default")
        
        if self.max_members < -1 or self.max_members == 0:
            raise ValidationError("max_members must be positive or -1 for unlimited")
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    @property
    def is_unlimited_members(self):
        """Check if plan allows unlimited members"""
        return self.max_members == -1
    
    @property
    def is_free_plan(self):
        """Check if this is a free plan"""
        return self.monthly_price == 0
    
    def has_feature(self, feature_name):
        """Check if plan includes a specific feature"""
        return self.features_json.get(feature_name, False)
    
    def get_feature_value(self, feature_name, default=None):
        """Get feature value or default"""
        return self.features_json.get(feature_name, default)
    
    def get_features(self):
        """Get list of enabled features for this plan"""
        return [feature for feature, enabled in self.features_json.items() if enabled]
    
    @classmethod
    def get_default_plan(cls):
        """Get the default plan for new clubs"""
        try:
            return cls.objects.get(is_default=True, is_active=True)
        except cls.DoesNotExist:
            # Fallback to cheapest active plan
            return cls.objects.filter(is_active=True).order_by('monthly_price').first()


class ClubSubscription(models.Model):
    """
    Tracks a club's subscription to a plan with Stripe integration
    """
    
    class SubscriptionStatus(models.TextChoices):
        INCOMPLETE = 'incomplete', 'Incomplete'
        INCOMPLETE_EXPIRED = 'incomplete_expired', 'Incomplete Expired'
        TRIALING = 'trialing', 'Trialing'
        ACTIVE = 'active', 'Active'
        PAST_DUE = 'past_due', 'Past Due'
        CANCELED = 'canceled', 'Canceled'
        UNPAID = 'unpaid', 'Unpaid'
        PAUSED = 'paused', 'Paused'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Core relationships
    club = models.OneToOneField(
        Club,
        on_delete=models.CASCADE,
        related_name='subscription'
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.PROTECT,
        related_name='subscriptions'
    )
    
    # Stripe integration
    stripe_customer_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Stripe Customer ID"
    )
    stripe_subscription_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Stripe Subscription ID"
    )
    
    # Subscription status
    status = models.CharField(
        max_length=20,
        choices=SubscriptionStatus.choices,
        default=SubscriptionStatus.ACTIVE
    )
    
    # Billing periods
    current_period_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Start of current billing period"
    )
    current_period_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End of current billing period"
    )
    
    # Usage tracking
    seats_used = models.IntegerField(
        default=0,
        help_text="Current number of club members"
    )
    
    # Trial information
    trial_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Trial period start date"
    )
    trial_end = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Trial period end date"
    )
    
    # Cancellation tracking
    cancel_at_period_end = models.BooleanField(
        default=False,
        help_text="Whether subscription will cancel at period end"
    )
    canceled_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When subscription was canceled"
    )
    
    # Metadata
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional subscription metadata"
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['club']),
            models.Index(fields=['status']),
            models.Index(fields=['stripe_customer_id']),
            models.Index(fields=['stripe_subscription_id']),
            models.Index(fields=['current_period_end']),
        ]
    
    def __str__(self):
        return f"{self.club.name} - {self.plan.name} ({self.status})"
    
    @property
    def is_active(self):
        """Check if subscription is in an active state"""
        return self.status in [
            self.SubscriptionStatus.ACTIVE,
            self.SubscriptionStatus.TRIALING
        ]
    
    @property
    def is_past_due(self):
        """Check if subscription is past due"""
        return self.status == self.SubscriptionStatus.PAST_DUE
    
    @property
    def is_canceled(self):
        """Check if subscription is canceled"""
        return self.status == self.SubscriptionStatus.CANCELED
    
    @property
    def is_on_trial(self):
        """Check if subscription is in trial period"""
        if not self.trial_end:
            return False
        return timezone.now() < self.trial_end
    
    @property
    def days_until_renewal(self):
        """Get days until next renewal"""
        if not self.current_period_end:
            return None
        
        delta = self.current_period_end - timezone.now()
        return max(0, delta.days)
    
    def calculate_seats_used(self):
        """Calculate current number of club members"""
        return self.club.members.filter(
            user__is_active=True
        ).count()
    
    def update_seats_used(self):
        """Update seats_used field with current member count"""
        self.seats_used = self.calculate_seats_used()
        self.save(update_fields=['seats_used', 'updated_at'])
        return self.seats_used
    
    def is_within_member_limit(self):
        """Check if club is within subscription member limits"""
        if self.plan.is_unlimited_members:
            return True
        
        current_seats = self.calculate_seats_used()
        return current_seats <= self.plan.max_members
    
    def get_member_limit_status(self):
        """Get detailed member limit status"""
        current_seats = self.calculate_seats_used()
        max_seats = self.plan.max_members
        
        if self.plan.is_unlimited_members:
            return {
                'current': current_seats,
                'max': None,
                'percentage': 0,
                'is_over_limit': False,
                'remaining': None,
                'status': 'unlimited'
            }
        
        percentage = (current_seats / max_seats * 100) if max_seats > 0 else 0
        is_over_limit = current_seats > max_seats
        remaining = max(0, max_seats - current_seats)
        
        if is_over_limit:
            status = 'over_limit'
        elif percentage >= 90:
            status = 'near_limit'
        elif percentage >= 75:
            status = 'approaching_limit'
        else:
            status = 'within_limit'
        
        return {
            'current': current_seats,
            'max': max_seats,
            'percentage': round(percentage, 1),
            'is_over_limit': is_over_limit,
            'remaining': remaining,
            'status': status
        }
    
    def get_available_features(self):
        """Return the raw features JSON of the associated plan.

        This is used by templates to quickly inspect which features are
        enabled for the current subscription. It simply proxies the
        `features_json` from the related SubscriptionPlan instance.
        """
        return self.plan.features_json if self.plan else {}

    def get_member_usage_percentage(self):
        """Return the member usage percentage relative to plan limit.

        If the plan has unlimited members (max_members == -1) the percentage
        is always 0.
        """
        if self.plan.is_unlimited_members or self.plan.max_members <= 0:
            return 0
        current = self.calculate_seats_used()
        return round((current / self.plan.max_members) * 100, 1)
    
    def has_feature_access(self, feature_name):
        """Check if subscription has access to a specific feature"""
        if not self.is_active:
            # Allow basic features for inactive subscriptions
            basic_features = ['basic_club_management', 'member_management']
            return feature_name in basic_features
        
        return self.plan.has_feature(feature_name)
    
    def get_feature_value(self, feature_name, default=None):
        """Get feature value from plan"""
        if not self.is_active:
            return default
        
        return self.plan.get_feature_value(feature_name, default)
    
    def can_add_members(self, count=1):
        """Check if club can add specified number of members"""
        if not self.is_active:
            return False
        
        if self.plan.is_unlimited_members:
            return True
        
        current_seats = self.calculate_seats_used()
        return (current_seats + count) <= self.plan.max_members
    
    def get_upgrade_recommendations(self):
        """Get recommended plans for upgrade"""
        if self.is_within_member_limit():
            return []
        
        current_seats = self.calculate_seats_used()
        
        # Find plans that can accommodate current member count
        suitable_plans = SubscriptionPlan.objects.filter(
            is_active=True,
            monthly_price__gt=self.plan.monthly_price
        ).filter(
            models.Q(max_members__gte=current_seats) |
            models.Q(max_members=-1)  # Unlimited plans
        ).order_by('monthly_price')
        
        return suitable_plans
    
    def sync_with_stripe(self, stripe_subscription_data):
        """Update subscription with data from Stripe webhook"""
        self.status = stripe_subscription_data.get('status', self.status)
        
        if 'current_period_start' in stripe_subscription_data:
            self.current_period_start = timezone.datetime.fromtimestamp(
                stripe_subscription_data['current_period_start'],
                tz=timezone.utc
            )
        
        if 'current_period_end' in stripe_subscription_data:
            self.current_period_end = timezone.datetime.fromtimestamp(
                stripe_subscription_data['current_period_end'],
                tz=timezone.utc
            )
        
        if 'trial_start' in stripe_subscription_data and stripe_subscription_data['trial_start']:
            self.trial_start = timezone.datetime.fromtimestamp(
                stripe_subscription_data['trial_start'],
                tz=timezone.utc
            )
        
        if 'trial_end' in stripe_subscription_data and stripe_subscription_data['trial_end']:
            self.trial_end = timezone.datetime.fromtimestamp(
                stripe_subscription_data['trial_end'],
                tz=timezone.utc
            )
        
        self.cancel_at_period_end = stripe_subscription_data.get(
            'cancel_at_period_end', 
            self.cancel_at_period_end
        )
        
        if 'canceled_at' in stripe_subscription_data and stripe_subscription_data['canceled_at']:
            self.canceled_at = timezone.datetime.fromtimestamp(
                stripe_subscription_data['canceled_at'],
                tz=timezone.utc
            )
        
        self.save()

    # -------------------------------------------------------------
    # Feature helpers (used by decorators and permissions checks)
    # -------------------------------------------------------------

    def has_feature(self, feature_name: str) -> bool:
        """Compatibility shim.

        Some legacy code (decorators, older views) expects
        `subscription.has_feature(name)` to exist.  The main
        implementation lives in :py:meth:`has_feature_access`, so
        this wrapper simply proxies to that to avoid AttributeErrors
        without changing existing call-sites.
        """
        return self.has_feature_access(feature_name)


class BillingEventLog(models.Model):
    """
    Logs Stripe webhook events and other billing-related events
    """
    
    class EventType(models.TextChoices):
        # Subscription events
        SUBSCRIPTION_CREATED = 'customer.subscription.created', 'Subscription Created'
        SUBSCRIPTION_UPDATED = 'customer.subscription.updated', 'Subscription Updated'
        SUBSCRIPTION_DELETED = 'customer.subscription.deleted', 'Subscription Deleted'
        SUBSCRIPTION_TRIAL_WILL_END = 'customer.subscription.trial_will_end', 'Trial Will End'
        
        # Payment events
        INVOICE_CREATED = 'invoice.created', 'Invoice Created'
        INVOICE_PAID = 'invoice.payment_succeeded', 'Invoice Paid'
        INVOICE_FAILED = 'invoice.payment_failed', 'Invoice Payment Failed'
        INVOICE_FINALIZED = 'invoice.finalized', 'Invoice Finalized'
        
        # Customer events
        CUSTOMER_CREATED = 'customer.created', 'Customer Created'
        CUSTOMER_UPDATED = 'customer.updated', 'Customer Updated'
        CUSTOMER_DELETED = 'customer.deleted', 'Customer Deleted'
        
        # Payment method events
        PAYMENT_METHOD_ATTACHED = 'payment_method.attached', 'Payment Method Attached'
        PAYMENT_METHOD_DETACHED = 'payment_method.detached', 'Payment Method Detached'
        
        # Checkout events
        CHECKOUT_SESSION_COMPLETED = 'checkout.session.completed', 'Checkout Completed'
        CHECKOUT_SESSION_EXPIRED = 'checkout.session.expired', 'Checkout Expired'
        
        # Custom internal events
        SUBSCRIPTION_LIMIT_EXCEEDED = 'subscription.limit_exceeded', 'Subscription Limit Exceeded'
        PLAN_CHANGED = 'subscription.plan_changed', 'Plan Changed'
        MANUAL_ADJUSTMENT = 'billing.manual_adjustment', 'Manual Adjustment'
    
    class ProcessingStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PROCESSED = 'processed', 'Processed'
        FAILED = 'failed', 'Failed'
        IGNORED = 'ignored', 'Ignored'
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Event identification
    stripe_event_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        help_text="Stripe Event ID (null for internal events)"
    )
    event_type = models.CharField(
        max_length=50,
        choices=EventType.choices,
        help_text="Type of billing event"
    )
    
    # Processing status
    processing_status = models.CharField(
        max_length=20,
        choices=ProcessingStatus.choices,
        default=ProcessingStatus.PENDING
    )
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the event was successfully processed"
    )
    
    # Event data
    data_json = models.JSONField(
        help_text="Full event data from Stripe or internal event data"
    )
    
    # Relationships
    club_subscription = models.ForeignKey(
        ClubSubscription,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='billing_events',
        help_text="Associated club subscription (if applicable)"
    )
    
    # Error tracking
    error_message = models.TextField(
        blank=True,
        help_text="Error message if processing failed"
    )
    retry_count = models.IntegerField(
        default=0,
        help_text="Number of processing retry attempts"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['stripe_event_id']),
            models.Index(fields=['event_type', 'processing_status']),
            models.Index(fields=['club_subscription', 'event_type']),
            models.Index(fields=['processing_status', 'created_at']),
            models.Index(fields=['processed_at']),
        ]
    
    def __str__(self):
        club_name = self.club_subscription.club.name if self.club_subscription else "N/A"
        return f"{self.event_type} - {club_name} ({self.processing_status})"
    
    def mark_processed(self):
        """Mark event as successfully processed"""
        self.processing_status = self.ProcessingStatus.PROCESSED
        self.processed_at = timezone.now()
        self.error_message = ""
        self.save(update_fields=['processing_status', 'processed_at', 'error_message', 'updated_at'])
    
    def mark_failed(self, error_message):
        """Mark event as failed with error message"""
        self.processing_status = self.ProcessingStatus.FAILED
        self.error_message = error_message
        self.retry_count += 1
        self.save(update_fields=['processing_status', 'error_message', 'retry_count', 'updated_at'])
    
    def mark_ignored(self, reason=""):
        """Mark event as ignored (not relevant for processing)"""
        self.processing_status = self.ProcessingStatus.IGNORED
        if reason:
            self.error_message = f"Ignored: {reason}"
        self.save(update_fields=['processing_status', 'error_message', 'updated_at'])
    
    def can_retry(self, max_retries=3):
        """Check if event can be retried"""
        return (
            self.processing_status == self.ProcessingStatus.FAILED and
            self.retry_count < max_retries
        )
    
    @classmethod
    def log_stripe_event(cls, stripe_event_id, event_type, event_data, club_subscription=None):
        """Create a new billing event log from Stripe webhook"""
        return cls.objects.create(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
            data_json=event_data,
            club_subscription=club_subscription
        )
    
    @classmethod
    def log_internal_event(cls, event_type, event_data, club_subscription=None):
        """Create a new internal billing event log"""
        return cls.objects.create(
            event_type=event_type,
            data_json=event_data,
            club_subscription=club_subscription,
            processing_status=cls.ProcessingStatus.PROCESSED,
            processed_at=timezone.now()
        )
    
    @classmethod
    def get_unprocessed_events(cls):
        """Get all unprocessed events for batch processing"""
        return cls.objects.filter(
            processing_status=cls.ProcessingStatus.PENDING
        ).order_by('created_at')
    
    @classmethod
    def get_failed_events(cls, max_retries=3):
        """Get failed events that can be retried"""
        return cls.objects.filter(
            processing_status=cls.ProcessingStatus.FAILED,
            retry_count__lt=max_retries
        ).order_by('created_at')