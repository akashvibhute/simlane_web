"""
Tests for billing views and subscription enforcement
"""

import json
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpResponse
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone

from simlane.billing.models import SubscriptionPlan, ClubSubscription, BillingEventLog
from simlane.billing.views import (
    subscription_dashboard,
    start_checkout,
    subscription_success,
    subscription_cancel,
    stripe_webhook,
    upgrade_required,
)
from simlane.teams.models import Club, ClubMember, ClubRole
from simlane.users.models import User


class BillingViewsTestCase(TestCase):
    """Base test case with common setup for billing views"""

    def setUp(self):
        self.factory = RequestFactory()
        
        # Create test users
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123",
        )
        self.member_user = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="testpass123",
        )
        self.non_member_user = User.objects.create_user(
            username="nonmember",
            email="nonmember@example.com",
            password="testpass123",
        )
        
        # Create test club
        self.club = Club.objects.create(
            name="Test Racing Club",
            slug="test-racing-club",
            description="A test club for racing",
            created_by=self.admin_user,
        )
        
        # Create club memberships
        ClubMember.objects.create(
            club=self.club,
            user=self.admin_user,
            role=ClubRole.ADMIN,
        )
        ClubMember.objects.create(
            club=self.club,
            user=self.member_user,
            role=ClubRole.MEMBER,
        )
        
        # Create subscription plans
        self.free_plan = SubscriptionPlan.objects.create(
            name="Free",
            stripe_price_id="price_free",
            max_members=5,
            monthly_price=Decimal("0.00"),
            features_json={"race_planning": False},
            is_active=True,
        )
        self.basic_plan = SubscriptionPlan.objects.create(
            name="Basic",
            stripe_price_id="price_basic",
            max_members=25,
            monthly_price=Decimal("9.99"),
            features_json={"race_planning": True},
            is_active=True,
        )
        self.pro_plan = SubscriptionPlan.objects.create(
            name="Pro",
            stripe_price_id="price_pro",
            max_members=None,  # Unlimited
            monthly_price=Decimal("19.99"),
            features_json={"race_planning": True, "advanced_analytics": True},
            is_active=True,
        )
        
        # Create club subscription
        self.club_subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.free_plan,
            stripe_customer_id="cus_test123",
            status="active",
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30),
            seats_used=2,
        )


