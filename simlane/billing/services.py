import logging
import stripe
from decimal import Decimal
from typing import Dict, List, Optional, Tuple, Any
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.dispatch import Signal
from django.core.exceptions import ValidationError

# Configure Stripe
stripe.api_key = getattr(settings, 'STRIPE_SECRET_KEY', '')

# Set up logging
logger = logging.getLogger(__name__)

# Django signals for subscription events
subscription_created = Signal()
subscription_updated = Signal()
subscription_cancelled = Signal()
subscription_reactivated = Signal()

User = get_user_model()


class StripeServiceError(Exception):
    """Base exception for Stripe service errors"""
    pass


class SubscriptionServiceError(Exception):
    """Base exception for subscription service errors"""
    pass


class StripeService:
    """
    Service class for handling Stripe API operations
    """
    
    @staticmethod
    def create_customer(user, **kwargs) -> stripe.Customer:
        """
        Create a Stripe customer for a user
        
        Args:
            user: Django User instance
            **kwargs: Additional customer data
            
        Returns:
            stripe.Customer: Created Stripe customer
            
        Raises:
            StripeServiceError: If customer creation fails
        """
        try:
            customer_data = {
                'email': user.email,
                'name': user.get_full_name() or user.username,
                'metadata': {
                    'user_id': str(user.id),
                    'username': user.username,
                }
            }
            customer_data.update(kwargs)
            
            customer = stripe.Customer.create(**customer_data)
            logger.info(f"Created Stripe customer {customer.id} for user {user.id}")
            return customer
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create Stripe customer for user {user.id}: {e}")
            raise StripeServiceError(f"Failed to create customer: {e}")
    
    @staticmethod
    def create_checkout_session(
        customer_id: str,
        price_id: str,
        success_url: str,
        cancel_url: str,
        club_id: str = None,
        **kwargs
    ) -> stripe.checkout.Session:
        """
        Create a Stripe Checkout session for subscription
        
        Args:
            customer_id: Stripe customer ID
            price_id: Stripe price ID for the subscription
            success_url: URL to redirect after successful payment
            cancel_url: URL to redirect after cancelled payment
            club_id: Club ID for metadata
            **kwargs: Additional session parameters
            
        Returns:
            stripe.checkout.Session: Created checkout session
            
        Raises:
            StripeServiceError: If session creation fails
        """
        try:
            session_data = {
                'customer': customer_id,
                'payment_method_types': ['card'],
                'line_items': [{
                    'price': price_id,
                    'quantity': 1,
                }],
                'mode': 'subscription',
                'success_url': success_url,
                'cancel_url': cancel_url,
                'metadata': {
                    'club_id': club_id,
                } if club_id else {},
                'subscription_data': {
                    'metadata': {
                        'club_id': club_id,
                    } if club_id else {},
                },
                'allow_promotion_codes': True,
                'billing_address_collection': 'required',
            }
            session_data.update(kwargs)
            
            session = stripe.checkout.Session.create(**session_data)
            logger.info(f"Created checkout session {session.id} for customer {customer_id}")
            return session
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to create checkout session: {e}")
            raise StripeServiceError(f"Failed to create checkout session: {e}")
    
    @staticmethod
    def retrieve_subscription(subscription_id: str) -> stripe.Subscription:
        """
        Retrieve a Stripe subscription
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            stripe.Subscription: Retrieved subscription
            
        Raises:
            StripeServiceError: If retrieval fails
        """
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return subscription
        except stripe.error.StripeError as e:
            logger.error(f"Failed to retrieve subscription {subscription_id}: {e}")
            raise StripeServiceError(f"Failed to retrieve subscription: {e}")
    
    @staticmethod
    def update_subscription(
        subscription_id: str,
        price_id: str = None,
        proration_behavior: str = 'create_prorations',
        **kwargs
    ) -> stripe.Subscription:
        """
        Update a Stripe subscription (upgrade/downgrade)
        
        Args:
            subscription_id: Stripe subscription ID
            price_id: New price ID (if changing plan)
            proration_behavior: How to handle prorations
            **kwargs: Additional update parameters
            
        Returns:
            stripe.Subscription: Updated subscription
            
        Raises:
            StripeServiceError: If update fails
        """
        try:
            update_data = {
                'proration_behavior': proration_behavior,
            }
            
            if price_id:
                # Get current subscription to update line items
                subscription = stripe.Subscription.retrieve(subscription_id)
                update_data['items'] = [{
                    'id': subscription['items']['data'][0]['id'],
                    'price': price_id,
                }]
            
            update_data.update(kwargs)
            
            subscription = stripe.Subscription.modify(subscription_id, **update_data)
            logger.info(f"Updated subscription {subscription_id}")
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to update subscription {subscription_id}: {e}")
            raise StripeServiceError(f"Failed to update subscription: {e}")
    
    @staticmethod
    def cancel_subscription(
        subscription_id: str,
        at_period_end: bool = True
    ) -> stripe.Subscription:
        """
        Cancel a Stripe subscription
        
        Args:
            subscription_id: Stripe subscription ID
            at_period_end: Whether to cancel at period end or immediately
            
        Returns:
            stripe.Subscription: Cancelled subscription
            
        Raises:
            StripeServiceError: If cancellation fails
        """
        try:
            if at_period_end:
                subscription = stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True
                )
            else:
                subscription = stripe.Subscription.delete(subscription_id)
            
            logger.info(f"Cancelled subscription {subscription_id} (at_period_end={at_period_end})")
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to cancel subscription {subscription_id}: {e}")
            raise StripeServiceError(f"Failed to cancel subscription: {e}")
    
    @staticmethod
    def reactivate_subscription(subscription_id: str) -> stripe.Subscription:
        """
        Reactivate a cancelled subscription (if still in current period)
        
        Args:
            subscription_id: Stripe subscription ID
            
        Returns:
            stripe.Subscription: Reactivated subscription
            
        Raises:
            StripeServiceError: If reactivation fails
        """
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=False
            )
            logger.info(f"Reactivated subscription {subscription_id}")
            return subscription
            
        except stripe.error.StripeError as e:
            logger.error(f"Failed to reactivate subscription {subscription_id}: {e}")
            raise StripeServiceError(f"Failed to reactivate subscription: {e}")
    
    @staticmethod
    def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
        """
        Construct and verify a Stripe webhook event
        
        Args:
            payload: Raw request body
            sig_header: Stripe signature header
            
        Returns:
            stripe.Event: Verified webhook event
            
        Raises:
            StripeServiceError: If verification fails
        """
        try:
            webhook_secret = getattr(settings, 'STRIPE_WEBHOOK_SECRET', '')
            if not webhook_secret:
                raise StripeServiceError("Webhook secret not configured")
            
            event = stripe.Webhook.construct_event(
                payload, sig_header, webhook_secret
            )
            return event
            
        except ValueError as e:
            logger.error(f"Invalid webhook payload: {e}")
            raise StripeServiceError(f"Invalid payload: {e}")
        except stripe.error.SignatureVerificationError as e:
            logger.error(f"Invalid webhook signature: {e}")
            raise StripeServiceError(f"Invalid signature: {e}")
    
    @staticmethod
    def process_webhook_event(event: stripe.Event) -> bool:
        """
        Process a Stripe webhook event
        
        Args:
            event: Stripe webhook event
            
        Returns:
            bool: True if processed successfully
            
        Raises:
            StripeServiceError: If processing fails
        """
        try:
            # Import here to avoid circular imports
            from .models import BillingEventLog, ClubSubscription
            
            # Log the event
            event_log, created = BillingEventLog.objects.get_or_create(
                stripe_event_id=event['id'],
                defaults={
                    'event_type': event['type'],
                    'data_json': event['data'],
                    'processed_at': timezone.now(),
                }
            )
            
            if not created:
                logger.info(f"Event {event['id']} already processed")
                return True
            
            # Process different event types
            if event['type'] == 'customer.subscription.created':
                SubscriptionService.handle_subscription_created(event['data']['object'])
            elif event['type'] == 'customer.subscription.updated':
                SubscriptionService.handle_subscription_updated(event['data']['object'])
            elif event['type'] == 'customer.subscription.deleted':
                SubscriptionService.handle_subscription_deleted(event['data']['object'])
            elif event['type'] == 'invoice.payment_succeeded':
                SubscriptionService.handle_payment_succeeded(event['data']['object'])
            elif event['type'] == 'invoice.payment_failed':
                SubscriptionService.handle_payment_failed(event['data']['object'])
            else:
                logger.info(f"Unhandled event type: {event['type']}")
            
            # Update event log with club subscription if applicable
            if 'customer' in event['data']['object']:
                customer_id = event['data']['object']['customer']
                try:
                    club_subscription = ClubSubscription.objects.get(
                        stripe_customer_id=customer_id
                    )
                    event_log.club_subscription = club_subscription
                    event_log.save()
                except ClubSubscription.DoesNotExist:
                    pass
            
            logger.info(f"Successfully processed webhook event {event['id']}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to process webhook event {event['id']}: {e}")
            raise StripeServiceError(f"Failed to process webhook: {e}")


