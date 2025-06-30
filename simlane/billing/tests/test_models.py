"""
Tests for billing app models
"""

import uuid
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from simlane.billing.models import BillingEventLog
from simlane.billing.models import ClubSubscription
from simlane.billing.models import SubscriptionPlan
from simlane.teams.models import Club
from simlane.teams.models import ClubMember
from simlane.users.models import User


class SubscriptionPlanModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_subscription_plan_creation(self):
        """Test basic subscription plan creation"""
        plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            slug="basic",
            stripe_price_id="price_basic123",
            max_members=25,
            monthly_price=Decimal('19.99'),
            features_json={"race_planning": True, "analytics": False},
            description="Basic plan for small teams",
        )

        self.assertEqual(plan.name, "Basic Plan")
        self.assertEqual(plan.slug, "basic")
        self.assertEqual(plan.max_members, 25)
        self.assertEqual(plan.monthly_price, Decimal('19.99'))
        self.assertTrue(plan.has_feature("race_planning"))
        self.assertFalse(plan.has_feature("analytics"))
        self.assertTrue(plan.is_active)
        self.assertFalse(plan.is_default)

    def test_subscription_plan_str_representation(self):
        """Test subscription plan string representation"""
        plan = SubscriptionPlan.objects.create(
            name="Pro Plan",
            slug="pro",
            max_members=-1,
            monthly_price=Decimal('49.99'),
        )
        self.assertEqual(str(plan), "Pro Plan ($49.99/month)")

    def test_subscription_plan_unique_constraints(self):
        """Test unique constraints on plan fields"""
        SubscriptionPlan.objects.create(
            name="Unique Plan",
            slug="unique",
            stripe_price_id="price_unique123",
            max_members=10,
        )

        # Test unique name
        with self.assertRaises(ValidationError):
            duplicate_name = SubscriptionPlan(
                name="Unique Plan",
                slug="unique2",
                max_members=10,
            )
            duplicate_name.full_clean()

        # Test unique slug
        with self.assertRaises(ValidationError):
            duplicate_slug = SubscriptionPlan(
                name="Another Plan",
                slug="unique",
                max_members=10,
            )
            duplicate_slug.full_clean()

        # Test unique stripe_price_id
        with self.assertRaises(ValidationError):
            duplicate_stripe = SubscriptionPlan(
                name="Third Plan",
                slug="third",
                stripe_price_id="price_unique123",
                max_members=10,
            )
            duplicate_stripe.full_clean()

    def test_subscription_plan_validation(self):
        """Test subscription plan validation rules"""
        # Test invalid max_members values
        with self.assertRaises(ValidationError):
            invalid_plan = SubscriptionPlan(
                name="Invalid Plan",
                slug="invalid",
                max_members=0,  # Invalid: must be positive or -1
            )
            invalid_plan.full_clean()

        with self.assertRaises(ValidationError):
            invalid_plan = SubscriptionPlan(
                name="Invalid Plan 2",
                slug="invalid2",
                max_members=-5,  # Invalid: must be positive or -1
            )
            invalid_plan.full_clean()

    def test_default_plan_constraint(self):
        """Test that only one plan can be set as default"""
        plan1 = SubscriptionPlan.objects.create(
            name="Plan 1",
            slug="plan1",
            max_members=5,
            is_default=True,
        )

        # Creating another default plan should raise validation error
        with self.assertRaises(ValidationError):
            plan2 = SubscriptionPlan(
                name="Plan 2",
                slug="plan2",
                max_members=10,
                is_default=True,
            )
            plan2.full_clean()

        # But we can update the existing default plan
        plan1.description = "Updated description"
        plan1.full_clean()  # Should not raise error

    def test_subscription_plan_properties(self):
        """Test subscription plan computed properties"""
        # Test unlimited members plan
        unlimited_plan = SubscriptionPlan.objects.create(
            name="Unlimited Plan",
            slug="unlimited",
            max_members=-1,
            monthly_price=Decimal('99.99'),
        )
        self.assertTrue(unlimited_plan.is_unlimited_members)
        self.assertFalse(unlimited_plan.is_free_plan)

        # Test free plan
        free_plan = SubscriptionPlan.objects.create(
            name="Free Plan",
            slug="free",
            max_members=5,
            monthly_price=Decimal('0.00'),
        )
        self.assertFalse(free_plan.is_unlimited_members)
        self.assertTrue(free_plan.is_free_plan)

    def test_subscription_plan_features(self):
        """Test feature access methods"""
        plan = SubscriptionPlan.objects.create(
            name="Feature Plan",
            slug="features",
            max_members=25,
            features_json={
                "race_planning": True,
                "analytics": False,
                "max_strategies": 5,
                "api_access": True,
            },
        )

        # Test has_feature method
        self.assertTrue(plan.has_feature("race_planning"))
        self.assertFalse(plan.has_feature("analytics"))
        self.assertFalse(plan.has_feature("nonexistent_feature"))

        # Test get_feature_value method
        self.assertEqual(plan.get_feature_value("max_strategies"), 5)
        self.assertTrue(plan.get_feature_value("api_access"))
        self.assertIsNone(plan.get_feature_value("nonexistent_feature"))
        self.assertEqual(plan.get_feature_value("nonexistent_feature", "default"), "default")

    def test_get_default_plan(self):
        """Test getting the default plan"""
        # No plans exist
        self.assertIsNone(SubscriptionPlan.get_default_plan())

        # Create non-default plan
        plan1 = SubscriptionPlan.objects.create(
            name="Plan 1",
            slug="plan1",
            max_members=5,
            monthly_price=Decimal('10.00'),
        )

        # Should return cheapest plan as fallback
        self.assertEqual(SubscriptionPlan.get_default_plan(), plan1)

        # Create default plan
        plan2 = SubscriptionPlan.objects.create(
            name="Default Plan",
            slug="default",
            max_members=10,
            monthly_price=Decimal('20.00'),
            is_default=True,
        )

        # Should return the default plan
        self.assertEqual(SubscriptionPlan.get_default_plan(), plan2)

        # Deactivate default plan
        plan2.is_active = False
        plan2.save()

        # Should fall back to cheapest active plan
        self.assertEqual(SubscriptionPlan.get_default_plan(), plan1)


class ClubSubscriptionModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="clubowner",
            email="owner@example.com",
            password="testpass123",
        )
        self.club = Club.objects.create(
            name="Test Racing Club",
            created_by=self.user,
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Basic Plan",
            slug="basic",
            max_members=25,
            monthly_price=Decimal('19.99'),
            features_json={"race_planning": True, "analytics": False},
        )

    def test_club_subscription_creation(self):
        """Test basic club subscription creation"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.plan,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test123",
            status=ClubSubscription.SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
        )

        self.assertEqual(subscription.club, self.club)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.status, ClubSubscription.SubscriptionStatus.ACTIVE)
        self.assertTrue(subscription.is_active)
        self.assertFalse(subscription.is_canceled)

    def test_club_subscription_str_representation(self):
        """Test club subscription string representation"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.plan,
            status=ClubSubscription.SubscriptionStatus.ACTIVE,
        )
        expected = f"{self.club.name} - {self.plan.name} (active)"
        self.assertEqual(str(subscription), expected)

    def test_subscription_status_properties(self):
        """Test subscription status property methods"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.plan,
        )

        # Test active status
        subscription.status = ClubSubscription.SubscriptionStatus.ACTIVE
        self.assertTrue(subscription.is_active)
        self.assertFalse(subscription.is_past_due)
        self.assertFalse(subscription.is_canceled)

        # Test trialing status
        subscription.status = ClubSubscription.SubscriptionStatus.TRIALING
        self.assertTrue(subscription.is_active)
        self.assertFalse(subscription.is_past_due)
        self.assertFalse(subscription.is_canceled)

        # Test past due status
        subscription.status = ClubSubscription.SubscriptionStatus.PAST_DUE
        self.assertFalse(subscription.is_active)
        self.assertTrue(subscription.is_past_due)
        self.assertFalse(subscription.is_canceled)

        # Test canceled status
        subscription.status = ClubSubscription.SubscriptionStatus.CANCELED
        self.assertFalse(subscription.is_active)
        self.assertFalse(subscription.is_past_due)
        self.assertTrue(subscription.is_canceled)

    def test_trial_period_detection(self):
        """Test trial period detection"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.plan,
        )

        # No trial end set
        self.assertFalse(subscription.is_on_trial)

        # Trial in future
        subscription.trial_end = timezone.now() + timedelta(days=7)
        self.assertTrue(subscription.is_on_trial)

        # Trial in past
        subscription.trial_end = timezone.now() - timedelta(days=1)
        self.assertFalse(subscription.is_on_trial)

    def test_days_until_renewal(self):
        """Test days until renewal calculation"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.plan,
        )

        # No period end set
        self.assertIsNone(subscription.days_until_renewal)

        # Period end in future
        subscription.current_period_end = timezone.now() + timedelta(days=15)
        self.assertEqual(subscription.days_until_renewal, 15)

        # Period end in past
        subscription.current_period_end = timezone.now() - timedelta(days=5)
        self.assertEqual(subscription.days_until_renewal, 0)

    def test_seat_calculation(self):
        """Test member seat calculation"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.plan,
        )

        # Initially no members except creator
        initial_count = subscription.calculate_seats_used()
        self.assertEqual(initial_count, 1)  # Club creator is automatically added

        # Add more members
        user2 = User.objects.create_user(username="user2", email="user2@example.com")
        user3 = User.objects.create_user(username="user3", email="user3@example.com")
        
        ClubMember.objects.create(club=self.club, user=user2, role="MEMBER")
        ClubMember.objects.create(club=self.club, user=user3, role="MEMBER")

        updated_count = subscription.calculate_seats_used()
        self.assertEqual(updated_count, 3)

        # Test update_seats_used method
        subscription.update_seats_used()
        subscription.refresh_from_db()
        self.assertEqual(subscription.seats_used, 3)

        # Test with inactive user
        user3.is_active = False
        user3.save()
        
        final_count = subscription.calculate_seats_used()
        self.assertEqual(final_count, 2)  # Inactive users don't count

    def test_member_limit_enforcement(self):
        """Test member limit enforcement"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.plan,  # max_members = 25
        )

        # Within limit
        self.assertTrue(subscription.is_within_member_limit())
        self.assertTrue(subscription.can_add_members(1))
        self.assertTrue(subscription.can_add_members(24))  # 1 existing + 24 new = 25

        # At limit
        subscription.seats_used = 25
        subscription.save()
        self.assertTrue(subscription.is_within_member_limit())
        self.assertFalse(subscription.can_add_members(1))

        # Over limit
        subscription.seats_used = 26
        subscription.save()
        self.assertFalse(subscription.is_within_member_limit())
        self.assertFalse(subscription.can_add_members(1))

    def test_unlimited_member_plan(self):
        """Test unlimited member plan behavior"""
        unlimited_plan = SubscriptionPlan.objects.create(
            name="Unlimited Plan",
            slug="unlimited",
            max_members=-1,
            monthly_price=Decimal('99.99'),
        )
        
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=unlimited_plan,
        )

        # Always within limit for unlimited plans
        subscription.seats_used = 1000
        subscription.save()
        self.assertTrue(subscription.is_within_member_limit())
        self.assertTrue(subscription.can_add_members(100))

    def test_member_limit_status(self):
        """Test detailed member limit status"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.plan,  # max_members = 25
            seats_used=20,
        )

        status = subscription.get_member_limit_status()
        self.assertEqual(status['current'], 20)
        self.assertEqual(status['max'], 25)
        self.assertEqual(status['percentage'], 80.0)
        self.assertEqual(status['remaining'], 5)
        self.assertFalse(status['is_over_limit'])
        self.assertEqual(status['status'], 'approaching_limit')

        # Test over limit
        subscription.seats_used = 30
        status = subscription.get_member_limit_status()
        self.assertTrue(status['is_over_limit'])
        self.assertEqual(status['status'], 'over_limit')

        # Test unlimited plan
        unlimited_plan = SubscriptionPlan.objects.create(
            name="Unlimited",
            slug="unlimited",
            max_members=-1,
        )
        subscription.plan = unlimited_plan
        status = subscription.get_member_limit_status()
        self.assertIsNone(status['max'])
        self.assertEqual(status['status'], 'unlimited')

    def test_feature_access(self):
        """Test feature access based on subscription status"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.plan,
            status=ClubSubscription.SubscriptionStatus.ACTIVE,
        )

        # Active subscription has plan features
        self.assertTrue(subscription.has_feature_access("race_planning"))
        self.assertFalse(subscription.has_feature_access("analytics"))

        # Inactive subscription only has basic features
        subscription.status = ClubSubscription.SubscriptionStatus.CANCELED
        self.assertFalse(subscription.has_feature_access("race_planning"))
        self.assertTrue(subscription.has_feature_access("basic_club_management"))

    def test_upgrade_recommendations(self):
        """Test upgrade plan recommendations"""
        # Create multiple plans
        basic_plan = SubscriptionPlan.objects.create(
            name="Basic",
            slug="basic",
            max_members=5,
            monthly_price=Decimal('10.00'),
        )
        pro_plan = SubscriptionPlan.objects.create(
            name="Pro",
            slug="pro",
            max_members=50,
            monthly_price=Decimal('50.00'),
        )
        unlimited_plan = SubscriptionPlan.objects.create(
            name="Unlimited",
            slug="unlimited",
            max_members=-1,
            monthly_price=Decimal('100.00'),
        )

        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=basic_plan,
            seats_used=3,  # Within limit
        )

        # No recommendations when within limit
        recommendations = subscription.get_upgrade_recommendations()
        self.assertEqual(len(recommendations), 0)

        # Over limit should get recommendations
        subscription.seats_used = 10  # Over 5-member limit
        recommendations = subscription.get_upgrade_recommendations()
        
        # Should recommend pro and unlimited plans (both can handle 10 members)
        recommended_names = [plan.name for plan in recommendations]
        self.assertIn("Pro", recommended_names)
        self.assertIn("Unlimited", recommended_names)
        
        # Should be ordered by price (cheapest first)
        self.assertEqual(recommendations[0].name, "Pro")

    def test_stripe_sync(self):
        """Test syncing subscription data from Stripe webhook"""
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.plan,
        )

        # Mock Stripe subscription data
        stripe_data = {
            'status': 'active',
            'current_period_start': 1640995200,  # 2022-01-01 00:00:00 UTC
            'current_period_end': 1643673600,    # 2022-02-01 00:00:00 UTC
            'trial_start': 1640995200,
            'trial_end': 1641600000,             # 2022-01-08 00:00:00 UTC
            'cancel_at_period_end': False,
            'canceled_at': None,
        }

        subscription.sync_with_stripe(stripe_data)

        self.assertEqual(subscription.status, 'active')
        self.assertIsNotNone(subscription.current_period_start)
        self.assertIsNotNone(subscription.current_period_end)
        self.assertIsNotNone(subscription.trial_start)
        self.assertIsNotNone(subscription.trial_end)
        self.assertFalse(subscription.cancel_at_period_end)
        self.assertIsNone(subscription.canceled_at)


class BillingEventLogModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )
        self.club = Club.objects.create(
            name="Test Club",
            created_by=self.user,
        )
        self.plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test",
            max_members=10,
        )
        self.subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.plan,
        )

    def test_billing_event_log_creation(self):
        """Test basic billing event log creation"""
        event_log = BillingEventLog.objects.create(
            stripe_event_id="evt_test123",
            event_type=BillingEventLog.EventType.SUBSCRIPTION_CREATED,
            data_json={"test": "data"},
            club_subscription=self.subscription,
        )

        self.assertEqual(event_log.stripe_event_id, "evt_test123")
        self.assertEqual(event_log.event_type, BillingEventLog.EventType.SUBSCRIPTION_CREATED)
        self.assertEqual(event_log.processing_status, BillingEventLog.ProcessingStatus.PENDING)
        self.assertIsNone(event_log.processed_at)

    def test_billing_event_log_str_representation(self):
        """Test billing event log string representation"""
        event_log = BillingEventLog.objects.create(
            event_type=BillingEventLog.EventType.INVOICE_PAID,
            data_json={},
            club_subscription=self.subscription,
        )
        expected = f"invoice.payment_succeeded - {self.club.name} (pending)"
        self.assertEqual(str(event_log), expected)

    def test_event_processing_status_methods(self):
        """Test event processing status management"""
        event_log = BillingEventLog.objects.create(
            event_type=BillingEventLog.EventType.SUBSCRIPTION_UPDATED,
            data_json={},
            club_subscription=self.subscription,
        )

        # Test mark_processed
        event_log.mark_processed()
        self.assertEqual(event_log.processing_status, BillingEventLog.ProcessingStatus.PROCESSED)
        self.assertIsNotNone(event_log.processed_at)
        self.assertEqual(event_log.error_message, "")

        # Test mark_failed
        event_log.mark_failed("Test error message")
        self.assertEqual(event_log.processing_status, BillingEventLog.ProcessingStatus.FAILED)
        self.assertEqual(event_log.error_message, "Test error message")
        self.assertEqual(event_log.retry_count, 1)

        # Test mark_ignored
        event_log.mark_ignored("Not relevant")
        self.assertEqual(event_log.processing_status, BillingEventLog.ProcessingStatus.IGNORED)
        self.assertEqual(event_log.error_message, "Ignored: Not relevant")

    def test_retry_logic(self):
        """Test event retry logic"""
        event_log = BillingEventLog.objects.create(
            event_type=BillingEventLog.EventType.INVOICE_FAILED,
            data_json={},
            club_subscription=self.subscription,
        )

        # Can retry when failed and under limit
        event_log.mark_failed("First failure")
        self.assertTrue(event_log.can_retry())

        # Still can retry after second failure
        event_log.mark_failed("Second failure")
        self.assertTrue(event_log.can_retry())

        # Cannot retry after third failure (default max is 3)
        event_log.mark_failed("Third failure")
        self.assertFalse(event_log.can_retry())

        # Cannot retry when processed
        event_log.mark_processed()
        self.assertFalse(event_log.can_retry())

    def test_log_stripe_event_class_method(self):
        """Test logging Stripe events"""
        event_log = BillingEventLog.log_stripe_event(
            stripe_event_id="evt_stripe123",
            event_type=BillingEventLog.EventType.CHECKOUT_SESSION_COMPLETED,
            event_data={"session_id": "cs_test123"},
            club_subscription=self.subscription,
        )

        self.assertEqual(event_log.stripe_event_id, "evt_stripe123")
        self.assertEqual(event_log.event_type, BillingEventLog.EventType.CHECKOUT_SESSION_COMPLETED)
        self.assertEqual(event_log.data_json, {"session_id": "cs_test123"})
        self.assertEqual(event_log.club_subscription, self.subscription)
        self.assertEqual(event_log.processing_status, BillingEventLog.ProcessingStatus.PENDING)

    def test_log_internal_event_class_method(self):
        """Test logging internal events"""
        event_log = BillingEventLog.log_internal_event(
            event_type=BillingEventLog.EventType.SUBSCRIPTION_LIMIT_EXCEEDED,
            event_data={"member_count": 30, "limit": 25},
            club_subscription=self.subscription,
        )

        self.assertIsNone(event_log.stripe_event_id)  # Internal events don't have Stripe IDs
        self.assertEqual(event_log.event_type, BillingEventLog.EventType.SUBSCRIPTION_LIMIT_EXCEEDED)
        self.assertEqual(event_log.processing_status, BillingEventLog.ProcessingStatus.PROCESSED)
        self.assertIsNotNone(event_log.processed_at)

    def test_get_unprocessed_events(self):
        """Test getting unprocessed events"""
        # Create various events
        processed_event = BillingEventLog.objects.create(
            event_type=BillingEventLog.EventType.SUBSCRIPTION_CREATED,
            data_json={},
            processing_status=BillingEventLog.ProcessingStatus.PROCESSED,
        )
        
        pending_event1 = BillingEventLog.objects.create(
            event_type=BillingEventLog.EventType.SUBSCRIPTION_UPDATED,
            data_json={},
            processing_status=BillingEventLog.ProcessingStatus.PENDING,
        )
        
        pending_event2 = BillingEventLog.objects.create(
            event_type=BillingEventLog.EventType.INVOICE_PAID,
            data_json={},
            processing_status=BillingEventLog.ProcessingStatus.PENDING,
        )

        unprocessed = BillingEventLog.get_unprocessed_events()
        self.assertEqual(unprocessed.count(), 2)
        self.assertIn(pending_event1, unprocessed)
        self.assertIn(pending_event2, unprocessed)
        self.assertNotIn(processed_event, unprocessed)

    def test_get_failed_events(self):
        """Test getting failed events that can be retried"""
        # Create events with different retry counts
        failed_event_retryable = BillingEventLog.objects.create(
            event_type=BillingEventLog.EventType.INVOICE_FAILED,
            data_json={},
            processing_status=BillingEventLog.ProcessingStatus.FAILED,
            retry_count=2,  # Under default max of 3
        )
        
        failed_event_max_retries = BillingEventLog.objects.create(
            event_type=BillingEventLog.EventType.INVOICE_FAILED,
            data_json={},
            processing_status=BillingEventLog.ProcessingStatus.FAILED,
            retry_count=3,  # At max retries
        )

        failed_events = BillingEventLog.get_failed_events()
        self.assertEqual(failed_events.count(), 1)
        self.assertIn(failed_event_retryable, failed_events)
        self.assertNotIn(failed_event_max_retries, failed_events)


class BillingModelIntegrationTest(TestCase):
    """Integration tests for billing models working together"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="clubowner",
            email="owner@example.com",
            password="testpass123",
        )
        self.club = Club.objects.create(
            name="Integration Test Club",
            created_by=self.user,
        )

    def test_club_subscription_lifecycle(self):
        """Test complete subscription lifecycle"""
        # Create plans
        free_plan = SubscriptionPlan.objects.create(
            name="Free",
            slug="free",
            max_members=5,
            monthly_price=Decimal('0.00'),
            is_default=True,
        )
        
        basic_plan = SubscriptionPlan.objects.create(
            name="Basic",
            slug="basic",
            max_members=25,
            monthly_price=Decimal('19.99'),
            features_json={"race_planning": True},
        )

        # Start with free subscription
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=free_plan,
            status=ClubSubscription.SubscriptionStatus.ACTIVE,
        )

        # Log subscription creation
        creation_log = BillingEventLog.log_internal_event(
            event_type=BillingEventLog.EventType.SUBSCRIPTION_CREATED,
            event_data={"plan": free_plan.name},
            club_subscription=subscription,
        )

        # Add members up to limit
        for i in range(4):  # 4 + 1 creator = 5 total
            user = User.objects.create_user(
                username=f"member{i}",
                email=f"member{i}@example.com",
            )
            ClubMember.objects.create(club=self.club, user=user)

        subscription.update_seats_used()
        self.assertTrue(subscription.is_within_member_limit())

        # Try to add one more member (should exceed limit)
        excess_user = User.objects.create_user(
            username="excess",
            email="excess@example.com",
        )
        ClubMember.objects.create(club=self.club, user=excess_user)
        
        subscription.update_seats_used()
        self.assertFalse(subscription.is_within_member_limit())

        # Log limit exceeded event
        limit_log = BillingEventLog.log_internal_event(
            event_type=BillingEventLog.EventType.SUBSCRIPTION_LIMIT_EXCEEDED,
            event_data={
                "current_members": subscription.seats_used,
                "limit": subscription.plan.max_members,
            },
            club_subscription=subscription,
        )

        # Upgrade to basic plan
        subscription.plan = basic_plan
        subscription.save()

        # Log plan change
        upgrade_log = BillingEventLog.log_internal_event(
            event_type=BillingEventLog.EventType.PLAN_CHANGED,
            event_data={
                "old_plan": free_plan.name,
                "new_plan": basic_plan.name,
            },
            club_subscription=subscription,
        )

        # Now within limit again
        self.assertTrue(subscription.is_within_member_limit())
        self.assertTrue(subscription.has_feature_access("race_planning"))

        # Verify all events were logged
        all_events = BillingEventLog.objects.filter(club_subscription=subscription)
        self.assertEqual(all_events.count(), 3)
        
        event_types = [event.event_type for event in all_events]
        self.assertIn(BillingEventLog.EventType.SUBSCRIPTION_CREATED, event_types)
        self.assertIn(BillingEventLog.EventType.SUBSCRIPTION_LIMIT_EXCEEDED, event_types)
        self.assertIn(BillingEventLog.EventType.PLAN_CHANGED, event_types)

    def test_subscription_feature_gating(self):
        """Test feature access based on subscription status and plan"""
        # Create plans with different features
        basic_plan = SubscriptionPlan.objects.create(
            name="Basic",
            slug="basic",
            max_members=10,
            features_json={
                "race_planning": True,
                "analytics": False,
                "api_access": False,
            },
        )
        
        pro_plan = SubscriptionPlan.objects.create(
            name="Pro",
            slug="pro",
            max_members=50,
            features_json={
                "race_planning": True,
                "analytics": True,
                "api_access": True,
                "advanced_strategies": True,
            },
        )

        # Active basic subscription
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=basic_plan,
            status=ClubSubscription.SubscriptionStatus.ACTIVE,
        )

        # Test basic plan features
        self.assertTrue(subscription.has_feature_access("race_planning"))
        self.assertFalse(subscription.has_feature_access("analytics"))
        self.assertFalse(subscription.has_feature_access("api_access"))

        # Upgrade to pro plan
        subscription.plan = pro_plan
        subscription.save()

        # Test pro plan features
        self.assertTrue(subscription.has_feature_access("race_planning"))
        self.assertTrue(subscription.has_feature_access("analytics"))
        self.assertTrue(subscription.has_feature_access("api_access"))
        self.assertTrue(subscription.has_feature_access("advanced_strategies"))

        # Cancel subscription
        subscription.status = ClubSubscription.SubscriptionStatus.CANCELED
        subscription.save()

        # Only basic features available when canceled
        self.assertFalse(subscription.has_feature_access("race_planning"))
        self.assertFalse(subscription.has_feature_access("analytics"))
        self.assertTrue(subscription.has_feature_access("basic_club_management"))

    @patch('simlane.billing.models.ClubSubscription.calculate_seats_used')
    def test_subscription_seat_tracking_with_mock(self, mock_calculate_seats):
        """Test subscription seat tracking with mocked member count"""
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test",
            max_members=10,
        )
        
        subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=plan,
        )

        # Mock different member counts
        mock_calculate_seats.return_value = 5
        self.assertTrue(subscription.can_add_members(3))
        self.assertTrue(subscription.can_add_members(5))
        self.assertFalse(subscription.can_add_members(6))

        mock_calculate_seats.return_value = 10
        self.assertFalse(subscription.can_add_members(1))
        self.assertTrue(subscription.is_within_member_limit())

        mock_calculate_seats.return_value = 11
        self.assertFalse(subscription.is_within_member_limit())

        # Test status calculations
        status = subscription.get_member_limit_status()
        self.assertEqual(status['current'], 11)
        self.assertTrue(status['is_over_limit'])
        self.assertEqual(status['status'], 'over_limit')


