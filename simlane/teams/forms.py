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
# ClubEvent removed - using sim.Event.organizing_club instead
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
        fields = [
            "name", 
            "description", 
            "logo", 
            "website", 
            "discord_url",
            "twitter_url", 
            "youtube_url", 
            "twitch_url", 
            "facebook_url", 
            "instagram_url"
        ]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "Enter club name",
                    "required": True,
                },
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-input",
                    "rows": 4,
                    "placeholder": "Describe your club...",
                },
            ),
            "logo": forms.ClearableFileInput(
                attrs={
                    "class": "form-input",
                    "accept": "image/*",
                },
            ),
            "website": forms.URLInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "https://example.com",
                },
            ),
            "discord_url": forms.URLInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "https://discord.gg/yourserver",
                },
            ),
            "twitter_url": forms.URLInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "https://twitter.com/yourclub",
                },
            ),
            "youtube_url": forms.URLInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "https://youtube.com/@yourclub",
                },
            ),
            "twitch_url": forms.URLInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "https://twitch.tv/yourclub",
                },
            ),
            "facebook_url": forms.URLInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "https://facebook.com/yourclub",
                },
            ),
            "instagram_url": forms.URLInput(
                attrs={
                    "class": "form-input",
                    "placeholder": "https://instagram.com/yourclub",
                },
            ),
        }
        help_texts = {
            "name": "Choose a unique name for your club",
            "description": "Tell potential members what your club is about",
            "logo": "Upload your club logo (JPG, PNG, or GIF)",
            "website": "Your club website (optional)",
            "discord_url": "Discord server invite link (optional)",
            "twitter_url": "Twitter/X profile URL (optional)",
            "youtube_url": "YouTube channel URL (optional)",
            "twitch_url": "Twitch channel URL (optional)",
            "facebook_url": "Facebook page URL (optional)",
            "instagram_url": "Instagram profile URL (optional)",
        }

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if Club.objects.filter(name__iexact=name).exists():
            raise ValidationError("A club with this name already exists.")
        return name

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo:
            # Validate file size (max 5MB)
            if logo.size > 5 * 1024 * 1024:
                raise ValidationError("Logo file size must be less than 5MB.")
            
            # Validate file type
            valid_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
            if logo.content_type not in valid_types:
                raise ValidationError("Logo must be a JPEG, PNG, GIF, or WebP image.")
        
        return logo


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
                "class": "form-input",
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
                "class": "form-select",
            },
        ),
        help_text="Role the invited user will have in this club",
    )

    personal_message = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-input",
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


