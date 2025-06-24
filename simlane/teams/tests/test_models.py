"""
Tests for teams app models
"""

from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from simlane.sim.models import Event
from simlane.sim.models import EventInstance
from simlane.sim.models import Simulator
from simlane.sim.models import Track
from simlane.teams.models import Club
from simlane.teams.models import ClubInvitation
from simlane.teams.models import ClubMember
from simlane.teams.models import Team
# Removed imports: EventSignup, StintAssignment, TeamAllocation, TeamAllocationMember, TeamEventStrategy
# These models have been removed in favor of enhanced participation system
from simlane.users.models import User


class ClubModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass123",
        )

    def test_club_creation(self):
        """Test club creation and automatic admin assignment"""
        club = Club.objects.create(
            name="Test Racing Club",
            description="A test club for racing",
            created_by=self.user,
        )

        self.assertEqual(club.name, "Test Racing Club")
        self.assertEqual(club.created_by, self.user)

        # Check if creator automatically becomes admin
        admin_member = ClubMember.objects.filter(
            club=club,
            user=self.user,
            role="ADMIN",
        ).first()
        self.assertIsNotNone(admin_member)

    def test_club_str_representation(self):
        """Test club string representation"""
        club = Club.objects.create(
            name="Test Club",
            created_by=self.user,
        )
        self.assertEqual(str(club), "Test Club")

    def test_club_unique_name(self):
        """Test club name uniqueness"""
        Club.objects.create(name="Unique Club", created_by=self.user)

        with self.assertRaises(ValidationError):
            duplicate_club = Club(name="Unique Club", created_by=self.user)
            duplicate_club.full_clean()


class ClubInvitationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="admin",
            email="admin@example.com",
            password="password123",
        )
        self.club = Club.objects.create(
            name="Test Club",
            created_by=self.user,
        )

    def test_invitation_creation(self):
        """Test invitation creation with token generation"""
        invitation = ClubInvitation.objects.create(
            club=self.club,
            inviter=self.user,
            invitee_email="newmember@example.com",
            role="MEMBER",
        )

        self.assertIsNotNone(invitation.token)
        self.assertEqual(invitation.status, "PENDING")
        self.assertTrue(invitation.expires_at > timezone.now())

    def test_invitation_expiry(self):
        """Test invitation expiry check"""
        past_time = timezone.now() - timedelta(days=1)

        invitation = ClubInvitation.objects.create(
            club=self.club,
            inviter=self.user,
            invitee_email="expired@example.com",
            role="MEMBER",
            expires_at=past_time,
        )

        self.assertTrue(invitation.is_expired())

    def test_invitation_acceptance(self):
        """Test invitation acceptance process"""
        invitee = User.objects.create_user(
            username="invitee",
            email="invitee@example.com",
            password="password123",
        )

        invitation = ClubInvitation.objects.create(
            club=self.club,
            inviter=self.user,
            invitee_email="invitee@example.com",
            role="MEMBER",
        )

        # Accept invitation
        result = invitation.accept(invitee)

        self.assertTrue(result)
        self.assertEqual(invitation.status, "ACCEPTED")

        # Check if club member was created
        member = ClubMember.objects.filter(
            club=self.club,
            user=invitee,
            role="MEMBER",
        ).first()
        self.assertIsNotNone(member)

    def test_invitation_decline(self):
        """Test invitation decline process"""
        invitation = ClubInvitation.objects.create(
            club=self.club,
            inviter=self.user,
            invitee_email="decline@example.com",
            role="MEMBER",
        )

        invitation.decline()

        self.assertEqual(invitation.status, "DECLINED")


# Legacy model tests removed - EventSignup, TeamAllocation, StintAssignment models no longer exist
# Tests for enhanced participation system (EventParticipation, AvailabilityWindow) should be added here


class ModelValidationTest(TestCase):
    """Test model validation rules"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
        )

    def test_club_name_length_validation(self):
        """Test club name length limits"""
        # Test maximum length
        long_name = "A" * 201  # Assuming max length is 200

        with self.assertRaises(ValidationError):
            club = Club(name=long_name, created_by=self.user)
            club.full_clean()

    def test_invitation_email_validation(self):
        """Test invitation email format validation"""
        club = Club.objects.create(name="Test Club", created_by=self.user)

        with self.assertRaises(ValidationError):
            invitation = ClubInvitation(
                club=club,
                inviter=self.user,
                invitee_email="invalid-email",  # Invalid email format
                role="MEMBER",
            )
            invitation.full_clean()

    def test_fuel_load_validation(self):
        """Test fuel load positive value validation"""
        # Setup required objects
        club = Club.objects.create(name="Test Club", created_by=self.user)
        team = Team.objects.create(name="Test Team", club=club)

        simulator = Simulator.objects.create(name="Test Sim", version="1.0")
        track = Track.objects.create(name="Test Track", country="Test")
        event = Event.objects.create(
            name="Test Event",
            simulator=simulator,
            track=track,
            start_time=timezone.now() + timedelta(days=7),
            duration_minutes=180,
        )
        event_instance = EventInstance.objects.create(
            event=event,
            session_type="RACE",
            start_time=event.start_time,
            duration_minutes=180,
        )

        signup = EventSignup.objects.create(
            event=event,
            club=club,
            created_by=self.user,
            title="Test Signup",
            signup_deadline=timezone.now() + timedelta(days=3),
        )
        allocation = TeamAllocation.objects.create(
            event_signup=signup,
            team=team,
            created_by=self.user,
        )
        strategy = TeamEventStrategy.objects.create(
            team_allocation=allocation,
            event_instance=event_instance,
            strategy_name="Test Strategy",
        )

        # Test negative fuel load
        with self.assertRaises(ValidationError):
            stint = StintAssignment(
                team_strategy=strategy,
                driver=self.user,
                start_minute=0,
                duration_minutes=60,
                fuel_load=-10.0,  # Negative fuel load
            )
            stint.full_clean()


class ModelSignalTest(TestCase):
    """Test model signals and automatic behaviors"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
        )

    @patch("simlane.teams.models.ClubMember.objects.create")
    def test_club_creation_creates_admin_member(self, mock_create):
        """Test that creating a club automatically creates admin membership"""
        club = Club.objects.create(
            name="Test Club",
            created_by=self.user,
        )

        # Should create a ClubMember with ADMIN role
        mock_create.assert_called_once_with(
            club=club,
            user=self.user,
            role="ADMIN",
        )

    def test_invitation_token_uniqueness(self):
        """Test that invitation tokens are unique"""
        club = Club.objects.create(name="Test Club", created_by=self.user)

        invitation1 = ClubInvitation.objects.create(
            club=club,
            inviter=self.user,
            invitee_email="user1@example.com",
            role="MEMBER",
        )

        invitation2 = ClubInvitation.objects.create(
            club=club,
            inviter=self.user,
            invitee_email="user2@example.com",
            role="MEMBER",
        )

        self.assertNotEqual(invitation1.token, invitation2.token)
