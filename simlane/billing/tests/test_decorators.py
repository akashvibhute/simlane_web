"""
Tests for billing subscription decorators
"""

import uuid
from datetime import timedelta
from unittest.mock import Mock, patch

from django.contrib.auth.models import AnonymousUser
from django.http import HttpRequest, HttpResponseForbidden, HttpResponseRedirect
from django.test import TestCase, RequestFactory
from django.urls import reverse
from django.utils import timezone
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.backends.db import SessionStore

from simlane.billing.decorators import (
    subscription_required,
    race_planning_required,
    member_limit_enforced,
    subscription_admin_required,
    feature_enabled,
    api_subscription_required,
    check_member_limit,
)
from simlane.billing.models import SubscriptionPlan, ClubSubscription, BillingEventLog
from simlane.teams.models import Club, ClubMember, ClubRole
from simlane.users.models import User


class SubscriptionDecoratorsTestCase(TestCase):
    """Base test case with common setup for subscription decorator tests"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        
        # Create test users
        self.admin_user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="testpass123"
        )
        self.member_user = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="testpass123"
        )
        self.non_member_user = User.objects.create_user(
            username="nonmember",
            email="nonmember@example.com",
            password="testpass123"
        )
        
        # Create test club
        self.club = Club.objects.create(
            name="Test Racing Club",
            slug="test-racing-club",
            created_by=self.admin_user
        )
        
        # Create club memberships
        self.admin_member = ClubMember.objects.create(
            user=self.admin_user,
            club=self.club,
            role=ClubRole.ADMIN
        )
        self.regular_member = ClubMember.objects.create(
            user=self.member_user,
            club=self.club,
            role=ClubRole.MEMBER
        )
        
        # Create subscription plans
        self.free_plan = SubscriptionPlan.objects.create(
            name="Free",
            slug="free",
            max_members=5,
            monthly_price=0,
            features_json={
                "basic_club_management": True,
                "member_management": True,
                "race_planning": False,
                "advanced_analytics": False
            },
            is_default=True
        )
        
        self.basic_plan = SubscriptionPlan.objects.create(
            name="Basic",
            slug="basic",
            max_members=25,
            monthly_price=19.99,
            features_json={
                "basic_club_management": True,
                "member_management": True,
                "race_planning": True,
                "advanced_analytics": False
            }
        )
        
        self.pro_plan = SubscriptionPlan.objects.create(
            name="Pro",
            slug="pro",
            max_members=-1,  # Unlimited
            monthly_price=49.99,
            features_json={
                "basic_club_management": True,
                "member_management": True,
                "race_planning": True,
                "advanced_analytics": True,
                "priority_support": True
            }
        )
        
        # Create active subscription for the club
        self.club_subscription = ClubSubscription.objects.create(
            club=self.club,
            plan=self.free_plan,
            status=ClubSubscription.SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timedelta(days=30)
        )

    def create_request(self, user=None, method='GET', path='/', club=None):
        """Helper to create a request with proper setup"""
        request = self.factory.get(path) if method == 'GET' else self.factory.post(path)
        request.user = user or AnonymousUser()
        
        # Add session and messages
        request.session = SessionStore()
        request._messages = FallbackStorage(request)
        
        # Add club context if provided
        if club:
            request.club = club
            # Add club member if user is a member
            if user and not isinstance(user, AnonymousUser):
                try:
                    request.club_member = ClubMember.objects.get(user=user, club=club)
                except ClubMember.DoesNotExist:
                    pass
        
        return request

    def create_mock_view(self, return_value="success"):
        """Create a mock view function for testing decorators"""
        def mock_view(request, *args, **kwargs):
            return return_value
        return mock_view


class SubscriptionRequiredDecoratorTest(SubscriptionDecoratorsTestCase):
    """Test the @subscription_required decorator"""

    def test_subscription_required_with_active_subscription(self):
        """Test decorator allows access with active subscription"""
        @subscription_required()
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        self.assertEqual(response, "success")
        self.assertTrue(hasattr(request, 'club_subscription'))
        self.assertEqual(request.club_subscription, self.club_subscription)

    def test_subscription_required_without_club_context(self):
        """Test decorator blocks access without club context"""
        @subscription_required()
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user)
        response = test_view(request)
        
        self.assertIsInstance(response, HttpResponseForbidden)

    def test_subscription_required_without_subscription(self):
        """Test decorator redirects when no active subscription"""
        # Delete the subscription
        self.club_subscription.delete()
        
        @subscription_required()
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertIn('upgrade_required', response.url)

    def test_subscription_required_with_expired_subscription(self):
        """Test decorator blocks access with expired subscription"""
        self.club_subscription.status = ClubSubscription.SubscriptionStatus.CANCELED
        self.club_subscription.save()
        
        @subscription_required()
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        self.assertIsInstance(response, HttpResponseRedirect)

    def test_subscription_required_with_specific_features(self):
        """Test decorator checks for specific features"""
        @subscription_required(features=['race_planning'])
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        # Should redirect because free plan doesn't have race_planning
        self.assertIsInstance(response, HttpResponseRedirect)

    def test_subscription_required_with_available_features(self):
        """Test decorator allows access when features are available"""
        # Upgrade to basic plan with race planning
        self.club_subscription.plan = self.basic_plan
        self.club_subscription.save()
        
        @subscription_required(features=['race_planning'])
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        self.assertEqual(response, "success")

    def test_subscription_required_no_redirect_mode(self):
        """Test decorator returns forbidden instead of redirect"""
        @subscription_required(redirect_to_upgrade=False)
        def test_view(request):
            return "success"
        
        # Delete subscription
        self.club_subscription.delete()
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        self.assertIsInstance(response, HttpResponseForbidden)

    def test_subscription_required_with_trialing_subscription(self):
        """Test decorator allows access with trialing subscription"""
        self.club_subscription.status = ClubSubscription.SubscriptionStatus.TRIALING
        self.club_subscription.save()
        
        @subscription_required()
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        self.assertEqual(response, "success")


class RacePlanningRequiredDecoratorTest(SubscriptionDecoratorsTestCase):
    """Test the @race_planning_required decorator"""

    def test_race_planning_required_with_basic_plan(self):
        """Test decorator allows access with race planning feature"""
        # Upgrade to basic plan
        self.club_subscription.plan = self.basic_plan
        self.club_subscription.save()
        
        @race_planning_required
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.member_user, club=self.club)
        response = test_view(request)
        
        self.assertEqual(response, "success")

    def test_race_planning_required_with_free_plan(self):
        """Test decorator blocks access without race planning feature"""
        @race_planning_required
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.member_user, club=self.club)
        response = test_view(request)
        
        self.assertIsInstance(response, HttpResponseRedirect)

    def test_race_planning_required_non_member(self):
        """Test decorator blocks access for non-members"""
        @race_planning_required
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.non_member_user, club=self.club)
        response = test_view(request)
        
        self.assertIsInstance(response, HttpResponseForbidden)

    def test_race_planning_required_anonymous_user(self):
        """Test decorator redirects anonymous users to login"""
        @race_planning_required
        def test_view(request):
            return "success"
        
        request = self.create_request(club=self.club)
        response = test_view(request)
        
        # Should redirect to login (from @login_required)
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertIn('login', response.url)


class MemberLimitEnforcedDecoratorTest(SubscriptionDecoratorsTestCase):
    """Test the @member_limit_enforced decorator"""

    def test_member_limit_enforced_within_limit(self):
        """Test decorator allows access when within member limits"""
        @member_limit_enforced
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        self.assertEqual(response, "success")
        self.assertTrue(hasattr(request, 'member_limit_info'))
        self.assertEqual(request.member_limit_info['max_members'], 5)
        self.assertEqual(request.member_limit_info['current_members'], 2)  # admin + member

    def test_member_limit_enforced_at_limit(self):
        """Test decorator blocks access when at member limit"""
        # Add more members to reach the limit
        for i in range(3):  # We already have 2, so this makes 5 total
            user = User.objects.create_user(
                username=f"user{i}",
                email=f"user{i}@example.com",
                password="testpass123"
            )
            ClubMember.objects.create(
                user=user,
                club=self.club,
                role=ClubRole.MEMBER
            )
        
        @member_limit_enforced
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        self.assertIsInstance(response, HttpResponseRedirect)
        self.assertIn('upgrade_required', response.url)

    def test_member_limit_enforced_unlimited_plan(self):
        """Test decorator allows access with unlimited plan"""
        # Upgrade to pro plan (unlimited members)
        self.club_subscription.plan = self.pro_plan
        self.club_subscription.save()
        
        @member_limit_enforced
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        self.assertEqual(response, "success")

    def test_member_limit_enforced_no_subscription(self):
        """Test decorator uses free plan limits when no subscription"""
        self.club_subscription.delete()
        
        @member_limit_enforced
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        self.assertEqual(response, "success")

    def test_member_limit_enforced_non_admin(self):
        """Test decorator blocks access for non-admin users"""
        @member_limit_enforced
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.member_user, club=self.club)
        response = test_view(request)
        
        self.assertIsInstance(response, HttpResponseForbidden)


class SubscriptionAdminRequiredDecoratorTest(SubscriptionDecoratorsTestCase):
    """Test the @subscription_admin_required decorator"""

    def test_subscription_admin_required_with_admin(self):
        """Test decorator allows access for club admin"""
        @subscription_admin_required
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        self.assertEqual(response, "success")
        self.assertTrue(hasattr(request, 'club_subscription'))

    def test_subscription_admin_required_creates_free_subscription(self):
        """Test decorator creates free subscription if none exists"""
        self.club_subscription.delete()
        
        @subscription_admin_required
        def test_view(request):
            return "success"
        
        with patch('simlane.billing.services.SubscriptionService') as mock_service:
            mock_service.return_value.assign_free_plan.return_value = Mock()
            
            request = self.create_request(user=self.admin_user, club=self.club)
            response = test_view(request)
            
            self.assertEqual(response, "success")
            mock_service.return_value.assign_free_plan.assert_called_once_with(self.club)

    def test_subscription_admin_required_non_admin(self):
        """Test decorator blocks access for non-admin users"""
        @subscription_admin_required
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.member_user, club=self.club)
        response = test_view(request)
        
        self.assertIsInstance(response, HttpResponseForbidden)


class FeatureEnabledDecoratorTest(SubscriptionDecoratorsTestCase):
    """Test the @feature_enabled decorator"""

    def test_feature_enabled_with_available_feature(self):
        """Test decorator sets feature_available=True for available features"""
        @feature_enabled('member_management')
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.member_user, club=self.club)
        response = test_view(request)
        
        self.assertEqual(response, "success")
        self.assertTrue(request.feature_available)
        self.assertFalse(request.feature_upgrade_required)

    def test_feature_enabled_with_unavailable_feature(self):
        """Test decorator sets feature_available=False for unavailable features"""
        @feature_enabled('race_planning')
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.member_user, club=self.club)
        response = test_view(request)
        
        self.assertEqual(response, "success")
        self.assertFalse(request.feature_available)
        self.assertTrue(request.feature_upgrade_required)

    def test_feature_enabled_no_subscription(self):
        """Test decorator handles missing subscription gracefully"""
        self.club_subscription.delete()
        
        @feature_enabled('race_planning')
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.member_user, club=self.club)
        response = test_view(request)
        
        self.assertEqual(response, "success")
        self.assertFalse(request.feature_available)
        self.assertTrue(request.feature_upgrade_required)

    def test_feature_enabled_non_member(self):
        """Test decorator blocks access for non-members"""
        @feature_enabled('member_management')
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.non_member_user, club=self.club)
        response = test_view(request)
        
        self.assertIsInstance(response, HttpResponseForbidden)


class ApiSubscriptionRequiredDecoratorTest(SubscriptionDecoratorsTestCase):
    """Test the @api_subscription_required decorator"""

    def test_api_subscription_required_with_active_subscription(self):
        """Test decorator allows API access with active subscription"""
        @api_subscription_required()
        def test_api_view(request):
            return {"status": "success"}
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_api_view(request)
        
        self.assertEqual(response, {"status": "success"})

    def test_api_subscription_required_without_subscription(self):
        """Test decorator returns JSON error without subscription"""
        self.club_subscription.delete()
        
        @api_subscription_required()
        def test_api_view(request):
            return {"status": "success"}
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_api_view(request)
        
        self.assertEqual(response.status_code, 402)
        response_data = response.json()
        self.assertEqual(response_data['error_code'], 'SUBSCRIPTION_REQUIRED')

    def test_api_subscription_required_missing_features(self):
        """Test decorator returns JSON error for missing features"""
        @api_subscription_required(features=['race_planning'])
        def test_api_view(request):
            return {"status": "success"}
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_api_view(request)
        
        self.assertEqual(response.status_code, 402)
        response_data = response.json()
        self.assertEqual(response_data['error_code'], 'FEATURE_NOT_AVAILABLE')
        self.assertIn('race_planning', response_data['missing_features'])

    def test_api_subscription_required_without_club_context(self):
        """Test decorator returns error without club context"""
        @api_subscription_required()
        def test_api_view(request):
            return {"status": "success"}
        
        request = self.create_request(user=self.admin_user)
        response = test_api_view(request)
        
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertEqual(response_data['error'], 'Club context required')


class CheckMemberLimitUtilityTest(SubscriptionDecoratorsTestCase):
    """Test the check_member_limit utility function"""

    def test_check_member_limit_within_limit(self):
        """Test utility returns True when within limits"""
        can_add, message, current, limit = check_member_limit(self.club, 1)
        
        self.assertTrue(can_add)
        self.assertEqual(current, 2)  # admin + member
        self.assertEqual(limit, 5)
        self.assertIn("Can add", message)

    def test_check_member_limit_at_limit(self):
        """Test utility returns False when at limit"""
        # Add members to reach limit
        for i in range(3):
            user = User.objects.create_user(
                username=f"user{i}",
                email=f"user{i}@example.com",
                password="testpass123"
            )
            ClubMember.objects.create(
                user=user,
                club=self.club,
                role=ClubRole.MEMBER
            )
        
        can_add, message, current, limit = check_member_limit(self.club, 1)
        
        self.assertFalse(can_add)
        self.assertEqual(current, 5)
        self.assertEqual(limit, 5)
        self.assertIn("exceed", message)

    def test_check_member_limit_unlimited_plan(self):
        """Test utility handles unlimited plans"""
        self.club_subscription.plan = self.pro_plan
        self.club_subscription.save()
        
        can_add, message, current, limit = check_member_limit(self.club, 10)
        
        self.assertTrue(can_add)
        self.assertEqual(limit, -1)
        self.assertIn("No member limit", message)

    def test_check_member_limit_multiple_members(self):
        """Test utility with adding multiple members"""
        can_add, message, current, limit = check_member_limit(self.club, 4)
        
        self.assertFalse(can_add)  # 2 + 4 = 6, exceeds limit of 5
        self.assertIn("Adding 4 member(s) would exceed", message)

    def test_check_member_limit_no_subscription(self):
        """Test utility uses default limits without subscription"""
        self.club_subscription.delete()
        
        can_add, message, current, limit = check_member_limit(self.club, 1)
        
        self.assertTrue(can_add)
        self.assertEqual(limit, 5)  # Default free limit


class DecoratorIntegrationTest(SubscriptionDecoratorsTestCase):
    """Test integration between subscription decorators and existing club decorators"""

    def test_club_admin_required_with_subscription_check(self):
        """Test that club_admin_required includes subscription validation"""
        from simlane.teams.decorators import club_admin_required
        
        @club_admin_required
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user)
        request.club = self.club
        response = test_view(request)
        
        self.assertEqual(response, "success")
        self.assertTrue(hasattr(request, 'club_subscription'))

    def test_club_admin_required_without_subscription(self):
        """Test that club_admin_required blocks access without subscription"""
        from simlane.teams.decorators import club_admin_required
        
        self.club_subscription.delete()
        
        @club_admin_required
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user)
        request.club = self.club
        response = test_view(request)
        
        self.assertIsInstance(response, HttpResponseForbidden)

    def test_stacked_decorators(self):
        """Test multiple decorators working together"""
        from simlane.teams.decorators import club_member_required
        
        # Upgrade to basic plan for race planning
        self.club_subscription.plan = self.basic_plan
        self.club_subscription.save()
        
        @club_member_required
        @subscription_required(features=['race_planning'])
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.member_user)
        request.club = self.club
        response = test_view(request)
        
        self.assertEqual(response, "success")

    def test_decorator_order_matters(self):
        """Test that decorator order affects behavior"""
        # Test with subscription check first
        @subscription_required(features=['race_planning'])
        @race_planning_required
        def test_view1(request):
            return "success"
        
        # Test with race planning check first
        @race_planning_required
        @subscription_required(features=['race_planning'])
        def test_view2(request):
            return "success"
        
        request = self.create_request(user=self.member_user, club=self.club)
        
        # Both should fail with free plan
        response1 = test_view1(request)
        response2 = test_view2(request)
        
        self.assertIsInstance(response1, HttpResponseRedirect)
        self.assertIsInstance(response2, HttpResponseRedirect)


class DecoratorErrorHandlingTest(SubscriptionDecoratorsTestCase):
    """Test error handling and edge cases in decorators"""

    def test_decorator_with_invalid_club(self):
        """Test decorator behavior with invalid club context"""
        @subscription_required()
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user)
        request.club = None
        response = test_view(request)
        
        self.assertIsInstance(response, HttpResponseForbidden)

    def test_decorator_with_deleted_subscription_plan(self):
        """Test decorator behavior when subscription plan is deleted"""
        plan_id = self.club_subscription.plan.id
        self.club_subscription.plan.delete()
        
        @subscription_required()
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        
        # Should handle gracefully (subscription becomes invalid)
        with self.assertRaises(Exception):
            test_view(request)

    def test_decorator_with_corrupted_features_json(self):
        """Test decorator behavior with corrupted features JSON"""
        # This would be handled by the model's has_feature method
        self.free_plan.features_json = None
        self.free_plan.save()
        
        @subscription_required(features=['race_planning'])
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        # Should redirect due to missing feature
        self.assertIsInstance(response, HttpResponseRedirect)

    def test_decorator_preserves_view_metadata(self):
        """Test that decorators preserve original view function metadata"""
        @subscription_required()
        def test_view(request):
            """Test view docstring"""
            return "success"
        
        self.assertEqual(test_view.__name__, 'test_view')
        self.assertEqual(test_view.__doc__, 'Test view docstring')

    def test_decorator_with_view_exceptions(self):
        """Test decorator behavior when decorated view raises exceptions"""
        @subscription_required()
        def test_view(request):
            raise ValueError("Test exception")
        
        request = self.create_request(user=self.admin_user, club=self.club)
        
        with self.assertRaises(ValueError):
            test_view(request)


class DecoratorMessagesTest(SubscriptionDecoratorsTestCase):
    """Test that decorators properly set Django messages"""

    def test_subscription_required_sets_error_message(self):
        """Test that subscription_required sets appropriate error messages"""
        self.club_subscription.delete()
        
        @subscription_required()
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        messages = list(get_messages(request))
        self.assertTrue(any("active subscription" in str(m) for m in messages))

    def test_member_limit_enforced_sets_error_message(self):
        """Test that member_limit_enforced sets appropriate error messages"""
        # Fill up to limit
        for i in range(3):
            user = User.objects.create_user(
                username=f"user{i}",
                email=f"user{i}@example.com",
                password="testpass123"
            )
            ClubMember.objects.create(
                user=user,
                club=self.club,
                role=ClubRole.MEMBER
            )
        
        @member_limit_enforced
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        messages = list(get_messages(request))
        self.assertTrue(any("plan allows up to" in str(m) for m in messages))

    def test_feature_specific_error_messages(self):
        """Test that feature-specific decorators set appropriate messages"""
        @subscription_required(features=['race_planning', 'advanced_analytics'])
        def test_view(request):
            return "success"
        
        request = self.create_request(user=self.admin_user, club=self.club)
        response = test_view(request)
        
        messages = list(get_messages(request))
        message_text = ' '.join(str(m) for m in messages)
        self.assertIn("race_planning", message_text)
        self.assertIn("advanced_analytics", message_text)