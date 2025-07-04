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
        fields = ["profile_image", "timezone"]
        widgets = {
            "profile_image": forms.FileInput(
                attrs={
                    "class": (
                        "mt-1 block w-full text-sm text-gray-900 dark:text-gray-300 "
                        "file:mr-4 file:py-2 file:px-4 file:rounded-md file:border-0 "
                        "file:text-sm file:font-semibold file:bg-primary-50 file:text-primary-700 "
                        "hover:file:bg-primary-100 dark:file:bg-primary-900 dark:file:text-primary-300 "
                        "dark:hover:file:bg-primary-800"
                    ),
                    "accept": "image/*",
                },
            ),
            "timezone": forms.Select(
                attrs={
                    "class": (
                        "mt-1 block w-full rounded-md border-gray-300 shadow-sm "
                        "focus:border-primary-500 focus:ring-primary-500 sm:text-sm "
                        "dark:bg-gray-700 dark:border-gray-600 dark:text-white "
                        "dark:focus:border-primary-400 dark:focus:ring-primary-400"
                    ),
                },
            ),
        }
        labels = {
            "profile_image": "Profile Picture",
            "timezone": "Timezone",
        }
        help_texts = {
            "profile_image": "Upload a square image for best results (max 2MB)",
            "timezone": "Select your timezone for displaying dates and times",
        }


class UserSignupForm(SignupForm):
    """
    Form that will be rendered on a user sign up section/screen.
    Default fields will be added automatically.
    Check UserSocialSignupForm for accounts created from social.
    """

    timezone = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.HiddenInput(),
        initial="UTC",
    )

    def save(self, request):
        user = super().save(request)
        # Set timezone if provided
        if self.cleaned_data.get("timezone"):
            user.timezone = self.cleaned_data["timezone"]
            user.save()
        return user


class UserSocialSignupForm(SocialSignupForm):
    """
    Renders the form when user has signed up using social accounts.
    Default fields will be added automatically.
    See UserSignupForm otherwise.
    """

    timezone = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.HiddenInput(),
        initial="UTC",
    )

    def save(self, request):
        user = super().save(request)
        # Set timezone if provided
        if self.cleaned_data.get("timezone"):
            user.timezone = self.cleaned_data["timezone"]
            user.save()
        return user


class SimProfileForm(forms.ModelForm):
    """Form for creating and editing sim racing profiles."""

    class Meta:
        model = SimProfile
        fields = ["simulator", "sim_api_id"]
        widgets = {
            "simulator": forms.Select(
                attrs={
                    "class": (
                        "mt-1 block w-full rounded-md border-gray-300 shadow-sm "
                        "focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    ),
                },
            ),
            "sim_api_id": forms.TextInput(
                attrs={
                    "class": (
                        "mt-1 block w-full rounded-md border-gray-300 shadow-sm "
                        "focus:border-primary-500 focus:ring-primary-500 sm:text-sm"
                    ),
                    "placeholder": "Enter your iRacing customer ID",
                    "required": True,
                },
            ),
        }
        labels = {
            "simulator": "Simulator",
            "sim_api_id": "iRacing Customer ID",
        }
        help_texts = {
            "sim_api_id": (
                "Your iRacing customer ID (required) - we'll fetch your profile data automatically"
            ),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        # Only show iRacing for now
        self.fields["simulator"].queryset = Simulator.objects.filter(
            name="iRacing",
            is_active=True,
        )
        # Make sim_api_id required
        self.fields["sim_api_id"].required = True

    def clean_sim_api_id(self):
        """Validate iRacing customer ID format."""
        sim_api_id = self.cleaned_data.get("sim_api_id")
        if sim_api_id:
            # Remove any whitespace
            sim_api_id = sim_api_id.strip()
            # Check if it's a valid number
            try:
                int(sim_api_id)
            except ValueError:
                raise forms.ValidationError(
                    "iRacing customer ID must be a number (e.g., 123456)",
                )
        return sim_api_id

    def clean(self):
        cleaned_data = super().clean()
        simulator = cleaned_data.get("simulator")
        sim_api_id = cleaned_data.get("sim_api_id")

        if simulator and sim_api_id and self.user:
            # Check if user already has this profile linked
            existing_profile = SimProfile.objects.filter(
                linked_user=self.user,
                simulator=simulator,
                sim_api_id=sim_api_id,
            )

            # Exclude the current instance if we're editing
            if self.instance.pk:
                existing_profile = existing_profile.exclude(pk=self.instance.pk)

            if existing_profile.exists():
                error_msg = f"You already have an iRacing profile with customer ID {sim_api_id}."
                raise forms.ValidationError(error_msg)

            # Check if profile exists and is linked to another user
            existing_any_profile = SimProfile.objects.filter(
                simulator=simulator,
                sim_api_id=sim_api_id,
            )

            if self.instance.pk:
                existing_any_profile = existing_any_profile.exclude(pk=self.instance.pk)

            if existing_any_profile.exists():
                existing_profile = existing_any_profile.first()
                if (
                    existing_profile.linked_user
                    and existing_profile.linked_user != self.user
                ):
                    error_msg = (
                        f"iRacing profile with customer ID {sim_api_id} is already "
                        "linked to another user."
                    )
                    raise forms.ValidationError(error_msg)
                # If profile exists but is unlinked, that's fine - we'll allow linking it
                # We need to temporarily exclude this instance from model validation
                # to avoid the unique_together constraint error
                self._existing_unlinked_profile = existing_profile

        return cleaned_data

    def validate_unique(self):
        """Override to skip unique validation when we have an existing unlinked profile."""
        # Check if we have an existing unlinked profile we want to link
        if (
            hasattr(self, "_existing_unlinked_profile")
            and self._existing_unlinked_profile
        ):
            # Skip model validation since we'll handle linking in the view
            return
        # Otherwise, run normal validation
        super().validate_unique()
