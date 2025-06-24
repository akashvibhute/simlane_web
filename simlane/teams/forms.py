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
from .models import Team
# Removed imports: EventSignup, EventSignupAvailability, TeamAllocation, TeamAllocationMember
# These models have been replaced by the enhanced participation system

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
                "class": "form-control",
                "type": "datetime-local",
            },
        ),
        help_text="Deadline for event signups",
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
                    "placeholder": "Event signup title",
                },
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Event description and details...",
                },
            ),
            "max_participants": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "placeholder": "Maximum participants",
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
                    "placeholder": "Minimum team size",
                },
            ),
            "team_size_max": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": 1,
                    "placeholder": "Maximum team size",
                },
            ),
        }

    def __init__(self, *args, **kwargs):
        self.club = kwargs.pop("club", None)
        super().__init__(*args, **kwargs)

        # Filter available events
        if self.club:
            self.fields["base_event"].queryset = Event.objects.filter(
                start_time__gte=timezone.now(),
            ).order_by("start_time")

    def clean(self):
        cleaned_data = super().clean()

        # Validate team size constraints
        requires_teams = cleaned_data.get("requires_team_assignment", False)
        team_size_min = cleaned_data.get("team_size_min")
        team_size_max = cleaned_data.get("team_size_max")

        if requires_teams:
            if not team_size_min or team_size_min < 1:
                raise ValidationError("Minimum team size is required for team events.")
            if not team_size_max or team_size_max < team_size_min:
                raise ValidationError("Maximum team size must be greater than minimum.")

        # Validate signup deadline
        signup_deadline = cleaned_data.get("signup_deadline")
        base_event = cleaned_data.get("base_event")

        if signup_deadline and base_event:
            if signup_deadline >= base_event.start_time:
                raise ValidationError("Signup deadline must be before event start time.")

        return cleaned_data


# Legacy form classes removed (EventSignupForm, EventSignupAvailabilityForm, TeamAllocationForm)
# These depended on removed models: EventSignup, EventSignupAvailability, TeamAllocation, TeamAllocationMember
# Use EnhancedEventSignupForm for new participation system


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
            'placeholder': 'Any additional notes or preferences...'
        }),
        help_text="Optional notes about your participation"
    )
    
    def __init__(self, *args, **kwargs):
        self.event = kwargs.pop('event', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set up car choices based on event simulator
        if self.event and self.event.simulator:
            available_cars = SimCar.objects.filter(
                simulator=self.event.simulator,
                is_active=True
            )
            self.fields['preferred_car'].queryset = available_cars
            self.fields['backup_car'].queryset = available_cars
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Ensure preferred and backup cars are different
        preferred_car = cleaned_data.get('preferred_car')
        backup_car = cleaned_data.get('backup_car')
        
        if preferred_car and backup_car and preferred_car == backup_car:
            raise ValidationError("Preferred and backup cars must be different")
        
        return cleaned_data
    
    def save(self, event=None, user=None, commit=True):
        """Create EventParticipation instance"""
        from .models import EventParticipation
        
        if not commit:
            return None
            
        participation = EventParticipation.objects.create(
            event=event or self.event,
            user=user or self.user,
            participation_type='team_signup',
            status='signed_up',
            preferred_car=self.cleaned_data['preferred_car'],
            backup_car=self.cleaned_data.get('backup_car'),
            experience_level=self.cleaned_data['experience_level'],
            max_stint_duration=self.cleaned_data['max_stint_duration'],
            min_rest_duration=self.cleaned_data['min_rest_duration'],
            notes=self.cleaned_data.get('notes', ''),
            signed_up_at=timezone.now()
        )
        
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
        help_text="Try to balance experience levels across teams"
    )
