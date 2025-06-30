"""
Tests for billing services
"""

import json
import uuid
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
from datetime import timedelta

import stripe
from django.test import TestCase, override_settings
from django.utils import timezone
from django.core.exceptions import ValidationError

from simlane.users.models import User
from simlane.teams.models import Club, ClubMember
from simlane.billing.models import SubscriptionPlan, ClubSubscription, BillingEventLog
from simlane.billing.services import (
    StripeService, 
    SubscriptionService, 
    StripeServiceError, 
    SubscriptionServiceError
)


class StripeServiceTest(TestCase):
    """Test StripeService methods"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.club = Club.objects.create(
            name="Test Racing Club",
            created_by=self.user
        )
    
    @patch('stripe.Customer.create')
    def test_create_customer_success(self, mock_create):
        """Test successful customer creation"""
        mock_customer = Mock()
        mock_customer.id = "cus_test123"
        mock_create.return_value = mock_customer
        
        customer = StripeService.create_customer(self.user)
        
        self.assertEqual(customer.id, "cus_test123")
        mock_create.assert_called_once_with(
            email=self.user.email,
            name=self.user.username,  # No full name set
            metadata={
                'user_id': str(self.user.id),
                'username': self.user.username,
            }
        )
    
    @patch('stripe.Customer.create')
    def test_create_customer_with_full_name(self, mock_create):
        """Test customer creation with full name"""
        self.user.first_name = "John"
        self.user.last_name = "Doe"
        self.user.save()
        
        mock_customer = Mock()
        mock_customer.id = "cus_test123"
        mock_create.return_value = mock_customer
        
        customer = StripeService.create_customer(self.user)
        
        mock_create.assert_called_once_with(
            email=self.user.email,
            name="John Doe",
            metadata={
                'user_id': str(self.user.id),
                'username': self.user.username,
            }
        )
    
    @patch('stripe.Customer.create')
    def test_create_customer_with_kwargs(self, mock_create):
        """Test customer creation with additional kwargs"""
        mock_customer = Mock()
        mock_customer.id = "cus_test123"
        mock_create.return_value = mock_customer
        
        customer = StripeService.create_customer(
            self.user,
            phone="+1234567890",
            address={'country': 'US'}
        )
        
        mock_create.assert_called_once_with(
            email=self.user.email,
            name=self.user.username,
            metadata={
                'user_id': str(self.user.id),
                'username': self.user.username,
            },
            phone="+1234567890",
            address={'country': 'US'}
        )
    
    @patch('stripe.Customer.create')
    def test_create_customer_stripe_error(self, mock_create):
        """Test customer creation with Stripe error"""
        mock_create.side_effect = stripe.error.InvalidRequestError(
            "Invalid email", None
        )
        
        with self.assertRaises(StripeServiceError) as context:
            StripeService.create_customer(self.user)
        
        self.assertIn("Failed to create customer", str(context.exception))
    
    @patch('stripe.checkout.Session.create')
    def test_create_checkout_session_success(self, mock_create):
        """Test successful checkout session creation"""
        mock_session = Mock()
        mock_session.id = "cs_test123"
        mock_session.url = "https://checkout.stripe.com/pay/cs_test123"
        mock_create.return_value = mock_session
        
        session = StripeService.create_checkout_session(
            customer_id="cus_test123",
            price_id="price_test123",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            club_id=str(self.club.id)
        )
        
        self.assertEqual(session.id, "cs_test123")
        mock_create.assert_called_once_with(
            customer="cus_test123",
            payment_method_types=['card'],
            line_items=[{
                'price': "price_test123",
                'quantity': 1,
            }],
            mode='subscription',
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            metadata={'club_id': str(self.club.id)},
            subscription_data={'metadata': {'club_id': str(self.club.id)}},
            allow_promotion_codes=True,
            billing_address_collection='required',
        )
    
    @patch('stripe.checkout.Session.create')
    def test_create_checkout_session_without_club(self, mock_create):
        """Test checkout session creation without club ID"""
        mock_session = Mock()
        mock_session.id = "cs_test123"
        mock_create.return_value = mock_session
        
        session = StripeService.create_checkout_session(
            customer_id="cus_test123",
            price_id="price_test123",
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel"
        )
        
        mock_create.assert_called_once_with(
            customer="cus_test123",
            payment_method_types=['card'],
            line_items=[{
                'price': "price_test123",
                'quantity': 1,
            }],
            mode='subscription',
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            metadata={},
            subscription_data={'metadata': {}},
            allow_promotion_codes=True,
            billing_address_collection='required',
        )
    
    @patch('stripe.checkout.Session.create')
    def test_create_checkout_session_stripe_error(self, mock_create):
        """Test checkout session creation with Stripe error"""
        mock_create.side_effect = stripe.error.InvalidRequestError(
            "Invalid price ID", None
        )
        
        with self.assertRaises(StripeServiceError) as context:
            StripeService.create_checkout_session(
                customer_id="cus_test123",
                price_id="invalid_price",
                success_url="https://example.com/success",
                cancel_url="https://example.com/cancel"
            )
        
        self.assertIn("Failed to create checkout session", str(context.exception))
    
    @patch('stripe.Subscription.retrieve')
    def test_retrieve_subscription_success(self, mock_retrieve):
        """Test successful subscription retrieval"""
        mock_subscription = Mock()
        mock_subscription.id = "sub_test123"
        mock_subscription.status = "active"
        mock_retrieve.return_value = mock_subscription
        
        subscription = StripeService.retrieve_subscription("sub_test123")
        
        self.assertEqual(subscription.id, "sub_test123")
        mock_retrieve.assert_called_once_with("sub_test123")
    
    @patch('stripe.Subscription.retrieve')
    def test_retrieve_subscription_error(self, mock_retrieve):
        """Test subscription retrieval with error"""
        mock_retrieve.side_effect = stripe.error.InvalidRequestError(
            "No such subscription", None
        )
        
        with self.assertRaises(StripeServiceError):
            StripeService.retrieve_subscription("invalid_sub")
    
    @patch('stripe.Subscription.retrieve')
    @patch('stripe.Subscription.modify')
    def test_update_subscription_success(self, mock_modify, mock_retrieve):
        """Test successful subscription update"""
        mock_subscription = Mock()
        mock_subscription.id = "sub_test123"
        mock_subscription.__getitem__ = Mock(return_value={
            'data': [{'id': 'si_test123'}]
        })
        mock_retrieve.return_value = mock_subscription
        
        mock_updated = Mock()
        mock_updated.id = "sub_test123"
        mock_modify.return_value = mock_updated
        
        result = StripeService.update_subscription(
            "sub_test123",
            price_id="price_new123"
        )
        
        self.assertEqual(result.id, "sub_test123")
        mock_modify.assert_called_once_with(
            "sub_test123",
            proration_behavior='create_prorations',
            items=[{
                'id': 'si_test123',
                'price': 'price_new123',
            }]
        )
    
    @patch('stripe.Subscription.modify')
    def test_update_subscription_without_price(self, mock_modify):
        """Test subscription update without price change"""
        mock_updated = Mock()
        mock_updated.id = "sub_test123"
        mock_modify.return_value = mock_updated
        
        result = StripeService.update_subscription(
            "sub_test123",
            metadata={'updated': 'true'}
        )
        
        mock_modify.assert_called_once_with(
            "sub_test123",
            proration_behavior='create_prorations',
            metadata={'updated': 'true'}
        )
    
    @patch('stripe.Subscription.modify')
    def test_cancel_subscription_at_period_end(self, mock_modify):
        """Test subscription cancellation at period end"""
        mock_cancelled = Mock()
        mock_cancelled.id = "sub_test123"
        mock_modify.return_value = mock_cancelled
        
        result = StripeService.cancel_subscription("sub_test123", at_period_end=True)
        
        mock_modify.assert_called_once_with(
            "sub_test123",
            cancel_at_period_end=True
        )
    
    @patch('stripe.Subscription.delete')
    def test_cancel_subscription_immediately(self, mock_delete):
        """Test immediate subscription cancellation"""
        mock_cancelled = Mock()
        mock_cancelled.id = "sub_test123"
        mock_delete.return_value = mock_cancelled
        
        result = StripeService.cancel_subscription("sub_test123", at_period_end=False)
        
        mock_delete.assert_called_once_with("sub_test123")
    
    @patch('stripe.Subscription.modify')
    def test_reactivate_subscription_success(self, mock_modify):
        """Test successful subscription reactivation"""
        mock_reactivated = Mock()
        mock_reactivated.id = "sub_test123"
        mock_modify.return_value = mock_reactivated
        
        result = StripeService.reactivate_subscription("sub_test123")
        
        mock_modify.assert_called_once_with(
            "sub_test123",
            cancel_at_period_end=False
        )
    
    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test123')
    @patch('stripe.Webhook.construct_event')
    def test_construct_webhook_event_success(self, mock_construct):
        """Test successful webhook event construction"""
        mock_event = Mock()
        mock_event['id'] = 'evt_test123'
        mock_event['type'] = 'customer.subscription.created'
        mock_construct.return_value = mock_event
        
        payload = b'{"id": "evt_test123"}'
        sig_header = "t=1234567890,v1=signature"
        
        event = StripeService.construct_webhook_event(payload, sig_header)
        
        self.assertEqual(event['id'], 'evt_test123')
        mock_construct.assert_called_once_with(
            payload, sig_header, 'whsec_test123'
        )
    
    @override_settings(STRIPE_WEBHOOK_SECRET='')
    def test_construct_webhook_event_no_secret(self):
        """Test webhook event construction without secret"""
        with self.assertRaises(StripeServiceError) as context:
            StripeService.construct_webhook_event(b'{}', 'sig')
        
        self.assertIn("Webhook secret not configured", str(context.exception))
    
    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test123')
    @patch('stripe.Webhook.construct_event')
    def test_construct_webhook_event_invalid_payload(self, mock_construct):
        """Test webhook event construction with invalid payload"""
        mock_construct.side_effect = ValueError("Invalid payload")
        
        with self.assertRaises(StripeServiceError) as context:
            StripeService.construct_webhook_event(b'invalid', 'sig')
        
        self.assertIn("Invalid payload", str(context.exception))
    
    @override_settings(STRIPE_WEBHOOK_SECRET='whsec_test123')
    @patch('stripe.Webhook.construct_event')
    def test_construct_webhook_event_invalid_signature(self, mock_construct):
        """Test webhook event construction with invalid signature"""
        mock_construct.side_effect = stripe.error.SignatureVerificationError(
            "Invalid signature", 'sig'
        )
        
        with self.assertRaises(StripeServiceError) as context:
            StripeService.construct_webhook_event(b'{}', 'invalid_sig')
        
        self.assertIn("Invalid signature", str(context.exception))
    
    @patch('simlane.billing.services.SubscriptionService.handle_subscription_created')
    def test_process_webhook_event_subscription_created(self, mock_handler):
        """Test processing subscription.created webhook"""
        event = {
            'id': 'evt_test123',
            'type': 'customer.subscription.created',
            'data': {
                'object': {
                    'id': 'sub_test123',
                    'customer': 'cus_test123'
                }
            }
        }
        
        result = StripeService.process_webhook_event(event)
        
        self.assertTrue(result)
        mock_handler.assert_called_once_with(event['data']['object'])
        
        # Check event log was created
        event_log = BillingEventLog.objects.get(stripe_event_id='evt_test123')
        self.assertEqual(event_log.event_type, 'customer.subscription.created')
    
    def test_process_webhook_event_duplicate(self):
        """Test processing duplicate webhook event"""
        # Create existing event log
        BillingEventLog.objects.create(
            stripe_event_id='evt_test123',
            event_type='customer.subscription.created',
            data_json={'test': 'data'},
            processed_at=timezone.now()
        )
        
        event = {
            'id': 'evt_test123',
            'type': 'customer.subscription.created',
            'data': {'object': {}}
        }
        
        result = StripeService.process_webhook_event(event)
        
        self.assertTrue(result)
        # Should only have one event log
        self.assertEqual(BillingEventLog.objects.filter(stripe_event_id='evt_test123').count(), 1)
    
    def test_process_webhook_event_unhandled_type(self):
        """Test processing unhandled webhook event type"""
        event = {
            'id': 'evt_test123',
            'type': 'unhandled.event.type',
            'data': {'object': {}}
        }
        
        result = StripeService.process_webhook_event(event)
        
        self.assertTrue(result)
        # Event should still be logged
        event_log = BillingEventLog.objects.get(stripe_event_id='evt_test123')
        self.assertEqual(event_log.event_type, 'unhandled.event.type')


class SubscriptionServiceTest(TestCase):
    """Test SubscriptionService methods"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.club = Club.objects.create(
            name="Test Racing Club",
            created_by=self.user
        )
        
        # Create subscription plans
        self.free_plan = SubscriptionPlan.objects.create(
            name="Free",
            slug="free",
            max_members=5,
            monthly_price=Decimal('0.00'),
            features_json={'basic_club_management': True},
            is_default=True
        )
        
        self.basic_plan = SubscriptionPlan.objects.create(
            name="Basic",
            slug="basic",
            stripe_price_id="price_basic123",
            max_members=25,
            monthly_price=Decimal('19.99'),
            features_json={
                'basic_club_management': True,
                'race_planning': True
            }
        )
        
        self.pro_plan = SubscriptionPlan.objects.create(
            name="Pro",
            slug="pro",
            stripe_price_id="price_pro123",
            max_members=-1,  # Unlimited
            monthly_price=Decimal('49.99'),
            features_json={
                'basic_club_management': True,
                'race_planning': True,
                'advanced_analytics': True
            }
        )
    
    def test_get_club_subscription_exists(self):
        """Test getting existing club subscription"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        result = SubscriptionService.get_club_subscription(self.club)
        
        self.assertEqual(result, subscription)
    
    def test_get_club_subscription_none(self):
        """Test getting club subscription when none exists"""
        result = SubscriptionService.get_club_subscription(self.club)
        
        self.assertIsNone(result)
    
    def test_get_club_subscription_inactive(self):
        """Test getting club subscription ignores inactive subscriptions"""
        ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.CANCELED
        )
        
        result = SubscriptionService.get_club_subscription(self.club)
        
        self.assertIsNone(result)
    
    def test_check_subscription_status_no_subscription(self):
        """Test subscription status check with no subscription"""
        # Add some members to test seat calculation
        for i in range(3):
            user = User.objects.create_user(
                username=f"member{i}",
                email=f"member{i}@example.com",
                password="password123"
            )
            ClubMember.objects.create(
                club=self.club,
                user=user,
                role="member"
            )
        
        status = SubscriptionService.check_subscription_status(self.club)
        
        expected = {
            'has_subscription': False,
            'status': 'none',
            'plan_name': 'Free',
            'max_members': 5,
            'features': ['basic_club_management'],
            'seats_used': 4,  # 3 members + 1 admin (creator)
            'seats_available': 1,
            'can_add_members': True,
            'has_race_planning': False,
            'is_trial': False,
            'trial_ends_at': None,
            'current_period_end': None,
        }
        
        self.assertEqual(status, expected)
    
    def test_check_subscription_status_with_subscription(self):
        """Test subscription status check with active subscription"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE,
            current_period_end=timezone.now() + timedelta(days=30)
        )
        
        status = SubscriptionService.check_subscription_status(self.club)
        
        self.assertTrue(status['has_subscription'])
        self.assertEqual(status['status'], 'active')
        self.assertEqual(status['plan_name'], 'Basic')
        self.assertEqual(status['max_members'], 25)
        self.assertTrue(status['has_race_planning'])
        self.assertEqual(status['subscription'], subscription)
    
    def test_calculate_seat_usage(self):
        """Test seat usage calculation"""
        # Create additional members
        for i in range(3):
            user = User.objects.create_user(
                username=f"member{i}",
                email=f"member{i}@example.com",
                password="password123"
            )
            ClubMember.objects.create(
                club=self.club,
                user=user,
                role="member"
            )
        
        usage = SubscriptionService.calculate_seat_usage(self.club)
        
        # Should count admin (creator) + 3 members = 4
        self.assertEqual(usage, 4)
    
    def test_can_add_member_within_limit(self):
        """Test can add member when within limits"""
        # Club has 1 admin, free plan allows 5 members
        can_add, reason = SubscriptionService.can_add_member(self.club)
        
        self.assertTrue(can_add)
        self.assertEqual(reason, "Can add member")
    
    def test_can_add_member_at_limit(self):
        """Test can add member when at limit"""
        # Add members to reach limit (4 more to make 5 total)
        for i in range(4):
            user = User.objects.create_user(
                username=f"member{i}",
                email=f"member{i}@example.com",
                password="password123"
            )
            ClubMember.objects.create(
                club=self.club,
                user=user,
                role="member"
            )
        
        can_add, reason = SubscriptionService.can_add_member(self.club)
        
        self.assertFalse(can_add)
        self.assertIn("reached maximum member limit", reason)
    
    def test_can_use_feature_available(self):
        """Test feature access when available"""
        ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        can_use, reason = SubscriptionService.can_use_feature(self.club, 'race_planning')
        
        self.assertTrue(can_use)
        self.assertEqual(reason, "Feature available")
    
    def test_can_use_feature_not_available(self):
        """Test feature access when not available"""
        can_use, reason = SubscriptionService.can_use_feature(self.club, 'race_planning')
        
        self.assertFalse(can_use)
        self.assertIn("Race planning requires a paid subscription", reason)
    
    def test_enforce_member_limit_within_limit(self):
        """Test member limit enforcement when within limits"""
        result = SubscriptionService.enforce_member_limit(self.club)
        
        self.assertTrue(result)
    
    def test_enforce_member_limit_over_limit_exception(self):
        """Test member limit enforcement when over limit with exception"""
        # Add members beyond free plan limit
        for i in range(6):
            user = User.objects.create_user(
                username=f"member{i}",
                email=f"member{i}@example.com",
                password="password123"
            )
            ClubMember.objects.create(
                club=self.club,
                user=user,
                role="member"
            )
        
        with self.assertRaises(SubscriptionServiceError) as context:
            SubscriptionService.enforce_member_limit(self.club)
        
        self.assertIn("exceeds member limit", str(context.exception))
    
    def test_enforce_member_limit_over_limit_no_exception(self):
        """Test member limit enforcement when over limit without exception"""
        # Add members beyond free plan limit
        for i in range(6):
            user = User.objects.create_user(
                username=f"member{i}",
                email=f"member{i}@example.com",
                password="password123"
            )
            ClubMember.objects.create(
                club=self.club,
                user=user,
                role="member"
            )
        
        result = SubscriptionService.enforce_member_limit(self.club, raise_exception=False)
        
        self.assertFalse(result)
    
    def test_create_subscription(self):
        """Test subscription creation"""
        subscription = SubscriptionService.create_subscription(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        self.assertEqual(subscription.club, self.club)
        self.assertEqual(subscription.plan, self.basic_plan)
        self.assertEqual(subscription.stripe_customer_id, "cus_test123")
        self.assertEqual(subscription.stripe_subscription_id, "sub_test123")
        self.assertEqual(subscription.status, ClubSubscription.SubscriptionStatus.ACTIVE)
    
    def test_create_subscription_cancels_existing(self):
        """Test that creating subscription cancels existing ones"""
        # Create existing subscription
        existing = ClubSubscription.objects.create(
            club=self.club,
            plan=self.free_plan,
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        # Create new subscription
        new_subscription = SubscriptionService.create_subscription(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123"
        )
        
        # Check existing subscription was cancelled
        existing.refresh_from_db()
        self.assertEqual(existing.status, ClubSubscription.SubscriptionStatus.CANCELED)
        
        # Check new subscription is active
        self.assertEqual(new_subscription.status, ClubSubscription.SubscriptionStatus.ACTIVE)
    
    @patch('simlane.billing.services.StripeService.update_subscription')
    def test_upgrade_subscription_success(self, mock_update):
        """Test successful subscription upgrade"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        mock_stripe_sub = Mock()
        mock_update.return_value = mock_stripe_sub
        
        result = SubscriptionService.upgrade_subscription(self.club, self.pro_plan)
        
        self.assertEqual(result.plan, self.pro_plan)
        mock_update.assert_called_once_with("sub_test123", "price_pro123")
    
    def test_upgrade_subscription_no_subscription(self):
        """Test upgrade when no subscription exists"""
        with self.assertRaises(SubscriptionServiceError) as context:
            SubscriptionService.upgrade_subscription(self.club, self.basic_plan)
        
        self.assertIn("No active subscription found", str(context.exception))
    
    def test_upgrade_subscription_same_plan(self):
        """Test upgrade to same plan"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        with self.assertRaises(SubscriptionServiceError) as context:
            SubscriptionService.upgrade_subscription(self.club, self.basic_plan)
        
        self.assertIn("Already on the requested plan", str(context.exception))
    
    @patch('simlane.billing.services.StripeService.update_subscription')
    def test_upgrade_subscription_stripe_error(self, mock_update):
        """Test upgrade with Stripe error"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        mock_update.side_effect = StripeServiceError("Stripe error")
        
        with self.assertRaises(SubscriptionServiceError) as context:
            SubscriptionService.upgrade_subscription(self.club, self.pro_plan)
        
        self.assertIn("Failed to upgrade subscription", str(context.exception))
    
    @patch('simlane.billing.services.StripeService.cancel_subscription')
    def test_cancel_subscription_success(self, mock_cancel):
        """Test successful subscription cancellation"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        mock_stripe_sub = Mock()
        mock_cancel.return_value = mock_stripe_sub
        
        result = SubscriptionService.cancel_subscription(self.club, at_period_end=True)
        
        self.assertTrue(result.cancel_at_period_end)
        mock_cancel.assert_called_once_with("sub_test123", at_period_end=True)
    
    @patch('simlane.billing.services.StripeService.cancel_subscription')
    def test_cancel_subscription_immediately(self, mock_cancel):
        """Test immediate subscription cancellation"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        mock_stripe_sub = Mock()
        mock_cancel.return_value = mock_stripe_sub
        
        result = SubscriptionService.cancel_subscription(self.club, at_period_end=False)
        
        self.assertEqual(result.status, ClubSubscription.SubscriptionStatus.CANCELED)
        self.assertIsNotNone(result.cancelled_at)
        mock_cancel.assert_called_once_with("sub_test123", at_period_end=False)
    
    def test_handle_subscription_created(self):
        """Test handling subscription.created webhook"""
        stripe_subscription = {
            'id': 'sub_test123',
            'customer': 'cus_test123',
            'status': 'active',
            'current_period_start': 1234567890,
            'current_period_end': 1234567890 + 2592000,  # +30 days
            'metadata': {'club_id': str(self.club.id)},
            'items': {
                'data': [{'price': {'id': 'price_basic123'}}]
            }
        }
        
        SubscriptionService.handle_subscription_created(stripe_subscription)
        
        subscription = ClubSubscription.objects.get(stripe_subscription_id='sub_test123')
        self.assertEqual(subscription.club, self.club)
        self.assertEqual(subscription.plan, self.basic_plan)
        self.assertEqual(subscription.status, ClubSubscription.SubscriptionStatus.ACTIVE)
    
    def test_handle_subscription_created_no_club_id(self):
        """Test handling subscription.created without club_id"""
        stripe_subscription = {
            'id': 'sub_test123',
            'customer': 'cus_test123',
            'status': 'active',
            'current_period_start': 1234567890,
            'current_period_end': 1234567890 + 2592000,
            'metadata': {},  # No club_id
            'items': {
                'data': [{'price': {'id': 'price_basic123'}}]
            }
        }
        
        # Should not raise exception, just log warning
        SubscriptionService.handle_subscription_created(stripe_subscription)
        
        # No subscription should be created
        self.assertFalse(ClubSubscription.objects.filter(stripe_subscription_id='sub_test123').exists())
    
    def test_handle_subscription_updated(self):
        """Test handling subscription.updated webhook"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        stripe_subscription = {
            'id': 'sub_test123',
            'status': 'past_due',
            'current_period_start': 1234567890,
            'current_period_end': 1234567890 + 2592000,
            'cancel_at_period_end': True,
            'items': {
                'data': [{'price': {'id': 'price_pro123'}}]  # Changed to pro plan
            }
        }
        
        SubscriptionService.handle_subscription_updated(stripe_subscription)
        
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, ClubSubscription.SubscriptionStatus.PAST_DUE)
        self.assertEqual(subscription.plan, self.pro_plan)
        self.assertTrue(subscription.cancel_at_period_end)
    
    def test_handle_subscription_deleted(self):
        """Test handling subscription.deleted webhook"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        stripe_subscription = {
            'id': 'sub_test123',
        }
        
        SubscriptionService.handle_subscription_deleted(stripe_subscription)
        
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, ClubSubscription.SubscriptionStatus.CANCELED)
        self.assertIsNotNone(subscription.cancelled_at)
    
    def test_handle_payment_succeeded_past_due(self):
        """Test handling payment_succeeded for past_due subscription"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.PAST_DUE
        )
        
        stripe_invoice = {
            'id': 'in_test123',
            'subscription': 'sub_test123',
        }
        
        SubscriptionService.handle_payment_succeeded(stripe_invoice)
        
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, ClubSubscription.SubscriptionStatus.ACTIVE)
    
    def test_handle_payment_failed(self):
        """Test handling payment_failed webhook"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        stripe_invoice = {
            'id': 'in_test123',
            'subscription': 'sub_test123',
        }
        
        SubscriptionService.handle_payment_failed(stripe_invoice)
        
        subscription.refresh_from_db()
        self.assertEqual(subscription.status, ClubSubscription.SubscriptionStatus.PAST_DUE)
    
    def test_get_upgrade_recommendations_no_subscription(self):
        """Test upgrade recommendations with no subscription"""
        recommendations = SubscriptionService.get_upgrade_recommendations(self.club)
        
        # Should recommend all paid plans
        self.assertEqual(len(recommendations), 2)  # Basic and Pro
        
        basic_rec = next(r for r in recommendations if r['plan'] == self.basic_plan)
        self.assertTrue(basic_rec['is_upgrade'])
        self.assertIn('Access to race planning features', basic_rec['benefits'])
    
    def test_get_upgrade_recommendations_with_subscription(self):
        """Test upgrade recommendations with existing subscription"""
        ClubSubscription.objects.create(
            club=self.club,
            plan=self.basic_plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE
        )
        
        recommendations = SubscriptionService.get_upgrade_recommendations(self.club)
        
        # Should only recommend Pro plan (higher than current Basic)
        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0]['plan'], self.pro_plan)
        self.assertIn('Unlimited members', recommendations[0]['benefits'])
    
    def test_get_upgrade_recommendations_over_limit(self):
        """Test upgrade recommendations when over member limit"""
        # Add many members to exceed basic plan limit
        for i in range(30):
            user = User.objects.create_user(
                username=f"member{i}",
                email=f"member{i}@example.com",
                password="password123"
            )
            ClubMember.objects.create(
                club=self.club,
                user=user,
                role="member"
            )
        
        recommendations = SubscriptionService.get_upgrade_recommendations(self.club)
        
        # Should only recommend Pro plan (unlimited members)
        # Basic plan should be excluded because it can't accommodate current members
        self.assertEqual(len(recommendations), 1)
        self.assertEqual(recommendations[0]['plan'], self.pro_plan)


class BillingServiceIntegrationTest(TestCase):
    """Integration tests for billing services"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123"
        )
        self.club = Club.objects.create(
            name="Test Racing Club",
            created_by=self.user
        )
        
        self.basic_plan = SubscriptionPlan.objects.create(
            name="Basic",
            slug="basic",
            stripe_price_id="price_basic123",
            max_members=25,
            monthly_price=Decimal('19.99'),
            features_json={
                'basic_club_management': True,
                'race_planning': True
            }
        )
    
    @patch('simlane.billing.services.StripeService.create_customer')
    @patch('simlane.billing.services.StripeService.create_checkout_session')
    def test_full_subscription_flow(self, mock_checkout, mock_customer):
        """Test complete subscription creation flow"""
        # Mock Stripe responses
        mock_customer.return_value = Mock(id="cus_test123")
        mock_checkout.return_value = Mock(
            id="cs_test123",
            url="https://checkout.stripe.com/pay/cs_test123"
        )
        
        # Create customer
        customer = StripeService.create_customer(self.user)
        
        # Create checkout session
        session = StripeService.create_checkout_session(
            customer_id=customer.id,
            price_id=self.basic_plan.stripe_price_id,
            success_url="https://example.com/success",
            cancel_url="https://example.com/cancel",
            club_id=str(self.club.id)
        )
        
        # Simulate webhook after successful payment
        stripe_subscription = {
            'id': 'sub_test123',
            'customer': customer.id,
            'status': 'active',
            'current_period_start': int(timezone.now().timestamp()),
            'current_period_end': int((timezone.now() + timedelta(days=30)).timestamp()),
            'metadata': {'club_id': str(self.club.id)},
            'items': {
                'data': [{'price': {'id': self.basic_plan.stripe_price_id}}]
            }
        }
        
        SubscriptionService.handle_subscription_created(stripe_subscription)
        
        # Verify subscription was created
        subscription = ClubSubscription.objects.get(club=self.club)
        self.assertEqual(subscription.plan, self.basic_plan)
        self.assertEqual(subscription.stripe_customer_id, customer.id)
        self.assertEqual(subscription.stripe_subscription_id, 'sub_test123')
        self.assertEqual(subscription.status, ClubSubscription.SubscriptionStatus.ACTIVE)
        
        # Verify subscription status
        status = SubscriptionService.check_subscription_status(self.club)
        self.assertTrue(status['has_subscription'])
        self.assertTrue(status['has_race_planning'])
        self.assertEqual(status['max_members'], 25)