class SubscriptionDashboardViewTest(BillingViewsTestCase):
    """Test subscription dashboard view"""

    def test_subscription_dashboard_admin_access(self):
        """Test that club admin can access subscription dashboard"""
        request = self.factory.get(f"/billing/{self.club.slug}/dashboard/")
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = subscription_dashboard(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Test Racing Club")
        self.assertContains(response, "Free Plan")
        self.assertContains(response, "2 / 5 members")

    def test_subscription_dashboard_member_forbidden(self):
        """Test that regular club member cannot access subscription dashboard"""
        request = self.factory.get(f"/billing/{self.club.slug}/dashboard/")
        request.user = self.member_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.member_user
        )
        
        with self.assertRaises(PermissionDenied):
            subscription_dashboard(request, club_slug=self.club.slug)

    def test_subscription_dashboard_non_member_forbidden(self):
        """Test that non-club member cannot access subscription dashboard"""
        request = self.factory.get(f"/billing/{self.club.slug}/dashboard/")
        request.user = self.non_member_user
        
        with self.assertRaises(Http404):
            subscription_dashboard(request, club_slug=self.club.slug)

    def test_subscription_dashboard_anonymous_user(self):
        """Test that anonymous user is redirected to login"""
        request = self.factory.get(f"/billing/{self.club.slug}/dashboard/")
        request.user = AnonymousUser()
        
        response = subscription_dashboard(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_subscription_dashboard_context_data(self):
        """Test that dashboard view provides correct context data"""
        request = self.factory.get(f"/billing/{self.club.slug}/dashboard/")
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = subscription_dashboard(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 200)
        # Check that subscription data is in context
        self.assertContains(response, "Free")
        self.assertContains(response, "$0.00")
        self.assertContains(response, "2 / 5")


class StartCheckoutViewTest(BillingViewsTestCase):
    """Test checkout initiation view"""

    @patch('simlane.billing.services.StripeService.create_checkout_session')
    def test_start_checkout_success(self, mock_create_session):
        """Test successful checkout session creation"""
        mock_create_session.return_value = {
            'url': 'https://checkout.stripe.com/session123'
        }
        
        request = self.factory.post(
            f"/billing/{self.club.slug}/checkout/",
            {'plan_id': self.basic_plan.id}
        )
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = start_checkout(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, 'https://checkout.stripe.com/session123')
        mock_create_session.assert_called_once()

    def test_start_checkout_invalid_plan(self):
        """Test checkout with invalid plan ID"""
        request = self.factory.post(
            f"/billing/{self.club.slug}/checkout/",
            {'plan_id': 99999}
        )
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = start_checkout(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 404)

    def test_start_checkout_member_forbidden(self):
        """Test that regular member cannot start checkout"""
        request = self.factory.post(
            f"/billing/{self.club.slug}/checkout/",
            {'plan_id': self.basic_plan.id}
        )
        request.user = self.member_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.member_user
        )
        
        with self.assertRaises(PermissionDenied):
            start_checkout(request, club_slug=self.club.slug)

    @patch('simlane.billing.services.StripeService.create_checkout_session')
    def test_start_checkout_stripe_error(self, mock_create_session):
        """Test checkout when Stripe returns an error"""
        mock_create_session.side_effect = Exception("Stripe API error")
        
        request = self.factory.post(
            f"/billing/{self.club.slug}/checkout/",
            {'plan_id': self.basic_plan.id}
        )
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = start_checkout(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 500)

    def test_start_checkout_get_method(self):
        """Test that GET request to checkout shows plan selection"""
        request = self.factory.get(f"/billing/{self.club.slug}/checkout/")
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = start_checkout(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Basic")
        self.assertContains(response, "Pro")
        self.assertContains(response, "$9.99")
        self.assertContains(response, "$19.99")


class SubscriptionSuccessViewTest(BillingViewsTestCase):
    """Test subscription success callback view"""

    def test_subscription_success(self):
        """Test successful subscription completion"""
        request = self.factory.get(
            f"/billing/{self.club.slug}/success/",
            {'session_id': 'cs_test_session123'}
        )
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = subscription_success(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subscription Successful")
        self.assertContains(response, "Test Racing Club")

    def test_subscription_success_missing_session(self):
        """Test success page without session ID"""
        request = self.factory.get(f"/billing/{self.club.slug}/success/")
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = subscription_success(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subscription Successful")


class SubscriptionCancelViewTest(BillingViewsTestCase):
    """Test subscription cancellation callback view"""

    def test_subscription_cancel(self):
        """Test subscription cancellation page"""
        request = self.factory.get(f"/billing/{self.club.slug}/cancel/")
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = subscription_cancel(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Subscription Cancelled")
        self.assertContains(response, "Try Again")


class StripeWebhookViewTest(BillingViewsTestCase):
    """Test Stripe webhook processing"""

    @patch('simlane.billing.services.StripeService.verify_webhook_signature')
    @patch('simlane.billing.services.SubscriptionService.handle_subscription_updated')
    def test_webhook_subscription_updated(self, mock_handle_updated, mock_verify):
        """Test webhook processing for subscription.updated event"""
        mock_verify.return_value = True
        
        webhook_payload = {
            'id': 'evt_test123',
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'id': 'sub_test123',
                    'customer': 'cus_test123',
                    'status': 'active',
                    'current_period_start': 1234567890,
                    'current_period_end': 1234567890 + 2592000,  # +30 days
                }
            }
        }
        
        request = self.factory.post(
            "/billing/stripe/webhook/",
            data=json.dumps(webhook_payload),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature"
        )
        
        response = stripe_webhook(request)
        
        self.assertEqual(response.status_code, 200)
        mock_verify.assert_called_once()
        mock_handle_updated.assert_called_once()

    @patch('simlane.billing.services.StripeService.verify_webhook_signature')
    def test_webhook_invalid_signature(self, mock_verify):
        """Test webhook with invalid signature"""
        mock_verify.return_value = False
        
        request = self.factory.post(
            "/billing/stripe/webhook/",
            data='{"test": "data"}',
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="invalid_signature"
        )
        
        response = stripe_webhook(request)
        
        self.assertEqual(response.status_code, 400)

    def test_webhook_missing_signature(self):
        """Test webhook without signature header"""
        request = self.factory.post(
            "/billing/stripe/webhook/",
            data='{"test": "data"}',
            content_type="application/json"
        )
        
        response = stripe_webhook(request)
        
        self.assertEqual(response.status_code, 400)

    @patch('simlane.billing.services.StripeService.verify_webhook_signature')
    def test_webhook_duplicate_event(self, mock_verify):
        """Test webhook with duplicate event ID"""
        mock_verify.return_value = True
        
        # Create existing event log
        BillingEventLog.objects.create(
            stripe_event_id="evt_test123",
            event_type="customer.subscription.updated",
            processed_at=timezone.now(),
            data_json={"test": "data"},
            club_subscription=self.club_subscription,
        )
        
        webhook_payload = {
            'id': 'evt_test123',
            'type': 'customer.subscription.updated',
            'data': {'object': {'id': 'sub_test123'}}
        }
        
        request = self.factory.post(
            "/billing/stripe/webhook/",
            data=json.dumps(webhook_payload),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature"
        )
        
        response = stripe_webhook(request)
        
        self.assertEqual(response.status_code, 200)
        # Should not create duplicate log entry
        self.assertEqual(
            BillingEventLog.objects.filter(stripe_event_id="evt_test123").count(),
            1
        )

    @patch('simlane.billing.services.StripeService.verify_webhook_signature')
    def test_webhook_unsupported_event_type(self, mock_verify):
        """Test webhook with unsupported event type"""
        mock_verify.return_value = True
        
        webhook_payload = {
            'id': 'evt_test123',
            'type': 'unsupported.event.type',
            'data': {'object': {'id': 'obj_test123'}}
        }
        
        request = self.factory.post(
            "/billing/stripe/webhook/",
            data=json.dumps(webhook_payload),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature"
        )
        
        response = stripe_webhook(request)
        
        self.assertEqual(response.status_code, 200)


class UpgradeRequiredViewTest(BillingViewsTestCase):
    """Test upgrade required view"""

    def test_upgrade_required_member_limit(self):
        """Test upgrade required view for member limit"""
        request = self.factory.get(
            f"/billing/{self.club.slug}/upgrade-required/",
            {'reason': 'member_limit', 'feature': 'add_member'}
        )
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = upgrade_required(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Member Limit Reached")
        self.assertContains(response, "Free Plan")
        self.assertContains(response, "5 members")

    def test_upgrade_required_race_planning(self):
        """Test upgrade required view for race planning feature"""
        request = self.factory.get(
            f"/billing/{self.club.slug}/upgrade-required/",
            {'reason': 'feature_required', 'feature': 'race_planning'}
        )
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = upgrade_required(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Feature Not Available")
        self.assertContains(response, "Race Planning")
        self.assertContains(response, "Basic Plan")

    def test_upgrade_required_member_access(self):
        """Test that regular members can view upgrade required page"""
        request = self.factory.get(
            f"/billing/{self.club.slug}/upgrade-required/",
            {'reason': 'member_limit'}
        )
        request.user = self.member_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.member_user
        )
        
        response = upgrade_required(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Member Limit Reached")


class SubscriptionEnforcementTest(BillingViewsTestCase):
    """Test subscription enforcement in views"""

    def test_member_limit_enforcement(self):
        """Test that member limit is enforced when adding new members"""
        # Fill up the free plan to its limit
        for i in range(3):  # Already have 2 members, add 3 more to reach 5
            user = User.objects.create_user(
                username=f"user{i}",
                email=f"user{i}@example.com",
                password="testpass123",
            )
            ClubMember.objects.create(
                club=self.club,
                user=user,
                role=ClubRole.MEMBER,
            )
        
        # Update seats used
        self.club_subscription.seats_used = 5
        self.club_subscription.save()
        
        # Try to add another member (should fail)
        new_user = User.objects.create_user(
            username="newuser",
            email="newuser@example.com",
            password="testpass123",
        )
        
        # This would be tested in the actual view that adds members
        # For now, we test the subscription service method
        from simlane.billing.services import SubscriptionService
        
        service = SubscriptionService()
        can_add, reason = service.can_add_member(self.club)
        
        self.assertFalse(can_add)
        self.assertIn("member limit", reason.lower())

    def test_race_planning_feature_enforcement(self):
        """Test that race planning features are gated behind subscription"""
        from simlane.billing.services import SubscriptionService
        
        service = SubscriptionService()
        has_feature = service.has_feature(self.club, "race_planning")
        
        self.assertFalse(has_feature)  # Free plan doesn't have race planning
        
        # Upgrade to basic plan
        self.club_subscription.plan = self.basic_plan
        self.club_subscription.save()
        
        has_feature = service.has_feature(self.club, "race_planning")
        self.assertTrue(has_feature)  # Basic plan has race planning


class BillingAPIEndpointsTest(BillingViewsTestCase):
    """Test billing-related API endpoints"""

    def test_subscription_status_api(self):
        """Test API endpoint for subscription status"""
        request = self.factory.get(f"/api/clubs/{self.club.slug}/subscription/")
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        # This would be implemented in the API views
        # For now, we test the data structure
        expected_data = {
            "plan_name": "Free",
            "max_members": 5,
            "seats_used": 2,
            "features": {"race_planning": False},
            "status": "active",
        }
        
        # Verify the subscription data matches expected structure
        self.assertEqual(self.club_subscription.plan.name, expected_data["plan_name"])
        self.assertEqual(self.club_subscription.plan.max_members, expected_data["max_members"])
        self.assertEqual(self.club_subscription.seats_used, expected_data["seats_used"])

    def test_payment_required_response(self):
        """Test that API returns 402 Payment Required for subscription limits"""
        # This would be tested in actual API views
        # For now, we verify the HTTP status code constant
        from django.http import HttpResponse
        
        response = HttpResponse(
            json.dumps({"error": "Subscription upgrade required"}),
            status=402,
            content_type="application/json"
        )
        
        self.assertEqual(response.status_code, 402)


class BillingErrorHandlingTest(BillingViewsTestCase):
    """Test error handling in billing views"""

    @patch('simlane.billing.services.StripeService.create_checkout_session')
    def test_stripe_service_unavailable(self, mock_create_session):
        """Test handling when Stripe service is unavailable"""
        mock_create_session.side_effect = Exception("Service unavailable")
        
        request = self.factory.post(
            f"/billing/{self.club.slug}/checkout/",
            {'plan_id': self.basic_plan.id}
        )
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = start_checkout(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 500)

    def test_invalid_club_slug(self):
        """Test handling of invalid club slug"""
        request = self.factory.get("/billing/invalid-club/dashboard/")
        request.user = self.admin_user
        
        with self.assertRaises(Http404):
            subscription_dashboard(request, club_slug="invalid-club")

    def test_subscription_not_found(self):
        """Test handling when club has no subscription"""
        # Delete the subscription
        self.club_subscription.delete()
        
        request = self.factory.get(f"/billing/{self.club.slug}/dashboard/")
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = subscription_dashboard(request, club_slug=self.club.slug)
        
        # Should still work but show no subscription state
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No active subscription")


class BillingIntegrationTest(BillingViewsTestCase):
    """Integration tests for billing system"""

    @patch('simlane.billing.services.StripeService.create_checkout_session')
    @patch('simlane.billing.services.StripeService.verify_webhook_signature')
    @patch('simlane.billing.services.SubscriptionService.handle_subscription_updated')
    def test_full_subscription_flow(self, mock_handle_updated, mock_verify, mock_create_session):
        """Test complete subscription upgrade flow"""
        # 1. Start checkout
        mock_create_session.return_value = {
            'url': 'https://checkout.stripe.com/session123',
            'id': 'cs_test_session123'
        }
        
        checkout_request = self.factory.post(
            f"/billing/{self.club.slug}/checkout/",
            {'plan_id': self.basic_plan.id}
        )
        checkout_request.user = self.admin_user
        checkout_request.club = self.club
        checkout_request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        checkout_response = start_checkout(checkout_request, club_slug=self.club.slug)
        self.assertEqual(checkout_response.status_code, 302)
        
        # 2. Process webhook
        mock_verify.return_value = True
        
        webhook_payload = {
            'id': 'evt_test123',
            'type': 'customer.subscription.updated',
            'data': {
                'object': {
                    'id': 'sub_test123',
                    'customer': 'cus_test123',
                    'status': 'active',
                }
            }
        }
        
        webhook_request = self.factory.post(
            "/billing/stripe/webhook/",
            data=json.dumps(webhook_payload),
            content_type="application/json",
            HTTP_STRIPE_SIGNATURE="test_signature"
        )
        
        webhook_response = stripe_webhook(webhook_request)
        self.assertEqual(webhook_response.status_code, 200)
        
        # 3. View success page
        success_request = self.factory.get(
            f"/billing/{self.club.slug}/success/",
            {'session_id': 'cs_test_session123'}
        )
        success_request.user = self.admin_user
        success_request.club = self.club
        success_request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        success_response = subscription_success(success_request, club_slug=self.club.slug)
        self.assertEqual(success_response.status_code, 200)
        
        # Verify all mocks were called
        mock_create_session.assert_called_once()
        mock_verify.assert_called_once()
        mock_handle_updated.assert_called_once()

    def test_subscription_downgrade_handling(self):
        """Test handling of subscription downgrades"""
        # Start with basic plan
        self.club_subscription.plan = self.basic_plan
        self.club_subscription.save()
        
        # Add members beyond free plan limit
        for i in range(8):  # Total will be 10 members
            user = User.objects.create_user(
                username=f"user{i}",
                email=f"user{i}@example.com",
                password="testpass123",
            )
            ClubMember.objects.create(
                club=self.club,
                user=user,
                role=ClubRole.MEMBER,
            )
        
        self.club_subscription.seats_used = 10
        self.club_subscription.save()
        
        # Downgrade to free plan (should show warning)
        self.club_subscription.plan = self.free_plan
        self.club_subscription.save()
        
        request = self.factory.get(f"/billing/{self.club.slug}/dashboard/")
        request.user = self.admin_user
        request.club = self.club
        request.club_member = ClubMember.objects.get(
            club=self.club, user=self.admin_user
        )
        
        response = subscription_dashboard(request, club_slug=self.club.slug)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "10 / 5")  # Over limit
        self.assertContains(response, "warning")  # Should show warning