class BillingModelValidationTest(TestCase):
    """Test model validation rules and edge cases"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_subscription_plan_edge_cases(self):
        """Test subscription plan edge cases and validation"""
        # Test very large member limits
        large_plan = SubscriptionPlan.objects.create(
            name="Large Plan",
            slug="large",
            max_members=999999,
            monthly_price=Decimal('999.99'),
        )
        self.assertFalse(large_plan.is_unlimited_members)

        # Test decimal precision for pricing
        precise_plan = SubscriptionPlan.objects.create(
            name="Precise Plan",
            slug="precise",
            max_members=10,
            monthly_price=Decimal('19.999'),  # Will be rounded to 2 decimal places
        )
        # Note: Django will handle decimal precision based on field definition

        # Test empty features JSON
        empty_features_plan = SubscriptionPlan.objects.create(
            name="Empty Features",
            slug="empty",
            max_members=5,
            features_json={},
        )
        self.assertFalse(empty_features_plan.has_feature("any_feature"))

    def test_club_subscription_edge_cases(self):
        """Test club subscription edge cases"""
        club = Club.objects.create(name="Test Club", created_by=self.user)
        plan = SubscriptionPlan.objects.create(
            name="Test Plan",
            slug="test",
            max_members=5,
        )

        # Test subscription without Stripe IDs (manual/internal subscription)
        subscription = ClubSubscription.objects.create(
            club=club,
            plan=plan,
            status=ClubSubscription.SubscriptionStatus.ACTIVE,
        )
        self.assertIsNone(subscription.stripe_customer_id)
        self.assertIsNone(subscription.stripe_subscription_id)

        # Test subscription with future trial end
        future_trial = timezone.now() + timedelta(days=30)
        subscription.trial_end = future_trial
        self.assertTrue(subscription.is_on_trial)

        # Test sync with incomplete Stripe data
        incomplete_stripe_data = {
            'status': 'active',
            # Missing other fields
        }
        subscription.sync_with_stripe(incomplete_stripe_data)
        self.assertEqual(subscription.status, 'active')

    def test_billing_event_log_edge_cases(self):
        """Test billing event log edge cases"""
        # Test event without club subscription
        orphan_event = BillingEventLog.objects.create(
            event_type=BillingEventLog.EventType.CUSTOMER_CREATED,
            data_json={"customer_id": "cus_test"},
        )
        self.assertIsNone(orphan_event.club_subscription)

        # Test event with large data payload
        large_data = {"data": "x" * 10000}  # Large JSON payload
        large_event = BillingEventLog.objects.create(
            event_type=BillingEventLog.EventType.SUBSCRIPTION_UPDATED,
            data_json=large_data,
        )
        self.assertEqual(len(large_event.data_json["data"]), 10000)

        # Test retry count limits
        failed_event = BillingEventLog.objects.create(
            event_type=BillingEventLog.EventType.INVOICE_FAILED,
            data_json={},
        )
        
        # Simulate multiple failures
        for i in range(5):
            failed_event.mark_failed(f"Failure {i+1}")
        
        self.assertEqual(failed_event.retry_count, 5)
        self.assertFalse(failed_event.can_retry(max_retries=3))
        self.assertTrue(failed_event.can_retry(max_retries=10))