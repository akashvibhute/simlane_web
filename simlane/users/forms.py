from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django import forms
from django.contrib.auth import forms as admin_forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from simlane.sim.models import SimProfile
from simlane.sim.models import Simulator

User = get_user_model()


class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):  # type: ignore[name-defined]
        model = User


class UserAdminCreationForm(admin_forms.UserCreationForm):
    """
    Form for User Creation in the Admin Area.
    To change user signup, see UserSignupForm and UserSocialSignupForm.
    """

    class Meta(admin_forms.UserCreationForm.Meta):  # type: ignore[name-defined]
        model = User
        error_messages = {
            "username": {"unique": _("This username has already been taken.")},
        }


class UserUpdateForm(forms.ModelForm):
    """Form for updating user profile information."""

    class Meta:
        model = User
        fields = ["name", "email"]
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full rounded-md border-gray-300 shadow-sm "
                        "focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    ),
                    "placeholder": "Enter your full name",
                },
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": (
                        "mt-1 block w-full rounded-md border-gray-300 shadow-sm "
                        "focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    ),
                    "placeholder": "Enter your email address",
                },
            ),
        }
        labels = {
            "name": "Full Name",
            "email": "Email Address",
        }


class UserSignupForm(SignupForm):
    """
    Form that will be rendered on a user sign up section/screen.
    Default fields will be added automatically.
    Check UserSocialSignupForm for accounts created from social.
    """


class UserSocialSignupForm(SocialSignupForm):
    """
    Renders the form when user has signed up using social accounts.
    Default fields will be added automatically.
    See UserSignupForm otherwise.
    """


class SimProfileForm(forms.ModelForm):
    """Form for creating and editing sim racing profiles."""

    class Meta:
        model = SimProfile
        fields = ["simulator", "profile_name", "sim_api_id"]
        widgets = {
            "simulator": forms.Select(
                attrs={
                    "class": (
                        "mt-1 block w-full rounded-md border-gray-300 shadow-sm "
                        "focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    ),
                },
            ),
            "profile_name": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full rounded-md border-gray-300 shadow-sm "
                        "focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    ),
                    "placeholder": "Enter your profile name",
                },
            ),
            "sim_api_id": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full rounded-md border-gray-300 shadow-sm "
                        "focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    ),
                    "placeholder": "External ID (optional)",
                },
            ),
        }
        labels = {
            "simulator": "Simulator",
            "profile_name": "Profile Name",
            "sim_api_id": "External Data ID",
        }
        help_texts = {
            "profile_name": "Your username or display name in the simulator",
            "sim_api_id": (
                "Optional: Your customer/user ID in the simulator "
                "(e.g., iRacing customer ID)"
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        # Only show active simulators
        self.fields["simulator"].queryset = Simulator.objects.filter(
            is_active=True,
        ).order_by("name")

    def clean(self):
        cleaned_data = super().clean()
        simulator = cleaned_data.get("simulator")
        profile_name = cleaned_data.get("profile_name")

        if simulator and profile_name and self.user:
            # Check for duplicate profile names for the same user and simulator
            # This is handled by the model's unique_together constraint,
            # but we can provide a better error message
            existing_profile = SimProfile.objects.filter(
                user=self.user,
                simulator=simulator,
                profile_name=profile_name,
            )

            # Exclude the current instance if we're editing
            if self.instance.pk:
                existing_profile = existing_profile.exclude(pk=self.instance.pk)

            if existing_profile.exists():
                error_msg = (
                    f'You already have a profile named "{profile_name}" '
                    f"for {simulator.name}."
                )
                raise forms.ValidationError(error_msg)

        return cleaned_data