class ClubEventSignupSheetForm(forms.ModelForm):
    """Form for club admins to create event signup sheets"""
    
    class Meta:
        from .models import ClubEventSignupSheet
        model = ClubEventSignupSheet
        fields = [
            'event',
            'title',
            'description',
            'signup_opens',
            'signup_closes',
            'max_teams',
            'target_team_size',
            'min_drivers_per_team',
            'max_drivers_per_team',
            'min_license_level',
            'notes_for_admins',
        ]
        widgets = {
            'event': forms.Select(
                attrs={
                    'class': 'form-select',
                    'required': True,
                }
            ),
            'title': forms.TextInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': 'e.g., "24h Le Mans Team Signup"',
                    'required': True,
                }
            ),
            'description': forms.Textarea(
                attrs={
                    'class': 'form-input',
                    'rows': 4,
                    'placeholder': 'Provide details about this event signup for club members...',
                }
            ),
            'signup_opens': forms.DateTimeInput(
                attrs={
                    'class': 'form-input',
                    'type': 'datetime-local',
                    'required': True,
                },
                format='%Y-%m-%dT%H:%M',
            ),
            'signup_closes': forms.DateTimeInput(
                attrs={
                    'class': 'form-input',
                    'type': 'datetime-local',
                    'required': True,
                },
                format='%Y-%m-%dT%H:%M',
            ),
            'max_teams': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': 'Leave blank for no limit',
                    'min': 1,
                }
            ),
            'target_team_size': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'min': 2,
                    'max': 10,
                }
            ),
            'min_drivers_per_team': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'min': 1,
                    'max': 10,
                }
            ),
            'max_drivers_per_team': forms.NumberInput(
                attrs={
                    'class': 'form-input',
                    'min': 2,
                    'max': 20,
                }
            ),
            'min_license_level': forms.TextInput(
                attrs={
                    'class': 'form-input',
                    'placeholder': 'e.g., "C4.0" (optional)',
                }
            ),
            'notes_for_admins': forms.Textarea(
                attrs={
                    'class': 'form-input',
                    'rows': 3,
                    'placeholder': 'Internal notes for club admins (not visible to members)...',
                }
            ),
        }
    
    def __init__(self, *args, **kwargs):
        self.club = kwargs.pop('club', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Only show events that are not already opened by this club
        if self.club:
            # Get events already with signup sheets for this club
            existing_event_ids = self.club.event_signup_sheets.values_list('event_id', flat=True)
            
            # Filter to available events
            self.fields['event'].queryset = Event.objects.exclude(
                id__in=existing_event_ids
            ).filter(
                # Only future events or events with instances in the future
                instances__start_time__gt=timezone.now()
            ).distinct().order_by('instances__start_time')
        
        # Convert datetime fields to local timezone for display
        if self.instance and self.instance.pk:
            if self.instance.signup_opens:
                self.initial['signup_opens'] = self.instance.signup_opens.strftime('%Y-%m-%dT%H:%M')
            if self.instance.signup_closes:
                self.initial['signup_closes'] = self.instance.signup_closes.strftime('%Y-%m-%dT%H:%M')
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate signup window
        signup_opens = cleaned_data.get('signup_opens')
        signup_closes = cleaned_data.get('signup_closes')
        
        if signup_opens and signup_closes:
            if signup_closes <= signup_opens:
                raise ValidationError("Signup close time must be after open time")
            
            # Check that signup opens before event starts
            event = cleaned_data.get('event')
            if event:
                earliest_instance = event.instances.order_by('start_time').first()
                if earliest_instance and signup_closes > earliest_instance.start_time:
                    raise ValidationError(
                        f"Signups must close before the event starts ({earliest_instance.start_time})"
                    )
        
        # Validate team size constraints
        min_drivers = cleaned_data.get('min_drivers_per_team')
        max_drivers = cleaned_data.get('max_drivers_per_team')
        target_size = cleaned_data.get('target_team_size')
        
        if min_drivers and max_drivers and min_drivers > max_drivers:
            raise ValidationError("Minimum drivers cannot be greater than maximum drivers")
        
        if target_size:
            if min_drivers and target_size < min_drivers:
                raise ValidationError("Target team size cannot be less than minimum drivers")
            if max_drivers and target_size > max_drivers:
                raise ValidationError("Target team size cannot be greater than maximum drivers")
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Set the club and creator
        if self.club:
            instance.club = self.club
        if self.user:
            instance.created_by = self.user
        
        # Auto-open if signup time has passed
        if instance.signup_opens <= timezone.now() and instance.status == 'draft':
            instance.status = 'open'
        
        if commit:
            instance.save()
        
        return instance


class ClubEventSignupBulkCreateForm(forms.Form):
    """Form for creating multiple event signup sheets at once"""
    
    # Event selection with multi-select
    events = forms.ModelMultipleChoiceField(
        queryset=Event.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'rounded border-gray-300 text-blue-600 focus:ring-blue-500'
        }),
        help_text="Select multiple events to create signup sheets for"
    )
    
    # Shared settings for all selected events
    title_template = forms.CharField(
        max_length=255,
        initial="{event_name} - Team Signup",
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Use {event_name} for event name, {date} for date'
        }),
        help_text="Title template for signup sheets. Use {event_name} and {date} as placeholders"
    )
    
    description_template = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-input',
            'rows': 3,
            'placeholder': 'Description template for all signup sheets...'
        }),
        help_text="Shared description for all signup sheets"
    )
    
    # Signup timing
    TIMING_CHOICES = [
        ('immediate', 'Open immediately'),
        ('relative', 'Relative to event start'),
        ('fixed', 'Fixed date/time'),
    ]
    
    signup_timing = forms.ChoiceField(
        choices=TIMING_CHOICES,
        initial='relative',
        widget=forms.RadioSelect(attrs={'class': 'text-blue-600'}),
        help_text="How to set signup open/close times"
    )
    
    # For relative timing
    days_before_open = forms.IntegerField(
        initial=14,
        min_value=1,
        max_value=365,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '14'
        }),
        help_text="Days before event to open signups"
    )
    
    days_before_close = forms.IntegerField(
        initial=2,
        min_value=0,
        max_value=30,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': '2'
        }),
        help_text="Days before event to close signups"
    )
    
    # For fixed timing
    fixed_signup_opens = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-input',
            'type': 'datetime-local'
        }),
        help_text="Fixed open time (only used if 'Fixed date/time' is selected)"
    )
    
    fixed_signup_closes = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={
            'class': 'form-input',
            'type': 'datetime-local'
        }),
        help_text="Fixed close time (only used if 'Fixed date/time' is selected)"
    )
    
    # Team formation settings (shared)
    max_teams = forms.IntegerField(
        required=False,
        min_value=1,
        widget=forms.NumberInput(attrs={
            'class': 'form-input',
            'placeholder': 'No limit'
        }),
        help_text="Maximum teams per event (leave blank for no limit)"
    )
    
    target_team_size = forms.IntegerField(
        initial=4,
        min_value=2,
        max_value=10,
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    
    min_drivers_per_team = forms.IntegerField(
        initial=2,
        min_value=1,
        max_value=10,
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    
    max_drivers_per_team = forms.IntegerField(
        initial=6,
        min_value=2,
        max_value=20,
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    
    # Requirements
    min_license_level = forms.CharField(
        required=False,
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g., C4.0'
        })
    )
    
    # Template saving
    save_as_template = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'rounded border-gray-300'}),
        help_text="Save these settings as a template for future use"
    )
    
    template_name = forms.CharField(
        required=False,
        max_length=100,
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'Template name...'
        }),
        help_text="Name for this template (required if saving as template)"
    )
    
    def __init__(self, *args, **kwargs):
        self.club = kwargs.pop('club', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.club:
            # Get events that don't already have signup sheets for this club
            existing_event_ids = self.club.event_signup_sheets.values_list('event_id', flat=True)
            
            # Show upcoming events only
            available_events = Event.objects.exclude(
                id__in=existing_event_ids
            ).filter(
                instances__start_time__gt=timezone.now()
            ).distinct().order_by('instances__start_time')
            
            self.fields['events'].queryset = available_events
    
    def clean(self):
        cleaned_data = super().clean()
        
        # Validate timing settings
        timing = cleaned_data.get('signup_timing')
        
        if timing == 'fixed':
            opens = cleaned_data.get('fixed_signup_opens')
            closes = cleaned_data.get('fixed_signup_closes')
            
            if not opens or not closes:
                raise ValidationError("Fixed open and close times are required when using fixed timing")
            
            if closes <= opens:
                raise ValidationError("Close time must be after open time")
        
        elif timing == 'relative':
            days_open = cleaned_data.get('days_before_open')
            days_close = cleaned_data.get('days_before_close')
            
            if days_close >= days_open:
                raise ValidationError("Signup must close closer to event than it opens")
        
        # Validate team settings
        min_drivers = cleaned_data.get('min_drivers_per_team')
        max_drivers = cleaned_data.get('max_drivers_per_team')
        target_size = cleaned_data.get('target_team_size')
        
        if min_drivers and max_drivers and min_drivers > max_drivers:
            raise ValidationError("Minimum drivers cannot be greater than maximum drivers")
        
        if target_size:
            if min_drivers and target_size < min_drivers:
                raise ValidationError("Target team size cannot be less than minimum drivers")
            if max_drivers and target_size > max_drivers:
                raise ValidationError("Target team size cannot be greater than maximum drivers")
        
        # Validate template saving
        save_template = cleaned_data.get('save_as_template')
        template_name = cleaned_data.get('template_name')
        
        if save_template and not template_name:
            raise ValidationError("Template name is required when saving as template")
        
        return cleaned_data
    
    def create_signup_sheets(self):
        """Create signup sheets for all selected events"""
        from datetime import timedelta
        
        events = self.cleaned_data['events']
        created_sheets = []
        
        for event in events:
            # Calculate signup times based on timing method
            timing = self.cleaned_data['signup_timing']
            
            if timing == 'immediate':
                signup_opens = timezone.now()
                # Close 2 days before event by default
                earliest_instance = event.instances.order_by('start_time').first()
                if earliest_instance:
                    signup_closes = earliest_instance.start_time - timedelta(days=2)
                else:
                    signup_closes = timezone.now() + timedelta(days=7)  # Fallback
            
            elif timing == 'fixed':
                signup_opens = self.cleaned_data['fixed_signup_opens']
                signup_closes = self.cleaned_data['fixed_signup_closes']
            
            else:  # relative
                earliest_instance = event.instances.order_by('start_time').first()
                if earliest_instance:
                    signup_opens = earliest_instance.start_time - timedelta(
                        days=self.cleaned_data['days_before_open']
                    )
                    signup_closes = earliest_instance.start_time - timedelta(
                        days=self.cleaned_data['days_before_close']
                    )
                else:
                    # Fallback if no instances
                    signup_opens = timezone.now()
                    signup_closes = timezone.now() + timedelta(days=7)
            
            # Generate title from template
            title_template = self.cleaned_data['title_template']
            title = title_template.format(
                event_name=event.name,
                date=earliest_instance.start_time.strftime('%b %d') if earliest_instance else 'TBD'
            )
            
            # Create the signup sheet
            sheet = ClubEventSignupSheet.objects.create(
                club=self.club,
                event=event,
                created_by=self.user,
                title=title,
                description=self.cleaned_data.get('description_template', ''),
                signup_opens=signup_opens,
                signup_closes=signup_closes,
                max_teams=self.cleaned_data.get('max_teams'),
                target_team_size=self.cleaned_data['target_team_size'],
                min_drivers_per_team=self.cleaned_data['min_drivers_per_team'],
                max_drivers_per_team=self.cleaned_data['max_drivers_per_team'],
                min_license_level=self.cleaned_data.get('min_license_level', ''),
                status='open' if signup_opens <= timezone.now() else 'draft'
            )
            
            created_sheets.append(sheet)
        
        # Save as template if requested
        if self.cleaned_data.get('save_as_template'):
            self._save_template()
        
        return created_sheets
    
    def _save_template(self):
        """Save form settings as a reusable template"""
        # TODO: Implement template saving
        # This would create a SignupSheetTemplate model
        pass


# ClubEventCreateForm removed - using sim.Event.organizing_club instead


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