class SubscriptionService:
    """
    Service class for managing subscription business logic
    """
    
    @staticmethod
    def get_club_subscription(club) -> Optional['ClubSubscription']:
        """
        Get the active subscription for a club
        
        Args:
            club: Club instance
            
        Returns:
            ClubSubscription or None
        """
        from .models import ClubSubscription
        
        try:
            return ClubSubscription.objects.select_related('plan').get(
                club=club,
                status__in=['active', 'trialing', 'past_due']
            )
        except ClubSubscription.DoesNotExist:
            return None
    
    @staticmethod
    def check_subscription_status(club) -> Dict[str, Any]:
        """
        Check comprehensive subscription status for a club
        
        Args:
            club: Club instance
            
        Returns:
            Dict with subscription status information
        """
        subscription = SubscriptionService.get_club_subscription(club)
        
        if not subscription:
            return {
                'has_subscription': False,
                'status': 'none',
                'plan_name': 'Free',
                'max_members': 5,
                'features': ['basic_club_management'],
                'seats_used': SubscriptionService.calculate_seat_usage(club),
                'seats_available': max(0, 5 - SubscriptionService.calculate_seat_usage(club)),
                'can_add_members': SubscriptionService.calculate_seat_usage(club) < 5,
                'has_race_planning': False,
                'is_trial': False,
                'trial_ends_at': None,
                'current_period_end': None,
            }
        
        seats_used = SubscriptionService.calculate_seat_usage(club)
        max_members = subscription.plan.max_members or float('inf')
        
        return {
            'has_subscription': True,
            'status': subscription.status,
            'plan_name': subscription.plan.name,
            'max_members': max_members,
            'features': subscription.get_available_features(),
            'seats_used': seats_used,
            'seats_available': max(0, max_members - seats_used) if max_members != float('inf') else float('inf'),
            'can_add_members': seats_used < max_members,
            'has_race_planning': subscription.has_feature('race_planning'),
            'is_trial': subscription.status == 'trialing',
            'trial_ends_at': subscription.trial_end,
            'current_period_end': subscription.current_period_end,
            'subscription': subscription,
        }
    
    @staticmethod
    def calculate_seat_usage(club) -> int:
        """
        Calculate current seat usage for a club
        
        Args:
            club: Club instance
            
        Returns:
            int: Number of seats currently used
        """
        from simlane.teams.models import ClubMember
        
        return ClubMember.objects.filter(
            club=club,
            role__in=['admin', 'teams_manager', 'member']
        ).count()
    
    @staticmethod
    def can_add_member(club) -> Tuple[bool, str]:
        """
        Check if a club can add a new member
        
        Args:
            club: Club instance
            
        Returns:
            Tuple[bool, str]: (can_add, reason)
        """
        status = SubscriptionService.check_subscription_status(club)
        
        if not status['can_add_members']:
            return False, f"Club has reached maximum member limit ({status['max_members']}). Please upgrade your subscription."
        
        return True, "Can add member"
    
    @staticmethod
    def can_use_feature(club, feature_name: str) -> Tuple[bool, str]:
        """
        Check if a club can use a specific feature
        
        Args:
            club: Club instance
            feature_name: Name of the feature to check
            
        Returns:
            Tuple[bool, str]: (can_use, reason)
        """
        status = SubscriptionService.check_subscription_status(club)
        
        if feature_name in status['features']:
            return True, "Feature available"
        
        if feature_name == 'race_planning':
            return False, "Race planning requires a paid subscription. Please upgrade to access this feature."
        
        return False, f"Feature '{feature_name}' not available in current plan"
    
    @staticmethod
    def enforce_member_limit(club, raise_exception: bool = True) -> bool:
        """
        Enforce member limits for a club
        
        Args:
            club: Club instance
            raise_exception: Whether to raise exception if limit exceeded
            
        Returns:
            bool: True if within limits
            
        Raises:
            SubscriptionServiceError: If limit exceeded and raise_exception=True
        """
        status = SubscriptionService.check_subscription_status(club)
        
        if status['seats_used'] > status['max_members']:
            message = f"Club exceeds member limit ({status['seats_used']}/{status['max_members']})"
            if raise_exception:
                raise SubscriptionServiceError(message)
            return False
        
        return True
    
    @staticmethod
    @transaction.atomic
    def create_subscription(
        club,
        plan,
        stripe_customer_id: str,
        stripe_subscription_id: str,
        **kwargs
    ) -> 'ClubSubscription':
        """
        Create a new club subscription
        
        Args:
            club: Club instance
            plan: SubscriptionPlan instance
            stripe_customer_id: Stripe customer ID
            stripe_subscription_id: Stripe subscription ID
            **kwargs: Additional subscription data
            
        Returns:
            ClubSubscription: Created subscription
        """
        from .models import ClubSubscription
        
        # Cancel any existing subscriptions
        existing_subscriptions = ClubSubscription.objects.filter(
            club=club,
            status__in=['active', 'trialing', 'past_due']
        )
        
        for sub in existing_subscriptions:
            sub.status = 'cancelled'
            sub.save()
        
        # Create new subscription
        subscription_data = {
            'club': club,
            'plan': plan,
            'stripe_customer_id': stripe_customer_id,
            'stripe_subscription_id': stripe_subscription_id,
            'status': 'active',
            'current_period_start': timezone.now(),
            'current_period_end': timezone.now() + timezone.timedelta(days=30),  # Default, will be updated by webhook
        }
        subscription_data.update(kwargs)
        
        subscription = ClubSubscription.objects.create(**subscription_data)
        
        # Send signal
        subscription_created.send(
            sender=ClubSubscription,
            subscription=subscription,
            club=club
        )
        
        logger.info(f"Created subscription {subscription.id} for club {club.id}")
        return subscription
    
    @staticmethod
    @transaction.atomic
    def upgrade_subscription(club, new_plan) -> 'ClubSubscription':
        """
        Upgrade a club's subscription to a new plan
        
        Args:
            club: Club instance
            new_plan: New SubscriptionPlan instance
            
        Returns:
            ClubSubscription: Updated subscription
            
        Raises:
            SubscriptionServiceError: If upgrade fails
        """
        subscription = SubscriptionService.get_club_subscription(club)
        
        if not subscription:
            raise SubscriptionServiceError("No active subscription found")
        
        if subscription.plan == new_plan:
            raise SubscriptionServiceError("Already on the requested plan")
        
        # Update Stripe subscription
        try:
            StripeService.update_subscription(
                subscription.stripe_subscription_id,
                new_plan.stripe_price_id
            )
        except StripeServiceError as e:
            raise SubscriptionServiceError(f"Failed to upgrade subscription: {e}")
        
        # Update local subscription (will be confirmed by webhook)
        old_plan = subscription.plan
        subscription.plan = new_plan
        subscription.save()
        
        # Send signal
        subscription_updated.send(
            sender=ClubSubscription,
            subscription=subscription,
            club=club,
            old_plan=old_plan,
            new_plan=new_plan
        )
        
        logger.info(f"Upgraded subscription {subscription.id} from {old_plan.name} to {new_plan.name}")
        return subscription
    
    @staticmethod
    @transaction.atomic
    def cancel_subscription(club, at_period_end: bool = True) -> 'ClubSubscription':
        """
        Cancel a club's subscription
        
        Args:
            club: Club instance
            at_period_end: Whether to cancel at period end
            
        Returns:
            ClubSubscription: Cancelled subscription
            
        Raises:
            SubscriptionServiceError: If cancellation fails
        """
        subscription = SubscriptionService.get_club_subscription(club)
        
        if not subscription:
            raise SubscriptionServiceError("No active subscription found")
        
        # Cancel Stripe subscription
        try:
            StripeService.cancel_subscription(
                subscription.stripe_subscription_id,
                at_period_end=at_period_end
            )
        except StripeServiceError as e:
            raise SubscriptionServiceError(f"Failed to cancel subscription: {e}")
        
        # Update local subscription
        if at_period_end:
            subscription.cancel_at_period_end = True
        else:
            subscription.status = 'cancelled'
            subscription.cancelled_at = timezone.now()
        
        subscription.save()
        
        # Send signal
        subscription_cancelled.send(
            sender=ClubSubscription,
            subscription=subscription,
            club=club,
            immediate=not at_period_end
        )
        
        logger.info(f"Cancelled subscription {subscription.id} (at_period_end={at_period_end})")
        return subscription
    
    @staticmethod
    def handle_subscription_created(stripe_subscription: Dict) -> None:
        """
        Handle Stripe subscription.created webhook
        
        Args:
            stripe_subscription: Stripe subscription object
        """
        from .models import ClubSubscription, SubscriptionPlan
        
        try:
            # Get club from metadata
            club_id = stripe_subscription.get('metadata', {}).get('club_id')
            if not club_id:
                logger.warning(f"No club_id in subscription metadata: {stripe_subscription['id']}")
                return
            
            from simlane.teams.models import Club
            club = Club.objects.get(id=club_id)
            
            # Get plan from price ID
            price_id = stripe_subscription['items']['data'][0]['price']['id']
            plan = SubscriptionPlan.objects.get(stripe_price_id=price_id)
            
            # Create or update subscription
            subscription, created = ClubSubscription.objects.update_or_create(
                stripe_subscription_id=stripe_subscription['id'],
                defaults={
                    'club': club,
                    'plan': plan,
                    'stripe_customer_id': stripe_subscription['customer'],
                    'status': stripe_subscription['status'],
                    'current_period_start': timezone.datetime.fromtimestamp(
                        stripe_subscription['current_period_start'], tz=timezone.utc
                    ),
                    'current_period_end': timezone.datetime.fromtimestamp(
                        stripe_subscription['current_period_end'], tz=timezone.utc
                    ),
                }
            )
            
            if created:
                subscription_created.send(
                    sender=ClubSubscription,
                    subscription=subscription,
                    club=club
                )
            
            logger.info(f"Handled subscription.created for {subscription.id}")
            
        except Exception as e:
            logger.error(f"Failed to handle subscription.created: {e}")
            raise
    
    @staticmethod
    def handle_subscription_updated(stripe_subscription: Dict) -> None:
        """
        Handle Stripe subscription.updated webhook
        
        Args:
            stripe_subscription: Stripe subscription object
        """
        from .models import ClubSubscription, SubscriptionPlan
        
        try:
            subscription = ClubSubscription.objects.get(
                stripe_subscription_id=stripe_subscription['id']
            )
            
            # Update subscription details
            old_status = subscription.status
            old_plan = subscription.plan
            
            # Get new plan if price changed
            price_id = stripe_subscription['items']['data'][0]['price']['id']
            new_plan = SubscriptionPlan.objects.get(stripe_price_id=price_id)
            
            subscription.plan = new_plan
            subscription.status = stripe_subscription['status']
            subscription.current_period_start = timezone.datetime.fromtimestamp(
                stripe_subscription['current_period_start'], tz=timezone.utc
            )
            subscription.current_period_end = timezone.datetime.fromtimestamp(
                stripe_subscription['current_period_end'], tz=timezone.utc
            )
            subscription.cancel_at_period_end = stripe_subscription.get('cancel_at_period_end', False)
            
            subscription.save()
            
            # Send appropriate signals
            if old_status != subscription.status or old_plan != new_plan:
                subscription_updated.send(
                    sender=ClubSubscription,
                    subscription=subscription,
                    club=subscription.club,
                    old_plan=old_plan,
                    new_plan=new_plan,
                    old_status=old_status,
                    new_status=subscription.status
                )
            
            logger.info(f"Handled subscription.updated for {subscription.id}")
            
        except ClubSubscription.DoesNotExist:
            logger.warning(f"Subscription not found: {stripe_subscription['id']}")
        except Exception as e:
            logger.error(f"Failed to handle subscription.updated: {e}")
            raise
    
    @staticmethod
    def handle_subscription_deleted(stripe_subscription: Dict) -> None:
        """
        Handle Stripe subscription.deleted webhook
        
        Args:
            stripe_subscription: Stripe subscription object
        """
        from .models import ClubSubscription
        
        try:
            subscription = ClubSubscription.objects.get(
                stripe_subscription_id=stripe_subscription['id']
            )
            
            subscription.status = 'cancelled'
            subscription.cancelled_at = timezone.now()
            subscription.save()
            
            subscription_cancelled.send(
                sender=ClubSubscription,
                subscription=subscription,
                club=subscription.club,
                immediate=True
            )
            
            logger.info(f"Handled subscription.deleted for {subscription.id}")
            
        except ClubSubscription.DoesNotExist:
            logger.warning(f"Subscription not found: {stripe_subscription['id']}")
        except Exception as e:
            logger.error(f"Failed to handle subscription.deleted: {e}")
            raise
    
    @staticmethod
    def handle_payment_succeeded(stripe_invoice: Dict) -> None:
        """
        Handle Stripe invoice.payment_succeeded webhook
        
        Args:
            stripe_invoice: Stripe invoice object
        """
        try:
            subscription_id = stripe_invoice.get('subscription')
            if not subscription_id:
                return
            
            from .models import ClubSubscription
            
            try:
                subscription = ClubSubscription.objects.get(
                    stripe_subscription_id=subscription_id
                )
                
                # Update subscription status if it was past_due
                if subscription.status == 'past_due':
                    subscription.status = 'active'
                    subscription.save()
                    
                    logger.info(f"Reactivated subscription {subscription.id} after successful payment")
                
            except ClubSubscription.DoesNotExist:
                logger.warning(f"Subscription not found for invoice: {stripe_invoice['id']}")
            
        except Exception as e:
            logger.error(f"Failed to handle payment_succeeded: {e}")
            raise
    
    @staticmethod
    def handle_payment_failed(stripe_invoice: Dict) -> None:
        """
        Handle Stripe invoice.payment_failed webhook
        
        Args:
            stripe_invoice: Stripe invoice object
        """
        try:
            subscription_id = stripe_invoice.get('subscription')
            if not subscription_id:
                return
            
            from .models import ClubSubscription
            
            try:
                subscription = ClubSubscription.objects.get(
                    stripe_subscription_id=subscription_id
                )
                
                # Update subscription status
                subscription.status = 'past_due'
                subscription.save()
                
                logger.warning(f"Subscription {subscription.id} marked as past_due due to payment failure")
                
            except ClubSubscription.DoesNotExist:
                logger.warning(f"Subscription not found for invoice: {stripe_invoice['id']}")
            
        except Exception as e:
            logger.error(f"Failed to handle payment_failed: {e}")
            raise
    
    @staticmethod
    def get_upgrade_recommendations(club) -> List[Dict[str, Any]]:
        """
        Get subscription upgrade recommendations for a club
        
        Args:
            club: Club instance
            
        Returns:
            List of upgrade recommendations
        """
        from .models import SubscriptionPlan
        
        current_status = SubscriptionService.check_subscription_status(club)
        current_plan = current_status.get('subscription')
        
        recommendations = []
        
        # Get all available plans
        available_plans = SubscriptionPlan.objects.filter(is_active=True).order_by('monthly_price')
        
        for plan in available_plans:
            # Skip current plan
            if current_plan and current_plan.plan == plan:
                continue
            
            # Skip downgrades if they would violate current usage
            if plan.max_members and current_status['seats_used'] > plan.max_members:
                continue
            
            features = plan.get_features()
            
            recommendation = {
                'plan': plan,
                'monthly_price': plan.monthly_price,
                'max_members': plan.max_members,
                'features': features,
                'benefits': [],
                'is_upgrade': not current_plan or plan.monthly_price > current_plan.plan.monthly_price,
            }
            
            # Calculate benefits
            if not current_status['has_race_planning'] and 'race_planning' in features:
                recommendation['benefits'].append('Access to race planning features')
            
            if plan.max_members and plan.max_members > current_status['max_members']:
                recommendation['benefits'].append(f'Increase member limit to {plan.max_members}')
            
            if plan.max_members is None:
                recommendation['benefits'].append('Unlimited members')
            
            recommendations.append(recommendation)
        
        return recommendations