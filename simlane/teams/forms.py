import secrets
from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import formset_factory
from django.utils import timezone

from simlane.sim.models import Event
from simlane.sim.models import SimCar

from .models import Club
from .models import ClubEvent
from .models import ClubInvitation
from .models import ClubMember
from .models import ClubRole
from .models import EventSignup
from .models import EventSignupAvailability
from .models import Team
from .models import TeamAllocation
from .models import TeamAllocationMember

User = get_user_model()


class ClubCreateForm(forms.ModelForm):
    """Form for creating new clubs"""

    class Meta:
        model = Club
        fields = ["name", "description", "logo_url", "website", "social_links"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Enter club name",
                    "required": True,
                },
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Describe your club...",
                },
            ),
            "logo_url": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://example.com/logo.png",
                },
            ),
            "website": forms.URLInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "https://example.com",
                },
            ),
            "social_links": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": '{"discord": "https://discord.gg/...", "twitter": "https://twitter.com/..."}',
                },
            ),
        }
        help_texts = {
            "name": "Choose a unique name for your club",
            "description": "Tell potential members what your club is about",
            "logo_url": "URL to your club logo image",
            "website": "Your club website (optional)",
            "social_links": "JSON format for social media links (optional)",
        }

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if Club.objects.filter(name__iexact=name).exists():
            raise ValidationError("A club with this name already exists.")
        return name

    def clean_social_links(self):
        social_links = self.cleaned_data.get("social_links")
        if social_links:
            try:
                import json

                # Try to parse as JSON to validate format
                if isinstance(social_links, str):
                    json.loads(social_links)
            except (json.JSONDecodeError, TypeError):
                raise ValidationError("Social links must be valid JSON format")
        return social_links


class ClubUpdateForm(ClubCreateForm):
    """Form for updating club information"""

    class Meta(ClubCreateForm.Meta):
        pass

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.get("instance")
        super().__init__(*args, **kwargs)

        # Don't validate name uniqueness for the current club
        if self.instance:
            self.initial_name = self.instance.name

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if Club.objects.filter(name__iexact=name).exclude(pk=self.instance.pk).exists():
            raise ValidationError("A club with this name already exists.")
        return name


class ClubInvitationForm(forms.Form):
    """Form for inviting members to clubs"""

    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "placeholder": "member@example.com",
                "required": True,
            },
        ),
        help_text="Email address of the person you want to invite",
    )

    role = forms.ChoiceField(
        choices=ClubRole.choices,
        initial=ClubRole.MEMBER,
        widget=forms.Select(
            attrs={
                "class": "form-control",
            },
        ),
        help_text="Role the invited user will have in this club",
    )

    personal_message = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Add a personal message to your invitation (optional)...",
            },
        ),
        required=False,
        max_length=500,
        help_text="Optional message to include in the invitation email",
    )

    def __init__(self, *args, **kwargs):
        self.club = kwargs.pop("club")
        self.inviter = kwargs.pop("inviter")
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"]

        # Check if user is already a club member
        if ClubMember.objects.filter(club=self.club, user__email=email).exists():
            raise ValidationError("This user is already a member of the club.")

        # Check if there's already a pending invitation
        if ClubInvitation.objects.filter(
            club=self.club,
            email=email,
            accepted_at__isnull=True,
            declined_at__isnull=True,
            expires_at__gt=timezone.now(),
        ).exists():
            raise ValidationError(
                "There is already a pending invitation for this email.",
            )

        return email

    def clean_role(self):
        role = self.cleaned_data["role"]

        # Only club admins can invite other admins
        try:
            inviter_member = ClubMember.objects.get(club=self.club, user=self.inviter)
            if role == ClubRole.ADMIN and inviter_member.role != ClubRole.ADMIN:
                raise ValidationError("Only club admins can invite other admins.")
        except ClubMember.DoesNotExist:
            raise ValidationError("You must be a club member to send invitations.")

        return role

    def save(self):
        """Create and save the invitation"""
        invitation = ClubInvitation(
            club=self.club,
            email=self.cleaned_data["email"],
            invited_by=self.inviter,
            role=self.cleaned_data["role"],
            personal_message=self.cleaned_data.get("personal_message", ""),
            token=secrets.token_urlsafe(32),
            expires_at=timezone.now() + timedelta(days=7),
        )
        invitation.save()
        return invitation


