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
from simlane.teams.models import EventSignup
from simlane.teams.models import StintAssignment
from simlane.teams.models import Team
from simlane.teams.models import TeamAllocation
from simlane.teams.models import TeamAllocationMember
from simlane.teams.models import TeamEventStrategy
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


class EventSignupModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="organizer",
            email="organizer@example.com",
            password="password123",
        )
        self.club = Club.objects.create(
            name="Racing Club",
            created_by=self.user,
        )

        # Create simulator and track
        self.simulator = Simulator.objects.create(
            name="Test Simulator",
            version="1.0",
        )
        self.track = Track.objects.create(
            name="Test Track",
            country="Test Country",
        )

        # Create event
        self.event = Event.objects.create(
            name="Test Race",
            simulator=self.simulator,
            track=self.track,
            start_time=timezone.now() + timedelta(days=7),
            duration_minutes=120,
        )

    def test_event_signup_creation(self):
        """Test event signup sheet creation"""
        signup = EventSignup.objects.create(
            event=self.event,
            club=self.club,
            created_by=self.user,
            title="Test Race Signup",
            signup_deadline=timezone.now() + timedelta(days=3),
            max_participants=20,
        )

        self.assertEqual(signup.title, "Test Race Signup")
        self.assertEqual(signup.event, self.event)
        self.assertEqual(signup.club, self.club)
        self.assertTrue(signup.is_active)

    def test_signup_deadline_validation(self):
        """Test signup deadline must be before event start"""
        past_deadline = timezone.now() - timedelta(days=1)

        with self.assertRaises(ValidationError):
            signup = EventSignup(
                event=self.event,
                club=self.club,
                created_by=self.user,
                title="Invalid Signup",
                signup_deadline=past_deadline,
                max_participants=20,
            )
            signup.full_clean()


class TeamAllocationModelTest(TestCase):
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
        self.team = Team.objects.create(
            name="Team A",
            club=self.club,
        )

        # Create event and signup
        self.simulator = Simulator.objects.create(name="Test Sim", version="1.0")
        self.track = Track.objects.create(name="Test Track", country="Test")
        self.event = Event.objects.create(
            name="Test Event",
            simulator=self.simulator,
            track=self.track,
            start_time=timezone.now() + timedelta(days=7),
            duration_minutes=120,
        )
        self.signup = EventSignup.objects.create(
            event=self.event,
            club=self.club,
            created_by=self.user,
            title="Test Signup",
            signup_deadline=timezone.now() + timedelta(days=3),
        )

    def test_team_allocation_creation(self):
        """Test team allocation creation"""
        allocation = TeamAllocation.objects.create(
            event_signup=self.signup,
            team=self.team,
            created_by=self.user,
        )

        self.assertEqual(allocation.event_signup, self.signup)
        self.assertEqual(allocation.team, self.team)
        self.assertEqual(allocation.created_by, self.user)

    def test_team_allocation_member_assignment(self):
        """Test assigning members to team allocation"""
        member_user = User.objects.create_user(
            username="member",
            email="member@example.com",
            password="password123",
        )

        allocation = TeamAllocation.objects.create(
            event_signup=self.signup,
            team=self.team,
            created_by=self.user,
        )

        allocation_member = TeamAllocationMember.objects.create(
            team_allocation=allocation,
            user=member_user,
            role="DRIVER",
        )

        self.assertEqual(allocation_member.team_allocation, allocation)
        self.assertEqual(allocation_member.user, member_user)
        self.assertEqual(allocation_member.role, "DRIVER")


class StintAssignmentModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="driver",
            email="driver@example.com",
            password="password123",
        )
        self.club = Club.objects.create(
            name="Test Club",
            created_by=self.user,
        )
        self.team = Team.objects.create(
            name="Test Team",
            club=self.club,
        )

        # Create event components
        self.simulator = Simulator.objects.create(name="Test Sim", version="1.0")
        self.track = Track.objects.create(name="Test Track", country="Test")
        self.event = Event.objects.create(
            name="Test Event",
            simulator=self.simulator,
            track=self.track,
            start_time=timezone.now() + timedelta(days=7),
            duration_minutes=180,
        )
        self.event_instance = EventInstance.objects.create(
            event=self.event,
            session_type="RACE",
            start_time=self.event.start_time,
            duration_minutes=180,
        )

        # Create signup and allocation
        self.signup = EventSignup.objects.create(
            event=self.event,
            club=self.club,
            created_by=self.user,
            title="Test Signup",
            signup_deadline=timezone.now() + timedelta(days=3),
        )
        self.allocation = TeamAllocation.objects.create(
            event_signup=self.signup,
            team=self.team,
            created_by=self.user,
        )

        # Create strategy
        self.strategy = TeamEventStrategy.objects.create(
            team_allocation=self.allocation,
            event_instance=self.event_instance,
            strategy_name="Default Strategy",
        )

    def test_stint_assignment_creation(self):
        """Test creating a stint assignment"""
        stint = StintAssignment.objects.create(
            team_strategy=self.strategy,
            driver=self.user,
            start_minute=0,
            duration_minutes=60,
            fuel_load=50.0,
            tire_compound="MEDIUM",
        )

        self.assertEqual(stint.team_strategy, self.strategy)
        self.assertEqual(stint.driver, self.user)
        self.assertEqual(stint.start_minute, 0)
        self.assertEqual(stint.duration_minutes, 60)
        self.assertEqual(stint.fuel_load, 50.0)
        self.assertEqual(stint.tire_compound, "MEDIUM")

    def test_stint_overlap_validation(self):
        """Test stint time overlap validation"""
        # Create first stint
        StintAssignment.objects.create(
            team_strategy=self.strategy,
            driver=self.user,
            start_minute=0,
            duration_minutes=60,
            fuel_load=50.0,
        )

        # Try to create overlapping stint
        with self.assertRaises(ValidationError):
            overlapping_stint = StintAssignment(
                team_strategy=self.strategy,
                driver=self.user,
                start_minute=30,  # Overlaps with first stint
                duration_minutes=60,
                fuel_load=50.0,
            )
            overlapping_stint.full_clean()

    def test_stint_end_time_calculation(self):
        """Test stint end time calculation property"""
        stint = StintAssignment.objects.create(
            team_strategy=self.strategy,
            driver=self.user,
            start_minute=30,
            duration_minutes=90,
            fuel_load=50.0,
        )

        self.assertEqual(stint.end_minute, 120)  # 30 + 90


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