class ClubEventCreateForm(forms.ModelForm):
    """Form for creating event signup sheets"""

    base_event = forms.ModelChoiceField(
        queryset=Event.objects.none(),
        widget=forms.Select(
            attrs={
                "class": "form-control select2",
                "data-placeholder": "Select an event",
            },
        ),
        help_text="Select the sim event for this signup",
    )

    signup_deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(
            attrs={
                "class": "form-control datetimepicker",
                "placeholder": "YYYY-MM-DD HH:MM",
            },
        ),
        help_text="Deadline for members to sign up",
    )

    class Meta:
        model = ClubEvent
        fields = [
            "base_event",
            "title",
            "description",
            "signup_deadline",
            "max_participants",
            "requires_team_assignment",
            "auto_assign_teams",
            "team_size_min",
            "team_size_max",
        ]
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Club event title",
                },
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Event description and rules...",
                },
            ),
            "max_participants": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                },
            ),
            "requires_team_assignment": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                },
            ),
            "auto_assign_teams": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                },
            ),
            "team_size_min": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "max": 10,
                },
            ),
            "team_size_max": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "max": 10,
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        self.club = kwargs.pop("club", None)
        super().__init__(*args, **kwargs)

        # Filter events to those accessible by the club
        if self.club:
            # For now, show all events. Later can filter by simulator, date, etc.
            self.fields["base_event"].queryset = Event.objects.filter(
                status__in=["SCHEDULED", "DRAFT"],
            ).order_by("-event_date")

    def clean(self):
        cleaned_data = super().clean()

        # Validate team sizes
        team_size_min = cleaned_data.get("team_size_min")
        team_size_max = cleaned_data.get("team_size_max")

        if team_size_min and team_size_max and team_size_min > team_size_max:
            raise ValidationError(
                "Minimum team size cannot be greater than maximum team size.",
            )

        # Validate signup deadline
        signup_deadline = cleaned_data.get("signup_deadline")
        base_event = cleaned_data.get("base_event")

        if signup_deadline and base_event and base_event.event_date:
            if signup_deadline > base_event.event_date:
                raise ValidationError("Signup deadline cannot be after the event date.")

        return cleaned_data


class EventSignupForm(forms.ModelForm):
    """Form for members to sign up for events"""

    preferred_cars = forms.ModelMultipleChoiceField(
        queryset=SimCar.objects.none(),
        widget=forms.CheckboxSelectMultiple(
            attrs={
                "class": "form-check-input",
            },
        ),
        required=False,
        help_text="Select your preferred cars (in order of preference)",
    )

    backup_cars = forms.ModelMultipleChoiceField(
        queryset=SimCar.objects.none(),
        widget=forms.CheckboxSelectMultiple(
            attrs={
                "class": "form-check-input",
            },
        ),
        required=False,
        help_text="Select backup car choices",
    )

    class Meta:
        model = EventSignup
        fields = [
            "can_drive",
            "can_spectate",
            "experience_level",
            "primary_sim_profile",
            "availability_notes",
            "max_stint_duration",
            "min_rest_duration",
            "notes",
        ]
        widgets = {
            "can_drive": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                },
            ),
            "can_spectate": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                },
            ),
            "experience_level": forms.Select(
                attrs={
                    "class": "form-control",
                },
            ),
            "primary_sim_profile": forms.Select(
                attrs={
                    "class": "form-control",
                },
            ),
            "availability_notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Any specific availability constraints...",
                },
            ),
            "max_stint_duration": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 10,
                    "max": 240,
                    "placeholder": "Minutes",
                },
            ),
            "min_rest_duration": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 10,
                    "max": 240,
                    "placeholder": "Minutes",
                },
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Additional notes or preferences...",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        self.club_event = kwargs.pop("club_event", None)
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)

        # Filter available cars based on event
        if self.club_event and self.club_event.base_event:
            event = self.club_event.base_event
            # Get cars allowed for this event
            available_cars = SimCar.objects.filter(
                simulator=event.simulator,
                is_active=True,
            )

            # Further filter by event classes if specified
            event_classes = event.classes.all()
            if event_classes:
                car_class_ids = event_classes.values_list("car_class_id", flat=True)
                available_cars = available_cars.filter(
                    car_model__car_class__in=car_class_ids,
                )

            self.fields["preferred_cars"].queryset = available_cars
            self.fields["backup_cars"].queryset = available_cars

        # Filter sim profiles for the user
        if self.user:
            self.fields["primary_sim_profile"].queryset = self.user.sim_profiles.all()

    def clean(self):
        cleaned_data = super().clean()

        # Ensure at least one role is selected
        can_drive = cleaned_data.get("can_drive")
        can_spectate = cleaned_data.get("can_spectate")

        if not can_drive and not can_spectate:
            raise ValidationError("You must be available to either drive or spectate.")

        # Validate car selections don't overlap
        preferred_cars = cleaned_data.get("preferred_cars", [])
        backup_cars = cleaned_data.get("backup_cars", [])

        overlap = set(preferred_cars) & set(backup_cars)
        if overlap:
            raise ValidationError(
                f"Cars cannot be in both preferred and backup lists: {', '.join(str(car) for car in overlap)}",
            )

        return cleaned_data


class EventSignupAvailabilityForm(forms.ModelForm):
    """Form for specifying availability for specific event instances"""

    class Meta:
        model = EventSignupAvailability
        fields = ["event_instance", "available", "preferred_stint_duration", "notes"]
        widgets = {
            "available": forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                },
            ),
            "preferred_stint_duration": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 10,
                    "max": 240,
                    "placeholder": "Minutes",
                },
            ),
            "notes": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Any notes for this time slot...",
                },
            ),
        }


# Formset for multiple event instance availabilities
EventSignupAvailabilityFormSet = formset_factory(
    EventSignupAvailabilityForm,
    extra=0,
    can_delete=False,
)


class TeamAllocationForm(forms.Form):
    """Form for admins to create team allocations"""

    team = forms.ModelChoiceField(
        queryset=Team.objects.none(),
        widget=forms.Select(
            attrs={
                "class": "form-control",
            },
        ),
        help_text="Select the team for this allocation",
    )

    assigned_sim_car = forms.ModelChoiceField(
        queryset=SimCar.objects.none(),
        widget=forms.Select(
            attrs={
                "class": "form-control",
            },
        ),
        help_text="Assign a car to this team",
    )

    selected_members = forms.ModelMultipleChoiceField(
        queryset=EventSignup.objects.none(),
        widget=forms.CheckboxSelectMultiple(
            attrs={
                "class": "form-check-input member-selector",
            },
        ),
        help_text="Select members for this team",
    )

    def __init__(self, *args, **kwargs):
        self.club_event = kwargs.pop("club_event", None)
        self.club = kwargs.pop("club", None)
        super().__init__(*args, **kwargs)

        # Filter teams to those in the club
        if self.club:
            self.fields["team"].queryset = Team.objects.filter(
                club=self.club,
                is_active=True,
            )

        # Filter cars and members based on the event
        if self.club_event:
            # Available cars from the event
            if self.club_event.base_event:
                self.fields["assigned_sim_car"].queryset = SimCar.objects.filter(
                    simulator=self.club_event.base_event.simulator,
                    is_active=True,
                )

            # Available signups that haven't been assigned yet
            self.fields["selected_members"].queryset = EventSignup.objects.filter(
                club_event=self.club_event,
                assigned_team__isnull=True,
            )

    def clean(self):
        cleaned_data = super().clean()

        # Validate team size constraints
        selected_members = cleaned_data.get("selected_members", [])
        if self.club_event:
            if len(selected_members) < self.club_event.team_size_min:
                raise ValidationError(
                    f"Team must have at least {self.club_event.team_size_min} members.",
                )
            if len(selected_members) > self.club_event.team_size_max:
                raise ValidationError(
                    f"Team cannot have more than {self.club_event.team_size_max} members.",
                )

        return cleaned_data

    def save(self):
        """Create the team allocation and assign members"""
        team_allocation = TeamAllocation.objects.create(
            club_event=self.club_event,
            team=self.cleaned_data["team"],
            assigned_sim_car=self.cleaned_data["assigned_sim_car"],
            created_by=self.club.created_by,  # Would be passed from view
        )

        # Create team allocation members
        for signup in self.cleaned_data["selected_members"]:
            TeamAllocationMember.objects.create(
                team_allocation=team_allocation,
                event_signup=signup,
                role="driver" if signup.can_drive else "spotter",
            )

            # Update the signup with team assignment
            signup.assigned_team = self.cleaned_data["team"]
            signup.assigned_at = timezone.now()
            signup.save()

        return team_allocation


# ===== ENHANCED FORMS FOR UNIFIED EVENT PARTICIPATION SYSTEM =====

class EnhancedEventSignupForm(forms.Form):
    """Enhanced form for event participation with availability support"""
    
    preferred_car = forms.ModelChoiceField(
        queryset=SimCar.objects.none(),
        widget=forms.Select(attrs={'class': 'w-full rounded-md border-gray-300'}),
        help_text="Your preferred car for this event"
    )
    
    backup_car = forms.ModelChoiceField(
        queryset=SimCar.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'w-full rounded-md border-gray-300'}),
        help_text="Alternative car choice (optional)"
    )
    
    EXPERIENCE_CHOICES = [
        ('beginner', 'Beginner'),
        ('intermediate', 'Intermediate'),
        ('advanced', 'Advanced'),
        ('professional', 'Professional'),
    ]
    
    experience_level = forms.ChoiceField(
        choices=EXPERIENCE_CHOICES,
        widget=forms.Select(attrs={'class': 'w-full rounded-md border-gray-300'})
    )
    
    max_stint_duration = forms.IntegerField(
        initial=60,
        min_value=15,
        max_value=180,
        widget=forms.NumberInput(attrs={
            'class': 'w-full rounded-md border-gray-300',
            'placeholder': '60'
        }),
        help_text="Maximum time you want to drive continuously (minutes)"
    )
    
    min_rest_duration = forms.IntegerField(
        initial=15,
        min_value=5,
        max_value=60,
        widget=forms.NumberInput(attrs={
            'class': 'w-full rounded-md border-gray-300',
            'placeholder': '15'
        }),
        help_text="Minimum break time needed between driving stints (minutes)"
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full rounded-md border-gray-300',
            'rows': 3,
            'placeholder': 'Any additional notes about your availability or preferences...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        event = kwargs.pop('event', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if event:
            # Filter cars based on event simulator
            available_cars = SimCar.objects.filter(
                simulator=event.simulator,
                is_active=True
            )
            self.fields['preferred_car'].queryset = available_cars
            self.fields['backup_car'].queryset = available_cars
        
    def clean(self):
        cleaned_data = super().clean()
        preferred_car = cleaned_data.get('preferred_car')
        backup_car = cleaned_data.get('backup_car')
        max_stint = cleaned_data.get('max_stint_duration')
        min_rest = cleaned_data.get('min_rest_duration')
        
        # Validate car choices
        if preferred_car and backup_car and preferred_car == backup_car:
            raise ValidationError("Backup car must be different from preferred car")
        
        # Validate stint durations
        if max_stint and max_stint < 15:
            raise ValidationError("Maximum stint duration must be at least 15 minutes")
        
        if min_rest and min_rest < 5:
            raise ValidationError("Minimum rest duration must be at least 5 minutes")
        
        return cleaned_data

    def save(self, event=None, user=None, commit=True):
        """Create event participation - placeholder implementation"""
        # This will be enhanced when the models are fully implemented
        # For now, return a mock object
        from types import SimpleNamespace
        
        participation = SimpleNamespace()
        participation.event = event
        participation.user = user
        participation.preferred_car = self.cleaned_data['preferred_car']
        participation.backup_car = self.cleaned_data['backup_car']
        participation.experience_level = self.cleaned_data['experience_level']
        participation.max_stint_duration = self.cleaned_data['max_stint_duration']
        participation.min_rest_duration = self.cleaned_data['min_rest_duration']
        participation.notes = self.cleaned_data['notes']
        
        return participation


class TeamFormationSettingsForm(forms.Form):
    """Form for team formation settings"""
    
    ALGORITHM_CHOICES = [
        ('availability', 'Availability Based'),
        ('balanced', 'Balanced Experience'),
        ('manual', 'Manual Selection'),
    ]
    
    team_size = forms.IntegerField(
        min_value=2,
        max_value=6,
        initial=3,
        widget=forms.NumberInput(attrs={'class': 'w-full rounded-md border-gray-300'})
    )
    
    max_teams = forms.IntegerField(
        required=False,
        min_value=1,
        max_value=20,
        widget=forms.NumberInput(attrs={
            'class': 'w-full rounded-md border-gray-300',
            'placeholder': 'No limit'
        })
    )
    
    algorithm = forms.ChoiceField(
        choices=ALGORITHM_CHOICES,
        initial='availability',
        widget=forms.Select(attrs={'class': 'w-full rounded-md border-gray-300'})
    )
    
    min_overlap_hours = forms.FloatField(
        initial=4.0,
        min_value=1.0,
        max_value=24.0,
        widget=forms.NumberInput(attrs={
            'class': 'w-full rounded-md border-gray-300',
            'step': '0.5'
        }),
        help_text="Minimum availability overlap required between team members"
    )
    
    balance_experience = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300'}),
        help_text="Try to balance experience levels within teams"
    )
